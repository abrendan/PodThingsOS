"""Check actual preprocessed C keymaps; these are not hardware tests."""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "rockbox-firmware/apps/keymaps/keymap-ipod.c"


def tables_for(target):
    with tempfile.TemporaryDirectory() as directory:
        for header in ("config.h", "action.h", "button.h", "settings.h"):
            (Path(directory) / header).touch()
        if target in ("IPOD_VIDEO", "IPOD_6G", "IPOD_NANO3G"):
            # Production configs enable this shared UI feature switch.
            (Path(directory) / "config.h").write_text("#define PODTHINGS_OS 1\n")
        code = subprocess.check_output(
            ["gcc", "-E", "-P", f"-D{target}", "-I", directory, str(SOURCE)],
            text=True,
        )
    tables = {}
    for name, body in re.findall(
        r"button_context_(\w+)\[\]\s*=\s*\{(.*?)\n\};", code, re.S
    ):
        rows = re.findall(
            r"\{\s*(ACTION_\w+)\s*,\s*([^,]+),\s*([^}]+)\}", body
        )
        fallback = re.search(r"NEXTLIST\(([^)]+)\)", body)
        tables[name] = (rows, fallback.group(1).replace(" ", "") if fallback else None)
    return tables


def bits(expression):
    return frozenset(part.strip() for part in expression.split("|"))


def lookup(tables, name, button, previous="BUTTON_NONE"):
    rows, fallback = tables[name]
    for action, event, prerequisite in rows:
        if bits(event) == bits(button) and (
            prerequisite.strip() == "BUTTON_NONE" or bits(prerequisite) == bits(previous)
        ):
            return action
    next_table = {
        "CONTEXT_STD": "standard",
        "CONTEXT_LIST": "standard",
        "CONTEXT_CUSTOM|CONTEXT_TREE": "tree",
    }.get(fallback)
    return lookup(tables, next_table, button, previous) if next_table else "ACTION_NONE"


class IpodNavigationTest(unittest.TestCase):
    def test_core_navigation_on_supported_devices(self):
        for target in ("IPOD_VIDEO", "IPOD_6G", "IPOD_NANO3G"):
            tables = tables_for(target)
            for context in ("standard", "tree", "tree_scroll_lr", "settings", "bmark"):
                with self.subTest(target=target, context=context):
                    self.assertEqual(
                        lookup(tables, context, "BUTTON_MENU|BUTTON_REL", "BUTTON_MENU"),
                        "ACTION_STD_CANCEL",
                    )
            for context in ("standard", "tree", "tree_scroll_lr"):
                self.assertEqual(lookup(tables, context, "BUTTON_LEFT"), "ACTION_NONE")
                self.assertEqual(lookup(tables, context, "BUTTON_RIGHT"), "ACTION_NONE")
                self.assertEqual(
                    lookup(tables, context, "BUTTON_SELECT|BUTTON_REL", "BUTTON_SELECT"),
                    "ACTION_STD_OK",
                )
                self.assertEqual(
                    lookup(tables, context, "BUTTON_MENU|BUTTON_REPEAT", "BUTTON_MENU"),
                    "ACTION_STD_MENU",
                )
                self.assertEqual(
                    lookup(tables, context, "BUTTON_MENU|BUTTON_REL",
                           "BUTTON_MENU|BUTTON_REPEAT"),
                    "ACTION_NONE",
                )

    def test_playback_and_special_screens(self):
        for target in ("IPOD_VIDEO", "IPOD_6G", "IPOD_NANO3G"):
            tables = tables_for(target)
            self.assertEqual(
                lookup(tables, "wps", "BUTTON_MENU|BUTTON_REL", "BUTTON_MENU"),
                "ACTION_WPS_BROWSE",
            )
            self.assertEqual(
                lookup(tables, "wps", "BUTTON_MENU|BUTTON_REPEAT", "BUTTON_MENU"),
                "ACTION_WPS_MENU",
            )
            for side, action in (("LEFT", "SKIPPREV"), ("RIGHT", "SKIPNEXT")):
                self.assertEqual(
                    lookup(tables, "wps", f"BUTTON_{side}|BUTTON_REL", f"BUTTON_{side}"),
                    f"ACTION_WPS_{action}",
                )
            self.assertEqual(
                lookup(tables, "wps", "BUTTON_LEFT|BUTTON_REPEAT"),
                "ACTION_WPS_SEEKBACK",
            )
            self.assertEqual(
                lookup(tables, "wps", "BUTTON_LEFT|BUTTON_REL", "BUTTON_LEFT|BUTTON_REPEAT"),
                "ACTION_WPS_STOPSEEK",
            )
            self.assertEqual(
                lookup(tables, "quickscreen", "BUTTON_MENU|BUTTON_REL", "BUTTON_MENU"),
                "ACTION_STD_CANCEL",
            )
            self.assertEqual(
                lookup(tables, "bmark", "BUTTON_MENU|BUTTON_REPEAT", "BUTTON_MENU"),
                "ACTION_STD_MENU",
            )

    def test_other_ipods_keep_upstream_navigation(self):
        tables = tables_for("IPOD_NANO")
        self.assertEqual(lookup(tables, "standard", "BUTTON_LEFT"), "ACTION_STD_CANCEL")
        self.assertEqual(
            lookup(tables, "standard", "BUTTON_MENU|BUTTON_REL", "BUTTON_MENU"),
            "ACTION_STD_MENU",
        )


if __name__ == "__main__":
    unittest.main()
