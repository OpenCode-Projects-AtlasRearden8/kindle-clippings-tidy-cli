"""Parse Kindle's My Clippings.txt into structured entries.

The real-world format is messy:

- Kindle writes the file as UTF-8 (with or without BOM), UTF-16LE (BOM), or
  occasionally cp1252 on older exports.
- Entries are separated by a run of ``=`` characters (usually exactly 10).
- The type line starts with a dash-like character: ``-`` (hyphen), en dash
  (U+2013), em dash (U+2014), minus (U+2212), figdash, or CJK fullwidth dash.
- Titles are commonly ``Title (Author)`` but the author isn't always there,
  and titles may contain their own parentheses.
- Bookmarks and clips often have an empty body; some entries end up blank or
  cut off mid-line when a user deletes content on the device.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SECTION_DELIMITER = "=========="


@dataclass
class Clipping:
    """One parsed entry from My Clippings.txt."""

    book: str
    author: str | None
    kind: str  # "highlight" | "note" | "bookmark"
    text: str
    location: str | None = None
    page: str | None = None
    added_on: str | None = None
    raw_type_line: str = ""

    def matches(self, other: Clipping) -> bool:
        """Return True if two clippings are duplicates.

        Text is compared after collapsing whitespace, because Kindle
        re-wraps long highlights identically but sometimes adds stray
        internal spacing.
        """
        return (
            self.book == other.book
            and self.kind == other.kind
            and _normalize_text(self.text) == _normalize_text(other.text)
        )


@dataclass
class ParseIssue:
    line_start: int
    reason: str


@dataclass
class ParseResult:
    clippings: list[Clipping] = field(default_factory=list)
    issues: list[ParseIssue] = field(default_factory=list)


# Dash-like characters seen in My Clippings.txt headers.
_DASH_PREFIX = re.compile(
    "^[\u002d\u2010-\u2015\u2212\u2796\ufe58\ufe63\uf83a\uf83b\uf83c\uff0d\uff70]+\\s*"
)
_AUTHOR_TAIL = re.compile(r"^(.*)\s*\(([^()]+)\)\s*$", re.DOTALL)
_KIND_PATTERNS = (
    ("highlight", re.compile(r"highlight", re.IGNORECASE)),
    ("note", re.compile(r"\bnote\b", re.IGNORECASE)),
    ("bookmark", re.compile(r"bookmark|clip", re.IGNORECASE)),
)
_PAGE = re.compile(r"(?:page\s*p?|seite\s*)[-:\s]*([0-9][0-9\u2010\-\u2013\u2014,\s]*)", re.IGNORECASE)
_LOCATION = re.compile(r"l[oa]cation\s*[-:\s]*([0-9][0-9\u2010\-\u2013\u2014,\s]*)", re.IGNORECASE)
_ADDED = re.compile(r"added\s+on\s*[:\s]\s*(.+)$", re.IGNORECASE)


def _normalize_text(text: str) -> str:
    """Collapse whitespace (including NBSP/FBSP and other unicode spaces)."""
    replaced = re.sub(r"[\s\u00a0\ufeff\u2007\u202f\u205f\u3000]+", " ", text)
    return replaced.strip()


def decode_clippings(raw: bytes) -> str:
    """Decode the raw bytes of My Clippings.txt, handling BOM quirks."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            pass  # truncated UTF-16: fall through to the byte heuristics below
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    # Last resort: never crash on the user's notes.
    return raw.decode("utf-8", errors="replace")


def _split_author(book_line: str) -> tuple[str, str | None]:
    """Split 'Title (Author)' into a (title, author-or-None) pair.

    Titles can legitimately contain parentheses ("AI (Really) Explained"),
    so the author (if present) is taken as the *last* parenthetical group.
    """
    match = _AUTHOR_TAIL.match(book_line.strip())
    if match:
        return match.group(1).strip(), match.group(2).strip() or None
    return book_line.strip(), None


def _classify(type_line: str) -> str | None:
    cleaned = _DASH_PREFIX.sub("", type_line.strip())
    if not cleaned:
        return None
    for kind, pattern in _KIND_PATTERNS:
        if pattern.search(cleaned):
            if kind == "note" and "notebook" in cleaned.lower():
                continue
            return kind
    return None


def _fields_from_type_line(type_line: str) -> dict:
    fields: dict = {}
    cleaned = _DASH_PREFIX.sub("", type_line.strip())
    page = _PAGE.search(cleaned)
    if page:
        fields["page"] = _normalize_text(page.group(1))
    loc = _LOCATION.search(cleaned)
    if loc:
        fields["location"] = _normalize_text(loc.group(1))
    added = _ADDED.search(cleaned)
    if added:
        fields["added_on"] = _normalize_text(added.group(1))
    return fields


def parse_text(text: str) -> ParseResult:
    """Parse the decoded contents of a My Clippings.txt file."""
    result = ParseResult()
    lines = text.split("\n")
    # Kindle uses runs of '=' (usually exactly 10) as entry separators.
    delim = re.compile(r"^=+\s*$")

    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        if delim.match(lines[i].strip()):
            # Section delimiter with no header before it (e.g. leading
            # delimiter or doubled delimiters).
            i += 1
            continue

        header = lines[i].strip()
        start_line = i + 1
        i += 1

        if i >= len(lines):
            result.issues.append(ParseIssue(start_line, "header with no type line"))
            break

        type_line = lines[i].strip()
        i += 1

        kind = _classify(type_line)
        if kind is None:
            result.issues.append(
                ParseIssue(start_line, f"unrecognized type line: {type_line[:60]!r}")
            )
            # Skip forward to the next delimiter to resync.
            while i < len(lines) and not delim.match(lines[i].strip()):
                i += 1
            if i < len(lines):
                i += 1
            continue

        body: list[str] = []
        while i < len(lines) and not delim.match(lines[i].strip()):
            body.append(lines[i].rstrip("\r"))
            i += 1
        if i < len(lines):
            i += 1

        book, author = _split_author(header)
        clipping = Clipping(
            book=book or "Unknown Book",
            author=author,
            kind=kind,
            text=_normalize_text("\n".join(body)),
            raw_type_line=type_line,
        )
        clipping.__dict__.update(_fields_from_type_line(type_line))
        result.clippings.append(clipping)

    return result


def parse_bytes(raw: bytes) -> ParseResult:
    return parse_text(decode_clippings(raw))


def parse_file(path: str) -> ParseResult:
    with open(path, "rb") as f:
        return parse_bytes(f.read())
