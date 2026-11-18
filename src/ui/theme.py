"""Tema dan stylesheet IslamicHabits.

Modul ini berada di lapisan antarmuka karena memakai GTK/Adw. Logika tetap
bebas dari pustaka grafis.
"""

from __future__ import annotations

import os
from pathlib import Path

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gtk

from ..logic.constants import APP_ID

__all__ = ["THEME_KEYS", "THEME_LABELS", "apply_theme", "load_stylesheet"]

THEME_KEYS = ("sistem", "terang", "gelap")
THEME_LABELS = ("Ikut sistem", "Terang", "Gelap")

_COLOR_SCHEMES = {
    "sistem": Adw.ColorScheme.DEFAULT,
    "terang": Adw.ColorScheme.FORCE_LIGHT,
    "gelap": Adw.ColorScheme.FORCE_DARK,
}


def apply_theme(theme: str) -> None:
    """Terapkan pilihan tema ke style manager global."""

    scheme = _COLOR_SCHEMES.get(theme, Adw.ColorScheme.DEFAULT)
    Adw.StyleManager.get_default().set_color_scheme(scheme)


def _stylesheet_candidates() -> list[Path]:
    candidates = [Path(__file__).resolve().parents[2] / "data" / "style.css"]
    data_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    for root in data_dirs.split(":"):
        if root:
            candidates.append(Path(root) / APP_ID / "style.css")
    return candidates


def load_stylesheet() -> None:
    """Muat CSS lokal bila tersedia; aman saat tidak ada display."""

    display = Gdk.Display.get_default()
    if display is None:
        return
    path = next((item for item in _stylesheet_candidates() if item.is_file()), None)
    if path is None:
        return
    provider = Gtk.CssProvider()
    try:
        provider.load_from_path(str(path))
    except Exception:
        return
    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
