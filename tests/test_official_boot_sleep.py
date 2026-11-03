"""Compile the actual Classic sleep function with deterministic hardware shims."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_ipod_battery import function

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "rockbox-firmware/firmware/target/arm/s5l8702/ipod6g/storage_ata-6g.c"


class ClassicBootSleepTests(unittest.TestCase):
    def test_nano_consumption_commits_ftl_without_ata_sleep(self):
        actual = function((ROOT / "rockbox-firmware/firmware/common/podthings_boot.c").read_text(),
                          "static bool cancel_request(const char *path)")
        shim = r"""
#include <assert.h>
#include <stdbool.h>
#define IPOD_NANO3G
static int removed, flushed;
static int remove(const char *p) { (void)p; return removed; }
static int flush_request_storage(void) { return flushed; }
"""
        main = r"""
int main(void) {
    assert(cancel_request("nano"));
    flushed=-1; assert(!cancel_request("nano"));
    flushed=0; removed=-1; assert(!cancel_request("nano"));
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"nano.c"; path.write_text(shim+actual+main)
            exe=Path(tmp)/"nano"
            subprocess.run(["cc","-std=c99","-Wall","-Wextra","-Werror",
                            "-fsanitize=undefined",str(path),"-o",str(exe)],check=True)
            subprocess.run([str(exe)],check=True,timeout=5)

    def test_video_flush_keeps_disk_awake_and_reports_failures(self):
        actual = function((ROOT / "rockbox-firmware/firmware/drivers/ata.c").read_text(),
                          "int ata_flush_for_handoff(void)")
        shim = r"""
#include <assert.h>
#include <stdbool.h>
#define ATA_ON 3
#define ATA_ALT_STATUS 0
#define STATUS_ERR 1
#define STATUS_DF 32
#define ATA_IN8(reg) status
static unsigned status;
static int ata_state, ata_mutex, locks, flushes, result;
static bool canflush, discover_unsupported;
static unsigned short identify_info[256];
static void mutex_lock(int *m) { (void)m; assert(!locks); ++locks; }
static void mutex_unlock(int *m) { (void)m; assert(locks==1); --locks; }
static int ata_perform_flush_cache(void) {
    ++flushes;
    if (discover_unsupported) canflush=false;
    return result;
}
"""
        main = r"""
int main(void) {
    assert(ata_flush_for_handoff()==-1 && !flushes && !locks);
    ata_state=ATA_ON; canflush=true;
    assert(!ata_flush_for_handoff() && flushes==1 && !locks);
    assert(ata_state==ATA_ON); /* No standby, wake or reset path. */
    status=STATUS_ERR;
    assert(ata_flush_for_handoff()==-1 && !locks);
    status=STATUS_DF;
    assert(ata_flush_for_handoff()==-1 && !locks);
    status=0;
    result=-2;
    assert(ata_flush_for_handoff()==-2 && !locks && ata_state==ATA_ON);
    result=0; discover_unsupported=true; identify_info[82]=1<<5;
    assert(ata_flush_for_handoff()==-1 && !locks);
    identify_info[82]=1<<5;
    assert(ata_flush_for_handoff()==-1 && !locks);
    identify_info[82]=0;
    assert(!ata_flush_for_handoff() && !locks && ata_state==ATA_ON);
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"video.c"
            path.write_text(shim+actual+main)
            exe = Path(tmp)/"video"
            subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                            "-fsanitize=undefined", str(path), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True, timeout=5)

    def test_video_protocol_never_sleeps_and_rejects_failed_barrier(self):
        actual = function((ROOT / "rockbox-firmware/firmware/common/podthings_boot.c").read_text(),
                          "static bool cancel_request(const char *path)")
        shim = r"""
#include <assert.h>
#include <stdbool.h>
#define IPOD_VIDEO
#define OFFICIAL_BOOT_REQUEST "test"
static int removed, flushed, persisted, barriers;
static int remove(const char *p) { (void)p; return removed; }
static int flush_request_storage(void) { return flushed; }
static int ata_flush_for_handoff(void) { ++barriers; return persisted; }
"""
        main = r"""
int main(void) {
    assert(cancel_request(OFFICIAL_BOOT_REQUEST) && barriers==1);
    persisted=-1;
    assert(!cancel_request(OFFICIAL_BOOT_REQUEST) && barriers==2);
    persisted=0; removed=-1;
    assert(!cancel_request(OFFICIAL_BOOT_REQUEST) && barriers==3);
    removed=0; flushed=-1;
    assert(!cancel_request(OFFICIAL_BOOT_REQUEST) && barriers==4);
    return 0;
}
"""
        for model in ("IPOD_VIDEO", "IPOD_COLOR"):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/"protocol.c"
                path.write_text(shim.replace("#define IPOD_VIDEO", "#define " + model)+actual+main)
                exe=Path(tmp)/"protocol"
                subprocess.run(["cc","-std=c99","-Wall","-Wextra","-Werror",
                                "-fsanitize=undefined",str(path),"-o",str(exe)],check=True)
                subprocess.run([str(exe)],check=True,timeout=5)

    def test_repeated_sleep_and_controller_timeout(self):
        actual = function(SOURCE.read_text(), "void ata_sleepnow(void)")
        shim = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#define HZ 100
#define BIT(n) (1u << (n))
#define TIME_AFTER(a,b) ((long)((b)-(a)) < 0)
#define CMD_STANDBY_IMMEDIATE 0xe0
#define ATA_PIO_DVR 0
#define ATA_PIO_CSD 1
#define PWRCON(n) power_register
#define logf(...) ((void)0)
static bool ata_powered, ceata, canflush, can_sleep, acknowledge;
static int ata_mutex, locks, flushes, commands, powerdowns;
static long current_tick;
static uint32_t ATA_CONTROL, power_register;
static unsigned char ceata_taskfile[16];
static void mutex_lock(int *m) { (void)m; assert(!locks); ++locks; }
static void mutex_unlock(int *m) { (void)m; assert(locks == 1); --locks; }
static void ata_flush_cache(void) { assert(ata_powered); ++flushes; }
static bool ata_disk_can_sleep(void) { return can_sleep; }
static void ceata_wait_idle(void) {}
static void ceata_write_multiple_register(int a, void *b, int c)
{ (void)a; (void)b; (void)c; ++commands; }
static void sleep(int ticks) { current_tick += ticks; }
static void ata_wait_for_rdy(int usecs) { (void)usecs; }
static void ata_write_cbr(void *reg, int value)
{ (void)reg; (void)value; ++commands; }
static void ata_power_down(void) { ++powerdowns; ata_powered = false; }
static void yield(void)
{ ++current_tick; if (acknowledge) ATA_CONTROL |= BIT(1); }
"""
        # The production address-of expressions expect mock registers, not macros.
        shim = shim.replace("#define ATA_PIO_DVR 0", "static int ATA_PIO_DVR;")
        shim = shim.replace("#define ATA_PIO_CSD 1", "static int ATA_PIO_CSD;")
        main = r"""
int main(void) {
    /* Missing request / already sleeping: don't issue any hardware command. */
    ata_sleepnow();
    assert(!locks && !flushes && !commands && !powerdowns);
    ata_powered = can_sleep = acknowledge = true;
    ATA_CONTROL = 0x80;
    ata_sleepnow();
    assert(!ata_powered && !locks && flushes == 1 && powerdowns == 1);
    int old_commands = commands;
    /* The old one-shot path entered sleep twice; the second must be harmless. */
    ata_sleepnow();
    assert(flushes == 1 && commands == old_commands && powerdowns == 1 && !locks);
    /* No controller acknowledgement: finite wait, restore controller, stay active.
     * The request consumer therefore rejects Apple handoff. */
    ata_powered = true; acknowledge = false; ATA_CONTROL = 0x80;
    long started = current_tick;
    ata_sleepnow();
    assert(ata_powered && !locks && ATA_CONTROL == 0x80);
    assert(current_tick - started < HZ * 2 && powerdowns == 1);
    /* Adapter that cannot safely sleep/flush remains active (not false success). */
    can_sleep = canflush = false;
    ata_sleepnow();
    assert(ata_powered && !locks && powerdowns == 1);
    /* CE-ATA path retains its existing command/power-down sequence. */
    ceata = true;
    ata_sleepnow();
    assert(!ata_powered && !locks && powerdowns == 2);
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sleep.c"
            path.write_text(shim + actual + main)
            exe = Path(tmp) / "sleep"
            subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                            "-fsanitize=undefined", "-fno-sanitize-recover=all",
                            str(path), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True, timeout=5)

    def test_bootloader_is_quiet_and_second_barrier_is_conditional(self):
        source = (ROOT / "rockbox-firmware/bootloader/ipod-s5l87xx.c").read_text()
        once = source[source.index("if (boot_target == PODTHINGS_BOOT_APPLE)"):]
        self.assertIn("if (storage_disk_is_active())\n            ata_sleepnow();", once)
        for target in ("ipod-s5l87xx.c", "ipod.c"):
            text = (ROOT / "rockbox-firmware/bootloader" / target).read_text()
            self.assertNotIn('printf("One-time OF', text)
            self.assertNotIn('One-Time OF request timeout', text)
        self.assertLess(once.index("OF: no LBA48"),
                        once.index("kernel_launch_onb()"))


if __name__ == "__main__":
    unittest.main()
