"""Tema dan stylesheet IslamicHabits.

Modul ini berada di lapisan antarmuka karena memakai GTK/Adw. Logika tetap
bebas dari pustaka grafis.

Ada tiga pilihan tema:

- ``hijau`` (default): palet sage dengan latar hijau lembut;
- ``putih``: latar netral terang dengan aksen sage;
- ``hitam``: latar netral gelap dengan aksen sage terang.

``style.css`` memuat aturan dan palet hijau. Dua berkas lain hanya mengganti
definisi warna ketika tema putih atau hitam dipilih. Area tulisan memakai
``ih-editor-bg`` yang sengaja berbeda dari latar aplikasi agar mudah dibedakan.
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

__all__ = [
    "THEME_KEYS",
    "THEME_LABELS",
    "apply_theme",
    "load_stylesheet",
    "normalize_theme",
]

THEME_KEYS = ("hijau", "putih", "hitam")
THEME_LABELS = ("Hijau (default)", "Putih", "Hitam")

# Nilai lama tetap dibaca supaya basis data dan berkas ekspor lama tidak
# kehilangan pilihan tema pengguna.
_LEGACY_THEMES = {
    "sistem": "hijau",
    "terang": "hijau",
    "gelap": "hitam",
}

_COLOR_SCHEMES = {
    "hijau": Adw.ColorScheme.FORCE_LIGHT,
    "putih": Adw.ColorScheme.FORCE_LIGHT,
    "hitam": Adw.ColorScheme.FORCE_DARK,
}

_PALETTE_FILES = {
    "hijau": None,
    "putih": "style-putih.css",
    "hitam": "style-hitam.css",
}

# Tema GTK milik pengguna (mis. Graphite) dimuat GTK pada prioritas USER dan
# sering menulis warna literal seperti ``.background { background-color: ... }``.
# Tanpa berada di atasnya, palet aplikasi kalah dan jendela bisa tetap gelap
# meski tema terang dipilih. Palet aplikasi sengaja didahulukan agar warna dan
# kontras konsisten; skema terang/gelap tetap diatur lewat StyleManager.
_PROVIDER_PRIORITY = Gtk.STYLE_PROVIDER_PRIORITY_USER + 1

_current_theme = THEME_KEYS[0]
_display: Gdk.Display | None = None
_base_provider: Gtk.CssProvider | None = None
_palette_provider: Gtk.CssProvider | None = None


def normalize_theme(theme: str | None) -> str:
    """Kembalikan kunci tema yang dikenal, termasuk konversi nilai lama."""

    if theme in THEME_KEYS:
        return str(theme)
    return _LEGACY_THEMES.get(theme or "", THEME_KEYS[0])


def apply_theme(theme: str) -> str:
    """Terapkan pilihan tema dan kembalikan kunci yang sudah dinormalkan."""

    global _current_theme
    _current_theme = normalize_theme(theme)
    Adw.StyleManager.get_default().set_color_scheme(
        _COLOR_SCHEMES[_current_theme]
    )
    _update_palette()
    return _current_theme


def _stylesheet_path(filename: str) -> Path | None:
    candidates = [Path(__file__).resolve().parents[2] / "data" / filename]

    # XDG_DATA_HOME (biasanya ~/.local/share) tidak termasuk XDG_DATA_DIRS,
    # padahal di situlah instalasi --user menaruh stylesheet.
    data_home = os.environ.get("XDG_DATA_HOME")
    user_data = Path(data_home) if data_home else Path.home() / ".local" / "share"
    candidates.append(user_data / APP_ID / filename)
    candidates.append(Path.home() / ".local" / "share" / APP_ID / filename)

    data_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    for root in data_dirs.split(":"):
        if root:
            candidates.append(Path(root) / APP_ID / filename)
    return next((item for item in candidates if item.is_file()), None)


def _remove_providers() -> None:
    global _display, _base_provider, _palette_provider
    if _display is not None:
        for provider in (_base_provider, _palette_provider):
            if provider is not None:
                Gtk.StyleContext.remove_provider_for_display(_display, provider)
    _display = None
    _base_provider = None
    _palette_provider = None


def _update_palette() -> None:
    """Ganti berkas palet di atas stylesheet dasar sesuai tema aktif."""

    global _palette_provider
    if _display is None or _base_provider is None:
        return
    if _palette_provider is not None:
        Gtk.StyleContext.remove_provider_for_display(_display, _palette_provider)
        _palette_provider = None

    filename = _PALETTE_FILES[_current_theme]
    if filename is None:
        return
    path = _stylesheet_path(filename)
    if path is None:
        return
    provider = Gtk.CssProvider()
    try:
        provider.load_from_path(str(path))
    except Exception:
        return
    Gtk.StyleContext.add_provider_for_display(
        _display,
        provider,
        _PROVIDER_PRIORITY + 1,
    )
    _palette_provider = provider


def load_stylesheet() -> None:
    """Muat CSS lokal bila tersedia; aman saat tidak ada display."""

    global _display, _base_provider
    _remove_providers()

    display = Gdk.Display.get_default()
    if display is None:
        return
    path = _stylesheet_path("style.css")
    if path is None:
        return

    provider = Gtk.CssProvider()
    try:
        provider.load_from_path(str(path))
    except Exception:
        return
    Gtk.StyleContext.add_provider_for_display(
        display, provider, _PROVIDER_PRIORITY
    )
    _display = display
    _base_provider = provider
    _update_palette()
