"""
stack_hybrid.py - HYBRID form-anchored stacker: global stacker for men,
women-only stacker for women, evaluated as ONE candidate in the harness.

Follows src/model/stack_form.py (global stacker) and
src/model/stack_form_gender.py (per-gender stacker). The per-gender round
showed the women-only stacker best for women and the global stacker best
for men; this candidate routes each gender to that stacker. It was chosen
AFTER seeing those results, so its per-gender numbers equal rows already
in docs/model/stack_per_gender_report.md - this run re-evaluates it as its
own walk-forward predictor so the verdict is computed, not assembled. The
honest out-of-sample test is still the live WBBL 2026 season. Reads L3
only; writes only the comparison report. ADOPTED as production on
2026-10-26: "stacked_hybrid_v4", served by src/model/stacked_hybrid.py.

HYBRID STACKER
--------------
  men   : p = sigmoid(a0 + a1*logit(p_v3.1) + a2*form_gap_tourn
                      + a3*form_gap_last5 + a4*is_female)
          fit on ALL genders' level-1 rows (= the global stacker).
  women : p = sigmoid(b0 + b1*logit(p_v3.1) + b2*form_gap_tourn
                      + b3*form_gap_last5)
          fit on WOMEN's level-1 rows only (= the per-gender women stacker).
  Same clip, NULL-gap = 0 convention, LogisticRegression C = 1.0.

WALK-FORWARD (same discipline as both parents)
----------------------------------------------
  Level 1: v3.1 OOF predictions from validation.walk_forward.
  Level 2: for month M both component stackers are fit only on level-1 OOF
           rows for matches strictly before the first day of M. Cold start
           is each component's own: < 200 rows overall (men's component) or
           < 200 women's rows (women's component) -> p_v3.1 passes through.
  Leakage check: for the last 3 monthly blocks the current block's labels
  are scrambled and the block is predicted again (v3.1 and hybrid); the
  predictions must not change.

ADOPTION BAR (the user's refined bar, unchanged; production NOT switched)
-------------------------------------------------------------------------
  1. WBBL: hybrid must MATCH OR BEAT form_favourite on log_loss AND brier,
     "match" = the 95% paired month-block bootstrap interval of
     (hybrid - form) includes zero (beat = whole interval below zero).
  2. MEN: hybrid <= global stacker on log_loss AND brier (point estimate).
  3. WOMEN overall: hybrid <= v3.1 on log_loss AND brier (point estimate).

Run:
    venv/Scripts/python.exe -m src.model.stack_hybrid
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.content.framing import BAND_CONFIG
from src.model.baselines import baseline_form_favourite
from src.model.retrain_men_women import (
    WBBL, _cal5, _metrics, band_table, paired_block_bootstrap,
    predict_pooled, predict_v2_per_gender,
)
from src.model.stack_form import STACK_C, STACK_MIN_TRAIN, make_stacker
from src.model.stack_form_gender import (
    COEF_NAMES, MAX_SIGN_FLIPS, _ci, _f, _pf, make_per_gender_stacker, stability,
)
from src.model.validation import IPL, calibration, load_completed, walk_forward

ROOT = Path(__file__).resolve().parents[2]
REPORT_MD = ROOT / "docs" / "model" / "stack_hybrid_report.md"
REPORT_JSON = REPORT_MD.with_suffix(".json")
SCRAMBLE_BLOCKS = 3
SCRAMBLE_SEED = 20261026

MODELS = ["v2", "v3_1", "stack_global", "stack_pg", "hybrid", "form"]
LABEL = {"v2": "v2 per-gender (PRODUCTION)", "v3_1": "v3.1 pooled",
         "stack_global": "global stacker (men's benchmark)",
         "stack_pg": "per-gender stacker",
         "hybrid": "hybrid: global men / women-only women (CANDIDATE)",
         "form": "form_favourite (bar)"}
SHORT = {"v2": "v2", "v3_1": "v3.1", "stack_global": "glob", "stack_pg": "pg",
         "hybrid": "hyb", "form": "form"}


# --------------------------------------------------------------------------
# stacker
# --------------------------------------------------------------------------
def _new_logs() -> dict:
    return {k: {"cold_start_ids": [], "fits": []} for k in ("global", "per_gender")}


def make_hybrid_stacker(level1: pd.Series, logs: dict):
    """Harness predictor: men's rows from the global stacker, women's rows
    from the women-only stacker; both fit on rows before the current block."""
    glob = make_stacker(level1, True, logs["global"])
    per_gender = make_per_gender_stacker(level1, logs["per_gender"])

    def predict(train: pd.DataFrame, current: pd.DataFrame) -> np.ndarray:
        assert train["match_date"].max() < current["match_date"].min()
        out = np.asarray(glob(train, current), float).copy()
        fem = (current["gender"] == "female").to_numpy()
        if fem.any():
            out[fem] = np.asarray(per_gender(train, current), float)[fem]
        return out
    return predict


def scrambled_label_check(df: pd.DataFrame, level1: pd.Series) -> dict:
    """Re-predict the last SCRAMBLE_BLOCKS monthly blocks with their own labels
    shuffled; a leak-free predictor returns identical probabilities."""
    rng = np.random.default_rng(SCRAMBLE_SEED)
    months = sorted(df["match_date"].dt.to_period("M").unique())[-SCRAMBLE_BLOCKS:]
    out = {"blocks": [str(m) for m in months], "n": 0,
           "max_abs_diff_v3_1": 0.0, "max_abs_diff_hybrid": 0.0}
    for m in months:
        train = df[df["match_date"] < m.start_time]
        cur = df[df["match_date"].dt.to_period("M") == m]
        scr = cur.copy()
        scr["y"] = rng.permutation(scr["y"].to_numpy())
        out["n"] += len(cur)
        d_v31 = np.abs(np.asarray(predict_pooled(train, cur), float)
                       - np.asarray(predict_pooled(train, scr), float))
        d_hyb = np.abs(make_hybrid_stacker(level1, _new_logs())(train, cur)
                       - make_hybrid_stacker(level1, _new_logs())(train, scr))
        out["max_abs_diff_v3_1"] = max(out["max_abs_diff_v3_1"], float(d_v31.max()))
        out["max_abs_diff_hybrid"] = max(out["max_abs_diff_hybrid"], float(d_hyb.max()))
    out["pass"] = out["max_abs_diff_v3_1"] == 0.0 and out["max_abs_diff_hybrid"] == 0.0
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
    print("  level 2: global / per-gender / hybrid stackers ...")
    lg_hyb = _new_logs()
    for name, pred in (("stack_global", make_stacker(level1, True, _new_logs()["global"])),
                       ("stack_pg", make_per_gender_stacker(level1, _new_logs()["per_gender"])),
                       ("hybrid", make_hybrid_stacker(level1, lg_hyb))):
        o, _ = walk_forward(df, pred)
        oof[name] = o.set_index("match_id")
    print("  leakage: scrambled current-block labels ...")
    leak = scrambled_label_check(df, level1)

    base = oof["v3_1"][["match_date", "league_key", "gender", "y"]].copy()
    for name in MODELS:
        base[name] = oof[name]["p"].reindex(base.index)
    common = base.dropna(subset=MODELS).reset_index()
    common["season"] = common["match_date"].dt.year
    men, wom = common[common.gender == "male"], common[common.gender == "female"]
    wb, ipl = common[common.league_key == WBBL], common[common.league_key == IPL]

    # routing check: men's rows = global stacker, women's rows = per-gender stacker
    ident = {"men_max_abs_diff_vs_global": float((men["hybrid"] - men["stack_global"]).abs().max()),
             "women_max_abs_diff_vs_per_gender": float((wom["hybrid"] - wom["stack_pg"]).abs().max())}

    def table(sub):
        return {m: _metrics(sub, m) for m in MODELS}

    cold_m = set(lg_hyb["global"]["cold_start_ids"])
    cold_w = set(lg_hyb["per_gender"]["cold_start_ids"])
    res = {"generated": datetime.now().isoformat(timespec="seconds"),
           "candidate": "hybrid", "selection": "post hoc (chosen after the per-gender round)",
           "stacker": {"inputs_men": COEF_NAMES + ["is_female"], "inputs_women": COEF_NAMES,
                       "C": STACK_C, "min_train": STACK_MIN_TRAIN},
           "leakage_scrambled_labels": leak, "routing_identity": ident,
           "women_stability": stability(lg_hyb["per_gender"]["fits"], "female"),
           "max_sign_flips": MAX_SIGN_FLIPS,
           "common_set": {"all": len(common), "male": len(men), "female": len(wom),
                          "wbbl": len(wb), "ipl": len(ipl),
                          "first_date": str(common.match_date.min().date()),
                          "last_date": str(common.match_date.max().date())},
           "cold_start_in_common": {
               "male": int(men["match_id"].isin(cold_m).sum()),
               "female": int(wom["match_id"].isin(cold_w).sum()),
               "wbbl": int(wb["match_id"].isin(cold_w).sum())},
           "band_config": BAND_CONFIG}
    res["overall"] = table(common)
    res["by_gender"] = {"male": table(men), "female": table(wom)}
    res["wbbl_metrics"] = table(wb)
    res["ipl_metrics"] = table(ipl)

    C = "hybrid"
    res["wbbl_vs_form"] = paired_block_bootstrap(wb, C, "form")
    res["men_vs_global"] = paired_block_bootstrap(men, C, "stack_global")
    res["women_vs_v3_1"] = paired_block_bootstrap(wom, C, "v3_1")
    res["context"] = {
        "overall_vs_global": paired_block_bootstrap(common, C, "stack_global"),
        "overall_vs_v2": paired_block_bootstrap(common, C, "v2"),
        "women_vs_form": paired_block_bootstrap(wom, C, "form"),
        "wbbl_vs_v2": paired_block_bootstrap(wb, C, "v2"),
        "wbbl_global_vs_form": paired_block_bootstrap(wb, "stack_global", "form"),
        "wbbl_v3_1_vs_form": paired_block_bootstrap(wb, "v3_1", "form"),
        "ipl_vs_form": paired_block_bootstrap(ipl, C, "form")}

    def wbbl_check(key):
        lo, hi = res["wbbl_vs_form"][f"{key}_ci95"]
        return {"match": bool(lo <= 0 <= hi), "beat": bool(hi < 0), "pass": bool(lo <= 0)}
    wbbl = {"log_loss": wbbl_check("d_log_loss"), "brier": wbbl_check("d_brier")}
    mm, wm = res["by_gender"]["male"], res["by_gender"]["female"]
    men_ok = {k: mm[C][k] <= mm["stack_global"][k] for k in ("log_loss", "brier")}
    women_ok = {k: wm[C][k] <= wm["v3_1"][k] for k in ("log_loss", "brier")}
    res["adoption"] = {"wbbl_match_or_beat_form": wbbl,
                       "men_no_regression_vs_global_stacker": men_ok,
                       "women_no_regression_vs_v3_1": women_ok,
                       "leakage_check_pass": leak["pass"],
                       "passes": (all(v["pass"] for v in wbbl.values()) and all(men_ok.values())
                                  and all(women_ok.values()) and leak["pass"])}

    recs = []
    for (lk, g), sub in common.groupby(["league_key", "gender"]):
        if len(sub) < 30 and lk not in (WBBL, IPL, "spring challenge"):
            continue
        recs.append({"league_key": lk, "gender": g, "n": len(sub),
                     **{m: {k: v for k, v in _metrics(sub, m).items()
                            if k in ("accuracy", "log_loss", "brier")} for m in MODELS}})
    res["per_league"] = sorted(recs, key=lambda r: -r["n"])
    res["wbbl"] = {
        "by_season": {int(s): {"n": int(len(g)), **{m: _metrics(g, m) for m in MODELS}}
                      for s, g in wb.groupby("season")},
        "calibration_5": {m: _cal5(wb["y"].to_numpy(), wb[m].to_numpy()) for m in MODELS},
        "calibration_10": {m: calibration(wb["y"].to_numpy(), wb[m].to_numpy()).to_dict("records")
                           for m in MODELS}}
    res["bands"] = {g: {m: band_table(sub, m) for m in ("v2", "v3_1", "stack_global", C)}
                    for g, sub in (("all", common), ("male", men), ("female", wom),
                                   ("wbbl", wb), ("ipl", ipl))}
    res["band_honesty"] = {g: band_honesty(sub, C) for g, sub in
                           (("male", men), ("female", wom), ("wbbl", wb), ("ipl", ipl))}
    return res


def _wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    if n == 0:
        return [float("nan"), float("nan")]
    ph = k / n
    c = (ph + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [float(c - h), float(c + h)]


def band_honesty(sub: pd.DataFrame, col: str) -> list[dict]:
    """Per band: the promise (its floor), the mean stated p_max, the hit rate
    of the predicted side and a 95% Wilson interval. Honest = hit rate >= floor."""
    p = sub[col].to_numpy(float)
    pmax = np.maximum(p, 1 - p)
    hit = (p >= 0.5) == (sub["y"].to_numpy() == 1)
    edges = {"confident": (BAND_CONFIG["confident"], 1.01),
             "moderate": (BAND_CONFIG["moderate"], BAND_CONFIG["confident"]),
             "close_call": (0.5, BAND_CONFIG["moderate"])}
    out = []
    for band, (lo, hi) in edges.items():
        m = (pmax >= lo) & (pmax < hi)
        n, k = int(m.sum()), int(hit[m].sum())
        out.append({"band": band, "promise": lo, "n": n,
                    "mean_p_max": float(pmax[m].mean()) if n else float("nan"),
                    "hit_rate": k / n if n else float("nan"), "wilson95": _wilson(k, n),
                    "honest": bool(n and k / n >= lo)})
    return out


# --------------------------------------------------------------------------
# markdown
# --------------------------------------------------------------------------
def to_markdown(r: dict) -> str:
    cs, ad, lk = r["common_set"], r["adoption"], r["leakage_scrambled_labels"]
    st, cold, idn = r["women_stability"], r["cold_start_in_common"], r["routing_identity"]
    L = ["# Hybrid form-anchored stacker: side-by-side comparison", "",
         f"- generated: {r['generated']}",
         "- script: `venv/Scripts/python.exe -m src.model.stack_hybrid` (scheme in its docstring)",
         "- previous rounds: docs/model/stack_v3_1_form_report.md (global), "
         "docs/model/stack_per_gender_report.md (per-gender)",
         "- **adopted as production 2026-10-26**: payload.py serves this model as `stacked_hybrid_v4` (src/model/stacked_hybrid.py).", "",
         "## 0. Scheme, checks and caveat", "",
         "Men's matches get the **global stacker** (v3.1 logit, tournament form gap, last-5 form gap, "
         "is_female; fit on all genders). Women's matches get the **women-only stacker** (same inputs "
         f"minus the flag; fit on women's matches only). C={r['stacker']['C']}. For month M both are fit "
         "only on level-1 v3.1 out-of-sample predictions for matches before the first day of M; under "
         f"{r['stacker']['min_train']} earlier rows (all rows for the men's part, women's rows for the "
         f"women's part) v3.1 passes through (in the common set: men {cold['male']}, women "
         f"{cold['female']}, WBBL {cold['wbbl']}).", "",
         "**Selection caveat:** this candidate was chosen after the per-gender round showed which "
         "stacker wins for each gender. Its rows equal the parents' rows by construction (routing "
         f"check: men max |hybrid - global| = {idn['men_max_abs_diff_vs_global']:.1e}, women max "
         f"|hybrid - per-gender| = {idn['women_max_abs_diff_vs_per_gender']:.1e}). The men's and "
         "women's checks below are therefore met partly by selection; the clean out-of-sample test "
         "is the live WBBL 2026 season.", "",
         f"Women's component stability: {st['fits']} fits from {st['first_block']}; sign flips logit "
         f"{st['sign_flips_logit(p_v3.1)']}, form_tourn {st['sign_flips_form_gap_tourn']}, form_last5 "
         f"{st['sign_flips_form_gap_last5']} (limit {r['max_sign_flips']}).", "",
         f"Leakage (scrambled current-block labels, blocks {', '.join(lk['blocks'])}, n={lk['n']}): "
         f"max |diff| v3.1 {lk['max_abs_diff_v3_1']:.1e}, hybrid {lk['max_abs_diff_hybrid']:.1e} -> "
         f"{'pass' if lk['pass'] else '**FAIL**'}.", "",
         f"Common set: **{cs['all']}** matches ({cs['male']} men, {cs['female']} women; WBBL "
         f"{cs['wbbl']}, IPL {cs['ipl']}), {cs['first_date']} .. {cs['last_date']}.", "",
         f"## 1. Adoption bar verdict: **{'PASS' if ad['passes'] else 'FAIL'}**", "",
         "| check | measure | value [95% block-bootstrap CI] | result |", "|---|---|---|---|"]
    wf, mg, wv = r["wbbl_vs_form"], r["men_vs_global"], r["women_vs_v3_1"]
    for k, nm in (("d_log_loss", "log_loss"), ("d_brier", "brier")):
        w = ad["wbbl_match_or_beat_form"][nm]
        verdict = "beat" if w["beat"] else ("match (CI includes 0)" if w["match"] else "**FAIL**")
        L.append(f"| WBBL: match or beat form | {nm} hybrid - form (n={wf['n']}) | {_ci(wf, k)} | {verdict} |")
    for k, nm in (("d_log_loss", "log_loss"), ("d_brier", "brier")):
        L.append(f"| Men: no regression vs global stacker | {nm} hybrid - global (n={mg['n']}) | "
                 f"{_ci(mg, k)} | {_pf(ad['men_no_regression_vs_global_stacker'][nm])} |")
    for k, nm in (("d_log_loss", "log_loss"), ("d_brier", "brier")):
        L.append(f"| Women: no regression vs v3.1 | {nm} hybrid - v3.1 (n={wv['n']}) | "
                 f"{_ci(wv, k)} | {_pf(ad['women_no_regression_vs_v3_1'][nm])} |")
    cx = r["context"]
    L += ["", "Negative deltas mean the hybrid is better. WBBL passes when the interval includes or "
          "lies below zero; men and women are judged on the point estimate.", "",
          "**Context** (log_loss deltas): overall hybrid - global "
          f"{_ci(cx['overall_vs_global'], 'd_log_loss')}; overall hybrid - v2 (production) "
          f"{_ci(cx['overall_vs_v2'], 'd_log_loss')}; women hybrid - form "
          f"{_ci(cx['women_vs_form'], 'd_log_loss')}; WBBL hybrid - v2 "
          f"{_ci(cx['wbbl_vs_v2'], 'd_log_loss')}; IPL hybrid - form {_ci(cx['ipl_vs_form'], 'd_log_loss')}.", "",
          "Same WBBL rule applied to earlier models: global stacker - form "
          f"{_ci(cx['wbbl_global_vs_form'], 'd_log_loss')}; v3.1 - form "
          f"{_ci(cx['wbbl_v3_1_vs_form'], 'd_log_loss')} (both would also 'match' at n={wf['n']}).", ""]

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
    L += ["## 3. WBBL and IPL explicit", ""]
    L += mtable(f"WBBL (n={cs['wbbl']})", r["wbbl_metrics"])
    L += mtable(f"IPL (n={cs['ipl']})", r["ipl_metrics"])
    S = [SHORT[m] for m in MODELS]
    L += ["### WBBL by season", "", "| season | n | " + " | ".join(f"ll {s}" for s in S) + " | "
          + " | ".join(f"brier {s}" for s in S) + " |", "|---|---|" + "---|" * (2 * len(S))]
    for s_, x in r["wbbl"]["by_season"].items():
        L.append(f"| {s_} | {x['n']} | " + " | ".join(_f(x[m]["log_loss"]) for m in MODELS)
                 + " | " + " | ".join(_f(x[m]["brier"]) for m in MODELS) + " |")
    for title, key, keep_empty in (("5 buckets of 20%", "calibration_5", True),
                                   ("deciles, non-empty buckets", "calibration_10", False)):
        L += ["", f"### WBBL calibration ({title}; P(home win))", "",
              "| bucket | " + " | ".join(f"n {s} | pred {s} | act {s}" for s in S) + " |",
              "|---|" + "---|" * (3 * len(S))]
        for rows in zip(*[r["wbbl"][key][m] for m in MODELS]):
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
                 + " | ".join(_f(x[m]["log_loss"]) for m in MODELS) + " |")
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

    L += ["## 6. Band honesty, hybrid (promise = band floor; honest = hit rate >= promise)", "",
          "| slice | band | promise | n | mean stated p_max | hit rate [95% Wilson] | honest |",
          "|---|---|---|---|---|---|---|"]
    for g, rows in r["band_honesty"].items():
        for x in rows:
            lo, hi = x["wilson95"]
            L.append(f"| {g} | {x['band']} | {x['promise']:.2f} | {x['n']} | {_f(x['mean_p_max'], 3)} | "
                     f"{_f(x['hit_rate'], 3)} [{_f(lo, 3)}, {_f(hi, 3)}] | "
                     f"{'yes' if x['honest'] else '**no**'} |")
    L += ["", "Men and women are the bar slices; WBBL and IPL are shown for context (small n).", ""]
    return "\n".join(L)


def main() -> None:
    print("Hybrid stacker - walk-forward comparison (nothing is switched)")
    res = run()
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(to_markdown(res), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    ad = res["adoption"]
    print(f"\nleakage={res['leakage_scrambled_labels']}\nrouting={res['routing_identity']}")
    print(f"ADOPTION BAR: {'PASS' if ad['passes'] else 'FAIL'}  "
          f"(WBBL={ {k: v['pass'] for k, v in ad['wbbl_match_or_beat_form'].items()} }, "
          f"men={ad['men_no_regression_vs_global_stacker']}, "
          f"women={ad['women_no_regression_vs_v3_1']})")
    print(f"Report: {REPORT_MD}\n        {REPORT_JSON}")


if __name__ == "__main__":
    main()
