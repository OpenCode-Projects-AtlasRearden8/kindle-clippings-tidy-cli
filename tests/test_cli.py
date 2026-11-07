"""End-to-end CLI tests (no LLM)."""

from __future__ import annotations

import os

import pytest

from kindle_clippings_tidy.cli import main

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "My Clippings.txt")


@pytest.fixture()
def out_dir(tmp_path):
    return str(tmp_path / "out")


def test_main_writes_files_and_index(out_dir):
    code = main([SAMPLE, "-o", out_dir])
    assert code == 0
    names = sorted(os.listdir(out_dir))
    assert "INDEX.md" in names
    assert any("Chess-for-Fun" in n for n in names)
    assert any("Massive-AI-Manual" in n for n in names)

    with open(os.path.join(out_dir, "INDEX.md"), encoding="utf-8") as f:
        index = f.read()
    assert "The Massive AI Manual" in index
    assert "| 1 | 1 | 1 |" in index  # manual: 1 highlight, 1 note, 1 bookmark after dedupe


def _read(out_dir: str, needle: str) -> str:
    filename = next(n for n in os.listdir(out_dir) if needle in n)
    with open(os.path.join(out_dir, filename), encoding="utf-8") as f:
        return f.read()


def test_main_dedupes_by_default(out_dir):
    code = main([SAMPLE, "-o", out_dir])
    assert code == 0
    assert _read(out_dir, "Chess").count("Tactics come before strategy") == 1


def test_main_keep_duplicates_flag(out_dir):
    code = main([SAMPLE, "-o", out_dir, "--keep-duplicates"])
    assert code == 0
    assert _read(out_dir, "Chess").count("Tactics come before strategy") == 2


def test_main_missing_input(tmp_path):
    assert main([str(tmp_path / "nope.txt"), "-o", str(tmp_path / "o")]) == 2
