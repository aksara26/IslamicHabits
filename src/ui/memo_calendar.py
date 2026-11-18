"""Dialog kalender Memo: checklist, memo, dan pengingat per tanggal.

Kalender ini dibuka dari halaman Memo dan tidak menggantikan editor. Satu
tanggal bisa dilihat lengkap tanpa berpindah halaman: kegiatan yang
dicentang, pratinjau memo, dan pengingat dengan jam yang terpisah dari memo.
Pengingat boleh dibuat untuk tanggal lampau, hari ini, maupun masa depan.
"""

from __future__ import annotations

from datetime import date
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from ..logic.repository import Repository
from ..logic.statistics import compute_daily, describe_daily_completion
from .a11y import set_accessible_label
from .history_common import (
    BULAN,
    HARI_SINGKAT,
    clear_grid,
    clear_list,
    format_day,
    format_entry_detail,
    month_range,
    shift_month,
)

__all__ = ["MemoCalendarDialog"]

OpenDayCallback = Callable[[date], None]
ChangedCallback = Callable[[], None]


class MemoCalendarDialog(Adw.Dialog):
    """Kalender bulan dengan panel detail tanggal terpilih."""

    def __init__(
        self,
        repository: Repository,
        *,
        current_day: date,
        on_open: OpenDayCallback,
        on_changed: ChangedCallback | None = None,
    ) -> None:
        super().__init__()
        self._repo = repository
        self._on_open = on_open
        self._on_changed = on_changed
        self._selected = current_day
        self._anchor = date(current_day.year, current_day.month, 1)

        self.set_title("Kalender Memo")
        self.set_content_width(940)
        self.set_content_height(640)

        header = Adw.HeaderBar()
        close = Gtk.Button(label="Tutup")
        close.connect("clicked", lambda *_: self.close())
        header.pack_start(close)
        header.set_title_widget(
            Adw.WindowTitle(
                title="Kalender Memo",
                subtitle="Checklist, memo, dan pengingat per tanggal",
            )
        )

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(self._build_content())
        self.set_child(toolbar)

        self._refresh()

    # -- konstruksi ------------------------------------------------------

    def _build_content(self) -> Gtk.Widget:
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        paned.set_position(500)
        paned.set_resize_start_child(False)
        paned.set_resize_end_child(True)
        paned.set_shrink_start_child(True)
        paned.set_shrink_end_child(True)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        left.set_margin_start(18)
        left.set_margin_end(12)
        left.set_margin_top(12)
        left.set_margin_bottom(18)

        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        previous = Gtk.Button.new_from_icon_name("go-previous-symbolic")
        previous.set_tooltip_text("Bulan sebelumnya")
        set_accessible_label(previous, "Bulan sebelumnya")
        previous.connect("clicked", lambda *_: self._shift(-1))
        nav.append(previous)

        self._month_title = Gtk.Label(label="")
        self._month_title.set_hexpand(True)
        self._month_title.set_xalign(0.5)
        self._month_title.add_css_class("dim-label")
        nav.append(self._month_title)

        next_button = Gtk.Button.new_from_icon_name("go-next-symbolic")
        next_button.set_tooltip_text("Bulan berikutnya")
        set_accessible_label(next_button, "Bulan berikutnya")
        next_button.connect("clicked", lambda *_: self._shift(1))
        nav.append(next_button)

        current = Gtk.Button(label="Bulan ini")
        current.set_tooltip_text("Kembali ke bulan hari ini")
        current.connect("clicked", lambda *_: self.go_current())
        nav.append(current)
        left.append(nav)

        legend = Gtk.Label(
            label="✎ hari punya memo · ◷ hari punya pengingat"
        )
        legend.set_xalign(0)
        legend.set_wrap(True)
        legend.add_css_class("ih-hint")
        left.append(legend)

        self._month_grid = Gtk.Grid()
        self._month_grid.set_column_spacing(4)
        self._month_grid.set_row_spacing(4)
        self._month_grid.set_column_homogeneous(True)
        self._month_grid.set_halign(Gtk.Align.FILL)
        self._month_grid.add_css_class("ih-calendar-grid")
        left.append(self._month_grid)

        left_scrolled = Gtk.ScrolledWindow(vexpand=True)
        left_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        left_scrolled.set_min_content_width(300)
        left_scrolled.set_child(left)

        right = self._build_detail()
        right_scrolled = Gtk.ScrolledWindow(vexpand=True)
        right_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        right_scrolled.set_child(right)

        paned.set_start_child(left_scrolled)
        paned.set_end_child(right_scrolled)
        return paned

    def _build_detail(self) -> Gtk.Widget:
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        right.set_margin_start(12)
        right.set_margin_end(18)
        right.set_margin_top(12)
        right.set_margin_bottom(18)

        self._detail_title = Gtk.Label(label="")
        self._detail_title.set_xalign(0)
        self._detail_title.set_wrap(True)
        self._detail_title.add_css_class("ih-section-title")
        right.append(self._detail_title)

        self._detail_context = Gtk.Label(label="")
        self._detail_context.set_xalign(0)
        self._detail_context.set_wrap(True)
        self._detail_context.add_css_class("ih-hint")
        right.append(self._detail_context)

        # Checklist kegiatan pada tanggal terpilih.
        checklist_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        checklist_card.add_css_class("ih-card")
        checklist_header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=8
        )
        checklist_title = Gtk.Label(label="Checklist")
        checklist_title.set_xalign(0)
        checklist_title.set_hexpand(True)
        checklist_title.add_css_class("ih-section-title")
        self._checklist_summary = Gtk.Label(label="")
        self._checklist_summary.add_css_class("ih-hint")
        self._checklist_summary.set_valign(Gtk.Align.CENTER)
        checklist_header.append(checklist_title)
        checklist_header.append(self._checklist_summary)
        checklist_card.append(checklist_header)

        self._checklist_list = Gtk.ListBox()
        self._checklist_list.add_css_class("boxed-list")
        self._checklist_list.set_selection_mode(Gtk.SelectionMode.NONE)
        checklist_card.append(self._checklist_list)
        right.append(checklist_card)

        # Pratinjau memo; teks lengkap tetap ditulis di editor Memo.
        memo_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        memo_card.add_css_class("ih-card")
        memo_title = Gtk.Label(label="Memo")
        memo_title.set_xalign(0)
        memo_title.add_css_class("ih-section-title")
        memo_card.append(memo_title)

        self._memo_preview = Gtk.Label(label="")
        self._memo_preview.set_xalign(0)
        self._memo_preview.set_wrap(True)
        self._memo_preview.add_css_class("ih-memo-preview")
        memo_card.append(self._memo_preview)

        memo_footer = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=8
        )
        self._memo_meta = Gtk.Label(label="")
        self._memo_meta.set_xalign(0)
        self._memo_meta.set_hexpand(True)
        self._memo_meta.set_wrap(True)
        self._memo_meta.add_css_class("ih-hint")
        memo_footer.append(self._memo_meta)

        open_memo = Gtk.Button(label="Buka memo tanggal ini")
        open_memo.add_css_class("ih-quick")
        open_memo.set_tooltip_text("Buka editor Memo pada tanggal terpilih")
        open_memo.connect("clicked", self._open_selected_memo)
        memo_footer.append(open_memo)
        memo_card.append(memo_footer)
        right.append(memo_card)

        # Pengingat per tanggal, terpisah dari memo.
        reminder_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        reminder_card.add_css_class("ih-card")
        reminder_title = Gtk.Label(label="Pengingat")
        reminder_title.set_xalign(0)
        reminder_title.add_css_class("ih-section-title")
        reminder_card.append(reminder_title)

        reminder_hint = Gtk.Label(
            label=(
                "Pengingat ini terpisah dari memo. Bisa dibuat untuk tanggal "
                "lampau, hari ini, atau masa depan."
            )
        )
        reminder_hint.set_xalign(0)
        reminder_hint.set_wrap(True)
        reminder_hint.add_css_class("ih-hint")
        reminder_card.append(reminder_hint)

        self._reminder_entry = Gtk.Entry()
        self._reminder_entry.set_placeholder_text(
            "Mis. Minum air, membaca, atau menghubungi keluarga"
        )
        self._reminder_entry.set_hexpand(True)
        self._reminder_entry.connect("activate", self._save_reminder)
        set_accessible_label(self._reminder_entry, "Teks pengingat tanggal ini")
        reminder_card.append(self._reminder_entry)

        time_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        time_label = Gtk.Label(label="Jam")
        time_label.set_xalign(0)
        time_row.append(time_label)
        self._reminder_time = Gtk.Entry()
        self._reminder_time.set_width_chars(6)
        self._reminder_time.set_max_length(5)
        self._reminder_time.set_placeholder_text("08:00")
        self._reminder_time.set_tooltip_text("Format 24 jam, mis. 07:30")
        self._reminder_time.connect("activate", self._save_reminder)
        set_accessible_label(
            self._reminder_time, "Jam pengingat dalam format jam:menit"
        )
        time_row.append(self._reminder_time)

        save = Gtk.Button(label="Simpan pengingat")
        save.add_css_class("suggested-action")
        save.connect("clicked", self._save_reminder)
        time_row.append(save)

        self._delete_reminder_button = Gtk.Button(label="Hapus")
        self._delete_reminder_button.add_css_class("flat")
        self._delete_reminder_button.add_css_class("ih-danger")
        self._delete_reminder_button.connect("clicked", self._delete_reminder)
        time_row.append(self._delete_reminder_button)
        reminder_card.append(time_row)

        self._reminder_status = Gtk.Label(label="")
        self._reminder_status.set_xalign(0)
        self._reminder_status.set_wrap(True)
        self._reminder_status.add_css_class("ih-hint")
        reminder_card.append(self._reminder_status)
        right.append(reminder_card)

        return right

    # -- data ------------------------------------------------------------

    def _refresh(self) -> None:
        self._refresh_month()
        self._refresh_detail()

    def _refresh_month(self) -> None:
        clear_grid(self._month_grid)
        self._month_title.set_label(
            f"{BULAN[self._anchor.month - 1]} {self._anchor.year}"
        )

        first, last = month_range(self._anchor)
        if (self._selected.year, self._selected.month) != (
            first.year,
            first.month,
        ):
            self._selected = first

        notes = {
            item.day: item
            for item in self._repo.list_daily_notes(start=first, end=last)
        }
        reminders = {
            item.day: item
            for item in self._repo.list_reminders(start=first, end=last)
        }

        for column, label in enumerate(HARI_SINGKAT):
            header = Gtk.Label(label=label)
            header.add_css_class("dim-label")
            self._month_grid.attach(header, column, 0, 1, 1)

        today = date.today()
        for day_number in range(1, last.day + 1):
            captured = date(first.year, first.month, day_number)
            index = first.weekday() + day_number - 1
            note = notes.get(captured)
            reminder = reminders.get(captured)
            has_memo = note is not None and (
                bool(note.text.strip()) or note.photo_count > 0
            )
            has_reminder = reminder is not None and bool(reminder.text.strip())

            button = Gtk.Button()
            button.add_css_class("ih-calendar-day")
            if captured == self._selected:
                button.add_css_class("ih-selected")

            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            number = Gtk.Label(label=str(day_number))
            inner.append(number)

            marks = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            marks.set_halign(Gtk.Align.CENTER)
            memo_mark = Gtk.Label(label="✎" if has_memo else "")
            memo_mark.add_css_class("dim-label")
            reminder_mark = Gtk.Label(label="◷" if has_reminder else "")
            reminder_mark.add_css_class("dim-label")
            marks.append(memo_mark)
            marks.append(reminder_mark)
            inner.append(marks)
            button.set_child(inner)

            details: list[str] = []
            if captured == today:
                details.append("hari ini")
            if has_memo:
                details.append("ada memo")
            if has_reminder:
                details.append(f"pengingat pukul {reminder.time}")
            label = format_day(captured)
            if details:
                label += " — " + ", ".join(details)
            button.set_tooltip_text(label)
            set_accessible_label(button, label)
            button.connect("clicked", self._on_day_clicked, captured)
            self._month_grid.attach(
                button, index % 7, index // 7 + 1, 1, 1
            )

    def _refresh_detail(self) -> None:
        day = self._selected
        today = date.today()
        if day == today:
            context = "Hari ini"
        elif day < today:
            context = "Tanggal lampau — pengingat tetap bisa disimpan"
        else:
            context = "Tanggal mendatang — pengingat bisa disiapkan"
        self._detail_title.set_label(format_day(day))
        self._detail_context.set_label(context)
        set_accessible_label(
            self._detail_title, f"{format_day(day)}. {context}."
        )

        self._refresh_checklist(day)
        self._refresh_memo(day)
        self._refresh_reminder(day)

    def _refresh_checklist(self, day: date) -> None:
        clear_list(self._checklist_list)
        records = {
            item.id: item
            for item in self._repo.list_worships(include_archived=True)
        }
        entry_records = self._repo.list_entries(start=day, end=day)
        worships = tuple(item.to_statistics() for item in records.values())
        entries = tuple(item.to_statistics() for item in entry_records)
        daily = compute_daily(day, worships, entries)
        self._checklist_summary.set_label(
            describe_daily_completion(daily.completed, daily.expected)
        )

        entry_map = {item.worship_id: item for item in entry_records}
        for item in daily.per_worship:
            if item.completed:
                status = "Selesai"
            elif item.partial:
                status = "Sebagian"
            else:
                status = "Belum ada catatan"
            entry = entry_map.get(item.worship_id)
            if entry is not None:
                status += f" — {format_entry_detail(entry, records.get(item.worship_id))}"
            row = Adw.ActionRow(title=item.name, subtitle=status)
            row.add_prefix(
                Gtk.Image.new_from_icon_name(
                    "checkbox-checked-symbolic"
                    if item.completed
                    else "checkbox-symbolic"
                )
            )
            self._checklist_list.append(row)

        if not daily.per_worship:
            self._checklist_list.append(
                Adw.ActionRow(
                    title="Tidak ada kegiatan aktif pada tanggal ini",
                    subtitle="Checklist mengikuti ibadah dan kebiasaan yang aktif.",
                )
            )

    def _refresh_memo(self, day: date) -> None:
        note = self._repo.get_daily_note(day)
        text = note.text.strip()
        if text:
            preview = text if len(text) <= 260 else text[:257].rstrip() + "…"
        else:
            preview = "Belum ada memo untuk tanggal ini."
        self._memo_preview.set_label(preview)
        set_accessible_label(self._memo_preview, preview)

        parts = [f"{len(note.text)} karakter"]
        if note.photo_count:
            parts.append(f"{note.photo_count} foto")
        self._memo_meta.set_label(" · ".join(parts))

    def _refresh_reminder(self, day: date) -> None:
        reminder = self._repo.get_reminder(day)
        self._reminder_entry.set_text(reminder.text)
        self._reminder_time.set_text(reminder.time or "08:00")
        self._delete_reminder_button.set_sensitive(bool(reminder.text))
        if reminder.text:
            status = f"Tersimpan pukul {reminder.time}."
            if reminder.sent:
                status += " Notifikasi untuk tanggal ini sudah dikirim."
        else:
            status = "Belum ada pengingat untuk tanggal ini."
        self._reminder_status.set_label(status)

    # -- interaksi -------------------------------------------------------

    def _shift(self, direction: int) -> None:
        self._anchor = shift_month(self._anchor, direction)
        first, last = month_range(self._anchor)
        self._selected = date(
            first.year, first.month, min(self._selected.day, last.day)
        )
        self._refresh()

    def go_current(self) -> None:
        today = date.today()
        self._selected = today
        self._anchor = date(today.year, today.month, 1)
        self._refresh()

    def _on_day_clicked(self, _button: Gtk.Button, day: date) -> None:
        self._selected = day
        self._refresh()

    def _open_selected_memo(self, _button: Gtk.Button) -> None:
        day = self._selected
        self.close()
        self._on_open(day)

    def _notify_changed(self) -> None:
        if self._on_changed is not None:
            self._on_changed()

    def _save_reminder(self, *_args: object) -> None:
        text = self._reminder_entry.get_text().strip()
        time = self._reminder_time.get_text().strip() or "08:00"
        if not text:
            self._repo.delete_reminder(self._selected)
            self._notify_changed()
            self._refresh()
            self._reminder_status.set_label(
                "Pengingat kosong, jadi baris pengingat dihapus."
            )
            return
        try:
            self._repo.save_reminder(self._selected, text, time)
        except ValueError as error:
            self._reminder_status.set_label(str(error))
            return
        self._notify_changed()
        self._refresh()
        saved = self._repo.get_reminder(self._selected)
        self._reminder_status.set_label(
            f"Pengingat disimpan untuk {format_day(self._selected)} "
            f"pukul {saved.time}."
        )

    def _delete_reminder(self, _button: Gtk.Button) -> None:
        self._repo.delete_reminder(self._selected)
        self._notify_changed()
        self._refresh()
        self._reminder_status.set_label("Pengingat dihapus.")
