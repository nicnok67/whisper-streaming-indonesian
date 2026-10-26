import json
import os
import sys
import time
from pathlib import Path

SR = 16000

# Pinned versions of the code and data used by the benchmark.
SIMULSTREAMING_COMMIT = "077ea37d5ab4ff98bc567e4507f140dc4e5d5ad6"
WHISPER_STREAMING_COMMIT = "6da90b44b7e50d79695e68166d2a2c7609c75abb"
FLEURS_REVISION = "70bb2e84b976b7e960aa89f1c648e09c59f894dd"

# Short language code -> FLEURS config and Whisper language code.
LANGS = {"id": "id_id", "en": "en_us"}


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_jsonl(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                # a line cut off by a killed session; the recording is simply redone
                pass
    return out


def append_jsonl(obj, path):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def add_simulstreaming_to_path(cfg):
    p = str(Path(cfg["simulstreaming_dir"]).resolve())
    if p not in sys.path:
        sys.path.insert(0, p)


class Timer:
    """Wall-clock timer that waits for queued GPU work before reading the clock."""

    def __init__(self, cuda):
        self.cuda = cuda

    def _sync(self):
        if self.cuda:
            import torch
            torch.cuda.synchronize()

    def __enter__(self):
        self._sync()
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self._sync()
        self.elapsed = time.perf_counter() - self.t0
        return False


def log(msg, file=None):
    line = time.strftime("%H:%M:%S ") + str(msg)
    print(line, flush=True)
    if file:
        with open(file, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def env_info():
    """Hardware and software of the run (reported with the computation-aware latencies)."""
    import platform
    info = {"python": platform.python_version(), "platform": platform.platform()}
    try:
        import torch
        info["torch"] = torch.__version__
        info["cuda"] = torch.version.cuda
        info["gpus"] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
    except ImportError:
        pass
    from importlib.metadata import PackageNotFoundError, version
    for pkg in ("numpy", "pandas", "scipy", "faster-whisper", "ctranslate2", "silero-vad",
                "rapidfuzz", "librosa", "soundfile", "huggingface_hub"):
        try:
            info[pkg] = version(pkg)
        except PackageNotFoundError:
            info[pkg] = None
    info.update(simulstreaming_commit=SIMULSTREAMING_COMMIT,
                whisper_streaming_commit=WHISPER_STREAMING_COMMIT, fleurs_revision=FLEURS_REVISION)
    return info
