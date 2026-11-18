"""Halaman Memo: catatan harian bebas dan foto untuk satu tanggal.

Memo sengaja dipisahkan dari Hari Ini supaya daftar ibadah tetap ringkas,
tetapi kartu kecil di Hari Ini tetap menautkan ke halaman ini. Teks disimpan
di ``catatan_harian`` dan foto di ``memo_foto``; berkas foto berada di folder
data pengguna, bukan di dalam basis data.

Tombol **Memo sebelumnya** membuka daftar tanggal yang sudah punya memo,
lengkap dengan cuplikan teks dan jumlah foto, sehingga pengguna tidak perlu
menekan panah hari satu per satu.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango

from ..logic.repository import MemoPhotoRecord, Repository
from .a11y import set_accessible_label
from .date_navigator import DateNavigator
from .history_common import format_day
from .memo_history import MemoHistoryDialog

__all__ = ["MemoPage"]

ToastCallback = Callable[[str, str | None, Callable[[], None] | None], None]
DataChangedCallback = Callable[[], None]


class MemoPage(Gtk.Box):
    """Editor memo harian dengan lampiran foto dan penjelajah memo lama."""

    def __init__(
        self,
        repository: Repository,
        *,
        on_data_changed: DataChangedCallback,
        on_toast: ToastCallback,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._repo = repository
        self._on_data_changed = on_data_changed
        self._on_toast = on_toast
        self.day = date.today()
        self._known_today = date.today()
        self._loaded_day: date | None = None
        self._note_source: int | None = None
        self._note_loading = False

        self._build_navigation()
        self._build_content()
        self.refresh()
        GLib.timeout_add_seconds(30, self._check_day_change)

    # -- konstruksi ------------------------------------------------------

    def _build_navigation(self) -> None:
        self._nav = DateNavigator(
            on_previous=self.go_previous_day,
            on_next=self.go_next_day,
            on_today=self.go_today,
            on_pick=self.set_day,
        )
        self.append(self._nav)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_margin_start(18)
        actions.set_margin_end(18)
        actions.set_margin_top(6)

        history = Gtk.Button()
        history.add_css_class("ih-quick")
        history.add_css_class("ih-memo-history")
        history.set_tooltip_text("Lihat daftar memo dari tanggal lain")
        history.set_child(self._icon_label("document-open-recent-symbolic", "Memo sebelumnya"))
        set_accessible_label(history, "Lihat memo sebelumnya")
        history.connect("clicked", self._open_history)
        actions.append(history)

        actions.append(Gtk.Box(hexpand=True))

        save = Gtk.Button()
        save.add_css_class("ih-quick")
        save.set_tooltip_text("Simpan sekarang (Ctrl+S)")
        save.set_child(self._icon_label("document-save-symbolic", "Simpan"))
        set_accessible_label(save, "Simpan memo sekarang")
        save.connect("clicked", self._on_save_clicked)
        actions.append(save)

        self.append(actions)

    @staticmethod
    def _icon_label(icon: str, label: str) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.append(Gtk.Image.new_from_icon_name(icon))
        box.append(Gtk.Label(label=label))
        return box

    def _build_content(self) -> None:
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        content.set_margin_start(18)
        content.set_margin_end(18)
        content.set_margin_top(6)
        content.set_margin_bottom(18)

        content.append(self._build_editor_card())
        content.append(self._build_photo_card())

        # Batasi lebar agar baris teks tidak melebar di layar besar.
        clamp = Adw.Clamp()
        clamp.set_maximum_size(820)
        clamp.set_tightening_threshold(620)
        clamp.set_child(content)

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(clamp)
        self.append(scrolled)

    def _build_editor_card(self) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("ih-card")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label="Tulis memo")
        title.set_xalign(0)
        title.set_hexpand(True)
        title.add_css_class("ih-section-title")

        self._note_count = Gtk.Label(label="0 karakter")
        self._note_count.add_css_class("ih-hint")
        self._note_count.set_valign(Gtk.Align.CENTER)
        header.append(title)
        header.append(self._note_count)

        self._note_view = Gtk.TextView()
        self._note_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._note_view.set_accepts_tab(False)
        self._note_view.set_top_margin(8)
        self._note_view.set_bottom_margin(8)
        self._note_view.set_left_margin(10)
        self._note_view.set_right_margin(10)
        self._note_view.get_buffer().connect("changed", self._on_note_changed)
        set_accessible_label(self._note_view, "Memo harian")

        note_scroll = Gtk.ScrolledWindow()
        note_scroll.set_min_content_height(190)
        note_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        note_scroll.set_child(self._note_view)

        # Permukaan editor memakai warna tersendiri, berbeda dari latar
        # aplikasi dan dari kartu putih di sekelilingnya.
        surface = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        surface.add_css_class("ih-editor-surface")

        overlay = Gtk.Overlay()
        overlay.set_child(note_scroll)
        self._placeholder = Gtk.Label(
            label=(
                "Tulis apa yang kamu syukuri, pelajari, atau ingin ingat "
                "hari ini…"
            )
        )
        self._placeholder.set_xalign(0)
        self._placeholder.set_yalign(0)
        self._placeholder.set_wrap(True)
        self._placeholder.set_margin_top(10)
        self._placeholder.set_margin_start(12)
        self._placeholder.set_margin_end(12)
        self._placeholder.set_can_target(False)
        self._placeholder.add_css_class("ih-placeholder")
        overlay.add_overlay(self._placeholder)
        surface.append(overlay)

        self._note_status = Gtk.Label(label="Tersimpan otomatis")
        self._note_status.set_xalign(0)
        self._note_status.add_css_class("ih-hint")

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        footer.append(self._note_status)
        footer.append(Gtk.Box(hexpand=True))
        self._saved_at = Gtk.Label(label="")
        self._saved_at.add_css_class("ih-hint")
        footer.append(self._saved_at)

        card.append(header)
        card.append(surface)
        card.append(footer)
        return card

    def _build_photo_card(self) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("ih-card")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label="Foto memo")
        title.set_xalign(0)
        title.set_hexpand(True)
        title.add_css_class("ih-section-title")

        self._photo_count = Gtk.Label(label="")
        self._photo_count.add_css_class("ih-hint")
        self._photo_count.set_valign(Gtk.Align.CENTER)

        add_button = Gtk.Button(label="Tambah foto")
        add_button.add_css_class("ih-quick")
        add_button.set_tooltip_text("Lampirkan satu atau beberapa foto")
        add_button.connect("clicked", self._on_add_photos)
        header.append(title)
        header.append(self._photo_count)
        header.append(add_button)

        self._photo_stack = Gtk.Stack()

        empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        empty_box.add_css_class("ih-empty")
        empty_icon = Gtk.Image.new_from_icon_name("insert-image-symbolic")
        empty_icon.set_pixel_size(32)
        empty_icon.set_halign(Gtk.Align.CENTER)
        empty_icon.add_css_class("dim-label")
        empty_label = Gtk.Label(
            label=(
                "Belum ada foto. Lampirkan gambar untuk mengingat suasana "
                "hari ini."
            )
        )
        empty_label.set_wrap(True)
        empty_label.set_justify(Gtk.Justification.CENTER)
        empty_label.set_xalign(0.5)
        empty_label.add_css_class("ih-hint")
        empty_box.append(empty_icon)
        empty_box.append(empty_label)
        self._photo_empty = empty_box

        self._photo_flow = Gtk.FlowBox()
        self._photo_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._photo_flow.set_homogeneous(True)
        self._photo_flow.set_min_children_per_line(1)
        self._photo_flow.set_max_children_per_line(4)
        self._photo_flow.set_row_spacing(10)
        self._photo_flow.set_column_spacing(10)

        self._photo_stack.add_named(self._photo_empty, "empty")
        self._photo_stack.add_named(self._photo_flow, "photos")
        self._photo_stack.set_visible_child_name("empty")

        card.append(header)
        card.append(self._photo_stack)
        return card

    # -- teks memo -------------------------------------------------------

    def _note_text(self) -> str:
        buffer = self._note_view.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

    def _load_note(self) -> None:
        self._note_loading = True
        try:
            record = self._repo.get_daily_note(self.day)
            # Jangan reset status simpan saat penyegaran dari halaman lain
            # membawa teks yang sama; status "Tersimpan HH:MM" harus tetap
            # terlihat sampai pengguna mengetik lagi atau pindah tanggal.
            if self._loaded_day != self.day or self._note_text() != record.text:
                self._note_view.get_buffer().set_text(record.text)
                self._update_note_meta("Tersimpan otomatis")
                self._saved_at.set_label("")
            self._loaded_day = self.day
        finally:
            self._note_loading = False
        self._sync_placeholder()

    def _update_note_meta(self, status: str | None = None) -> None:
        text = self._note_text()
        self._note_count.set_label(f"{len(text)} karakter")
        if status is not None:
            self._note_status.set_label(status)

    def _sync_placeholder(self) -> None:
        self._placeholder.set_visible(not self._note_text().strip())

    def _on_note_changed(self, *_args: object) -> None:
        if self._note_loading:
            return
        self._update_note_meta("Menyimpan…")
        self._sync_placeholder()
        if self._note_source is not None:
            GLib.source_remove(self._note_source)
        self._note_source = GLib.timeout_add_seconds(1, self._autosave_note)

    def _autosave_note(self) -> bool:
        self._note_source = None
        self._save_note_now()
        return False

    def _save_note_now(self, *, notify: bool = True) -> None:
        try:
            self._repo.save_daily_note(self.day, self._note_text())
        except sqlite3.Error:
            self._note_status.set_label("Gagal menyimpan — coba lagi")
            return
        self._note_status.set_label("Tersimpan")
        self._saved_at.set_label(datetime.now().strftime("%H:%M"))
        if notify:
            self._on_data_changed()

    def _flush_note(self, *, notify: bool = True) -> None:
        if self._note_source is not None:
            GLib.source_remove(self._note_source)
            self._note_source = None
            self._save_note_now(notify=notify)

    def save_now(self) -> None:
        """Simpan segera; dipakai tombol Simpan dan pintasan Ctrl+S."""

        self._flush_note()
        self._save_note_now()
        self._on_toast("Memo disimpan", None, None)

    def _on_save_clicked(self, _button: Gtk.Button) -> None:
        self.save_now()

    # -- memo sebelumnya -------------------------------------------------

    def _open_history(self, _button: Gtk.Button) -> None:
        self._flush_note()
        dialog = MemoHistoryDialog(
            self._repo,
            current_day=self.day,
            on_open=self._open_from_history,
        )
        dialog.present(self.get_root() or self)

    def _open_from_history(self, day: date) -> None:
        self.set_day(day)

    # -- foto ------------------------------------------------------------

    def _refresh_photos(self) -> None:
        photos = self._repo.list_memo_photos(self.day)
        child = self._photo_flow.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            self._photo_flow.remove(child)
            child = following

        for index, photo in enumerate(photos, start=1):
            self._photo_flow.append(self._build_photo_tile(photo, index))

        if photos:
            self._photo_stack.set_visible_child_name("photos")
            self._photo_count.set_label(f"{len(photos)} foto")
        else:
            self._photo_stack.set_visible_child_name("empty")
            self._photo_count.set_label("0 foto")

    def _build_photo_tile(self, photo: MemoPhotoRecord, index: int) -> Gtk.Widget:
        path = self._repo.photo_path(photo)
        preview: Gtk.Widget
        if path.is_file():
            try:
                # Perkecil tekstur saat memuat supaya galeri tidak menyimpan
                # gambar penuh di memori dan ukuran ubin tetap konsisten.
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    str(path), 160, 120, True
                )
                picture = Gtk.Picture.new_for_paintable(
                    Gdk.Texture.new_for_pixbuf(pixbuf)
                )
            except (GLib.Error, ValueError):
                picture = Gtk.Picture.new_for_filename(str(path))
            picture.set_content_fit(Gtk.ContentFit.COVER)
            picture.set_can_shrink(True)
            picture.set_size_request(160, 120)
            preview = picture
        else:
            fallback = Gtk.Image.new_from_icon_name("image-missing-symbolic")
            fallback.set_pixel_size(48)
            holder = Gtk.Box()
            holder.set_size_request(160, 120)
            holder.set_halign(Gtk.Align.CENTER)
            holder.set_valign(Gtk.Align.CENTER)
            holder.append(fallback)
            preview = holder

        open_button = Gtk.Button()
        open_button.add_css_class("flat")
        open_button.add_css_class("ih-photo-open")
        open_button.set_child(preview)
        open_button.set_tooltip_text("Buka foto ukuran penuh")
        set_accessible_label(open_button, f"Buka foto {index}")
        open_button.connect("clicked", lambda *_: self._open_photo(photo))

        caption = photo.caption.strip() or f"Foto {index}"
        label = Gtk.Label(label=caption)
        label.set_xalign(0)
        label.set_hexpand(True)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_max_width_chars(20)
        label.add_css_class("ih-hint")

        menu = self._photo_menu(photo, index)

        caption_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        caption_row.append(label)
        caption_row.append(menu)

        tile = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        tile.add_css_class("ih-photo-tile")
        tile.set_halign(Gtk.Align.START)
        tile.set_valign(Gtk.Align.START)
        tile.append(open_button)
        tile.append(caption_row)
        return tile

    def _photo_menu(self, photo: MemoPhotoRecord, index: int) -> Gtk.MenuButton:
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(6)
        box.set_margin_end(6)

        view = Gtk.Button(label="Lihat foto")
        view.set_halign(Gtk.Align.FILL)
        view.add_css_class("flat")
        view.connect("clicked", lambda *_: (popover.popdown(), self._open_photo(photo)))
        box.append(view)

        caption = Gtk.Button(label="Ubah keterangan")
        caption.set_halign(Gtk.Align.FILL)
        caption.add_css_class("flat")
        caption.connect(
            "clicked", lambda *_: (popover.popdown(), self._edit_caption(photo))
        )
        box.append(caption)

        remove = Gtk.Button(label="Hapus foto")
        remove.set_halign(Gtk.Align.FILL)
        remove.add_css_class("flat")
        remove.add_css_class("ih-danger")
        remove.connect(
            "clicked", lambda *_: (popover.popdown(), self._confirm_delete_photo(photo))
        )
        box.append(remove)

        popover.set_child(box)

        button = Gtk.MenuButton()
        button.add_css_class("flat")
        button.add_css_class("ih-photo-menu")
        button.set_icon_name("view-more-symbolic")
        button.set_tooltip_text(f"Aksi foto {index}")
        button.set_popover(popover)
        set_accessible_label(button, f"Aksi foto {index}")
        return button

    def _edit_caption(self, photo: MemoPhotoRecord) -> None:
        dialog = Adw.AlertDialog(
            heading="Ubah keterangan foto",
            body="Keterangan tampil di bawah foto dan ikut tersimpan di memo.",
        )
        entry = Gtk.Entry()
        entry.set_text(photo.caption)
        entry.set_placeholder_text("Mis. Suasana setelah subuh")
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Batal")
        dialog.add_response("save", "Simpan")
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_caption_response, photo, entry)
        dialog.present(self.get_root() or self)

    def _on_caption_response(
        self,
        _dialog: Adw.AlertDialog,
        response: str,
        photo: MemoPhotoRecord,
        entry: Gtk.Entry,
    ) -> None:
        if response != "save":
            return
        self._repo.update_memo_caption(photo.id, entry.get_text())
        self._refresh_photos()
        self._on_data_changed()
        self._on_toast("Keterangan foto diperbarui", None, None)

    def _on_add_photos(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileDialog(title="Tambah foto memo")
        image_filter = Gtk.FileFilter()
        image_filter.set_name("Foto (JPG, PNG, WEBP, GIF)")
        for pattern in ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.gif"):
            image_filter.add_pattern(pattern)
        dialog.set_default_filter(image_filter)
        dialog.set_accept_label("Lampirkan")
        dialog.open_multiple(self.get_root() or self, None, self._on_photos_chosen)

    def _on_photos_chosen(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            files = dialog.open_multiple_finish(result)
        except Exception:
            return
        added = 0
        errors: list[str] = []
        for index in range(files.get_n_items()):
            item = files.get_item(index)
            path = item.get_path() if isinstance(item, Gio.File) else None
            if path is None:
                continue
            try:
                self._repo.add_memo_photo(self.day, path)
            except (ValueError, OSError) as error:
                errors.append(str(error))
            else:
                added += 1
        if added:
            self._refresh_photos()
            self._on_data_changed()
            self._on_toast(f"{added} foto ditambahkan", None, None)
        if errors:
            self._on_toast(
                errors[0]
                if len(errors) == 1
                else f"{len(errors)} foto gagal: {errors[0]}",
                None,
                None,
            )

    def _open_photo(self, photo: MemoPhotoRecord) -> None:
        path = self._repo.photo_path(photo)
        dialog = Adw.Dialog()
        dialog.set_title(f"Foto memo {format_day(photo.day)}")
        dialog.set_content_width(760)
        dialog.set_content_height(560)

        header = Adw.HeaderBar()
        close = Gtk.Button(label="Tutup")
        close.connect("clicked", lambda *_: dialog.close())
        header.pack_start(close)
        caption = Gtk.Button(label="Ubah keterangan")
        caption.connect("clicked", lambda *_: self._edit_caption(photo))
        header.pack_end(caption)

        picture = Gtk.Picture.new_for_filename(str(path))
        picture.set_can_shrink(True)
        picture.set_content_fit(Gtk.ContentFit.CONTAIN)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(picture)
        dialog.set_child(toolbar)
        dialog.present(self.get_root() or self)

    def _confirm_delete_photo(self, photo: MemoPhotoRecord) -> None:
        dialog = Adw.AlertDialog(
            heading="Hapus foto ini?",
            body="Foto akan dihapus dari memo tanggal ini. Teks memo tetap disimpan.",
        )
        dialog.add_response("cancel", "Batal")
        dialog.add_response("delete", "Hapus foto")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_delete_photo_response, photo)
        dialog.present(self.get_root() or self)

    def _on_delete_photo_response(
        self,
        _dialog: Adw.AlertDialog,
        response: str,
        photo: MemoPhotoRecord,
    ) -> None:
        if response != "delete":
            return
        self._repo.delete_memo_photo(photo.id)
        self._refresh_photos()
        self._on_data_changed()
        self._on_toast("Foto dihapus", None, None)

    # -- navigasi tanggal ------------------------------------------------

    @staticmethod
    def _context_for(day: date) -> str:
        if day > date.today():
            return "Hari depan — memo masih bisa ditulis"
        if day < date.today():
            return "Mengisi memo hari lampau"
        return ""

    def refresh(self) -> None:
        # Simpan ketikan yang masih menunggu autosave sebelum buffer dimuat
        # ulang, supaya penyegaran dari halaman lain tidak menghapus teks.
        self._flush_note()
        self._nav.set_day(self.day, context=self._context_for(self.day))
        self._load_note()
        self._refresh_photos()

    def go_previous_day(self) -> None:
        self._flush_note()
        self.day -= timedelta(days=1)
        self.refresh()

    def go_next_day(self) -> None:
        self._flush_note()
        self.day += timedelta(days=1)
        self.refresh()

    def go_today(self) -> None:
        self.set_day(date.today())

    def set_day(self, day: date) -> None:
        """Buka memo tanggal tertentu, misalnya dari Kalender atau Hari Ini."""

        self._flush_note()
        self.day = day
        self.refresh()

    def _check_day_change(self) -> bool:
        today = date.today()
        if today != self._known_today:
            self._known_today = today
            self._nav.set_day(self.day, context=self._context_for(self.day))
        return True

    def do_dispose(self) -> None:
        self._flush_note(notify=False)
        Gtk.Box.do_dispose(self)
