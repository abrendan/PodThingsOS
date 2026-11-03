#!/usr/bin/env python3
"""Shared release metadata. Does not detect devices, install or flash anything."""
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "assets/installer/bootloader-requirements.json"
TARGETS = ("ipodvideo", "ipod6g", "ipodnano3g", "ipodcolor")
KINDS = ("device-kit", "firmware-update", "themes", "bundle", "source", "diagnostic")


def config(kind, version, target=None):
    if kind not in KINDS:
        raise ValueError(f"Unsupported package type: {kind}")
    if not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", version):
        raise ValueError("Release versions must be numeric major.minor[.patch]")
    data = {
        "schema_version": 1,
        "product": "PodThings OS",
        "package_type": kind,
        "release_version": version,
        "installable": kind in ("device-kit", "firmware-update", "themes"),
        "target": target,
        "minimum_bootloader_version": None,
    }
    if kind in ("device-kit", "firmware-update", "diagnostic"):
        if target not in TARGETS:
            raise ValueError("An exact supported model is required")
    elif target is not None:
        raise ValueError("This package type has no single target")
    if kind in ("device-kit", "firmware-update", "bundle"):
        policy = json.loads(POLICY.read_text())
        if set(policy) != set(TARGETS):
            raise ValueError("Incomplete bootloader compatibility policy")
        for minimum in policy.values():
            if not isinstance(minimum, str) or not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", minimum):
                raise ValueError("Invalid minimum bootloader version")
    if kind in ("device-kit", "firmware-update"):
        data.update(
            minimum_bootloader_version=policy[target],
            firmware_directory=".podthingsloader",
            firmware_file="podthingsos.ipod",
        )
        if kind == "device-kit":
            data.update(
                bundled_bootloader_version=version,
                firmware_archive="firmware/podthingsos-firmware.zip",
            )
    elif kind == "bundle":
        data["packages"] = [
            {"target": name, "minimum_bootloader_version": policy[name],
             "config": f"{name}/installer.config"} for name in TARGETS
        ]
    elif kind == "themes":
        # The standalone shared theme pack contains 320x240 skins. Photo's
        # native 220x176 presets are distributed in its complete firmware kit.
        data["supported_targets"] = [name for name in TARGETS if name != "ipodcolor"]
    return (json.dumps(data, indent=2) + "\n").encode()


def release_payload(files):
    """Keep installable payloads/metadata/licenses, not developer documents."""
    result = {}
    for name, data in files.items():
        parts = Path(name).parts
        lower = name.lower()
        basename = Path(lower).name
        if (lower.endswith((".md", ".markdown", ".rst"))
                or any(part.lower() in ("source", "docs", "debug") for part in parts)
                or basename in ("readme", "changelog", "contributing",
                                "build-info.txt", "firmware-build-info.txt",
                                "bootloader-build-info.txt")):
            continue
        result[name] = data
    return result


def firmware_archive(raw, version, target):
    """Keep firmware bytes intact, omit developer docs, and refresh metadata."""
    output = io.BytesIO()
    checksums = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(output, "w") as dest:
        if source.testzip():
            raise ValueError("Corrupt input firmware archive")
        for entry in source.infolist():
            if entry.filename in ("installer.config", "SHA256SUMS", "COPYING"):
                continue
            if not release_payload({entry.filename: b""}):
                continue
            data = source.read(entry)
            dest.writestr(entry, data)
            if not entry.is_dir():
                checksums[entry.filename] = hashlib.sha256(data).hexdigest()
        # Standalone firmware updates need the same GPL notice as full kits.
        license_data = (ROOT / "rockbox-firmware/docs/COPYING").read_bytes()
        dest.writestr("COPYING", license_data)
        checksums["COPYING"] = hashlib.sha256(license_data).hexdigest()
        metadata = config("firmware-update", version, target)
        dest.writestr("installer.config", metadata)
        checksums["installer.config"] = hashlib.sha256(metadata).hexdigest()
        dest.writestr("SHA256SUMS", "".join(
            f"{digest}  {name}\n" for name, digest in sorted(checksums.items())))
    return output.getvalue()


if __name__ == "__main__":
    # Used by the theme-only packager, which has no firmware/bootloader payload.
    if len(sys.argv) != 4 or sys.argv[1] != "themes":
        raise SystemExit("Usage: installer_config.py themes VERSION OUTPUT")
    Path(sys.argv[3]).write_bytes(config(sys.argv[1], sys.argv[2]))
