"""Coverage for all native theme presets and the static glass renderer."""
import re
import runpy
import struct
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = runpy.run_path(str(ROOT / "scripts/generate-podthings-logo.py"))


def bitmap_pixel(path, x, y):
    data = path.read_bytes()
    width, height = struct.unpack_from("<ii", data, 18)
    stride = (width * 3 + 3) & ~3
    start = struct.unpack_from("<I", data, 10)[0] + (height - 1 - y) * stride + x * 3
    return tuple(data[start:start + 3][::-1])


class ThemeCollectionTests(unittest.TestCase):
    def test_glass_has_a_distinct_static_treatment(self):
        folder = ROOT / "rockbox-firmware/wps/podthingsos-liquid-glass"
        sbs = folder.with_name(folder.name + ".320x240x16.sbs").read_text()
        self.assertIn("%X(menu-backdrop.bmp)", sbs)
        # Solid status strip, visible landscape, rim and frosted playback.
        self.assertEqual(bitmap_pixel(folder / "menu-backdrop.bmp", 160, 0),
                         tuple(bytes.fromhex(GEN["THEMES"]["liquid-glass"]["bg"])))
        self.assertNotEqual(bitmap_pixel(folder / "menu-backdrop.bmp", 4, 85),
                            bitmap_pixel(folder / "menu-backdrop.bmp", 315, 85))
        self.assertNotEqual(bitmap_pixel(folder / "backdrop.bmp", 160, 42),
                            bitmap_pixel(folder / "backdrop.bmp", 160, 43))
        self.assertNotEqual(bitmap_pixel(folder / "backdrop.bmp", 160, 48),
                            bitmap_pixel(folder / "backdrop.bmp", 160, 180))
        self.assertNotEqual(bitmap_pixel(folder / "selection.bmp", 150, 0),
                            bitmap_pixel(folder / "selection.bmp", 150, 1))
        self.assertEqual(bitmap_pixel(folder / "selection.bmp", 0, 0), (255, 0, 255))

    def test_landscape_provenance_and_readability(self):
        license_text = (ROOT / "assets/wallpapers/Yosemite-LICENSE.txt").read_text()
        self.assertIn("Ted Wakabayashi", license_text)
        self.assertIn("public domain worldwide", license_text)
        self.assertIn("commons.wikimedia.org/wiki/File:", license_text)
        raw = GEN["landscape_pixels"]()
        blurred = GEN["landscape_pixels"](blur=True)
        self.assertEqual((len(raw), len(raw[0])), (240, 320))
        self.assertNotEqual(raw[100][100], blurred[100][100])
        palette = GEN["THEMES"]["liquid-glass"]
        for y in range(240):
            for x in range(320):
                material = GEN["blend"](blurred[y][x], GEN["rgb"](palette["bg"]), .68)
                # The brightest possible panel stays below sRGB 0x70,
                # protecting small, near-white metadata from bright snow.
                self.assertLessEqual(max(material), 112)

    def test_every_palette_has_readable_text_contrast(self):
        def luminance(color):
            values = [v / 255 for v in bytes.fromhex(color)]
            linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4
                      for v in values]
            return sum(a * b for a, b in zip(linear, (.2126, .7152, .0722)))
        for name, palette in GEN["THEMES"].items():
            for text, background in (("fg", "accent"), ("fg", "bg"),
                                     ("muted", "card"), ("secondary", "card")):
                a, b = sorted((luminance(palette[text]), luminance(palette[background])))
                self.assertGreaterEqual((b + .05) / (a + .05), 4.5, (name, text, background))

    def test_all_presets_are_in_the_theme_catalog(self):
        listing = (ROOT / "rockbox-firmware/wps/WPSLIST").read_text()
        for name in GEN["THEMES"]:
            self.assertEqual(listing.count(f"Name: podthingsos-{name}\n"), 1)

    def test_default_alias_and_bright_palette_materials(self):
        themes = GEN["THEMES"]
        self.assertEqual(themes["default"], themes["current"])
        for name in ("pearl", "sky", "lavender"):
            self.assertGreater(min(GEN["rgb"](themes[name]["bg"])), 225)
            self.assertLess(max(GEN["rgb"](themes[name]["fg"])), 80)

    def test_volume_overlay_assets_and_selected_text_well(self):
        for name, palette in GEN["THEMES"].items():
            folder = ROOT / f"rockbox-firmware/wps/podthingsos-{name}"
            sbs = folder.with_name(folder.name + ".320x240x16.sbs").read_text()
            self.assertIn(f'%Vg({palette["accent"]},{palette["accent"]},{palette["fg"]})%Vs(gradient)', sbs)
            self.assertIn("|%Vs(clear)", sbs)
            # The entire padded text well must use the same foreground fill
            # as the pill, including during long-label scrolling.
            for x, y in ((12, 2), (150, 13), (283, 23)):
                self.assertEqual(bitmap_pixel(folder / "selection.bmp", x, y),
                                 GEN["rgb"](palette["accent"]))
            self.assertEqual(bitmap_pixel(folder / "volume-panel.bmp", 0, 0),
                             (255, 0, 255))
            self.assertEqual(bitmap_pixel(folder / "volume-panel.bmp", 116, 23),
                             GEN["rgb"](palette["card"]))
            self.assertEqual(bitmap_pixel(folder / "volume-track.bmp", 100, 3),
                             GEN["rgb"](palette["inset"]))
            self.assertEqual(bitmap_pixel(folder / "volume-fill.bmp", 100, 3),
                             GEN["rgb"](palette["soft"]))

    def test_final_theme_zip_is_complete_and_non_destructive(self):
        version = (ROOT / "VERSION").read_text().strip()
        path = ROOT / f"generated-artifacts/podthingsos-themes-{version}.zip"
        if not path.exists():
            self.skipTest("Run scripts/rockbox-theme-package.sh to validate a final ZIP")
        with zipfile.ZipFile(path) as archive:
            self.assertIsNone(archive.testzip())
            names = archive.namelist()
            self.assertFalse(any(n.endswith((".ipod", "config.cfg")) for n in names))
            self.assertIn("installer.config", names)
            license_path = ".podthingsloader/themes/podthings-licenses/Yosemite-LICENSE.txt"
            self.assertEqual(archive.read(license_path),
                             (ROOT / "assets/wallpapers/Yosemite-LICENSE.txt").read_bytes())
            for variant in GEN["THEMES"]:
                base = f".podthingsloader/wps/podthingsos-{variant}"
                self.assertIn(f".podthingsloader/themes/podthingsos-{variant}.cfg", names)
                for kind in ("wps", "sbs"):
                    skin = archive.read(f"{base}.{kind}").decode()
                    source = ROOT / f"rockbox-firmware/wps/podthingsos-{variant}.320x240x16.{kind}"
                    self.assertEqual(skin, source.read_text())
                    for bitmap in re.findall(r"[\w-]+\.bmp", skin):
                        self.assertIn(f"{base}/{bitmap}", names)
                for bitmap in (ROOT / f"rockbox-firmware/wps/podthingsos-{variant}").glob("*.bmp"):
                    if bitmap.name.startswith("photo-"):
                        continue  # Photo skins ship in its kit, not this 320x240 ZIP.
                    self.assertEqual(archive.read(f"{base}/{bitmap.name}"), bitmap.read_bytes())
            for size in (16, 22):
                self.assertIn(f".podthingsloader/fonts/{size}-PodThings-Sans.fnt", names)


if __name__ == "__main__":
    unittest.main()
