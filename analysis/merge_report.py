import sys, json, csv, warnings
from pathlib import Path
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2] + "/shim")
warnings.simplefilter("ignore", RuntimeWarning)
from wspb import data, plan, report, common
S = Path(sys.argv[2])
# manifest from the transcripts only: audio is not needed for scoring, so file paths are placeholders
data.Path  # noqa
orig_rglob = Path.rglob
def fake_wavs(lang_dir):
    pass
LANGS = common.LANGS
rows = {l: data.read_tsv(S / "fleurs" / "data" / c / "test.tsv") for l, c in LANGS.items()}
class P(str):
    @property
    def name(self): return self
def rglob(self, pat):
    for l, c in LANGS.items():
        if str(self).replace("\\", "/").endswith(f"{c}/audio/test"):
            return [P(r["file"]) for r in rows[l]]
    return orig_rglob(self, pat)
Path.rglob = rglob
manifest = data.build_manifest(S / "fleurs")
Path.rglob = orig_rglob
speech = common.load_json(S / "s0" / "state" / "speech_durations.json")
ca_ids = plan.ca_subset(manifest["paired_ids"], n=40)
jobs = plan.make_jobs(model="large-v3", ca_ids=ca_ids)
cfg = dict(results_dir=str(S / "merged" / "results"), jobs=jobs, quick_ids=None, primary_aa="aa_trim",
           bootstrap_B=10000, seed=20261022, equivalence_margin=0.42, model="large-v3", hold_n=2)
for j in jobs:
    n = len(common.read_jsonl(f"{cfg['results_dir']}/{j['id']}.jsonl"))
    done = (Path(cfg["results_dir"]) / f"{j['id']}.done").exists()
    if not done: print("NOT DONE:", j["id"], n)
print("paired ids", len(manifest["paired_ids"]))
report.run(cfg, manifest, speech, S / "merged" / "report")
