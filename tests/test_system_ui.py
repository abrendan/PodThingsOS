"""Compile production UI logic against small native-platform shims."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    match = re.search(r"(?:static\s+)?(?:bool|void|unsigned|int|long)\s+" + name +
                      r"\s*\([^)]*\)\s*\{", source)
    if not match:
        raise AssertionError(name)
    start = match.start()
    at = source.index("{", start)
    depth = 1
    end = at + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


class SystemUITests(unittest.TestCase):
    def compile_run(self, source, extra=()):
        with tempfile.TemporaryDirectory() as tmp:
            c = Path(tmp) / "ui.c"
            binary = Path(tmp) / "ui"
            c.write_text(source)
            compiled = subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                            "-I", str(ROOT / "rockbox-firmware/apps"),
                            str(c), *map(str, extra), "-o", str(binary)],
                           capture_output=True, text=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0")
            result = subprocess.run([str(binary)], env=env,
                           capture_output=True, text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_scrub_state_and_actual_wps_routing(self):
        wps = (ROOT / "rockbox-firmware/apps/gui/wps.c").read_text()
        prefix = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdarg.h>
#include "podthings_scrub.h"
#define HZ 100
#define MAX_PATH 260
#define AFMT_UNKNOWN 0
#define ACTION_NONE 0
#define ACTION_WPS_BROWSE 1
#define ACTION_WPS_PODTHINGS_SCRUB 20
#define ACTION_UNKNOWN 21
#define ACTION_REDRAW 22
#define ACTION_WPS_VOLUP 2
#define ACTION_WPS_VOLDOWN 3
#define ACTION_WPS_PLAY 4
#define ACTION_REMOTE 1
#define WPS 0
struct mp3entry { char path[MAX_PATH]; uint32_t elapsed,length; int codectype; };
struct wps_state { struct mp3entry *id3; int ff_rewind_count; };
static struct wps_state state;
static struct { bool party_mode; } global_settings;
static struct podthings_scrub wheel_scrub;
static char scrub_path[MAX_PATH];
static volatile unsigned scrub_track_epoch;
static unsigned scrub_epoch, current_tick, remote, seeks, warnings, last_seek;
static struct wps_state *get_wps_state(void) { return &state; }
static unsigned get_action_statuscode(void *p) { (void)p; return remote; }
static void skin_request_full_update(int v) { (void)v; }
static void splash(int t,const char *s) { (void)t; (void)s; warnings++; }
static void audio_ff_rewind(unsigned n) { ++seeks; last_seek=n; }
#define strlcpy(d,s,n) snprintf(d,n,"%s",s)
'''
        methods = "\n".join(function(wps, n) for n in
                            ("podthings_scrub_active", "cancel_wheel_scrub",
                             "wheel_scrub_action"))
        checks = r'''
static int action(int a,unsigned tick) {
 current_tick=tick; wheel_scrub_action(&a,&state); return a;
}
int main(void) {
 struct podthings_scrub s={0}; uint32_t pos=999;
 assert(!podthings_scrub_begin(&s,0,0,0));
 assert(!podthings_scrub_begin(&s,0,UINT32_MAX,0));
 assert(podthings_scrub_begin(&s,10000,20000,UINT32_MAX-20));
 podthings_scrub_move(&s,1,UINT32_MAX,UINT32_MAX-10);
 assert(s.target==19999 && s.dirty);
 assert(!podthings_scrub_tick(&s,5,30,500,&pos));
 assert(podthings_scrub_tick(&s,25,30,500,&pos) && pos==19999 && s.active);
 assert(!podthings_scrub_tick(&s,30,30,500,&pos)); /* no repeated seeks */
 podthings_scrub_move(&s,-1,UINT32_MAX,40); assert(s.target==0);
 assert(podthings_scrub_tick(&s,540,30,500,&pos) && pos==0 && !s.active);
 assert(podthings_scrub_begin(&s,UINT32_MAX,100,0) && s.target==99);
 podthings_scrub_move(&s,-1,50,1); podthings_scrub_follow(&s,10);
 assert(s.target==49); assert(!podthings_scrub_finish(&s,false,&pos));
 assert(podthings_scrub_begin(&s,10,100,0));
 assert(!podthings_scrub_tick(&s,500,30,500,&pos) && !s.active);

 struct mp3entry song={"/Music/first.mp3",10000,60000,1};
 state.id3=&song;
 assert(action(ACTION_WPS_VOLUP,0)==ACTION_WPS_VOLUP); /* normal volume */
 assert(action(ACTION_WPS_PODTHINGS_SCRUB,1)==ACTION_NONE && podthings_scrub_active());
 action(ACTION_UNKNOWN,2); action(ACTION_REDRAW,2);
 assert(podthings_scrub_active()); /* unmapped button-down / LCD wake */
 assert(action(ACTION_NONE,2)==ACTION_NONE && seeks==0); /* no move = no seek */
 assert(action(ACTION_WPS_VOLUP,3)==ACTION_NONE);
 assert(state.ff_rewind_count==5000 && song.elapsed==10000 && seeks==0);
 assert(action(ACTION_NONE,20)==ACTION_NONE && seeks==0);
 action(ACTION_NONE,37);
 assert(seeks==1 && last_seek==15000 && song.elapsed==15000);
 assert(state.ff_rewind_count==0 && podthings_scrub_active());
 action(ACTION_NONE,45); assert(seeks==1);
 action(ACTION_NONE,503); assert(!podthings_scrub_active());
 assert(action(ACTION_WPS_VOLDOWN,504)==ACTION_WPS_VOLDOWN);
 action(ACTION_WPS_PODTHINGS_SCRUB,600); action(ACTION_WPS_VOLDOWN,601);
 action(ACTION_UNKNOWN,602); assert(podthings_scrub_active()); /* Center down */
 action(ACTION_WPS_PODTHINGS_SCRUB,602);
 assert(seeks==2 && last_seek==10000 && !podthings_scrub_active());
 action(ACTION_WPS_PODTHINGS_SCRUB,700); action(ACTION_WPS_VOLUP,701);
 assert(action(ACTION_WPS_BROWSE,702)==ACTION_WPS_BROWSE &&
        !podthings_scrub_active() && seeks==2); /* Menu is Back, never a toggle */
 action(ACTION_WPS_PODTHINGS_SCRUB,800); action(ACTION_WPS_VOLUP,801);
 assert(action(ACTION_WPS_PLAY,802)==ACTION_WPS_PLAY && seeks==3);
 assert(!podthings_scrub_active()); /* native pause action remains intact */
 action(ACTION_WPS_PODTHINGS_SCRUB,900); action(ACTION_WPS_VOLUP,901);
 strcpy(song.path,"/Music/next.mp3"); action(ACTION_NONE,940);
 assert(!podthings_scrub_active() && seeks==3 && state.ff_rewind_count==0);
 action(ACTION_WPS_PODTHINGS_SCRUB,1000); action(ACTION_WPS_VOLUP,1001);
 ++scrub_track_epoch; action(ACTION_NONE,1040); /* even repeat-one same pathname */
 assert(!podthings_scrub_active() && seeks==3);
 action(ACTION_WPS_PODTHINGS_SCRUB,1100); action(ACTION_WPS_VOLUP,1101);
 remote=ACTION_REMOTE;
 assert(action(ACTION_WPS_VOLUP,1102)==ACTION_WPS_VOLUP && seeks==3);
 assert(action(ACTION_WPS_BROWSE,1103)==ACTION_WPS_BROWSE);
 remote=0; song.length=0; action(ACTION_WPS_PODTHINGS_SCRUB,1200);
 assert(warnings==1 && !podthings_scrub_active());
 song.length=60000;
 action(ACTION_WPS_PODTHINGS_SCRUB,1300); action(ACTION_WPS_VOLUP,1301);
 state.id3=NULL; action(ACTION_NONE,1340);
 assert(!podthings_scrub_active() && state.ff_rewind_count==0 && seeks==3);
 state.id3=&song;
 action(ACTION_WPS_PODTHINGS_SCRUB,1400); action(ACTION_WPS_VOLUP,1401);
 global_settings.party_mode=true; action(ACTION_NONE,1440);
 assert(!podthings_scrub_active() && seeks==3);
 return 0;
}
'''
        self.compile_run(prefix + methods + checks,
                         [ROOT / "rockbox-firmware/apps/podthings_scrub.c"])
        keymap=(ROOT / "rockbox-firmware/apps/keymaps/keymap-ipod.c").read_text()
        self.assertRegex(keymap,r"ACTION_WPS_PODTHINGS_SCRUB,\s*BUTTON_SELECT\|BUTTON_REL")
        self.assertRegex(keymap,r"ACTION_WPS_BROWSE,\s*BUTTON_MENU\|BUTTON_REL")
        self.assertIn("case ACTION_WPS_PODTHINGS_SCRUB:",function(wps,"do_party_mode"))

    def test_actual_popup_renderer_bounds_and_progress(self):
        source = (ROOT / "rockbox-firmware/apps/gui/splash.c").read_text()
        prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define MIN(a,b) ((a)<(b)?(a):(b))
#define MAX(a,b) ((a)>(b)?(a):(b))
#define LCD_RGBPACK(r,g,b) (((r)<<16)|((g)<<8)|(b))
#define RGB_UNPACK_RED(c) (((c)>>16)&255)
#define RGB_UNPACK_GREEN(c) (((c)>>8)&255)
#define RGB_UNPACK_BLUE(c) ((c)&255)
#define VP_FLAG_ALIGN_CENTER 1
#define DRMODE_FG 1
#define RECT_SPACING 12
struct viewport { int width,height,drawmode; unsigned flags; };
struct screen {
 void (*set_foreground)(unsigned);
 void (*fillrect)(int,int,int,int);
 int (*getcharheight)(void);
 int (*getstringsize)(const unsigned char *,int *,int *);
 void (*putsxy)(int,int,const unsigned char *);
};
static struct { unsigned bg_color,fg_color,lss_color; } global_settings;
static unsigned current_tick,foreground,pixels[240][320];
static struct viewport vp;
static char label[20];
static void set_fg(unsigned n) { foreground=n; }
static void rect(int x,int y,int w,int h) {
 assert(x>=0 && y>=0 && w>=0 && h>=0);
 assert(x+w<=vp.width && y+h<=vp.height);
 for(int j=y;j<y+h;j++) for(int i=x;i<x+w;i++) pixels[j][i]=foreground;
}
static int charheight(void) { return 22; }
static int measure(const unsigned char *s,int *w,int *h) {
 *w=strlen((const char *)s)*9; *h=22; return *w;
}
static void text(int x,int y,const unsigned char *s) {
 int w,h; measure(s,&w,&h);
 assert(x>=0 && y>=0 && x+w<=vp.width && y+h<=vp.height);
 assert(!(vp.flags&VP_FLAG_ALIGN_CENTER));
 snprintf(label,sizeof(label),"%s",s);
}
'''
        methods = "\n".join(function(source, n) for n in
                            ("popup_foreground", "popup_blend", "popup_round_fill",
                             "popup_card", "popup_progress"))
        checks = r'''
int main(void) {
 struct screen screen={set_fg,rect,charheight,measure,text};
 unsigned accents[]={0x73e1d0,0x7cbfff,0xa78bfa};
 for(unsigned c=0;c<3;c++) for(int w=240;w<=296;w+=14)
 for(int h=80;h<=240;h+=40) {
  vp=(struct viewport){w,h,0,VP_FLAG_ALIGN_CENTER};
  global_settings.bg_color=0x161427;
  global_settings.fg_color=0xfaf8ff;
  global_settings.lss_color=accents[c];
  memset(pixels,0,sizeof(pixels)); popup_card(&screen,&vp);
  assert(pixels[0][0]==0); /* corners remain transparent */
  assert(pixels[8][w/2]==accents[c]);
  assert(pixels[h/2][w/2]!=global_settings.bg_color);
  for(int n=-5;n<=105;n+=5) {
   popup_card(&screen,&vp); label[0]=0;
   popup_progress(&screen,&vp,n,100);
   char expected[20];snprintf(expected,sizeof(expected),"%d%%",MAX(0,MIN(n,100)));
   assert(!strcmp(label,expected) && vp.flags==VP_FLAG_ALIGN_CENTER);
  }
  for(unsigned tick=0;tick<1000;tick+=7) {
   current_tick=tick; label[0]=0; popup_card(&screen,&vp);
   popup_progress(&screen,&vp,700,0);
   assert(!label[0] && vp.flags==VP_FLAG_ALIGN_CENTER);
  }
 }
 global_settings.bg_color=global_settings.fg_color=0xffffff;
 assert(popup_foreground()!=0xffffff);
 global_settings.bg_color=global_settings.fg_color=0;
 assert(popup_foreground()!=0);
 return 0;
}
'''
        self.compile_run(prefix + methods + checks)
        # Repeated progress calls must not add the decorative header to the
        # remembered content height, causing the modal to grow every frame.
        self.assertIn("height - 2*RECT_SPACING - SPLASH_TOP_DETAIL", source)
        root = (ROOT / "rockbox-firmware/apps/root_menu.c").read_text()
        self.assertIn("splash_progress(stat->processed_entries,0,", root)
        for path in (ROOT / "rockbox-firmware/wps").glob("podthings*.wps"):
            skin=path.read_text()
            self.assertIn("%?pJ<%Vd(s)%Vd(t)|%?mv(2)<%Vd(v)%Vd(w)%Vd(z)|%Vd(n)%Vd(t)>>",skin)
            self.assertIn("noborder,slider,D",skin)
            self.assertNotIn("turn wheel",skin)


if __name__ == "__main__":
    unittest.main()
