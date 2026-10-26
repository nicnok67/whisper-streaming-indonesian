"""Build the self-contained Kaggle notebook from the wspb package.

Usage: python build_notebook.py   (writes whisper_streaming_benchmark.ipynb next to this file)
Every module of wspb/ becomes one %%writefile cell, so the notebook is the only file to upload.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULES = ["__init__", "common", "text", "align", "data", "commit", "engines", "sim", "worker",
           "metrics", "stats", "qa", "budget", "plan", "report"]


def md(src):
    return {"cell_type": "markdown", "metadata": {}, "source": src.strip("\n").splitlines(True)}


def code(src):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": src.strip("\n").splitlines(True)}


INTRO = r"""
# Whisper streaming policies: Indonesian vs English (FLEURS)

Benchmark with the analysis fixed before the runs (Chapter Plan + review round 1 fixes R1, R2, R3, R5).

**Kaggle settings (right-hand panel):** Accelerator **GPU T4 x2**, Internet **On**, Persistence: none needed.

**How to run**
1. (Done on 22 Oct 2026.) Check session: set `MODE = "check"` and use **Save Version → Save & Run All (Commit)**.
   It installs everything, runs the unit tests, the QA checks (harness = released tools),
   every job on 2 sentence indices, the full analysis on that mini set, and prints
   the GPU-hour estimate for the full plan. Send all the output back.
2. Main runs: `MODE = "run"` (the default) and commit. Each session runs jobs in priority order until
   `SESSION_HOURS`, saves every finished recording, and writes the report on whatever is done.
3. To continue in a new session: **Add Input → Notebook Output → this notebook's previous
   version**, then commit again. Finished recordings are restored and skipped.

**Two accounts (you and a second person, each on their own account):** set `N_SHARDS = 2` and
`SHARD_INDEX = 0` on one account, `SHARD_INDEX = 1` on the other. Each runs its own half of the jobs
(the split is computed the same way on both). When both halves are done, the second person downloads
the zip from the last cell and gives it to you; upload it as a private Kaggle **Dataset**, add it
(and your own previous output) as input, and commit once more: the report then covers all jobs.

All outputs go to `/kaggle/working` (results, logs, report, figure). Data and models live in
`/tmp` and are downloaded again each session.
"""

CONFIG = r"""
import os, sys, time
T0 = time.time()

MODE = "run"              # "run" (main runs; the check run was done on 22 Oct 2026) or "check"
SESSION_HOURS = 11.0      # stop starting new recordings after this (Kaggle limit is 12 h)
REPORT_RESERVE_MIN = 25   # time kept for the final report
CHECK_N_INDICES = 2       # sentence indices per job in check mode

N_SHARDS = 2              # number of accounts running the jobs (1 = this account runs everything)
SHARD_INDEX = 0           # 0 = first account, 1 = second account (must differ between accounts)

MODEL = "large-v3"
PRIMARY_AA = "aa_trim"    # always holds the last word back (--never_fire); the as-released default
                          # (aa_keep) degenerated into "." loops at 0.5/1.0 s in the check run and is
                          # reported as "SimulStreaming as released"
HOLD_N = 2
FRAME_THRESHOLD = 25
EQUIVALENCE_MARGIN = 0.42 # fixed before the runs: +/-42 points of relative advantage (review R2)
BOOTSTRAP_B = 10000
SEED = 20261022
VAD_PARAMS = dict(threshold=0.5, min_silence_duration_ms=500, speech_pad_ms=100)

OUT = "/kaggle/working"
WORK = "/tmp/wspb_work"
SS_DIR = f"{WORK}/SimulStreaming"
WS_DIR = f"{WORK}/whisper_streaming"
DATA_DIR = f"{WORK}/fleurs"
MODEL_DIR = f"{WORK}/models"
STATE = f"{OUT}/state"
RESULTS = f"{OUT}/results" if MODE == "run" else f"{OUT}/check_results"
REPORT = f"{OUT}/report" if MODE == "run" else f"{OUT}/check_report"
for d in (WORK, MODEL_DIR, STATE, RESULTS, REPORT, f"{OUT}/wspb"):
    os.makedirs(d, exist_ok=True)
print("MODE:", MODE)
"""

INSTALL = r"""
import subprocess

def sh(cmd, check=True):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and r.returncode:
        print(r.stdout[-3000:]); print(r.stderr[-3000:])
        raise RuntimeError(f"failed: {cmd}")
    return r.stdout

sh("pip install -q openai-whisper==20250625 silero-vad==5.1.2 faster-whisper==1.1.1 rapidfuzz tabulate")
if not os.path.exists(SS_DIR):
    sh(f"git clone -q https://github.com/ufal/SimulStreaming {SS_DIR}")
sh(f"git -C {SS_DIR} checkout -q 077ea37d5ab4ff98bc567e4507f140dc4e5d5ad6")
if not os.path.exists(WS_DIR):
    sh(f"git clone -q https://github.com/ufal/whisper_streaming {WS_DIR}")
sh(f"git -C {WS_DIR} checkout -q 6da90b44b7e50d79695e68166d2a2c7609c75abb")
print(sh(f"git -C {SS_DIR} log -1 --format='SimulStreaming %H'"), end="")
print(sh(f"git -C {WS_DIR} log -1 --format='whisper_streaming %H'"), end="")

# cuDNN 9 from the pip wheel, for faster-whisper (anchor runs) in the worker processes
import glob, site
CUDNN = [p for sp in site.getsitepackages() for p in glob.glob(f"{sp}/nvidia/cudnn/lib")]
print("cuDNN lib:", CUDNN)
"""

SETUP = r"""
import glob, json, shutil, importlib
for p in (OUT, SS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)
import wspb
from wspb import common, text, align, data, commit, plan, report, qa, budget, stats
for m in (common, text, align, data, commit, plan, report, qa, budget, stats):
    importlib.reload(m)

assert commit.self_test() and text.self_test()
print("unit tests passed")

ENV = common.env_info()
common.save_json(ENV, f"{STATE}/environment_{MODE}.json")
print(json.dumps(ENV, indent=1))

import torch
N_GPUS = max(1, torch.cuda.device_count())
print("GPUs:", N_GPUS)

# Restore finished work from previous versions attached as input (Add Input -> Notebook Output)
restored = 0
if MODE == "run":
    for src in glob.glob("/kaggle/input/**/results/*.jsonl", recursive=True):
        dst = os.path.join(RESULTS, os.path.basename(src))
        n_src = sum(1 for _ in open(src, encoding="utf-8"))
        n_dst = sum(1 for _ in open(dst, encoding="utf-8")) if os.path.exists(dst) else -1
        if n_src > n_dst:
            shutil.copy(src, dst); restored += 1
    for src in glob.glob("/kaggle/input/**/results/*.done", recursive=True):
        shutil.copy(src, os.path.join(RESULTS, os.path.basename(src)))
for src in glob.glob("/kaggle/input/**/state/*.json", recursive=True):
    dst = os.path.join(STATE, os.path.basename(src))
    if not os.path.exists(dst):
        shutil.copy(src, dst)
shutil.rmtree(f"{RESULTS}/claims", ignore_errors=True)   # locks of a previous session
print("restored result files:", restored)
"""

DATA = r"""
t = time.time()
data.fetch_fleurs(DATA_DIR)
manifest = data.build_manifest(DATA_DIR)
print("paired indices:", len(manifest["paired_ids"]), "| excluded (>30 s):", manifest["excluded_too_long"],
      "| indices with numbers:", len(manifest["number_ids"]))

speech_path = f"{STATE}/speech_durations.json"
speech = data.speech_durations(manifest, speech_path, VAD_PARAMS)
stats_data = data.data_statistics(manifest, speech)
common.save_json(stats_data, f"{STATE}/data_statistics.json")
print(json.dumps(stats_data, indent=1))
print(f"data ready in {(time.time() - t) / 60:.1f} min")
"""

MODELS = r"""
import whisper as openai_whisper
t = time.time()
for name in (MODEL, "large-v2"):
    path = os.path.join(MODEL_DIR, name + ".pt")
    if not os.path.exists(path):
        openai_whisper._download(openai_whisper._MODELS[name], MODEL_DIR, in_memory=False)
    print(name, os.path.getsize(path) // 2**20, "MB")
print(f"models ready in {(time.time() - t) / 60:.1f} min")
"""

QA = r"""
# QA before the main runs (planned): the harness reproduces the released tools.
BASE_CFG = dict(simulstreaming_dir=SS_DIR, whisper_streaming_dir=WS_DIR, data_dir=DATA_DIR,
                model_dir=MODEL_DIR, model=MODEL, frame_threshold=FRAME_THRESHOLD, hold_n=HOLD_N,
                primary_aa=PRIMARY_AA, bootstrap_B=BOOTSTRAP_B, seed=SEED,
                equivalence_margin=EQUIVALENCE_MARGIN)
qa_path = f"{STATE}/qa.json"
if os.path.exists(qa_path):
    QA_RES = common.load_json(qa_path)
    print("QA already done in an earlier session")
else:
    t = time.time()
    QA_RES = qa.run_all(BASE_CFG, manifest)
    common.save_json(QA_RES, qa_path)
    print(f"QA took {(time.time() - t) / 60:.1f} min")
for kind in ("localagreement", "alignatt"):
    for r in QA_RES[kind]:
        extra = "" if r["passed"] else " <-- MISMATCH: " + json.dumps(
            {k: v for k, v in r.items() if k not in ("passed",)}, ensure_ascii=False)[:1500]
        print(f"QA {kind:15s} {r['key']:40s} trim={r.get('trim', '-')!s:5s} passed={r['passed']}{extra}")
print("QA PASSED" if QA_RES["passed"] else "QA FAILED (see mismatches above)")
"""

RUN = r"""
CA_IDS = plan.ca_subset(manifest["paired_ids"], n=40)   # CA timing subset (budget decision)
ALL_JOBS = plan.make_jobs(model=MODEL, ca_ids=CA_IDS)
JOBS = plan.shard_jobs(ALL_JOBS, N_SHARDS, SHARD_INDEX) if MODE == "run" else ALL_JOBS
print(f"shard {SHARD_INDEX + 1} of {N_SHARDS}: {len(JOBS)} of {len(ALL_JOBS)} jobs, "
      f"~{sum(plan.job_cost(j) for j in JOBS):.0f} T4 GPU-hours (rough)")
quick = manifest["paired_ids"][:CHECK_N_INDICES] if MODE == "check" else None
deadline = T0 + SESSION_HOURS * 3600 - REPORT_RESERVE_MIN * 60
cfg = dict(BASE_CFG, results_dir=RESULTS, jobs=JOBS, quick_ids=quick, deadline_epoch=deadline)
cfg_path = f"{RESULTS}/config.json"
common.save_json(cfg, cfg_path)
cfg_report = dict(cfg, jobs=ALL_JOBS)      # the report always covers every job that has results
os.makedirs(f"{RESULTS}/logs", exist_ok=True)
print(f"{len(JOBS)} jobs; {N_GPUS} worker(s); deadline in {(deadline - time.time()) / 3600:.2f} h")

env = dict(os.environ, PYTHONPATH=os.pathsep.join([OUT, SS_DIR]), PYTHONUNBUFFERED="1",
           LD_LIBRARY_PATH=os.pathsep.join(CUDNN + [os.environ.get("LD_LIBRARY_PATH", "")]))
procs = []
for g in range(N_GPUS):
    out_f = open(f"{RESULTS}/logs/worker{g}.stdout", "a")
    procs.append(subprocess.Popen([sys.executable, "-m", "wspb.worker", "--config", cfg_path,
                                   "--worker", str(g)], env=dict(env, CUDA_VISIBLE_DEVICES=str(g)),
                                  stdout=out_f, stderr=subprocess.STDOUT))
seen = {}
def show_new_log_lines():
    for g in range(N_GPUS):
        f = f"{RESULTS}/logs/worker{g}.log"
        if not os.path.exists(f):
            continue
        lines = open(f, encoding="utf-8").read().splitlines()
        for line in lines[seen.get(f, 0):]:
            print(f"[gpu{g}] {line}")
        seen[f] = len(lines)
while any(p.poll() is None for p in procs):
    time.sleep(60)
    show_new_log_lines()
show_new_log_lines()
print("worker exit codes:", [p.returncode for p in procs])
for g in range(N_GPUS):
    so = open(f"{RESULTS}/logs/worker{g}.stdout", encoding="utf-8", errors="replace").read()
    if "Traceback" in so:
        print(f"--- worker{g}.stdout (tail) ---"); print(so[-4000:])
"""

STATUS = r"""
# Job status of ALL jobs: done / partial / not started, and which shard runs each job
from wspb.worker import records_for
mine_ids = {j["id"] for j in JOBS}
rows = []
for job in ALL_JOBS:
    n_have = len(common.read_jsonl(f"{RESULTS}/{job['id']}.jsonl"))
    n_need = len(records_for(job, manifest, set(quick) if quick else None))
    rows.append((job["id"], "this account" if job["id"] in mine_ids else "other account", n_have, n_need,
                 "done" if os.path.exists(f"{RESULTS}/{job['id']}.done") else ("partial" if n_have else "not started")))
import pandas as pd
st = pd.DataFrame(rows, columns=["job", "run_by", "recordings_saved", "recordings_needed", "status"])
print(st.to_string(index=False))
print("this account:", st[st.run_by == "this account"].status.value_counts().to_dict())
print("all jobs:    ", st.status.value_counts().to_dict())
if (st.status != "done").any():
    print("NOTE: the report below covers only the jobs with results so far.")
"""

REPORT_CELL = r"""
import warnings
warnings.simplefilter("ignore", RuntimeWarning)
t = time.time()
rep = report.run(cfg_report, manifest, speech, REPORT)
if rep is not None:
    res, table = rep
    print(open(f"{REPORT}/summary.md", encoding="utf-8").read()[:12000])
print(f"report in {(time.time() - t) / 60:.1f} min; files:", sorted(os.listdir(REPORT)))
"""

BUDGET = r"""
# GPU-time estimate for the full plan (check mode only)
if MODE == "check":
    full_jobs = plan.make_jobs(model=MODEL, ca_ids=CA_IDS)
    bt, tot = budget.estimate(RESULTS, JOBS, full_jobs, manifest, n_gpus=N_GPUS)
    bt.to_csv(f"{REPORT}/gpu_budget.csv", index=False)
    print(bt.round(3).to_string(index=False))
    print(json.dumps(tot, indent=1))
    print(f"Kaggle sessions of {SESSION_HOURS} h needed (approx.): "
          f"{tot['wall_hours_with_gpus'] / SESSION_HOURS:.1f}")
"""

FINAL = r"""
shutil.make_archive(f"{OUT}/outputs_{MODE}", "zip", OUT, os.path.basename(REPORT))
print(f"total session time {(time.time() - T0) / 3600:.2f} h")
"""


ZIP_ALL = r"""
# Zip all outputs of this run and show a download link (also in the Output tab after a commit)
from IPython.display import FileLink, display
stamp = time.strftime("%Y%m%d_%H%M")
zip_base = f"{OUT}/wspb_{MODE}_shard{SHARD_INDEX}_all_{stamp}"
tmp = f"/tmp/wspb_export_{stamp}"
shutil.rmtree(tmp, ignore_errors=True)
os.makedirs(tmp)
for name in sorted(os.listdir(OUT)):
    src = os.path.join(OUT, name)
    if name.endswith(".zip") or name.startswith("."):
        continue
    (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, os.path.join(tmp, name))
zip_path = shutil.make_archive(zip_base, "zip", tmp)
shutil.rmtree(tmp, ignore_errors=True)
print("Created:", zip_path, f"({os.path.getsize(zip_path) / 2**20:.1f} MB)")
os.chdir(OUT)
display(FileLink(os.path.basename(zip_path)))
"""


def main():
    cells = [md(INTRO), code(CONFIG), md("## Install and pinned code"), code(INSTALL),
             md("## The `wspb` package (one cell per module)")]
    cells.append(code('os.makedirs("/kaggle/working/wspb", exist_ok=True)'))
    for m in MODULES:
        src = (HERE / "wspb" / f"{m}.py").read_text(encoding="utf-8")
        cells.append(code(f"%%writefile /kaggle/working/wspb/{m}.py\n" + src))
    cells += [md("## Setup, unit tests, restore"), code(SETUP),
              md("## Data: FLEURS test sets, paired manifest, VAD"), code(DATA),
              md("## Models"), code(MODELS),
              md("## QA: harness vs released tools"), code(QA),
              md("## Runs"), code(RUN), code(STATUS),
              md("## Report"), code(REPORT_CELL), code(BUDGET), code(FINAL),
              md("## Download everything (results, logs, report, state, code)"), code(ZIP_ALL)]
    nb = {"cells": cells, "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
        "kaggle": {"accelerator": "nvidiaTeslaT4", "isInternetEnabled": True, "isGpuEnabled": True}},
        "nbformat": 4, "nbformat_minor": 4}
    out = HERE / "whisper_streaming_benchmark.ipynb"
    out.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
