#!/usr/bin/env python3
"""Mechanical check for Clearer Thinking copy.

Finds two kinds of problem in a draft:

  RULE  a house rule is broken (em dash, "ClearerThinking", "modules", self-praise,
        "scientifically proven"). No exceptions: fix every one.
  TELL  a pattern that makes copy read as generic or machine-written. Rewrite it,
        or keep it only for a reason you can state.

Usage:
    copy_lint.py draft.md [more.md ...]
    pbpaste | copy_lint.py -
    copy_lint.py --json draft.md

Exit code 1 when a RULE is broken, otherwise 0 (tells never fail the run).

This file is the single source for the word and pattern lists. The reasoning behind each
family is in ../references/generic_tells.md. Names of CT tools (read from CT_TOOLS.md),
URLs, email addresses and hashtags are masked before matching, so "Life-Changing Questions"
or a clearerthinking.org link is never flagged.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]

# Product names that contain a flagged word and are not in CT_TOOLS.md.
EXTRA_PROTECTED = ("Life-Changing Questions",)


@dataclass(frozen=True)
class Finding:
    line: int
    level: str   # "rule" or "tell"
    id: str
    text: str
    advice: str


def _words(*alternatives: str) -> str:
    """Whole-word, case-insensitive alternation."""
    return r"(?i)\b(?:" + "|".join(alternatives) + r")\b"


# (id, level, advice, pattern). Patterns are searched on the masked text.
CHECKS: list[tuple[str, str, str, str]] = [
    # ---- house rules -------------------------------------------------------------------
    ("em-dash", "rule", "No em dashes (Igor's rule). Use a comma, colon, period or parentheses.",
     r"[—―]|\s–\s|\s--\s"),
    ("brand-name", "rule", 'Write "Clearer Thinking" or "ClearerThinking.org", never "ClearerThinking".',
     r"\bClearerThinking\b(?!\.org)"),
    ("modules", "rule", 'We say "interactive tools" (or "programs"), not "modules".',
     _words("modules?")),
    ("self-praise", "rule", "No self-praise or hype. Say what the thing does and let the reader judge.",
     _words("groundbreaking", "revolutionary", "cutting[- ]edge", "world[- ]class", "best[- ]in[- ]class",
            "state[- ]of[- ]the[- ]art", "game[- ]chang(?:er|ers|ing)", "unparalleled", "unrivall?ed",
            "second to none", "life[- ]changing", "mind[- ]blowing")),
    ("proven", "rule", "Science does not prove; it measures. Say what was measured, in whom, and how big the effect was.",
     _words("(?:scientifically|clinically) proven", "proven to (?:work|help|boost|improve|reduce)")),
    # ---- generic / machine-sounding tells -------------------------------------------------
    ("unnamed-evidence", "tell", "Evidence with no source. Name the study (who, what was measured) or drop the claim.",
     _words("studies (?:show|have shown|suggest)", "research (?:shows|has shown|suggests|says)", "science says",
            "experts (?:agree|say)", "backed by science", "science[- ]backed", "according to (?:science|research|experts)")),
    ("ai-vocabulary", "tell", "Stock AI vocabulary. Use the plain word for what actually happens.",
     _words("delv(?:e|es|ing)", "tapestry", "testament to", "unleash(?:es|ed|ing)?", "supercharg(?:e|es|ed|ing)",
            "elevat(?:e|es|ing)", "empower(?:s|ed|ing)?", "embark(?:s|ed|ing)?", "harness(?:es|ed|ing)?",
            "leverag(?:e|es|ed|ing)", "seamless(?:ly)?", "holistic(?:ally)?", "transformative", "myriad", "plethora",
            "realm", "landscape", "navigat(?:e|es|ing)", "foster(?:s|ed|ing)?", "pivotal", "multifaceted",
            "ever[- ](?:evolving|changing)", "fast[- ]paced", "deep dive", "dive (?:in|into|deep|deeper)")),
    ("marketing-cliche", "tell", "Marketing cliche: it could sit on any brand's page. Replace it with a fact only this thing has.",
     _words("unlock(?:s|ed|ing)?", "(?:full|true) potential", "(?:true|best|authentic|higher) self", "next level",
            "level up", "take control", "transform your", "your journey", "journey (?:to|of|toward|towards)",
            "curious minds", "secrets?", "hacks?", "tips and tricks", "treasure trove", "one[- ]stop",
            "look no further", "say goodbye to", "the power of", "a world of", "like never before",
            "now more than ever", "more than ever", "in today's")),
    ("filler", "tell", "Throat-clearing. Delete it and start with the point.",
     _words("it'?s (?:important|worth) (?:to note|noting)", "it is (?:important|worth) (?:to note|noting)",
            "when it comes to", "at the end of the day", "needless to say", "rest assured", "the fact of the matter",
            "in conclusion", "in summary", "to sum up", "in other words", "simply put", "that said", "with that in mind")),
    ("signpost", "tell", "Signpost or staged reveal. Say the thing instead of announcing it.",
     r"(?i)\b(?:here'?s (?:the (?:thing|kicker|catch|truth|deal|secret|good news)|what (?:you need to know|that means)|why(?: that matters)?)"
     r"|let'?s (?:dive|explore|unpack|break (?:it|this) down|face it|be honest|talk about)"
     r"|the (?:truth|bottom line|reality) is|spoiler(?: alert)?:"
     r"|(?:the|your|our) (?:results?|best part|catch|kicker|answer|secret|good news|bad news|problem|solution|upshot|takeaway|twist|truth)\?)"),
    ("stock-opener", "tell", "Stock opener. Start with the finding, the reader's problem in their words, or the ask.",
     r"(?im)^[ \t>*#-]*(?:ever wonder(?:ed)?|have you ever|imagine\b|picture this|what if\b|did you know|in a world|"
     r"we'?ve all been|we all (?:know|have)|as humans|if you'?re like most)"),
    ("stock-cta", "tell", 'Stock call to action. Name the action and what the reader gets ("Take the 10-minute test").',
     r"(?i)\bready to [^?\n]{1,70}\?|\bwhat are you waiting for|\bget started today|\bstart your journey|\bjoin us today"),
    ("not-x-but-y", "tell", "Contrast with a claim nobody made. State the positive point directly.",
     r"(?i)\bnot (?:just|only|merely|simply)\b|\bmore than just\b|\bisn'?t just\b"
     r"|\b(?:it'?s|it is|this is|this isn'?t|that'?s|they'?re) not (?:about )?[^.!?\n]{1,60}[.;,]\s+(?:it'?s|it is|they'?re|this is|that'?s)\b"
     r"|\bisn'?t (?:about )?[^.!?\n]{1,60}[.;]\s+(?:it'?s|it is)\b"),
    ("audience-cover", "tell", "Audience-covering phrase. Pick the one reader this piece is for.",
     r"(?i)\bwhether you(?:'re| are)\b"),
    ("intensifier", "tell", "Sincerity marker or intensifier. If the sentence is true without it, cut it.",
     _words("truly", "genuinely", "incredibly", "absolutely", "utterly", "honestly", "frankly", "remarkably")),
    ("prescriptive", "tell", 'Prescriptive. CT explains and lets the reader decide ("you can", "one option is").',
     _words("you should", "you must", "you need to", "you have to")),
    ("fake-urgency", "tell", "Urgency only when the deadline is real, and then state the date.",
     _words("act now", "don'?t miss(?: out)?", "last chance", "limited time", "hurry", "before it'?s too late",
            "while supplies last")),
    ("validation", "tell", "Stock reassurance. Say something specific to this reader's situation, or nothing.",
     _words("you'?re not alone", "you are not alone", "it'?s okay to", "be kind to yourself", "you'?ve got this",
            "you deserve")),
    ("woo", "tell", "Borrowed mysticism. Say the literal thing.",
     _words("the universe", "manifest(?:s|ed|ing)?", "vibrations?", "inner wisdom", "sacred", "awaken(?:s|ed|ing)?",
            "destiny", "soul'?s?", "hold(?:ing)? space", "aligned with your")),
    ("borrowed-authority", "tell", "Borrowed authority. Unless the quote is the subject, write your own sentence.",
     r"(?i)\bas [A-Z][\w.' -]{2,40}? (?:once |famously )?(?:said|wrote|put it|observed)\b"),
    ("america", "tell", 'Say "the U.S.", not "America": readers in other American countries notice.',
     r"\bAmerica\b"),
    ("exclamation", "tell", "Exclamation mark. Let the fact carry the energy.",
     r"(?<![<!])!(?!important|=|-|\[)"),  # not <!DOCTYPE, <!--, !important, != or a Markdown image
    # Second and third items lowercase, so lists of names ("LinkedIn, Instagram and X") are left alone.
    ("triad", "tell", "List of three single words. Keep it only if there are exactly three things and each one is specific.",
     r"\b[A-Za-z'-]+, [a-z'-]+,? and [a-z'-]+\b"),
]

_COMPILED = [(cid, level, advice, re.compile(pat)) for cid, level, advice, pat in CHECKS]

_MASK_ALWAYS = re.compile(r"https?://\S+|\b[\w.-]+@[\w.-]+\.\w+\b|\b[\w-]+(?:\.[\w-]+)*\.(?:org|com|net|io)(?:/\S*)?|#\w+")
# A sentence ends at . ! or ? followed by a space and a capital, digit or quote, so "the U.S. sleeps" stays whole.
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[\"'“‘A-Z0-9])")
FRAGMENT_MAX_WORDS = 4
FRAGMENT_RUN = 3


def tool_names(path: Path | None = None) -> list[str]:
    """Tool names from CT_TOOLS.md (the `**[Name](url)**` entries), with and without a leading "The"."""
    path = path or REPO_ROOT / "CT_TOOLS.md"
    if not path.exists():
        return []
    names = re.findall(r"\*\*\[(.+?)\]\(", path.read_text(encoding="utf-8"))
    return names + [n[4:] for n in names if n.startswith("The ")]


def mask(text: str, protected: list[str] | tuple[str, ...] = ()) -> str:
    """Blank out URLs, emails, hashtags and protected names, keeping every character position."""
    def blank(m: re.Match) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    # ClearerThinking.org is a legal brand form: keep it visible to the brand-name check.
    out = _MASK_ALWAYS.sub(lambda m: m.group(0) if m.group(0).startswith("ClearerThinking.org") else blank(m), text)
    for name in sorted(set(protected), key=len, reverse=True):
        if name.strip():
            out = re.sub(re.escape(name), blank, out, flags=re.IGNORECASE)
    return out


def _fragment_runs(masked: str) -> list[tuple[int, str]]:
    """Runs of three or more consecutive very short sentences ("No fluff. No jargon. Just science.")."""
    found = []
    for para in re.finditer(r"[^\n]+", masked):
        run: list[tuple[int, str]] = []
        pos = 0
        for piece in _SENTENCE_BREAK.split(para.group(0)) + [""]:
            start = para.group(0).find(piece, pos) if piece else pos
            pos = start + len(piece)
            if piece and piece.rstrip()[-1:] in ".!?" and len(piece.split()) <= FRAGMENT_MAX_WORDS:
                run.append((para.start() + start, piece.strip()))
                continue
            if len(run) >= FRAGMENT_RUN:
                found.append((run[0][0], " ".join(text for _, text in run)))
            run = []
    return found


def lint(text: str, protected: list[str] | tuple[str, ...] | None = None) -> list[Finding]:
    """Every finding in `text`, in reading order. `protected` defaults to CT's tool names."""
    if protected is None:
        protected = tool_names() + list(EXTRA_PROTECTED)
    masked = mask(text, protected)
    line_of = lambda pos: masked.count("\n", 0, pos) + 1  # noqa: E731
    hits: list[tuple[int, Finding]] = []
    for cid, level, advice, rx in _COMPILED:
        for m in rx.finditer(masked):
            snippet = " ".join(text[m.start():m.end()].split())
            hits.append((m.start(), Finding(line_of(m.start()), level, cid, snippet, advice)))
    for pos, snippet in _fragment_runs(masked):
        hits.append((pos, Finding(line_of(pos), "tell", "fragment-run", snippet,
                                  "Staccato fragments for drama. Say it in one sentence.")))
    return [f for _, f in sorted(hits, key=lambda h: (h[0], h[1].id))]


def summary(findings: list[Finding]) -> str:
    rules = sum(f.level == "rule" for f in findings)
    tells = len(findings) - rules
    if not findings:
        return "Clean: no rule broken, no tell found."
    return (f"{rules} rule(s) broken, {tells} tell(s). Fix every rule. "
            "Rewrite each tell, or keep it only for a reason you can state.")


def report(name: str, findings: list[Finding]) -> str:
    lines = [name]
    for f in findings:
        lines.append(f'  {f.level.upper():4}  {f.id:18} line {f.line:<4} "{f.text}"\n        {f.advice}')
    lines.append("  " + summary(findings))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check Clearer Thinking copy for house rules and generic tells.")
    ap.add_argument("files", nargs="+", help='draft files, or "-" for stdin')
    ap.add_argument("--json", action="store_true", help="print findings as JSON")
    args = ap.parse_args(argv)

    results = {}
    for name in args.files:
        text = sys.stdin.read() if name == "-" else Path(name).read_text(encoding="utf-8")
        results["stdin" if name == "-" else name] = lint(text)

    if args.json:
        print(json.dumps({n: [asdict(f) for f in fs] for n, fs in results.items()}, indent=2, ensure_ascii=False))
    else:
        print("\n\n".join(report(n, fs) for n, fs in results.items()))
    return 1 if any(f.level == "rule" for fs in results.values() for f in fs) else 0


if __name__ == "__main__":
    sys.exit(main())
