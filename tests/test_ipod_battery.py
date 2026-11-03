"""Run production target tables and the core interpolation in a host C harness."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = ROOT / "rockbox-firmware/firmware"


def function(text, signature):
    start = text.index(signature)
    opening = text.index("{", start)
    depth = 0
    for pos in range(opening, len(text)):
        depth += (text[pos] == "{") - (text[pos] == "}")
        if not depth:
            return text[start:pos + 1]
    raise ValueError("Unclosed C function")


class BatteryTests(unittest.TestCase):
    def check_model(self, video=False, fork=True):
        target = ("target/arm/ipod/powermgmt-ipod-pcf.c" if video else
                  "target/arm/s5l8702/ipod6g/powermgmt-6g.c")
        tables = re.sub(r"^#include.*$", "", (FIRMWARE / target).read_text(),
                        flags=re.M)
        core = (FIRMWARE / "powermgmt.c").read_text()
        definitions = """
#include <assert.h>
#include <stdbool.h>
#define CONFIG_CHARGING 2
#define CHARGING_MONITOR 1
#define ADC_UNREG_POWER 0
static int adc_read(int channel) { return channel; }
static int adc_read_battery_voltage(void) { return 4061; }
static bool charging;
static bool charging_state(void) { return charging; }
"""
        if fork:
            definitions += "#define PODTHINGS_OS 1\n"
        if video:
            definitions += "#define IPOD_VIDEO 1\n"
        program = definitions + tables + "\n" + function(
            core, "static int voltage_to_percent(") + "\n" + function(
                core, "static int voltage_to_battery_level(")
        program += """
int main(void) {
    charging = false;
    assert(voltage_to_battery_level(4061) == EXPECTED_UNPLUGGED);
    charging = true;
"""
        program = program.replace("EXPECTED_UNPLUGGED", "85" if video else "89")
        program += (f"assert(voltage_to_battery_level(4061) == {85 if video else 89});\n"
                    if fork or video else
                    "assert(voltage_to_battery_level(4061) == 57);\n")
        if fork:
            program += """
    for (int mv = -1; mv <= 4500; ++mv) {
        charging = false;
        int unplugged = voltage_to_battery_level(mv);
        charging = true;
        assert(voltage_to_battery_level(mv) ==
               (unplugged > 99 ? 99 : unplugged));
    }
"""
        program += """
    charging = true;
    assert(voltage_to_battery_level(4300) == 99);
    assert(voltage_to_battery_level(-1) == -1);
    charging = false;
    assert(voltage_to_battery_level(4300) == 100);
    assert(voltage_to_battery_level(3200) == 0);
    assert(battery_level_shutoff == 3300);
"""
        program += "assert(battery_level_disksafe == 3500);"
        program += "\nreturn 0; }\n"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "battery.c"
            source.write_text(program)
            binary = Path(directory) / "battery"
            result = subprocess.run(
                ["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                 "-Wno-pointer-sign", "-Wno-unused-function",
                 str(source), "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(binary)], check=True)

    def test_classic_uses_one_scale_with_charging_cap_and_safety_unchanged(self):
        self.check_model()

    def test_video_already_has_matching_scales(self):
        self.check_model(video=True)

    def test_legacy_classic_tables_reproduce_the_report(self):
        self.check_model(fork=False)
