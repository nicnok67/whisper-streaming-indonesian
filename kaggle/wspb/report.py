"""Run every analysis on whatever has finished, and write tables, Figure 1 and a summary."""
import json
from pathlib import Path

import numpy as np

from . import stats
from .common import save_json
from .data import index_features
from .metrics import collect

LABEL = {"hold0": "Hold-0", "hold2": "Hold-2", "la2": "LocalAgreement-2",
         "la2_beam5": "LocalAgreement-2, beam 5 (sensitivity)",
         "aa_keep": "AlignAtt-keep (SimulStreaming default)", "aa_trim": "AlignAtt-trim",
         "ws_anchor": "Whisper-Streaming as released", "offline_v3": "Offline large-v3 (greedy)"}


def _safe(fn, *a, **k):
    """One analysis failing (e.g. too few indices in a check run) must not stop the others."""
    try:
        return fn(*a, **k)
    except Exception as e:  # noqa: BLE001 - reported in stats.json
        return {"error": f"{type(e).__name__}: {e}"}


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def _md(t):
    try:
        return t.to_markdown(index=False)
    except ImportError:
        return t.to_string(index=False)


def figure1(table, out_dir, primary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pols = ["hold0", "hold2", "la2", "aa_keep", "aa_trim"]
    markers = {"hold0": "s", "hold2": "D", "la2": "o", "aa_keep": "^", "aa_trim": "v"}
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), sharey=True)
    for ax, lang, title in zip(axes, ("en", "id"), ("English", "Indonesian")):
        t = table[table.lang == lang]
        for p in pols:
            d = t[t.policy == p].sort_values("chunk")
            if d.empty:
                continue
            ax.plot(d.LAAL_cu, d.WER, marker=markers[p], ms=4, lw=1.4 if p in ("la2", primary) else 1.0,
                    label=LABEL[p])
            for _, r in d.iterrows():
                ax.annotate(f"{r.chunk:g}", (r.LAAL_cu, r.WER), fontsize=6, xytext=(2, 2),
                            textcoords="offset points")
        off = t[t.policy == "offline_v3"]
        if len(off):
            ax.axhline(off.WER.iloc[0], color="0.5", ls="--", lw=0.8, label=LABEL["offline_v3"])
        anc = t[t.policy == "ws_anchor"]
        if len(anc):
            ax.plot(anc.LAAL_cu, anc.WER, "o", mfc="none", mec="k", ms=6, label=LABEL["ws_anchor"])
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("LAAL, computation-unaware (s)", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(alpha=0.3, lw=0.5)
    axes[0].set_ylabel("WER (%)", fontsize=8)
    h, l = axes[1].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, fontsize=6.5, frameon=False, bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    for ext in ("png", "pdf"):
        fig.savefig(Path(out_dir) / f"figure1_wer_laal.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def run(cfg, manifest, speech, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = collect(cfg["results_dir"], cfg["jobs"], manifest)
    if df.empty:
        print("No results yet.")
        return None
    df.drop(columns=["text"]).to_csv(out_dir / "per_recording_metrics.csv", index=False)
    table = stats.summary_table(df)
    table.to_csv(out_dir / "summary_by_run.csv", index=False)

    primary = cfg["primary_aa"]
    ids = manifest["paired_ids"]
    if cfg.get("quick_ids") is not None:
        ids = [i for i in ids if i in set(cfg["quick_ids"])]
    D = stats.Data(df, ids, B=cfg["bootstrap_B"], seed=cfg["seed"])
    spw = index_features(manifest, speech)
    streaming = ["hold0", "hold2", "la2", primary]
    margin = cfg.get("equivalence_margin", 0.42)
    h3_primary = _safe(stats.h3, D, primary, margin=margin)
    h3_matched_cu = _safe(stats.h3_matched_latency, D, primary, lat_mode="cu", anchor="la", margin=margin)
    h3_matched_ca = _safe(stats.h3_matched_latency, D, primary, lat_mode="ca", anchor="la", margin=margin)
    h3_matched_rev = _safe(stats.h3_matched_latency, D, primary, lat_mode="cu", anchor="aa", margin=margin)
    res = {
        "primary_alignatt": primary,
        "n_indices": len(ids),
        "equivalence_margin": margin,
        "H3_primary": h3_primary,
        "H3_matched_latency_primary_cu": h3_matched_cu,
        "H3_matched_latency_secondary_ca": h3_matched_ca,
        "H3_matched_latency_secondary_reverse_anchor": h3_matched_rev,
        "H3_CER_secondary": _safe(stats.h3, D, primary, metric="cer", margin=margin),
        "H3_equal_index_weight_sensitivity": _safe(stats.h3, D, primary, equal_weight=True, margin=margin),
        "H3_LA_beam5_sensitivity": _safe(stats.h3, D, primary, la="la2_beam5", margin=margin),
        "H3_other_alignatt": _safe(stats.h3, D, "aa_trim" if primary == "aa_keep" else "aa_keep"),
        "H3_without_number_indices": _safe(stats.h3, D, primary, exclude=manifest["number_ids"]),
        "H4_alignatt_primary": _safe(stats.h4, D, primary),
        "H4_localagreement_secondary": _safe(stats.h4, D, "la2"),
        "H4_without_number_indices": _safe(stats.h4, D, primary, exclude=manifest["number_ids"]),
        "H1_ranking": _safe(stats.h1, D, streaming, [0.5, 1.0, 1.2]),
        "H2_language_gap": _safe(stats.h2, D, streaming, [0.5, 1.0, 1.2, 2.0]),
        "H5_alignatt_latency": _safe(stats.h5, D, primary, [0.5, 1.0, 1.2, 1.5, 2.0], mode="cu"),
        "H5_alignatt_latency_ca_subset": _safe(stats.h5, D, primary, [1.0, 1.2], mode="ca"),
        "M3_word_duration_slope": _safe(stats.m3, D, spw, la="la2", aa=primary),
        "M4_held_back_word_excess": _safe(stats.m4, D, "aa_trim"),
        "M5_trim_gain": _safe(stats.m5_trim_gain, D),
        "offline_setup_check": _safe(stats.offline_check, df, manifest, B=cfg["bootstrap_B"], seed=cfg["seed"]),
    }
    res = _clean(res)
    save_json(res, out_dir / "stats.json")
    _safe(figure1, table, out_dir, primary)

    t1 = _safe(stats.table1, h3_primary, h3_matched_cu)
    if not hasattr(t1, "to_csv"):
        import pandas as pd
        t1 = pd.DataFrame([t1])
    t1.to_csv(out_dir / "table1_h3.csv", index=False)
    t2 = table[np.isclose(table.chunk.fillna(-1), 1.2) | (table.policy == "ws_anchor")]
    t2.to_csv(out_dir / "table2_metrics_1.2s.csv", index=False)
    md_table = _md(table.round(3))
    lines = ["# Results summary", "",
             f"Primary AlignAtt variant: **{LABEL.get(primary, primary)}**. Text metrics: computation-unaware runs; "
             "latency: computation-unaware LAAL (all indices; primary) and computation-aware LAAL on the virtual "
             "clock (CA timing subset of indices; secondary).", "",
             "## Table 1 (H3)", "", _md(t1.round(3).T.reset_index()), "",
             "## H3 (main result)", "```", json.dumps(res["H3_primary"], indent=1)[:6000], "```", "",
             "## H3 at matched latency (computation-unaware LAAL, primary)", "```",
             json.dumps(res["H3_matched_latency_primary_cu"], indent=1)[:4000], "```", "",
             "## Offline setup check", "```", json.dumps(res["offline_setup_check"], indent=1), "```", "",
             "## WER and latency by run", "", md_table, ""]
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    return res, table
