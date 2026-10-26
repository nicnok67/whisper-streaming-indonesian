"""Job runner. Usage: python -m wspb.worker --config CONFIG --worker N

Each worker takes the next unfinished job in priority order (claimed with an exclusive lock
file), runs it one recording at a time, appends one JSON line per recording, and stops starting
new recordings after the session deadline. A job interrupted by the deadline continues in the
next session from its last saved recording.
"""
import argparse
import os
import time
import traceback
from pathlib import Path

from .common import add_simulstreaming_to_path, append_jsonl, load_config, log, read_jsonl


def job_paths(cfg, job_id):
    rd = Path(cfg["results_dir"])
    return rd / f"{job_id}.jsonl", rd / f"{job_id}.done"


def records_for(job, manifest, quick_ids):
    recs = manifest["full"] if job.get("set") == "full" else manifest["paired"]
    recs = [r for r in recs if r["lang"] == job["lang"]]
    if job.get("ids") is not None:          # CA timing subset
        keep = set(job["ids"])
        recs = [r for r in recs if r["idx"] in keep]
    if quick_ids is not None:
        recs = [r for r in recs if r["idx"] in quick_ids]
    return recs


def claim(cfg, job_id):
    d = Path(cfg["results_dir"]) / "claims"
    d.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(d / f"{job_id}.lock", os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return True
    except FileExistsError:
        return False


def build_engine(job, cfg):
    from . import engines
    lang = job["lang"]
    if job["kind"] == "redecode":
        return engines.RedecodeEngine(job["model"], lang, cfg["model_dir"], beam=job.get("beam", 1))
    if job["kind"] == "offline":
        return engines.RedecodeEngine(job["model"], lang, cfg["model_dir"])
    if job["kind"] == "aa":
        return engines.AlignAttEngine(job["model"], lang, cfg["model_dir"], job["chunk"],
                                      frame_threshold=cfg["frame_threshold"], trim=job["trim"])
    if job["kind"] == "anchor":
        return engines.AnchorEngine(lang, cfg["whisper_streaming_dir"], cache_dir=cfg["model_dir"])
    raise ValueError(job["kind"])


def run_job(job, cfg, manifest, deadline, logfile):
    import torch
    from .common import Timer
    from .data import load_audio
    from .sim import simulate

    cuda = torch.cuda.is_available()
    out, done = job_paths(cfg, job["id"])
    finished = {r["key"] for r in read_jsonl(out)}
    todo = [r for r in records_for(job, manifest, cfg.get("quick_ids")) if r["key"] not in finished]
    log(f"{job['id']}: {len(todo)} recordings to run ({len(finished)} already saved)", logfile)
    if not todo:
        done.touch()
        return True
    engine = build_engine(job, cfg)
    t_job = time.time()
    try:
        for i, r in enumerate(todo):
            if time.time() > deadline:
                log(f"{job['id']}: deadline reached after {i} recordings; resume next session", logfile)
                return False
            t_rec = time.time()
            audio = load_audio(r["path"])
            line = {"key": r["key"], "idx": r["idx"], "lang": r["lang"], "dur": len(audio) / 16000}
            if job["kind"] == "offline":
                with Timer(cuda) as t:
                    line["text"] = engine.offline_text(audio, beam=job.get("beam", False))
                line["compute"] = t.elapsed
            else:
                name = job.get("policy_name")
                res = simulate(job["kind"] if job["kind"] == "redecode" else "incremental",
                               engine, audio, job["chunk"], hold_n=cfg["hold_n"],
                               policy_name=name, cuda=cuda,
                               modes=tuple(job.get("modes", ("ca", "cu"))))
                line.update(res)
            line["wall"] = time.time() - t_rec
            append_jsonl(line, out)
            if (i + 1) % 25 == 0:
                rate = (time.time() - t_job) / (i + 1)
                log(f"{job['id']}: {i + 1}/{len(todo)}  ~{rate * (len(todo) - i - 1) / 3600:.2f} h left", logfile)
    finally:
        engine.close()
    done.touch()
    log(f"{job['id']}: done in {(time.time() - t_job) / 3600:.2f} h", logfile)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--worker", type=int, default=0)
    a = ap.parse_args()
    cfg = load_config(a.config)
    add_simulstreaming_to_path(cfg)
    from .data import load_manifest
    manifest = load_manifest(cfg["data_dir"])
    if cfg.get("quick_ids") is not None:
        cfg["quick_ids"] = set(cfg["quick_ids"])
    logfile = Path(cfg["results_dir"]) / "logs" / f"worker{a.worker}.log"
    logfile.parent.mkdir(parents=True, exist_ok=True)
    deadline = cfg["deadline_epoch"]
    log(f"worker {a.worker} started; GPU {os.environ.get('CUDA_VISIBLE_DEVICES')}", logfile)
    for job in cfg["jobs"]:
        if time.time() > deadline:
            break
        _, done = job_paths(cfg, job["id"])
        if done.exists() or not claim(cfg, job["id"]):
            continue
        try:
            run_job(job, cfg, manifest, deadline, logfile)
        except Exception:
            log(f"{job['id']}: FAILED\n{traceback.format_exc()}", logfile)
    log(f"worker {a.worker} finished", logfile)


if __name__ == "__main__":
    main()
