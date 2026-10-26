"""Planned analyses (fixed before the runs). Primary text metrics use the computation-unaware (CU) records,
whose output depends only on the audio and the chunk size, not on the GPU.

Bootstrap: sentence indices resampled with replacement, the same indices for both languages
(paired), B resamples (10,000 by default), fixed seed. Two-sided bootstrap p-value:
2 * min(P(stat* <= 0), P(stat* >= 0)). Holm correction within each family.

H3 estimand (fixed before the runs, review R2). For a language L and chunk size c,
    R_L = (E_LA - E_AA) / E_LA,
where E_P is the pooled error count of policy P over all recordings of the paired indices
(a ratio of sums, never a mean of per-sentence ratios, so sentences with zero errors need no
special handling; N is the same for both policies, so the ratio of WERs is the same number).
R is recomputed inside every bootstrap resample; a resample with E_LA = 0 is dropped (reported).
Delta = R_ID - R_EN. Co-reported: the absolute gap
    A = (WER_LA,ID - WER_AA,ID) - (WER_LA,EN - WER_AA,EN)   (WER points).
Equivalence ("ruled out"): the 95% CI of Delta lies entirely inside +/- equivalence_margin
(default 0.42 = the 7%-49% spread of Simul-Whisper's per-language results). The smallest change
the data exclude, max(|lo|, |hi|), is always reported.

H3 at matched latency (fixed before the runs, review R1). For each language and H3 chunk size c,
AlignAtt's WER is linearly interpolated along AlignAtt's own WER-LAAL curve (its chunk sizes
0.5-2.0 s) at LocalAgreement's LAAL at c (primary); the reverse anchoring is secondary. No
extrapolation. Latency axis: computation-unaware LAAL (primary; it does not depend on the GPU),
computation-aware LAAL (secondary). R*, Delta* as above,
recomputed per resample. Tie-break: when the fixed-chunk and matched-latency verdicts differ, both
are reported and the abstract uses the weaker claim ("bounds"/"suggests", never "shows").
"""
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

Z_MDE = 2.241 + 0.842   # z(1 - 0.025/2) + z(0.80)


def holm(pvals):
    p = np.asarray(pvals, float)
    order = np.argsort(p)
    adj = np.empty_like(p)
    running = 0.0
    m = len(p)
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * p[i])
        adj[i] = min(1.0, running)
    return adj.tolist()


def boot_p(dist):
    dist = np.asarray(dist)
    dist = dist[np.isfinite(dist)]
    if len(dist) == 0:
        return np.nan
    return float(min(1.0, 2 * min((dist <= 0).mean(), (dist >= 0).mean())))


def ci(dist):
    dist = np.asarray(dist)
    dist = dist[np.isfinite(dist)]
    return [float(np.percentile(dist, 2.5)), float(np.percentile(dist, 97.5))] if len(dist) else [np.nan, np.nan]


class Data:
    """Per-index pooled error counts for every (policy, lang, chunk) in the CU records."""

    def __init__(self, df, ids, B=10000, seed=20261022):
        self.df = df
        self.ids = list(ids)
        self.n = len(self.ids)
        rng = np.random.default_rng(seed)
        self.W = rng.multinomial(self.n, np.full(self.n, 1 / self.n), size=B).astype(np.float64)
        self._cache = {}

    def counts(self, policy, lang, chunk=None, mode="cu", exclude=(), metric="wer", equal_weight=False):
        """Per-index (errors, reference units). metric: "wer" (words) or "cer" (characters).
        equal_weight: every sentence index weighs the same whatever its number of recordings
        (sensitivity analysis; the primary analysis pools recordings)."""
        key = (policy, lang, chunk, mode, tuple(sorted(exclude)), metric, equal_weight)
        if key in self._cache:
            return self._cache[key]
        d = self.df[(self.df.policy == policy) & (self.df.lang == lang) & (self.df["mode"] == mode)]
        if chunk is not None:
            d = d[np.isclose(d.chunk, chunk)]
        if metric == "cer":
            d = d.assign(E=d.CE.astype(float), N=d.CN.astype(float))
        else:
            d = d.assign(E=(d.S + d.D + d.I).astype(float), N=d.N.astype(float))
        if equal_weight:
            k = d.n_rec_idx.astype(float)
            d = d.assign(E=d.E / k, N=d.N / k)
        g = d.groupby("idx")[["E", "N"]].sum()
        g = g.reindex(self.ids)
        if g.isna().any().any():
            res = None                               # incomplete run: analysis skipped
        else:
            E, N = g.E.to_numpy(float), g.N.to_numpy(float)
            mask = np.array([i not in set(exclude) for i in self.ids], float)
            res = (E * mask, N * mask)
        self._cache[key] = res
        return res

    def wer(self, policy, lang, chunk=None, mode="cu", exclude=(), metric="wer", equal_weight=False):
        c = self.counts(policy, lang, chunk, mode, exclude, metric, equal_weight)
        if c is None:
            return None, None
        E, N = c
        return E.sum() / N.sum(), (self.W @ E) / (self.W @ N)

    def latency(self, policy, lang, chunk, mode="cu", col="laal"):
        """Mean per-index latency (recordings of an index averaged first) and its bootstrap."""
        key = ("lat", policy, lang, chunk, mode, col)
        if key in self._cache:
            return self._cache[key]
        x = per_index_mean(self.df, policy, lang, chunk, col, mode, self.ids)
        if x is None:
            res = (None, None)
        else:
            ok = np.isfinite(x)
            Wk = self.W[:, ok]
            res = (float(x[ok].mean()), (Wk @ x[ok]) / Wk.sum(1))
        self._cache[key] = res
        return res


def rel_adv(D, la, aa, lang, chunk, exclude=(), metric="wer", equal_weight=False):
    w_la, b_la = D.wer(la, lang, chunk, exclude=exclude, metric=metric, equal_weight=equal_weight)
    w_aa, b_aa = D.wer(aa, lang, chunk, exclude=exclude, metric=metric, equal_weight=equal_weight)
    if w_la is None or w_aa is None:
        return None, None
    with np.errstate(divide="ignore", invalid="ignore"):
        b = np.where(b_la > 0, (b_la - b_aa) / b_la, np.nan)
    return (w_la - w_aa) / w_la, b


def abs_adv(D, la, aa, lang, chunk, exclude=(), metric="wer", equal_weight=False):
    w_la, b_la = D.wer(la, lang, chunk, exclude=exclude, metric=metric, equal_weight=equal_weight)
    w_aa, b_aa = D.wer(aa, lang, chunk, exclude=exclude, metric=metric, equal_weight=equal_weight)
    if w_la is None or w_aa is None:
        return None, None
    return w_la - w_aa, b_la - b_aa


def equivalence(ci95, margin):
    lo, hi = ci95
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return {"margin": margin, "verdict": "not available"}
    return {"margin": margin, "smallest_change_excluded": float(max(abs(lo), abs(hi))),
            "verdict": f"change larger than +/-{margin:.2f} ruled out" if -margin < lo and hi < margin
            else f"a change of +/-{margin:.2f} is not ruled out"}


def pratt(D, a, b, lang, chunk, metric="wer", equal_weight=False):
    """Wilcoxon signed-rank (Pratt) on per-index WER(a) - WER(b)."""
    ca = D.counts(a, lang, chunk, metric=metric, equal_weight=equal_weight)
    cb = D.counts(b, lang, chunk, metric=metric, equal_weight=equal_weight)
    if ca is None or cb is None:
        return None
    x = ca[0] / ca[1] - cb[0] / cb[1]
    if np.allclose(x, 0):
        return {"p": 1.0, "mean_diff": 0.0, "pooled_diff": 0.0}
    return {"p": float(wilcoxon(x, zero_method="pratt").pvalue), "mean_diff": float(x.mean()),
            "pooled_diff": float(ca[0].sum() / ca[1].sum() - cb[0].sum() / cb[1].sum())}


def verdict(p, est, pos="widens", neg="shrinks", null="no detectable change"):
    if p is None or not np.isfinite(p):
        return "not available"
    return (pos if est > 0 else neg) if p < 0.05 else null


def h3(D, aa, la="la2", chunks=(0.5, 1.0), exclude=(), metric="wer", equal_weight=False, margin=0.42):
    out = {"chunks": {}, "metric": metric, "equal_weight": equal_weight, "la": la, "aa": aa}
    pre, keep, h3p = [], [], []
    for c in chunks:
        pe = pratt(D, la, aa, "en", c, metric=metric, equal_weight=equal_weight)
        pi = pratt(D, la, aa, "id", c, metric=metric, equal_weight=equal_weight)
        r_en, b_en = rel_adv(D, la, aa, "en", c, exclude, metric, equal_weight)
        r_id, b_id = rel_adv(D, la, aa, "id", c, exclude, metric, equal_weight)
        if None in (pe, pi, r_en, r_id):
            out["chunks"][str(c)] = "not available"
            pre.append(np.nan); keep.append(np.nan); h3p.append(np.nan)
            continue
        delta, bd = r_id - r_en, b_id - b_en
        a_en, ba_en = abs_adv(D, la, aa, "en", c, exclude, metric, equal_weight)
        a_id, ba_id = abs_adv(D, la, aa, "id", c, exclude, metric, equal_weight)
        lat = {}
        for mode in ("cu", "ca"):
            for k, (p, l) in {"la_en": (la, "en"), "aa_en": (aa, "en"), "la_id": (la, "id"),
                              "aa_id": (aa, "id")}.items():
                lat[f"laal_{mode}_{k}"] = D.latency(p, l, c, mode)[0]
        ci_d = ci(bd)
        out["chunks"][str(c)] = {
            "R_en": r_en, "R_id": r_id, "delta": delta, "ci95_unadjusted": ci_d,
            "p_boot": boot_p(bd), "se": float(np.nanstd(bd)), "mde_80": float(Z_MDE * np.nanstd(bd)),
            "resamples_dropped": int((~np.isfinite(bd)).sum()),
            "equivalence": equivalence(ci_d, margin),
            "abs_gap_en": a_en, "abs_gap_id": a_id, "abs_delta": a_id - a_en,
            "abs_delta_ci95": ci(ba_id - ba_en), "abs_delta_p_boot": boot_p(ba_id - ba_en),
            "precondition_en": pe, "keeps_id": pi,
            "wer": {k: D.wer(p, l, c, exclude=exclude, metric=metric, equal_weight=equal_weight)[0]
                    for k, (p, l) in {"la_en": (la, "en"), "aa_en": (aa, "en"), "la_id": (la, "id"),
                                      "aa_id": (aa, "id")}.items()},
            "latency": lat,
        }
        pre.append(pe["p"]); keep.append(pi["p"]); h3p.append(boot_p(bd))
    # Holm within each family, over the chunk sizes whose p-value exists (a p-value can be
    # missing when too few indices make every bootstrap resample degenerate)
    for name, ps in (("precondition_holm", pre), ("keeps_holm", keep), ("h3_holm", h3p)):
        valid = [i for i, p in enumerate(ps) if np.isfinite(p)]
        if valid:
            for i, a in zip(valid, holm([ps[i] for i in valid])):
                out["chunks"][str(chunks[i])][name] = a
    for c in chunks:
        r = out["chunks"][str(c)]
        if not isinstance(r, dict):
            continue
        p_pre, p_keep = r.get("precondition_holm", np.nan), r.get("keeps_holm", np.nan)
        r["precondition_met"] = bool(p_pre < 0.05 and r["precondition_en"].get("pooled_diff", 0) > 0)
        r["keeps"] = bool(p_keep < 0.05 and r["keeps_id"].get("pooled_diff", 0) > 0)
        r["verdict"] = verdict(r.get("h3_holm", np.nan), r["delta"]) if r["precondition_met"] else \
            "not tested (precondition not met; descriptive only)"
    return out


def h4(D, policy, exclude=()):
    res = {}
    for lang in ("en", "id"):
        w1, b1 = D.wer(policy, lang, 1.0, exclude=exclude)
        w2, b2 = D.wer(policy, lang, 2.0, exclude=exclude)
        if w1 is None or w2 is None:
            return "not available"
        res[lang] = ((w1 - w2) / w2, (b1 - b2) / b2)
    d, bd = res["id"][0] - res["en"][0], res["id"][1] - res["en"][1]
    p = boot_p(bd)
    return {"P_en": res["en"][0], "P_id": res["id"][0], "diff": d, "ci95": ci(bd), "p_boot": p,
            "verdict": verdict(p, d, "larger penalty for Indonesian", "smaller penalty for Indonesian")}


def h2(D, policies, chunks):
    out = {}
    for pol in policies:
        for c in chunks:
            we, be = D.wer(pol, "en", c)
            wi, bi = D.wer(pol, "id", c)
            if we is None or wi is None:
                continue
            out[f"{pol}@{c}"] = {"wer_en": we, "wer_id": wi, "diff": wi - we, "ci95": ci(bi - be),
                                 "p_boot": boot_p(bi - be)}
    return out


def h1(D, policies, chunks):
    out = {}
    for lang in ("en", "id"):
        for c in chunks:
            w = {p: D.wer(p, lang, c)[0] for p in policies}
            if any(v is None for v in w.values()):
                continue
            out[f"{lang}@{c}"] = {"wer": w, "ranking": sorted(w, key=w.get)}
    return out


def per_index_mean(df, policy, lang, chunk, col, mode, ids):
    d = df[(df.policy == policy) & (df.lang == lang) & (df["mode"] == mode) & np.isclose(df.chunk, chunk)]
    s = d.groupby("idx")[col].mean().reindex(ids)
    return None if s.isna().all() else s.to_numpy(float)


def h5(D, aa, chunks, mode="cu"):
    """AlignAtt LAAL, Indonesian minus English, per chunk size. mode="cu" (primary, all indices) or
    "ca" (secondary, CA timing subset)."""
    out = {"mode": mode}
    for c in chunks:
        e = per_index_mean(D.df, aa, "en", c, "laal", mode, D.ids)
        i = per_index_mean(D.df, aa, "id", c, "laal", mode, D.ids)
        if e is None or i is None:
            continue
        x = i - e
        ok = np.isfinite(x)
        bd = (D.W[:, ok] @ x[ok]) / D.W[:, ok].sum(1)
        out[str(c)] = {"laal_en": float(np.nanmean(e)), "laal_id": float(np.nanmean(i)),
                       "n_indices": int(ok.sum()),
                       "diff": float(np.nanmean(x)), "ci95": ci(bd), "p_boot": boot_p(bd)}
    return out


def m3(D, sec_per_word, chunk=1.0, la="la2", aa="aa_keep"):
    """WLS per language: WER_LA - WER_AA (per index) ~ speech seconds per word + offline WER."""
    out = {}
    for lang in ("en", "id"):
        cl, ca_, co = D.counts(la, lang, chunk), D.counts(aa, lang, chunk), D.counts("offline_v3", lang, None, "offline")
        if None in (cl, ca_, co):
            continue
        y = cl[0] / cl[1] - ca_[0] / ca_[1]
        x = np.array([sec_per_word.get(f"{lang}:{i}", np.nan) for i in D.ids])
        z = co[0] / co[1]
        ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
        X = np.column_stack([np.ones(ok.sum()), x[ok], z[ok]])
        w = cl[1][ok]

        def fit(weights):
            XtW = X.T * weights
            return np.linalg.solve(XtW @ X, XtW @ y[ok])

        beta = fit(w)
        Wb = D.W[:, ok] * w
        XtWX = np.einsum("bn,ni,nj->bij", Wb, X, X)
        XtWy = np.einsum("bn,ni,n->bi", Wb, X, y[ok])
        slopes = np.array([np.linalg.lstsq(A, v, rcond=None)[0][1] for A, v in zip(XtWX, XtWy)])
        p = boot_p(slopes)
        out[lang] = {"slope_sec_per_word": float(beta[1]), "ci95": ci(slopes), "p_boot": p,
                     "verdict": verdict(p, beta[1], "supports M3", "contradicts M3", "does not support M3")}
    return out


def m4(D, aa_trim="aa_trim", chunks=(0.5, 1.0)):
    """X = T / E per language; T = share of held-back words that come back changed,
    E = share of committed words that are substituted or inserted."""
    out = {}
    df = D.df
    for c in chunks:
        res = {}
        for lang in ("en", "id"):
            d = df[(df.policy == aa_trim) & (df.lang == lang) & (df["mode"] == "cu") & np.isclose(df.chunk, c)]
            if d.empty:
                break
            g = d.assign(unconf=d.tail_total - d.tail_conf, err_h=d.S + d.I).groupby("idx")[
                ["unconf", "tail_total", "err_h", "H"]].sum().reindex(D.ids).fillna(0).to_numpy(float).T
            u, t, e, h = g
            X = (u.sum() / t.sum()) / (e.sum() / h.sum())
            Xb = ((D.W @ u) / (D.W @ t)) / ((D.W @ e) / (D.W @ h))
            res[lang] = (X, Xb, u.sum() / t.sum(), e.sum() / h.sum())
        if len(res) < 2:
            continue
        d, bd = res["id"][0] - res["en"][0], res["id"][1] - res["en"][1]
        lo, hi = ci(bd)
        v = "(b) supported" if lo > 0 else "(b) contradicted" if hi < 0 else \
            "(b) not supported; (a) remains the simpler reading, not a demonstrated one"
        out[str(c)] = {"X_en": res["en"][0], "X_id": res["id"][0], "T_en": res["en"][2], "T_id": res["id"][2],
                       "E_en": res["en"][3], "E_id": res["id"][3], "diff": d, "ci95": [lo, hi], "reading": v}
    return out


def m5_trim_gain(D, la="la2", chunks=(0.5, 1.0)):
    """Added before data (after finding that SimulStreaming keeps the last word by default):
    gain in relative advantage from holding back the last word, Indonesian minus English."""
    out = {}
    for c in chunks:
        g = {}
        for lang in ("en", "id"):
            rk, bk = rel_adv(D, la, "aa_keep", lang, c)
            rt, bt = rel_adv(D, la, "aa_trim", lang, c)
            if rk is None or rt is None:
                break
            g[lang] = (rt - rk, bt - bk)
        if len(g) < 2:
            continue
        d, bd = g["id"][0] - g["en"][0], g["id"][1] - g["en"][1]
        p = boot_p(bd)
        out[str(c)] = {"gain_en": g["en"][0], "gain_id": g["id"][0], "diff": d, "ci95": ci(bd),
                       "p_boot": p, "verdict": verdict(p, d, "trimming helps Indonesian more",
                                                       "trimming helps English more")}
    return out


def _interp_rows(x, xp, fp):
    """Per resample b: interpolate fp[:, b] against xp[:, b] at x[b]; NaN outside the range."""
    out = np.full(len(x), np.nan)
    for b in range(len(x)):
        ok = np.isfinite(xp[:, b]) & np.isfinite(fp[:, b])
        if ok.sum() < 2 or not np.isfinite(x[b]):
            continue
        o = np.argsort(xp[ok, b])
        out[b] = np.interp(x[b], xp[ok, b][o], fp[ok, b][o], left=np.nan, right=np.nan)
    return out


def h3_matched_latency(D, aa, la="la2", chunks=(0.5, 1.0), curve_chunks=(0.5, 1.0, 1.2, 1.5, 2.0),
                       lat_mode="cu", anchor="la", margin=0.42):
    """anchor="la" (primary): at LocalAgreement's LAAL at chunk c, AlignAtt's WER is interpolated
    along AlignAtt's own WER-LAAL curve. anchor="aa" (secondary): the reverse. No extrapolation."""
    fixed, curve = (la, aa) if anchor == "la" else (aa, la)
    out = {"latency_axis": "LAAL, " + ("computation-unaware" if lat_mode == "cu" else "computation-aware"),
           "anchor": fixed, "interpolated": curve, "chunks": {}}
    for c in chunks:
        res = {}
        for lang in ("en", "id"):
            pts = [(k, D.wer(curve, lang, k), D.latency(curve, lang, k, lat_mode)) for k in curve_chunks]
            pts = [(k, w, l) for k, w, l in pts if w[0] is not None and l[0] is not None]
            w_fx, b_fx = D.wer(fixed, lang, c)
            l_fx, bl_fx = D.latency(fixed, lang, c, lat_mode)
            if len(pts) < 2 or w_fx is None or l_fx is None:
                break
            xp = np.array([l[0] for _, _, l in pts])
            fp = np.array([w[0] for _, w, _ in pts])
            o = np.argsort(xp)
            w_cv = float(np.interp(l_fx, xp[o], fp[o], left=np.nan, right=np.nan))
            bw_cv = _interp_rows(bl_fx, np.stack([l[1] for _, _, l in pts]), np.stack([w[1] for _, w, _ in pts]))
            w_la, w_aa = (w_fx, w_cv) if anchor == "la" else (w_cv, w_fx)
            b_la, b_aa = (b_fx, bw_cv) if anchor == "la" else (bw_cv, b_fx)
            with np.errstate(divide="ignore", invalid="ignore"):
                r = (w_la - w_aa) / w_la if w_la > 0 else np.nan
                br = np.where(b_la > 0, (b_la - b_aa) / b_la, np.nan)
            res[lang] = {"laal_anchor": l_fx, "curve_laal_range": [float(xp.min()), float(xp.max())],
                         "curve_chunks_used": [k for k, _, _ in pts],
                         "wer_la": w_la, "wer_aa": w_aa, "R": r, "_b": br}
        if len(res) < 2:
            out["chunks"][str(c)] = "not available"
            continue
        d = res["id"]["R"] - res["en"]["R"]
        bd = res["id"].pop("_b") - res["en"].pop("_b")
        if not np.isfinite(d):
            out["chunks"][str(c)] = {**res, "verdict": "not available (the anchor's LAAL is outside the "
                                     "other policy's latency range in at least one language; no extrapolation)"}
            continue
        p = boot_p(bd)
        cd = ci(bd)
        out["chunks"][str(c)] = {**res, "delta": d, "ci95_unadjusted": cd, "p_boot": p,
                                 "resamples_outside_range": int((~np.isfinite(bd)).sum()),
                                 "equivalence": equivalence(cd, margin), "verdict": verdict(p, d)}
    return out


def table1(h3_fixed, h3_matched):
    """Table 1 rows (0.5 s, 1.0 s): WER and latency per policy and language, R, Delta, and the
    matched-latency Delta (review R1: latency is shown next to every WER used for H3)."""
    rows = []
    for c, r in h3_fixed["chunks"].items():
        if not isinstance(r, dict):
            continue
        m = h3_matched["chunks"].get(c, {})
        m = m if isinstance(m, dict) else {}
        row = {"chunk_s": float(c)}
        for lang in ("en", "id"):
            row[f"WER_LA_{lang}"] = 100 * r["wer"][f"la_{lang}"]
            row[f"WER_AA_{lang}"] = 100 * r["wer"][f"aa_{lang}"]
            for mode in ("cu", "ca"):
                row[f"LAAL{mode}_LA_{lang}"] = r["latency"][f"laal_{mode}_la_{lang}"]
                row[f"LAAL{mode}_AA_{lang}"] = r["latency"][f"laal_{mode}_aa_{lang}"]
            row[f"R_{lang}"] = 100 * r[f"R_{lang}"]
        row["p_precondition_holm"] = r.get("precondition_holm")
        row["p_keeps_holm"] = r.get("keeps_holm")
        row["Delta_pts"] = 100 * r["delta"]
        row["Delta_ci_lo"], row["Delta_ci_hi"] = [100 * v for v in r["ci95_unadjusted"]]
        row["p_H3_holm"] = r.get("h3_holm")
        row["absDelta_pts"] = 100 * r["abs_delta"]
        row["absDelta_ci_lo"], row["absDelta_ci_hi"] = [100 * v for v in r["abs_delta_ci95"]]
        row["Delta_matched_pts"] = 100 * m["delta"] if "delta" in m else np.nan
        lo, hi = m.get("ci95_unadjusted", [np.nan, np.nan])
        row["Delta_matched_ci_lo"], row["Delta_matched_ci_hi"] = 100 * lo, 100 * hi
        row["verdict_fixed"] = r.get("verdict")
        row["verdict_matched"] = m.get("verdict", "not available")
        row["equivalence_fixed"] = r["equivalence"]["verdict"]
        rows.append(row)
    return pd.DataFrame(rows)


def offline_check(df, manifest, B=10000, seed=20261022):
    """large-v2 (beam 5 + fallback) on the full test sets vs Radford et al. (2023), Table 11."""
    published = {"id": 7.1, "en": 4.2}
    out = {}
    rng = np.random.default_rng(seed)
    for lang in ("en", "id"):
        d = df[(df.policy == "offline_v2") & (df.lang == lang)]
        if d.empty:
            continue
        g = d.assign(E=d.S + d.D + d.I).groupby("idx")[["E", "N"]].sum()
        E, N = g.E.to_numpy(float), g.N.to_numpy(float)
        W = rng.multinomial(len(E), np.full(len(E), 1 / len(E)), size=B)
        wb = 100 * (W @ E) / (W @ N)
        lo, hi = ci(wb)
        out[lang] = {"wer": 100 * E.sum() / N.sum(), "ci95": [lo, hi], "published": published[lang],
                     "pass": bool(lo <= published[lang] <= hi), "recordings": int(len(d))}
    return out


def summary_table(df):
    """Pooled WER and mean latency per policy, language, chunk (CU text; CA latency)."""
    rows = []
    for (pol, lang, chunk), d in df[df["mode"] == "cu"].groupby(["policy", "lang", "chunk"], dropna=False):
        ca = df[(df.policy == pol) & (df.lang == lang) & (df["mode"] == "ca") & np.isclose(df.chunk, chunk)]
        N = d.N.sum()
        rows.append({
            "policy": pol, "lang": lang, "chunk": chunk, "recordings": len(d),
            "WER": 100 * (d.S + d.D + d.I).sum() / N, "sub": 100 * d.S.sum() / N,
            "del": 100 * d.D.sum() / N, "ins": 100 * d.I.sum() / N,
            "CER": 100 * d.CE.sum() / d.CN.sum(), "splits_per_100w": 100 * d.splits.sum() / N,
            "merges_per_100w": 100 * d.merges.sum() / N,
            "LAAL_cu": d.laal.mean(), "LAAL_ca": ca.laal.mean() if len(ca) else np.nan,
            "first_cu": d["first"].mean(), "first_ca": ca["first"].mean() if len(ca) else np.nan,
            "RTF": d.compute.sum() / d.dur.sum(),
            "erasure": d.erasure.mean(), "erasure_raw": d.erasure_raw.mean(),
            "tail_conf": d.tail_conf.sum() / d.tail_total.sum() if d.tail_total.sum() else np.nan,
            "spread": d["spread"].mean() if "spread" in d else np.nan,
            "share_lagging": ca.lag.mean() if len(ca) else np.nan,
        })
    for (pol, lang), d in df[df["mode"] == "offline"].groupby(["policy", "lang"]):
        N = d.N.sum()
        rows.append({"policy": pol, "lang": lang, "chunk": np.nan, "recordings": len(d),
                     "WER": 100 * (d.S + d.D + d.I).sum() / N, "sub": 100 * d.S.sum() / N,
                     "del": 100 * d.D.sum() / N, "ins": 100 * d.I.sum() / N,
                     "CER": 100 * d.CE.sum() / d.CN.sum(), "splits_per_100w": 100 * d.splits.sum() / N,
                     "merges_per_100w": 100 * d.merges.sum() / N,
                     "RTF": d.compute.sum() / d.dur.sum()})
    return pd.DataFrame(rows).sort_values(["lang", "policy", "chunk"])
