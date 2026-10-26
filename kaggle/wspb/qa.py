"""QA before the main runs (planned): the harness reproduces the released tools.

qa_localagreement  The LocalAgreement-2 port commits exactly what Whisper-Streaming's own
                   HypothesisBuffer (commit 6da90b4) commits when both receive the same decodes.
qa_alignatt        The AlignAtt engine wrapper outputs exactly what SimulStreaming's own command
                   line (commit 077ea37, --comp_unaware) outputs for the same file and settings.
"""
import json
import os
import subprocess
import sys

import numpy as np

from .commit import LocalAgreement
from .common import SR


def _hypothesis_buffer(ws_dir):
    if ws_dir not in sys.path:
        sys.path.insert(0, ws_dir)
    from whisper_online import HypothesisBuffer
    return HypothesisBuffer(logfile=open(os.devnull, "w"))


def qa_localagreement(engine, audio, chunk, ws_dir):
    """Same decodes into both implementations; returns (passed, n_steps, first difference)."""
    ours, ref = LocalAgreement(), _hypothesis_buffer(ws_dir)
    dur = len(audio) / SR
    end, k = 0.0, 0
    while True:
        end = min(end + chunk, dur)
        hyp = engine.decode(audio[: int(round(end * SR))])
        c_ours, _ = ours.step(hyp)
        ref.insert(hyp, 0.0)
        c_ref = ref.flush()
        if [tuple(w) for w in c_ours] != [tuple(w) for w in c_ref]:
            return False, k, {"step": k, "end": end, "ours": c_ours, "whisper_streaming": c_ref}
        k += 1
        if end >= dur - 1e-9:
            break
    # finish: Whisper-Streaming commits the remaining buffer (OnlineASRProcessor.finish -> complete())
    if [tuple(w) for w in ours.finish()] != [tuple(w) for w in ref.buffer]:
        return False, k, {"step": "finish"}
    return True, k, None


def qa_alignatt(engine_factory, wav_path, audio, lang, chunk, trim, ss_dir, model_path):
    """Run SimulStreaming's CLI on the file and compare its emitted text with the wrapper's
    committed pieces, including the final finish() call that the CLI makes after its loop."""
    cmd = [sys.executable, "simulstreaming_whisper.py", wav_path, "--comp_unaware",
           "--lan", lang, "--model_path", model_path, "--min-chunk-size", str(chunk),
           "--frame_threshold", "25", "-l", "WARNING"]
    if trim:
        cmd.append("--never_fire")
    p = subprocess.run(cmd, cwd=ss_dir, capture_output=True, text=True)
    if p.returncode != 0:
        return False, {"error": p.stderr[-2000:]}
    cli = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            cli.append(json.loads(line).get("text", ""))
    eng = engine_factory()
    try:
        eng.start()
        pieces, prev_end, dur = [], 0.0, len(audio) / SR
        # the CLI's own loop: beg = previous end, end += chunk, slices with int(t * 16000)
        end = chunk
        while True:
            text, _, _ = eng.step(audio[int(prev_end * SR): int(end * SR)])
            pieces.append(text)
            if end >= dur:
                break
            prev_end = end
            end = dur if end + chunk > dur else end + chunk
        text, _, _ = eng.finish()
        pieces.append(text)
    finally:
        eng.close()
    a, b = "".join(cli), "".join(pieces)
    return a == b, {"cli": a, "wrapper": b}


def run_all(cfg, manifest, n_per_lang=2, chunk=1.0):
    from . import engines
    from .data import load_audio

    ws_dir, ss_dir = cfg["whisper_streaming_dir"], cfg["simulstreaming_dir"]
    model = cfg.get("model", "large-v3")
    model_path = os.path.join(cfg["model_dir"], model + ".pt")
    report = {"localagreement": [], "alignatt": []}
    for lang in ("en", "id"):
        recs = [r for r in manifest["paired"] if r["lang"] == lang][:n_per_lang]
        eng = engines.RedecodeEngine(model, lang, cfg["model_dir"])
        try:
            for r in recs:
                ok, n, diff = qa_localagreement(eng, load_audio(r["path"]), chunk, ws_dir)
                report["localagreement"].append({"key": r["key"], "passed": ok, "steps": n, "diff": diff})
        finally:
            eng.close()
        for r in recs[:1]:
            for trim in (False, True):
                ok, detail = qa_alignatt(
                    lambda: engines.AlignAttEngine(model, lang, cfg["model_dir"], chunk,
                                                   frame_threshold=cfg["frame_threshold"], trim=trim),
                    r["path"], load_audio(r["path"]), lang, chunk, trim, ss_dir, model_path)
                report["alignatt"].append({"key": r["key"], "trim": trim, "passed": ok, **detail})
    report["passed"] = all(x["passed"] for v in ("localagreement", "alignatt") for x in report[v])
    return report
