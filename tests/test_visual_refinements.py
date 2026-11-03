"""Native text rendering, Video timing and confirmation wiring."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_ipod_battery import function

ROOT = Path(__file__).resolve().parents[1]
LCD = ROOT / "rockbox-firmware/firmware/drivers/lcd-bitmap-common.c"
FLOW = ROOT / "rockbox-firmware/apps/plugins/pictureflow/pictureflow.c"


class VisualRefinements(unittest.TestCase):
    def run_c(self, source):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "test.c").write_text(source)
            subprocess.run(["gcc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                            "-no-pie", "-I", str(ROOT / "rockbox-firmware/firmware/export"),
                            str(path / "test.c"), "-o", str(path / "test")], check=True)
            subprocess.run([str(path / "test")], check=True,
                           env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0"})

    def test_font_smoothing_completely_removed(self):
        for path in (
            LCD,
            ROOT / "rockbox-firmware/firmware/export/lcd.h",
            ROOT / "rockbox-firmware/apps/settings.h",
            ROOT / "rockbox-firmware/apps/settings.c",
            ROOT / "rockbox-firmware/apps/settings_list.c",
            ROOT / "rockbox-firmware/apps/menus/main_menu.c",
            ROOT / "rockbox-firmware/apps/lang/english.lang",
        ):
            source = path.read_text()
            for removed in ("podthings_smooth_text", "lcd_set_smooth_text",
                            "lcd_smooth_glyph_part", "smooth_text_enabled",
                            "LANG_PODTHINGS_SMOOTH_TEXT", "Smooth Text (Beta)"):
                self.assertNotIn(removed, source, str(path))
        self.assertFalse((ROOT / "rockbox-firmware/firmware/export/podthings_text.h").exists())
        renderer = LCD.read_text()
        self.assertIn("bmp_part_fn = lcd_alpha_bitmap_part;", renderer)
        self.assertIn("bmp_part_fn = LCDFN(mono_bmp_part_helper);", renderer)

    def test_video_time_catchup_and_exact_transition_endpoints(self):
        source = FLOW.read_text()
        methods = "\n".join(("static int " if name == "video_animation_steps"
                            else "static void ") + function(source, name) for name in (
            "video_animation_steps", "update_cover_in_animation",
            "update_cover_out_animation"))
        self.run_c(r'''
#include <assert.h>
#define HZ 100
#define MIN(a,b) ((a)<(b)?(a):(b))
#define MAX(a,b) ((a)>(b)?(a):(b))
#define ZOOMIN_FRAME_COUNT 19
#define ZOOMIN_FRAME_DIST -5
#define ZOOMIN_FRAME_ANGLE 1
#define ZOOMIN_FRAME_FADE 13
#define ROTATE_FRAME_COUNT 15
#define ROTATE_FRAME_ANGLE 16
#define KEYFRAME_COUNT (ZOOMIN_FRAME_COUNT+ROTATE_FRAME_COUNT)
static int animation_steps=1,cover_animation_keyframe,extra_fade;
static struct {int distance,angle;} center_slide;
enum {pf_idle,pf_cover_in,pf_cover_out,pf_show_tracks};
static int pf_state;
''' + methods + r'''
int main(void) {
 assert(video_animation_steps(0)==1);
 assert(video_animation_steps(2)==1);
 assert(video_animation_steps(5)==3);
 assert(video_animation_steps(10)==6);
 assert(video_animation_steps(1000000)==8);
 for(int frames=1;frames<=8;frames++) {
  animation_steps=frames; pf_state=pf_cover_in;
  cover_animation_keyframe=extra_fade=0;
  center_slide.distance=center_slide.angle=0;
  int calls=0;
  while(pf_state==pf_cover_in) {update_cover_in_animation();assert(++calls<40);}
  assert(pf_state==pf_show_tracks && center_slide.distance==-95 &&
         center_slide.angle==259 && extra_fade==247);
  pf_state=pf_cover_out;
  while(pf_state==pf_cover_out) {update_cover_out_animation();assert(++calls<80);}
  assert(center_slide.distance==0 && center_slide.angle==0 && extra_fade==0);
 }
 return 0;
}
''')
        self.assertIn("#if defined(PODTHINGS_OS) && (defined(IPOD_VIDEO) || defined(IPOD_COLOR))", source)
        self.assertIn("speed = MIN(32768, speed * animation_steps);", source)

    def test_setting_and_safe_reboot_card_integration(self):
        menu = (ROOT / "rockbox-firmware/apps/menus/main_menu.c").read_text()
        for name, target in (("reboot_to_official_firmware","Apple Firmware"),
                             ("reboot_to_rockbox","Rockbox")):
            body = function(menu, name)
            self.assertLess(body.index(f'splash_set_reboot_target("{target}")'),
                            body.index("default_event_handler(SYS_REBOOT)"))
            self.assertGreater(body.index("splash_set_reboot_target(NULL)"),
                               body.index("default_event_handler(SYS_REBOOT)"))
            self.assertIn("podthings_cancel_",body)
        yesno = (ROOT / "rockbox-firmware/apps/gui/yesno.c").read_text()
        self.assertIn("splash_draw_card(display, &yn->card)", yesno)
        self.assertNotIn("set_viewport(&content)", yesno)  # no dangling scroll viewport


if __name__ == "__main__":
    unittest.main()
