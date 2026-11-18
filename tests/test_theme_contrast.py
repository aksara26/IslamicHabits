"""Pengujian kontras palet tema tanpa GTK.

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
LIGHT_THEMES = ("hijau", "putih")


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
        cls.hijau = _read_colors("style.css")
        cls.putih = dict(cls.hijau)
        cls.putih.update(_read_colors("style-putih.css"))
        cls.hitam = dict(cls.hijau)
        cls.hitam.update(_read_colors("style-hitam.css"))
        cls.palettes = {
            "hijau": cls.hijau,
            "putih": cls.putih,
            "hitam": cls.hitam,
        }

    def test_light_palettes_have_enough_contrast(self) -> None:
        for name in LIGHT_THEMES:
            palette = self.palettes[name]
            background = palette["surface"]
            for role in TEXT_ROLES:
                with self.subTest(theme=name, role=role):
                    self.assertGreaterEqual(
                        _contrast(palette[role], background), MIN_RATIO
                    )

    def test_dark_palette_has_enough_contrast(self) -> None:
        background = self.hitam["night"]
        for role in TEXT_ROLES:
            with self.subTest(role=role):
                self.assertGreaterEqual(
                    _contrast(self.hitam[role], background), MIN_RATIO
                )

    def test_empty_state_does_not_use_opacity(self) -> None:
        text = (ROOT / "data" / "style.css").read_text(encoding="utf-8")
        block = re.search(r"\.state-kosong\s*\{([^}]*)\}", text)
        self.assertIsNotNone(block)
        self.assertIn("color: @ih-pending;", block.group(1))  # type: ignore[union-attr]
        self.assertNotIn("opacity", block.group(1))  # type: ignore[union-attr]

    def test_gold_marker_has_enough_contrast(self) -> None:
        """Titik tren emas harus terlihat di atas kartu, bukan hanya di latar."""

        for name, palette in self.palettes.items():
            with self.subTest(theme=name):
                self.assertGreaterEqual(
                    _contrast(palette["gold"], palette["surface-card"]), MIN_RATIO
                )

    def test_editor_surface_differs_from_window(self) -> None:
        """Area tulisan harus punya latar berbeda dari latar aplikasi."""

        for name, palette in self.palettes.items():
            with self.subTest(theme=name):
                self.assertIn("editor-bg", palette)
                self.assertNotEqual(palette["editor-bg"], palette["surface"])
                self.assertNotEqual(palette["editor-bg"], palette["surface-card"])

        text = (ROOT / "data" / "style.css").read_text(encoding="utf-8")
        block = re.search(r"\.ih-editor-surface\s*\{([^}]*)\}", text)
        self.assertIsNotNone(block)
        self.assertIn(
            "background-color: @ih-editor-bg;", block.group(1)  # type: ignore[union-attr]
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

    def test_stylesheet_lookup_includes_user_data_home(self) -> None:
        """Instalasi --user menaruh CSS di XDG_DATA_HOME, bukan XDG_DATA_DIRS."""

        source = (ROOT / "src" / "ui" / "theme.py").read_text(encoding="utf-8")
        self.assertIn("XDG_DATA_HOME", source)
        self.assertIn('Path.home() / ".local" / "share"', source)


if __name__ == "__main__":
    unittest.main()
