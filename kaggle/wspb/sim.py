"""Streaming simulation of one recording.

Computation-unaware (CU), as SimulStreaming's --comp_unaware loop: audio is processed at
end = chunk, 2*chunk, ..., duration; a word committed at a step is emitted at `end`.

Computation-aware (CA), as the real-time loop of whisper_online_main.py, on a virtual clock
(no sleeping): a step starts at max(clock, previous end + chunk), takes all audio received by
then, and emits its words when its measured compute time has passed. When processing falls
behind, steps take longer pieces of audio, exactly as in a live run.

When no CA step started later than its schedule, the CA steps process the same audio pieces as
the CU steps, so the CU record is derived from the CA run (same outputs, emission at `end`)
instead of being decoded again.

Record layout (per mode): steps = [[end, emit, compute], ...]; per policy: per step
[committed_piece, displayed_tail] as raw text. Pieces are joined by plain concatenation (each
re-decoding word is written with its leading space), so the transcript is "".join(pieces).
The last step entry of every policy is the finish step.
"""
import math

from .commit import make_redecode_policies


def _text(words):
    return "".join(" " + w for _, _, w in words)
from .common import SR, Timer

EPS = 1e-9


def _schedule_step(mode, prev_end, clock, chunk, dur):
    if mode == "cu":
        end = min(prev_end + chunk, dur)
        return end, end
    start = max(clock, prev_end + chunk)
    return start, min(start, dur)


def _run_redecode(engine, audio, dur, chunk, mode, hold_n, cuda):
    pols = make_redecode_policies(hold_n)
    out = {p.name: [] for p in pols}
    steps, prev_end, clock, lag = [], 0.0, 0.0, False
    while True:
        start, end = _schedule_step(mode, prev_end, clock, chunk, dur)
        if mode == "ca" and start > prev_end + chunk + EPS:
            lag = True
        with Timer(cuda) as t:
            hyp = engine.decode(audio[: int(round(end * SR))])
        clock = start + t.elapsed
        steps.append([end, end if mode == "cu" else clock, t.elapsed])
        for p in pols:
            c, tail = p.step(hyp)
            out[p.name].append([_text(c), _text(tail)])
        prev_end = end
        if end >= dur - EPS:
            break
    # finish: the policies commit their remaining tail without another decode (as Whisper-Streaming)
    steps.append([dur, dur if mode == "cu" else clock, 0.0])
    for p in pols:
        out[p.name].append([_text(p.finish()), ""])
    return {"steps": steps, "policies": out, "lag": lag}


def _run_incremental(engine, audio, dur, chunk, mode, cuda, name):
    """AlignAtt (and the anchor): new audio pieces are inserted into the engine's own buffer."""
    engine.start()
    steps, recs, aux = [], [], []
    prev_end, clock, lag = 0.0, 0.0, False
    while True:
        start, end = _schedule_step(mode, prev_end, clock, chunk, dur)
        if mode == "ca" and start > prev_end + chunk + EPS:
            lag = True
        piece = audio[int(round(prev_end * SR)): int(round(end * SR))]
        with Timer(cuda) as t:
            text, tail, a = engine.step(piece)
        clock = start + t.elapsed
        steps.append([end, end if mode == "cu" else clock, t.elapsed])
        recs.append([text, tail])
        aux.append(a)
        prev_end = end
        if end >= dur - EPS:
            break
    with Timer(cuda) as t:
        text, tail, a = engine.finish()
    clock += t.elapsed
    steps.append([dur, dur if mode == "cu" else clock, t.elapsed])
    recs.append([text, tail])
    aux.append(a)
    return {"steps": steps, "policies": {name: recs}, "aux": aux, "lag": lag}


def simulate(kind, engine, audio, chunk, hold_n=2, policy_name=None, cuda=True, modes=("ca", "cu")):
    """modes=("ca", "cu"): run CA; run CU separately only if CA fell behind its schedule.
    modes=("cu",) or ("ca",): run only that mode; the other is None."""
    dur = len(audio) / SR
    run = (lambda mode: _run_redecode(engine, audio, dur, chunk, mode, hold_n, cuda)) \
        if kind == "redecode" else \
        (lambda mode: _run_incremental(engine, audio, dur, chunk, mode, cuda, policy_name))
    if "ca" not in modes:
        cu = run("cu")
        cu["derived"] = False
        cu["n_expected"] = int(math.ceil(dur / chunk - EPS)) + 1
        return {"dur": dur, "ca": None, "cu": cu}
    ca = run("ca")
    if "cu" not in modes:
        return {"dur": dur, "ca": ca, "cu": None}
    if ca["lag"]:
        cu = run("cu")
        cu["derived"] = False
    else:
        cu = {k: v for k, v in ca.items()}
        cu["steps"] = [[end, end if i < len(ca["steps"]) - 1 else dur, c]
                       for i, (end, _, c) in enumerate(ca["steps"])]
        cu["derived"] = True
    # number of CU steps expected without lag, for a consistency check
    cu["n_expected"] = int(math.ceil(dur / chunk - EPS)) + 1
    return {"dur": dur, "ca": ca, "cu": cu}
