"""Run the production C helpers for the 0.7.3 navigation/theme changes."""
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def function(path, name):
    source = (ROOT / path).read_text()
    offset = source.index(name + "(")
    start = source.rfind("\n", 0, offset) + 1
    brace = source.index("{", offset)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


HEADER = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <stdlib.h>
#define PODTHINGS_OS 1
#define MAX_PATH 260
#define ROCKBOX_DIR "/.podthingsloader"
#define MIN(a,b) ((a)<(b)?(a):(b))
#define MAX(a,b) ((a)>(b)?(a):(b))
"""


class Refinements(unittest.TestCase):
    def run_c(self, code):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "test.c"
            exe = Path(tmp) / "test"
            source.write_text(HEADER + code)
            subprocess.run(
                ["gcc", "-std=c11", "-Wall", "-Wextra", "-no-pie",
                 "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                 str(source), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True,
                           env={"ASAN_OPTIONS": "detect_leaks=0"})

    def test_actual_titles_keep_metadata_without_added_numbers(self):
        production = function(
            "rockbox-firmware/apps/plugins/pictureflow/pictureflow.c",
            "pf_tcs_retrieve_track_title")
        self.run_c(r"""
#define UNTAGGED "<Untagged>"
#define tag_virt_basename 1
static struct {const char *result; int idx_id;} tcs;
static struct {char names[512];} pf_tracks;
static bool space_available=true;
static bool track_buffer_avail(int n) {return space_available && n<512;}
static bool retrieve(void *unused,int id,int tag,char *out,int size)
{(void)unused;(void)id;(void)tag;snprintf(out,size,"01. Butterfly.flac");return true;}
static struct {
    int (*strcmp)(const char*,const char*);
    size_t (*strlen)(const char*);
    int (*snprintf)(char*,size_t,const char*,...);
    bool (*tagcache_retrieve)(void*,int,int,char*,int);
} api={strcmp,strlen,snprintf,retrieve}, *rb=&api;
""" + production + r"""
int main(void) {
    tcs.result="01. Butterfly";
    assert(pf_tcs_retrieve_track_title(7,1,1)==13);
    assert(!strcmp(pf_tracks.names+7,"01. Butterfly"));
    tcs.result="1999";
    assert(pf_tcs_retrieve_track_title(0,2,5)==4);
    assert(!strcmp(pf_tracks.names,"1999"));
    tcs.result=UNTAGGED;
    assert(pf_tcs_retrieve_track_title(0,1,1)>0);
    assert(!strcmp(pf_tracks.names,"01. Butterfly.flac"));
    space_available=false;
    assert(pf_tcs_retrieve_track_title(0,1,1)==0);
}
""")

    def test_actual_restoration_keeps_selection_inside_track_window(self):
        source = (ROOT / "rockbox-firmware/apps/plugins/pictureflow/pictureflow.c").read_text()
        body = source.split("if (show_track_list() && pf_tracks.count>0)", 1)[1]
        body = body[body.index("{") + 1:body.index("}")]
        self.run_c(r"""
static struct {int count,sel,list_visible,list_start,last_sel;} pf_tracks;
static struct {int last_track;} pf_cfg;
static void restore(void) {
""" + body + r"""
}
int main(void) {
    for (int count=1;count<=100;count++)
      for(int visible=1;visible<=MIN(count,12);visible++)
        for(int saved=0;saved<count+10;saved++) {
          pf_tracks.count=count; pf_tracks.list_visible=visible;
          pf_cfg.last_track=saved; restore();
          assert(pf_tracks.sel>=0 && pf_tracks.sel<count);
          assert(pf_tracks.list_start>=0);
          assert(pf_tracks.list_start+visible<=count);
          assert(pf_tracks.sel>=pf_tracks.list_start);
          assert(pf_tracks.sel<pf_tracks.list_start+visible);
          assert(pf_tracks.last_sel==-1);
        }
}
""")

    def test_actual_legacy_resource_paths_do_not_rewrite_user_directories(self):
        config = function("rockbox-firmware/apps/settings.c", "copy_filename_setting")
        images = function("rockbox-firmware/apps/gui/skin_engine/skin_parser.c",
                          "get_image_filename")
        self.run_c(r"""
struct filename_setting {const char *prefix,*suffix; int max_len;};
static void strmemccpy(char *out,const char *src,size_t size)
{if(size) snprintf(out,size,"%s",src);}
static void path_append(char *out,const char *base,const char *name,int size)
{if(name[0]=='/') snprintf(out,size,"%s",name);
 else snprintf(out,size,"%s/%s",base,name);}
""" + config + images + r"""
int main(void) {
    char out[260];
    struct filename_setting theme={ROCKBOX_DIR "/wps/",".wps",64};
    assert(copy_filename_setting(out,sizeof(out),"/.rockbox/wps/Legacy.wps",&theme));
    assert(!strcmp(out,"Legacy"));
    assert(copy_filename_setting(out,sizeof(out),ROCKBOX_DIR "/wps/Legacy.wps",&theme));
    assert(!strcmp(out,"Legacy"));
    struct filename_setting directory={NULL,NULL,260};
    assert(copy_filename_setting(out,sizeof(out),"/.rockbox/MyPlaylists",&directory));
    assert(!strcmp(out,"/.rockbox/MyPlaylists"));
    get_image_filename("/.rockbox/wps/Legacy/art.bmp","ignored",out,sizeof(out));
    assert(!strcmp(out,ROCKBOX_DIR "/wps/Legacy/art.bmp"));
    get_image_filename("art.bmp",ROCKBOX_DIR "/wps/Legacy",out,sizeof(out));
    assert(!strcmp(out,ROCKBOX_DIR "/wps/Legacy/art.bmp"));
    get_image_filename("/Custom/art.bmp","ignored",out,sizeof(out));
    assert(!strcmp(out,"/Custom/art.bmp"));
    get_image_filename("/.rockbox2/art.bmp","ignored",out,sizeof(out));
    assert(!strcmp(out,"/.rockbox2/art.bmp"));
}
""")

    def test_actual_shuffle_request_is_consumed_only_once(self):
        first = function("rockbox-firmware/apps/tagtree.c", "tagtree_podthings_request_shuffle")
        second = function("rockbox-firmware/apps/tagtree.c", "tagtree_podthings_take_shuffle")
        self.run_c("static bool podthings_auto_shuffle;\n" + first + second + r"""
int main(void) {
    assert(!tagtree_podthings_take_shuffle());
    tagtree_podthings_request_shuffle();
    tagtree_podthings_request_shuffle();
    assert(tagtree_podthings_take_shuffle());
    assert(!tagtree_podthings_take_shuffle());
    tagtree_podthings_request_shuffle();
    assert(tagtree_podthings_take_shuffle());
    assert(!tagtree_podthings_take_shuffle());
}
""")

    def test_no_branding_now_playing_shows_ipod_without_the_logo(self):
        for variant in ("current","blue","purple"):
            skin=(ROOT/f"rockbox-firmware/wps/podthingsos-{variant}.320x240x16.wps").read_text()
            self.assertIn("%?pN<%Vd(P)%Vd(L)|%Vd(I)>",skin)
            self.assertIn("%Vl(I,12,4,116,16,2)",skin)
            self.assertIn("\niPod\n",skin)
            # The logo viewport is enabled only in the branded branch.
            self.assertNotIn("|%Vd(L)",skin)

    def test_branding_preferences_are_independent_and_not_theme_gated(self):
        source = (ROOT / "rockbox-firmware/apps/gui/skin_engine/skin_tokens.c").read_text()
        begin = source.index("if (token->type == SKIN_TOKEN_PODTHINGS_WPS_BRANDING)")
        condition = source[begin:source.index(";", begin) + 1]
        self.assertLess(begin, source.index("if (id3)", begin))
        root = (ROOT / "rockbox-firmware/apps/root_menu.c").read_text()
        begin = root.index("snprintf(podthings_home_title")
        caption = root[begin:root.index(";", begin) + 1]
        self.run_c(r"""
#define SKIN_TOKEN_PODTHINGS_WPS_BRANDING 1
static struct {bool podthings_menu_branding,podthings_wps_branding;} global_settings;
static char podthings_home_title[16];
static const char *branding(void) {
    struct {int type;} value={SKIN_TOKEN_PODTHINGS_WPS_BRANDING}, *token=&value;
""" + condition + r"""
    return NULL;
}
static void caption(void) {
""" + caption + r"""
}
int main(void) {
    for(int menus=0;menus<2;menus++) for(int wps=0;wps<2;wps++) {
      global_settings.podthings_menu_branding=menus;
      global_settings.podthings_wps_branding=wps; caption();
      assert(!strcmp(podthings_home_title,menus?"PodThings OS":"Home"));
      assert((branding()!=NULL)==(bool)wps);
    }
}
""")


if __name__ == "__main__":
    unittest.main()
