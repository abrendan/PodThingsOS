import runpy
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECK = runpy.run_path(str(ROOT / "scripts/check-public-repo.py"))


class PublicRepoTests(unittest.TestCase):
    def test_local_state_and_generated_files_are_rejected(self):
        for name in (
            "generated-artifacts/releases/firmware.zip",
            ".agents/memory/MEMORY.md", "attached_assets/upload.jpg",
            ".local/toolchain/gcc", "AGENTS.md", "CLAUDE.md",
            ".env", ".env.production", "scripts/__pycache__/build.pyc",
            "build-video/rockbox.ipod", "firmware.o", "debug.map",
        ):
            with self.subTest(name=name):
                self.assertTrue(CHECK["forbidden"](name))

    def test_source_licenses_and_required_assets_are_allowed(self):
        for name in (
            "README.md", "docs/INSTALLATION.md", "LICENSE", ".gitignore",
            ".env.example", "rockbox-firmware/apps/main.c",
            "rockbox-firmware/apps/plugins/puzzles/fonts.zip",
            "assets/branding/podthings.svg", "tests/test_public_repo.py",
        ):
            with self.subTest(name=name):
                self.assertFalse(CHECK["forbidden"](name))
