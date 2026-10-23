"""
retrain_men_women.py - Phase 2 PART B: men+women retrain, scored through the
SAME walk-forward harness (src/model/validation.py) as v1/v2.

Reads L3 only. Writes ONLY the comparison report (docs/model/). It does NOT
switch the production model: payload.py keeps MODEL_VERSION logistic_v2 until
the report is reviewed and the switch is approved.

ROUNDS
------
  * v3   (2026-10-23, docs/model/retrain_men_women_report.md, kept as the
         record): pooled candidate on the pre-fix data. Passed the rule,
         lost to form_favourite on WBBL. Production held on v2.
  * v3.1 (this script's current CANDIDATE_TAG): SAME spec as v3, retrained
         on the league_key-fixed data (revise_l1.LEAGUE_KEY_ALIASES: the
         split women's Vitality Blast / WCPL / U19 World Cup keys and the
         men's World Cup warm-up keys consolidated).

MODELS
------
  * v2_per_gender  PRODUCTION as deployed: train_logistic.predict_logistic
                   (C=0.01, league one-hot >= 50 train matches) refit on
                   SAME-GENDER history only - exactly what payload.py does.
                   A gender with < MIN_TRAIN (100) same-gender train matches
                   gets no prediction (payload: prediction_available=false).
  * v3_1_pooled    CANDIDATE: one model on men+women history. Same features,
                   same preprocessing, same C, plus an is_female flag; league
                   dummies learned per fold on the pooled train (WBBL earns its
                   own column once it has >= 50 train matches).
  * form_favourite the Phase-2 bar (baselines.baseline_form_favourite).

EVALUATION SET: every completed match that ALL predictors score (the common
set), so every comparison is paired on identical matches. Women's matches
that only the pooled model can score (too little same-gender history for v2)
are counted separately and reported for WBBL.

ADOPTION RULE (as specified by the user, made mechanical here)
--------------------------------------------------------------
  1. MEN - no degradation beyond noise: for log_loss AND brier,
     delta = candidate - v2_per_gender on the men's common set. FAIL only if
     delta > 0 AND the 95% paired bootstrap interval (resampling whole
     monthly walk-forward blocks, 2000 reps, seed 20261023) lies entirely
     above 0, i.e. the candidate is worse by more than noise.
  2. WOMEN - must beat form_favourite on BOTH log_loss and brier (point
     estimate on the women's common set; the interval is reported alongside).
  3. WBBL (added for v3.1) - must at least MATCH form_favourite on BOTH
     log_loss and brier on the WBBL common set: candidate <= form on the
     point estimate. Whether the gap is within noise is reported alongside,
     but does not turn a loss into a pass.
  All must pass. Passing does NOT switch production - the user decides.

Run:
    venv/Scripts/python.exe -m src.model.retrain_men_women
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from src.content.framing import BAND_CONFIG, BANDS, confidence_band
from src.model.baselines import baseline_form_favourite
from src.model.train_logistic import (
    C_REG, MAX_ITER, _Prep, _slug, design_matrix, league_list, predict_logistic,
)
from src.model.validation import IPL, MIN_TRAIN, calibration, load_completed, metrics, walk_forward

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_TAG = "v3.1"
CAND = "v3_1_pooled"
REPORT_MD = ROOT / "docs" / "model" / "retrain_v3_1_report.md"
REPORT_JSON = REPORT_MD.with_suffix(".json")

WBBL = "womens big bash league"
BOOT_REPS = 2000
BOOT_SEED = 20261023
MODELS = ["v2_per_gender", CAND, "form_favourite"]
LABEL = {"v2_per_gender": "v2 per-gender (PRODUCTION)",
         CAND: f"{CANDIDATE_TAG} pooled (CANDIDATE)",
         "form_favourite": "form_favourite (bar)"}
SHORT = {"v2_per_gender": "v2", CAND: CANDIDATE_TAG, "form_favourite": "form"}


# --------------------------------------------------------------------------
# predictors (harness contract: fit on train only, never read current['y'])
# --------------------------------------------------------------------------
def predict_v2_per_gender(train: pd.DataFrame, current: pd.DataFrame) -> np.ndarray:
    out = np.full(len(current), np.nan)
    for g in current["gender"].unique():
        cm = (current["gender"] == g).to_numpy()
        tr = train[train["gender"] == g]
        if len(tr) >= MIN_TRAIN:
            out[cm] = predict_logistic(tr, current[cm])
    return out


def design_pooled(df: pd.DataFrame, leagues: list[str]) -> pd.DataFrame:
    X = design_matrix(df, leagues)
    X["is_female"] = (df["gender"] == "female").astype(float)
    return X


def _fit_pooled(train: pd.DataFrame):
    leagues = league_list(train)
    Xraw = design_pooled(train, leagues)
    prep = _Prep().fit(Xraw)
    clf = LogisticRegression(C=C_REG, max_iter=MAX_ITER)
    clf.fit(prep.transform(Xraw), train["y"].to_numpy(dtype=int))
    return leagues, prep, clf, list(Xraw.columns)


def predict_pooled(train: pd.DataFrame, current: pd.DataFrame) -> np.ndarray:
    """v3 / v3.1 spec: v2 pipeline on men+women history + is_female."""
    ytr = train["y"].to_numpy(dtype=int)
    if len(np.unique(ytr)) < 2:
        return np.full(len(current), float(ytr.mean()))
    leagues, prep, clf, _ = _fit_pooled(train)
    return clf.predict_proba(prep.transform(design_pooled(current, leagues)))[:, 1]


PREDICTORS = {"v2_per_gender": predict_v2_per_gender,
              CAND: predict_pooled,
              "form_favourite": baseline_form_favourite}


# --------------------------------------------------------------------------
# scoring helpers
# --------------------------------------------------------------------------
def _ll_vec(y, p):
    pc = np.clip(p, 1e-15, 1 - 1e-15)
    return -(y * np.log(pc) + (1 - y) * np.log(1 - pc))


def paired_block_bootstrap(sub: pd.DataFrame, a: str, b: str) -> dict:
    """delta = mean(metric_a) - mean(metric_b) on identical matches, with a
    95% interval from resampling whole monthly blocks (paired)."""
    y = sub["y"].to_numpy(float)
    d_ll = _ll_vec(y, sub[a].to_numpy(float)) - _ll_vec(y, sub[b].to_numpy(float))
    d_br = (sub[a].to_numpy(float) - y) ** 2 - (sub[b].to_numpy(float) - y) ** 2
    blocks = sub["match_date"].dt.to_period("M").to_numpy()
    uniq = pd.unique(blocks)
    idx_by_block = [np.flatnonzero(blocks == u) for u in uniq]
    rng = np.random.default_rng(BOOT_SEED)
    bs_ll, bs_br = np.empty(BOOT_REPS), np.empty(BOOT_REPS)
    for r in range(BOOT_REPS):
        pick = rng.integers(0, len(uniq), len(uniq))
        ii = np.concatenate([idx_by_block[k] for k in pick])
        bs_ll[r], bs_br[r] = d_ll[ii].mean(), d_br[ii].mean()
    return {"n": int(len(sub)), "blocks": int(len(uniq)),
            "d_log_loss": float(d_ll.mean()),
            "d_log_loss_ci95": [float(np.percentile(bs_ll, 2.5)), float(np.percentile(bs_ll, 97.5))],
            "d_brier": float(d_br.mean()),
            "d_brier_ci95": [float(np.percentile(bs_br, 2.5)), float(np.percentile(bs_br, 97.5))]}


def _metrics(sub: pd.DataFrame, col: str) -> dict:
    return metrics(sub["y"].to_numpy(), sub[col].to_numpy())


def band_table(sub: pd.DataFrame, col: str) -> list[dict]:
    p = sub[col].to_numpy(float)
    y = sub["y"].to_numpy(float)
    pmax = np.maximum(p, 1 - p)
    bands = np.array([confidence_band(v) for v in pmax])
    hit = (p >= 0.5) == (y == 1)
    out = []
    for b in BANDS:
        m = bands == b
        out.append({"band": b, "n": int(m.sum()),
                    "share": float(m.mean()) if len(m) else float("nan"),
                    "acc_in_band": float(hit[m].mean()) if m.sum() else float("nan"),
                    "avg_p_max": float(pmax[m].mean()) if m.sum() else float("nan")})
    return out


def _cal5(y, p):
    """5 buckets of 20% - the decile table is too thin at WBBL's sample size."""
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    idx = np.clip((p * 5).astype(int), 0, 4)
    out = []
    for b in range(5):
        m = idx == b
        out.append({"bucket": f"{b*20}-{(b+1)*20}%", "count": int(m.sum()),
                    "pred_avg": float(p[m].mean()) if m.sum() else float("nan"),
                    "actual_win_rate": float(y[m].mean()) if m.sum() else float("nan")})
    return out


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------
def run() -> dict:
    df = load_completed(gender=None)
    oofs = {}
    for name, pred in PREDICTORS.items():
        oof, info = walk_forward(df, pred)          # gender passes through the harness
        oofs[name] = oof.set_index("match_id")
        print(f"  walk-forward {name:15s} evaluated={info['evaluated']} "
              f"blocks={info['blocks_used']}")
    base = oofs[CAND][["match_date", "league_key", "gender", "y"]].copy()
    for name in MODELS:
        base[name] = oofs[name]["p"].reindex(base.index)
    common = base.dropna(subset=MODELS).reset_index()
    pooled_only = base[base["v2_per_gender"].isna() & base[CAND].notna()]
    common["season"] = common["match_date"].dt.year

    res = {"generated": datetime.now().isoformat(timespec="seconds"),
           "candidate": CANDIDATE_TAG,
           "data": {"league_keys": int(df["league_key"].nunique()),
                    "note": "league_key aliases applied (revise_l1.LEAGUE_KEY_ALIASES); "
                            "U19 WWC 2025 duplicate ids 911/912 flagged, not dropped"},
           "completed_matches": {"all": len(df),
                                 "male": int((df.gender == "male").sum()),
                                 "female": int((df.gender == "female").sum())},
           "common_set": {"all": len(common),
                          "male": int((common.gender == "male").sum()),
                          "female": int((common.gender == "female").sum()),
                          "first_date": str(common.match_date.min().date()),
                          "last_date": str(common.match_date.max().date())},
           "pooled_only_coverage": {
               "matches": int(len(pooled_only)),
               "by_gender": pooled_only["gender"].value_counts().to_dict(),
               "wbbl": int((pooled_only["league_key"] == WBBL).sum())},
           "band_config": BAND_CONFIG}

    def table(sub):
        return {m: _metrics(sub, m) for m in MODELS}

    men = common[common.gender == "male"]
    wom = common[common.gender == "female"]
    wb = common[common.league_key == WBBL]
    res["overall"] = table(common)
    res["by_gender"] = {"male": table(men), "female": table(wom)}
    res["men_noise"] = paired_block_bootstrap(men, CAND, "v2_per_gender")
    res["women_vs_form"] = paired_block_bootstrap(wom, CAND, "form_favourite")
    res["women_vs_v2"] = paired_block_bootstrap(wom, CAND, "v2_per_gender")

    # ---- adoption ----
    def worse_beyond_noise(d, key):
        return d[key] > 0 and d[f"{key}_ci95"][0] > 0

    men_fail = [k for k in ("d_log_loss", "d_brier")
                if worse_beyond_noise(res["men_noise"], k)]
    wm = res["by_gender"]["female"]
    women_ok = {k: wm[CAND][k] < wm["form_favourite"][k] for k in ("log_loss", "brier")}
    wbm = table(wb)
    wbbl_ok = {k: wbm[CAND][k] <= wbm["form_favourite"][k] for k in ("log_loss", "brier")}
    res["adoption"] = {
        "men_no_degradation_beyond_noise": not men_fail,
        "men_failed_metrics": men_fail,
        "women_beats_form_favourite": women_ok,
        "wbbl_matches_form_favourite": wbbl_ok,
        "passes": (not men_fail) and all(women_ok.values()) and all(wbbl_ok.values()),
        "note": "a PASS makes the candidate eligible; production stays v2 "
                "until the user approves the switch"}

    # ---- per league (common set): n>=30, WBBL + IPL + spring challenge always
    recs = []
    for (lk, g), sub in common.groupby(["league_key", "gender"]):
        if len(sub) < 30 and lk not in (WBBL, IPL, "spring challenge"):
            continue
        r = {"league_key": lk, "gender": g, "n": len(sub), "home_rate": float(sub["y"].mean())}
        for m in MODELS:
            mm = _metrics(sub, m)
            r[m] = {k: mm[k] for k in ("accuracy", "log_loss", "brier")}
        recs.append(r)
    res["per_league"] = sorted(recs, key=lambda r: -r["n"])

    # ---- WBBL explicit ----
    wb_all = base[(base["league_key"] == WBBL) & base[CAND].notna()].reset_index()
    res["wbbl"] = {
        "n_common": int(len(wb)),
        "metrics": wbm,
        "by_season": {int(s): {"n": int(len(g)), **{m: _metrics(g, m) for m in MODELS}}
                      for s, g in wb.groupby("season")},
        "vs_form": paired_block_bootstrap(wb, CAND, "form_favourite"),
        "vs_v2": paired_block_bootstrap(wb, CAND, "v2_per_gender"),
        "calibration_5": {m: _cal5(wb["y"].to_numpy(), wb[m].to_numpy()) for m in MODELS},
        "calibration_10": {m: calibration(wb["y"].to_numpy(), wb[m].to_numpy()).to_dict("records")
                           for m in MODELS},
        "all_candidate_scored": {
            "n": int(len(wb_all)),
            "by_season": {int(k): int(v) for k, v in
                          wb_all["match_date"].dt.year.value_counts().sort_index().items()},
            CAND: _metrics(wb_all, CAND),
            "form_favourite": _metrics(wb_all, "form_favourite"),
            "vs_form": paired_block_bootstrap(wb_all, CAND, "form_favourite")},
    }
    res["bands"] = {g: {m: band_table(sub, m) for m in ("v2_per_gender", CAND)}
                    for g, sub in (("all", common), ("male", men), ("female", wom),
                                   ("wbbl", wb))}

    # ---- full-data interpretation fit (never used for scoring) ----
    leagues, prep, clf, names = _fit_pooled(df)
    coefs = sorted(zip(names, clf.coef_[0]), key=lambda t: -abs(t[1]))
    cd = dict(coefs)
    res["coefficients"] = {"intercept": float(clf.intercept_[0]),
                           "leagues_with_dummy": leagues,
                           "top": [(n, float(c)) for n, c in coefs[:15]],
                           "is_female": float(cd["is_female"]),
                           "wbbl_dummy": float(cd.get(_slug(WBBL), float("nan")))}
    return res


# --------------------------------------------------------------------------
# markdown
# --------------------------------------------------------------------------
def _f(x, nd=4):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def _ci(d, key):
    lo, hi = d[f"{key}_ci95"]
    return f"{d[key]:+.4f} [{lo:+.4f}, {hi:+.4f}]"


def _pf(ok: bool) -> str:
    return "pass" if ok else "**FAIL**"


def to_markdown(r: dict) -> str:
    T = CANDIDATE_TAG
    L = [f"# Men + women retrain {T}: side-by-side comparison", "",
         f"- generated: {r['generated']}",
         "- harness: src/model/validation.walk_forward (expanding window, monthly "
         "blocks, train strictly before the block; MIN_TRAIN 100)",
         "- script: `venv/Scripts/python.exe -m src.model.retrain_men_women`",
         f"- data: {r['data']['league_keys']} league_keys in the completed set; "
         f"{r['data']['note']}",
         "- previous round (v3, pre-fix data): docs/model/retrain_men_women_report.md",
         "- **production is NOT switched** by this report (payload.py still "
         "uses logistic_v2 per gender).", ""]
    cs, po = r["common_set"], r["pooled_only_coverage"]
    L += ["## 0. Models and evaluation set", "",
          "| model | what it is |", "|---|---|",
          "| v2 per-gender (PRODUCTION) | logistic v2 (C=0.01, league dummies) refit on same-gender history only; what payload.py serves today |",
          f"| {T} pooled (CANDIDATE) | same spec as v3: the v2 pipeline on men+women history, plus is_female; league dummies per fold on the pooled train |",
          "| form_favourite (bar) | the Phase-2 rule baseline |", "",
          f"Common set (scored by all): **{cs['all']}** matches ({cs['male']} men, "
          f"{cs['female']} women), {cs['first_date']} .. {cs['last_date']}. Completed "
          f"matches in L3: {r['completed_matches']['all']} ({r['completed_matches']['male']} "
          f"men, {r['completed_matches']['female']} women).", "",
          f"Pooled-only coverage (excluded from the comparisons): {po['matches']} matches "
          f"{po['by_gender']}, of which WBBL {po['wbbl']}.", ""]

    ad, mn, wf, wb = r["adoption"], r["men_noise"], r["women_vs_form"], r["wbbl"]
    wbf = wb["vs_form"]
    L += [f"## 1. Adoption rule verdict: **{'PASS' if ad['passes'] else 'FAIL'}**", "",
          "| check | measure | value [95% block-bootstrap CI] | result |",
          "|---|---|---|---|",
          f"| Men: no degradation beyond noise | log_loss {T} - v2 (n={mn['n']}) | {_ci(mn, 'd_log_loss')} | "
          f"{_pf('d_log_loss' not in ad['men_failed_metrics'])} |",
          f"| Men: no degradation beyond noise | brier {T} - v2 | {_ci(mn, 'd_brier')} | "
          f"{_pf('d_brier' not in ad['men_failed_metrics'])} |",
          f"| Women: beat form_favourite | log_loss {T} - form (n={wf['n']}) | {_ci(wf, 'd_log_loss')} | "
          f"{_pf(ad['women_beats_form_favourite']['log_loss'])} |",
          f"| Women: beat form_favourite | brier {T} - form | {_ci(wf, 'd_brier')} | "
          f"{_pf(ad['women_beats_form_favourite']['brier'])} |",
          f"| WBBL: at least match form_favourite | log_loss {T} - form (n={wbf['n']}) | {_ci(wbf, 'd_log_loss')} | "
          f"{_pf(ad['wbbl_matches_form_favourite']['log_loss'])} |",
          f"| WBBL: at least match form_favourite | brier {T} - form | {_ci(wbf, 'd_brier')} | "
          f"{_pf(ad['wbbl_matches_form_favourite']['brier'])} |",
          "",
          "Negative deltas mean the candidate is better. Men fail only if the delta is "
          "positive and its whole interval is above zero. Women and WBBL are judged on "
          "the point estimate; the interval is context. Intervals resample whole monthly "
          f"blocks, {BOOT_REPS} reps.", "",
          f"For context, women {T} - v2: log_loss {_ci(r['women_vs_v2'], 'd_log_loss')}, "
          f"brier {_ci(r['women_vs_v2'], 'd_brier')}.", ""]

    def mtable(title, block):
        out = [f"### {title}", "", "| model | n | accuracy | log_loss | brier | home rate |",
               "|---|---|---|---|---|---|"]
        for m in MODELS:
            x = block[m]
            out.append(f"| {LABEL[m]} | {x['n']} | {_f(x['accuracy'])} | {_f(x['log_loss'])} | "
                       f"{_f(x['brier'])} | {_f(x['base_rate'])} |")
        return out + [""]

    L += ["## 2. Overall and per gender (common set)", ""]
    L += mtable("Overall", r["overall"])
    L += mtable("Men", r["by_gender"]["male"])
    L += mtable("Women", r["by_gender"]["female"])

    S = [SHORT[m] for m in MODELS]
    L += ["## 3. Per league (common set; n >= 30, WBBL / IPL / Spring Challenge always)", "",
          "| league_key | gender | n | " + " | ".join(f"ll {s}" for s in S) + " | "
          + " | ".join(f"brier {s}" for s in S) + " | " + " | ".join(f"acc {s}" for s in S) + " |",
          "|---|---|---|" + "---|" * (3 * len(S))]
    for x in r["per_league"]:
        tag = " **(WBBL)**" if x["league_key"] == WBBL else (" (IPL)" if x["league_key"] == IPL else "")
        cells = ([_f(x[m]["log_loss"]) for m in MODELS] + [_f(x[m]["brier"]) for m in MODELS]
                 + [_f(x[m]["accuracy"], 3) for m in MODELS])
        L.append(f"| {x['league_key']}{tag} | {x['gender']} | {x['n']} | " + " | ".join(cells) + " |")
    L.append("")

    L += ["## 4. WBBL explicit", ""]
    L += mtable(f"WBBL, common set (n={wb['n_common']})", wb["metrics"])
    L += ["### WBBL by season", "",
          "| season | n | " + " | ".join(f"ll {s}" for s in S) + " | "
          + " | ".join(f"brier {s}" for s in S) + " |",
          "|---|---|" + "---|" * (2 * len(S))]
    for s_, x in wb["by_season"].items():
        L.append(f"| {s_} | {x['n']} | " + " | ".join(_f(x[m]["log_loss"]) for m in MODELS)
                 + " | " + " | ".join(_f(x[m]["brier"]) for m in MODELS) + " |")
    wa = wb["all_candidate_scored"]
    L += ["", f"WBBL {T} - form: log_loss {_ci(wb['vs_form'], 'd_log_loss')}, brier {_ci(wb['vs_form'], 'd_brier')}.",
          f"WBBL {T} - v2: log_loss {_ci(wb['vs_v2'], 'd_log_loss')}, brier {_ci(wb['vs_v2'], 'd_brier')}.", "",
          f"WBBL on every match the candidate scores (n={wa['n']}, by season {wa['by_season']}; "
          f"includes matches v2 cannot score): {T} log_loss {_f(wa[CAND]['log_loss'])} / brier "
          f"{_f(wa[CAND]['brier'])} / acc {_f(wa[CAND]['accuracy'], 3)} vs form log_loss "
          f"{_f(wa['form_favourite']['log_loss'])} / brier {_f(wa['form_favourite']['brier'])} / acc "
          f"{_f(wa['form_favourite']['accuracy'], 3)}; {T} - form log_loss {_ci(wa['vs_form'], 'd_log_loss')}.", ""]
    L += ["### WBBL calibration (5 buckets of 20%; P(home win))", "",
          "| bucket | " + " | ".join(f"n {s} | pred {s} | actual {s}" for s in S) + " |",
          "|---|" + "---|" * (3 * len(S))]
    cals = [wb["calibration_5"][m] for m in MODELS]
    for rows in zip(*cals):
        L.append(f"| {rows[0]['bucket']} | " + " | ".join(
            f"{x['count']} | {_f(x['pred_avg'], 3)} | {_f(x['actual_win_rate'], 3)}" for x in rows) + " |")
    L += ["", "### WBBL calibration (deciles, non-empty buckets)", "",
          "| bucket | " + " | ".join(f"n {s} | pred {s} | actual {s}" for s in S) + " |",
          "|---|" + "---|" * (3 * len(S))]
    cals = [wb["calibration_10"][m] for m in MODELS]
    for rows in zip(*cals):
        if any(x["count"] for x in rows):
            L.append(f"| {rows[0]['bucket'].strip()} | " + " | ".join(
                f"{x['count']} | {_f(x['pred_avg'], 3)} | {_f(x['actual_win_rate'], 3)}" for x in rows) + " |")
    L.append("")

    L += ["## 5. Confidence-band distribution (framing.BAND_CONFIG: confident >= "
          f"{BAND_CONFIG['confident']}, moderate >= {BAND_CONFIG['moderate']})", "",
          "| slice | model | confident n / share / acc | moderate n / share / acc | close_call n / share / acc |",
          "|---|---|---|---|---|"]
    for g, per in r["bands"].items():
        for m, rows in per.items():
            cells = [f"{x['n']} / {_f(x['share'] * 100, 1)}% / "
                     + (f"{_f(x['acc_in_band'] * 100, 1)}%" if x["n"] else "-") for x in rows]
            L.append(f"| {g} | {LABEL[m]} | " + " | ".join(cells) + " |")
    L.append("")

    co = r["coefficients"]
    L += [f"## 6. {T} coefficients (full-data fit, interpretation only)", "",
          f"- intercept {co['intercept']:+.4f}; is_female {co['is_female']:+.4f}; "
          f"WBBL dummy {co['wbbl_dummy']:+.4f}",
          f"- leagues with a dummy (>= 50 matches): {len(co['leagues_with_dummy'])}", "",
          "| feature | coef (standardized) |", "|---|---|"]
    L += [f"| {n} | {c:+.4f} |" for n, c in co["top"]]
    L.append("")
    return "\n".join(L)


def main() -> None:
    print(f"Men+women retrain {CANDIDATE_TAG} - walk-forward comparison (nothing is switched)")
    res = run()
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(to_markdown(res), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    ad = res["adoption"]
    print(f"\nADOPTION RULE: {'PASS' if ad['passes'] else 'FAIL'}  "
          f"(men ok={ad['men_no_degradation_beyond_noise']}, "
          f"women beats form={ad['women_beats_form_favourite']}, "
          f"WBBL matches form={ad['wbbl_matches_form_favourite']})")
    print(f"Report: {REPORT_MD}\n        {REPORT_JSON}")


if __name__ == "__main__":
    main()
