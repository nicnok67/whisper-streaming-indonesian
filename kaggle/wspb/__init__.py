"""Whisper streaming-policy benchmark (Indonesian vs English, FLEURS).

Modules
-------
common   paths, config and small I/O helpers
data     FLEURS download, paired manifest, audio loading, VAD statistics
text     Whisper text normalisers and number-word detection
align    word-level Levenshtein alignment
commit   commit rules of the re-decoding policies (hold-n, LocalAgreement-2)
engines  model wrappers: re-decoding Whisper, AlignAtt (SimulStreaming), offline, anchor
sim      streaming simulation (computation-unaware and computation-aware)
worker   job runner (one process per GPU, resumable)
metrics  per-recording metrics (WER, LAAL, erasure, tail confirmation, ...)
stats    planned tests (H1-H5, M1, M3, M4), matched-latency H3, and bootstrap
qa       QA before the main runs: the harness reproduces Whisper-Streaming and SimulStreaming
budget   GPU-time estimate for the full job list from a check run
report   tables, Figure 1 and a summary
"""
