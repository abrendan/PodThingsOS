"""Exercise the production one-shot C protocol, not a Python reimplementation."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "rockbox-firmware"


class OfficialBootTests(unittest.TestCase):
    def run_checked(self, command):
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0,
                         " ".join(command) + "\n" + result.stdout + result.stderr)

    def test_native_protocol_and_io_failures(self):
        self.check_native_protocol()

    def test_rockbox_protocol_and_io_failures(self):
        self.check_native_protocol(rockbox=True)

    def check_native_protocol(self, rockbox=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            volume = root / ".podthingsloader"
            volume.mkdir()
            stubs = {
                "config.h": "",
                "rbpaths.h": "#define ROCKBOX_DIR TEST_ROOT\n",
                "storage.h": """
#include <stdbool.h>
int storage_flush(void);
void storage_sleepnow(void);
bool storage_disk_is_active(void);
""",
                "file.h": """
#include <unistd.h>
#include <fcntl.h>
#include <stdio.h>
int test_open(const char *, int, ...);
ssize_t test_read(int, void *, size_t);
ssize_t test_write(int, const void *, size_t);
int test_fsync(int);
int test_close(int);
int test_remove(const char *);
#define open test_open
#define read test_read
#define write test_write
#define fsync test_fsync
#define close test_close
#define remove test_remove
""",
            }
            for name, content in stubs.items():
                (root / name).write_text(content)
            harness = root / "harness.c"
            content = (ROOT / "tests/podthings_boot_harness.c").read_text()
            if rockbox:
                content = content.replace("official", "rockbox")
            harness.write_text(content)
            executable = root / "boot-protocol"
            self.run_checked([
                "cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                "-DHAVE_STORAGE_FLUSH",
                f'-DTEST_ROOT="{volume}"', f"-I{root}",
                f"-I{SOURCE / 'firmware/export'}",
                str(SOURCE / "firmware/common/podthings_boot.c"),
                str(harness),
                "-o", str(executable),
            ])
            for case in (
                "missing", "one-shot", "cancel", "malformed", "empty",
                "trailing-data", "open-fail", "short-write", "sync-fail",
                "close-fail", "flush-create-fail", "read-fail",
                "remove-fail", "flush-consume-fail",
                "sleep-fail",
            ):
                with self.subTest(case=case):
                    self.run_checked([str(executable), case])
            # The generic fallback (not the new Video-specific handoff) still
            # needs its standby barrier when no optional flush API exists.
            self.run_checked([
                "cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                f'-DTEST_ROOT="{volume}"', f"-I{root}",
                f"-I{SOURCE / 'firmware/export'}",
                str(SOURCE / "firmware/common/podthings_boot.c"),
                str(harness),
                "-o", str(executable),
            ])
            for case in ("one-shot", "sleep-fail", "cancel", "malformed"):
                with self.subTest(no_flush_hook=case):
                    self.run_checked([str(executable), case])

    def test_both_bootloaders_consume_before_loading_podthings(self):
        for name in ("ipod.c", "ipod-s5l87xx.c"):
            source = (SOURCE / "bootloader" / name).read_text()
            main = source[source.index("main(void)"):]
            consume = main.index("podthings_consume_official_boot()")
            self.assertLess(main.index("disk_mount_all()"), consume)
            self.assertLess(consume, main.index("load_firmware(loadbuffer, BOOTFILE"))
            self.assertIn("podthings_boot_resolve_disk(", main)
        classic = (SOURCE / "bootloader/ipod-s5l87xx.c").read_text()
        once = classic[classic.index("if (boot_target == PODTHINGS_BOOT_APPLE)"): ]
        self.assertLess(once.index("OF: no LBA48"),
                        once.index("kernel_launch_onb()"))
        self.assertLess(once.index("ata_sleepnow()"),
                        once.index("kernel_launch_onb()"))

    def test_settings_confirmation_clean_reboot_and_cancellation(self):
        source = (SOURCE / "apps/menus/main_menu.c").read_text()
        action = source[source.index("static int reboot_to_official_firmware"):]
        self.assertLess(action.index("gui_syncyesno_run"),
                        action.index("podthings_request_official_boot()"))
        self.assertLess(action.index("battery_level_safe()"),
                        action.index("podthings_request_official_boot()"))
        self.assertLess(action.index("default_event_handler(SYS_REBOOT)"),
                        action.index("podthings_cancel_official_boot()"))
        self.assertIn("&reboot_official_item", action)
        misc = (SOURCE / "apps/misc.c").read_text()
        self.assertIn("#ifdef IPOD_VIDEO\n       || sd_type == SHUTDOWN_REBOOT",
                      misc)


if __name__ == "__main__":
    unittest.main()
