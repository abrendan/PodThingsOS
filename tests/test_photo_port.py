"""Photo target isolation, native geometry and shared-feature regressions."""
import json
from pathlib import Path
import re
import runpy
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "rockbox-firmware"
THEMES = runpy.run_path(str(ROOT / "scripts/generate-podthings-logo.py"))["THEMES"]


class PhotoPortTests(unittest.TestCase):
    def test_native_identity_and_hardware_limits_are_retained(self):
        config = (SOURCE / "firmware/export/config/ipodcolor.h").read_text()
        for define in (
            "#define MODEL_NUMBER 3", "#define LCD_WIDTH  220",
            "#define LCD_HEIGHT 176", "#define CONFIG_CPU PP5020",
            "#define LCD_PIXELFORMAT RGB565SWAPPED",
            "#define PODTHINGS_OS 1", '#define BOOTDIR "/.podthingsloader"',
            '#define BOOTFILE "podthingsos." BOOTFILE_EXT',
            "#define CODEC_SIZE 0x100000", "#define PLUGIN_BUFFER_SIZE 0x80000",
        ):
            self.assertIn(define, config)
        configure = (SOURCE / "tools/configure").read_text().split(
            "20|ipodcolor)", 1)[1].split(";;", 1)[0]
        self.assertIn("memory=32", configure)
        self.assertIn("arm7tdmicc", configure)
        self.assertIn('output="podthingsos.ipod"', configure)

    def test_photo_loader_uses_shared_policy_and_correct_rom_cookie(self):
        loader = (SOURCE / "bootloader/ipod.c").read_text()
        self.assertIn("#if defined(PODTHINGS_OS) && (defined(IPOD_VIDEO) || defined(IPOD_COLOR))", loader)
        for call in ("podthings_boot_resolve_disk(", "podthings_consume_official_boot(",
                     "podthings_consume_rockbox_boot(", "podthings_consume_disk_boot(",
                     "ipodvideo_load_apple(loadbuffer, MAX_LOADSIZE)"):
            self.assertIn(call, loader)
        disk = loader.split("if (boot_target == PODTHINGS_BOOT_DISK)", 1)[1].split(
            "if (boot_target == PODTHINGS_BOOT_ROCKBOX)", 1)[0]
        self.assertIn('#if CONFIG_CPU == PP5020\n'
                      '        memcpy((void *)0x40017f00, "diskmode\\0\\0hotstuff\\0\\0\\1", 21);', disk)
        self.assertIn("#elif CONFIG_CPU == PP5022", disk)
        self.assertIn("system_reboot()", disk)
        self.assertNotIn("usb_mode()", disk)
        protocol = (SOURCE / "firmware/common/podthings_boot.c").read_text()
        self.assertIn("(defined(IPOD_VIDEO) || defined(IPOD_COLOR)) && !defined(SIMULATOR)", protocol)
        self.assertIn("int persisted = ata_flush_for_handoff()", protocol)
        menu = (SOURCE / "apps/menus/main_menu.c").read_text()
        for prompt in ("Boot Apple firmware?", "One-time boot only.",
                       "Connect USB for files.", "Default boot unchanged."):
            self.assertIn(prompt, menu)
        yesno = (SOURCE / "apps/gui/yesno.c").read_text()
        self.assertIn("const int card_space = vp->height < 150 ? 32 : 36", yesno)
        self.assertIn("getcharheight()+card_space>vp->height", yesno)

    def test_all_twelve_themes_have_native_bounded_photo_viewports(self):
        self.assertEqual(len(THEMES), 12)
        for variant in THEMES:
            for kind in ("wps", "sbs"):
                text = (SOURCE / f"wps/podthingsos-{variant}.220x176x16.{kind}").read_text()
                for line in text.splitlines():
                    match = re.match(r"%V(?:l|i)?\(([^)]*)\)", line)
                    if not match:
                        continue
                    args = match[1].split(",")
                    if not args[0].isdigit():
                        label, *args = args
                        if label == "r":
                            continue  # row-relative, bounded by the %Lb geometry
                    x, y, w, h = map(int, args[:4])
                    self.assertGreater(w, 0)
                    self.assertGreater(h, 0)
                    self.assertLessEqual(x + w, 220, (variant, line))
                    self.assertLessEqual(y + h, 176, (variant, line))
            wps = (SOURCE / f"wps/podthingsos-{variant}.220x176x16.wps").read_text()
            for feature in ("%?pN<%Vd(P)%Vd(L)|%Vd(I)>", "\niPod\n",
                            "%?pJ<", "%?mv(2)<", "%Cd%xd(M)",
                            "%ac%?St(time format)", "%ar%bl%%%",
                            "%fc", "%fb kbps", "16-PodThings-Sans.fnt"):
                self.assertIn(feature, wps)
            folder = SOURCE / f"wps/podthingsos-{variant}"
            for asset, size in (
                ("backdrop", (220, 176)), ("selection", (204, 20)),
                ("art-mask", (80, 80)), ("volume-panel", (204, 28)),
                ("volume-track", (184, 5)), ("volume-fill", (184, 5)),
            ):
                data = (folder / f"photo-{asset}.bmp").read_bytes()
                self.assertEqual(data[:2], b"BM")
                self.assertEqual(struct.unpack_from("<ii", data, 18), size)
            sbs = (SOURCE / f"wps/podthingsos-{variant}.220x176x16.sbs").read_text()
            self.assertIn("%Lb(r,204,20)", sbs)
            self.assertIn("%Vl(r,8,2,188,16,1)", sbs)
            self.assertIn("%Vs(gradient)", sbs)

    def test_photo_cover_formats_and_current_theme_registration(self):
        artwork = (SOURCE / "apps/podthings_artwork.c").read_text()
        self.assertIn("case 1017:return 56; case 1016:return 140;", artwork)
        listing = (SOURCE / "wps/WPSLIST").read_text()
        for variant in THEMES:
            for kind in ("wps", "sbs"):
                self.assertIn(f"{kind}.220x176x16: podthingsos-{variant}.220x176x16.{kind}", listing)
        self.assertIn("Font.220x176x16: 16-PodThings-Sans.fnt", listing)
        policy = json.loads((ROOT / "assets/installer/bootloader-requirements.json").read_text())
        self.assertEqual(policy["ipodcolor"], "0.9.5")
        metadata = runpy.run_path(str(ROOT / "scripts/installer_config.py"))
        config = json.loads(metadata["config"]("device-kit", "0.9.5", "ipodcolor"))
        self.assertEqual(config["target"], "ipodcolor")
        self.assertEqual(config["minimum_bootloader_version"], "0.9.5")
        shared_themes = json.loads(metadata["config"]("themes", "0.9.5"))
        self.assertNotIn("ipodcolor", shared_themes["supported_targets"])


if __name__ == "__main__":
    unittest.main()
