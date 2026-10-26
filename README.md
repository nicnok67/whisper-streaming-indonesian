# Whisper Streaming Policies for Indonesian

Code, run logs and per-recording results for the paper

> **Whisper Streaming Policies for Indonesian Live Captioning: A Comparative Study**
> Nicolas Wijaya and Amalia Zahra, BINUS Graduate Program – Master of Computer Science, Bina Nusantara University.
> (Manuscript under submission.)

The study compares five streaming policies for Whisper large-v3 on 325 FLEURS Indonesian test sentences, with the same sentences in English as a reference, at chunk sizes of 0.5, 1.0, 1.2, 1.5 and 2.0 s. The policies are:

| Policy | How it decides which words are final |
|---|---|
| Hold-0 | Commits every new word at once |
| Hold-2 | Holds back the last two words of each transcript |
| LocalAgreement-2 | Commits the words that two consecutive transcripts agree on (Whisper-Streaming) |
| AlignAtt-keep | Attention-guided stopping; keeps the last decoded word (SimulStreaming default) |
| AlignAtt-trim | The same, but always holds back the last decoded word (SimulStreaming `--never_fire`) |

Metrics: WER, computation-unaware LAAL (latency) and normalized erasure (stability).

## Main result (Indonesian)

LocalAgreement-2 (LA) vs. AlignAtt-trim (AA). *d* = WER of AA minus WER of LA, in points (negative favors AA); 95% CI from a paired bootstrap over sentences.

| Chunk (s) | WER LA / AA (%) | *d* | 95% CI | LAAL LA / AA (s) |
|---|---|---|---|---|
| 0.5 | 15.41 / 15.30 | −0.11 | [−2.24, 2.10] | 0.77 / 1.53 |
| 1.0 | 8.43 / 13.67 | 5.24 | [3.37, 7.24] | 1.87 / 1.73 |
| 1.2 | 7.95 / 8.93 | 0.98 | [0.35, 1.73] | 2.24 / 1.59 |
| 1.5 | 7.67 / 10.06 | 2.39 | [1.38, 3.49] | 2.80 / 1.78 |
| 2.0 | 7.63 / 8.44 | 0.81 | [0.26, 1.46] | 3.70 / 1.95 |

The two policies are level at 0.5 s. From 1.0 s on, LocalAgreement-2 is more accurate, while AlignAtt-trim commits words earlier and revises less displayed text. SimulStreaming's default (AlignAtt-keep) degenerated on 30% of Indonesian recordings at 0.5 s; holding the last word back prevents this. English results and all other numbers are in `results/report/`.

## Repository layout

```
kaggle/                      the benchmark, as run on Kaggle
  wspb/                      benchmark package (policies, simulation, metrics, statistics, report)
  build_notebook.py          builds the self-contained notebook from wspb/
  whisper_streaming_benchmark.ipynb   the notebook that was run (one %%writefile cell per module)
  tools/mde_simulation.py    power simulation used when planning the runs
analysis/                    local scoring and analysis
  merge_report.py            merges the two shards and rebuilds the report
  degen.py                   counts degenerate outputs (punctuation loops, missing half the words)
  within_lang.py             within-language policy comparisons used in the paper (writes within_lang.json)
  inputs/fleurs/             FLEURS test transcripts (en_us, id_id); no audio
  inputs/shim/               Whisper text normalizers, so scoring runs without installing openai-whisper
results/
  raw/results_shard_{0,1}.zip    raw Kaggle outputs: per-recording decoding records (.jsonl), logs, config
  report/                    merged report
    per_recording_metrics.csv    one row per recording, policy, chunk size
    merged_summary.csv           pooled WER, LAAL and erasure per policy, language, chunk size
    within_lang.json             numbers behind Table II and Section IV of the paper
    figure1_wer_laal.{pdf,png}   Fig. 1
```

`results/report/stats.json`, `summary.md` and `table1_h3.csv` also contain cross-language statistics from an earlier analysis plan. The paper does not use them; its numbers come from `within_lang.json` and `merged_summary.csv`.

## Setup used

- Model: Whisper large-v3, greedy decoding (temperature 0, no fallback), FP32, language fixed.
- Tools (pinned): openai-whisper 20250625, SimulStreaming commit `077ea37`, whisper_streaming commit `6da90b4`, faster-whisper 1.1.1, silero-vad 5.1.2.
- Data: FLEURS (`google/fleurs` on Hugging Face, revision `70bb2e8`), test splits `id_id` and `en_us`. Audio is downloaded by the notebook and is not stored here.
- Hardware: NVIDIA T4 GPUs on Kaggle; the jobs were split across two accounts (shards 0 and 1).

## Reproducing

**Re-running the benchmark (GPU).** Upload `kaggle/whisper_streaming_benchmark.ipynb` to Kaggle with a T4 GPU and Internet on, then follow the instructions in its first cell (`N_SHARDS` / `SHARD_INDEX` split the jobs across accounts). If you edit `kaggle/wspb/`, rebuild the notebook with `python kaggle/build_notebook.py`.

**Re-scoring from the stored results (CPU only).** Requires Python 3.10+, numpy, pandas, scipy, regex, more-itertools and matplotlib.

1. Make a work folder and unzip `results/raw/results_shard_0.zip` into `<work>/s0/` and `results_shard_1.zip` into `<work>/s1/`.
2. Copy `analysis/inputs/fleurs` and `analysis/inputs/shim` into `<work>/`.
3. Copy both shards' `results/*.jsonl` and `results/*.done` into `<work>/merged/results/`.
4. Run `python -I analysis/merge_report.py kaggle <work>` to rebuild the merged report in `<work>/merged/report/`.
5. For the within-language comparisons, also unzip shard 0's inner `wspb_run_shard0_all_*.zip` into `<work>/in0/`, then run `python -I analysis/within_lang.py <work>`.

## Licenses

- Code in this repository: MIT License (see `LICENSE`).
- Results in `results/`: CC BY 4.0.
- FLEURS transcripts in `analysis/inputs/fleurs/`: from FLEURS (Conneau et al., 2023), CC BY 4.0.
- Whisper text normalizers in `analysis/inputs/shim/`: from openai-whisper, MIT License (see `THIRD_PARTY_NOTICES.md`).

## Citation

If you use this code or these results, please cite the paper (citation details will be added after publication).
