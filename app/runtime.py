"""Shared runtime constants and bundled resource lookup."""
from pathlib import Path
import sys

DEFAULT_PORT = 8000
VERSION = '0.1.1'


def resource_path(*parts):
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
    return root.joinpath(*parts)
