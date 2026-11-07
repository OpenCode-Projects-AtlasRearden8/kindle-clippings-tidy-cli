"""Command-line interface for kindle-tidy."""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .llm import DEFAULT_ENDPOINT, DEFAULT_MODEL, LLMConfig, LLMError, theme_clippings
from .parser import parse_file
from .tidy import render_book, render_index, slugify, tidy, today


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kindle-tidy",
        description=(
            "Parse Kindle's My Clippings.txt into tidy Markdown: one clean file "
            "per book plus a master index. Runs 100% locally; the optional "
            "theming step talks only to your own local OpenAI-compatible "
            "endpoint (Ollama works out of the box, no API keys needed)."
        ),
        epilog="Example: kindle-tidy 'My Clippings.txt' -o clippings-out --themes",
    )
    p.add_argument("input", nargs="?", default="My Clippings.txt", help="Path to My Clippings.txt (default: %(default)s)")
    p.add_argument("-o", "--output", default="out", help="Output directory (default: %(default)s)")
    p.add_argument(
        "--keep-duplicates",
        action="store_true",
        help="Keep repeated highlights instead of deduping them (default: dedupe)",
    )
    p.add_argument(
        "--index-name",
        default="INDEX.md",
        help='Name of the master index file (default: %(default)s)',
    )
    p.add_argument(
        "--themes",
        action="store_true",
        help="Ask a local OpenAI-compatible endpoint to group clippings into themes",
    )
    p.add_argument(
        "--llm-endpoint",
        default=DEFAULT_ENDPOINT,
        help="OpenAI-compatible chat completions URL (default: %(default)s — Ollama)",
    )
    p.add_argument(
        "--llm-model",
        default=DEFAULT_MODEL,
        help="Model name at the endpoint (default: %(default)s)",
    )
    p.add_argument(
        "--llm-timeout",
        type=float,
        default=120.0,
        help="Seconds to wait for the local model per book (default: %(default)s)",
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    input_path = args.input

    if not os.path.isfile(input_path):
        print(f"error: input file not found: {input_path}", file=sys.stderr)
        return 2

    result = parse_file(input_path)
    for issue in result.issues:
        print(f"warning: line ~{issue.line_start}: {issue.reason}", file=sys.stderr)

    if not result.clippings:
        print("error: no clippings could be parsed from this file", file=sys.stderr)
        return 1

    sections, removed = tidy(result.clippings, keep_duplicates=args.keep_duplicates)

    if args.themes:
        config = LLMConfig(
            endpoint=args.llm_endpoint,
            model=args.llm_model,
            timeout_seconds=args.llm_timeout,
        )

    os.makedirs(args.output, exist_ok=True)
    generated = today()
    written = []
    for section in sections:
        if args.themes:
            try:
                section.themes_markdown = theme_clippings(section, config)
            except LLMError as exc:
                print(f"warning: theming skipped for '{section.title}': {exc}", file=sys.stderr)
        filename = slugify(section.title) + ".md"
        filepath = os.path.join(args.output, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(render_book(section, generated))
        written.append((section, filename))

    index_path = os.path.join(args.output, args.index_name)
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(render_index(sections, generated, args.output))

    parsed = sum(len(s.clippings) for s in sections)
    print(f"parsed {len(result.clippings)} clipping(s) ({parsed} kept after tidying) from: {input_path}")
    if removed:
        print(f"removed {removed} duplicate(s)")
    print(f"wrote {len(written)} book file(s) + {args.index_name} in: {args.output}")
    for section, filename in written:
        counts = {}
        for clip in section.clippings:
            counts[clip.kind] = counts.get(clip.kind, 0) + 1
        summary = ", ".join(f"{v} {k}s" for k, v in counts.items()) or "empty"
        print(f"  - {filename}: {summary}")
    if result.issues:
        print(f"skipped {len(result.issues)} unrecognized entr(ies) (see warnings above)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
