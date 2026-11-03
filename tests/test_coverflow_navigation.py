"""Execute the actual root dispatcher and Cover Flow bridge, not a model."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_coverflow_refinements import function

ROOT = Path(__file__).resolve().parents[1]


class CoverFlowNavigation(unittest.TestCase):
    def test_dispatcher_back_chain_on_both_ipods(self):
        dispatcher = function("rockbox-firmware/apps/root_menu.c", "load_screen")
        bridge = "\n".join(function("rockbox-firmware/apps/podthings_music.c", name)
                           for name in ("podthings_coverflow_wps_return",
                                        "podthings_coverflow"))
        code = r"""
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#define PODTHINGS_OS 1
#define HZ 100
#define PLUGIN_DEMOS_DIR "/plugins/demos"
enum {GO_TO_ROOT=-1, GO_TO_PREVIOUS=-2, GO_TO_PREVIOUS_BROWSER=-3,
      GO_TO_PREVIOUS_MUSIC=-4};
enum {GO_TO_FILEBROWSER, GO_TO_DBBROWSER, GO_TO_WPS, GO_TO_MAINMENU,
      GO_TO_SYSTEM_SCREEN, GO_TO_PLUGIN, GO_TO_BROWSEPLUGINS,
      GO_TO_MUSIC, GO_TO_EXTRAS, GO_TO_COVER_FLOW, GO_TO_MUSIC_SHUFFLE,
      SCREEN_COUNT};
enum current_activity {ACTIVITY_UNKNOWN, ACTIVITY_PLUGINBROWSER,
                       ACTIVITY_SETTINGS, ACTIVITY_SYSTEMSCREEN};
enum {PLUGIN_OK, PLUGIN_GOTO_WPS};
static struct {char last_screen;} global_status;
static int last_screen=GO_TO_ROOT, menu_result, plugin_result;
static bool usable=true, return_to_coverflow, expect_resume;
static int status_saves, plugin_calls;
static void status_save(bool force) {(void)force; ++status_saves;}
static void push_current_activity(enum current_activity a) {(void)a;}
static void pop_current_activity(void) {}
static void pop_current_activity_without_refresh(void) {}
static void tagtree_podthings_take_shuffle(void) {}
static bool tagcache_is_usable(void) {return usable;}
static void splash(int ticks,const char *s) {(void)ticks;(void)s;}
static int plugin_load(const char *path,const void *parameter)
{
    (void)path; ++plugin_calls;
    assert((parameter!=NULL)==expect_resume);
    return plugin_result;
}
""" + bridge + r"""
static int menu(void *p) {(void)p; return menu_result;}
static struct {int (*function)(void *); void *param;} items[SCREEN_COUNT];
""" + dispatcher + r"""
static int dispatch(int screen)
{
    int result=load_screen(screen);
    /* Same GO_TO_PREVIOUS resolution as root_menu's main loop. */
    return result==GO_TO_PREVIOUS ? last_screen : result;
}
static void enter_flow(void)
{
    last_screen=GO_TO_ROOT; return_to_coverflow=false; expect_resume=false;
    menu_result=GO_TO_COVER_FLOW;
    assert(dispatch(GO_TO_MUSIC)==GO_TO_COVER_FLOW);
    assert(last_screen==GO_TO_MUSIC);
}
static void leave_music(void)
{
    menu_result=GO_TO_PREVIOUS;
    assert(dispatch(GO_TO_MUSIC)==GO_TO_ROOT);
    /* Reentering Music must not resurrect the previous child either. */
    assert(dispatch(GO_TO_MUSIC)==GO_TO_ROOT);
}
int main(void)
{
    for(int i=0;i<SCREEN_COUNT;i++) items[i].function=menu;
    items[GO_TO_COVER_FLOW].function=podthings_coverflow;
    for(int repeat=0;repeat<10;repeat++) {
        enter_flow(); plugin_result=PLUGIN_OK;
        assert(dispatch(GO_TO_COVER_FLOW)==GO_TO_MUSIC);
        assert(!return_to_coverflow);
        leave_music();

        enter_flow(); plugin_result=PLUGIN_GOTO_WPS;
        assert(dispatch(GO_TO_COVER_FLOW)==GO_TO_WPS);
        assert(return_to_coverflow);
        menu_result=GO_TO_PREVIOUS_BROWSER;
        assert(dispatch(GO_TO_WPS)==GO_TO_COVER_FLOW);
        expect_resume=true; plugin_result=PLUGIN_OK;
        assert(dispatch(GO_TO_COVER_FLOW)==GO_TO_MUSIC);
        assert(!return_to_coverflow);
        leave_music();

        /* Alternate Now Playing Back result, not just previous-browser. */
        enter_flow(); plugin_result=PLUGIN_GOTO_WPS;
        assert(dispatch(GO_TO_COVER_FLOW)==GO_TO_WPS);
        menu_result=GO_TO_PREVIOUS;
        assert(dispatch(GO_TO_WPS)==GO_TO_COVER_FLOW);
        expect_resume=true; plugin_result=PLUGIN_OK;
        assert(dispatch(GO_TO_COVER_FLOW)==GO_TO_MUSIC);
        leave_music();

        /* Missing database must also return to Music, never stale history. */
        enter_flow(); usable=false;
        int before=plugin_calls;
        assert(dispatch(GO_TO_COVER_FLOW)==GO_TO_MUSIC);
        assert(plugin_calls==before);
        usable=true; leave_music();

        /* Browse Music retains its parent, then Music exits to Home. */
        last_screen=GO_TO_ROOT; menu_result=GO_TO_DBBROWSER;
        assert(dispatch(GO_TO_MUSIC)==GO_TO_DBBROWSER);
        menu_result=GO_TO_PREVIOUS;
        assert(dispatch(GO_TO_DBBROWSER)==GO_TO_MUSIC);
        leave_music();

        /* Extras uses the same parent rule without affecting other routes. */
        last_screen=GO_TO_PLUGIN; menu_result=GO_TO_PREVIOUS;
        assert(dispatch(GO_TO_EXTRAS)==GO_TO_ROOT);
        last_screen=GO_TO_MUSIC; menu_result=GO_TO_WPS;
        assert(dispatch(GO_TO_MUSIC)==GO_TO_WPS);
    }
    assert(status_saves>0);
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            source, exe = Path(tmp) / "nav.c", Path(tmp) / "nav"
            source.write_text(code)
            for target in ("IPOD_VIDEO", "IPOD_6G"):
                with self.subTest(target=target):
                    subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra",
                                    "-Werror", "-fsanitize=undefined",
                                    "-fno-sanitize-recover=all", f"-D{target}",
                                    str(source), "-o", str(exe)], check=True)
                    subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    unittest.main()
