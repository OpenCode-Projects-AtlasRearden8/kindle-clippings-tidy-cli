# STATUS.md — kindle-clippings-tidy

Last updated: 2026-11-07

## What was built

A local-only Python CLI (`kindle-tidy`) that turns Kindle's `My Clippings.txt`
export into tidy Markdown:

- **By-book splitting** — one clean `.md` file per book (slugified, unicode-safe filenames).
- **Tagging** — clippings classified as Highlights / Notes / Bookmarks and grouped under labeled headings.
- **Deduplication** — repeated highlights within a book collapse to one (whitespace-normalized matching); `--keep-duplicates` disables it.
- **Metadata** — YAML front matter per book (title, author, counts, generation date) plus a master `INDEX.md` (books × authors × counts, linked).
- **Robust parser** — handles UTF-8/UTF-16/BOM/cp1252 encodings, CRLF endings, hyphen/en-dash/em-dash/minus/figure-dash type-line markers, unicode titles (CJK, RTL, smart quotes), titles with parentheses, author-less books, empty bookmark bodies, stray/doubled/leading delimiters, and cut-off entries (reported as warnings, never crashes).
- **Optional local-LLM theming** — `--themes` sends each book's clippings to any OpenAI-compatible endpoint (default: Ollama `http://localhost:11434/v1/chat/completions`, no API key) and appends a `## Themes` section. Key, if an endpoint needs one, is read from the `OPENAI_API_KEY` env var at runtime only — never stored.
- Standard library only (no runtime dependencies). Python 3.10+.

## Layout

```
kindle_clippings_tidy/   # parser.py, tidy.py, llm.py, cli.py
tests/                   # 45 tests incl. dash + unicode edge cases
examples/My Clippings.txt
pyproject.toml           # console script: kindle-tidy
README.md, LICENSE (MIT)
```

## How to run

```bash
pip install .                      # or run without install: python -m kindle_clippings_tidy
kindle-tidy "My Clippings.txt" -o clippings
kindle-tidy "My Clippings.txt" -o clippings --themes   # with a local Ollama/endpoint running
```

## Verification results (2026-11-07)

- `pytest` — **45/45 passed** (parser edge cases: dash variants –, —, −, ‒, －; unicode titles/quotes/CJK, UTF-16LE and cp1252 files, BOM, CRLF, malformed entries; dedupe; tags/counts; index; subject CLI end-to-end; fake OpenAI endpoint incl. HTTP 400 and unreachable-server paths).
- `ruff check .` — clean.
- Installed in a fresh venv (`pip install -e .`) — `kindle-tidy --version` → 0.1.0; `python -m kindle_clippings_tidy` works.
- End-to-end on `examples/My Clippings.txt`: 6 parsed, 1 duplicate removed, 3 book files + INDEX.md written, correct YAML front matter and section headings.
- `--themes` verified end-to-end against a stub OpenAI-compatible HTTP server (own machine only): `## Themes` section present in book files; unreachable endpoint degrades gracefully (warning per book, files still written).

## Known gaps

- Author detection relies on Kindle's trailing `(Author)` convention; author-less exports stay author-less.
- Non-English Kindle locale type lines ("Your Highlight" prose) would need per-locale patterns.
- Theme output quality depends on the local model; the model reply is embedded verbatim (system prompt forbids inventing quotes, but it isn't machine-enforced).
- No `--watch`/PDF/EPUB export; dedupe is exact-text (not fuzzy) by design.

## Privacy

Local files only. The only network call is the one you explicitly request via `--themes`, sent to the local endpoint you configure. No telemetry, no keys in code or config.
