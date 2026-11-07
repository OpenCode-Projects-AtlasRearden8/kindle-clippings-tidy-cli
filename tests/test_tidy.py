"""Tests for grouping, dedupe, tagging, and Markdown rendering."""

from __future__ import annotations

from kindle_clippings_tidy.parser import Clipping
from kindle_clippings_tidy.tidy import (
    dedupe_clippings,
    group_by_book,
    render_book,
    render_index,
    slugify,
    tidy,
    yaml_quote,
)


def clip(book="Book", author="Author", kind="highlight", text="hello", page="1") -> Clipping:
    return Clipping(book=book, author=author, kind=kind, text=text, page=page)


class TestGrouping:
    def test_groups_preserve_first_seen_order(self):
        clippings = [clip(book="Odd"), clip(book="Odd"), clip(book="Even"), clip(book="Odd")]
        groups = group_by_book(clippings)
        assert [g.title for g in groups] == ["Odd", "Even"]
        assert len(groups[0].clippings) == 3

    def test_fills_author_from_any_entry(self):
        c1 = Clipping(book="B", author=None, kind="note", text="n")
        c2 = Clipping(book="B", author="Later", kind="note", text="n2")
        groups = group_by_book([c1, c2])
        assert groups[0].author == "Later"

    def test_missing_author_defaults_later(self):
        groups = group_by_book([clip(author=None)])
        assert groups[0].author is None


class TestDedupe:
    def test_exact_duplicates_removed(self):
        kept, removed = dedupe_clippings([clip(text="x"), clip(text="x")])
        assert removed == 1 and len(kept) == 1

    def test_whitespace_variants_count_as_duplicates(self):
        kept, removed = dedupe_clippings([clip(text="two words"), clip(text="two \u00a0words\u3000")])
        assert removed == 1
        assert kept[0].text == "two words"  # original casing/spacing kept

    def test_different_kind_not_duplicate(self):
        kept, removed = dedupe_clippings([clip(kind="highlight"), clip(kind="note")])
        assert removed == 0 and len(kept) == 2

    def test_tidies_across_books(self):
        clippings = [clip(book="A", text="q"), clip(book="A", text="q"), clip(book="B", text="q")]
        sections, removed = tidy(clippings)
        assert removed == 1
        assert len(sections) == 2
        assert len(sections[0].clippings) == 1 and len(sections[1].clippings) == 1


class TestTags:
    def test_counts_in_index_row(self):
        c = clip(kind="highlight")
        groups = group_by_book([c, c, c, clip(kind="note"), clip(kind="bookmark")])
        index = render_index(groups, "2026-11-07", "out")
        assert "| 3 | 1 | 1 |" in index
        assert "# Kindle Clippings — Master Index" in index

    def test_kind_headings_present_in_book_file(self):
        groups = group_by_book([clip(kind="highlight"), clip(kind="note"), clip(kind="bookmark")])
        md = render_book(groups[0], "2026-11-07")
        assert "## Highlights" in md
        assert "## Notes" in md
        assert "## Bookmarks" in md


class TestRender:
    def test_front_matter_metadata(self):
        groups = group_by_book([clip(book="My Book", author="Me")])
        md = render_book(groups[0], "2026-11-07")
        assert md.startswith("---\n")
        assert 'title: "My Book"' in md
        assert 'author: "Me"' in md
        assert "generated: \"2026-11-07\"" in md

    def test_yaml_quoting_escapes(self):
        assert yaml_quote('say "hi" \\ back') == '"say \\"hi\\" \\\\ back"'

    def test_themes_section_appended(self):
        groups = group_by_book([clip()])
        groups[0].themes_markdown = "## Themes\n\n### One\n- hello\n"
        md = render_book(groups[0], "2026-11-07")
        assert "## Themes" in md and "### One" in md

    def test_section_footer_trimmed(self):
        groups = group_by_book([clip()])
        md = render_book(groups[0], "2026-11-07")
        assert not md.endswith("\n\n")


class TestSlugify:
    def test_basic(self):
        assert slugify("The Massive AI Manual") == "The-Massive-AI-Manual"

    def test_unicode_slug_is_safe_slug(self):
        s = slugify("Café Robots ☕ (2026)")
        assert "/" not in s and " " not in s
        assert s.startswith("Café-Robots")

    def test_empty_title_fallback(self):
        assert slugify("###") == "unknown-book"
        assert slugify("") == "unknown-book"
