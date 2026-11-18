"""Dialog tambah dan ubah ibadah."""

from __future__ import annotations

from datetime import date
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from ..logic.repository import CategoryRecord, Repository, WorshipRecord
from ..logic.statistics import EntryKind

__all__ = ["WorshipDialog"]

DAY_LABELS = ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min")
KIND_LABELS = ("Centang", "Angka", "Status")
KINDS = (EntryKind.CHECK, EntryKind.NUMBER, EntryKind.STATUS)


class WorshipDialog(Adw.Dialog):
    """Form satu ibadah; dipakai untuk tambah maupun ubah."""

    def __init__(
        self,
        repository: Repository,
        categories: tuple[CategoryRecord, ...],
        *,
        worship: WorshipRecord | None = None,
        on_saved: Callable[[int], None],
    ) -> None:
        super().__init__()
        self._repo = repository
        self._worship = worship
        self._on_saved = on_saved
        self._categories = categories
        self._category_ids = [None, *(category.id for category in categories)]

        self.set_title("Ubah ibadah" if worship is not None else "Ibadah baru")
        self.set_content_width(480)

        group = Adw.PreferencesGroup()
        group.set_title("Detail ibadah")

        self._name_row = Adw.EntryRow(title="Nama")
        group.add(self._name_row)

        category_labels = ["Tanpa kategori", *(category.name for category in categories)]
        self._category_row = Adw.ComboRow(title="Kategori")
        self._category_row.set_model(Gtk.StringList.new(category_labels))
        group.add(self._category_row)

        self._kind_row = Adw.ComboRow(title="Tipe isian")
        self._kind_row.set_model(Gtk.StringList.new(list(KIND_LABELS)))
        self._kind_row.connect("notify::selected", self._on_kind_changed)
        group.add(self._kind_row)

        self._target_row = Adw.EntryRow(title="Target")
        self._target_row.set_input_purpose(Gtk.InputPurpose.NUMBER)
        group.add(self._target_row)

        self._unit_row = Adw.EntryRow(title="Satuan")
        group.add(self._unit_row)

        days_row = Adw.ActionRow(title="Hari aktif")
        days_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._day_buttons: list[Gtk.ToggleButton] = []
        for label in DAY_LABELS:
            button = Gtk.ToggleButton(label=label)
            button.set_tooltip_text(label)
            days_box.append(button)
            self._day_buttons.append(button)
        days_row.add_suffix(days_box)
        group.add(days_row)

        self._start_row = Adw.EntryRow(title="Mulai aktif (YYYY-MM-DD)")
        group.add(self._start_row)

        self._error = Gtk.Label(label="")
        self._error.add_css_class("dim-label")
        self._error.set_wrap(True)
        self._error.set_xalign(0)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.append(group)
        content.append(self._error)

        header = Adw.HeaderBar()
        cancel = Gtk.Button(label="Batal")
        cancel.connect("clicked", lambda *_: self.close())
        header.pack_start(cancel)
        save = Gtk.Button(label="Simpan")
        save.add_css_class("suggested-action")
        save.connect("clicked", self._on_save)
        header.pack_end(save)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(content)
        self.set_child(toolbar)
        self.set_default_widget(save)

        self._load(worship)

    # -- isi awal --------------------------------------------------------

    def _load(self, worship: WorshipRecord | None) -> None:
        if worship is None:
            self._name_row.set_text("")
            self._category_row.set_selected(0)
            self._kind_row.set_selected(0)
            self._target_row.set_text("")
            self._unit_row.set_text("")
            selected_days = set(range(7))
            self._start_row.set_text(date.today().isoformat())
        else:
            self._name_row.set_text(worship.name)
            try:
                category_index = self._category_ids.index(worship.category_id)
            except ValueError:
                category_index = 0
            self._category_row.set_selected(category_index)
            self._kind_row.set_selected(KINDS.index(worship.kind))
            self._target_row.set_text(
                "" if worship.target is None else f"{worship.target:g}"
            )
            self._unit_row.set_text(worship.unit)
            selected_days = set(worship.active_weekdays)
            self._start_row.set_text(
                worship.active_from.isoformat()
                if worship.active_from is not None
                else date.today().isoformat()
            )

        for index, button in enumerate(self._day_buttons):
            button.set_active(index in selected_days)
        self._on_kind_changed()

    def _on_kind_changed(self, *_args: object) -> None:
        is_number = KINDS[self._kind_row.get_selected()] is EntryKind.NUMBER
        self._target_row.set_visible(is_number)
        self._unit_row.set_visible(is_number)

    # -- simpan ----------------------------------------------------------

    def _on_save(self, _button: Gtk.Button) -> None:
        name = self._name_row.get_text().strip()
        if not name:
            self._show_error("Nama ibadah tidak boleh kosong")
            return

        kind = KINDS[self._kind_row.get_selected()]
        target: float | None = None
        if kind is EntryKind.NUMBER:
            text = self._target_row.get_text().strip()
            if text:
                try:
                    target = float(text)
                except ValueError:
                    self._show_error("Target harus berupa angka")
                    return
                if target < 0:
                    self._show_error("Target tidak boleh negatif")
                    return

        try:
            active_from = date.fromisoformat(self._start_row.get_text().strip())
        except ValueError:
            self._show_error("Tanggal mulai harus berformat YYYY-MM-DD")
            return

        weekdays = frozenset(
            index for index, button in enumerate(self._day_buttons) if button.get_active()
        )
        if not weekdays:
            self._show_error("Pilih minimal satu hari aktif")
            return

        category_id = self._category_ids[self._category_row.get_selected()]
        values = dict(
            name=name,
            category_id=category_id,
            kind=kind,
            target=target,
            unit=self._unit_row.get_text(),
            active_weekdays=weekdays,
            active_from=active_from,
        )

        try:
            if self._worship is None:
                worship = self._repo.add_worship(**values)  # type: ignore[arg-type]
            else:
                worship = self._repo.update_worship(self._worship.id, **values)  # type: ignore[arg-type]
        except (ValueError, KeyError) as error:
            self._show_error(str(error))
            return

        self._on_saved(worship.id)
        self.close()

    def _show_error(self, message: str) -> None:
        self._error.set_label(message)
