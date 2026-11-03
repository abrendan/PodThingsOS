"""Archive migration tests, separate from actual ARM-image validation."""
import runpy
import tempfile
import unittest
import zipfile
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NORMALIZE = runpy.run_path(str(ROOT / "scripts/brand-podthings-package.py"))["package"]


class PackageBrandingTest(unittest.TestCase):
    def test_runtime_names_and_failsafe_references(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.zip"
            output = Path(directory) / "output.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr(".podthingsloader/podthingsos.ipod", b"test fixture")
                archive.writestr(
                    ".podthingsloader/themes/rockbox_failsafe.cfg",
                    b"wps: /.podthingsloader/wps/rockbox_failsafe.wps\n",
                )
                archive.writestr(".podthingsloader/wps/rockbox_failsafe.wps", b"skin")
                archive.writestr(".podthingsloader/rockbox-info.txt", b"info")
                archive.writestr(".podthingsloader/rocks/demos/bounce.rock", b"old logo demo")
            NORMALIZE(source, output)
            with zipfile.ZipFile(output) as archive:
                self.assertTrue(all("rockbox" not in name.lower()
                                    for name in archive.namelist()))
                config = archive.read(".podthingsloader/themes/podthings_failsafe.cfg")
                self.assertIn(b"/.podthingsloader/wps/podthings_failsafe.wps", config)
                self.assertEqual(archive.read(".podthingsloader/podthings-info.txt"), b"info")
                self.assertNotIn(".podthingsloader/rocks/demos/bounce.rock",
                                 archive.namelist())

    def test_legacy_root_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr(".rockbox/rockbox.ipod", b"test fixture")
            with self.assertRaisesRegex(ValueError, "Unexpected install path"):
                NORMALIZE(source, Path(directory) / "output.zip")

    def test_alias_collision_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr(".podthingsloader/podthingsos.ipod", b"test fixture")
                archive.writestr(".podthingsloader/themes/rockbox_failsafe.cfg", b"old")
                archive.writestr(".podthingsloader/themes/podthings_failsafe.cfg", b"new")
            with self.assertRaisesRegex(ValueError, "Duplicate installed filename"):
                NORMALIZE(source, Path(directory) / "output.zip")

    def test_old_image_name_is_rejected_in_new_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr(".podthingsloader/podthings.ipod", b"old name")
            with self.assertRaisesRegex(ValueError, "Missing native"):
                NORMALIZE(source, Path(directory) / "output.zip")

    def test_expanded_palettes_and_current_default(self):
        themes = runpy.run_path(str(ROOT / "scripts/generate-podthings-logo.py"))["THEMES"]
        self.assertEqual(set(themes), {"current", "blue", "purple", "mint", "rose",
                                     "amber", "graphite", "liquid-glass", "default",
                                     "pearl", "sky", "lavender"})
        self.assertEqual(len({palette["bg"] for palette in themes.values()}), len(themes) - 1)
        for variant, palette in themes.items():
            name = f"podthingsos-{variant}"
            skin = (ROOT / f"rockbox-firmware/wps/{name}.320x240x16.wps").read_text()
            self.assertIn(palette["soft"], skin)
            self.assertIn(palette["secondary"], skin)
            bitmap = (ROOT / f"rockbox-firmware/wps/{name}/backdrop.bmp").read_bytes()
            self.assertEqual(struct.unpack_from("<ii", bitmap, 18), (320, 240))
            offset = struct.unpack_from("<I", bitmap, 10)[0] + 239 * 960
            if variant != "liquid-glass":
                self.assertEqual(bitmap[offset:offset + 3], bytes.fromhex(palette["bg"])[::-1])
        defaults = (ROOT / "rockbox-firmware/apps/settings_list.c").read_text()
        self.assertIn('#define DEFAULT_WPSNAME  "podthingsos-current"', defaults)
        self.assertIn('LCD_RGBPACK(0x0e, 0x0b, 0x16)', defaults)
        self.assertEqual(themes["purple"]["accent"], "7C3AED")

    def test_menu_labels_are_inside_the_rounded_selection(self):
        generator = runpy.run_path(str(ROOT / "scripts/generate-podthings-logo.py"))
        for variant, palette in generator["THEMES"].items():
            name = f"podthingsos-{variant}"
            status = (ROOT / f"rockbox-firmware/wps/{name}.320x240x16.sbs").read_text()
            self.assertIn("%Vi(-,12,50,296,182,1)", status)
            self.assertIn("%Lb(r,296,26)", status)
            self.assertIn("%Vl(r,12,2,272,22,1)", status)
            self.assertIn(f'%?Lc<%Vg({palette["accent"]},{palette["accent"]},{palette["fg"]})%Vs(gradient)|%Vs(clear)%Vb({palette["bg"]})>', status)
            self.assertIn("%s%LT", status)
            self.assertLess(status.index("%xd(S)"), status.index("%s%LT"))
            bitmap = (ROOT / f"rockbox-firmware/wps/{name}/selection.bmp").read_bytes()
            width, height = struct.unpack_from("<ii", bitmap, 18)
            self.assertEqual((width, height), (296, 26))
            stride = (width * 3 + 3) & ~3
            offset = struct.unpack_from("<I", bitmap, 10)[0]
            for y in range(4, 22):
                for x in (12, 283):
                    start = offset + (height - 1 - y) * stride + x * 3
                    self.assertEqual(bitmap[start:start + 3],
                                     bytes.fromhex(palette["accent"])[::-1])

    def test_playback_masks_status_and_quality_metadata(self):
        generator = runpy.run_path(str(ROOT / "scripts/generate-podthings-logo.py"))
        for variant in generator["THEMES"]:
            name = f"podthingsos-{variant}"
            folder = ROOT / f"rockbox-firmware/wps/{name}"
            def pixel(bitmap, x, y):
                data = (folder / bitmap).read_bytes()
                width, height = struct.unpack_from("<ii", data, 18)
                stride = (width * 3 + 3) & ~3
                offset = struct.unpack_from("<I", data, 10)[0]
                start = offset + (height - 1 - y) * stride + x * 3
                return data[start:start + 3][::-1]
            self.assertEqual(pixel("art-mask.bmp", 56, 56), b"\xff\x00\xff")
            for x, y in ((0, 0), (111, 0), (0, 111), (111, 111)):
                self.assertEqual(pixel("art-mask.bmp", x, y),
                                 pixel("backdrop.bmp", 24 + x, 58 + y))
            skin = (ROOT / f"rockbox-firmware/wps/{name}.320x240x16.wps").read_text()
            self.assertIn("%Cd%xd(M)", skin)
            self.assertIn("%Vl(P,36,4,92,16,2)", skin)
            self.assertIn("%?pN<%Vd(P)%Vd(L)|%Vd(I)>",skin)
            for tag in ("%fc", "%fk", "%fb"):
                self.assertIn(tag, skin)
            for kind in ("wps", "sbs"):
                content = (ROOT / f"rockbox-firmware/wps/{name}.320x240x16.{kind}").read_text()
                self.assertIn("%Fl(2,16-PodThings-Sans.fnt)", content)
                self.assertIn("%xd(B)%bl(2,3,16,6,-,noborder)", content)
                self.assertIn("%bl%%", content)

    def test_battery_frame_cannot_erase_the_live_fill(self):
        generator = runpy.run_path(str(ROOT / "scripts/generate-podthings-logo.py"))
        for variant, palette in generator["THEMES"].items():
            data = (ROOT / f"rockbox-firmware/wps/podthingsos-{variant}/battery.bmp").read_bytes()
            width, height = struct.unpack_from("<ii", data, 18)
            self.assertEqual((width, height), (22, 12))
            stride = (width * 3 + 3) & ~3
            offset = struct.unpack_from("<I", data, 10)[0]
            frame = [[tuple(data[offset + (height - 1 - y) * stride + x * 3:
                                  offset + (height - 1 - y) * stride + x * 3 + 3][::-1])
                      for x in range(width)] for y in range(height)]
            transparent = (255, 0, 255)
            background = generator["rgb"](palette["bg"])
            foreground = generator["rgb"](palette["soft"])
            for y in range(3, 9):
                for x in range(2, 18):
                    self.assertEqual(frame[y][x], transparent)
            self.assertEqual(frame[0][0], transparent)
            self.assertEqual(frame[5][21], foreground)
            # Match the native layer order: draw live fill FIRST, then overlay
            # the actual frame BMP. The old opaque frame made every level empty.
            for level in (0, 1, 10, 50, 87, 100):
                canvas = [[background] * width for _ in range(height)]
                filled = 16 * level // 100
                for y in range(3, 9):
                    for x in range(2, 2 + filled):
                        canvas[y][x] = foreground
                for y in range(height):
                    for x in range(width):
                        if frame[y][x] != transparent:
                            canvas[y][x] = frame[y][x]
                actual = sum(canvas[y][x] == foreground
                             for y in range(3, 9) for x in range(2, 18))
                self.assertEqual(actual, filled * 6, (variant, level))

    def test_battery_group_spacing_and_no_playback_status(self):
        generator = runpy.run_path(str(ROOT / "scripts/generate-podthings-logo.py"))
        font = generator["load_font"]("16-PodThings-Sans.bdf")
        self.assertLessEqual(generator["text_width"](font, "100%+"), 48)
        self.assertLessEqual(generator["text_width"](font, "PodThings OS"), 92)
        self.assertLessEqual(generator["text_width"](font, "23:59"), 56)
        self.assertEqual(294 - (242 + 48), 4)
        self.assertEqual(320 - (294 + 22), 4)
        for variant in generator["THEMES"]:
            for kind in ("wps", "sbs"):
                skin = (ROOT / f"rockbox-firmware/wps/podthingsos-{variant}.320x240x16.{kind}").read_text()
                self.assertIn("%V(294,6,22,12,2)", skin)
                self.assertIn("%V(242,4,48,16,2)", skin)
                self.assertIn("\n%ar%bl%%%?bc<+|>", skin)
                if kind == "wps":
                    self.assertIn("%V(132,4,56,16,2)", skin)
                    self.assertEqual(132 + 56 / 2, 320 / 2)
                if kind == "sbs":
                    self.assertNotIn("%mp", skin)
                    for label in ("Stopped", "Playing", "Paused", "Seeking", "Recording", "Radio"):
                        self.assertNotIn(label, skin)


if __name__ == "__main__":
    unittest.main()
