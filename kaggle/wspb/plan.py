"""Job list in priority order (the runs the planned tests need come first).

Budget decision after the check run (22 Oct 2026): on a T4, large-v3 in fp32 runs slower than real
time at chunks <= 1.2 s, so the computation-aware (CA) simulation always lags and every job had to
be run twice. Main jobs therefore run computation-unaware (CU) only on all paired indices; CA
latency is measured on an evenly spaced subset of indices (`ca_ids`) at the H3 and Table 2 chunk
sizes. The anchor (real-time capable) keeps both modes. Beam-5 sensitivity runs at 1.0 s only.
"""


def ca_subset(paired_ids, n=40):
    """Evenly spaced subset of the paired sentence indices for the CA timing jobs."""
    ids = sorted(paired_ids)
    if len(ids) <= n:
        return ids
    step = len(ids) / n
    return [ids[int(i * step)] for i in range(n)]


def make_jobs(model="large-v3", v2_model="large-v2", chunks=(0.5, 1.0, 1.2, 1.5, 2.0),
              run_anchor=True, langs=("id", "en"), beam_chunks=(1.0,), ca_ids=None,
              ca_chunks=(1.0, 1.2)):
    def rd(lang, c):
        return {"id": f"redecode_{lang}_{c:g}", "kind": "redecode", "lang": lang, "chunk": c,
                "model": model, "set": "paired", "modes": ["cu"]}

    def aa(lang, c, trim):
        v = "aa_trim" if trim else "aa_keep"
        return {"id": f"{v}_{lang}_{c:g}", "kind": "aa", "lang": lang, "chunk": c, "model": model,
                "trim": trim, "policy_name": v, "set": "paired", "modes": ["cu"]}

    def off(lang, name, m, beam, s):
        return {"id": f"{name}_{lang}", "kind": "offline", "lang": lang, "model": m, "beam": beam,
                "policy_name": name, "set": s}

    def rd_beam(lang, c):
        # LocalAgreement (and hold-n) with beam 5 inside the harness: sensitivity check for the
        # greedy port (review R3). Policy names get the suffix "_beam5".
        return {"id": f"redecode_beam5_{lang}_{c:g}", "kind": "redecode", "lang": lang, "chunk": c,
                "model": model, "beam": 5, "policy_suffix": "_beam5", "set": "paired", "modes": ["cu"]}

    def ca_timing(job):
        # the same run, computation-aware only, on the CA subset; its rows are used for latency only
        return dict(job, id="catime_" + job["id"], modes=["ca"], ca_timing=True, ids=list(ca_ids))

    jobs = []
    tiers = [
        # tier 1: H3 (0.5, 1.0) and H4 (1.0 vs 2.0) for LocalAgreement and both AlignAtt variants
        [(c, k) for c in (1.0, 0.5, 2.0) for k in ("rd", "keep", "trim")],
        # tier 2: offline ceiling (M3 control) and setup check
        [("off", None)],
        # tier 2b: LocalAgreement beam-5 sensitivity (review R3)
        [(c, "beam") for c in (1.0, 0.5)],
        # tier 3: the shared 1.2 s chunk (RQ1, Table 2) and the 1.5 s curve point
        [(c, k) for c in (1.2, 1.5) for k in ("rd", "keep", "trim")],
    ]
    for tier in tiers:
        for c, k in tier:
            for lang in langs:
                if k is None:
                    jobs.append(off(lang, "offline_v3", model, False, "paired"))
                    jobs.append(off(lang, "offline_v2", v2_model, True, "full"))
                elif k == "beam":
                    if c in beam_chunks:
                        jobs.append(rd_beam(lang, c))
                elif c in chunks:
                    jobs.append(rd(lang, c) if k == "rd" else aa(lang, c, k == "trim"))
    # tier 4: computation-aware latency on the subset
    if ca_ids:
        jobs += [ca_timing(j) for j in list(jobs)
                 if j["kind"] in ("redecode", "aa") and "beam" not in j and j["chunk"] in ca_chunks]
    if run_anchor:
        for lang in langs:
            jobs.append({"id": f"ws_anchor_{lang}_1", "kind": "anchor", "lang": lang, "chunk": 1.0,
                         "model": model, "policy_name": "ws_anchor", "set": "paired",
                         "modes": ["ca", "cu"]})
    return jobs


# Seconds of T4 compute per second of audio, measured in the check run (22 Oct 2026; CA+CU where
# the job lagged). Only used to split the jobs into shards of similar length; relative values matter.
_SPEED = {
    ("redecode", 1): {0.5: 6.5, 1.0: 3.7, 1.2: 3.4, 1.5: 3.0, 2.0: 2.55},
    ("redecode", 5): {0.5: 9.5, 1.0: 5.2},
    ("aa_keep", 1): {0.5: 4.8, 1.0: 3.7, 1.2: 1.7, 1.5: 0.9, 2.0: 0.76},
    ("aa_trim", 1): {0.5: 3.55, 1.0: 2.45, 1.2: 2.2, 1.5: 1.3, 2.0: 0.8},
    ("anchor", 1): {1.0: 1.2},
}
_AUDIO_H = {"id": 2.31, "en": 1.64}          # paired audio per language
_N_PAIRED = 325


def job_cost(job):
    """Rough relative cost of a job (T4 hours), for balancing shards."""
    if job["kind"] == "offline":
        return _AUDIO_H[job["lang"]] * (0.36 if job.get("beam") else 0.17)
    key = (job.get("policy_name") if job["kind"] == "aa" else job["kind"], job.get("beam", 1))
    speeds = _SPEED.get(key, {})
    s = speeds.get(job.get("chunk"), max(speeds.values()) if speeds else 3.0)
    if job.get("modes") == ["cu"] or job.get("modes") == ["ca"]:
        s *= 0.5                                # one mode instead of CA + CU
    frac = len(job["ids"]) / _N_PAIRED if job.get("ids") is not None else 1.0
    return _AUDIO_H[job["lang"]] * s * frac


def shard_jobs(jobs, n_shards, index):
    """Split the jobs over n_shards accounts/machines: each job goes, in priority order, to the
    shard with the least work so far, so every shard starts with high-priority jobs and the
    shards take about the same time. Deterministic: every account computes the same split."""
    if n_shards <= 1:
        return list(jobs)
    load = [0.0] * n_shards
    mine = []
    for job in jobs:
        k = min(range(n_shards), key=lambda i: (load[i], i))
        load[k] += job_cost(job)
        if k == index:
            mine.append(job)
    return mine
