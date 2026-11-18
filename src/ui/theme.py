"""Tema dan stylesheet IslamicHabits.

Modul ini berada di lapisan antarmuka karena memakai GTK/Adw. Logika tetap
bebas dari pustaka grafis.

Palet sage disimpan dalam dua berkas: ``style.css`` memuat aturan dan warna
terang, sedangkan ``style-dark.css`` hanya mengganti definisi warna ketika
skema gelap aktif. Dengan begitu kontras tetap terjaga di kedua tema tanpa
menggandakan aturan kelas.
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

# Tema GTK milik pengguna (mis. Graphite) dimuat GTK pada prioritas USER dan
# sering menulis warna literal seperti ``.background { background-color: ... }``.
# Tanpa berada di atasnya, palet sage aplikasi kalah dan jendela bisa tetap
# gelap meski skema "Terang" dipilih. Palet aplikasi sengaja didahulukan agar
# warna dan kontras konsisten; pilihan terang/gelap tetap mengikuti StyleManager.
_PROVIDER_PRIORITY = Gtk.STYLE_PROVIDER_PRIORITY_USER + 1

_current_theme = THEME_KEYS[0]
_display: Gdk.Display | None = None
_base_provider: Gtk.CssProvider | None = None
_dark_provider: Gtk.CssProvider | None = None
_style_signal_connected = False


def apply_theme(theme: str) -> None:
    """Terapkan pilihan tema ke style manager dan palet stylesheet."""

    global _current_theme
    _current_theme = theme if theme in THEME_KEYS else THEME_KEYS[0]
    Adw.StyleManager.get_default().set_color_scheme(
        _COLOR_SCHEMES[_current_theme]
    )
    _update_dark_provider()


def _stylesheet_path(filename: str) -> Path | None:
    candidates = [Path(__file__).resolve().parents[2] / "data" / filename]
    data_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    for root in data_dirs.split(":"):
        if root:
            candidates.append(Path(root) / APP_ID / filename)
    return next((item for item in candidates if item.is_file()), None)


def _remove_providers() -> None:
    global _display, _base_provider, _dark_provider
    if _display is not None:
        for provider in (_base_provider, _dark_provider):
            if provider is not None:
                Gtk.StyleContext.remove_provider_for_display(_display, provider)
    _display = None
    _base_provider = None
    _dark_provider = None


def _is_dark_theme() -> bool:
    if _current_theme == "gelap":
        return True
    if _current_theme == "terang":
        return False
    return bool(Adw.StyleManager.get_default().get_dark())


def _on_style_changed(*_args: object) -> None:
    """Ikuti perubahan skema sistem ketika pilihan tema adalah 'sistem'."""

    _update_dark_provider()


def _connect_style_signal() -> None:
    global _style_signal_connected
    if _style_signal_connected:
        return
    Adw.StyleManager.get_default().connect("notify::dark", _on_style_changed)
    _style_signal_connected = True


def _update_dark_provider() -> None:
    global _dark_provider
    if _display is None or _base_provider is None:
        return
    if _dark_provider is not None:
        Gtk.StyleContext.remove_provider_for_display(_display, _dark_provider)
        _dark_provider = None
    if not _is_dark_theme():
        return
    path = _stylesheet_path("style-dark.css")
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
    _dark_provider = provider


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
    _connect_style_signal()
    _update_dark_provider()
