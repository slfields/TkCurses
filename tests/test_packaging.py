"""Packaging smoke tests: the distribution is importable and correctly typed."""

from __future__ import annotations

import importlib.metadata
import importlib.util
from pathlib import Path

import tkcurses


def test_version_is_exposed():
    assert tkcurses.__version__ == "0.1.0"


def test_installed_metadata_matches_module_version():
    assert importlib.metadata.version("tkcurses") == tkcurses.__version__


def test_ships_py_typed_marker():
    """PEP 561: type hints are only honoured downstream if py.typed is shipped."""
    spec = importlib.util.find_spec("tkcurses")
    assert spec is not None and spec.origin is not None
    assert (Path(spec.origin).parent / "py.typed").is_file()


def test_licensed_gpl3():
    meta = importlib.metadata.metadata("tkcurses")
    license_field = meta.get("License-Expression") or meta.get("License", "")
    assert "GPL-3.0" in license_field
