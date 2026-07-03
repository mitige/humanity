# core/language.py
"""The invention of language (Phase 6) — deterministic naming games.

FUNCTIONAL NOTE (load-bearing): this implements the mechanism by which shared
lexical CONVENTIONS emerge in a population — the naming game (Steels; iterated
alignment, Kirby) — made fully deterministic. Each agent INVENTS word forms
(seeded syllable composition) for the meanings it actually perceives (the
grounded object kinds), names what it sees when it verbalizes, and ALIGNS on
what it hears: a heard word is bound to the meaning the hearer's OWN context
suggests (the speaker's meaning is never transmitted — that inference gap is
the game), reinforced when familiar, adopted when new, with lateral inhibition
of competing synonyms. Usage entrenches; conventions spread; a shared lexicon
EMERGES and is measured (per-agent success, society-level convergence).

"Inventing a language" here is exactly that measurable emergence — update
rules over strength tables. It is not reference, understanding, intention, or
experience; reproducing the mechanism does not prove phenomenality; the agents
are not conscious.
"""
from __future__ import annotations

from core.constants import (
    LANGUAGE_ADOPT_STRENGTH,
    LANGUAGE_HEAR_BOOST,
    LANGUAGE_HOMONYM_INHIBITION,
    LANGUAGE_INHIBITION,
    LANGUAGE_MEANINGS,
    LANGUAGE_STRENGTH_FLOOR,
    LANGUAGE_SUCCESS_EMA,
    LANGUAGE_SYLLABLES,
    LANGUAGE_USE_BOOST,
)
from schemas.models import HeardWord, LanguageState


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


class Lexicon:
    """One agent's invented lexicon: meaning->word strengths + game updates."""

    # Ticks for the urge to speak to fully rebuild after an utterance: speaking
    # is PERIODIC (the drive swells, overflows into VERBALIZE, then resets), so
    # the agents keep foraging between exchanges instead of chattering nonstop.
    URGE_PERIOD: int = 8

    def __init__(self, agent_id: int) -> None:
        self.agent_id = int(agent_id)
        # (meaning, word) -> strength in (0, 1]
        self._strengths: dict[tuple[str, str], float] = {}
        self._invented: int = 0
        self._success_ema: float = 0.0
        self._n_exchanges: int = 0
        self._last_utterance: dict | None = None
        self._heard_this_tick: list[HeardWord] = []
        self._ticks_since_spoken: int = self.URGE_PERIOD  # full urge at birth

    # ------------------------------------------------------------- invention
    def _invent(self, meaning: str) -> str:
        """Coin a new word form, deterministically, unique to this agent's history.

        No RNG: syllable indices derive from (agent id, meaning, invention
        counter) arithmetic, so two same-seed societies coin identical words.
        """
        m_idx = LANGUAGE_MEANINGS.index(meaning) if meaning in LANGUAGE_MEANINGS else 0
        n = len(LANGUAGE_SYLLABLES)
        base = self.agent_id * 31 + m_idx * 17 + self._invented * 7
        length = 2 + (base % 2)                     # 2- or 3-syllable words
        word = "".join(LANGUAGE_SYLLABLES[(base + k * 5 + (base >> 3)) % n]
                       for k in range(length))
        self._invented += 1
        return word

    # ------------------------------------------------------------- speaking
    def word_for(self, meaning: str) -> str | None:
        """The agent's current strongest word for a meaning (stable tie-break)."""
        entries = [(w, s) for (m, w), s in self._strengths.items() if m == meaning]
        if not entries:
            return None
        # strongest first; lexicographic tie-break keeps this deterministic
        entries.sort(key=lambda e: (-e[1], e[0]))
        return entries[0][0]

    def speak(self, meaning: str) -> dict:
        """Name a meaning: use the strongest word (inventing one if none) and
        entrench it slightly (use begets convention; rivals are inhibited)."""
        word = self.word_for(meaning)
        if word is None:
            word = self._invent(meaning)
            self._strengths[(meaning, word)] = LANGUAGE_ADOPT_STRENGTH
        key = (meaning, word)
        self._strengths[key] = _clip01(self._strengths[key] + LANGUAGE_USE_BOOST)
        self._inhibit_rivals(meaning, word)
        self._last_utterance = {"word": word, "meaning": meaning}
        self._ticks_since_spoken = 0          # the urge resets after speaking
        return self._last_utterance

    @property
    def urge(self) -> float:
        """How much the drive to speak has rebuilt since the last utterance (0..1)."""
        return _clip01(self._ticks_since_spoken / float(self.URGE_PERIOD))

    # -------------------------------------------------------------- hearing
    def hear(self, word: str, inferred_meaning: str | None, sender_id: int) -> HeardWord:
        """Align on a heard word, binding it to the hearer's OWN inferred meaning.

        understood = the hearer's current word for that meaning already matched
        (measured BEFORE the update). Adoption/reinforcement + lateral
        inhibition of competing synonyms follow — the naming-game alignment.
        With no inferable context the exchange leaves the lexicon untouched.
        """
        heard = HeardWord(word=str(word), sender_id=int(sender_id),
                          inferred_meaning=inferred_meaning, understood=False)
        if inferred_meaning is None:
            self._heard_this_tick.append(heard)
            return heard
        own = self.word_for(inferred_meaning)
        heard.understood = bool(own == word)
        self._n_exchanges += 1
        self._success_ema = _clip01(
            (1.0 - LANGUAGE_SUCCESS_EMA) * self._success_ema
            + LANGUAGE_SUCCESS_EMA * (1.0 if heard.understood else 0.0))
        key = (inferred_meaning, word)
        if key in self._strengths:
            self._strengths[key] = _clip01(self._strengths[key] + LANGUAGE_HEAR_BOOST)
        else:
            self._strengths[key] = LANGUAGE_ADOPT_STRENGTH
        self._inhibit_rivals(inferred_meaning, word)
        self._heard_this_tick.append(heard)
        return heard

    def _inhibit_rivals(self, meaning: str, word: str) -> None:
        """Lateral inhibition, both ways (the classic anti-drift updates).

        Reinforcing (meaning, word) weakens (a) SYNONYMS — other words this
        agent holds for the same meaning — and (b) HOMONYMS — other meanings
        this agent attaches to the same word. Without (b), one early word
        spreads across every meaning (heard words bind to whatever context the
        hearer happens to have) and the 'language' collapses into a single
        all-purpose sound.
        """
        for (m, w) in list(self._strengths):
            if (m == meaning) == (w == word):
                continue  # the reinforced entry itself, or an unrelated one
            # Homonyms (same word, other meaning) are inhibited harder than
            # synonyms: alternating contexts re-boost them (+HEAR_BOOST) fast
            # enough that a soft decay never evicts them.
            rate = LANGUAGE_HOMONYM_INHIBITION if w == word else LANGUAGE_INHIBITION
            s = self._strengths[(m, w)] * (1.0 - rate)
            if s < LANGUAGE_STRENGTH_FLOOR:
                del self._strengths[(m, w)]
            else:
                self._strengths[(m, w)] = s

    # ------------------------------------------------------------- readouts
    def vocabulary(self) -> dict[str, str]:
        """meaning -> current strongest word, for every meaning that has one."""
        return {m: w for m in LANGUAGE_MEANINGS
                if (w := self.word_for(m)) is not None}

    def deficit(self) -> float:
        """How far the goal 'invent a language' still is (drives the pressure).

        Success-weighted: coverage (having words at all) is earned quickly, but
        the goal is a SHARED language — so the drive persists while exchanges
        keep failing (words not matching the interlocutors') and only dies out
        as conventions actually settle (success EMA -> 1).
        """
        coverage = len(self.vocabulary()) / max(1, len(LANGUAGE_MEANINGS))
        return _clip01(1.0 - (0.25 * coverage + 0.75 * self._success_ema))

    @property
    def success_rate(self) -> float:
        return float(self._success_ema)

    def state(self) -> LanguageState:
        """Assemble this tick's LanguageState and clear the per-tick buffers."""
        self._ticks_since_spoken += 1         # the urge to speak rebuilds
        vocab = self.vocabulary()
        st = LanguageState(
            utterance=self._last_utterance,
            heard=list(self._heard_this_tick),
            vocabulary=vocab,
            vocabulary_size=len(vocab),
            success_rate=round(self._success_ema, 4),
            n_exchanges=int(self._n_exchanges),
            deficit=round(self.deficit(), 4),
            report=self._report(vocab),
        )
        self._last_utterance = None
        self._heard_this_tick = []
        return st

    def _report(self, vocab: dict[str, str]) -> str:
        """One factual sentence about the lexicon, from the variables."""
        if not vocab:
            return ("Language: no invented words yet — the lexicon is empty. "
                    "(Naming-game variables; not understanding.)")
        pairs = ", ".join(f"'{w}'={m}" for m, w in sorted(vocab.items()))
        return (f"Language: {len(vocab)}/{len(LANGUAGE_MEANINGS)} meanings named ({pairs}); "
                f"communicative success {self._success_ema:.2f} over {self._n_exchanges} exchange(s). "
                "(Emergent naming-game conventions; not understanding, not experience.)")


def society_language_summary(lexicons: dict[int, Lexicon]) -> dict:
    """The emergent dictionary of a society + its lexical convergence.

    For each meaning: every agent's current word, the modal (majority) variant
    and its share. Convergence = across meanings named by >= 2 agents, the mean
    share of agents agreeing on the modal word — the standard naming-game
    convergence measure. None until at least one meaning is shared.
    """
    dictionary: dict[str, dict] = {}
    shares: list[float] = []
    for meaning in LANGUAGE_MEANINGS:
        words = {aid: lex.word_for(meaning) for aid, lex in lexicons.items()}
        words = {aid: w for aid, w in words.items() if w is not None}
        if not words:
            continue
        counts: dict[str, int] = {}
        for w in words.values():
            counts[w] = counts.get(w, 0) + 1
        modal, modal_n = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        share = modal_n / len(words)
        if len(words) >= 2:
            shares.append(share)
        dictionary[meaning] = {
            "modal_word": modal,
            "agreement": round(share, 4),
            "speakers": len(words),
            "variants": dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))),
            "by_agent": {str(aid): w for aid, w in sorted(words.items())},
        }
    convergence = round(sum(shares) / len(shares), 4) if shares else None
    modal_words = [d["modal_word"] for d in dictionary.values()]
    return {
        "dictionary": dictionary,
        "convergence": convergence,
        "n_meanings_named": len(dictionary),
        # Distinct modal words expose population-level POLYSEMY honestly: a
        # 'language' whose every meaning shares one sound converged trivially
        # (proto-language polysemy — a real naming-game outcome, not hidden).
        "distinct_modal_words": len(set(modal_words)),
        "note": ("The emergent lexicon: invented word forms per grounded meaning, "
                 "with the majority convention and each agent's variant. Convergence "
                 "is the mean agreement on the modal word (naming-game measure); "
                 "distinct_modal_words exposes cross-speaker polysemy."),
    }
