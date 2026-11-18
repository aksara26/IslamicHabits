"""Satu baris ibadah di halaman Hari Ini.

Tiga varian mengikuti tipe isian: centang, angka, dan status. Tombol detail
selalu terlihat supaya aksi penting tidak hanya ada di balik kursor.
"""

from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from ..logic.repository import EntryRecord, EntryValue, WorshipRecord
from ..logic.statistics import EntryKind, StatusValue

__all__ = ["WorshipRow"]

ValueChanged = Callable[[int, EntryValue], None]
DetailsRequested = Callable[[WorshipRecord], None]


def _set_accessible_label(widget: Gtk.Widget, text: str) -> None:
    """GTK4 memakai properti aksesibel, bukan set_accessible_name."""

    try:
        Gtk.Accessible.update_property(
            widget, [Gtk.AccessibleProperty.LABEL], [text]
        )
    except Exception:
        pass


class WorshipRow(Adw.ActionRow):
    """Baris ibadah yang menulis perubahan lewat callback."""

    def __init__(
        self,
        worship: WorshipRecord,
        entry: EntryRecord | None,
        *,
        on_value_changed: ValueChanged,
        on_details: DetailsRequested,
    ) -> None:
        super().__init__()
        self.worship = worship
        self.entry = entry
        self._on_value_changed = on_value_changed
        self._on_details = on_details
        self._updating = False

        self.set_title(worship.name)
        self.set_subtitle(self._subtitle(entry))

        self._build_value_widget(entry)

        detail_button = Gtk.Button.new_from_icon_name("document-edit-symbolic")
        detail_button.set_tooltip_text("Detail, jam, dan catatan")
        _set_accessible_label(detail_button, f"Detail {worship.name}")
        detail_button.add_css_class("flat")
        detail_button.connect("clicked", self._on_detail_clicked)
        self.add_suffix(detail_button)

    # -- konstruksi ------------------------------------------------------

    def _build_value_widget(self, entry: EntryRecord | None) -> None:
        kind = self.worship.kind
        value = None if entry is None else entry.value

        if kind is EntryKind.CHECK:
            check = Gtk.CheckButton()
            check.set_active(bool(value))
            check.set_tooltip_text("Tandai selesai")
            _set_accessible_label(check, f"Selesai: {self.worship.name}")
            check.connect("toggled", self._on_check_toggled)
            self._value_widget = check
            self.add_suffix(check)
            return

        if kind is EntryKind.NUMBER:
            spin = Gtk.SpinButton.new_with_range(0, 9999, 1)
            spin.set_value(float(value) if isinstance(value, (int, float)) else 0.0)
            spin.set_numeric(True)
            spin.set_tooltip_text("Jumlah untuk hari ini")
            _set_accessible_label(spin, f"Jumlah {self.worship.name}")
            spin.connect("value-changed", self._on_number_changed)
            self._value_widget = spin
            self.add_suffix(spin)
            return

        labels = [status.value for status in StatusValue]
        dropdown = Gtk.DropDown.new_from_strings(labels)
        selected = 0
        if isinstance(value, StatusValue):
            selected = labels.index(value.value)
        elif isinstance(value, str) and value in labels:
            selected = labels.index(value)
        dropdown.set_selected(selected)
        dropdown.set_tooltip_text("Status pelaksanaan")
        _set_accessible_label(dropdown, f"Status {self.worship.name}")
        dropdown.connect("notify::selected", self._on_status_changed)
        self._value_widget = dropdown
        self.add_suffix(dropdown)

    def _subtitle(self, entry: EntryRecord | None) -> str:
        parts: list[str] = []
        if self.worship.kind is EntryKind.NUMBER:
            target = self.worship.target
            if target and target > 0:
                amount = f"{target:g}"
                if self.worship.unit:
                    amount += f" {self.worship.unit}"
                parts.append(f"Target {amount}")
            else:
                parts.append("Angka")
        elif self.worship.kind is EntryKind.STATUS:
            parts.append("Pilih status")
        else:
            parts.append("Centang")

        if entry is not None and entry.time:
            parts.append(entry.time)
        if entry is not None and entry.note:
            parts.append(entry.note)
        return " · ".join(parts)

    # -- callback --------------------------------------------------------

    def _on_check_toggled(self, button: Gtk.CheckButton) -> None:
        if self._updating:
            return
        # Membatalkan centang mengembalikan ke "kosong", bukan catatan False.
        self._on_value_changed(
            self.worship.id, True if button.get_active() else None
        )

    def _on_number_changed(self, spin: Gtk.SpinButton) -> None:
        if self._updating:
            return
        amount = spin.get_value()
        value: EntryValue = int(amount) if amount.is_integer() else amount
        self._on_value_changed(self.worship.id, value)

    def _on_status_changed(self, dropdown: Gtk.DropDown, _param: object) -> None:
        if self._updating:
            return
        index = dropdown.get_selected()
        labels = [status.value for status in StatusValue]
        if 0 <= index < len(labels):
            self._on_value_changed(self.worship.id, StatusValue(labels[index]))

    def _on_detail_clicked(self, _button: Gtk.Button) -> None:
        self._on_details(self.worship)

    # -- API -------------------------------------------------------------

    def focus_value(self) -> None:
        """Kembalikan fokus ke widget isian utama baris ini."""

        self._value_widget.grab_focus()

    def refresh(self, entry: EntryRecord | None) -> None:
        """Sinkronkan widget setelah data ditulis ulang dari luar."""

        self.entry = entry
        self._updating = True
        value = None if entry is None else entry.value
        widget = self._value_widget
        if isinstance(widget, Gtk.CheckButton):
            widget.set_active(bool(value))
        elif isinstance(widget, Gtk.SpinButton):
            widget.set_value(float(value) if isinstance(value, (int, float)) else 0.0)
        elif isinstance(widget, Gtk.DropDown):
            labels = [status.value for status in StatusValue]
            raw = value.value if isinstance(value, StatusValue) else value
            index = labels.index(raw) if raw in labels else 0
            widget.set_selected(index)
        self.set_subtitle(self._subtitle(entry))
        self._updating = False
