#!/usr/bin/env python3
"""Validate and package already-built native images. Never accesses an iPod."""
import hashlib
import argparse
import io
import os
import re
import runpy
import struct
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from installer_config import config as installer_metadata, firmware_archive, release_payload
OUTPUT = ROOT / "generated-artifacts/releases"
SOURCE = ROOT / "rockbox-firmware"
# The PodThings branch precedes the upstream branch in plugin.h. Validate
# against the actual source ABI, not a separately maintained release constant.
PLUGIN_API = int(re.search(r"^#define PLUGIN_API_VERSION\s+(\d+)$",
                          (SOURCE / "apps/plugin.h").read_text(), re.M).group(1))
THEMES = runpy.run_path(str(ROOT / "scripts/generate-podthings-logo.py"))["THEMES"]
VERSION = os.environ.get("PODTHINGS_VERSION", (ROOT / "VERSION").read_text().strip())
EXTRAS = [
    "rockbox-firmware/bootloader/ipodvideo-apple.c",
    "rockbox-firmware/bootloader/ipodvideo-apple.h",
    "tests/test_video_parity.py", "tests/video_apple_harness.c",
    "assets/installer/bootloader-requirements.json",
    "scripts/installer_config.py", "tests/test_installer_config.py",
    "docs/INSTALLER.md",
    "docs/INSTALLATION.md",
    "scripts/check-public-repo.py",
    "VERSION", "LICENSE", "CHANGELOG.md", "CONTRIBUTING.md",
    ".gitignore", "scripts/prepare-host-tests.sh",
    "scripts/package-podthings-nano.py",
    "tests/test_nano_port.py",
    "rockbox-firmware/apps/bitmaps/native/rockboxlogo.80x32x16.podthings.bmp",
    "rockbox-firmware/apps/podthings_scrub.c",
    "rockbox-firmware/apps/podthings_scrub.h",
    "tests/test_system_ui.py",
    "tests/test_coverflow_refinements.py",
    "rockbox-firmware/apps/podthings_artwork.c",
    "rockbox-firmware/apps/podthings_artwork.h",
    "tests/artwork_harness.c",
    "tests/test_itunes_artwork.py",
    "docs/ARTWORK.md",
    "rockbox-firmware/apps/podthings_music.h",
    "rockbox-firmware/apps/podthings_music.c",
    "tests/music_ui_harness.c",
    "tests/test_music_modernization.py",
    "tests/test_official_boot_sleep.py",
    "docs/MUSIC-NAVIGATION.md",
    "rockbox-firmware/apps/podthings_itunes.h",
    "rockbox-firmware/apps/podthings_itunes.c",
    "rockbox-firmware/apps/podthings_itunesdb.h",
    "rockbox-firmware/apps/podthings_itunesdb.c",
    "tests/test_itunes_playlists.py",
    "tests/test_itunes_ui.py",
    "tests/itunes_ui_harness.c",
    "docs/ITUNES-PLAYLISTS.md",
    "tests/test_ipod_battery.py",
    "tests/test_playback_update.py",
    "scripts/generate-podthings-fonts.py",
    "scripts/podthings-font-raster.c",
    "assets/fonts/DejaVuSans.ttf",
    "assets/fonts/DejaVu-COPYING.txt",
    "assets/fonts/Unifont-LICENSE.txt",
    "assets/fonts/FONT-SOURCES.md",
    "rockbox-firmware/fonts/16-GNU-Unifont.bdf",
    "tests/test_podthings_fonts.py",
    "rockbox-firmware/firmware/export/podthings_boot.h",
    "rockbox-firmware/firmware/common/podthings_boot.c",
    "tests/test_podthings_boot.py",
    "tests/podthings_boot_harness.c",
    "docs/OFFICIAL-FIRMWARE.md",
    "rockbox-firmware/UPSTREAM.md",
    "rockbox-firmware/apps/plugins/lib/podthings_branding.h",
    "rockbox-firmware/wps/podthings.320x240x16.wps",
    "rockbox-firmware/wps/podthings.320x240x16.sbs",
    "rockbox-firmware/apps/bitmaps/native/rockboxlogo.320x128x16.podthings.bmp",
    "rockbox-firmware/apps/bitmaps/native/rockboxlogo.160x64x16.podthings.bmp",
    "rockbox-firmware/apps/bitmaps/native/podthings_credits.96x100x16.bmp",
    "rockbox-firmware/wps/podthings/backdrop.bmp",
    "rockbox-firmware/wps/podthings/branding.bmp",
    "rockbox-firmware/wps/podthings/seek-dot.bmp",
    "assets/branding/podthings.svg",
    "assets/branding/abrendan.svg",
    "README.md",
    "docs/HARDWARE-TESTING.md",
    "docs/NAVIGATION.md",
    "docs/THEME-TESTING.md",
    "scripts/rockbox-build.sh",
    "scripts/brand-podthings-package.py",
    "scripts/rockbox-theme-package.sh",
    "scripts/generate-podthings-logo.py",
    "scripts/package-podthings-release.py",
    "tests/test_ipod_navigation.py",
    "tests/test_podthings_package.py",
]
for variant in THEMES:
    EXTRAS.extend((
        f"rockbox-firmware/wps/podthingsos-{variant}.320x240x16.wps",
        f"rockbox-firmware/wps/podthingsos-{variant}/backdrop.bmp",
        f"rockbox-firmware/wps/podthingsos-{variant}.320x240x16.sbs",
        f"rockbox-firmware/wps/podthingsos-{variant}/art-mask.bmp",
        f"rockbox-firmware/wps/podthingsos-{variant}/battery.bmp",
        f"rockbox-firmware/wps/podthingsos-{variant}/selection.bmp",
        f"rockbox-firmware/wps/podthingsos-{variant}/branding.bmp",
        f"rockbox-firmware/wps/podthingsos-{variant}/seek-dot.bmp",
        f"rockbox-firmware/wps/podthingsos-{variant}/volume-panel.bmp",
        f"rockbox-firmware/wps/podthingsos-{variant}/volume-track.bmp",
        f"rockbox-firmware/wps/podthingsos-{variant}/volume-fill.bmp",
    ))
EXTRAS.append("rockbox-firmware/wps/podthingsos-liquid-glass/menu-backdrop.bmp")
EXTRAS.extend(("assets/wallpapers/yosemite.png",
               "assets/wallpapers/Yosemite-LICENSE.txt", "tests/test_theme_collection.py"))


def validate_elf(path, brand):
    image = path.read_bytes()
    if image[:6] != b"\x7fELF\x01\x01" or struct.unpack_from("<H", image, 18)[0] != 40:
        raise ValueError(f"Not a 32-bit little-endian ARM ELF: {path}")
    if brand not in image:
        raise ValueError(f"Expected compiled branding is missing: {path}")

def validate_unicode_font(data, height):
    """Validate the actual RB12 file, not just source BDF glyph membership."""
    (magic, maxwidth, actual_height, ascent, depth, first, default, count,
     nbits, noffset, nwidth) = struct.unpack_from("<4s4H6I", data)
    if (magic != b"RB12" or actual_height != height or depth != 0
            or noffset != count or nwidth != count or len(data) > 5 * 1024 * 1024):
        raise ValueError(f"Invalid {height}px Unicode font header/size")
    alignment = 2 if nbits < 0xffdb else 4
    start = (36 + nbits + alignment - 1) & ~(alignment - 1)
    fmt = "H" if alignment == 2 else "I"
    offsets = struct.unpack_from("<" + fmt * noffset, data, start)
    width_start = start + alignment * noffset
    widths = data[width_start:width_start + nwidth]
    if len(widths) != nwidth or max(widths) > maxwidth:
        raise ValueError("Glyph advance exceeds native font/cache bounds")
    for offset, width in zip(offsets, widths):
        if offset + width * ((height + 7) // 8) > nbits:
            raise ValueError("Glyph bitmap points outside font data")
    for char in "한국어日本語かなカナ简体中文繁體ΕλληνικάРусский":
        index = ord(char) - first
        if (not 0 <= index < count or widths[index] == 0 or
                offsets[index] == offsets[default - first]):
            raise ValueError(f"Missing compiled glyph: {char}")
        length = widths[index] * ((height + 7) // 8)
        if not any(data[36 + offsets[index]:36 + offsets[index] + length]):
            raise ValueError(f"Empty compiled glyph: {char}")


def device_package(target, magic):
    photo = target == "ipodcolor"
    prefix = "photo-" if photo else ""
    base = ROOT / "generated-artifacts/rockbox"
    firmware_dir = base / f"{target}-firmware"
    boot_dir = base / f"{target}-bootloader"
    firmware_zip = firmware_dir / "podthingsos-firmware.zip"
    boot_name = f"bootloader-{target}.ipod"
    boot_image = (boot_dir / boot_name).read_bytes()
    validate_elf(firmware_dir / "rockbox.elf", b"PodThings OS")
    validate_elf(boot_dir / "bootloader.elf", b"PodThings OS boot loader")
    validate_elf(firmware_dir / "rockbox.elf", b"abrendan")
    validate_elf(firmware_dir / "rockbox.elf", b"Rockbox Credits")
    validate_elf(firmware_dir / "rockbox.elf", b"Rockbox Team")
    validate_elf(firmware_dir / "rockbox.elf", b"Reboot to Official Firmware")
    validate_elf(boot_dir / "bootloader.elf", b"Built by abrendan")
    validate_elf(boot_dir / "bootloader.elf", b"based on Rockbox")
    validate_elf(firmware_dir / "rockbox.elf", b"PodThing OS - %s - Based on Rockbox")
    with zipfile.ZipFile(firmware_zip) as archive:
        if archive.testzip() is not None:
            raise ValueError(f"Corrupt firmware archive: {target}")
        required = (
            ".podthingsloader/podthingsos.ipod",
            ".podthingsloader/wps/podthingsos-purple.wps",
            f".podthingsloader/wps/podthingsos-purple/{prefix}backdrop.bmp",
            ".podthingsloader/themes/podthingsos-purple.cfg",
            (".podthingsloader/fonts/12-Adobe-Helvetica.fnt" if photo else
             ".podthingsloader/fonts/22-PodThings-Sans.fnt"),
            ".podthingsloader/fonts/16-PodThings-Sans.fnt",
            ".podthingsloader/fonts/PodThings-Sans-LICENSES.txt",
            ".podthingsloader/podthings-info.txt",
        )
        for name in required:
            if not archive.read(name):
                raise ValueError(f"Missing or empty package asset: {name}")
        for height in ((16,) if photo else (16, 22)):
            validate_unicode_font(
                archive.read(f".podthingsloader/fonts/{height}-PodThings-Sans.fnt"),
                height)
        for name in archive.namelist():
            if not name.startswith(".podthingsloader/") or "rockbox" in name.lower():
                raise ValueError(f"Legacy or invalid installed filename: {name}")
            if name.endswith(("/config.cfg", "/boot-official-once")):
                raise ValueError(f"Unsafe update entry: {name}")
        firmware = archive.read(".podthingsloader/podthingsos.ipod")
        if ".podthingsloader/podthings.ipod" in archive.namelist():
            raise ValueError("Obsolete firmware filename in archive")
        if b"PodThings OS" not in archive.read(".podthingsloader/wps/podthingsos-purple.wps"):
            raise ValueError("Old playback branding in firmware archive")
        for variant in THEMES:
            skin=archive.read(f".podthingsloader/wps/podthingsos-{variant}.wps")
            if b"%?pN<%Vd(P)%Vd(L)|%Vd(I)>" not in skin or b"\niPod\n" not in skin:
                raise ValueError(f"Missing unbranded iPod fallback: {variant}")
        config = archive.read(".podthingsloader/themes/podthingsos-purple.cfg")
        font = b"16-PodThings-Sans.fnt" if photo else b"22-PodThings-Sans.fnt"
        if b"/.podthingsloader/" not in config or font not in config:
            raise ValueError("Incorrect theme directory or font")
        if b"list padding: 8" not in config:
            raise ValueError("Missing modern list spacing")
        for variant, palette in THEMES.items():
            background, accent = palette["bg"].encode(), palette["accent"].encode()
            name = f"podthingsos-{variant}"
            preset = archive.read(f".podthingsloader/themes/{name}.cfg")
            if b"background color: " + background not in preset:
                raise ValueError(f"Incorrect {variant} theme background")
            if b"line selector start color: " + accent not in preset:
                raise ValueError(f"Incorrect {variant} theme selection color")
            if f"/.podthingsloader/wps/{name}.wps".encode() not in preset:
                raise ValueError(f"Incorrect {variant} theme skin")
            for member in (f"wps/{name}.wps", f"wps/{name}.sbs",
                           *(f"wps/{name}/{p.name}" for p in (SOURCE / "wps" / name).glob("*.bmp")
                             if p.name.startswith("photo-") == photo)):
                if not archive.read(f".podthingsloader/{member}"):
                    raise ValueError(f"Missing {variant} theme asset")
    for label, image in (("firmware", firmware), ("bootloader", boot_image)):
        if b"/.podthingsloader/boot-official-once" not in image:
            raise ValueError(f"Missing one-shot boot protocol in {target} {label}")
        if b"/.podthingsloader" not in image or b"podthingsos.ipod" not in image:
            raise ValueError(f"Missing matching loader path in {target} {label}")
        if b"ptos-0.2-dev" in image or b"Development menu" in image:
            raise ValueError(f"Old development label in {target} {label}")
        model_config = SOURCE / f"firmware/export/config/{target}.h"
        model = int(re.search(r"^#define MODEL_NUMBER\s+(\d+)",
                              model_config.read_text(), re.MULTILINE)[1])
        if struct.unpack(">I", image[:4])[0] != (sum(image[8:]) + model) & 0xffffffff:
            raise ValueError(f"Invalid native image checksum: {target} {label}")
    if b"podthingsos-current" not in firmware:
        raise ValueError("Current is not compiled as the default skin")
    for build in (firmware_dir, boot_dir):
        if f'#define RBVERSION "{VERSION}"' not in (build / "rbversion.h").read_text():
            raise ValueError(f"Unexpected displayed version: {build}")
    if firmware != (firmware_dir / "podthingsos.ipod").read_bytes():
        raise ValueError("Stale firmware archive")
    if firmware[4:8] != magic or boot_image[4:8] != magic:
        raise ValueError(f"Image model identifier mismatch: {target}")
    if VERSION:
        validate_elf(firmware_dir / "rockbox.elf", b"iTunes Playlists (read-only)")
        validate_elf(firmware_dir / "rockbox.elf", b"/iPod_Control/iTunes/iTunesDB")
        for label in (b"Continue Listening", b"Recently Played Albums",
                      b"Cover Flow", b"A-Z Jump", b"Appearance", b"Advanced"):
            validate_elf(firmware_dir / "rockbox.elf", label)
        if b"One-time OF request" in boot_image or b"One-Time OF request" in boot_image:
            raise ValueError("Technical one-shot diagnostic remains in bootloader")
        with zipfile.ZipFile(firmware_zip) as archive:
            if not archive.read(".podthingsloader/rocks/demos/pictureflow.rock"):
                raise ValueError("Cover Flow engine missing")
            tagmenu = archive.read(".podthingsloader/tagnavi.config")
            if b"/.rockbox/" in tagmenu or b'"Music Library"' not in tagmenu:
                raise ValueError("Old library navigation or resource paths")
            if VERSION:
                engine = archive.read(".podthingsloader/rocks/demos/pictureflow.rock")
                if VERSION:
                    for name in archive.namelist():
                        if name.endswith(".rock"):
                            plugin=archive.read(name)
                            expected_api=PLUGIN_API
                            if len(plugin)<8 or struct.unpack_from("<H",plugin,6)[0]!=expected_api:
                                raise ValueError(f"Plugin API mismatch: {name}")
                    for variant in THEMES:
                        skin=archive.read(f".podthingsloader/wps/podthingsos-{variant}.wps")
                        seek = (b"%pb(0,0,204,7,-,noborder,slider,D)" if photo else
                                b"%pb(0,0,296,9,-,noborder,slider,D)")
                        if b"%?pJ<%Vd(s)%Vd(t)|" not in skin or seek not in skin:
                            raise ValueError("Seek-mode indicator missing")
                        if VERSION:
                            if b"turn wheel" in skin or b"%?pN<%Vd(P)%Vd(L)|%Vd(I)>" not in skin:
                                raise ValueError("Outdated seeking/branding theme")
                            if b"%?mv(2)<%Vd(v)%Vd(w)%Vd(z)|%Vd(n)%Vd(t)>" not in skin:
                                raise ValueError("Transient volume overlay missing")
                            for asset in ("branding", "seek-dot", "volume-panel",
                                          "volume-track", "volume-fill"):
                                archive.getinfo(f".podthingsloader/wps/podthingsos-{variant}/{prefix}{asset}.bmp")
                    validate_elf(firmware_dir / "rockbox.elf",
                                 b"Seeking unavailable for this track")
                if b"PictureFlow" in engine:
                    raise ValueError("Visible PictureFlow branding remains")
                for variant in THEMES:
                    skin = archive.read(f".podthingsloader/wps/podthingsos-{variant}.wps")
                    if b"%?pQ<" not in skin or b"Loading..." not in skin:
                        raise ValueError("Metadata-loading guard missing")
                validate_elf(firmware_dir / "rockbox.elf",
                             b"/iPod_Control/Artwork/ArtworkDB")

    update_bytes = firmware_archive(firmware_zip.read_bytes(), VERSION, target)
    files = {
        "installer.config": installer_metadata("device-kit", VERSION, target),
        "firmware/podthingsos-firmware.zip": update_bytes,
        f"bootloader/{boot_name}": boot_image,
        "COPYING": (SOURCE / "docs/COPYING").read_bytes(),
    }
    files = release_payload(files)
    files["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n"
        for name, data in files.items()
    ).encode()
    output = OUTPUT / f"PodThings-OS-{target}-{VERSION}.zip"
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data, compress_type=(
                zipfile.ZIP_STORED if name.endswith(".zip") else zipfile.ZIP_DEFLATED
            ))
    print(f"Validated ARM firmware + bootloader: {output.relative_to(ROOT)}")
    update = OUTPUT / f"PodThings-OS-{target}-{VERSION}-firmware-update.zip"
    update.write_bytes(update_bytes)
    return output


def source_package(version=VERSION):
    # Package the actual fork, not the old preserved upstream Git index.
    # This works in a normal GitHub clone and in an extracted source archive.
    saved_manifest = ROOT / "SOURCE-FILES.txt"
    roots = ["rockbox-firmware", "assets", "docs", "scripts", "tests", ".github",
             "README.md", "LICENSE", "VERSION", "CHANGELOG.md", "CONTRIBUTING.md",
             ".gitignore"]
    if (ROOT / ".git").exists():
        tracked = subprocess.check_output([
            "git", "--no-optional-locks", "-C", str(ROOT), "ls-files",
            "--cached", "--others", "--exclude-standard", "-z", "--", *roots,
        ]).decode().split("\0")
        paths = {path for path in tracked if path and
                 ((ROOT/path).is_file() or (ROOT/path).is_symlink())}
    elif saved_manifest.exists():
        paths = set(saved_manifest.read_text().splitlines())
    else:
        raise RuntimeError("Cannot identify the matching source file manifest")
    paths.update(EXTRAS)
    output = OUTPUT / f"PodThings-OS-source-{version}.tar.gz"
    prefix = "podthings-os-source"
    with tarfile.open(output, "w:gz", compresslevel=3, dereference=False) as archive:
        for name in sorted(paths):
            path = ROOT / name
            if not path.is_file() and not path.is_symlink():
                raise ValueError(f"Missing or unsupported source file: {name}")
            archive.add(path, arcname=f"{prefix}/{name}", recursive=False)
        manifest = ("\n".join(sorted(paths)) + "\n").encode()
        info = tarfile.TarInfo(f"{prefix}/SOURCE-FILES.txt")
        info.size = len(manifest)
        archive.addfile(info, io.BytesIO(manifest))
        metadata = installer_metadata("source", version)
        info = tarfile.TarInfo(f"{prefix}/installer.config")
        info.size = len(metadata)
        archive.addfile(info, io.BytesIO(metadata))
    print(f"Matching source: {output.relative_to(ROOT)}")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("ipodvideo", "ipod6g", "ipodnano3g", "ipodcolor"),
                        help="Package a model-specific patch release without rebuilding unrelated models")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    nano_env=dict(os.environ,PODTHINGS_NANO_UNVALIDATED_WRITES="1",
                  PODTHINGS_VERSION=VERSION)
    if args.target:
        if args.target == "ipodnano3g":
            subprocess.run([sys.executable,str(ROOT/"scripts/package-podthings-nano.py")],
                           env=nano_env,check=True)
            package = OUTPUT/f"PodThings-OS-ipodnano3g-{VERSION}.zip"
            source = OUTPUT/f"PodThings-OS-source-{VERSION}.tar.gz"
        else:
            package = device_package(args.target,
                {"ipodvideo": b"ipvd", "ipod6g": b"ip6g", "ipodcolor": b"ipco"}[args.target])
            source = source_package()
        update = OUTPUT/f"PodThings-OS-{args.target}-{VERSION}-firmware-update.zip"
        paths = [package, update, source]
        theme = ROOT/f"generated-artifacts/podthingsos-themes-{VERSION}.zip"
        if theme.exists():
            paths.append(theme)
        lines = []
        for path in paths:
            with path.open("rb") as stream:
                lines.append(f"{hashlib.file_digest(stream,'sha256').hexdigest()}  {path.name}\n")
        (OUTPUT/f"SHA256SUMS-{args.target}-{VERSION}").write_text("".join(lines))
        return
    # The Nano packager validates the already-built write policy. This never
    # builds with an implicit opt-in or connects to a device.
    subprocess.run([sys.executable,str(ROOT/"scripts/package-podthings-nano.py")],
                   env=nano_env,check=True)
    packages = [
        device_package("ipodvideo", b"ipvd"),
        device_package("ipod6g", b"ip6g"),
        OUTPUT/f"PodThings-OS-ipodnano3g-{VERSION}.zip",
        device_package("ipodcolor", b"ipco"),
        source_package(),
    ]
    theme = ROOT / f"generated-artifacts/podthingsos-themes-{VERSION}.zip"
    if not theme.exists():
        raise ValueError("Build and validate the matching theme pack first")
    with zipfile.ZipFile(theme) as archive:
        if archive.testzip():
            raise ValueError("Corrupt theme pack")
    bundle = OUTPUT / f"PodThings-OS-{VERSION}.zip"
    entries = {"installer.config": installer_metadata("bundle", VERSION)}
    for target, package_path in zip(("ipodvideo", "ipod6g", "ipodnano3g", "ipodcolor"), packages[:4]):
        with zipfile.ZipFile(package_path) as archive:
            model_files={}
            for name in archive.namelist():
                # Source is published as a separate release asset.
                if name=="SHA256SUMS" or name.startswith("source/"):
                    continue
                model_files[name]=archive.read(name)
            model_files["SHA256SUMS"]="".join(
                f"{hashlib.sha256(data).hexdigest()}  {name}\n"
                for name,data in model_files.items()).encode()
            entries.update({f"{target}/{name}":data for name,data in model_files.items()})
    entries[f"themes/{theme.name}"] = theme.read_bytes()
    entries = release_payload(entries)
    entries["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n"
        for name, data in entries.items()).encode()
    with zipfile.ZipFile(bundle, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data, compress_type=(
                zipfile.ZIP_STORED if name.endswith((".zip", ".gz"))
                else zipfile.ZIP_DEFLATED))
    packages += [OUTPUT / f"PodThings-OS-{target}-{VERSION}-firmware-update.zip"
                 for target in ("ipodvideo", "ipod6g", "ipodnano3g", "ipodcolor")]
    packages += [theme, bundle]
    (OUTPUT / f"SHA256SUMS-{VERSION}").write_text("".join(
        f"{hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()}  {path.name}\n"
        for path in packages
    ))


if __name__ == "__main__":
    main()
