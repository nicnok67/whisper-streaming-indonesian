"""Text normalisation (Whisper's normalisers), CER, split/merge errors, and number detection.

Normalisation rule (fixed before the runs, review R5): English uses EnglishTextNormalizer, Indonesian
BasicTextNormalizer (as in Radford et al., 2023). BasicTextNormalizer replaces every punctuation
mark, hyphens included, with a space, so a reduplicated word ("anak-anak") is two words in the
reference and in the hypothesis alike; the same rule applies to both sides and to both languages
for erasure, tail confirmation and M4. Word-segmentation differences ("dirumah" / "di rumah") are
not normalised away: they are counted by split_merge() and are absent from CER, which is computed
on the normalised text with spaces removed (segmentation-insensitive).
"""
import re

# OpenAI Whisper's package (SimulStreaming's bundled copy lacks english.json, the spelling table
# EnglishTextNormalizer needs)
from whisper.normalizers import BasicTextNormalizer, EnglishTextNormalizer

_EN = EnglishTextNormalizer()
_BASIC = BasicTextNormalizer()


def norm_wer(text, lang):
    """Normaliser used for WER: English -> EnglishTextNormalizer, Indonesian -> BasicTextNormalizer
    (as in Radford et al., 2023)."""
    return (_EN if lang == "en" else _BASIC)(text)


def norm_basic(text):
    """Language-neutral normaliser (lowercase, punctuation and symbols removed), used for
    erasure, tail confirmation and M4 in both languages."""
    return _BASIC(text)


def words_wer(text, lang):
    return norm_wer(text, lang).split()


def words_basic(text):
    return norm_basic(text).split()


def _levenshtein(a, b):
    try:
        from rapidfuzz.distance import Levenshtein
        return Levenshtein.distance(a, b)
    except ImportError:
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i]
            for j, cb in enumerate(b, 1):
                cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
            prev = cur
        return prev[-1]


def cer_counts(ref, hyp, lang):
    """Character edits and reference characters, on the WER-normalised text without spaces."""
    r = norm_wer(ref, lang).replace(" ", "")
    h = norm_wer(hyp, lang).replace(" ", "")
    return _levenshtein(r, h), len(r)


def split_merge(ops, ref, hyp):
    """Word-segmentation errors in an alignment: a split (one reference word written as two
    hypothesis words, "dirumah" -> "di rumah") or a merge (two reference words written as one).
    Each shows up as a substitution next to an insertion or deletion."""
    splits = merges = 0
    for k, (op, i, j) in enumerate(ops):
        if op != "S":
            continue
        for nb in (ops[k - 1] if k else None, ops[k + 1] if k + 1 < len(ops) else None):
            if nb is None:
                continue
            nop, ni, nj = nb
            if nop == "I":
                pair = (hyp[j] + hyp[nj]) if nj > j else (hyp[nj] + hyp[j])
                if pair == ref[i]:
                    splits += 1
                    break
            elif nop == "D":
                pair = (ref[i] + ref[ni]) if ni > i else (ref[ni] + ref[i])
                if pair == hyp[j]:
                    merges += 1
                    break
    return splits, merges


# Cardinal number words for the number-word sensitivity check (word lists fixed before the runs).
NUMBER_WORDS = {
    "en": {
        "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
        "nineteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
        "hundred", "hundreds", "thousand", "thousands", "million", "millions", "billion",
        "billions", "trillion", "dozen",
    },
    "id": {
        "nol", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan",
        "sepuluh", "sebelas", "belas", "puluh", "puluhan", "seratus", "ratus", "ratusan",
        "seribu", "ribu", "ribuan", "sejuta", "juta", "jutaan", "miliar", "milyar", "triliun",
        "lusin",
    },
}

_DIGIT = re.compile(r"\d")


def has_number(text, lang):
    if _DIGIT.search(text):
        return True
    return any(w in NUMBER_WORDS[lang] for w in norm_basic(text).split())


def self_test():
    from .align import align
    ref, hyp = "saya di rumah anak anak".split(), "saya dirumah anak anak".split()
    assert split_merge(align(ref, hyp), ref, hyp) == (0, 1)
    ref, hyp = "pergi kerumah".split(), "pergi ke rumah".split()
    assert split_merge(align(ref, hyp), ref, hyp) == (1, 0)
    assert norm_basic("Anak-anak") == "anak anak"
    assert cer_counts("di rumah", "dirumah", "id") == (0, 7)
    return True
