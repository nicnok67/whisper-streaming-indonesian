"""Commit rules of the three re-decoding policies.

Each step receives the hypothesis of the whole buffer (re-decoded from its start with an empty
prompt) as a list of (start, end, word). The new-tail step is Whisper-Streaming's
HypothesisBuffer.insert (ufal/whisper_streaming, commit 6da90b4, whisper_online.py): keep the words
starting after the last committed word's end minus 0.1 s, then drop up to 5 words that repeat the
end of the committed text. The policies differ only in what they commit from that tail.

Because the hypothesis does not depend on what was committed (no prompt, no buffer trimming),
all three policies can be evaluated on the same sequence of decodes.
"""


class _TailState:
    def __init__(self):
        self.committed_in_buffer = []   # committed (start, end, word); never trimmed (trimming off)
        self.last_committed_time = 0.0

    def insert(self, hyp):
        new = [(a, b, t) for a, b, t in hyp if a > self.last_committed_time - 0.1]
        if len(new) >= 1:
            a, b, t = new[0]
            if abs(a - self.last_committed_time) < 1 and self.committed_in_buffer:
                cn, nn = len(self.committed_in_buffer), len(new)
                for i in range(1, min(min(cn, nn), 5) + 1):
                    c = " ".join([self.committed_in_buffer[-j][2] for j in range(1, i + 1)][::-1])
                    tail = " ".join(new[j - 1][2] for j in range(1, i + 1))
                    if c == tail:
                        for _ in range(i):
                            new.pop(0)
                        break
        return new

    def committed(self, words):
        if words:
            self.committed_in_buffer.extend(words)
            self.last_committed_time = words[-1][1]


class LocalAgreement:
    """LocalAgreement-2: commit the longest common prefix of the new tail and the previous tail
    (HypothesisBuffer.flush). The displayed tail is the unconfirmed rest (complete())."""

    name = "la2"

    def __init__(self):
        self.s = _TailState()
        self.buffer = []

    def step(self, hyp):
        new = self.s.insert(hyp)
        commit = []
        while new:
            if len(self.buffer) == 0:
                break
            if new[0][2] == self.buffer[0][2]:
                commit.append(new.pop(0))
                self.buffer.pop(0)
            else:
                break
        self.buffer = new
        self.s.committed(commit)
        return commit, list(self.buffer)

    def finish(self):
        c, self.buffer = self.buffer, []
        self.s.committed(c)
        return c


class HoldN:
    """Hold-n: commit every new word except the last n; hold-0 is the fixed-chunk policy."""

    def __init__(self, n):
        self.n = n
        self.name = f"hold{n}"
        self.s = _TailState()
        self.tail = []

    def step(self, hyp):
        new = self.s.insert(hyp)
        k = max(0, len(new) - self.n)
        commit, self.tail = new[:k], new[k:]
        self.s.committed(commit)
        return commit, list(self.tail)

    def finish(self):
        c, self.tail = self.tail, []
        self.s.committed(c)
        return c


def make_redecode_policies(hold_n):
    return [HoldN(0), HoldN(hold_n), LocalAgreement()]


def self_test():
    """Scripted hypothesis sequences with hand-computed commits (run in the notebook)."""
    W = lambda *ws: [(i * 0.5, i * 0.5 + 0.4, w) for i, w in enumerate(ws)]

    la = LocalAgreement()
    assert la.step(W("a", "b")) == ([], [(0, .4, "a"), (.5, .9, "b")])
    c, t = la.step(W("a", "b", "x"))
    assert [w[2] for w in c] == ["a", "b"] and [w[2] for w in t] == ["x"]
    c, t = la.step(W("a", "b", "c", "d"))           # "x" changed to "c": nothing agrees
    assert c == [] and [w[2] for w in t] == ["c", "d"]
    c, t = la.step(W("a", "b", "c", "d", "e"))
    assert [w[2] for w in c] == ["c", "d"] and [w[2] for w in t] == ["e"]
    assert [w[2] for w in la.finish()] == ["e"]

    h2 = HoldN(2)
    c, t = h2.step(W("a", "b", "c"))
    assert [w[2] for w in c] == ["a"] and [w[2] for w in t] == ["b", "c"]
    c, t = h2.step(W("a", "B", "c", "d"))           # committed "a" is never revised
    assert [w[2] for w in c] == ["B"] and [w[2] for w in t] == ["c", "d"], (c, t)
    h0 = HoldN(0)
    c, t = h0.step(W("a", "b"))
    assert [w[2] for w in c] == ["a", "b"] and t == []
    assert h0.finish() == []

    # n-gram de-duplication: a re-decoded word starting before the last committed end - 0.1 s is dropped
    la = LocalAgreement()
    la.step([(0.0, 0.4, "a"), (0.5, 0.9, "b")])
    la.step([(0.0, 0.4, "a"), (0.5, 0.9, "b"), (1.0, 1.4, "c")])   # commits a, b
    c, t = la.step([(0.0, 0.4, "a"), (0.85, 1.0, "b"), (1.0, 1.4, "c"), (1.5, 1.9, "d")])
    # "b" at 0.85 > 0.9-0.1 survives the time filter and repeats the committed "b": dropped
    assert [w[2] for w in c] == ["c"] and [w[2] for w in t] == ["d"], (c, t)
    return True
