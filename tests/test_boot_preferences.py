"""Exercise native production boot selection, persistence and recovery."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BootPreferences(unittest.TestCase):
    def test_saved_preferences_hold_matrix_requests_and_io_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "config.h").write_text("")
            (out / "rbpaths.h").write_text('#define ROCKBOX_DIR TEST_ROOT\n')
            (out / "file.h").write_text("""
#include <unistd.h>
#include <fcntl.h>
#include <stdio.h>
ssize_t injected_write(int, const void *, size_t);
int injected_rename(const char *, const char *);
#define write injected_write
#define rename injected_rename
""")
            (out / "storage.h").write_text("""
#include <stdbool.h>
int storage_flush(void);
void storage_sleepnow(void);
bool storage_disk_is_active(void);
""")
            (out / "test.c").write_text(r"""
#include <assert.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include "podthings_boot.h"
static int fail_write, fail_rename, fail_flush;
ssize_t injected_write(int fd, const void *data, size_t n)
{ return write(fd, data, fail_write ? n - 1 : n); }
int injected_rename(const char *a, const char *b)
{ return fail_rename ? -1 : rename(a,b); }
int storage_flush(void) { return fail_flush ? -1 : 0; }
void storage_sleepnow(void) {}
bool storage_disk_is_active(void) { return false; }
static void corrupt(const char *text)
{
    int fd = open(TEST_ROOT "/boot-default", O_WRONLY|O_CREAT|O_TRUNC, 0600);
    assert(fd >= 0);
    assert(write(fd,text,strlen(text)) == (ssize_t)strlen(text));
    assert(!close(fd));
}
int main(void)
{
    assert(podthings_boot_default() == PODTHINGS_BOOT_OS);
    for (int target = 0; target < 3; target++)
    {
        assert(podthings_set_boot_default(target));
        assert(podthings_boot_default() == target);
        assert(podthings_boot_resolve(target,false,0,0) == target);
        assert(podthings_boot_resolve(target,true,0,0) ==
               (target == 0 ? PODTHINGS_BOOT_APPLE : PODTHINGS_BOOT_OS));
        assert(podthings_boot_resolve(target,false,1,0) == PODTHINGS_BOOT_APPLE);
        assert(podthings_boot_resolve(target,false,0,1) == PODTHINGS_BOOT_ROCKBOX);
        assert(podthings_boot_resolve(target,false,-1,0) == PODTHINGS_BOOT_OS);
        assert(podthings_boot_resolve(target,false,0,-1) == PODTHINGS_BOOT_OS);
        assert(podthings_boot_resolve(target,false,1,1) == PODTHINGS_BOOT_OS);
        if (target)
        {
            assert(podthings_boot_resolve(target,true,1,0) == PODTHINGS_BOOT_OS);
            assert(podthings_boot_resolve(target,true,0,1) == PODTHINGS_BOOT_OS);
        }
    }
    assert(!podthings_set_boot_default(-1));
    assert(!podthings_set_boot_default(3));
    assert(podthings_boot_default() == 2);
    fail_write = 1;
    assert(!podthings_set_boot_default(1));
    fail_write = 0;
    assert(podthings_boot_default() == 2); /* No truncation on partial write. */
    fail_rename = 1;
    assert(!podthings_set_boot_default(1));
    fail_rename = 0;
    assert(podthings_boot_default() == 2);
    fail_flush = 1;
    assert(!podthings_set_boot_default(1));
    fail_flush = 0;
    const char *bad[] = {"", "1", "2\nx", "3\n", "-1", "apple\n", "1x"};
    for (unsigned i=0; i<sizeof(bad)/sizeof(*bad); i++)
    {
        corrupt(bad[i]);
        assert(podthings_boot_default() == PODTHINGS_BOOT_OS);
    }
    /* A one-time handoff does not overwrite the persistent default. */
    assert(podthings_set_boot_default(2));
    assert(podthings_request_official_boot());
    assert(podthings_consume_official_boot() == 1);
    assert(podthings_consume_official_boot() == 0);
    assert(podthings_boot_default() == 2);
    assert(podthings_request_rockbox_boot());
    assert(podthings_consume_rockbox_boot() == 1);
    assert(podthings_consume_rockbox_boot() == 0);
    assert(podthings_boot_default() == 2);
    assert(podthings_request_disk_boot());
    assert(podthings_consume_disk_boot() == 1);
    assert(podthings_consume_disk_boot() == 0);
    assert(podthings_boot_default() == 2);
    for(int target=0;target<3;target++) {
        assert(podthings_boot_resolve_disk(target,false,0,0,1)==PODTHINGS_BOOT_DISK);
        assert(podthings_boot_resolve_disk(target,false,1,0,1)==PODTHINGS_BOOT_OS);
        assert(podthings_boot_resolve_disk(target,false,0,1,1)==PODTHINGS_BOOT_OS);
        assert(podthings_boot_resolve_disk(target,false,0,0,-1)==PODTHINGS_BOOT_OS);
        assert(podthings_boot_resolve_disk(target,true,0,0,1)==
               (target ? PODTHINGS_BOOT_OS : PODTHINGS_BOOT_DISK));
    }
    int disk=open(TEST_ROOT "/boot-disk-once",O_WRONLY|O_CREAT|O_TRUNC,0600);
    assert(disk>=0 && write(disk,"bad",3)==3 && !close(disk));
    assert(podthings_consume_disk_boot()==-1);
    assert(podthings_consume_disk_boot()==0);
    return 0;
}
""")
            exe = out / "test"
            subprocess.run([
                "cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                "-fsanitize=undefined", "-DHAVE_STORAGE_FLUSH",
                f'-DTEST_ROOT="{out}"', f"-I{out}",
                f"-I{ROOT / 'rockbox-firmware/firmware/export'}",
                str(ROOT / "rockbox-firmware/firmware/common/podthings_boot.c"),
                str(out / "test.c"), "-o", str(exe)
            ], check=True)
            subprocess.run([str(exe)], check=True, timeout=10)

    def test_bootloaders_use_explicit_stock_path_and_fallback(self):
        for filename in ("ipod.c", "ipod-s5l87xx.c"):
            text = (ROOT / "rockbox-firmware/bootloader" / filename).read_text()
            self.assertIn("podthings_boot_resolve_disk(", text)
            stock = text.index('load_firmware(loadbuffer, "/.rockbox/rockbox.ipod"')
            own = text.index("load_firmware(loadbuffer, BOOTFILE", stock)
            self.assertLess(stock, own)
            self.assertNotIn('load_firmware(loadbuffer, "rockbox.ipod"', text)

    def test_settings_visibility_order_and_branding_labels(self):
        text = (ROOT / "rockbox-firmware/apps/menus/main_menu.c").read_text()
        callback = text.split("static int rockbox_available_callback",1)[1].split(
            "static int reboot_to_rockbox",1)[0]
        self.assertIn('!dir_exists("/.rockbox")', callback)
        self.assertIn("ACTION_EXIT_MENUITEM", callback)
        self.assertIn('rockbox ? 3 : 2', text)
        self.assertIn('&reboot_official_item,\n          &reboot_rockbox_item', text)
        self.assertRegex(text, r'&change_theme_item,\s*&display_menu,\s*'
                         r'&podthings_branding_settings,\s*&theme_menu')
        self.assertIn('"Show Branding on Menu"', text)
        self.assertIn('"Show Branding on Now Playing"', text)
        menu = (ROOT / "rockbox-firmware/apps/menu.c").read_text()
        self.assertIn('if (type == MT_SETTING_W_TEXT)\n            return P2STR', menu)

    def test_disk_action_only_exposes_real_apple_path(self):
        menu = (ROOT / "rockbox-firmware/apps/menus/main_menu.c").read_text()
        action = menu.index("static int reboot_to_disk_mode")
        self.assertEqual(menu.rfind("#if defined(IPOD_VIDEO) || defined(IPOD_COLOR)", 0, action),
                         menu.rfind("#if", 0, action))
        for name in ("device_settings", "main_menu_"):
            body = menu.split("MAKE_MENU(" + name + ",", 1)[1].split(");", 1)[0]
            self.assertIn("#if defined(IPOD_VIDEO) || defined(IPOD_COLOR)\n"
                          "          &reboot_disk_item,\n#endif", body)
        s5l = (ROOT / "rockbox-firmware/bootloader/ipod-s5l87xx.c").read_text()
        disk = s5l.split("if (boot_target == PODTHINGS_BOOT_DISK)", 1)[1].split(
            "if (boot_target == PODTHINGS_BOOT_APPLE)", 1)[0]
        self.assertNotIn("usb_mode()", disk)
        self.assertNotIn("kernel_launch_onb()", disk)
        self.assertIn('printf("Apple Disk Mode unavailable")', disk)
        self.assertIn("goto load_podthings", disk)
        video = (ROOT / "rockbox-firmware/bootloader/ipod.c").read_text()
        disk = video.split("if (boot_target == PODTHINGS_BOOT_DISK)", 1)[1].split(
            "if (boot_target == PODTHINGS_BOOT_APPLE)", 1)[0]
        self.assertIn('"diskmode\\0\\0hotstuff\\0\\0\\1"', disk)
        self.assertIn("system_reboot()", disk)
