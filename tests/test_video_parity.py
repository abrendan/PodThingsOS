from pathlib import Path
import subprocess
import tempfile
import unittest

from test_ipod_battery import function

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "rockbox-firmware"


class VideoParityTests(unittest.TestCase):
    def test_readonly_apple_partition_loader(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path/"config.h").write_text("#define IF_MD(x,...)\n#define STORAGE_GET_INFO\n")
            (path/"storage.h").write_text("""
#include <stdint.h>
typedef uint64_t sector_t;
struct storage_info { int sector_size; };
int storage_read_sectors(sector_t start, int count, void *out);
void storage_get_info(int drive, struct storage_info *info);
""")
            executable = path/"apple"
            subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                "-fsanitize=undefined", "-fno-sanitize-recover=all",
                f"-I{path}", f"-I{SOURCE/'bootloader'}",
                str(SOURCE/"bootloader/ipodvideo-apple.c"),
                str(ROOT/"tests/video_apple_harness.c"), "-o", str(executable)], check=True)
            subprocess.run([str(executable)], check=True, timeout=5)

    def test_theme_upgrade_is_once_only_and_preserves_other_themes(self):
        actual = function((SOURCE/"apps/settings.c").read_text(),
                          "static void podthings_upgrade_video_theme(void)")
        shim = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#define MAX_PATH 260
#define THEME_DIR "/.podthingsloader/themes"
static struct {
  char wps_file[128], sbs_file[128];
  int podthings_theme_revision, volume;
  bool podthings_wps_branding;
} global_settings;
static unsigned loads, saves;
static bool present;
static char loaded[MAX_PATH];
static size_t strlcpy(char *out, const char *in, size_t cap)
{ size_t n=strlen(in); snprintf(out,cap,"%s",in); return n; }
static bool settings_load_config(const char *path, bool apply)
{ assert(!apply); ++loads; strlcpy(loaded,path,sizeof(loaded)); return present; }
static void settings_save(void) { ++saves; }
static void reset(const char *wps, const char *sbs) {
  memset(&global_settings,0,sizeof(global_settings));
  strlcpy(global_settings.wps_file,wps,sizeof(global_settings.wps_file));
  strlcpy(global_settings.sbs_file,sbs,sizeof(global_settings.sbs_file));
  global_settings.volume=-17;
  present=true; loads=saves=0;
}
"""
        main = r"""
int main(void) {
  const char *palettes[]={"current","blue","purple","default"};
  for (unsigned i=0; i<4; ++i) {
    char wps[64], expected[MAX_PATH];
    snprintf(wps,sizeof(wps),"podthingsos-%s",palettes[i]);
    snprintf(expected,sizeof(expected),THEME_DIR "/%s.cfg",wps);
    reset(wps,"-"); podthings_upgrade_video_theme();
    assert(loads==1 && saves==1 && !strcmp(loaded,expected));
    assert(global_settings.volume==-17 && !global_settings.podthings_wps_branding);
    podthings_upgrade_video_theme();
    assert(loads==1 && saves==1); /* Disabled SBS is not re-enabled every boot. */
  }
  reset("/.rockbox/wps/podthingsos-blue.wps","/.rockbox/wps/podthingsos-blue.sbs");
  podthings_upgrade_video_theme();
  assert(loads==1 && strstr(loaded,"/podthingsos-blue.cfg"));
  reset("podthings","-"); podthings_upgrade_video_theme();
  assert(loads==1 && strstr(loaded,"/podthingsos-default.cfg"));
  reset("my-custom-theme","-"); podthings_upgrade_video_theme();
  assert(!loads && !saves);
  reset("podthingsos-purple","custom-sbs"); podthings_upgrade_video_theme();
  assert(!loads && !saves);
  reset("podthingsos-purple","podthings-custom"); podthings_upgrade_video_theme();
  assert(!loads && !saves);
  reset("podthingsos-blue","-"); present=false;
  podthings_upgrade_video_theme();
  assert(loads==1 && !saves && !global_settings.podthings_theme_revision);
  present=true; podthings_upgrade_video_theme();
  assert(loads==2 && saves==1 && global_settings.podthings_theme_revision==1);
  return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            (path/"theme.c").write_text(shim+actual+main)
            subprocess.run(["cc","-std=c99","-Wall","-Wextra","-Werror",
                "-fsanitize=undefined",str(path/"theme.c"),"-o",str(path/"theme")],check=True)
            subprocess.run([str(path/"theme")],check=True,timeout=5)

    def test_fresh_defaults_enable_the_modern_statusbar(self):
        text=(SOURCE/"apps/settings_list.c").read_text()
        defaults=text.split("/* Default theme settings */",1)[1].split("#else",1)[0]
        self.assertIn('#define DEFAULT_SBSNAME  "podthingsos-current"',defaults)
        self.assertIn('#define DEFAULT_WPSNAME  "podthingsos-current"',defaults)
        source=(SOURCE/"bootloader/ipod.c").read_text()
        self.assertIn("ipodvideo_load_apple(loadbuffer, MAX_LOADSIZE)",source)
        self.assertIn("if (boot_target == PODTHINGS_BOOT_APPLE)",source)
        self.assertIn("&& official_once <= 0",source)
        self.assertIn("goto load_podthings",source)


if __name__ == "__main__":
    unittest.main()
