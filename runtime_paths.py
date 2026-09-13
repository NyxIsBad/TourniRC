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


def _platform_data_root() -> Path:
    """find a writable data root on the current platform."""
    home = Path.home()
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or home / 'AppData' / 'Local')
    if sys.platform == 'darwin':
        return home / 'Library' / 'Application Support'
    return Path(os.environ.get('XDG_DATA_HOME') or home / '.local' / 'share')


def data_dir() -> Path:
    override = os.environ.get("TOURNIRC_DATA_DIR") or os.environ.get("TOURNIRC_CONFIG_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return _platform_data_root() / 'TourniRC'
    return application_dir() / "cfg"


def logs_dir() -> Path:
    override = os.environ.get("TOURNIRC_LOG_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return _platform_data_root() / 'TourniRC' / 'logs'
    return application_dir() / "logs"
