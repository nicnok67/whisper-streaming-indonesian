"""Within-language policy comparisons on the merged shards (no cross-language statistics).
Usage: python -I within_lang.py <data_dir>"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

data = Path(sys.argv[1])
sys.path.insert(0, str(data / "in0"))
from wspb import stats  # noqa: E402

a = pd.read_csv(data / "s0/report/per_recording_metrics.csv")
b = pd.read_csv(data / "s1/report/per_recording_metrics.csv")
df = pd.concat([a, b]).drop_duplicates(subset=["policy", "lang", "chunk", "mode", "key"])
df.to_csv(data / "merged_per_recording.csv", index=False)
cu = df[df["mode"] == "cu"]
ids = sorted(set(cu[cu.lang == "en"].idx) & set(cu[cu.lang == "id"].idx))
assert len(ids) == 325, len(ids)
D = stats.Data(df, ids)
CH = [0.5, 1.0, 1.2, 1.5, 2.0]
out = {}

# summary table (should reproduce the paper's numbers)
tab = stats.summary_table(df)
tab.to_csv(data / "merged_summary.csv", index=False)


def pair(la, aa, lang, c, metric="wer", equal_weight=False):
    w_la, b_la = D.wer(la, lang, c, metric=metric, equal_weight=equal_weight)
    w_aa, b_aa = D.wer(aa, lang, c, metric=metric, equal_weight=equal_weight)
    if w_la is None or w_aa is None:
        return None
    d, bd = w_aa - w_la, b_aa - b_la
    r, br = stats.rel_adv(D, la, aa, lang, c, metric=metric, equal_weight=equal_weight)
    pr = stats.pratt(D, la, aa, lang, c, metric=metric, equal_weight=equal_weight)
    l_la, bl_la = D.latency(la, lang, c)
    l_aa, bl_aa = D.latency(aa, lang, c)
    return {"wer_la": 100 * w_la, "wer_aa": 100 * w_aa,
            "diff_pts": 100 * d, "diff_ci": [100 * v for v in stats.ci(bd)], "diff_p_boot": stats.boot_p(bd),
            "R_pct": 100 * r, "R_ci": [100 * v for v in stats.ci(br)], "p_pratt": pr["p"],
            "laal_la": l_la, "laal_aa": l_aa, "laal_diff": l_aa - l_la,
            "laal_diff_ci": stats.ci(bl_aa - bl_la), "laal_p_boot": stats.boot_p(bl_aa - bl_la)}


# A. LocalAgreement-2 vs AlignAtt-trim, every chunk, each language
A = {lang: {str(c): pair("la2", "aa_trim", lang, c) for c in CH} for lang in ("en", "id")}
# Holm over the four pre-specified tests (0.5 and 1.0 s, both languages)
keys = [(l, c) for l in ("en", "id") for c in ("0.5", "1.0")]
for (l, c), p in zip(keys, stats.holm([A[l][c]["p_pratt"] for l, c in keys])):
    A[l][c]["p_pratt_holm"] = p
out["la2_vs_aa_trim"] = A

# B. matched latency, within each language (primary: LA anchored; secondary: AA anchored)
for anchor in ("la", "aa"):
    m = stats.h3_matched_latency(D, "aa_trim", anchor=anchor)
    res = {}
    for c, r in m["chunks"].items():
        if not isinstance(r, dict):
            res[c] = r
            continue
        res[c] = {}
        for lang in ("en", "id"):
            x = r.get(lang)
            if not isinstance(x, dict):
                continue
            res[c][lang] = {k: v for k, v in x.items() if not k.startswith("_")}
    out[f"matched_{anchor}_anchor"] = res


# per-language matched-latency CIs (h3_matched_latency only bootstraps the cross-language delta)
def matched_one(lang, c, anchor="la", aa="aa_trim", la="la2"):
    fixed, curve = (la, aa) if anchor == "la" else (aa, la)
    pts = [(k, D.wer(curve, lang, k), D.latency(curve, lang, k)) for k in CH]
    xp = np.array([l[0] for _, _, l in pts]); fp = np.array([w[0] for _, w, _ in pts])
    w_fx, b_fx = D.wer(fixed, lang, c)
    l_fx, bl_fx = D.latency(fixed, lang, c)
    o = np.argsort(xp)
    w_cv = float(np.interp(l_fx, xp[o], fp[o], left=np.nan, right=np.nan))
    bw = stats._interp_rows(bl_fx, np.stack([l[1] for _, _, l in pts]), np.stack([w[1] for _, w, _ in pts]))
    w_la, w_aa, b_la, b_aa = (w_fx, w_cv, b_fx, bw) if anchor == "la" else (w_cv, w_fx, bw, b_fx)
    bd = b_aa - b_la
    return {"anchor_laal": l_fx, "wer_la": 100 * w_la, "wer_aa": 100 * w_aa,
            "diff_pts": 100 * (w_aa - w_la), "diff_ci": [100 * v for v in stats.ci(bd)],
            "p_boot": stats.boot_p(bd), "R_pct": 100 * (w_la - w_aa) / w_la,
            "resamples_outside": int((~np.isfinite(bd)).sum())}


out["matched_per_language"] = {f"{lang}@{c}/{an}": matched_one(lang, c, an)
                               for lang in ("en", "id") for c in (0.5, 1.0) for an in ("la", "aa")}

# C. robustness of LA2 vs AA-trim at 0.5 and 1.0
out["robustness"] = {}
for lang in ("en", "id"):
    for c in (0.5, 1.0):
        out["robustness"][f"{lang}@{c}"] = {
            "cer": pair("la2", "aa_trim", lang, c, metric="cer"),
            "equal_weight": pair("la2", "aa_trim", lang, c, equal_weight=True),
            "aa_keep": pair("la2", "aa_keep", lang, c),
        }
    out["robustness"][f"{lang}@1.0"]["la_beam5"] = pair("la2_beam5", "aa_trim", lang, 1.0)

# D. hold-n baselines vs LocalAgreement-2, and Hold-2 vs Hold-0
out["baselines"] = {f"{lang}@{c}": {"hold0_vs_la2": pair("la2", "hold0", lang, c),
                                    "hold2_vs_la2": pair("la2", "hold2", lang, c),
                                    "hold2_vs_hold0": pair("hold0", "hold2", lang, c)}
                    for lang in ("en", "id") for c in CH}

# E. erasure difference AA-trim minus LA2 (per-index mean, bootstrap)
out["erasure"] = {}
for lang in ("en", "id"):
    for c in CH:
        x = stats.per_index_mean(df, "aa_trim", lang, c, "erasure", "cu", ids)
        y = stats.per_index_mean(df, "la2", lang, c, "erasure", "cu", ids)
        d = x - y
        bd = (D.W @ d) / D.W.sum(1)
        out["erasure"][f"{lang}@{c}"] = {"aa": float(x.mean()), "la": float(y.mean()), "diff": float(d.mean()),
                                         "ci": stats.ci(bd), "p_boot": stats.boot_p(bd)}

# F. held-back words (descriptive, per language)
out["held_back"] = stats.m4(D)

(data / "within_lang.json").write_text(json.dumps(out, indent=1, default=float))
print("done")
