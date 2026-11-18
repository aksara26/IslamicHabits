"""Halaman Kelola Ibadah: tambah, ubah, urutkan, arsipkan, pulihkan."""

from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from ..logic.repository import Repository, WorshipRecord
from ..logic.statistics import EntryKind
from .a11y import set_accessible_label

__all__ = ["ManagePage"]

AddWorshipCallback = Callable[[int | None], None]
ToastCallback = Callable[[str, str | None, Callable[[], None] | None], None]
DataChangedCallback = Callable[[], None]


class ManagePage(Gtk.Box):
    """Daftar semua ibadah dengan aksi pengelolaan yang jelas."""

    def __init__(
        self,
        repository: Repository,
        *,
        on_add_worship: AddWorshipCallback,
        on_toast: ToastCallback,
        on_data_changed: DataChangedCallback,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._repo = repository
        self._on_add_worship = on_add_worship
        self._on_toast = on_toast
        self._on_data_changed = on_data_changed
        self._show_archived = False

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header_box.set_margin_start(18)
        header_box.set_margin_end(18)
        header_box.set_margin_top(12)
        label = Gtk.Label(label="Atur ibadah yang tampil di Hari Ini.")
        label.set_xalign(0)
        label.set_hexpand(True)
        header_box.append(label)

        archive_toggle = Gtk.CheckButton(label="Tampilkan arsip")
        archive_toggle.connect("toggled", self._on_archive_toggled)
        header_box.append(archive_toggle)
        self.append(header_box)

        add_button = Gtk.Button(label="Tambah ibadah")
        add_button.add_css_class("suggested-action")
        add_button.set_halign(Gtk.Align.START)
        add_button.set_margin_start(18)
        add_button.set_margin_top(6)
        add_button.connect("clicked", lambda *_: self._on_add_worship(None))
        self.append(add_button)

        self._scrolled = Gtk.ScrolledWindow(vexpand=True)
        self._scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(self._scrolled)
        self.refresh()

    def _on_archive_toggled(self, button: Gtk.CheckButton) -> None:
        self._show_archived = button.get_active()
        self.refresh()

    # -- daftar ----------------------------------------------------------

    def refresh(self) -> None:
        worships = self._repo.list_worships(include_archived=self._show_archived)
        if not worships:
            empty = Adw.StatusPage(
                title="Belum ada ibadah" if not self._show_archived else "Arsip kosong",
                description=(
                    "Tambahkan ibadah pertama Anda."
                    if not self._show_archived
                    else "Belum ada ibadah yang diarsipkan."
                ),
                icon_name="view-list-symbolic",
            )
            self._scrolled.set_child(empty)
            return

        group = Adw.PreferencesGroup()
        group.set_title("Ibadah" if not self._show_archived else "Arsip ibadah")
        active_ids = [item.id for item in self._repo.list_worships()]
        for worship in worships:
            group.add(self._create_row(worship, active_ids))
        self._scrolled.set_child(group)

    def _create_row(self, worship: WorshipRecord, active_ids: list[int]) -> Adw.ActionRow:
        row = Adw.ActionRow(title=worship.name)
        row.set_subtitle(self._subtitle(worship))

        if worship.archived_on is None:
            index = active_ids.index(worship.id)
            if index > 0:
                row.add_suffix(
                    self._icon_button(
                        "go-up-symbolic",
                        f"Naikkan {worship.name}",
                        lambda *_: self._move(worship.id, -1),
                    )
                )
            if index < len(active_ids) - 1:
                row.add_suffix(
                    self._icon_button(
                        "go-down-symbolic",
                        f"Turunkan {worship.name}",
                        lambda *_: self._move(worship.id, 1),
                    )
                )

        row.add_suffix(
            self._icon_button(
                "edit-symbolic",
                f"Ubah {worship.name}",
                lambda *_: self._on_add_worship(worship.id),
            )
        )

        if worship.archived_on is None:
            row.add_suffix(
                self._icon_button(
                    "view-reveal-symbolic",
                    f"Arsipkan {worship.name}",
                    lambda *_: self._archive(worship),
                )
            )
        else:
            row.add_suffix(
                self._icon_button(
                    "edit-undo-symbolic",
                    f"Pulihkan {worship.name}",
                    lambda *_: self._restore(worship),
                )
            )

        row.add_suffix(
            self._icon_button(
                "user-trash-symbolic",
                f"Hapus permanen {worship.name}",
                lambda *_: self._confirm_delete(worship),
            )
        )
        return row

    @staticmethod
    def _icon_button(icon: str, label: str, callback: Callable) -> Gtk.Button:
        button = Gtk.Button.new_from_icon_name(icon)
        button.set_tooltip_text(label)
        set_accessible_label(button, label)
        button.get_style_context().add_class("flat")
        button.connect("clicked", callback)
        return button

    @staticmethod
    def _subtitle(worship: WorshipRecord) -> str:
        kind = {
            EntryKind.CHECK: "Centang",
            EntryKind.NUMBER: "Angka",
            EntryKind.STATUS: "Status",
        }[worship.kind]
        parts = [worship.category_name or "Tanpa kategori", kind]
        if worship.kind is EntryKind.NUMBER and worship.target:
            amount = f"{worship.target:g}"
            if worship.unit:
                amount += f" {worship.unit}"
            parts.append(f"target {amount}")
        if len(worship.active_weekdays) < 7:
            parts.append(f"{len(worship.active_weekdays)} hari/minggu")
        if worship.archived_on is not None:
            parts.append(f"diarsipkan {worship.archived_on.isoformat()}")
        return " · ".join(parts)

    # -- aksi ------------------------------------------------------------

    def _move(self, worship_id: int, direction: int) -> None:
        ids = [item.id for item in self._repo.list_worships()]
        index = ids.index(worship_id)
        target = index + direction
        if target < 0 or target >= len(ids):
            return
        ids[index], ids[target] = ids[target], ids[index]
        self._repo.reorder_worships(ids)
        self.refresh()
        self._on_data_changed()

    def _archive(self, worship: WorshipRecord) -> None:
        self._repo.archive_worship(worship.id)
        self.refresh()
        self._on_data_changed()
        self._on_toast(
            f"{worship.name} diarsipkan",
            "Urungkan",
            self._undo_archive(worship.id),
        )

    def _undo_archive(self, worship_id: int) -> Callable[[], None]:
        def restore() -> None:
            self._repo.restore_worship(worship_id)
            self.refresh()
            self._on_data_changed()

        return restore

    def _restore(self, worship: WorshipRecord) -> None:
        self._repo.restore_worship(worship.id)
        self.refresh()
        self._on_data_changed()
        self._on_toast(f"{worship.name} dipulihkan", None, None)

    def _confirm_delete(self, worship: WorshipRecord) -> None:
        dialog = Adw.AlertDialog(
            heading="Hapus permanen?",
            body=(
                f"Riwayat {worship.name} akan ikut hilang dan tidak bisa dikembalikan. "
                "Arsipkan saja bila ingin menyimpannya."
            ),
        )
        dialog.add_response("cancel", "Batal")
        dialog.add_response("delete", "Hapus permanen")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_delete_response, worship)
        dialog.present(self)

    def _on_delete_response(
        self,
        _dialog: Adw.AlertDialog,
        response: str,
        worship: WorshipRecord,
    ) -> None:
        if response != "delete":
            return
        self._repo.delete_worship(worship.id)
        self.refresh()
        self._on_data_changed()
        self._on_toast(f"{worship.name} dihapus permanen", None, None)
