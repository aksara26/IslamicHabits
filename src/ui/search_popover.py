"""Pencarian global untuk memo, muhasabah, catatan ibadah, dan nama ibadah.

Sebelumnya tombol cari di header berpindah ke halaman Muhasabah, sehingga
pengguna yang ingin mencari memo malah dibawa ke halaman lain. Popover ini
mencari ke semua sumber sekaligus dan membuka halaman yang tepat pada tanggal
hasil yang dipilih.
"""

from __future__ import annotations

from datetime import date
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from ..logic.repository import Repository, SearchHit
from .a11y import set_accessible_label
from .history_common import BULAN

__all__ = ["SearchPopover"]

DayCallback = Callable[[date], None]
WorshipCallback = Callable[[int], None]

_KIND_TITLE = {
    "memo": "Memo harian",
    "muhasabah": "Muhasabah",
    "entry": "Catatan ibadah",
    "worship": "Ibadah & kebiasaan",
}
_KIND_ICON = {
    "memo": "text-x-generic-symbolic",
    "muhasabah": "document-edit-symbolic",
    "entry": "view-list-symbolic",
    "worship": "checkbox-checked-symbolic",
}


def _short_day(day: date) -> str:
    return f"{day.day} {BULAN[day.month - 1][:3]} {day.year}"


class SearchPopover(Gtk.Popover):
    """Popover pencarian yang hasilnya langsung membuka halaman tujuan."""

    def __init__(
        self,
        repository: Repository,
        *,
        on_open_memo: DayCallback,
        on_open_muhasabah: DayCallback,
        on_open_day: DayCallback,
        on_open_worship: WorshipCallback,
    ) -> None:
        super().__init__()
        self._repo = repository
        self._on_open_memo = on_open_memo
        self._on_open_muhasabah = on_open_muhasabah
        self._on_open_day = on_open_day
        self._on_open_worship = on_open_worship

        self.set_has_arrow(True)
        self.set_position(Gtk.PositionType.BOTTOM)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_size_request(520, -1)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)

        title = Gtk.Label(label="Cari semua catatan")
        title.set_xalign(0)
        title.add_css_class("ih-section-title")
        box.append(title)

        self._entry = Gtk.SearchEntry()
        self._entry.set_placeholder_text(
            "Cari memo, muhasabah, catatan ibadah, atau nama ibadah…"
        )
        self._entry.connect("search-changed", self._on_search_changed)
        box.append(self._entry)

        self._results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._scrolled.set_max_content_height(380)
        self._scrolled.set_propagate_natural_height(True)
        self._scrolled.set_child(self._results)
        box.append(self._scrolled)

        self._hint = Gtk.Label(
            label="Ketik minimal dua huruf untuk mulai mencari."
        )
        self._hint.set_xalign(0)
        self._hint.set_wrap(True)
        self._hint.add_css_class("ih-hint")
        box.append(self._hint)

        self.set_child(box)

    # -- pencarian -------------------------------------------------------

    def focus(self) -> None:
        """Fokuskan kolom pencarian; dipakai pintasan Ctrl+F."""

        self._entry.grab_focus()

    def _on_search_changed(self, *_args: object) -> None:
        query = self._entry.get_text().strip()
        child = self._results.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            self._results.remove(child)
            child = following

        if len(query) < 2:
            self._scrolled.set_visible(False)
            self._hint.set_label("Ketik minimal dua huruf untuk mulai mencari.")
            self._hint.set_visible(True)
            return

        hits = self._repo.search_all(query)
        if not hits:
            self._scrolled.set_visible(False)
            self._hint.set_label(f"Tidak ada hasil untuk “{query}”.")
            self._hint.set_visible(True)
            return

        self._hint.set_visible(False)
        self._scrolled.set_visible(True)
        current_kind: str | None = None
        group: Gtk.ListBox | None = None
        for hit in hits:
            if hit.kind != current_kind:
                current_kind = hit.kind
                heading = Gtk.Label(label=_KIND_TITLE.get(hit.kind, hit.kind))
                heading.set_xalign(0)
                heading.add_css_class("ih-hint")
                heading.set_margin_top(6)
                self._results.append(heading)

                # Adw.ActionRow hanya boleh berada di dalam Gtk.ListBox.
                group = Gtk.ListBox()
                group.add_css_class("boxed-list")
                group.set_selection_mode(Gtk.SelectionMode.NONE)
                self._results.append(group)
            assert group is not None
            group.append(self._build_row(hit))

    def _build_row(self, hit: SearchHit) -> Adw.ActionRow:
        row = Adw.ActionRow(title=hit.title, subtitle=hit.snippet or "—")
        icon = Gtk.Image.new_from_icon_name(_KIND_ICON.get(hit.kind, "go-next-symbolic"))
        row.add_prefix(icon)
        if hit.day is not None:
            day_label = Gtk.Label(label=_short_day(hit.day))
            day_label.add_css_class("ih-hint")
            row.add_suffix(day_label)
        row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        set_accessible_label(
            row,
            f"{hit.title}: {hit.snippet}. Tekan Enter untuk membuka.",
        )
        row.connect("activated", lambda *_: self._activate(hit))
        return row

    def _activate(self, hit: SearchHit) -> None:
        self.popdown()
        if hit.kind == "worship" and hit.worship_id is not None:
            self._on_open_worship(hit.worship_id)
            return
        if hit.day is None:
            return
        if hit.kind == "memo":
            self._on_open_memo(hit.day)
        elif hit.kind == "muhasabah":
            self._on_open_muhasabah(hit.day)
        else:
            self._on_open_day(hit.day)
