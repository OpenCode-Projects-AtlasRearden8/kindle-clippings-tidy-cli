"""Tidy parsed clippings: group by book, dedupe, and render Markdown."""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field

from .parser import Clipping

KIND_LABELS = {
    "highlight": "Highlights",
    "note": "Notes",
    "bookmark": "Bookmarks",
}

_SLUG_CLEAN = re.compile(r"[^\w\s-]", re.UNICODE)
_SLUG_SPACES = re.compile(r"[\s_]+")


def slugify(title: str) -> str:
    """Filesystem-safe slug that keeps unicode letters where possible."""
    slug = _SLUG_CLEAN.sub("", title.strip())
    slug = _SLUG_SPACES.sub("-", slug).strip("-")
    slug = slug[:80] or "unknown-book"
    return slug


def yaml_quote(value: str) -> str:
    """Quote a string for YAML front matter."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


@dataclass
class BookSection:
    title: str
    author: str | None
    clippings: list[Clipping] = field(default_factory=list)
    themes_markdown: str | None = None


def group_by_book(clippings: list[Clipping]) -> list[BookSection]:
    """Group clippings by book, preserving first-seen order."""
    order: dict[str, BookSection] = {}
    for clip in clippings:
        section = order.get(clip.book)
        if section is None:
            section = BookSection(title=clip.book, author=clip.author)
            order[clip.book] = section
        if section.author is None and clip.author:
            section.author = clip.author
        section.clippings.append(clip)
    return list(order.values())


def dedupe_clippings(clippings: list[Clipping]) -> tuple[list[Clipping], int]:
    """Remove repeated clippings within a book; return (kept, removed)."""
    kept: list[Clipping] = []
    removed = 0
    for clip in clippings:
        if any(clip.matches(existing) for existing in kept):
            removed += 1
            continue
        kept.append(clip)
    return kept, removed


def _detail_line(clip: Clipping) -> str:
    parts = []
    if clip.page:
        parts.append(f"page {clip.page}")
    if clip.location:
        parts.append(f"location {clip.location}")
    if clip.added_on:
        parts.append(clip.added_on)
    return " · ".join(parts)


def render_book(section: BookSection, generated: str) -> str:
    notes = [c for c in section.clippings if c.kind == "note"]
    highlights = [c for c in section.clippings if c.kind == "highlight"]
    bookmarks = [c for c in section.clippings if c.kind == "bookmark"]
    author = section.author or "Unknown author"

    lines = [
        "---",
        f"title: {yaml_quote(section.title)}",
        f"author: {yaml_quote(author)}",
        'source: "My Clippings.txt"',
        f"highlights: {len(highlights)}",
        f"notes: {len(notes)}",
        f"bookmarks: {len(bookmarks)}",
        f"generated: {yaml_quote(generated)}",
        "---",
        "",
        f"# {section.title}",
        "",
        f"*by {author}*",
        "",
    ]

    for kind, label in KIND_LABELS.items():
        group = [c for c in section.clippings if c.kind == kind]
        if not group:
            continue
        lines.append(f"## {label}")
        lines.append("")
        for idx, clip in enumerate(group, start=1):
            detail = _detail_line(clip)
            if kind == "note":
                lines.append(f"{idx}. **Note:** {clip.text or '(empty note)'}")
                if detail:
                    lines.append(f"   *{detail}*")
            elif kind == "bookmark":
                lines.append(f"{idx}. Bookmark — *{detail or 'no location recorded'}*")
            else:
                heading = f"### {idx}."
                text = clip.text or "(empty highlight)"
                if "\n" in text:
                    text = "\n> ".join("> " + line for line in text.split("\n"))
                else:
                    text = "> " + text
                if detail:
                    lines.append(f"{heading} *{detail}*")
                else:
                    lines.append(heading)
                lines.append("")
                lines.append(text)
                lines.append("")
                continue
            lines.append("")

    if section.themes_markdown:
        lines.append(section.themes_markdown.rstrip())
        lines.append("")

    # Trim trailing blank lines, keep exactly one.
    out = "\n".join(lines).rstrip() + "\n"
    return out


def render_index(sections: list[BookSection], generated: str, out_dir: str) -> str:
    total = {k: 0 for k in KIND_LABELS}
    rows = [
        "| Book | Author | Highlights | Notes | Bookmarks | File |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for section in sections:
        counts = {k: sum(1 for c in section.clippings if c.kind == k) for k in KIND_LABELS}
        for k in total:
            total[k] += counts[k]
        filename = slugify(section.title) + ".md"
        rows.append(
            f"| {section.title} | {section.author or 'Unknown author'} "
            f"| {counts['highlight']} | {counts['note']} | {counts['bookmark']} | [{filename}](./{filename}) |"
        )
    lines = [
        "---",
        f"generated: {yaml_quote(generated)}",
        f"out_dir: {yaml_quote(out_dir)}",
        "---",
        "",
        "# Kindle Clippings — Master Index",
        "",
        f"*{len(sections)} book(s) · {total['highlight']} highlights · {total['note']} notes · "
        + f"{total['bookmark']} bookmarks*",
        "",
        *rows,
        "",
    ]
    return "\n".join(lines)


def tidy(
    clippings: list[Clipping],
    keep_duplicates: bool = False,
) -> tuple[list[BookSection], int]:
    """Group and (optionally) dedupe clippings."""
    sections = group_by_book(clippings)
    removed_total = 0
    if keep_duplicates:
        return sections, removed_total
    for section in sections:
        section.clippings, removed = dedupe_clippings(section.clippings)
        removed_total += removed
    return sections, removed_total


def today() -> str:
    return datetime.date.today().isoformat()
