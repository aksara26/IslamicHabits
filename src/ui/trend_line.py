"""Garis tren harian, bulanan, dan tahunan untuk halaman Riwayat.

Sesuai keputusan desain: tren memakai **garis lengkung**, bukan batang dan
bukan heatmap. Widget ini hanya menggambar; semua angka dihitung oleh
``src.logic.statistics``. Alternatif teks dan navigasi keyboard disediakan
karena garis saja tidak cukup untuk pembaca layar. Sinyal ``point-activated``
membawa indeks titik (0-based), sedangkan ``month-activated`` dipertahankan
untuk kompatibilitas tahunan.
"""

from __future__ import annotations

from typing import Sequence

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")

import cairo
from gi.repository import Gdk, GObject, Gtk

try:
    from ..logic.statistics import YearPoint, describe_completion
except ImportError:  # memungkinkan impor langsung saat prototyping
    from src.logic.statistics import YearPoint, describe_completion  # type: ignore[no-redef]

__all__ = ["MONTH_NAMES", "TrendLine"]

MONTH_NAMES = (
    "Januari",
    "Februari",
    "Maret",
    "April",
    "Mei",
    "Juni",
    "Juli",
    "Agustus",
    "September",
    "Oktober",
    "November",
    "Desember",
)

# Emas lembut dari palet README; dipakai untuk titik/ornamen, bukan teks kecil.
ACCENT_GOLD = (0.788, 0.635, 0.294)


class TrendLine(Gtk.DrawingArea):
    """Gtk.DrawingArea + Cairo untuk deret titik harian/bulanan/tahunan.

    Sinyal ``month-activated`` membawa nomor bulan (1–12) dan dipancarkan
    lewat Enter/klik. Sinyal ``point-activated`` membawa indeks titik sehingga
    pemanggil bisa memetakannya ke tanggal. Titik tanpa kegiatan aktif sengaja
    dilewati: tidak ada titik, tidak ada garis, dan tidak dibaca sebagai nol.
    """

    __gtype_name__ = "IslamicHabitsTrendLine"
    __gsignals__ = {
        "point-activated": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (GObject.TYPE_INT,),
        ),
        "month-activated": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (GObject.TYPE_INT,),
        ),
    }

    def __init__(self) -> None:
        super().__init__()
        self._points: tuple[YearPoint, ...] = ()
        self._labels: tuple[str, ...] = MONTH_NAMES
        self._title = "Garis tren"
        self._selected: int | None = None

        self.set_hexpand(True)
        self.set_content_height(180)
        self.set_focusable(True)
        self.set_accessible_role(Gtk.AccessibleRole.IMG)
        self.set_tooltip_text("Garis tren")

        # GTK4 memakai set_draw_func, bukan sinyal "draw" seperti GTK3.
        self.set_draw_func(self._on_draw, None)

        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

        click_controller = Gtk.GestureClick.new()
        click_controller.connect("pressed", self._on_clicked)
        self.add_controller(click_controller)

        self._update_accessible()

    # -- API publik -----------------------------------------------------

    def set_points(
        self,
        points: Sequence[YearPoint],
        *,
        labels: Sequence[str] | None = None,
        title: str | None = None,
    ) -> None:
        """Ganti data tren dan segarkan tampilan."""

        self._points = tuple(points)
        self._labels = tuple(labels) if labels is not None else MONTH_NAMES
        self._title = title or "Garis tren"
        self._selected = next(
            (index for index, point in enumerate(self._points) if point.has_data),
            None,
        )
        self.queue_draw()
        self._update_accessible()

    # -- Geometri --------------------------------------------------------

    def _geometry(self) -> tuple[float, float, float, float]:
        width = max(float(self.get_width()), 1.0)
        height = max(float(self.get_height()), 1.0)
        padding = 20.0
        count = max(len(self._points), 1)
        step = (width - 2 * padding) / max(count - 1, 1)
        plot_height = max(height - 2 * padding - 12, 1.0)
        return width, padding, step, plot_height

    def _position(self, index: int) -> tuple[float, float]:
        _, padding, step, plot_height = self._geometry()
        point = self._points[index]
        x = padding + index * step
        y = padding + (1.0 - point.ratio) * plot_height
        return x, y

    def _index_at(self, x: float) -> int | None:
        _, padding, step, _ = self._geometry()
        if not self._points:
            return None
        index = round((x - padding) / step) if step > 0 else 0
        if index < 0 or index >= len(self._points):
            return None
        return index

    def _segments(self) -> list[list[int]]:
        """Kelompokkan titik bersambung yang punya data."""

        segments: list[list[int]] = []
        current: list[int] = []
        for index, point in enumerate(self._points):
            if point.has_data:
                current.append(index)
            elif current:
                segments.append(current)
                current = []
        if current:
            segments.append(current)
        return segments

    # -- Menggambar ------------------------------------------------------

    def _trace(
        self, cr: cairo.Context, segment: list[int], *, close_to_baseline: bool
    ) -> None:
        """Gambar satu ruas lengkung; opsional tutup ke garis dasar."""

        if not segment:
            return
        first_x, first_y = self._position(segment[0])
        _, padding, _, plot_height = self._geometry()
        baseline = padding + plot_height
        if close_to_baseline:
            cr.move_to(first_x, baseline)
            cr.line_to(first_x, first_y)
        else:
            cr.move_to(first_x, first_y)

        previous_x, previous_y = first_x, first_y
        for index in segment[1:]:
            x, y = self._position(index)
            middle = (previous_x + x) / 2
            cr.curve_to(middle, previous_y, middle, y, x, y)
            previous_x, previous_y = x, y

        if close_to_baseline:
            cr.line_to(previous_x, baseline)
            cr.close_path()

    def _on_draw(
        self,
        _area: Gtk.DrawingArea,
        cr: cairo.Context,
        width: int,
        height: int,
        _data: object,
    ) -> None:
        del height
        _, padding, _, plot_height = self._geometry()
        baseline = padding + plot_height
        color = self.get_color()

        # Garis bantu halus memberi skala tanpa mendominasi.
        cr.set_source_rgba(color.red, color.green, color.blue, 0.14)
        cr.set_line_width(1)
        for ratio in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = padding + (1.0 - ratio) * plot_height
            cr.move_to(padding, y)
            cr.line_to(width - padding, y)
            cr.stroke()

        segments = self._segments()

        # Isi tipis di bawah lengkung supaya tren mudah dipindai.
        for segment in segments:
            if len(segment) < 2:
                continue
            self._trace(cr, segment, close_to_baseline=True)
            cr.set_source_rgba(color.red, color.green, color.blue, 0.09)
            cr.fill()

        # Lengkung utama: putus saat ada titik tanpa data.
        cr.set_source_rgba(color.red, color.green, color.blue, 1.0)
        cr.set_line_width(2.5)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        for segment in segments:
            if len(segment) < 2:
                continue
            self._trace(cr, segment, close_to_baseline=False)
            cr.stroke()

        # Penanda titik.
        for index, point in enumerate(self._points):
            if not point.has_data:
                continue
            x, y = self._position(index)
            cr.set_source_rgba(*ACCENT_GOLD, 1.0)
            cr.arc(x, y, 3.5, 0, 2 * 3.141592653589793)
            cr.fill()

            if index == self._selected:
                cr.set_source_rgba(color.red, color.green, color.blue, 0.9)
                cr.set_line_width(1.5)
                cr.arc(x, y, 7.5, 0, 2 * 3.141592653589793)
                cr.stroke()

                cr.set_source_rgba(color.red, color.green, color.blue, 0.35)
                cr.set_line_width(1)
                cr.set_dash([3, 4], 0)
                cr.move_to(x, y + 8)
                cr.line_to(x, baseline)
                cr.stroke()
                cr.set_dash([], 0)

        # Label sumbu hanya untuk 12 titik agar tidak bertumpuk.
        if len(self._points) <= 12:
            cr.set_source_rgba(color.red, color.green, color.blue, 0.75)
            cr.select_font_face(
                "Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL
            )
            cr.set_font_size(10)
            for index, label in enumerate(self._labels[: len(self._points)]):
                x, _ = self._position(index)
                extents = cr.text_extents(label[:3])
                cr.move_to(x - extents.width / 2, baseline + 14)
                cr.show_text(label[:3])

    # -- Interaksi -------------------------------------------------------

    def _on_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        if keyval in (Gdk.KEY_Left, Gdk.KEY_Right):
            self._move_selection(1 if keyval == Gdk.KEY_Right else -1)
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if self._selected is not None:
                self.emit("point-activated", self._selected)
                self.emit("month-activated", self._selected + 1)
            return True
        return False

    def _on_clicked(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> None:
        del y
        index = self._index_at(x)
        if index is None or not self._points[index].has_data:
            return
        self._selected = index
        self.queue_draw()
        self.emit("point-activated", index)
        self.emit("month-activated", index + 1)

    def _move_selection(self, direction: int) -> None:
        valid = [i for i, point in enumerate(self._points) if point.has_data]
        if not valid:
            return
        if self._selected is None:
            self._selected = valid[0]
        else:
            current = valid.index(self._selected) if self._selected in valid else 0
            self._selected = valid[(current + direction) % len(valid)]
        self.queue_draw()

    # -- Aksesibilitas ---------------------------------------------------

    def _update_accessible(self) -> None:
        total_completed = sum(point.completed_days for point in self._points)
        total_expected = sum(point.expected_days for point in self._points)
        lines = [
            self._title + ": " + describe_completion(total_completed, total_expected)
        ]

        for index, point in enumerate(self._points):
            label = self._labels[index] if index < len(self._labels) else f"Titik {index + 1}"
            if point.has_data:
                detail = describe_completion(point.completed_days, point.expected_days)
            else:
                detail = "tidak ada kegiatan aktif"
            if index < 12 or index == len(self._points) - 1:
                lines.append(f"{label}: {detail}")

        text = "\n".join(lines)
        self.set_tooltip_text(text)
        try:
            # GTK4: Gtk.Accessible.update_property(widget, [prop], [nilai]).
            Gtk.Accessible.update_property(
                self,
                [Gtk.AccessibleProperty.LABEL],
                [text],
            )
        except Exception:  # AT-SPI mungkin tidak tersedia di sesi tanpa aksesibilitas
            pass
