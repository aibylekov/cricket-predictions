"""
retrain_men_women.py - Phase 2 PART B: men+women retrain, scored through the
SAME walk-forward harness (src/model/validation.py) as v1/v2.

Reads L3 only. Writes ONLY the comparison report (docs/model/). It does NOT
switch the production model: payload.py keeps MODEL_VERSION logistic_v2 until
the report is reviewed and the switch is approved.

MODELS (pre-declared before the run; one candidate, one sensitivity)
-------------------------------------------------------------------
  * v2_per_gender  PRODUCTION as deployed: train_logistic.predict_logistic
                   (C=0.01, league one-hot >= 50 train matches) refit on
                   SAME-GENDER history only - exactly what payload.py does.
                   A gender with < MIN_TRAIN (100) same-gender train matches
                   gets no prediction (payload: prediction_available=false).
  * v3_pooled      CANDIDATE: one model on men+women history. Same features,
                   same preprocessing, same C, plus an is_female flag; league
                   dummies learned per fold on the pooled train (WBBL earns its
                   own column once it has >= 50 train matches).
  * v3_interact    SENSITIVITY ONLY (not a candidate): v3_pooled + is_female x
                   every base feature (partial pooling through the shared L2).
  * form_favourite the Phase-2 bar (baselines.baseline_form_favourite).

EVALUATION SET: every completed match that ALL four predictors score (the
common set), so every comparison is paired on identical matches. Women's
matches that only the pooled model can score (too little same-gender
history for v2) are counted separately.

ADOPTION RULE (as specified by the user, made mechanical here)
--------------------------------------------------------------
  1. MEN - no degradation beyond noise: for log_loss AND brier,
     delta = v3_pooled - v2_per_gender on the men's common set. FAIL only if
     delta > 0 AND the 95% paired bootstrap interval (resampling whole
     monthly walk-forward blocks, 2000 reps, seed 20261023) lies entirely
     above 0, i.e. the candidate is worse by more than noise.
  2. WOMEN - must beat form_favourite on BOTH log_loss and brier (point
     estimate on the women's common set; the bootstrap interval is reported
     alongside).
  Both must pass. Passing does NOT switch production - the user decides.

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
    BASE_FEATURES, C_REG, MAX_ITER, _Prep, _slug, design_matrix, league_list,
    predict_logistic,
)
from src.model.validation import IPL, MIN_TRAIN, calibration, load_completed, metrics, walk_forward

ROOT = Path(__file__).resolve().parents[2]
REPORT_MD = ROOT / "docs" / "model" / "retrain_men_women_report.md"
REPORT_JSON = REPORT_MD.with_suffix(".json")

WBBL = "womens big bash league"
BOOT_REPS = 2000
BOOT_SEED = 20261023
MODELS = ["v2_per_gender", "v3_pooled", "v3_interact", "form_favourite"]
LABEL = {"v2_per_gender": "v2 per-gender (PRODUCTION)",
         "v3_pooled": "v3 pooled (CANDIDATE)",
         "v3_interact": "v3 interact (sensitivity)",
         "form_favourite": "form_favourite (bar)"}


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


def design_v3(df: pd.DataFrame, leagues: list[str], interact: bool) -> pd.DataFrame:
    X = design_matrix(df, leagues)
    fem = (df["gender"] == "female").astype(float)
    if interact:
        for c in BASE_FEATURES:
            X[f"fem_x_{c}"] = X[c] * fem          # NaN stays NaN -> train-mean imputed
    X["is_female"] = fem
    return X


def _fit_v3(train: pd.DataFrame, interact: bool):
    leagues = league_list(train)
    Xraw = design_v3(train, leagues, interact)
    prep = _Prep().fit(Xraw)
    ytr = train["y"].to_numpy(dtype=int)
    clf = LogisticRegression(C=C_REG, max_iter=MAX_ITER)
    clf.fit(prep.transform(Xraw), ytr)
    return leagues, prep, clf, list(Xraw.columns)


def _predict_v3(train, current, interact):
    ytr = train["y"].to_numpy(dtype=int)
    if len(np.unique(ytr)) < 2:
        return np.full(len(current), float(ytr.mean()))
    leagues, prep, clf, _ = _fit_v3(train, interact)
    return clf.predict_proba(prep.transform(design_v3(current, leagues, interact)))[:, 1]


def predict_v3_pooled(train, current):
    return _predict_v3(train, current, interact=False)


def predict_v3_interact(train, current):
    return _predict_v3(train, current, interact=True)


PREDICTORS = {"v2_per_gender": predict_v2_per_gender,
              "v3_pooled": predict_v3_pooled,
              "v3_interact": predict_v3_interact,
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


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------
def run() -> dict:
    df = load_completed(gender=None)
    oofs = {}
    for name, pred in PREDICTORS.items():
        oof, info = walk_forward(df, pred)
        oofs[name] = oof.set_index("match_id")
        print(f"  walk-forward {name:15s} evaluated={info['evaluated']} "
              f"blocks={info['blocks_used']}")
    base = oofs["v3_pooled"][["match_date", "league_key", "y"]].copy()
    # gender comes from L3 (the harness's OOF blocks do not carry it)
    base["gender"] = base.index.map(df.set_index("match_id")["gender"])
    for name in MODELS:
        base[name] = oofs[name]["p"].reindex(base.index)
    common = base.dropna(subset=MODELS).reset_index()
    pooled_only = base[base["v2_per_gender"].isna() & base["v3_pooled"].notna()]
    years = df.set_index("match_id")["match_date"].dt.year
    common["season"] = common["match_id"].map(years)

    res = {"generated": datetime.now().isoformat(timespec="seconds"),
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
               "wbbl": int((pooled_only["league_key"] == WBBL).sum()),
               "note": "scored only by the pooled models (v2 per-gender had < "
                       f"{MIN_TRAIN} same-gender train matches); excluded from "
                       "every comparison"},
           "band_config": BAND_CONFIG}

    def table(sub):
        return {m: _metrics(sub, m) for m in MODELS}

    res["overall"] = table(common)
    res["by_gender"] = {g: table(common[common.gender == g]) for g in ("male", "female")}

    men = common[common.gender == "male"]
    wom = common[common.gender == "female"]
    res["men_noise"] = paired_block_bootstrap(men, "v3_pooled", "v2_per_gender")
    res["women_vs_form"] = paired_block_bootstrap(wom, "v3_pooled", "form_favourite")
    res["women_vs_v2"] = paired_block_bootstrap(wom, "v3_pooled", "v2_per_gender")
    res["sensitivity_men_noise"] = paired_block_bootstrap(men, "v3_interact", "v2_per_gender")
    res["sensitivity_women_vs_form"] = paired_block_bootstrap(wom, "v3_interact", "form_favourite")

    def worse_beyond_noise(d, key):
        lo, _hi = d[f"{key}_ci95"]
        return d[key] > 0 and lo > 0

    men_fail = [k for k in ("d_log_loss", "d_brier")
                if worse_beyond_noise(res["men_noise"], k)]
    wm = res["by_gender"]["female"]
    women_ok = {"log_loss": wm["v3_pooled"]["log_loss"] < wm["form_favourite"]["log_loss"],
                "brier": wm["v3_pooled"]["brier"] < wm["form_favourite"]["brier"]}
    res["adoption"] = {
        "men_no_degradation_beyond_noise": not men_fail,
        "men_failed_metrics": men_fail,
        "women_beats_form_favourite": women_ok,
        "passes": (not men_fail) and all(women_ok.values()),
        "note": "a PASS makes the candidate eligible; production stays v2 "
                "until the user approves the switch"}

    # per league (common set): n>=30, WBBL + IPL + spring challenge always
    recs = []
    for (lk, g), sub in common.groupby(["league_key", "gender"]):
        if len(sub) < 30 and lk not in (WBBL, IPL, "spring challenge"):
            continue
        r = {"league_key": lk, "gender": g, "n": len(sub)}
        for m in MODELS:
            mm = _metrics(sub, m)
            r[m] = {k: mm[k] for k in ("accuracy", "log_loss", "brier")}
        r["home_rate"] = float(sub["y"].mean())
        recs.append(r)
    res["per_league"] = sorted(recs, key=lambda r: (-r["n"]))

    wb = common[common.league_key == WBBL]
    wb_all = base[(base["league_key"] == WBBL) & base["v3_pooled"].notna()]
    res["wbbl_all_candidate_scored"] = {
        "n": int(len(wb_all)),
        "by_season": {int(k): int(v) for k, v in
                      wb_all["match_date"].dt.year.value_counts().sort_index().items()},
        **{m: _metrics(wb_all, m) for m in ("v3_pooled", "v3_interact", "form_favourite")},
        "vs_form": paired_block_bootstrap(wb_all.reset_index(), "v3_pooled", "form_favourite")}
    res["wbbl"] = {
        "n_common": int(len(wb)),
        "metrics": table(wb) if len(wb) else {},
        "by_season": {int(s): {"n": int(len(g)), **{m: _metrics(g, m) for m in MODELS}}
                      for s, g in wb.groupby("season")},
        "vs_form": paired_block_bootstrap(wb, "v3_pooled", "form_favourite") if len(wb) else {},
        "vs_v2": paired_block_bootstrap(wb, "v3_pooled", "v2_per_gender") if len(wb) else {},
        "calibration": {m: calibration(wb["y"].to_numpy(), wb[m].to_numpy()).to_dict("records")
                        for m in ("v2_per_gender", "v3_pooled", "form_favourite")},
        "calibration_5": {m: _cal5(wb["y"].to_numpy(), wb[m].to_numpy())
                          for m in ("v2_per_gender", "v3_pooled", "form_favourite")},
    }
    res["women_calibration"] = {m: calibration(wom["y"].to_numpy(), wom[m].to_numpy()).to_dict("records")
                                for m in ("v2_per_gender", "v3_pooled")}
    res["bands"] = {g: {m: band_table(sub, m) for m in ("v2_per_gender", "v3_pooled")}
                    for g, sub in (("all", common), ("male", men), ("female", wom),
                                   ("wbbl", wb))}

    # full-data interpretation fit of the candidate (never used for scoring)
    leagues, prep, clf, names = _fit_v3(df, interact=False)
    coefs = sorted(zip(names, clf.coef_[0]), key=lambda t: -abs(t[1]))
    res["v3_coefficients"] = {"intercept": float(clf.intercept_[0]),
                              "leagues_with_dummy": leagues,
                              "top": [(n, float(c)) for n, c in coefs[:15]],
                              "is_female": float(dict(coefs)["is_female"]),
                              "wbbl_dummy": float(dict(coefs).get(_slug(WBBL), float("nan")))}
    return res


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
# markdown
# --------------------------------------------------------------------------
def _f(x, nd=4):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def _ci(d, key):
    lo, hi = d[f"{key}_ci95"]
    return f"{d[key]:+.4f} [{lo:+.4f}, {hi:+.4f}]"


def to_markdown(r: dict) -> str:
    L = ["# Men + women retrain: side-by-side comparison", "",
         f"- generated: {r['generated']}",
         "- harness: src/model/validation.walk_forward (expanding window, monthly "
         "blocks, train strictly before the block; MIN_TRAIN 100)",
         "- script: `venv/Scripts/python.exe -m src.model.retrain_men_women`",
         "- **production is NOT switched** by this report (payload.py still "
         "uses logistic_v2 per gender).", ""]
    cs = r["common_set"]
    po = r["pooled_only_coverage"]
    L += ["## 0. Models and evaluation set", "",
          "| model | what it is |", "|---|---|",
          "| v2 per-gender (PRODUCTION) | logistic v2 (C=0.01, league dummies) refit on same-gender history only; what payload.py serves today |",
          "| v3 pooled (CANDIDATE) | same pipeline on men+women history, plus is_female; league dummies per fold on the pooled train |",
          "| v3 interact (sensitivity) | v3 pooled + is_female x every base feature; reported, not a candidate |",
          "| form_favourite (bar) | the Phase-2 rule baseline |", "",
          f"Common set (scored by all four): **{cs['all']}** matches "
          f"({cs['male']} men, {cs['female']} women), {cs['first_date']} .. {cs['last_date']}. "
          f"Completed matches in L3: {r['completed_matches']['all']} "
          f"({r['completed_matches']['male']} men, {r['completed_matches']['female']} women).",
          "",
          f"Pooled-only coverage (excluded from all comparisons): {po['matches']} matches "
          f"{po['by_gender']}, of which WBBL {po['wbbl']}. v2 cannot score them "
          f"(fewer than 100 same-gender train matches at the time).", ""]

    ad = r["adoption"]
    mn = r["men_noise"]
    wf = r["women_vs_form"]
    verdict = "PASS" if ad["passes"] else "FAIL"
    L += ["## 1. Adoption rule verdict: " + f"**{verdict}**", "",
          "| check | measure | value [95% block-bootstrap CI] | result |",
          "|---|---|---|---|",
          f"| Men: no degradation beyond noise | log_loss v3 - v2 (n={mn['n']}) | {_ci(mn, 'd_log_loss')} | "
          f"{'pass' if 'd_log_loss' not in ad['men_failed_metrics'] else 'FAIL'} |",
          f"| Men: no degradation beyond noise | brier v3 - v2 | {_ci(mn, 'd_brier')} | "
          f"{'pass' if 'd_brier' not in ad['men_failed_metrics'] else 'FAIL'} |",
          f"| Women: beat form_favourite | log_loss v3 - form (n={wf['n']}) | {_ci(wf, 'd_log_loss')} | "
          f"{'pass' if ad['women_beats_form_favourite']['log_loss'] else 'FAIL'} |",
          f"| Women: beat form_favourite | brier v3 - form | {_ci(wf, 'd_brier')} | "
          f"{'pass' if ad['women_beats_form_favourite']['brier'] else 'FAIL'} |",
          "",
          "Negative deltas mean the candidate is better. Men fail only if the delta is "
          "positive and its whole interval is above zero. Women pass on the point "
          "estimate, per the rule; the interval is shown for context. Intervals resample "
          f"whole monthly blocks ({mn['blocks']} men's blocks, {wf['blocks']} women's), "
          f"{BOOT_REPS} reps.", ""]
    wv = r["women_vs_v2"]
    L += [f"For context, women v3 - v2 per-gender: log_loss {_ci(wv, 'd_log_loss')}, "
          f"brier {_ci(wv, 'd_brier')}.", ""]

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

    L += ["## 3. Per league (common set; n >= 30, WBBL / IPL / Spring Challenge always)", "",
          "| league_key | gender | n | ll v2 | ll v3 | ll form | brier v2 | brier v3 | brier form | acc v2 | acc v3 | acc form |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in r["per_league"]:
        tag = " **(WBBL)**" if x["league_key"] == WBBL else (" (IPL)" if x["league_key"] == IPL else "")
        L.append(f"| {x['league_key']}{tag} | {x['gender']} | {x['n']} | "
                 f"{_f(x['v2_per_gender']['log_loss'])} | {_f(x['v3_pooled']['log_loss'])} | {_f(x['form_favourite']['log_loss'])} | "
                 f"{_f(x['v2_per_gender']['brier'])} | {_f(x['v3_pooled']['brier'])} | {_f(x['form_favourite']['brier'])} | "
                 f"{_f(x['v2_per_gender']['accuracy'], 3)} | {_f(x['v3_pooled']['accuracy'], 3)} | {_f(x['form_favourite']['accuracy'], 3)} |")
    L.append("")

    wb = r["wbbl"]
    L += ["## 4. WBBL explicit", ""]
    if wb["n_common"]:
        L += mtable(f"WBBL, all seasons in the common set (n={wb['n_common']})", wb["metrics"])
        wa = r["wbbl_all_candidate_scored"]
        L += [f"WBBL on every match the candidate scores (n={wa['n']}, by season {wa['by_season']}; "
              "includes the matches v2 cannot score): "
              f"v3 log_loss {_f(wa['v3_pooled']['log_loss'])} / brier {_f(wa['v3_pooled']['brier'])} / acc "
              f"{_f(wa['v3_pooled']['accuracy'], 3)} vs form log_loss {_f(wa['form_favourite']['log_loss'])} / "
              f"brier {_f(wa['form_favourite']['brier'])} / acc {_f(wa['form_favourite']['accuracy'], 3)}; "
              f"v3 - form log_loss {_ci(wa['vs_form'], 'd_log_loss')}.", ""]
        L += ["### WBBL by season", "", "| season | n | ll v2 | ll v3 | ll form | brier v2 | brier v3 | brier form |",
              "|---|---|---|---|---|---|---|---|"]
        for s, x in wb["by_season"].items():
            L.append(f"| {s} | {x['n']} | {_f(x['v2_per_gender']['log_loss'])} | {_f(x['v3_pooled']['log_loss'])} | "
                     f"{_f(x['form_favourite']['log_loss'])} | {_f(x['v2_per_gender']['brier'])} | "
                     f"{_f(x['v3_pooled']['brier'])} | {_f(x['form_favourite']['brier'])} |")
        L += ["", f"WBBL v3 - form: log_loss {_ci(wb['vs_form'], 'd_log_loss')}, brier {_ci(wb['vs_form'], 'd_brier')}.",
              f"WBBL v3 - v2: log_loss {_ci(wb['vs_v2'], 'd_log_loss')}, brier {_ci(wb['vs_v2'], 'd_brier')}.", ""]
        L += ["### WBBL calibration (5 buckets of 20%; P(home win))", "",
              "| bucket | n v2 | pred v2 | actual v2 | n v3 | pred v3 | actual v3 | n form | pred form | actual form |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        c2, c3, cf = (wb["calibration_5"][m] for m in ("v2_per_gender", "v3_pooled", "form_favourite"))
        for a, b, c in zip(c2, c3, cf):
            L.append(f"| {a['bucket']} | {a['count']} | {_f(a['pred_avg'], 3)} | {_f(a['actual_win_rate'], 3)} | "
                     f"{b['count']} | {_f(b['pred_avg'], 3)} | {_f(b['actual_win_rate'], 3)} | "
                     f"{c['count']} | {_f(c['pred_avg'], 3)} | {_f(c['actual_win_rate'], 3)} |")
        L += ["", "### WBBL calibration (deciles, as the harness prints them)", "",
              "| bucket | n v2 | pred v2 | actual v2 | n v3 | pred v3 | actual v3 |", "|---|---|---|---|---|---|---|"]
        for a, b in zip(wb["calibration"]["v2_per_gender"], wb["calibration"]["v3_pooled"]):
            if a["count"] or b["count"]:
                L.append(f"| {a['bucket'].strip()} | {a['count']} | {_f(a['pred_avg'], 3)} | {_f(a['actual_win_rate'], 3)} | "
                         f"{b['count']} | {_f(b['pred_avg'], 3)} | {_f(b['actual_win_rate'], 3)} |")
        L.append("")

    L += ["## 5. Confidence-band distribution (framing.BAND_CONFIG: confident >= "
          f"{BAND_CONFIG['confident']}, moderate >= {BAND_CONFIG['moderate']})", "",
          "| slice | model | confident n / share / acc | moderate n / share / acc | close_call n / share / acc |",
          "|---|---|---|---|---|"]
    for g, per in r["bands"].items():
        for m, rows in per.items():
            cells = [f"{x['n']} / {_f(x['share'] * 100, 1)}% / "
                     + (f"{_f(x['acc_in_band'] * 100, 1)}%" if x["n"] else "-")
                     for x in rows]
            L.append(f"| {g} | {LABEL[m]} | " + " | ".join(cells) + " |")
    L.append("")

    L += ["## 6. Sensitivity: v3 interact (not a candidate)", "",
          f"- Men v3_interact - v2: log_loss {_ci(r['sensitivity_men_noise'], 'd_log_loss')}, "
          f"brier {_ci(r['sensitivity_men_noise'], 'd_brier')}",
          f"- Women v3_interact - form: log_loss {_ci(r['sensitivity_women_vs_form'], 'd_log_loss')}, "
          f"brier {_ci(r['sensitivity_women_vs_form'], 'd_brier')}", ""]

    co = r["v3_coefficients"]
    L += ["## 7. Candidate coefficients (full-data fit, interpretation only)", "",
          f"- intercept {co['intercept']:+.4f}; is_female {co['is_female']:+.4f}; "
          f"WBBL dummy {co['wbbl_dummy']:+.4f}",
          f"- leagues with a dummy (>= 50 matches): {len(co['leagues_with_dummy'])}", "",
          "| feature | coef (standardized) |", "|---|---|"]
    L += [f"| {n} | {c:+.4f} |" for n, c in co["top"]]
    L.append("")
    return "\n".join(L)


def main() -> None:
    print("Men+women retrain - walk-forward comparison (nothing is switched)")
    res = run()
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(to_markdown(res), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    ad = res["adoption"]
    print(f"\nADOPTION RULE: {'PASS' if ad['passes'] else 'FAIL'}  "
          f"(men ok={ad['men_no_degradation_beyond_noise']}, "
          f"women beats form={ad['women_beats_form_favourite']})")
    print(f"Report: {REPORT_MD}\n        {REPORT_JSON}")


if __name__ == "__main__":
    main()
