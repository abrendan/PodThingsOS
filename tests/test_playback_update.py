"""Metadata fit and the native engine's transient volume condition."""
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PlaybackUpdateTests(unittest.TestCase):
    def test_smaller_metadata_and_transient_indicator_in_every_palette(self):
        generator = runpy.run_path(str(ROOT / "scripts/generate-podthings-logo.py"))
        font = generator["load_font"]("16-PodThings-Sans.bdf")
        for value in ("Here Comes the Sun", "Blinding Lights", "Bohemian Rhapsody"):
            self.assertLessEqual(generator["text_width"](font, value), 146, value)
        for value in ("Vol -74 dB", "Vol +6 dB", "Vol -74.0 dB"):
            self.assertLessEqual(generator["text_width"](font, value), 88, value)
        for variant in generator["THEMES"]:
            skin = (ROOT / f"rockbox-firmware/wps/podthingsos-{variant}.320x240x16.wps"
                    ).read_text()
            for viewport in ("150,60,146,20,2", "150,90,146,18,2",
                             "150,117,146,18,2"):
                self.assertIn(f"%V({viewport})", skin)
            self.assertIn("%Vl(t,16,217,288,20,2)", skin)
            self.assertIn("%?mv(2)<%Vd(v)%Vd(w)%Vd(z)|%Vd(n)%Vd(t)>", skin)
            self.assertIn("%Vl(v,12,196,296,40,2)", skin)
            self.assertIn("%pv(0,0,264,6,-,image,F,backdrop,T)", skin)
            self.assertEqual(skin.count("Volume %pv"), 1)
            self.assertNotIn("Vol %pv", skin)
            for tag in ("%s%?it", "%s%?ia", "%s%?id", "%fc", "%fk", "%fb"):
                self.assertIn(tag, skin)

    def test_production_volume_condition_stays_hidden_until_change_and_expires(self):
        source = (ROOT / "rockbox-firmware/apps/gui/skin_engine/skin_tokens.c"
                  ).read_text()
        condition = source.split("case SKIN_TOKEN_BUTTON_VOLUME:", 1)[1].split(
            "case SKIN_TOKEN_LASTTOUCH:", 1)[0]
        program = """
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#define TIME_BEFORE(a,b) ((int32_t)((uint32_t)(a)-(uint32_t)(b)) < 0)
static uint32_t current_tick;
static struct { uint32_t last_volume_change; } global_status;
struct token { union { int i; } value; };
static const char *visible(struct token *token) {
""" + condition + """
}
int main(void) {
    struct token token = { .value.i = 200 };
    current_tick = 1;
    assert(visible(&token) == NULL);
    global_status.last_volume_change = 100;
    current_tick = 100;
    assert(visible(&token));
    current_tick = 299;
    assert(visible(&token));
    current_tick = 300;
    assert(visible(&token) == NULL);
    global_status.last_volume_change = 301;
    current_tick = 301;
    assert(visible(&token));
    current_tick = 502;
    assert(visible(&token) == NULL);
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "volume.c").write_text(program)
            result = subprocess.run(
                ["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                 str(path / "volume.c"), "-o", str(path / "volume")],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(path / "volume")], check=True)
