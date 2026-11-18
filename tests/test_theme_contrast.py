"""Pengujian kontras palet sage tanpa GTK.

Berkas CSS dibaca sebagai teks biasa supaya rasio kontras tetap bisa dijaga
tanpa membuka jendela. Ambang 4.5:1 memakai aturan WCAG untuk teks biasa.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLOR_RE = re.compile(r"@define-color\s+ih-([a-z-]+)\s+(#[0-9a-fA-F]{6});")
MIN_RATIO = 4.5
TEXT_ROLES = ("sage", "accent", "ink", "done", "pending")


def _read_colors(filename: str) -> dict[str, str]:
    text = (ROOT / "data" / filename).read_text(encoding="utf-8")
    return {name: value.lower() for name, value in COLOR_RE.findall(text)}


def _luminance(hex_color: str) -> float:
    channels = [int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def _contrast(first: str, second: str) -> float:
    lighter, darker = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


class ThemeContrastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.light = _read_colors("style.css")
        cls.dark = dict(cls.light)
        cls.dark.update(_read_colors("style-dark.css"))

    def test_light_palette_has_enough_contrast(self) -> None:
        background = self.light["surface"]
        for role in TEXT_ROLES:
            with self.subTest(role=role):
                self.assertGreaterEqual(
                    _contrast(self.light[role], background), MIN_RATIO
                )

    def test_dark_palette_has_enough_contrast(self) -> None:
        background = self.dark["night"]
        for role in TEXT_ROLES:
            with self.subTest(role=role):
                self.assertGreaterEqual(_contrast(self.dark[role], background), MIN_RATIO)

    def test_empty_state_does_not_use_opacity(self) -> None:
        text = (ROOT / "data" / "style.css").read_text(encoding="utf-8")
        block = re.search(r"\.state-kosong\s*\{([^}]*)\}", text)
        self.assertIsNotNone(block)
        self.assertIn("color: @ih-pending;", block.group(1))  # type: ignore[union-attr]
        self.assertNotIn("opacity", block.group(1))  # type: ignore[union-attr]

    def test_gold_marker_has_enough_contrast(self) -> None:
        """Titik tren emas harus terlihat di atas kartu, bukan hanya di latar."""

        for palette in (self.light, self.dark):
            with self.subTest(theme=palette["surface"]):
                self.assertGreaterEqual(
                    _contrast(palette["gold"], palette["surface-card"]), MIN_RATIO
                )

    def test_window_surface_is_declared_explicitly(self) -> None:
        """Palet aplikasi harus menang atas tema GTK pengguna.

        Tema pihak ketiga (mis. Graphite) memuat ``.background`` dengan warna
        literal pada prioritas USER. Tanpa aturan eksplisit di berkas ini,
        jendela tetap gelap meski pengguna memilih tema terang.
        """

        text = (ROOT / "data" / "style.css").read_text(encoding="utf-8")
        self.assertRegex(text, r"window\.background[^{]*\{[^}]*background-color:")

    def test_provider_priority_is_above_user_theme(self) -> None:
        source = (ROOT / "src" / "ui" / "theme.py").read_text(encoding="utf-8")
        self.assertIn(
            "_PROVIDER_PRIORITY = Gtk.STYLE_PROVIDER_PRIORITY_USER + 1", source
        )


if __name__ == "__main__":
    unittest.main()
