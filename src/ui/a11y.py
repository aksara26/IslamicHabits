"""Pembantu aksesibilitas bersama untuk widget IslamicHabits.

GTK4 memakai ``Gtk.Accessible.update_property`` untuk memberi label yang
terbaca pembaca layar. Pembungkus ini menjaga pemanggil tetap ringkas dan
aman bila AT-SPI tidak tersedia di sesi tanpa aksesibilitas.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

__all__ = ["set_accessible_label"]


def set_accessible_label(widget: Gtk.Widget, text: str) -> None:
    """Pasang label aksesibel pada sebuah widget."""

    try:
        Gtk.Accessible.update_property(
            widget, [Gtk.AccessibleProperty.LABEL], [text]
        )
    except Exception:
        pass
