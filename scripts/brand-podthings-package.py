#!/usr/bin/env python3
"""Normalize installed product filenames after the upstream ZIP builder."""
import sys
import zipfile
from pathlib import Path

ALIASES = {
    "rockbox_failsafe": "podthings_failsafe",
    "rockbox_default_icons": "podthings_default_icons",
    "rockbox-fonts.config": "podthings-fonts.config",
    "rockbox-info.txt": "podthings-info.txt",
    "rockbox.map": "podthings.map",
}


def branded_name(name):
    for original, replacement in ALIASES.items():
        name = name.replace(original, replacement)
    return name


def package(source, output):
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED
    ) as new:
        seen = set()
        for info in old.infolist():
            # This demo exists to animate the old product wordmark. It is not
            # part of the branded OS; keep its source and copyright intact.
            if info.filename == ".podthingsloader/rocks/demos/bounce.rock":
                continue
            name = branded_name(info.filename)
            if not name.startswith(".podthingsloader/"):
                raise ValueError(f"Unexpected install path: {name}")
            if "rockbox" in name.lower():
                raise ValueError(f"Unbranded installed filename: {name}")
            if name in seen:
                raise ValueError(f"Duplicate installed filename: {name}")
            seen.add(name)
            data = old.read(info)
            if name == ".podthingsloader/tagnavi.config":
                # Keep the parser signature, but fix installed paths and
                # make the native music library's labels easier to scan.
                data = data.replace(b"/.rockbox/", b"/.podthingsloader/")
                for original, replacement in (
                    (b'%menu_start "main" "Database"', b'%menu_start "main" "Music Library"'),
                    (b'"Album Artist" ->', b'"Album Artists" ->'),
                    (b'"Artist"   ->', b'"Artists"  ->'),
                    (b'"Album"    ->', b'"Albums"   ->'),
                    (b'"First Letter" ==>', b'"A-Z Jump" ==>'),
                    (b'"Tracks by"   ==>', b'"Songs"       ==>'),
                    (b'"Filename" -> basename', b'"By Filename" -> basename'),
                    (b'"Title" -> title', b'"All Songs" -> title'),
                ):
                    data = data.replace(original, replacement)
            if name.endswith((".cfg", ".wps", ".sbs", ".fms", ".wrs", ".config")):
                for original, replacement in ALIASES.items():
                    data = data.replace(original.encode(), replacement.encode())
            info.filename = name
            new.writestr(info, data)
        if ".podthingsloader/podthingsos.ipod" not in seen:
            raise ValueError("Missing native PodThings OS firmware")
        if any(f".podthingsloader/fonts/{height}-PodThings-Sans.fnt" in seen
               for height in (16, 22)):
            root = Path(__file__).resolve().parents[1]
            license_text = (
                "PodThings Sans: DejaVu Sans + GNU Unifont fallback.\n\n" +
                (root / "assets/fonts/DejaVu-COPYING.txt").read_text() + "\n\n" +
                (root / "assets/fonts/FONT-SOURCES.md").read_text() + "\n\n" +
                (root / "assets/fonts/Unifont-LICENSE.txt").read_text() + "\n\n" +
                (root / "rockbox-firmware/docs/COPYING").read_text() + "\n\n" +
                (root / "rockbox-firmware/fonts/COPYING").read_text())
            new.writestr(".podthingsloader/fonts/PodThings-Sans-LICENSES.txt",
                         license_text)
        if any(name.startswith(".podthingsloader/wps/podthingsos-liquid-glass/")
               for name in seen):
            root = Path(__file__).resolve().parents[1]
            new.writestr(".podthingsloader/themes/podthings-licenses/Yosemite-LICENSE.txt",
                         (root / "assets/wallpapers/Yosemite-LICENSE.txt").read_bytes())
    print(f"Branded runtime package: {output}")


if __name__ == "__main__":
    package(Path(sys.argv[1]), Path(sys.argv[2]))
