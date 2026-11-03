"""Coverage/geometry checks use the generated glyphs actually built by Rockbox."""
from pathlib import Path
import re
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UnicodeFontTests(unittest.TestCase):
    def test_native_compiled_glyph_widths_and_offsets(self):
        validate = runpy.run_path(str(ROOT / "scripts/package-podthings-release.py"))[
            "validate_unicode_font"]
        for height in (16, 22):
            path = ROOT / (
                "generated-artifacts/podthings-theme-package/.podthingsloader/"
                f"fonts/{height}-PodThings-Sans.fnt")
            validate(path.read_bytes(), height)

    def test_common_cjk_and_other_languages_have_real_glyphs(self):
        parse = runpy.run_path(str(ROOT / "scripts/generate-podthings-fonts.py"))["glyphs"]
        for height, ascent, descent in ((22, 17, 5), (16, 13, 3)):
            path = ROOT / f"rockbox-firmware/fonts/{height}-PodThings-Sans.bdf"
            glyphs = parse(path.read_text())
            self.assertGreater(len(glyphs), 55000)
            self.assertEqual(len(re.findall(r"^DWIDTH ", path.read_text(), re.M)),
                             len(glyphs))
            for start, end in ((0xac00, 0xd7a3), (0x4e00, 0x9fff)):
                self.assertTrue(all(c in glyphs for c in range(start, end + 1)))
            for text in ("한국어 음악", "日本語 音楽 かな カタカナ", "简体中文", "繁體中文",
                         "Ελληνικά", "Русский", "العربية", "עברית", "हिन्दी", "ไทย"):
                for char in text:
                    glyph = glyphs[ord(char)]
                    self.assertNotEqual(glyph.split("BITMAP\n")[1],
                                        glyphs[0xfffd].split("BITMAP\n")[1])
                    w, h, x, y = map(int, re.search(
                        r"^BBX (\d+) (\d+) (-?\d+) (-?\d+)", glyph, re.M).groups())
                    self.assertLessEqual(h + y, ascent, (height, char))
                    self.assertGreaterEqual(y, -descent, (height, char))
            self.assertIn(f"FONT_ASCENT {ascent}", path.read_text()[:500])

    def test_theme_defaults_and_conservative_font_upgrade(self):
        defaults = (ROOT / "rockbox-firmware/apps/settings_list.c").read_text()
        self.assertIn('#define DEFAULT_FONTNAME "22-PodThings-Sans"', defaults)
        settings = (ROOT / "rockbox-firmware/apps/settings.c").read_text()
        self.assertIn('!strcmp(global_settings.font_file, "18-Adobe-Helvetica")', settings)
        for variant in ("current", "blue", "purple"):
            self.assertIn(f'!strcmp(global_settings.wps_file, "podthingsos-{variant}")',
                          settings)
            skin = (ROOT / f"rockbox-firmware/wps/podthingsos-{variant}.320x240x16.wps").read_text()
            self.assertIn("%Fl(2,16-PodThings-Sans.fnt)", skin)
        logo = (ROOT / "scripts/generate-podthings-logo.py").read_text()
        self.assertIn('credit = "Built by abrendan"', logo)
        self.assertNotIn('credit = "Built on Rockbox"', logo)
        main = (ROOT / "rockbox-firmware/apps/main.c").read_text()
        self.assertIn('PodThing OS - %s - Based on Rockbox', main)
        self.assertLessEqual(len("PodThing OS - 0.5 - Based on Rockbox") * 6, 320)


if __name__ == "__main__":
    unittest.main()
