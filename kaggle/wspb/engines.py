"""Model wrappers. All harness engines load the same large-v3 checkpoint file, in fp32 as
SimulStreaming ships, with greedy decoding and a fixed language. AlignAtt runs through
SimulStreaming's own code; the re-decoding policies and the offline runs use the openai-whisper
package (SimulStreaming's bundled transcribe() predates large-v3: it always computes 80 mel bands,
while large-v3 needs 128)."""
import os

import numpy as np

from .common import SR


def _cuda():
    import torch
    return torch.cuda.is_available()


class RedecodeEngine:
    """Re-decodes the whole buffer from its start with an empty prompt and returns word timestamps
    (the input of hold-0, hold-n and LocalAgreement-2). Mirrors Whisper-Streaming's
    whisper_timestamped backend: greedy (beam 5 for the sensitivity runs), no temperature fallback, word timestamps,
    condition_on_previous_text=True (it only acts across 30 s windows, which never occur here)."""

    def __init__(self, model_name, lang, model_dir, beam=1):
        from whisper import load_model
        from whisper.transcribe import transcribe
        self.model = load_model(model_name, download_root=model_dir)
        self.transcribe = transcribe
        self.lang = lang
        # beam > 1: beam search with a single temperature (no fallback), so every step is still one
        # decode; used only for the LocalAgreement sensitivity runs (review R3)
        self.beam = beam
        self.decode(np.zeros(SR, dtype=np.float32))  # warm-up

    def decode(self, audio):
        kw = dict(beam_size=self.beam) if self.beam > 1 else {}
        r = self.transcribe(self.model, audio, language=self.lang, task="transcribe",
                            temperature=0.0, word_timestamps=True, condition_on_previous_text=True,
                            initial_prompt=None, fp16=False, verbose=None, **kw)
        words = []
        for seg in r["segments"]:
            for w in seg.get("words", []):
                t = w["word"].strip()
                if t:
                    words.append((float(w["start"]), float(w["end"]), t))
        return words

    def offline_text(self, audio, beam=False):
        kw = dict(language=self.lang, task="transcribe", fp16=False, verbose=None,
                  condition_on_previous_text=True)
        if beam:
            # Decoding of OpenAI's FLEURS notebook (beam 5, best_of 5, temperature fallback)
            kw.update(beam_size=5, best_of=5, temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0))
        else:
            kw.update(temperature=0.0)
        return self.transcribe(self.model, audio, **kw)["text"]

    def close(self):
        del self.model
        _free()


class AlignAttEngine:
    """SimulStreaming's own SimulWhisperASR + SimulWhisperOnline, unchanged, with settings as the
    command line sets them (frame threshold 25, audio_max_len 30, audio_min_len 0, greedy,
    no CIF model, no prompt, no logdir). `trim` sets --never_fire:
      trim=False (default as released): the last decoded word is kept;
      trim=True  (--never_fire): the last decoded word is always held back.
    Two read-only wrappers record what infer() already computes: the held-back word
    (generation['result_truncated']) and the alignment-head attention (for attention spread)."""

    def __init__(self, model_name, lang, model_dir, chunk, frame_threshold=25, trim=False):
        from simulstreaming_whisper import SimulWhisperASR, SimulWhisperOnline
        self.asr = SimulWhisperASR(
            language=lang, model_path=os.path.join(model_dir, model_name + ".pt"),
            cif_ckpt_path=None, frame_threshold=frame_threshold, audio_max_len=30.0,
            audio_min_len=0.0, segment_length=chunk, beams=1, task="transcribe",
            decoder_type="greedy", never_fire=trim, init_prompt=None, static_init_prompt=None,
            max_context_tokens=None, logdir=None)
        self.online = SimulWhisperOnline(self.asr)
        m = self.asr.model
        self._m = m
        self._attns = None
        self.last_gen = None
        orig_clean, orig_infer = m._clean_cache, m.infer

        def clean():
            self._attns = m.dec_attns          # keep the list the original is about to drop
            orig_clean()

        def infer(is_last=False):
            self._attns = None
            toks, gen = orig_infer(is_last=is_last)
            self.last_gen = gen
            return toks, gen

        m._clean_cache, m.infer = clean, infer
        self.asr.warmup(np.zeros(SR, dtype=np.float32))

    def attention_spread(self):
        """Mean entropy (nats) of the alignment heads' attention over the received frames, for the
        query position of every decoding pass of the last infer() call."""
        import torch
        gen, attns = self.last_gen, self._attns
        if not gen or not attns:
            return None
        L = len(self._m.model.decoder.blocks)
        T = int(gen["frames_len"])
        if T <= 1:
            return None
        ents = []
        for p in range(len(attns) // L):
            for layer, heads in self._m.align_source.items():
                a = attns[p * L + layer]                     # heads x queries x 1500
                for _, h in heads:
                    q = a[h, -1, :T].float()
                    q = q / q.sum().clamp_min(1e-12)
                    ents.append(float(-(q * torch.log(q.clamp_min(1e-12))).sum()))
        return float(np.mean(ents)) if ents else None

    def start(self):
        self.online.init()

    def _out(self, o):
        # The committed piece is the decoded text of the new tokens, as SimulStreaming outputs it:
        # pieces are joined by plain concatenation, so a word split across chunks ("pemot" +
        # "ongan") is rebuilt exactly as the tool's own output would show it.
        piece = o.get("text", "") if o else ""
        gen = self.last_gen or {}
        rt = gen.get("result_truncated") if isinstance(gen, dict) else None
        tail = "".join(rt["split_words"]) if rt else ""
        aux = {"spread": self.attention_spread(),
               "frames": gen.get("frames_len") if isinstance(gen, dict) else None}
        return piece, tail, aux

    def step(self, new_audio):
        self.online.insert_audio_chunk(new_audio)
        return self._out(self.online.process_iter())

    def finish(self):
        return self._out(self.online.finish())

    def close(self):
        del self.online, self.asr, self._m
        _free()


class AnchorEngine:
    """Whisper-Streaming as released (commit 6da90b4): FasterWhisperASR (beam 5, as hard-coded) +
    OnlineASRProcessor with its default segment trimming at 15 s; model large-v3, language fixed."""

    def __init__(self, lang, ws_dir, model_size="large-v3", cache_dir=None):
        import sys
        if ws_dir not in sys.path:
            sys.path.insert(0, ws_dir)
        from whisper_online import FasterWhisperASR, OnlineASRProcessor
        self.asr = FasterWhisperASR(lang, model_size, cache_dir=cache_dir)
        self.online = OnlineASRProcessor(self.asr)
        self.asr.transcribe(np.zeros(SR, dtype=np.float32))  # warm-up

    def start(self):
        self.online.init()

    def _out(self, o):
        # faster-whisper words carry their leading space and the tool joins them with sep=""
        tail = "".join(w for _, _, w in self.online.transcript_buffer.complete())
        return o[2] or "", tail, {}

    def step(self, new_audio):
        self.online.insert_audio_chunk(new_audio)
        return self._out(self.online.process_iter())

    def finish(self):
        o = self.online.finish()
        return o[2] or "", "", {}

    def close(self):
        del self.online, self.asr
        _free()


def _free():
    import gc
    gc.collect()
    if _cuda():
        import torch
        torch.cuda.empty_cache()
