"""Navigasi tanggal bersama untuk Hari Ini, Memo, dan Muhasabah.

Satu komponen dipakai di semua halaman bertanggal supaya posisi tombol,
pintasan, dan cara melompat ke tanggal jauh selalu sama. Label tanggal juga
membuka kalender kecil, sehingga pengguna tidak perlu menekan panah puluhan
kali untuk kembali ke bulan lalu.
"""

from __future__ import annotations

from datetime import date
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib, Gtk

from .a11y import set_accessible_label
from .history_common import format_day

__all__ = ["DateNavigator"]

DayCallback = Callable[[date], None]


class DateNavigator(Gtk.Box):
    """Baris ``‹ tanggal ▾ › Hari ini`` dengan kalender popover."""

    def __init__(
        self,
        *,
        on_previous: Callable[[], None],
        on_next: Callable[[], None],
        on_today: Callable[[], None],
        on_pick: DayCallback,
        margin: int = 18,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._on_pick = on_pick
        self._day = date.today()
        self._syncing = False

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.set_margin_start(margin)
        row.set_margin_end(margin)
        row.set_margin_top(12)

        previous = Gtk.Button.new_from_icon_name("go-previous-symbolic")
        previous.set_tooltip_text("Hari sebelumnya (Ctrl+←)")
        set_accessible_label(previous, "Hari sebelumnya")
        previous.connect("clicked", lambda *_: on_previous())
        row.append(previous)

        self._date_button = Gtk.Button()
        self._date_button.add_css_class("flat")
        self._date_button.add_css_class("ih-date-button")
        self._date_button.set_hexpand(True)
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        content.set_halign(Gtk.Align.CENTER)
        self._date_label = Gtk.Label(label="")
        self._date_label.add_css_class("ih-page-date")
        content.append(self._date_label)
        content.append(Gtk.Image.new_from_icon_name("pan-down-symbolic"))
        self._date_button.set_child(content)
        self._date_button.connect("clicked", self._on_date_clicked)
        row.append(self._date_button)

        following = Gtk.Button.new_from_icon_name("go-next-symbolic")
        following.set_tooltip_text("Hari berikutnya (Ctrl+→)")
        set_accessible_label(following, "Hari berikutnya")
        following.connect("clicked", lambda *_: on_next())
        row.append(following)

        today = Gtk.Button(label="Hari ini")
        today.add_css_class("ih-quick")
        today.set_tooltip_text("Kembali ke hari ini (Ctrl+T)")
        set_accessible_label(today, "Kembali ke hari ini")
        today.connect("clicked", lambda *_: on_today())
        row.append(today)

        self.append(row)

        self._context_label = Gtk.Label(label="")
        self._context_label.set_xalign(0.5)
        self._context_label.add_css_class("ih-hint")
        self._context_label.set_visible(False)
        self.append(self._context_label)

        self._popover = Gtk.Popover()
        self._popover.set_parent(self._date_button)
        self._popover.set_position(Gtk.PositionType.BOTTOM)
        self._calendar = Gtk.Calendar()
        self._calendar.connect("day-selected", self._on_calendar_day)
        self._popover.set_child(self._calendar)

    # -- API -------------------------------------------------------------

    def set_day(self, day: date, *, context: str = "") -> None:
        """Perbarui label tanggal dan keterangan konteks di bawahnya."""

        self._day = day
        label = format_day(day)
        self._date_label.set_label(label)
        self._date_button.set_tooltip_text(f"Pilih tanggal — {label}")
        set_accessible_label(self._date_button, f"Pilih tanggal, sekarang {label}")
        self._context_label.set_label(context)
        self._context_label.set_visible(bool(context))

    # -- kalender --------------------------------------------------------

    def _on_date_clicked(self, _button: Gtk.Button) -> None:
        self._syncing = True
        try:
            self._calendar.select_day(
                GLib.DateTime.new_local(
                    self._day.year, self._day.month, self._day.day, 0, 0, 0
                )
            )
        finally:
            self._syncing = False
        self._popover.popup()

    def _on_calendar_day(self, _calendar: Gtk.Calendar) -> None:
        if self._syncing:
            return
        value = self._calendar.get_date()
        day = date(value.get_year(), value.get_month(), value.get_day_of_month())
        self._popover.popdown()
        if day != self._day:
            self._on_pick(day)

    def do_dispose(self) -> None:
        self._popover.unparent()
        Gtk.Box.do_dispose(self)
