"""Dialog tambah dan ubah ibadah atau kebiasaan.

Kebiasaan memakai tabel yang sama dengan ibadah. Perbedaannya hanya pada
kategori ``Kebiasaan``, preset yang disiapkan, dan kata yang dipakai di form.
Dengan begitu satu catatan per item per tanggal dan aturan statistik tetap
sama untuk keduanya.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Callable, NamedTuple

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from ..logic.defaults import HABIT_CATEGORY
from ..logic.repository import CategoryRecord, Repository, WorshipRecord
from ..logic.statistics import EntryKind

__all__ = ["WorshipDialog"]

DAY_LABELS = ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min")
KIND_LABELS = ("Centang", "Angka", "Status")
KINDS = (EntryKind.CHECK, EntryKind.NUMBER, EntryKind.STATUS)


class HabitPreset(NamedTuple):
    name: str
    label: str
    kind: EntryKind
    target: float | None = None
    unit: str = ""


HABIT_PRESETS: tuple[HabitPreset, ...] = (
    HabitPreset("Belajar", "Belajar · 30 menit", EntryKind.NUMBER, 30, "menit"),
    HabitPreset(
        "Baca buku", "Baca buku · 10 halaman", EntryKind.NUMBER, 10, "halaman"
    ),
    HabitPreset("Olahraga", "Olahraga · centang", EntryKind.CHECK),
    HabitPreset("Jalan kaki", "Jalan kaki · 20 menit", EntryKind.NUMBER, 20, "menit"),
    HabitPreset("Tidur awal", "Tidur awal · centang", EntryKind.CHECK),
)

CUSTOM_LABEL = "Kustom"
CUSTOM_INDEX = len(HABIT_PRESETS)


class WorshipDialog(Adw.Dialog):
    """Form satu kegiatan; dipakai untuk tambah maupun ubah."""

    def __init__(
        self,
        repository: Repository,
        categories: tuple[CategoryRecord, ...],
        *,
        worship: WorshipRecord | None = None,
        habit: bool = False,
        on_saved: Callable[[int], None],
    ) -> None:
        super().__init__()
        self._repo = repository
        self._worship = worship
        self._on_saved = on_saved
        self._habit = habit or (
            worship is not None and worship.category_name == HABIT_CATEGORY
        )
        self._loading = True

        available = list(categories)
        if self._habit and not any(item.name == HABIT_CATEGORY for item in available):
            try:
                available.append(repository.add_category(HABIT_CATEGORY))
            except (ValueError, sqlite3.Error):
                pass
        self._categories = tuple(available)
        self._category_ids = [None, *(category.id for category in available)]

        noun = "kebiasaan" if self._habit else "ibadah"
        heading = "Kebiasaan" if self._habit else "Ibadah"
        prefix = "Ubah " if worship is not None else ""
        suffix = "" if worship is not None else " baru"
        self.set_title(f"{prefix}{heading}{suffix}")
        self.set_content_width(480)

        group = Adw.PreferencesGroup()
        group.set_title("Detail " + noun)
        group.set_description(
            "Kebiasaan ikut dihitung di statistik harian, bulanan, dan tahunan."
            if self._habit
            else "Satu ibadah cukup satu catatan per hari."
        )

        if self._habit:
            self._preset_row = Adw.ComboRow(
                title="Contoh kebiasaan",
                subtitle="Pilih lalu ubah sesuai kebutuhan Anda",
            )
            labels = [*(preset.label for preset in HABIT_PRESETS), CUSTOM_LABEL]
            self._preset_row.set_model(Gtk.StringList.new(labels))
            self._preset_row.connect("notify::selected", self._on_preset_changed)
            group.add(self._preset_row)
        else:
            self._preset_row = None

        self._name_row = Adw.EntryRow(title="Nama " + noun)
        group.add(self._name_row)

        category_labels = [
            "Tanpa kategori",
            *(category.name for category in self._categories),
        ]
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
        self._error.add_css_class("ih-hint")
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
        self._loading = False

    # -- isi awal --------------------------------------------------------

    def _habit_category_index(self) -> int:
        for index, category_id in enumerate(self._category_ids):
            if category_id is None:
                continue
            category = next(
                (item for item in self._categories if item.id == category_id), None
            )
            if category is not None and category.name == HABIT_CATEGORY:
                return index
        return 0

    @staticmethod
    def _match_preset(worship: WorshipRecord | None) -> int:
        if worship is None:
            return 0
        for index, preset in enumerate(HABIT_PRESETS):
            if preset.name.casefold() == worship.name.strip().casefold():
                return index
        return CUSTOM_INDEX

    def _apply_preset(self, index: int) -> None:
        if not 0 <= index < len(HABIT_PRESETS):
            return
        preset = HABIT_PRESETS[index]
        self._name_row.set_text(preset.name)
        self._category_row.set_selected(self._habit_category_index())
        self._kind_row.set_selected(KINDS.index(preset.kind))
        self._target_row.set_text(
            "" if preset.target is None else f"{preset.target:g}"
        )
        self._unit_row.set_text(preset.unit)
        for button in self._day_buttons:
            button.set_active(True)
        self._start_row.set_text(date.today().isoformat())

    def _load(self, worship: WorshipRecord | None) -> None:
        if self._habit:
            preset_index = self._match_preset(worship)
            self._preset_row.set_selected(preset_index)
            self._apply_preset(preset_index)

        if worship is None:
            if not self._habit:
                self._name_row.set_text("")
                self._category_row.set_selected(0)
                self._kind_row.set_selected(0)
                self._target_row.set_text("")
                self._unit_row.set_text("")
                for button in self._day_buttons:
                    button.set_active(True)
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
            for index, button in enumerate(self._day_buttons):
                button.set_active(index in worship.active_weekdays)
            self._start_row.set_text(
                worship.active_from.isoformat()
                if worship.active_from is not None
                else date.today().isoformat()
            )

        self._on_kind_changed()

    def _on_preset_changed(self, *_args: object) -> None:
        if self._loading or self._preset_row is None:
            return
        self._apply_preset(self._preset_row.get_selected())

    def _on_kind_changed(self, *_args: object) -> None:
        is_number = KINDS[self._kind_row.get_selected()] is EntryKind.NUMBER
        self._target_row.set_visible(is_number)
        self._unit_row.set_visible(is_number)

    # -- simpan ----------------------------------------------------------

    def _on_save(self, _button: Gtk.Button) -> None:
        noun = "kebiasaan" if self._habit else "ibadah"
        name = self._name_row.get_text().strip()
        if not name:
            self._show_error(f"Nama {noun} tidak boleh kosong")
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
