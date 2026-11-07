"""Tests for parsing My Clippings.txt, focused on real-world edge cases."""

from __future__ import annotations

import textwrap

from kindle_clippings_tidy.parser import (
    Clipping,
    decode_clippings,
    parse_bytes,
    parse_text,
)


def _entry(book: str, type_line: str, body: str = "", delim: str = "==========") -> str:
    return f"{book}\n{type_line}\n{body}\n{delim}\n"


def make_clipping(book="Book (Author)", kind="Highlight", body="text", where="on page 7 | location 70-71 | Added on Monday, February 2, 2026 10:00:00 AM") -> Clipping:
    text = textwrap.dedent(
        f"""\
        {book}
        - Your {kind} {where}

        {body}
        ==========
        """
    )
    result = parse_text(text)
    assert result.issues == []
    assert len(result.clippings) == 1
    return result.clippings[0]


class TestBasics:
    def test_classifies_three_kinds(self):
        parsed = parse_text(
            "B (A)\n- Your Highlight on page 1 | Added on Sun Jan 1 2026\n"
            "hi\n==========\n"
            "B (A)\n- Your Note on page 2 | Added on Sun Jan 1 2026\n"
            "n\n==========\n"
            "B (A)\n- Your Bookmark on page 3 | Added on Sun Jan 1 2026\n"
            "\n==========\n"
        )
        assert [c.kind for c in parsed.clippings] == ["highlight", "note", "bookmark"]
        assert parsed.issues == []

    def test_extracts_page_location_added_on(self):
        clip = make_clipping()
        assert clip.book == "Book"
        assert clip.author == "Author"
        assert clip.page == "7"
        assert clip.location == "70-71"
        assert clip.added_on == "Monday, February 2, 2026 10:00:00 AM"
        assert clip.text == "text"

    def test_title_with_internal_parens(self):
        clip = make_clipping(book="AI (Really) Explained (Dylan Asdale)")
        assert clip.book == "AI (Really) Explained"
        assert clip.author == "Dylan Asdale"

    def test_title_without_author(self):
        clip = make_clipping(book="Some Journal")
        assert clip.author is None
        assert clip.book == "Some Journal"


class TestDashVariants:
    """Kindle exports in different locales use different dash characters."""

    def test_hyphen(self):
        clip = make_clipping()
        assert clip.kind == "highlight"

    def test_en_dash_type_line(self):
        result = parse_text(
            _entry("B (A)", "\u2013 Your Highlight on page 12 | Added on Mon Feb 2 2026")
        )
        assert result.clippings[0].kind == "highlight"

    def test_em_dash_type_line(self):
        result = parse_text(
            _entry("B (A)", "\u2014 Your Note on location 9 | Added on Mon Feb 2 2026")
        )
        assert result.clippings[0].kind == "note"

    def test_minus_and_figure_dash(self):
        for dash in ("\u2212", "\u2012", "\uff0d"):
            result = parse_text(
                _entry("B (A)", f"{dash} Your Bookmark | Added on Mon Feb 2 2026")
            )
            assert result.clippings[0].kind == "bookmark", dash

    def test_page_range_with_unicode_dash(self):
        clip = make_clipping(where="on page 145\u2013146 | location 2222\u20132237 | Added on Fri Apr 3 2020")
        assert clip.page == "145\u2013146"
        assert clip.location == "2222\u20132237"


class TestUnicodeAndEncodings:
    def test_utf8_bom_and_smart_quotes(self):
        raw = "B \u201cCalled\u201d (A)\n- Your Highlight on page 1\n\u2018quoted\u2019 text\n==========\n".encode("utf-8-sig")
        parsed = parse_bytes(raw)
        assert parsed.clippings[0].text == "\u2018quoted\u2019 text"
        assert parsed.clippings[0].book == "B \u201cCalled\u201d"

    def test_utf16le_file(self):
        raw = _entry("B\u00e4ch (A)", "- Your Highlight on page 1", "text").encode("utf-16")
        parsed = parse_bytes(raw)
        assert parsed.clippings[0].book == "B\u00e4ch"

    def test_cp1252_fallback(self):
        raw = _entry("Caf\u00e9 (A)", "- Your Highlight on page 1", "v\u00e9rit\u00e9").encode("cp1252")
        parsed = parse_bytes(raw)
        assert parsed.clippings[0].book == "Caf\u00e9"
        assert parsed.clippings[0].text == "v\u00e9rit\u00e9"

    def test_cjk_and_rtl_titles(self):
        raw = _entry("\u300a\u4eba\u5de5\u667a\u80fd\u6559\u7a0b\u300b (\u674e\u56db)", "- Your Highlight on page 1").encode("utf-8")
        parsed = parse_bytes(raw)
        assert parsed.clippings[0].book == "\u300a\u4eba\u5de5\u667a\u80fd\u6559\u7a0b\u300b"

    def test_decode_never_crashes(self):
        assert decode_clippings(b"\xff\xfe ok").endswith("ok")
        assert decode_clippings(b"plain ascii") == "plain ascii"


class TestMalformedInput:
    def test_unrecognized_type_line_is_recorded_and_skipped(self):
        result = parse_text(
            "B (A)\nSomething odd happened\nbody\n==========\n"
            "B (A)\n- Your Highlight on page 1\nok\n==========\n"
        )
        assert len(result.issues) == 1
        assert [c.text for c in result.clippings] == ["ok"]

    def test_leading_and_doubled_delimiters(self):
        result = parse_text(
            "==========\nB (A)\n- Your Highlight on page 1\nhi\n==========\n==========\n"
        )
        assert len(result.clippings) == 1
        assert result.issues == []

    def test_header_with_no_type_line(self):
        result = parse_text("B (A)\n")
        assert result.clippings == []
        assert len(result.issues) == 1

    def test_empty_file(self):
        result = parse_text("\r\n\r\n")
        assert result.clippings == [] and result.issues == []

    def test_crlf_everywhere(self):
        text = "B (A)\r\n- Your Highlight on page 1\r\nfirst\r\n\r\nsecond\r\n==========\r\n"
        parsed = parse_text(text)
        assert parsed.clippings[0].text == "first second"   # blank line normalized away

    def test_delimiter_of_any_equal_length(self):
        result = parse_text("B (A)\n- Your Highlight on page 1\nhi\n===\n")
        assert len(result.clippings) == 1
