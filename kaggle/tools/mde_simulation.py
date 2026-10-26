"""Pre-run precision estimate for H3: Delta = R_ID - R_EN, R = (WER_LA - WER_AA) / WER_LA.
Paired bootstrap over sentence indices (errors and words pooled over recordings).
All rates and noise levels are ASSUMPTIONS, not data. Fixed seed for reproducibility."""
import numpy as np

SEED = 20261022
B = 2000          # bootstrap resamples per simulated data set (10,000 in the real analysis)
REPS = 20         # simulated data sets per scenario
Z = 2.241 + 0.842 # z(1 - 0.025/2) + z(0.80): 80% power at Holm's stricter level

def one_dataset(rng, n, recs, w_en=21, w_id=19, la_en=.08, aa_en=.05, la_id=.14, aa_id=.09,
                k=1.0, shared_lang=0.5, policy_noise=0.35):
    g = lambda size: rng.gamma(k, 1 / k, size)
    z = g(n)                                          # content difficulty, shared by both languages
    out = {}
    for lang, w, la, aa in (("en", w_en, la_en, aa_en), ("id", w_id, la_id, aa_id)):
        d_sent = shared_lang * z + (1 - shared_lang) * g(n)
        W = np.zeros(n); E_la = np.zeros(n); E_aa = np.zeros(n)
        r = rng.choice(recs, size=n)                  # recordings per sentence index
        for j in range(max(recs)):
            m = r > j
            d = 0.7 * d_sent + 0.3 * g(n)             # recording (speaker) variation
            words = rng.poisson(w, n) + 3
            for E, rate in ((E_la, la), (E_aa, aa)):
                e = (1 - policy_noise) * d + policy_noise * g(n)
                E += m * rng.poisson(words * rate * e)
            W += m * words
        out[lang] = (W, E_la, E_aa)
    return out

def delta_se(rng, data, n):
    idx = rng.integers(0, n, (B, n))
    def R(lang):
        W, L, A = data[lang]; Ls = L[idx].sum(1); As = A[idx].sum(1); return (Ls - As) / Ls
    D = R("id") - R("en")
    return np.percentile(D, 97.5) - np.percentile(D, 2.5), D.std()

scenarios = {
    "n=350, 1 recording each":            dict(n=350, recs=[1]),
    "n=350, 1-3 recordings (mean 2)":     dict(n=350, recs=[1, 2, 3]),
    "n=250, 1-3 recordings (mean 2)":     dict(n=250, recs=[1, 2, 3]),
    "n=350, mean 2, low WER":             dict(n=350, recs=[1, 2, 3], la_en=.06, aa_en=.04, la_id=.10, aa_id=.065),
    "n=350, mean 2, more overdispersion": dict(n=350, recs=[1, 2, 3], k=0.5),
}
rng = np.random.default_rng(SEED)
print(f"{'scenario':38s} CI width   MDE (80%, a=.025)")
for name, kw in scenarios.items():
    n = kw["n"]; res = [delta_se(rng, one_dataset(rng, **kw), n) for _ in range(REPS)]
    w, se = np.mean(res, axis=0)
    print(f"{name:38s} {100*w:5.1f} pts  {100*Z*se:5.1f} pts")
