from __future__ import annotations

import json
import sys
from pathlib import Path

import click


def read_text_input(value: str) -> str:
    """Read text from an inline string, @file, or @- (stdin)."""
    if not value.startswith("@"):
        return value
    path = value[1:]
    if path == "-":
        return sys.stdin.read()
    p = Path(path)
    if not p.exists():
        raise click.BadParameter(f"File not found: {path}")
    return p.read_text()


def parse_json_input(value: str) -> dict:
    """Parse JSON from inline string, @file, or @- (stdin)."""
    text = read_text_input(value)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise click.BadParameter(f"Invalid JSON: {e}")
