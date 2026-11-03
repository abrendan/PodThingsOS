"""Native music flows, real temporary files, mocked platform APIs—not a simulator."""
import re
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "rockbox-firmware/apps"


class MusicModernizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        folder = Path(cls.temp.name)
        body = re.sub(r'^#include .*\n', '', (APPS / "podthings_music.c").read_text(),
                      flags=re.M)
        (folder / "music-ui-under-test.c").write_text(body)
        cls.exe = folder / "music-ui"
        subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=undefined", "-fno-sanitize-recover=all",
                        "-I", str(folder), str(ROOT / "tests/music_ui_harness.c"),
                        "-o", str(cls.exe)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_recent_albums_playback_and_failure_paths(self):
        for case in ("play", "shuffle", "cancel", "party", "size_limit",
                     "storage_error", "oom", "empty", "missing",
                     "enable_history", "decline_history"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)
                (folder / ".podthingsloader").mkdir()
                (folder / "Music").mkdir()
                sentinel = folder / ".podthingsloader/recent-album-a.m3u8"
                sentinel.write_bytes(b"current-playback\n")
                for name in ("A1", "A2", "B1", "B2", "C1"):
                    if case != "missing" or name != "A2":
                        (folder / f"Music/{name}.mp3").write_bytes(b"fixture-audio")
                result = subprocess.run([str(self.exe), tmp, case],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(sentinel.read_bytes(), b"current-playback\n")

    def test_home_settings_and_position_preservation_wiring(self):
        root = (APPS / "root_menu.c").read_text()
        self.assertIn("&wps_item, &music_home, &recent_albums_home, &favorites_home, &menu_, &extras_home", root)
        self.assertIn("Continue Listening", root)
        self.assertIn("last_db_selection = tc->selected_item", root)
        self.assertIn("tc->selected_item = last_db_selection", root)
        self.assertIn("tagtree_podthings_root(tc, menu_id)", root)
        browser_routes = root[root.index("case GO_TO_DBBROWSER:",
                              root.index("void root_menu(void)")):
                              root.index("global_status.last_browser = previous_browser = next_screen")]
        self.assertIn("case GO_TO_MUSIC_AZ:", browser_routes)
        self.assertIn("case GO_TO_MUSIC_SEARCH:", browser_routes)
        settings = (APPS / "menus/main_menu.c").read_text()
        for group in ("appearance_settings", "music_settings", "device_settings",
                      "about_settings", "advanced_settings"):
            self.assertIn(f"MAKE_MENU({group}", settings)
        for old in ("&settings_menu_item", "&main_menu_config_item", "&manage_settings",
                    "&reboot_official_item", "&startup_shutdown_menu"):
            self.assertIn(old, settings)

    def test_installed_library_config_is_rebranded_not_custom_config(self):
        import runpy
        import zipfile
        package = runpy.run_path(str(ROOT / "scripts/brand-podthings-package.py"))["package"]
        with tempfile.TemporaryDirectory() as tmp:
            source, out = Path(tmp) / "in.zip", Path(tmp) / "out.zip"
            custom = b"custom library preferences\n"
            with zipfile.ZipFile(source, "w") as z:
                z.writestr(".podthingsloader/podthingsos.ipod", b"fixture")
                z.writestr(".podthingsloader/tagnavi.config", (APPS / "tagnavi.config").read_bytes())
                z.writestr(".podthingsloader/tagnavi_user.config", custom)
            package(source, out)
            with zipfile.ZipFile(out) as z:
                config = z.read(".podthingsloader/tagnavi.config")
                self.assertTrue(config.startswith(b"#! rockbox/tagbrowser/2.0\n"))
                self.assertNotIn(b"/.rockbox/", config)
                self.assertIn(b'"Music Library"', config)
                self.assertIn(b'"A-Z Jump"', config)
                self.assertEqual(z.read(".podthingsloader/tagnavi_user.config"), custom)

    def test_library_root_switch_preserves_same_view_and_resets_other_views(self):
        from test_ipod_battery import function
        actual = function((APPS / "tagtree.c").read_text(),
                          "int tagtree_podthings_root(")
        shim = r"""
#include <assert.h>
#include <string.h>
#define TABLE_ROOT 0
struct tree_context {int dirlevel, selected_item, currtable, currextra;};
struct menu_root {char *id;};
static struct menu_root a={"main"}, b={"a2z"}, d={"search"};
static struct menu_root *menus[]={&a,&b,&d};
static int menu_count=3, rootmenu=0, max_history_level=4;
static int tagtree_handle=1,pinned;
static void core_pin(int h){assert(h==1);++pinned;}
static void core_unpin(int h){assert(h==1);--pinned;}
"""
        main = r"""
int main(void) {
 struct tree_context c={3,17,5,2};
 assert(tagtree_podthings_root(&c,"main")==0);
 assert(c.dirlevel==3 && c.selected_item==17 && max_history_level==4 && !pinned);
 assert(tagtree_podthings_root(&c,"a2z")==1);
 assert(c.dirlevel==0 && c.selected_item==0 && c.currtable==TABLE_ROOT);
 assert(c.currextra==1 && rootmenu==1 && !max_history_level && !pinned);
 c.dirlevel=2;c.selected_item=6;max_history_level=2;
 assert(tagtree_podthings_root(&c,"a2z")==0);
 assert(c.dirlevel==2 && c.selected_item==6 && max_history_level==2);
 assert(tagtree_podthings_root(&c,"missing")==-1 && rootmenu==1 && !pinned);
 assert(c.dirlevel==2 && c.selected_item==6);
 assert(tagtree_podthings_root(&c,"search")==1 && rootmenu==2 && !pinned);
 assert(!c.dirlevel && !c.selected_item);
 return 0;
}
"""
        folder = Path(self.temp.name)
        path, exe = folder / "roots.c", folder / "roots"
        path.write_text(shim + actual + main)
        subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=undefined", "-fno-sanitize-recover=all",
                        str(path), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    unittest.main()
