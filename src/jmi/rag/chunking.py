"""Turn vacancy HTML into chunks for embedding.

Two strategies are kept side by side so stage 7 can measure which retrieves better:

* ``window``   - fixed windows of ~CHUNK_WORDS words with overlap. Simple, works on any text.
* ``sections`` - split on the posting's own headings ("Requirements", "Обязанности", ...);
  tiny sections are merged, huge ones fall back to windows. Each chunk carries its section,
  so a question about requirements can be filtered to requirement chunks.

Sizes are in words, not tokens: there is no bge-m3 tokenizer in the pipeline, and ~350 English
words is ~470 tokens. bge-m3 accepts 8k tokens, so the limit is about retrieval precision
(one topic per chunk), not about truncation.
"""

import html
import re
from dataclasses import dataclass

CHUNK_WORDS = 350
OVERLAP_WORDS = 50
MIN_SECTION_WORDS = 40
MAX_HEADING_CHARS = 80

STRATEGIES = ("window", "sections")

_HEADING = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.IGNORECASE | re.DOTALL)
_BOLD = re.compile(r"<(b|strong)\b[^>]*>(.*?)</\1>", re.IGNORECASE | re.DOTALL)
_LI = re.compile(r"<li\b[^>]*>", re.IGNORECASE)
_BLOCK = re.compile(r"<(?:br|p|div|ul|ol|/li|tr|h[1-6])\b[^>]*/?>|</(?:p|div|ul|ol|tr|h[1-6])>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"[ \t ]+")
# Private-use markers survive tag stripping and tell a bold-only line apart from bold inside a sentence.
_B_OPEN, _B_CLOSE = "", ""

# Section heading keywords -> kind. Checked in order; first match wins.
SECTION_KINDS: list[tuple[str, re.Pattern]] = [
    ("benefits", re.compile(r"benefit|perk|we offer|what we offer|compensation|условия|предлагаем|мы предлагаем|"
                            r"бонус|льгот", re.I)),
    ("requirements", re.compile(r"requirement|qualification|must have|nice to have|you have|you bring|skills|"
                                r"experience|about you|who you are|требовани|ожидаем|навык|опыт", re.I)),
    ("responsibilities", re.compile(r"responsib|duties|what you.?ll do|the role|your role|day to day|"
                                    r"обязанност|задачи|чем предстоит", re.I)),
    ("company", re.compile(r"about us|about the company|who we are|our company|о компании|о нас", re.I)),
]


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    section: str | None = None
    section_kind: str = "other"


def html_to_lines(raw: str) -> list[str]:
    """Readable lines; headings become '## heading', list items '- item'."""
    text = _HEADING.sub(lambda m: f"\n## {m.group(1)}\n", raw or "")
    text = _BOLD.sub(lambda m: f"{_B_OPEN}{m.group(2)}{_B_CLOSE}", text)
    text = _LI.sub("\n- ", text)
    text = _BLOCK.sub("\n", text)
    text = html.unescape(_TAG.sub(" ", text))

    lines = []
    for line in text.splitlines():
        line = _SPACES.sub(" ", line).strip()
        bare = line.replace(_B_OPEN, "").replace(_B_CLOSE, "").strip()
        if not bare or bare == "##":
            continue
        # A line that is entirely bold and short is how many postings write headings.
        if line.startswith(_B_OPEN) and line.endswith(_B_CLOSE) and len(bare) <= MAX_HEADING_CHARS:
            bare = f"## {bare}"
        lines.append(bare)
    return lines


def section_kind(heading: str | None) -> str:
    if heading:
        for kind, pattern in SECTION_KINDS:
            if pattern.search(heading):
                return kind
    return "other"


def _windows(words: list[str], size: int = CHUNK_WORDS, overlap: int = OVERLAP_WORDS) -> list[str]:
    if len(words) <= size:
        return [" ".join(words)] if words else []
    step = size - overlap
    out = []
    for start in range(0, len(words), step):
        out.append(" ".join(words[start:start + size]))
        if start + size >= len(words):
            break
    return out


def chunk_window(description_html: str) -> list[Chunk]:
    words = " ".join(line.removeprefix("## ") for line in html_to_lines(description_html)).split()
    return [Chunk(i, text) for i, text in enumerate(_windows(words))]


def _sections(lines: list[str]) -> list[tuple[str | None, list[str]]]:
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in lines:
        if line.startswith("## "):
            sections.append((line[3:].rstrip(":").strip(), []))
        else:
            sections[-1][1].append(line)
    return [(heading, body) for heading, body in sections if body]


def chunk_sections(description_html: str) -> list[Chunk]:
    merged: list[tuple[str | None, list[str]]] = []
    for heading, body in _sections(html_to_lines(description_html)):
        words = " ".join(body).split()
        # Fold a tiny section into the previous one rather than embedding a 10-word chunk.
        if merged and len(" ".join(merged[-1][1]).split()) < MIN_SECTION_WORDS:
            prev_heading, prev_body = merged[-1]
            merged[-1] = (prev_heading or heading, prev_body + ([f"{heading}:"] if heading else []) + body)
        elif merged and len(words) < MIN_SECTION_WORDS and section_kind(heading) == "other":
            merged[-1][1].extend(([f"{heading}:"] if heading else []) + body)
        else:
            merged.append((heading, list(body)))

    chunks: list[Chunk] = []
    for heading, body in merged:
        for text in _windows(" ".join(body).split()):
            chunks.append(Chunk(len(chunks), text, heading, section_kind(heading)))
    return chunks


def chunk(description_html: str, strategy: str) -> list[Chunk]:
    if strategy == "window":
        return chunk_window(description_html)
    if strategy == "sections":
        return chunk_sections(description_html)
    raise ValueError(f"unknown chunking strategy: {strategy}")
