"""GPU-time estimate for the full job list, from a check run on a few sentence indices."""
from pathlib import Path

import pandas as pd

from .common import read_jsonl


def _mode_factor(job, m):
    """A check job that lagged ran CA and then CU again; a single-mode job runs about half of that."""
    modes = job.get("modes", ("ca", "cu"))
    if len(modes) == 1 and (m["job"].get("modes") is None or len(m["job"]["modes"]) == 2):
        return 1 - 0.5 * (m["lag_share"] or 0)
    return 1.0


def estimate(check_results_dir, check_jobs, full_jobs, manifest, n_gpus=1, load_s=60.0):
    """Wall seconds per audio second of each check job, scaled to the audio of the full job.
    A full job with no check counterpart (same kind, model, beam) uses the nearest chunk size."""
    measured = {}
    for job in check_jobs:
        lines = read_jsonl(Path(check_results_dir) / f"{job['id']}.jsonl")
        if not lines:
            continue
        audio = sum(l["dur"] for l in lines)
        wall = sum(l.get("wall", 0.0) for l in lines)
        measured[job["id"]] = {"job": job, "s_per_audio_s": wall / audio, "lag_share":
                               sum(bool((l.get("ca") or {}).get("lag")) for l in lines) / len(lines)}

    def audio_seconds(job):
        recs = manifest["full"] if job.get("set") == "full" else manifest["paired"]
        ids = set(job["ids"]) if job.get("ids") is not None else None
        return sum(r["dur"] for r in recs if r["lang"] == job["lang"] and (ids is None or r["idx"] in ids))

    def match(job):
        if job["id"] in measured:
            return measured[job["id"]]
        cands = [m for m in measured.values()
                 if m["job"]["kind"] == job["kind"] and m["job"]["lang"] == job["lang"]
                 and m["job"].get("model") == job.get("model") and m["job"].get("beam", 1) == job.get("beam", 1)]
        if not cands:
            return None
        return min(cands, key=lambda m: abs(m["job"].get("chunk", 0) - job.get("chunk", 0)))

    rows = []
    for job in full_jobs:
        m = match(job)
        a = audio_seconds(job)
        rows.append({"job": job["id"], "audio_h": a / 3600,
                     "measured_from": m["job"]["id"] if m else None,
                     "s_per_audio_s": m["s_per_audio_s"] if m else None,
                     "ca_lag_share": m["lag_share"] if m else None,
                     "est_gpu_h": (m["s_per_audio_s"] * a * _mode_factor(job, m) + load_s) / 3600 if m else None})
    t = pd.DataFrame(rows)
    total = t.est_gpu_h.sum()
    return t, {"total_gpu_hours": float(total), "wall_hours_with_gpus": float(total / n_gpus),
               "jobs_without_estimate": t[t.est_gpu_h.isna()].job.tolist()}
