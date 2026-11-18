"""Garis tren tahunan untuk halaman Riwayat.

Sesuai keputusan desain: tahunan memakai **garis**, bukan batang dan bukan
heatmap. Widget ini hanya menggambar; semua angka dihitung oleh
``src.logic.statistics``. Alternatif teks dan navigasi keyboard disediakan
karena garis saja tidak cukup untuk pembaca layar.
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

__all__ = ["TrendLine"]

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
    """Gtk.DrawingArea + Cairo untuk 12 titik bulanan.

    Sinyal ``month-activated`` membawa nomor bulan (1–12) dan dipancarkan
    lewat Enter/klik. Bulan tanpa ibadah aktif sengaja dilewati: tidak ada
    titik, tidak ada garis, dan tidak dibaca sebagai angka nol.
    """

    __gtype_name__ = "IslamicHabitsTrendLine"
    __gsignals__ = {
        "month-activated": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (GObject.TYPE_INT,),
        )
    }

    def __init__(self) -> None:
        super().__init__()
        self._points: tuple[YearPoint, ...] = ()
        self._selected: int | None = None

        self.set_hexpand(True)
        self.set_content_height(160)
        self.set_focusable(True)
        self.set_accessible_role(Gtk.AccessibleRole.IMG)
        self.set_tooltip_text("Garis tren tahunan")

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

    def set_points(self, points: Sequence[YearPoint]) -> None:
        """Ganti data 12 titik dan segarkan tampilan."""

        self._points = tuple(points)
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
        padding = 18.0
        count = max(len(self._points), 1)
        step = (width - 2 * padding) / max(count - 1, 1)
        plot_height = max(height - 2 * padding, 1.0)
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

    # -- Menggambar ------------------------------------------------------

    def _on_draw(
        self,
        _area: Gtk.DrawingArea,
        cr: cairo.Context,
        width: int,
        height: int,
        _data: object,
    ) -> None:
        padding = 18.0
        color = self.get_color()

        # Garis dasar yang sangat halus.
        cr.set_source_rgba(color.red, color.green, color.blue, 0.25)
        cr.set_line_width(1)
        cr.move_to(padding, height - padding)
        cr.line_to(width - padding, height - padding)
        cr.stroke()

        # Garis tren: putus saat ada bulan tanpa data.
        cr.set_source_rgba(color.red, color.green, color.blue, 1.0)
        cr.set_line_width(2)
        pen_down = False
        for index, point in enumerate(self._points):
            if not point.has_data:
                pen_down = False
                continue
            x, y = self._position(index)
            if pen_down:
                cr.line_to(x, y)
            else:
                cr.move_to(x, y)
                pen_down = True
        cr.stroke()

        # Titik bulan.
        for index, point in enumerate(self._points):
            if not point.has_data:
                continue
            x, y = self._position(index)
            cr.set_source_rgba(*ACCENT_GOLD, 1.0)
            cr.arc(x, y, 3.5, 0, 2 * 3.141592653589793)
            cr.fill()

            if index == self._selected:
                cr.set_source_rgba(color.red, color.green, color.blue, 0.85)
                cr.set_line_width(1.5)
                cr.arc(x, y, 7, 0, 2 * 3.141592653589793)
                cr.stroke()

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
        lines = ["Garis tren tahunan: " + describe_completion(total_completed, total_expected)]

        for index, point in enumerate(self._points):
            label = MONTH_NAMES[index] if index < len(MONTH_NAMES) else f"Bulan {index + 1}"
            if point.has_data:
                detail = describe_completion(point.completed_days, point.expected_days)
            else:
                detail = "tidak ada ibadah aktif"
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
