"""
stack_form.py - FORM-ANCHORED RECALIBRATION LAYER (stacking) on top of v3.1.

Purpose: v3.1 (pooled men+women logistic) lost to the form_favourite rule on
WBBL. This layer's ONLY job is to let the form signal pull the model's
probability where form is strong. Reads L3 only; writes only the comparison
report (docs/model/). It does NOT switch production (payload.py keeps
logistic_v2 until the user confirms).

STACKER (pre-declared before the run)
-------------------------------------
    p_final = sigmoid(b0 + b1*logit(p_v3.1) + b2*form_gap_tourn
                      + b3*form_gap_last5 + b4*is_female)
  * logit(p_v3.1): the first-level v3.1 probability, clipped to [0.01, 0.99]
    before the logit.
  * form_gap_tourn = home_win_pct_tourn - away_win_pct_tourn; form_gap_last5
    likewise (exactly the inputs form_favourite uses). A NULL gap (no history
    in that window) is 0 = no form signal - form_favourite's own convention.
  * is_female: the optional gender term (primary variant). The variant
    WITHOUT it is reported as a sensitivity only.
  * Nothing else. LogisticRegression, C = 1.0 (mild L2; 4 inputs).

WALK-FORWARD SCHEME (no leakage, two levels, same monthly blocks)
------------------------------------------------------------------
  Level 1: v3.1 is run through validation.walk_forward once. Every match in
           month M gets p_v3.1 from a model trained only on matches strictly
           before the first day of M (its out-of-fold prediction, "OOF").
  Level 2: the stacker is itself a harness predictor. For month M the harness
           hands it train = matches strictly before the first day of M. The
           stacker is fit ONLY on the level-1 OOF predictions of those train
           matches (each made before its own month, so every input the
           stacker sees is out-of-sample) and their known results. It then
           maps the current month's level-1 OOF p_v3.1 (made from data before
           M) and the current rows' form gaps (L3, point-in-time) to p_final.
           No current-month result is read at any level.
  Cold start: fewer than STACK_MIN_TRAIN (200) level-1 OOF rows before M ->
           the stacker passes p_v3.1 through unchanged (counted in the report).

ADOPTION BAR (unchanged; all must pass; production is NOT switched)
-------------------------------------------------------------------
  1. WBBL: stacked must MATCH OR BEAT form_favourite on log_loss AND brier
     (point estimate on the WBBL common set; interval shown as context).
  2. MEN: stacked must not degrade beyond noise vs production v2: FAIL only
     if delta > 0 AND the 95% paired month-block bootstrap interval lies
     entirely above 0 (log_loss and brier).
  3. WOMEN overall: stacked must not regress vs v3.1: stacked <= v3.1 on
     log_loss AND brier (point estimate; interval shown as context).

Run:
    venv/Scripts/python.exe -m src.model.stack_form
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
from src.model.validation import IPL, calibration, load_completed, walk_forward

ROOT = Path(__file__).resolve().parents[2]
REPORT_MD = ROOT / "docs" / "model" / "stack_v3_1_form_report.md"
REPORT_JSON = REPORT_MD.with_suffix(".json")

STACK_C = 1.0
STACK_MIN_TRAIN = 200
P_CLIP = 0.01

MODELS = ["v2", "v3_1", "v3_1_stack", "form"]
LABEL = {"v2": "v2 per-gender (PRODUCTION)",
         "v3_1": "v3.1 pooled",
         "v3_1_stack": "v3.1 + form stacker (CANDIDATE)",
         "form": "form_favourite (bar)"}
SHORT = {"v2": "v2", "v3_1": "v3.1", "v3_1_stack": "stack", "form": "form"}


# --------------------------------------------------------------------------
# stacker
# --------------------------------------------------------------------------
def stack_features(df: pd.DataFrame, p_first: np.ndarray, with_gender: bool) -> np.ndarray:
    p = np.clip(np.asarray(p_first, float), P_CLIP, 1 - P_CLIP)
    cols = [np.log(p / (1 - p)),
            (pd.to_numeric(df["home_win_pct_tourn"], errors="coerce")
             - pd.to_numeric(df["away_win_pct_tourn"], errors="coerce")).fillna(0.0).to_numpy(),
            (pd.to_numeric(df["home_win_pct_last5"], errors="coerce")
             - pd.to_numeric(df["away_win_pct_last5"], errors="coerce")).fillna(0.0).to_numpy()]
    if with_gender:
        cols.append((df["gender"] == "female").astype(float).to_numpy())
    return np.column_stack(cols)


def make_stacker(level1: pd.Series, with_gender: bool, log: dict):
    """Harness predictor. level1: match_id -> OOF p_v3.1 (level-1 walk-forward)."""
    def predict(train: pd.DataFrame, current: pd.DataFrame) -> np.ndarray:
        p_cur = current["match_id"].map(level1).to_numpy(float)
        tr = train[train["match_id"].isin(level1.index)]
        p_tr = tr["match_id"].map(level1).to_numpy(float)
        if len(tr) < STACK_MIN_TRAIN or tr["y"].nunique() < 2:
            log["cold_start_ids"].extend(current["match_id"].tolist())
            return p_cur                                   # pass-through
        # leakage guard: every stacker input predates the current block
        assert train["match_date"].max() < current["match_date"].min()
        clf = LogisticRegression(C=STACK_C, max_iter=1000)
        clf.fit(stack_features(tr, p_tr, with_gender), tr["y"].to_numpy(int))
        log["fits"].append({"block": str(current["match_date"].min().to_period("M")),
                            "n_train": int(len(tr)),
                            "coef": [float(c) for c in clf.coef_[0]],
                            "intercept": float(clf.intercept_[0])})
        return clf.predict_proba(stack_features(current, p_cur, with_gender))[:, 1]
    return predict


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------
def run() -> dict:
    df = load_completed(gender=None)
    oof = {}
    print("  level 1: v2 / v3.1 / form_favourite walk-forward ...")
    for name, pred in (("v2", predict_v2_per_gender), ("v3_1", predict_pooled),
                       ("form", baseline_form_favourite)):
        o, _ = walk_forward(df, pred)
        oof[name] = o.set_index("match_id")
    level1 = oof["v3_1"]["p"]
    logs = {}
    print("  level 2: stacker walk-forward (with gender, then without) ...")
    for tag, wg in (("v3_1_stack", True), ("v3_1_stack_nogender", False)):
        logs[tag] = {"cold_start_ids": [], "fits": []}
        o, _ = walk_forward(df, make_stacker(level1, wg, logs[tag]))
        oof[tag] = o.set_index("match_id")

    base = oof["v3_1"][["match_date", "league_key", "gender", "y"]].copy()
    for name in MODELS + ["v3_1_stack_nogender"]:
        base[name] = oof[name]["p"].reindex(base.index)
    common = base.dropna(subset=MODELS + ["v3_1_stack_nogender"]).reset_index()
    common["season"] = common["match_date"].dt.year
    cold = set(logs["v3_1_stack"]["cold_start_ids"])
    men, wom = common[common.gender == "male"], common[common.gender == "female"]
    wb = common[common.league_key == WBBL]

    def table(sub, models=MODELS):
        return {m: _metrics(sub, m) for m in models}

    res = {"generated": datetime.now().isoformat(timespec="seconds"),
           "stacker": {"features": ["logit(p_v3.1)", "form_gap_tourn", "form_gap_last5",
                                    "is_female"],
                       "C": STACK_C, "min_train": STACK_MIN_TRAIN, "p_clip": P_CLIP},
           "common_set": {"all": len(common), "male": len(men), "female": len(wom),
                          "wbbl": len(wb), "first_date": str(common.match_date.min().date()),
                          "last_date": str(common.match_date.max().date())},
           "cold_start_in_common": {"all": int(common["match_id"].isin(cold).sum()),
                                    "wbbl": int(wb["match_id"].isin(cold).sum())},
           "band_config": BAND_CONFIG}
    res["overall"] = table(common)
    res["by_gender"] = {"male": table(men), "female": table(wom)}

    S = "v3_1_stack"
    res["men_vs_v2"] = paired_block_bootstrap(men, S, "v2")
    res["men_vs_v3_1"] = paired_block_bootstrap(men, S, "v3_1")
    res["women_vs_v3_1"] = paired_block_bootstrap(wom, S, "v3_1")
    res["women_vs_form"] = paired_block_bootstrap(wom, S, "form")
    res["wbbl_vs_form"] = paired_block_bootstrap(wb, S, "form")
    res["wbbl_vs_v3_1"] = paired_block_bootstrap(wb, S, "v3_1")

    def worse_beyond_noise(d, key):
        return d[key] > 0 and d[f"{key}_ci95"][0] > 0

    wbm, wm = table(wb), res["by_gender"]["female"]
    men_fail = [k for k in ("d_log_loss", "d_brier") if worse_beyond_noise(res["men_vs_v2"], k)]
    wbbl_ok = {k: wbm[S][k] <= wbm["form"][k] for k in ("log_loss", "brier")}
    women_ok = {k: wm[S][k] <= wm["v3_1"][k] for k in ("log_loss", "brier")}
    res["adoption"] = {"wbbl_matches_or_beats_form": wbbl_ok,
                       "men_no_degradation_beyond_noise_vs_v2": not men_fail,
                       "men_failed_metrics": men_fail,
                       "women_no_regression_vs_v3_1": women_ok,
                       "passes": all(wbbl_ok.values()) and not men_fail and all(women_ok.values())}

    # sensitivity: no gender term
    NG = "v3_1_stack_nogender"
    res["sensitivity_nogender"] = {
        "overall": _metrics(common, NG), "male": _metrics(men, NG),
        "female": _metrics(wom, NG), "wbbl": _metrics(wb, NG),
        "wbbl_vs_form": paired_block_bootstrap(wb, NG, "form")}

    recs = []
    for (lk, g), sub in common.groupby(["league_key", "gender"]):
        if len(sub) < 30 and lk not in (WBBL, IPL, "spring challenge"):
            continue
        r = {"league_key": lk, "gender": g, "n": len(sub)}
        for m in MODELS:
            mm = _metrics(sub, m)
            r[m] = {k: mm[k] for k in ("accuracy", "log_loss", "brier")}
        recs.append(r)
    res["per_league"] = sorted(recs, key=lambda r: -r["n"])

    res["wbbl"] = {
        "metrics": wbm,
        "by_season": {int(s): {"n": int(len(g)), **{m: _metrics(g, m) for m in MODELS}}
                      for s, g in wb.groupby("season")},
        "calibration_5": {m: _cal5(wb["y"].to_numpy(), wb[m].to_numpy()) for m in MODELS},
        "calibration_10": {m: calibration(wb["y"].to_numpy(), wb[m].to_numpy()).to_dict("records")
                           for m in MODELS}}
    res["bands"] = {g: {m: band_table(sub, m) for m in ("v2", "v3_1", S)}
                    for g, sub in (("all", common), ("male", men), ("female", wom), ("wbbl", wb))}

    fits = logs[S]["fits"]
    res["stacker_fits"] = {"n_blocks_fitted": len(fits),
                           "cold_start_matches_total": len(cold),
                           "first": fits[0] if fits else None,
                           "last": fits[-1] if fits else None,
                           "coef_names": res["stacker"]["features"]}
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
    cs, ad = r["common_set"], r["adoption"]
    L = ["# v3.1 + form-anchored stacker: side-by-side comparison", "",
         f"- generated: {r['generated']}",
         "- script: `venv/Scripts/python.exe -m src.model.stack_form` (scheme in its docstring)",
         "- harness: src/model/validation.walk_forward, monthly blocks, train strictly before the block",
         "- **production is NOT switched** (payload.py still serves logistic_v2 per gender).", "",
         "## 0. Stacker and walk-forward scheme", "",
         "`p_final = sigmoid(b0 + b1*logit(p_v3.1) + b2*form_gap_tourn + b3*form_gap_last5 + b4*is_female)`, "
         f"logistic regression, C={r['stacker']['C']}. A missing form gap counts as 0.", "",
         "1. Level 1: v3.1 runs through the harness once; each match's p_v3.1 comes from a model "
         "trained only on matches before its month.",
         "2. Level 2: for month M the stacker is fit only on level-1 predictions and results of "
         "matches before the first day of M, then applied to month M's level-1 predictions.",
         f"3. Cold start: under {r['stacker']['min_train']} earlier level-1 rows, p_v3.1 passes through "
         f"unchanged. In the common set that is {r['cold_start_in_common']['all']} matches "
         f"({r['cold_start_in_common']['wbbl']} WBBL).", "",
         f"Common set (all predictors score): **{cs['all']}** matches ({cs['male']} men, "
         f"{cs['female']} women, WBBL {cs['wbbl']}), {cs['first_date']} .. {cs['last_date']}.", "",
         f"## 1. Adoption bar verdict: **{'PASS' if ad['passes'] else 'FAIL'}**", "",
         "| check | measure | value [95% block-bootstrap CI] | result |", "|---|---|---|---|"]
    wf, mv, wv = r["wbbl_vs_form"], r["men_vs_v2"], r["women_vs_v3_1"]
    L += [f"| WBBL: match or beat form | log_loss stack - form (n={wf['n']}) | {_ci(wf, 'd_log_loss')} | {_pf(ad['wbbl_matches_or_beats_form']['log_loss'])} |",
          f"| WBBL: match or beat form | brier stack - form | {_ci(wf, 'd_brier')} | {_pf(ad['wbbl_matches_or_beats_form']['brier'])} |",
          f"| Men: no degradation beyond noise | log_loss stack - v2 (n={mv['n']}) | {_ci(mv, 'd_log_loss')} | {_pf('d_log_loss' not in ad['men_failed_metrics'])} |",
          f"| Men: no degradation beyond noise | brier stack - v2 | {_ci(mv, 'd_brier')} | {_pf('d_brier' not in ad['men_failed_metrics'])} |",
          f"| Women: no regression vs v3.1 | log_loss stack - v3.1 (n={wv['n']}) | {_ci(wv, 'd_log_loss')} | {_pf(ad['women_no_regression_vs_v3_1']['log_loss'])} |",
          f"| Women: no regression vs v3.1 | brier stack - v3.1 | {_ci(wv, 'd_brier')} | {_pf(ad['women_no_regression_vs_v3_1']['brier'])} |",
          "", "Negative deltas mean the stacked model is better. WBBL and women are judged on the "
          "point estimate; men fail only if the whole interval is above zero.", "",
          f"Context: men stack - v3.1 log_loss {_ci(r['men_vs_v3_1'], 'd_log_loss')}; women stack - form "
          f"log_loss {_ci(r['women_vs_form'], 'd_log_loss')}; WBBL stack - v3.1 log_loss "
          f"{_ci(r['wbbl_vs_v3_1'], 'd_log_loss')}.", ""]

    def mtable(title, block):
        out = [f"### {title}", "", "| model | n | accuracy | log_loss | brier | home rate |",
               "|---|---|---|---|---|---|"]
        for m in MODELS:
            x = block[m]
            out.append(f"| {LABEL[m]} | {x['n']} | {_f(x['accuracy'])} | {_f(x['log_loss'])} | "
                       f"{_f(x['brier'])} | {_f(x['base_rate'])} |")
        return out + [""]

    L += ["## 2. Overall and per gender (common set)", ""]
    L += mtable("Overall", r["overall"]) + mtable("Men", r["by_gender"]["male"])
    L += mtable("Women", r["by_gender"]["female"])

    S = [SHORT[m] for m in MODELS]
    L += ["## 3. Per league (common set; n >= 30, WBBL / IPL / Spring Challenge always)", "",
          "| league_key | gender | n | " + " | ".join(f"ll {s}" for s in S) + " | "
          + " | ".join(f"brier {s}" for s in S) + " |", "|---|---|---|" + "---|" * (2 * len(S))]
    for x in r["per_league"]:
        tag = " **(WBBL)**" if x["league_key"] == WBBL else (" (IPL)" if x["league_key"] == IPL else "")
        L.append(f"| {x['league_key']}{tag} | {x['gender']} | {x['n']} | "
                 + " | ".join(_f(x[m]["log_loss"]) for m in MODELS) + " | "
                 + " | ".join(_f(x[m]["brier"]) for m in MODELS) + " |")
    L.append("")

    wb = r["wbbl"]
    L += ["## 4. WBBL explicit", ""] + mtable(f"WBBL (n={cs['wbbl']})", wb["metrics"])
    L += ["### WBBL by season", "", "| season | n | " + " | ".join(f"ll {s}" for s in S) + " | "
          + " | ".join(f"brier {s}" for s in S) + " |", "|---|---|" + "---|" * (2 * len(S))]
    for s_, x in wb["by_season"].items():
        L.append(f"| {s_} | {x['n']} | " + " | ".join(_f(x[m]["log_loss"]) for m in MODELS)
                 + " | " + " | ".join(_f(x[m]["brier"]) for m in MODELS) + " |")
    for title, key, keep_empty in (("5 buckets of 20%", "calibration_5", True),
                                   ("deciles, non-empty buckets", "calibration_10", False)):
        L += ["", f"### WBBL calibration ({title}; P(home win))", "",
              "| bucket | " + " | ".join(f"n {s} | pred {s} | actual {s}" for s in S) + " |",
              "|---|" + "---|" * (3 * len(S))]
        for rows in zip(*[wb[key][m] for m in MODELS]):
            if keep_empty or any(x["count"] for x in rows):
                L.append(f"| {rows[0]['bucket'].strip()} | " + " | ".join(
                    f"{x['count']} | {_f(x['pred_avg'], 3)} | {_f(x['actual_win_rate'], 3)}"
                    for x in rows) + " |")
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

    sn = r["sensitivity_nogender"]
    L += ["## 6. Sensitivity: stacker without the gender term (not the candidate)", "",
          f"- overall log_loss {_f(sn['overall']['log_loss'])} / brier {_f(sn['overall']['brier'])}; "
          f"men {_f(sn['male']['log_loss'])} / {_f(sn['male']['brier'])}; women "
          f"{_f(sn['female']['log_loss'])} / {_f(sn['female']['brier'])}; WBBL "
          f"{_f(sn['wbbl']['log_loss'])} / {_f(sn['wbbl']['brier'])}",
          f"- WBBL no-gender stack - form: log_loss {_ci(sn['wbbl_vs_form'], 'd_log_loss')}, "
          f"brier {_ci(sn['wbbl_vs_form'], 'd_brier')}", ""]

    sf = r["stacker_fits"]
    L += ["## 7. Stacker coefficients (raw scale)", "",
          f"{sf['n_blocks_fitted']} monthly fits; {sf['cold_start_matches_total']} matches passed "
          "through at cold start.", "",
          "| fit | block | n_train | intercept | " + " | ".join(sf["coef_names"]) + " |",
          "|---|---|---|---|" + "---|" * len(sf["coef_names"])]
    for nm in ("first", "last"):
        x = sf[nm]
        if x:
            L.append(f"| {nm} | {x['block']} | {x['n_train']} | {x['intercept']:+.4f} | "
                     + " | ".join(f"{c:+.4f}" for c in x["coef"]) + " |")
    L.append("")
    return "\n".join(L)


def main() -> None:
    print("v3.1 + form-anchored stacker - walk-forward comparison (nothing is switched)")
    res = run()
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(to_markdown(res), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    ad = res["adoption"]
    print(f"\nADOPTION BAR: {'PASS' if ad['passes'] else 'FAIL'}  "
          f"(WBBL match/beat form={ad['wbbl_matches_or_beats_form']}, "
          f"men ok={ad['men_no_degradation_beyond_noise_vs_v2']}, "
          f"women no regression={ad['women_no_regression_vs_v3_1']})")
    print(f"Report: {REPORT_MD}\n        {REPORT_JSON}")


if __name__ == "__main__":
    main()
