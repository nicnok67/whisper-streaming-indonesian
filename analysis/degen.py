import json, re, sys, glob, collections
import pandas as pd
S = sys.argv[1]
pr = pd.read_csv(f"{S}/merged/report/per_recording_metrics.csv")
pr = pr[(pr["mode"] == "cu") & pr.policy.isin(["aa_keep", "aa_trim"]) & ~pr.job.str.startswith("catime")]
texts = {}
for pol in ("aa_keep", "aa_trim"):
    for f in glob.glob(f"{S}/merged/results/{pol}_*.jsonl"):
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            if not r.get("cu"): continue
            t = "".join(p[0] for p in r["cu"]["policies"][pol])
            ch = float(f.rsplit("_", 1)[1][:-6])
            texts[(pol, r["lang"], ch, r["key"])] = t
loop = re.compile(r"(?:\s*[.,!?。]\s*){4,}")
rows = []
for _, r in pr.iterrows():
    t = texts.get((r.policy, r.lang, r.chunk, r.key), "")
    has_loop = bool(loop.search(t))
    trunc = r.D / r.N >= 0.5
    rows.append((r.policy, r.lang, r.chunk, has_loop, trunc, has_loop or trunc))
d = pd.DataFrame(rows, columns=["policy", "lang", "chunk", "punct_loop", "del50", "degenerate"])
g = d.groupby(["policy", "lang", "chunk"]).agg(n=("degenerate", "size"), punct_loop=("punct_loop", "mean"),
      del50=("del50", "mean"), degenerate=("degenerate", "mean")).reset_index()
print((g.assign(**{c: (g[c]*100).round(1) for c in ["punct_loop", "del50", "degenerate"]})).to_string(index=False))
# one example
for k, t in texts.items():
    if k[0] == "aa_keep" and k[2] == 0.5 and k[1] == "en" and loop.search(t):
        print("EXAMPLE", k, repr(t[:250])); break
