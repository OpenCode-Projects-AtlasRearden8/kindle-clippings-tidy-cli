# kindle-clippings-tidy

> Turn Kindle's `My Clippings.txt` export into tidy, organized Markdown — one clean
> file per book plus a master index. 100% local: your highlights never leave your
> computer. Optional: group highlights into themes using your *own* local
> OpenAI-compatible endpoint (Ollama works out of the box — no API keys needed).

Built by [Asdale Dynamics, LLC](https://dylanasdale.github.io) as part of a
beginner-friendly suite of local-first AI tools. Simple, tested, and explained
like a friend would.

## What it does

- **Splits by book** — every book gets its own tidy `.md` file (slugified filename).
- **Tags each clipping** — Highlights, Notes, and Bookmarks are grouped into labeled sections.
- **Dedupes** — repeated highlights (Kindle loves to re-sync duplicates) collapse to one; turn it off with `--keep-duplicates`.
- **Adds metadata** — YAML front matter with title, author, counts, and the generation date.
- **Master index** — `INDEX.md` table of every book with counts, authors, and links.
- **Handles the messy format** — UTF-8/UTF-16/BOM encodings, CRLF line endings, hyphen/en-dash/em-dash type markers, unicode titles, and cut-off entries are all dealt with.
- **Optional themes (local LLM)** — with `--themes`, sends each book's clippings to your local endpoint (default: Ollama at `http://localhost:11434/v1/chat/completions`) and adds a `## Themes` section grouping quotes by theme.

Distinct from *web clippings* and *citation formatting* tools — this one is only
for tidying Kindle's own export file.

## Requirements

- Python 3.10+ (standard library only for the core tool)

## Quick start

```bash
# From the folder containing My Clippings.txt (copied from your Kindle)
pip install .
kindle-tidy "My Clippings.txt" -o clippings
```

Or run it from this repo without installing:

```bash
python -m kindle_clippings_tidy "My Clippings.txt" -o clippings
```

Output:

```
clippings/
  INDEX.md                      # master index
  The-Massive-AI-Manual.md      # one file per book
  ...
```

## Grouping highlights into themes (local LLM)

1. Have a model running at an OpenAI-compatible endpoint. With Ollama:
   `ollama serve` and a model such as `ollama pull llama3.2`.
2. Run:

```bash
kindle-tidy "My Clippings.txt" -o clippings --themes
```

Options:

```bash
--llm-endpoint URL    # default: http://localhost:11434/v1/chat/completions
--llm-model NAME      # default: llama3.2
--llm-timeout SECONDS # default: 120
```

No API key is required for local endpoints such as Ollama. If your endpoint does
need a key, the tool reads it from the `OPENAI_API_KEY` environment variable at
runtime — it is never stored in files and you should never pass keys as CLI
arguments. Everything is local-files-only except the one HTTP call you
explicitly request.

## Tips

- **Kindle USB mode**: plug in your Kindle, copy `documents/My Clippings.txt` to your computer.
- **Adobe Digital Editions / older firmware**: some exports are UTF-16; this tool auto-detects it.
- **Skipped entries**: entries the parser can't recognize are reported as warnings and listed in the summary, and your data is left untouched.
- **Re-runs are safe**: the tool only writes to the output folder you choose.

## Relationship to other tools

- `clipping-cabinet-cli` — organizes *web* clippings.
- `citation-formatter-cli` — build formatted *citations* properly.
- `kindle-clippings-tidy` (this tool) — tidies *Kindle's own* `My Clippings.txt` export.

## Development

```bash
pip install -e .
pip install pytest ruff   # dev tools
pytest
ruff check .
```

Project layout:

```
kindle_clippings_tidy/   # package: parser, tidy, llm (theming), cli
tests/                   # parser edge cases (dashes, unicode), tidy, CLI, fake LLM endpoint
examples/                # sample My Clippings.txt
```

## Known limits

- Author detection uses the trailing `(Author)` convention of Amazon/Kindle exports; titles without one stay author-less.
- Bookmark rows without any text are kept as a simple list (nothing to dedupe on).
- Non-English Kindle locales use translated type lines ("Your Highlight" etc.); those may need their own patterns — contributions welcome.
- Theme quality depends on your local model; the tool never invents highlights and simply embeds the model's Markdown reply.

## License

MIT — Copyright (c) 2026 Asdale Dynamics, LLC
