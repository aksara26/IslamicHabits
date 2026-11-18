"""Halaman Memo: catatan harian bebas dan foto untuk satu tanggal.

Memo sengaja dipisahkan dari Hari Ini supaya daftar ibadah tetap ringkas,
tetapi kartu kecil di bawah checklist tetap menautkan ke halaman ini. Teks
disimpan di ``catatan_harian`` dan foto di ``memo_foto``; berkas foto berada
di folder data pengguna, bukan di dalam basis data.
"""

from __future__ import annotations

from datetime import date, timedelta
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
from .history_common import format_day

__all__ = ["MemoPage"]

ToastCallback = Callable[[str, str | None, Callable[[], None] | None], None]
DataChangedCallback = Callable[[], None]


class MemoPage(Gtk.Box):
    """Editor memo harian dengan lampiran foto."""

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
        self._note_source: int | None = None
        self._note_loading = False

        self._build_navigation()
        self._build_content()
        self.refresh()
        GLib.timeout_add_seconds(30, self._check_day_change)

    # -- konstruksi ------------------------------------------------------

    def _build_navigation(self) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)

        previous = Gtk.Button.new_from_icon_name("go-previous-symbolic")
        previous.set_tooltip_text("Memo hari sebelumnya")
        set_accessible_label(previous, "Memo hari sebelumnya")
        previous.connect("clicked", lambda *_: self.go_previous_day())
        box.append(previous)

        self._date_label = Gtk.Label(label="")
        self._date_label.set_hexpand(True)
        self._date_label.set_xalign(0.5)
        box.append(self._date_label)

        today = Gtk.Button(label="Hari ini")
        today.set_tooltip_text("Kembali ke memo hari ini")
        set_accessible_label(today, "Kembali ke memo hari ini")
        today.connect("clicked", lambda *_: self.go_today())
        box.append(today)

        following = Gtk.Button.new_from_icon_name("go-next-symbolic")
        following.set_tooltip_text("Memo hari berikutnya")
        set_accessible_label(following, "Memo hari berikutnya")
        following.connect("clicked", lambda *_: self.go_next_day())
        box.append(following)

        self._context_label = Gtk.Label(label="")
        self._context_label.set_xalign(0.5)
        self._context_label.add_css_class("dim-label")

        wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        wrapper.append(box)
        wrapper.append(self._context_label)
        self.append(wrapper)

    def _build_content(self) -> None:
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_start(18)
        content.set_margin_end(18)
        content.set_margin_top(6)
        content.set_margin_bottom(18)

        content.append(self._build_editor_card())
        content.append(self._build_photo_card())

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(content)
        self.append(scrolled)

    def _build_editor_card(self) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("ih-card")

        title = Gtk.Label(label="Tulis memo")
        title.set_xalign(0)
        title.add_css_class("ih-section-title")
        hint = Gtk.Label(
            label=(
                "Catatan ini tersimpan otomatis di komputer ini. "
                "Gunakan foto di bawah untuk melampirkan gambar."
            )
        )
        hint.set_xalign(0)
        hint.set_wrap(True)
        hint.add_css_class("ih-hint")

        self._note_view = Gtk.TextView()
        self._note_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._note_view.set_accepts_tab(False)
        self._note_view.get_buffer().connect("changed", self._on_note_changed)
        set_accessible_label(self._note_view, "Memo harian")
        note_scroll = Gtk.ScrolledWindow()
        note_scroll.set_min_content_height(150)
        note_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        note_scroll.set_child(self._note_view)

        self._note_status = Gtk.Label(label="Tersimpan otomatis")
        self._note_status.set_xalign(0)
        self._note_status.add_css_class("ih-hint")

        card.append(title)
        card.append(hint)
        card.append(note_scroll)
        card.append(self._note_status)
        return card

    def _build_photo_card(self) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("ih-card")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label="Foto memo")
        title.set_xalign(0)
        title.set_hexpand(True)
        title.add_css_class("ih-section-title")

        self._photo_count = Gtk.Label(label="")
        self._photo_count.add_css_class("ih-hint")

        add_button = Gtk.Button(label="Tambah foto")
        add_button.add_css_class("ih-quick")
        add_button.set_tooltip_text("Lampirkan satu atau beberapa foto")
        add_button.connect("clicked", self._on_add_photos)
        header.append(title)
        header.append(self._photo_count)
        header.append(add_button)

        self._photo_stack = Gtk.Stack()
        self._photo_empty = Gtk.Label(
            label="Belum ada foto. Lampirkan gambar untuk mengingat suasana hari ini."
        )
        self._photo_empty.set_xalign(0)
        self._photo_empty.set_wrap(True)
        self._photo_empty.add_css_class("ih-hint")

        self._photo_flow = Gtk.FlowBox()
        self._photo_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._photo_flow.set_homogeneous(True)
        self._photo_flow.set_min_children_per_line(1)
        self._photo_flow.set_max_children_per_line(4)
        self._photo_flow.set_row_spacing(8)
        self._photo_flow.set_column_spacing(8)

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
            self._note_view.get_buffer().set_text(record.text)
            self._note_status.set_label("Tersimpan otomatis")
        finally:
            self._note_loading = False

    def _on_note_changed(self, *_args: object) -> None:
        if self._note_loading:
            return
        self._note_status.set_label("Menunggu penyimpanan…")
        if self._note_source is not None:
            GLib.source_remove(self._note_source)
        self._note_source = GLib.timeout_add_seconds(1, self._autosave_note)

    def _autosave_note(self) -> bool:
        self._note_source = None
        self._save_note_now()
        return False

    def _save_note_now(self, *, notify: bool = True) -> None:
        self._repo.save_daily_note(self.day, self._note_text())
        self._note_status.set_label("Tersimpan otomatis")
        if notify:
            self._on_data_changed()

    def _flush_note(self, *, notify: bool = True) -> None:
        if self._note_source is not None:
            GLib.source_remove(self._note_source)
            self._note_source = None
            self._save_note_now(notify=notify)

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

        remove_button = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        remove_button.add_css_class("flat")
        remove_button.add_css_class("ih-photo-remove")
        remove_button.set_halign(Gtk.Align.END)
        remove_button.set_valign(Gtk.Align.START)
        remove_button.set_tooltip_text("Hapus foto")
        set_accessible_label(remove_button, f"Hapus foto {index}")
        remove_button.connect("clicked", lambda *_: self._confirm_delete_photo(photo))

        overlay = Gtk.Overlay()
        overlay.set_child(open_button)
        overlay.add_overlay(remove_button)

        tile = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        tile.add_css_class("ih-photo-tile")
        tile.set_halign(Gtk.Align.START)
        tile.set_valign(Gtk.Align.START)
        tile.append(overlay)
        caption = photo.caption.strip() or f"Foto {index}"
        label = Gtk.Label(label=caption)
        label.set_xalign(0)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_max_width_chars(22)
        label.add_css_class("ih-hint")
        tile.append(label)
        return tile

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

    def refresh(self) -> None:
        # Simpan ketikan yang masih menunggu autosave sebelum buffer dimuat
        # ulang, supaya penyegaran dari halaman lain tidak menghapus teks.
        self._flush_note()
        self._date_label.set_label(format_day(self.day))
        if self.day > date.today():
            self._context_label.set_label("Hari depan — memo masih bisa ditulis")
        elif self.day < date.today():
            self._context_label.set_label("Mengisi memo hari lampau")
        else:
            self._context_label.set_label("")
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
            self._context_label.set_label("Hari sudah berganti; buka memo hari ini.")
        return True

    def do_dispose(self) -> None:
        self._flush_note(notify=False)
        Gtk.Box.do_dispose(self)
