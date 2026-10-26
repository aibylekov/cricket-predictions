"""
stack_form_gender.py - PER-GENDER form-anchored stacker on top of v3.1.

Extension of src/model/stack_form.py (the GLOBAL stacker). The global stacker
learns ONE form weight from men+women; its weight is dominated by men's
matches, while form is a much stronger signal on WBBL. Here the stacker is
fit SEPARATELY PER GENDER, so the women's form weight comes from women's
matches only. Reads L3 only; writes only the comparison report. It does NOT
switch production (payload.py keeps logistic_v2 until the user confirms).

PER-GENDER STACKER (pre-declared before the run)
------------------------------------------------
  For gender g: p_final = sigmoid(b0_g + b1_g*logit(p_v3.1)
                                  + b2_g*form_gap_tourn + b3_g*form_gap_last5)
  Same inputs as the global stacker minus the gender flag; same clip, same
  NULL-gap = 0 convention, LogisticRegression C = 1.0.

WALK-FORWARD (same discipline as stack_form.py)
-----------------------------------------------
  Level 1: v3.1 OOF predictions from validation.walk_forward (each from a
           model trained before its own month).
  Level 2: for month M and gender g, the g-stacker is fit ONLY on level-1
           OOF rows of gender g for matches strictly before the first day of
           M, then applied to month M's gender-g rows. Cold start PER GENDER:
           fewer than STACK_MIN_TRAIN (200) gender-g rows -> p_v3.1 passes
           through unchanged for that gender.

STABILITY RULE (pre-declared; decides primary vs fallback)
----------------------------------------------------------
  The per-gender stacker is the candidate unless the WOMEN's coefficient on
  logit(p_v3.1) or on form_gap_tourn changes sign between consecutive monthly
  fits more than MAX_SIGN_FLIPS (2) times after the cold start. In that case
  the fallback - ONE stacker with gender interactions (inputs + is_female +
  is_female x each input) - becomes the candidate. The interaction model is
  reported as a sensitivity row either way.

ADOPTION BAR (refined by the user; all must pass; production NOT switched)
--------------------------------------------------------------------------
  1. WBBL: candidate must MATCH OR BEAT form_favourite on log_loss AND brier,
     "match" = the 95% paired month-block bootstrap interval of
     (candidate - form) includes zero (beat = whole interval below zero).
  2. MEN: candidate must not regress vs the GLOBAL stacker (now the men's
     benchmark): candidate <= global stacker on log_loss AND brier (point
     estimate; interval shown as context).
  3. WOMEN overall: candidate must not regress vs v3.1: candidate <= v3.1 on
     log_loss AND brier (point estimate; interval shown as context).

Run:
    venv/Scripts/python.exe -m src.model.stack_form_gender
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from src.content.framing import BAND_CONFIG
from src.model.baselines import baseline_form_favourite
from src.model.retrain_men_women import (
    WBBL, _cal5, _metrics, band_table, paired_block_bootstrap,
    predict_pooled, predict_v2_per_gender,
)
from src.model.stack_form import STACK_C, STACK_MIN_TRAIN, make_stacker, stack_features
from src.model.validation import IPL, calibration, load_completed, walk_forward

ROOT = Path(__file__).resolve().parents[2]
REPORT_MD = ROOT / "docs" / "model" / "stack_per_gender_report.md"
REPORT_JSON = REPORT_MD.with_suffix(".json")
MAX_SIGN_FLIPS = 2
COEF_NAMES = ["logit(p_v3.1)", "form_gap_tourn", "form_gap_last5"]

MODELS = ["v2", "v3_1", "stack_global", "stack_pg", "form"]
LABEL = {"v2": "v2 per-gender (PRODUCTION)", "v3_1": "v3.1 pooled",
         "stack_global": "global stacker (men's benchmark)",
         "stack_pg": "per-gender stacker (CANDIDATE)",
         "stack_ix": "interaction stacker (fallback / sensitivity)",
         "form": "form_favourite (bar)"}
SHORT = {"v2": "v2", "v3_1": "v3.1", "stack_global": "glob", "stack_pg": "pg",
         "stack_ix": "ix", "form": "form"}


# --------------------------------------------------------------------------
# stackers
# --------------------------------------------------------------------------
def make_per_gender_stacker(level1: pd.Series, log: dict):
    """Harness predictor: one stacker per gender, each fit on its own gender's
    level-1 OOF rows from before the current block."""
    def predict(train: pd.DataFrame, current: pd.DataFrame) -> np.ndarray:
        assert train["match_date"].max() < current["match_date"].min()
        out = current["match_id"].map(level1).to_numpy(float).copy()  # pass-through default
        block = str(current["match_date"].min().to_period("M"))
        for g in current["gender"].unique():
            cm = (current["gender"] == g).to_numpy()
            tr = train[(train["gender"] == g) & train["match_id"].isin(level1.index)]
            if len(tr) < STACK_MIN_TRAIN or tr["y"].nunique() < 2:
                log["cold_start_ids"].extend(current.loc[cm, "match_id"].tolist())
                continue
            p_tr = tr["match_id"].map(level1).to_numpy(float)
            clf = LogisticRegression(C=STACK_C, max_iter=1000)
            clf.fit(stack_features(tr, p_tr, with_gender=False), tr["y"].to_numpy(int))
            cur = current[cm]
            out[cm] = clf.predict_proba(stack_features(
                cur, cur["match_id"].map(level1).to_numpy(float), with_gender=False))[:, 1]
            log["fits"].append({"gender": g, "block": block, "n_train": int(len(tr)),
                                "intercept": float(clf.intercept_[0]),
                                "coef": [float(c) for c in clf.coef_[0]]})
        return out
    return predict


def _ix_features(df: pd.DataFrame, p: np.ndarray) -> np.ndarray:
    base = stack_features(df, p, with_gender=False)
    fem = (df["gender"] == "female").astype(float).to_numpy()[:, None]
    return np.hstack([base, fem, base * fem])


def make_interaction_stacker(level1: pd.Series, log: dict):
    """Fallback: ONE stacker with gender interactions (pooled cold start)."""
    def predict(train: pd.DataFrame, current: pd.DataFrame) -> np.ndarray:
        assert train["match_date"].max() < current["match_date"].min()
        p_cur = current["match_id"].map(level1).to_numpy(float)
        tr = train[train["match_id"].isin(level1.index)]
        if len(tr) < STACK_MIN_TRAIN or tr["y"].nunique() < 2:
            log["cold_start_ids"].extend(current["match_id"].tolist())
            return p_cur
        clf = LogisticRegression(C=STACK_C, max_iter=1000)
        clf.fit(_ix_features(tr, tr["match_id"].map(level1).to_numpy(float)),
                tr["y"].to_numpy(int))
        return clf.predict_proba(_ix_features(current, p_cur))[:, 1]
    return predict


def stability(fits: list[dict], gender: str) -> dict:
    f = [x for x in fits if x["gender"] == gender]
    out = {"fits": len(f), "first_block": f[0]["block"] if f else None}
    for i, nm in enumerate(COEF_NAMES):
        signs = [np.sign(x["coef"][i]) for x in f]
        out[f"sign_flips_{nm}"] = int(sum(1 for a, b in zip(signs, signs[1:]) if a != b))
        vals = [x["coef"][i] for x in f]
        out[f"range_{nm}"] = [float(min(vals)), float(max(vals))] if vals else None
    out["unstable"] = (out.get("sign_flips_logit(p_v3.1)", 0) > MAX_SIGN_FLIPS
                       or out.get("sign_flips_form_gap_tourn", 0) > MAX_SIGN_FLIPS)
    return out


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------
def run() -> dict:
    df = load_completed(gender=None)
    oof = {}
    print("  level 1: v2 / v3.1 / form_favourite ...")
    for name, pred in (("v2", predict_v2_per_gender), ("v3_1", predict_pooled),
                       ("form", baseline_form_favourite)):
        o, _ = walk_forward(df, pred)
        oof[name] = o.set_index("match_id")
    level1 = oof["v3_1"]["p"]
    logs = {k: {"cold_start_ids": [], "fits": []} for k in ("stack_global", "stack_pg", "stack_ix")}
    print("  level 2: global / per-gender / interaction stackers ...")
    for name, maker in (("stack_global", lambda lg: make_stacker(level1, True, lg)),
                        ("stack_pg", lambda lg: make_per_gender_stacker(level1, lg)),
                        ("stack_ix", lambda lg: make_interaction_stacker(level1, lg))):
        o, _ = walk_forward(df, maker(logs[name]))
        oof[name] = o.set_index("match_id")

    all_models = MODELS + ["stack_ix"]
    base = oof["v3_1"][["match_date", "league_key", "gender", "y"]].copy()
    for name in all_models:
        base[name] = oof[name]["p"].reindex(base.index)
    common = base.dropna(subset=all_models).reset_index()
    common["season"] = common["match_date"].dt.year
    men, wom = common[common.gender == "male"], common[common.gender == "female"]
    wb, ipl = common[common.league_key == WBBL], common[common.league_key == IPL]

    stab = {g: stability(logs["stack_pg"]["fits"], g) for g in ("male", "female")}
    cand = "stack_ix" if stab["female"]["unstable"] else "stack_pg"

    def table(sub, models=all_models):
        return {m: _metrics(sub, m) for m in models}

    cold_pg = set(logs["stack_pg"]["cold_start_ids"])
    res = {"generated": datetime.now().isoformat(timespec="seconds"),
           "candidate": cand, "stability": stab, "max_sign_flips": MAX_SIGN_FLIPS,
           "stacker": {"inputs": COEF_NAMES, "C": STACK_C, "min_train_per_gender": STACK_MIN_TRAIN},
           "common_set": {"all": len(common), "male": len(men), "female": len(wom),
                          "wbbl": len(wb), "ipl": len(ipl),
                          "first_date": str(common.match_date.min().date()),
                          "last_date": str(common.match_date.max().date())},
           "cold_start_per_gender_in_common": {
               g: int(common.loc[common.gender == g, "match_id"].isin(cold_pg).sum())
               for g in ("male", "female")} | {"wbbl": int(wb["match_id"].isin(cold_pg).sum())},
           "band_config": BAND_CONFIG}
    res["overall"] = table(common)
    res["by_gender"] = {"male": table(men), "female": table(wom)}
    res["wbbl_metrics"] = table(wb)
    res["ipl_metrics"] = table(ipl)

    C = cand
    res["wbbl_vs_form"] = paired_block_bootstrap(wb, C, "form")
    res["men_vs_global"] = paired_block_bootstrap(men, C, "stack_global")
    res["women_vs_v3_1"] = paired_block_bootstrap(wom, C, "v3_1")
    res["context"] = {
        "wbbl_global_vs_form": paired_block_bootstrap(wb, "stack_global", "form"),
        "wbbl_v3_1_vs_form": paired_block_bootstrap(wb, "v3_1", "form"),
        "wbbl_cand_vs_global": paired_block_bootstrap(wb, C, "stack_global"),
        "women_cand_vs_form": paired_block_bootstrap(wom, C, "form"),
        "ipl_cand_vs_form": paired_block_bootstrap(ipl, C, "form"),
        "men_cand_vs_v2": paired_block_bootstrap(men, C, "v2")}

    def wbbl_check(key):
        lo, hi = res["wbbl_vs_form"][f"{key}_ci95"]
        return {"match": bool(lo <= 0 <= hi), "beat": bool(hi < 0),
                "pass": bool(lo <= 0)}           # pass = match or beat
    wbbl = {"log_loss": wbbl_check("d_log_loss"), "brier": wbbl_check("d_brier")}
    mm, wm = res["by_gender"]["male"], res["by_gender"]["female"]
    men_ok = {k: mm[C][k] <= mm["stack_global"][k] for k in ("log_loss", "brier")}
    women_ok = {k: wm[C][k] <= wm["v3_1"][k] for k in ("log_loss", "brier")}
    res["adoption"] = {"wbbl_match_or_beat_form": wbbl,
                       "men_no_regression_vs_global_stacker": men_ok,
                       "women_no_regression_vs_v3_1": women_ok,
                       "passes": (all(v["pass"] for v in wbbl.values())
                                  and all(men_ok.values()) and all(women_ok.values()))}

    recs = []
    for (lk, g), sub in common.groupby(["league_key", "gender"]):
        if len(sub) < 30 and lk not in (WBBL, IPL, "spring challenge"):
            continue
        recs.append({"league_key": lk, "gender": g, "n": len(sub),
                     **{m: {k: v for k, v in _metrics(sub, m).items()
                            if k in ("accuracy", "log_loss", "brier")} for m in all_models}})
    res["per_league"] = sorted(recs, key=lambda r: -r["n"])
    res["wbbl"] = {
        "by_season": {int(s): {"n": int(len(g)), **{m: _metrics(g, m) for m in all_models}}
                      for s, g in wb.groupby("season")},
        "calibration_5": {m: _cal5(wb["y"].to_numpy(), wb[m].to_numpy()) for m in MODELS},
        "calibration_10": {m: calibration(wb["y"].to_numpy(), wb[m].to_numpy()).to_dict("records")
                           for m in MODELS}}
    res["bands"] = {g: {m: band_table(sub, m) for m in ("v2", "v3_1", "stack_global", C)}
                    for g, sub in (("all", common), ("male", men), ("female", wom),
                                   ("wbbl", wb), ("ipl", ipl))}
    fits = logs["stack_pg"]["fits"]
    res["women_fit_path"] = [x for x in fits if x["gender"] == "female"]
    res["men_fit_last"] = next((x for x in reversed(fits) if x["gender"] == "male"), None)
    return res


# --------------------------------------------------------------------------
# markdown
# --------------------------------------------------------------------------
def _f(x, nd=4):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def _ci(d, key):
    lo, hi = d[f"{key}_ci95"]
    return f"{d[key]:+.4f} [{lo:+.4f}, {hi:+.4f}]"


def _pf(ok):
    return "pass" if ok else "**FAIL**"


def to_markdown(r: dict) -> str:
    C = r["candidate"]
    cs, ad, st = r["common_set"], r["adoption"], r["stability"]
    L = ["# Per-gender form-anchored stacker: side-by-side comparison", "",
         f"- generated: {r['generated']}",
         "- script: `venv/Scripts/python.exe -m src.model.stack_form_gender` (scheme in its docstring)",
         "- previous round (global stacker): docs/model/stack_v3_1_form_report.md",
         "- **production is NOT switched** (payload.py still serves logistic_v2 per gender).", "",
         "## 0. Scheme, stability check and candidate", "",
         "Per gender g: `p = sigmoid(b0_g + b1_g*logit(p_v3.1) + b2_g*form_gap_tourn + b3_g*form_gap_last5)`, "
         f"C={r['stacker']['C']}. For month M each gender's stacker is fit only on that gender's "
         "level-1 v3.1 out-of-sample predictions for matches before the first day of M. Under "
         f"{r['stacker']['min_train_per_gender']} earlier rows for a gender, v3.1 passes through for "
         f"that gender (in the common set: men {r['cold_start_per_gender_in_common']['male']}, "
         f"women {r['cold_start_per_gender_in_common']['female']}, WBBL "
         f"{r['cold_start_per_gender_in_common']['wbbl']}).", "",
         f"Stability rule: fall back to the interaction stacker if the women's logit or "
         f"tournament-form coefficient flips sign more than {r['max_sign_flips']} times between "
         "consecutive monthly fits.", "",
         "| gender | fits | first fit | sign flips logit | sign flips form_tourn | sign flips form_last5 | logit range | form_tourn range | form_last5 range |",
         "|---|---|---|---|---|---|---|---|---|"]
    for g in ("female", "male"):
        s = st[g]
        rng = lambda nm: (f"{s[f'range_{nm}'][0]:+.2f} .. {s[f'range_{nm}'][1]:+.2f}"
                          if s.get(f"range_{nm}") else "-")
        L.append(f"| {g} | {s['fits']} | {s['first_block']} | {s['sign_flips_logit(p_v3.1)']} | "
                 f"{s['sign_flips_form_gap_tourn']} | {s['sign_flips_form_gap_last5']} | "
                 f"{rng('logit(p_v3.1)')} | {rng('form_gap_tourn')} | {rng('form_gap_last5')} |")
    L += ["", f"**Candidate: {LABEL[C]}** "
          f"({'women stable - per-gender stacker kept' if C == 'stack_pg' else 'women unstable - interaction fallback used'}).", "",
          f"Common set: **{cs['all']}** matches ({cs['male']} men, {cs['female']} women; WBBL "
          f"{cs['wbbl']}, IPL {cs['ipl']}), {cs['first_date']} .. {cs['last_date']}.", "",
          f"## 1. Adoption bar verdict: **{'PASS' if ad['passes'] else 'FAIL'}**", "",
          "| check | measure | value [95% block-bootstrap CI] | result |", "|---|---|---|---|"]
    wf, mg, wv = r["wbbl_vs_form"], r["men_vs_global"], r["women_vs_v3_1"]
    for k, nm in (("d_log_loss", "log_loss"), ("d_brier", "brier")):
        w = ad["wbbl_match_or_beat_form"][nm]
        verdict = "beat" if w["beat"] else ("match (CI includes 0)" if w["match"] else "**FAIL**")
        L.append(f"| WBBL: match or beat form | {nm} cand - form (n={wf['n']}) | {_ci(wf, k)} | {verdict} |")
    for k, nm in (("d_log_loss", "log_loss"), ("d_brier", "brier")):
        L.append(f"| Men: no regression vs global stacker | {nm} cand - global (n={mg['n']}) | "
                 f"{_ci(mg, k)} | {_pf(ad['men_no_regression_vs_global_stacker'][nm])} |")
    for k, nm in (("d_log_loss", "log_loss"), ("d_brier", "brier")):
        L.append(f"| Women: no regression vs v3.1 | {nm} cand - v3.1 (n={wv['n']}) | "
                 f"{_ci(wv, k)} | {_pf(ad['women_no_regression_vs_v3_1'][nm])} |")
    cx = r["context"]
    L += ["", "Negative deltas mean the candidate is better. WBBL passes when the interval "
          "includes or lies below zero; men and women are judged on the point estimate.", "",
          "**Context for the WBBL rule** (same matches, same bootstrap): global stacker - form "
          f"log_loss {_ci(cx['wbbl_global_vs_form'], 'd_log_loss')}; v3.1 - form log_loss "
          f"{_ci(cx['wbbl_v3_1_vs_form'], 'd_log_loss')}. Candidate - global stacker on WBBL: "
          f"log_loss {_ci(cx['wbbl_cand_vs_global'], 'd_log_loss')}.", "",
          f"Also: women candidate - form log_loss {_ci(cx['women_cand_vs_form'], 'd_log_loss')}; "
          f"IPL candidate - form log_loss {_ci(cx['ipl_cand_vs_form'], 'd_log_loss')}; men "
          f"candidate - v2 log_loss {_ci(cx['men_cand_vs_v2'], 'd_log_loss')}.", ""]

    def mtable(title, block, models):
        out = [f"### {title}", "", "| model | n | accuracy | log_loss | brier | home rate |",
               "|---|---|---|---|---|---|"]
        for m in models:
            x = block[m]
            out.append(f"| {LABEL[m]} | {x['n']} | {_f(x['accuracy'])} | {_f(x['log_loss'])} | "
                       f"{_f(x['brier'])} | {_f(x['base_rate'])} |")
        return out + [""]

    five = MODELS
    six = MODELS[:4] + ["stack_ix", "form"]
    L += ["## 2. Overall and per gender (common set)", ""]
    L += mtable("Overall", r["overall"], six) + mtable("Men", r["by_gender"]["male"], six)
    L += mtable("Women", r["by_gender"]["female"], six)
    L += ["## 3. WBBL and IPL explicit", ""]
    L += mtable(f"WBBL (n={cs['wbbl']})", r["wbbl_metrics"], six)
    L += mtable(f"IPL (n={cs['ipl']})", r["ipl_metrics"], six)
    S = [SHORT[m] for m in five]
    L += ["### WBBL by season", "", "| season | n | " + " | ".join(f"ll {s}" for s in S) + " | "
          + " | ".join(f"brier {s}" for s in S) + " |", "|---|---|" + "---|" * (2 * len(S))]
    for s_, x in r["wbbl"]["by_season"].items():
        L.append(f"| {s_} | {x['n']} | " + " | ".join(_f(x[m]["log_loss"]) for m in five)
                 + " | " + " | ".join(_f(x[m]["brier"]) for m in five) + " |")
    for title, key, keep_empty in (("5 buckets of 20%", "calibration_5", True),
                                   ("deciles, non-empty buckets", "calibration_10", False)):
        L += ["", f"### WBBL calibration ({title}; P(home win))", "",
              "| bucket | " + " | ".join(f"n {s} | pred {s} | act {s}" for s in S) + " |",
              "|---|" + "---|" * (3 * len(S))]
        for rows in zip(*[r["wbbl"][key][m] for m in five]):
            if keep_empty or any(x["count"] for x in rows):
                L.append(f"| {rows[0]['bucket'].strip()} | " + " | ".join(
                    f"{x['count']} | {_f(x['pred_avg'], 3)} | {_f(x['actual_win_rate'], 3)}"
                    for x in rows) + " |")
    L.append("")

    L += ["## 4. Per league (common set; n >= 30, WBBL / IPL / Spring Challenge always)", "",
          "| league_key | gender | n | " + " | ".join(f"ll {s}" for s in S) + " |",
          "|---|---|---|" + "---|" * len(S)]
    for x in r["per_league"]:
        tag = " **(WBBL)**" if x["league_key"] == WBBL else (" **(IPL)**" if x["league_key"] == IPL else "")
        L.append(f"| {x['league_key']}{tag} | {x['gender']} | {x['n']} | "
                 + " | ".join(_f(x[m]["log_loss"]) for m in five) + " |")
    L.append("")

    L += ["## 5. Confidence-band distribution (confident >= "
          f"{r['band_config']['confident']}, moderate >= {r['band_config']['moderate']})", "",
          "| slice | model | confident n / share / acc | moderate n / share / acc | close_call n / share / acc |",
          "|---|---|---|---|---|"]
    for g, per in r["bands"].items():
        for m, rows in per.items():
            cells = [f"{x['n']} / {_f(x['share'] * 100, 1)}% / "
                     + (f"{_f(x['acc_in_band'] * 100, 1)}%" if x["n"] else "-") for x in rows]
            L.append(f"| {g} | {LABEL[m]} | " + " | ".join(cells) + " |")
    L.append("")

    L += ["## 6. Women's stacker coefficient path (raw scale)", "",
          "| block | n_train | intercept | " + " | ".join(COEF_NAMES) + " |",
          "|---|---|---|" + "---|" * len(COEF_NAMES)]
    path = r["women_fit_path"]
    shown = path if len(path) <= 14 else path[:4] + path[4:-6:max(1, (len(path) - 10) // 4)] + path[-6:]
    for x in shown:
        L.append(f"| {x['block']} | {x['n_train']} | {x['intercept']:+.3f} | "
                 + " | ".join(f"{c:+.3f}" for c in x["coef"]) + " |")
    mf = r["men_fit_last"]
    if mf:
        L += ["", f"Men's last fit ({mf['block']}, n={mf['n_train']}): intercept {mf['intercept']:+.3f}, "
              + ", ".join(f"{n} {c:+.3f}" for n, c in zip(COEF_NAMES, mf["coef"])) + "."]
    L.append("")
    return "\n".join(L)


def main() -> None:
    print("Per-gender stacker - walk-forward comparison (nothing is switched)")
    res = run()
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(to_markdown(res), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    ad = res["adoption"]
    print(f"\ncandidate={res['candidate']}  women stability={res['stability']['female']}")
    print(f"ADOPTION BAR: {'PASS' if ad['passes'] else 'FAIL'}  "
          f"(WBBL={ {k: v['pass'] for k, v in ad['wbbl_match_or_beat_form'].items()} }, "
          f"men={ad['men_no_regression_vs_global_stacker']}, "
          f"women={ad['women_no_regression_vs_v3_1']})")
    print(f"Report: {REPORT_MD}\n        {REPORT_JSON}")


if __name__ == "__main__":
    main()
