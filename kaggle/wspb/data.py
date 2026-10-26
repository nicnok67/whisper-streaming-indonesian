"""FLEURS test sets: download, paired manifest, audio, and data statistics."""
import csv
import tarfile
from collections import defaultdict
from pathlib import Path

import numpy as np

from .common import FLEURS_REVISION, LANGS, SR, load_json, save_json
from .text import has_number, norm_basic


def fetch_fleurs(data_dir):
    """Download test.tsv and test audio for both languages and extract the audio."""
    from huggingface_hub import hf_hub_download

    data_dir = Path(data_dir)
    for code in LANGS.values():
        for f in (f"data/{code}/test.tsv", f"data/{code}/audio/test.tar.gz"):
            hf_hub_download("google/fleurs", f, repo_type="dataset",
                            revision=FLEURS_REVISION, local_dir=str(data_dir))
        out = data_dir / "data" / code / "audio" / "test"
        marker = out / ".extracted"
        if not marker.exists():
            out.mkdir(parents=True, exist_ok=True)
            with tarfile.open(data_dir / "data" / code / "audio" / "test.tar.gz") as tar:
                tar.extractall(out)
            marker.touch()


def read_tsv(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for r in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            rows.append({"idx": int(r[0]), "file": r[1], "ref": r[2],
                         "samples": int(r[5]), "gender": r[6]})
    return rows


def build_manifest(data_dir, max_dur=30.0):
    """Paired set: sentence indices present in both languages, minus any index with a
    recording longer than max_dur in either language (exclusion applies to both)."""
    data_dir = Path(data_dir)
    rows, wavs = {}, {}
    for lang, code in LANGS.items():
        rows[lang] = read_tsv(data_dir / "data" / code / "test.tsv")
        wavs[lang] = {p.name: str(p) for p in (data_dir / "data" / code / "audio" / "test").rglob("*.wav")}
        missing = [r["file"] for r in rows[lang] if r["file"] not in wavs[lang]]
        if missing:
            raise FileNotFoundError(f"{lang}: {len(missing)} wav files missing, e.g. {missing[:3]}")

    ids = {lang: {r["idx"] for r in rows[lang]} for lang in LANGS}
    common = ids["id"] & ids["en"]
    too_long = {r["idx"] for lang in LANGS for r in rows[lang]
                if r["idx"] in common and r["samples"] / SR > max_dur}
    numbers = {r["idx"] for lang in LANGS for r in rows[lang]
               if r["idx"] in common and has_number(r["ref"], lang)}
    paired_ids = sorted(common - too_long)

    def rec(lang, r):
        return {"lang": lang, "idx": r["idx"], "file": r["file"], "path": wavs[lang][r["file"]],
                "ref": r["ref"], "dur": r["samples"] / SR, "gender": r["gender"],
                "key": f"{lang}:{r['file']}"}

    paired = [rec(lang, r) for lang in LANGS for r in rows[lang] if r["idx"] in set(paired_ids)]
    full = [rec(lang, r) for lang in LANGS for r in rows[lang]]
    manifest = {
        "fleurs_revision": FLEURS_REVISION,
        "paired_ids": paired_ids,
        "excluded_too_long": sorted(too_long),
        "number_ids": sorted(numbers & set(paired_ids)),
        "paired": paired,
        "full": full,
    }
    save_json(manifest, data_dir / "manifest.json")
    return manifest


def load_manifest(data_dir):
    return load_json(Path(data_dir) / "manifest.json")


def load_audio(path):
    import soundfile as sf
    a, sr = sf.read(path, dtype="float32", always_2d=False)
    if a.ndim > 1:
        a = a.mean(axis=1)
    if sr != SR:
        raise ValueError(f"{path}: sample rate {sr}, expected {SR}")
    return np.ascontiguousarray(a, dtype=np.float32)


def speech_durations(manifest, out_path, vad_params):
    """Speech-only duration of every paired recording with Silero VAD (fixed parameters)."""
    import torch
    from silero_vad import get_speech_timestamps, load_silero_vad

    out_path = Path(out_path)
    done = load_json(out_path) if out_path.exists() else {}
    model = load_silero_vad()
    for r in manifest["paired"]:
        if r["key"] in done:
            continue
        wav = torch.from_numpy(load_audio(r["path"]))
        ts = get_speech_timestamps(wav, model, sampling_rate=SR, return_seconds=True, **vad_params)
        done[r["key"]] = float(sum(t["end"] - t["start"] for t in ts))
    save_json(done, out_path)
    return done


def data_statistics(manifest, speech):
    """The 'to measure' table: n, recordings, speakers by gender, durations, word statistics (M1)."""
    by_lang = defaultdict(list)
    for r in manifest["paired"]:
        by_lang[r["lang"]].append(r)
    stats = {"n_paired_indices": len(manifest["paired_ids"]),
             "excluded_too_long": manifest["excluded_too_long"],
             "n_number_indices": len(manifest["number_ids"])}
    for lang, recs in by_lang.items():
        dur = np.array([r["dur"] for r in recs])
        sp = np.array([speech.get(r["key"], np.nan) for r in recs])
        words = np.array([len(norm_basic(r["ref"]).split()) for r in recs])
        chars = np.array([len(norm_basic(r["ref"]).replace(" ", "")) for r in recs])
        per_idx = defaultdict(int)
        for r in recs:
            per_idx[r["idx"]] += 1
        vals, counts = np.unique(list(per_idx.values()), return_counts=True)
        stats[lang] = {
            "recordings": len(recs),
            "recordings_per_index": {str(int(v)): int(c) for v, c in zip(vals, counts)},
            "gender": {g: sum(r["gender"] == g for r in recs) for g in sorted({r["gender"] for r in recs})},
            "hours_total": float(dur.sum() / 3600),
            "hours_speech": float(np.nansum(sp) / 3600),
            "dur_median": float(np.median(dur)), "dur_p90": float(np.percentile(dur, 90)),
            "dur_max": float(dur.max()), "share_over_15s": float((dur > 15).mean()),
            "chars_per_word": float(chars.sum() / words.sum()),
            "sec_per_word_total": float(dur.sum() / words.sum()),
            "sec_per_word_speech": float(np.nansum(sp) / words.sum()),
            "chars_per_speech_sec": float(chars.sum() / np.nansum(sp)),
        }
    return stats


def index_features(manifest, speech):
    """Per sentence index and language: pooled speech seconds per word (M3 predictor)."""
    acc = defaultdict(lambda: [0.0, 0])
    for r in manifest["paired"]:
        k = (r["lang"], r["idx"])
        acc[k][0] += speech.get(r["key"], np.nan)
        acc[k][1] += len(norm_basic(r["ref"]).split())
    return {f"{l}:{i}": v[0] / v[1] for (l, i), v in acc.items() if v[1] > 0}
