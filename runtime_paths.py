"""Stable resource and writable-data locations for source and frozen runs."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def resource_root() -> Path:
    """read-only resource directory."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    return Path(frozen_root) if frozen_root else Path(__file__).resolve().parent


def application_dir() -> Path:
    """directory beside the executable"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def data_dir() -> Path:
    override = os.environ.get("TOURNIRC_DATA_DIR") or os.environ.get("TOURNIRC_CONFIG_DIR")
    return Path(override).expanduser().resolve() if override else application_dir() / "cfg"


def logs_dir() -> Path:
    override = os.environ.get("TOURNIRC_LOG_DIR")
    return Path(override).expanduser().resolve() if override else application_dir() / "logs"
