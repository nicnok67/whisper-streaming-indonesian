"""Per-recording metrics from the saved simulation records.

Transcript: committed pieces joined by plain concatenation. A word's delay is the time at which
its last character was committed (so a word split across chunks counts when it is complete).

WER          Whisper normaliser per language, word Levenshtein alignment.
CER          same normaliser, spaces removed (insensitive to word segmentation; review R5).
split/merge  word-segmentation errors in the WER alignment ("dirumah" vs "di rumah").
LAAL         Papi et al. (2022), on raw output words; tau from the source time consumed (step end).
             CU: delay = step end (finish = duration). CA: delay = emission on the virtual clock.
first output delay of the first output word (CU and CA).
RTF          total compute time / duration (CU record).
erasure      Arivazhagan et al. (2020) on the display = committed text + uncommitted tail:
             sum over updates of (|previous display| - common prefix) / |final transcript|;
             primary after BasicTextNormalizer, secondary on the raw display.
tail conf.   share of displayed tail words later committed unchanged at the same position.
M4 (E)       share of committed (hypothesis-side) words that are substituted or inserted.
"""
import re

import numpy as np

from .align import align, counts
from .text import cer_counts, norm_basic, split_merge, words_wer

_WORD = re.compile(r"\S+")


def word_delays(pieces, emits, ends):
    full = "".join(pieces)
    step_of_char = np.empty(len(full), dtype=np.int32)
    pos = 0
    for k, p in enumerate(pieces):
        step_of_char[pos:pos + len(p)] = k
        pos += len(p)
    words, d_emit, d_src = [], [], []
    for m in _WORD.finditer(full):
        k = int(step_of_char[m.end() - 1])
        words.append(m.group())
        d_emit.append(emits[k])
        d_src.append(ends[k])
    return full.strip(), words, np.array(d_emit), np.array(d_src)


def laal(delays, src, dur, n_hyp, n_ref):
    if n_hyp == 0:
        return np.nan
    reach = np.nonzero(src >= dur - 1e-6)[0]
    tau = int(reach[0]) + 1 if len(reach) else n_hyp
    rate = dur / max(n_hyp, n_ref)
    i = np.arange(tau)
    return float(np.mean(delays[:tau] - i * rate))


def _lcp(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def display_metrics(pieces, tails, final_text):
    final_n = norm_basic(final_text).split()
    final_r = final_text.split()
    prev_n, prev_r = [], []
    er_n = er_r = 0
    conf = total = 0
    committed = ""
    for piece, tail in zip(pieces, tails):
        committed += piece
        disp_n = norm_basic(committed + tail).split()
        disp_r = (committed + tail).split()
        er_n += len(prev_n) - _lcp(prev_n, disp_n)
        er_r += len(prev_r) - _lcp(prev_r, disp_r)
        prev_n, prev_r = disp_n, disp_r
        if tail.strip():
            start = len(norm_basic(committed).split())
            for j, w in enumerate(norm_basic(tail).split()):
                total += 1
                conf += int(start + j < len(final_n) and final_n[start + j] == w)
    return (er_n / max(1, len(final_n)), er_r / max(1, len(final_r)), conf, total)


def recording_metrics(rec, policy, mode_rec, ref, lang):
    steps = mode_rec["steps"]
    emits = [s[1] for s in steps]
    ends = [s[0] for s in steps]
    pieces = [p for p, _ in mode_rec["policies"][policy]]
    tails = [t for _, t in mode_rec["policies"][policy]]
    final, words, d_emit, d_src = word_delays(pieces, emits, ends)
    ref_w, hyp_w = words_wer(ref, lang), words_wer(final, lang)
    ops = align(ref_w, hyp_w)
    c = counts(ops)
    sp, mg = split_merge(ops, ref_w, hyp_w)
    ce, cn = cer_counts(ref, final, lang)
    n_ref_raw = len(ref.split())
    er_n, er_r, conf, total = display_metrics(pieces, tails, final)
    dur = rec["dur"]
    return {
        "S": c["S"], "D": c["D"], "I": c["I"], "C": c["C"], "N": len(ref_w), "H": len(hyp_w),
        "CE": ce, "CN": cn, "splits": sp, "merges": mg,
        "laal": laal(d_emit, d_src, dur, len(words), n_ref_raw),
        "first": float(d_emit[0]) if len(words) else np.nan,
        "compute": float(sum(s[2] for s in steps)),
        "erasure": er_n, "erasure_raw": er_r, "tail_conf": conf, "tail_total": total,
        "text": final,
    }


def offline_metrics(line, ref, lang):
    ref_w, hyp_w = words_wer(ref, lang), words_wer(line["text"], lang)
    ops = align(ref_w, hyp_w)
    c = counts(ops)
    sp, mg = split_merge(ops, ref_w, hyp_w)
    ce, cn = cer_counts(ref, line["text"], lang)
    return {"S": c["S"], "D": c["D"], "I": c["I"], "C": c["C"], "N": len(ref_w), "H": len(hyp_w),
            "CE": ce, "CN": cn, "splits": sp, "merges": mg,
            "compute": line.get("compute", np.nan), "text": line["text"].strip()}


def collect(results_dir, jobs, manifest):
    """One row per (job, policy, mode, recording)."""
    import pandas as pd
    from .common import read_jsonl

    from collections import Counter
    refs = {r["key"]: r for r in manifest["full"]}
    # recordings per (language, sentence index) in the paired set, for the equal-weight sensitivity
    n_rec = Counter((r["lang"], r["idx"]) for r in manifest["paired"])
    rows = []
    for job in jobs:
        lines = read_jsonl(f"{results_dir}/{job['id']}.jsonl")
        for line in lines:
            r = refs[line["key"]]
            base = {"job": job["id"], "kind": job["kind"], "lang": line["lang"], "idx": line["idx"],
                    "key": line["key"], "dur": line["dur"], "chunk": job.get("chunk", np.nan)}
            if job["kind"] == "offline":
                rows.append({**base, "policy": job["policy_name"], "mode": "offline",
                             "n_rec_idx": n_rec.get((line["lang"], line["idx"]), 1),
                             **offline_metrics(line, r["ref"], r["lang"])})
                continue
            suffix = job.get("policy_suffix", "")
            # CA timing jobs (subset of indices) contribute latency rows only: their CU records, if
            # any, would duplicate the main jobs' text results for those indices
            modes = ("ca",) if job.get("ca_timing") else ("cu", "ca")
            ca_line = line.get("ca") or {}
            for mode in modes:
                mrec = line.get(mode)
                if not mrec:
                    continue
                for pol in mrec["policies"]:
                    m = recording_metrics(line, pol, mrec, r["ref"], r["lang"])
                    m["n_rec_idx"] = n_rec[(line["lang"], line["idx"])]
                    if mode == "cu" and pol.startswith("aa"):
                        sp = [a["spread"] for a in mrec.get("aux", []) if a and a.get("spread") is not None]
                        m["spread"] = float(np.mean(sp)) if sp else np.nan
                    m["lag"] = bool(ca_line["lag"]) if ca_line else np.nan
                    m["cu_derived"] = bool((line.get("cu") or {}).get("derived", False))
                    rows.append({**base, "policy": pol + suffix, "mode": mode, **m})
    return pd.DataFrame(rows)
