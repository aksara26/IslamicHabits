"""Halaman Pengaturan: tampilan, pengingat, data, dan tentang aplikasi."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, Gtk

from ..logic.constants import (
    APP_NAME,
    APP_VERSION,
    LICENSE,
    REPOSITORY_URL,
    SETTING_BACKUP_FOLDER,
    SETTING_REMINDER_ENABLED,
    SETTING_REMINDER_PERMISSION,
    SETTING_REMINDER_POPUP,
    SETTING_REMINDER_TIME,
    SETTING_THEME,
)
from ..logic.database import default_data_dir
from ..logic.repository import Repository
from ..logic.transfer import (
    TransferError,
    backup_folder,
    create_backup,
    describe_import,
    import_payload,
    parse_export,
    write_export,
)
from .theme import THEME_KEYS, THEME_LABELS, normalize_theme

__all__ = ["SettingsPage", "THEME_KEYS", "THEME_LABELS"]

ToastCallback = Callable[[str, str | None, Callable[[], None] | None], None]
ThemeCallback = Callable[[str], None]
DataChangedCallback = Callable[[], None]
NotificationCallback = Callable[[], None]


class SettingsPage(Gtk.Box):
    """Preferensi dengan aksi data yang memakai konfirmasi jelas."""

    def __init__(
        self,
        repository: Repository,
        *,
        on_theme_changed: ThemeCallback,
        on_toast: ToastCallback,
        on_data_changed: DataChangedCallback,
        on_test_notification: NotificationCallback,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._repo = repository
        self._on_theme_changed = on_theme_changed
        self._on_toast = on_toast
        self._on_data_changed = on_data_changed
        self._on_test_notification = on_test_notification
        self._refreshing = False

        self._build_page()

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(self._preferences)
        self.append(scrolled)

    # -- konstruksi ------------------------------------------------------

    def _build_page(self) -> None:
        self._preferences = Adw.PreferencesPage()

        self._preferences.add(self._build_display_group())
        self._preferences.add(self._build_reminder_group())
        self._preferences.add(self._build_data_group())
        self._preferences.add(self._build_about_group())

    def refresh(self) -> None:
        """Muat ulang nilai setelah impor atau penghapusan data."""

        self._refreshing = True
        try:
            theme = normalize_theme(
                self._repo.get_setting(SETTING_THEME, THEME_KEYS[0])
            )
            self._theme_row.set_selected(THEME_KEYS.index(theme))

            self._reminder_switch.set_active(
                self._repo.get_setting(SETTING_REMINDER_ENABLED, "0") == "1"
            )
            self._popup_switch.set_active(
                self._repo.get_setting(SETTING_REMINDER_POPUP, "1") == "1"
            )
            self._time_row.set_text(
                self._repo.get_setting(SETTING_REMINDER_TIME, "20:00")
            )
            self._update_permission_row()
            self._backup_row.set_subtitle(str(backup_folder(self._repo)))
        finally:
            self._refreshing = False

    def _build_display_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title="Tampilan",
            description=(
                "Warna latar aplikasi. Area tulisan memakai permukaan "
                "tersendiri agar mudah dibedakan."
            ),
        )

        self._theme_row = Adw.ComboRow(
            title="Tema",
            subtitle="Hijau sage (default), putih, atau hitam",
        )
        self._theme_row.set_model(Gtk.StringList.new(list(THEME_LABELS)))
        current = normalize_theme(
            self._repo.get_setting(SETTING_THEME, THEME_KEYS[0])
        )
        self._theme_row.set_selected(THEME_KEYS.index(current))
        self._theme_row.connect("notify::selected", self._on_theme_selected)
        group.add(self._theme_row)
        return group

    def _build_reminder_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title="Pengingat",
            description=(
                "Pengingat berjalan selama aplikasi terbuka. Popup desktop "
                "memerlukan izin dan dapat diblokir oleh pengaturan sistem."
            ),
        )

        self._reminder_switch = Adw.SwitchRow(
            title="Pengingat harian",
            subtitle="Tampilkan pengingat pada jam yang dipilih",
        )
        self._reminder_switch.set_active(
            self._repo.get_setting(SETTING_REMINDER_ENABLED, "0") == "1"
        )
        self._reminder_switch.connect("notify::active", self._on_reminder_toggled)
        group.add(self._reminder_switch)

        self._popup_switch = Adw.SwitchRow(
            title="Popup pemberitahuan",
            subtitle="Tampilkan notifikasi desktop saat pengingat berbunyi",
        )
        self._popup_switch.set_active(
            self._repo.get_setting(SETTING_REMINDER_POPUP, "1") == "1"
        )
        self._popup_switch.connect("notify::active", self._on_popup_toggled)
        group.add(self._popup_switch)

        self._permission_row = Adw.ActionRow(
            title="Izin popup",
            subtitle="Belum diizinkan",
        )
        self._permission_button = Gtk.Button(label="Minta izin")
        self._permission_button.set_valign(Gtk.Align.CENTER)
        self._permission_button.connect("clicked", self._on_permission_button)
        self._permission_row.add_suffix(self._permission_button)
        group.add(self._permission_row)
        self._update_permission_row()

        group.add(
            self._action_row(
                "Uji notifikasi",
                "Kirim satu popup contoh untuk memeriksa izin sistem",
                "Kirim",
                self._on_test_notification,
            )
        )

        self._time_row = Adw.EntryRow(title="Jam (HH:MM)")
        self._time_row.set_text(self._repo.get_setting(SETTING_REMINDER_TIME, "20:00"))
        self._time_row.connect("changed", self._on_time_changed)
        group.add(self._time_row)
        return group

    def _build_data_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title="Data",
            description="Data hanya tersimpan di komputer ini. Tidak ada akun atau server.",
        )
        group.add(
            self._action_row(
                "Ekspor data",
                "Simpan salinan JSON lengkap ibadah, kebiasaan, dan catatan",
                "Ekspor",
                self._on_export,
            )
        )
        group.add(
            self._action_row("Impor data", "Gabungkan atau timpa dengan berkas JSON", "Impor", self._on_import)
        )

        self._backup_row = Adw.ActionRow(
            title="Folder cadangan",
            subtitle=str(backup_folder(self._repo)),
        )
        pick_folder = Gtk.Button(label="Pilih folder")
        pick_folder.set_valign(Gtk.Align.CENTER)
        pick_folder.connect("clicked", self._on_pick_backup_folder)
        self._backup_row.add_suffix(pick_folder)
        group.add(self._backup_row)

        group.add(
            self._action_row(
                "Cadangkan sekarang",
                "Buat salinan berversi di folder cadangan",
                "Cadangkan",
                self._on_backup_now,
            )
        )

        data_dir = default_data_dir()
        group.add(
            self._action_row(
                "Lokasi data",
                str(data_dir / "islamichabits.sqlite3"),
                "Buka folder",
                self._on_open_data_folder,
            )
        )

        delete_row = Adw.ActionRow(
            title="Hapus semua data",
            subtitle="Kembalikan ke ibadah dan kebiasaan bawaan; tidak bisa diurungkan",
        )
        delete_button = Gtk.Button(label="Hapus semua")
        delete_button.add_css_class("destructive-action")
        delete_button.set_valign(Gtk.Align.CENTER)
        delete_button.connect("clicked", self._confirm_delete_all)
        delete_row.add_suffix(delete_button)
        group.add(delete_row)
        return group

    def _build_about_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(title="Tentang")
        group.add(
            self._action_row(
                "Tentang IslamicHabits",
                f"Versi {APP_VERSION} · {LICENSE}",
                "Lihat",
                self._on_about,
            )
        )
        return group

    @staticmethod
    def _action_row(
        title: str, subtitle: str, button_label: str, callback: Callable
    ) -> Adw.ActionRow:
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        button = Gtk.Button(label=button_label)
        button.set_valign(Gtk.Align.CENTER)
        button.connect("clicked", callback)
        row.add_suffix(button)
        return row

    # -- tampilan & pengingat --------------------------------------------

    def _on_theme_selected(self, *_args: object) -> None:
        if self._refreshing:
            return
        index = self._theme_row.get_selected()
        if not 0 <= index < len(THEME_KEYS):
            return
        theme = THEME_KEYS[index]
        self._repo.set_setting(SETTING_THEME, theme)
        self._on_theme_changed(theme)

    def _on_reminder_toggled(self, row: Adw.SwitchRow, *_args: object) -> None:
        if self._refreshing:
            return
        self._repo.set_setting(
            SETTING_REMINDER_ENABLED, "1" if row.get_active() else "0"
        )
        if (
            row.get_active()
            and self._repo.get_setting(SETTING_REMINDER_POPUP, "1") == "1"
            and not self._permission_granted()
        ):
            self._request_permission(
                revert_row=self._popup_switch,
                revert_setting=SETTING_REMINDER_POPUP,
            )

    def _on_popup_toggled(self, row: Adw.SwitchRow, *_args: object) -> None:
        if self._refreshing:
            return
        if not row.get_active():
            self._repo.set_setting(SETTING_REMINDER_POPUP, "0")
            return
        if self._permission_granted():
            self._repo.set_setting(SETTING_REMINDER_POPUP, "1")
            return
        self._request_permission(
            on_granted=lambda: self._repo.set_setting(SETTING_REMINDER_POPUP, "1"),
            revert_row=row,
            revert_setting=SETTING_REMINDER_POPUP,
        )

    def _permission_granted(self) -> bool:
        return (
            self._repo.get_setting(SETTING_REMINDER_PERMISSION, "0") == "1"
        )

    def _update_permission_row(self) -> None:
        granted = self._permission_granted()
        self._permission_row.set_subtitle(
            "Diizinkan" if granted else "Belum diizinkan"
        )
        self._permission_button.set_label("Uji" if granted else "Minta izin")

    def _on_permission_button(self, _button: Gtk.Button) -> None:
        if self._permission_granted():
            self._on_test_notification()
            return
        self._request_permission(on_granted=self._on_test_notification)

    def _request_permission(
        self,
        *,
        on_granted: Callable[[], None] | None = None,
        revert_row: Adw.SwitchRow | None = None,
        revert_setting: str = SETTING_REMINDER_POPUP,
    ) -> None:
        if self._permission_granted():
            if on_granted is not None:
                on_granted()
            return
        dialog = Adw.AlertDialog(
            heading="Izinkan popup pemberitahuan?",
            body=(
                "IslamicHabits dapat menampilkan pengingat sebagai notifikasi "
                "desktop. Izin ini hanya dipakai untuk pengingat; tidak ada data "
                "yang dikirim ke server. Beberapa desktop tetap dapat memblokir "
                "notifikasi lewat pengaturan sistem."
            ),
        )
        dialog.add_response("cancel", "Nanti")
        dialog.add_response("allow", "Izinkan")
        dialog.set_default_response("allow")
        dialog.set_close_response("cancel")
        dialog.connect(
            "response",
            self._on_permission_response,
            on_granted,
            revert_row,
            revert_setting,
        )
        dialog.present(self.get_root() or self)

    def _on_permission_response(
        self,
        _dialog: Adw.AlertDialog,
        response: str,
        on_granted: Callable[[], None] | None,
        revert_row: Adw.SwitchRow | None,
        revert_setting: str,
    ) -> None:
        if response == "allow":
            self._repo.set_setting(SETTING_REMINDER_PERMISSION, "1")
            self._update_permission_row()
            if on_granted is not None:
                on_granted()
            return
        if revert_row is not None:
            self._refreshing = True
            try:
                revert_row.set_active(False)
            finally:
                self._refreshing = False
            self._repo.set_setting(revert_setting, "0")

    def _on_time_changed(self, row: Adw.EntryRow) -> None:
        if self._refreshing:
            return
        value = row.get_text().strip()
        try:
            normalized = datetime.strptime(value, "%H:%M").strftime("%H:%M")
        except ValueError:
            row.add_css_class("error")
            return
        row.remove_css_class("error")
        if value != normalized:
            row.set_text(normalized)
            return
        self._repo.set_setting(SETTING_REMINDER_TIME, normalized)

    # -- ekspor & cadangan ------------------------------------------------

    def _json_filter(self) -> Gtk.FileFilter:
        file_filter = Gtk.FileFilter()
        file_filter.set_name("JSON IslamicHabits (*.json)")
        file_filter.add_pattern("*.json")
        return file_filter

    def _on_export(self, *_args: object) -> None:
        dialog = Gtk.FileDialog(title="Ekspor data")
        dialog.set_default_filter(self._json_filter())
        dialog.set_initial_name("islamichabits-export.json")
        dialog.save(
            self.get_root() or self,
            None,
            self._on_export_finished,
        )

    def _on_export_finished(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            path = dialog.save_finish(result).get_path()
        except Exception:
            return
        if not path:
            return
        try:
            target = write_export(self._repo, path)
        except OSError as error:
            self._on_toast(f"Ekspor tidak tersimpan: {error}", None, None)
            return
        self._on_toast(f"Data tersimpan di {target.name}", None, None)

    def _on_backup_now(self, *_args: object) -> None:
        try:
            target = create_backup(self._repo)
        except OSError as error:
            self._on_toast(f"Cadangan tidak tersimpan: {error}", None, None)
            return
        self._on_toast(f"Cadangan dibuat: {target.name}", None, None)

    def _on_pick_backup_folder(self, *_args: object) -> None:
        dialog = Gtk.FileDialog(title="Pilih folder cadangan")
        dialog.select_folder(
            self.get_root() or self, None, self._on_folder_finished
        )

    def _on_folder_finished(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            path = dialog.select_folder_finish(result).get_path()
        except Exception:
            return
        if not path:
            return
        self._repo.set_setting(SETTING_BACKUP_FOLDER, path)
        self._backup_row.set_subtitle(path)
        self._on_toast("Folder cadangan diperbarui", None, None)

    def _on_open_data_folder(self, *_args: object) -> None:
        folder = default_data_dir()
        folder.mkdir(parents=True, exist_ok=True)
        try:
            Gio.AppInfo.launch_default_for_uri(folder.as_uri(), None)
        except Exception as error:
            self._on_toast(f"Folder tidak bisa dibuka: {error}", None, None)

    # -- impor -----------------------------------------------------------

    def _on_import(self, *_args: object) -> None:
        dialog = Gtk.FileDialog(title="Impor data")
        dialog.set_default_filter(self._json_filter())
        dialog.open(self.get_root() or self, None, self._on_import_finished)

    def _on_import_finished(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            path = dialog.open_finish(result).get_path()
        except Exception:
            return
        if not path:
            return
        try:
            payload = parse_export(Path(path))
            preview = describe_import(self._repo, payload)
        except TransferError as error:
            self._on_toast(str(error), None, None)
            return

        details = (
            f"Berkas berisi {preview.counts['ibadah']} kegiatan, "
            f"{preview.counts['catatan']} catatan kegiatan, "
            f"{preview.counts['catatan_harian']} catatan harian, dan "
            f"{preview.counts['muhasabah']} muhasabah.\n\n"
            f"Baris baru: {preview.total_new}. "
            f"Kunci sudah ada: {preview.total_conflicts}."
        )
        confirm = Adw.AlertDialog(
            heading="Impor data",
            body=details + "\n\nGabungkan menyimpan data yang belum ada. Timpa mengganti semua data saat ini.",
        )
        confirm.add_response("cancel", "Batal")
        confirm.add_response("merge", "Gabungkan")
        confirm.add_response("replace", "Timpa semua")
        confirm.set_response_appearance("replace", Adw.ResponseAppearance.DESTRUCTIVE)
        confirm.set_default_response("merge")
        confirm.set_close_response("cancel")
        confirm.connect("response", self._on_import_confirmed, payload)
        confirm.present(self.get_root() or self)

    def _on_import_confirmed(
        self,
        _dialog: Adw.AlertDialog,
        response: str,
        payload: dict,
    ) -> None:
        if response not in {"merge", "replace"}:
            return
        try:
            summary = import_payload(self._repo, payload, mode=response)
        except TransferError as error:
            self._on_toast(str(error), None, None)
            return
        self._on_data_changed()
        self._on_toast(
            f"Impor selesai: {summary.total_inserted} baris ditambahkan", None, None
        )

    # -- hapus semua -----------------------------------------------------

    def _confirm_delete_all(self, *_args: object) -> None:
        dialog = Adw.AlertDialog(
            heading="Hapus semua data?",
            body=(
                "Seluruh ibadah, kebiasaan, catatan kegiatan, catatan harian, "
                "muhasabah, dan pengaturan akan dihapus, lalu data bawaan "
                "dikembalikan. "
                "Buat cadangan dulu bila perlu."
            ),
        )
        dialog.add_response("cancel", "Batal")
        dialog.add_response("delete", "Hapus semua")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_delete_all_response)
        dialog.present(self.get_root() or self)

    def _on_delete_all_response(self, _dialog: Adw.AlertDialog, response: str) -> None:
        if response != "delete":
            return
        self._repo.clear_all_data()
        self._on_data_changed()
        self._on_toast(
            "Data dihapus dan ibadah serta kebiasaan bawaan dikembalikan", None, None
        )

    # -- tentang ---------------------------------------------------------

    def _on_about(self, *_args: object) -> None:
        dialog = Adw.AboutDialog(
            application_name=APP_NAME,
            application_icon="io.github.kurakura.IslamicHabits",
            version=APP_VERSION,
            developer_name="kurakura",
            license=LICENSE,
            website=REPOSITORY_URL,
            comments=(
                "Catatan ibadah dan kebiasaan harian yang privat dan lokal. "
                "Tidak ada akun, tidak ada server."
            ),
        )
        dialog.present(self.get_root() or self)
