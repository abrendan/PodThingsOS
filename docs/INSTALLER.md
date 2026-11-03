# Installer package contract

This document describes the package format for installer developers.
For end-user installation and updates, use the **PodThings OS Installer** at
**[https://podthings.space/](https://podthings.space/)** for Video, Classic, and
Photo/Color. Nano 3G is not supported by that installer; see the
[Nano-specific installation instructions](INSTALLATION.md#nano-3g-a1236).

Every downloadable release archive contains UTF-8 JSON named `installer.config`
at its root. In the source tarball it is inside the single source root directory.
This is metadata, not executable configuration. Reject unknown schema versions.
All archive hashes are regenerated when metadata changes.

Example firmware-only update:

```json
{
  "schema_version": 1,
  "product": "PodThings OS",
  "package_type": "firmware-update",
  "release_version": "0.8",
  "installable": true,
  "target": "ipod6g",
  "minimum_bootloader_version": "0.8",
  "firmware_directory": ".podthingsloader",
  "firmware_file": "podthingsos.ipod"
}
```

## Types and targets

- `device-kit`: firmware plus matching bootloader; `firmware_archive` identifies
  the nested firmware ZIP and `bundled_bootloader_version` describes its loader.
- `firmware-update`: `.podthingsloader/` is directly at ZIP root.
- `themes`: installs theme assets only; never flashes a bootloader.
- `bundle`: not directly installable. Select the exact model's child manifest
  using `packages[].config`, then process that model kit.
- `source` and `diagnostic`: not normal firmware installations; never run the
  ordinary firmware updater on these. The Nano diagnostic is a separate RAM
  diagnostic, not a persistent bootloader installation.

Targets: `ipodvideo` = Video 5G, `ipod6g` = Classic 6G,
`ipodnano3g` = Nano 3G A1236, `ipodcolor` = Photo/Color 4G (220×176 color LCD).
Do not map monochrome 4G or Mini devices to `ipodcolor`. Its native image magic
is `ipco`, model number 3, and first compatible PodThings loader is 0.9.5.
Photo uses the PortalPlayer disk-firmware installation path, not Classic/Nano
NOR/DFU installation. Capacity alone is not a model identifier.
`minimum_bootloader_version` is a version string on firmware-bearing packages.
`null` on themes/source/diagnostic/bundle is **not** permission to bypass the
child firmware's requirement or to treat unknown metadata as compatible.

## Bootloader compatibility

Compare numeric version components, padded with zero: `0.10` is newer than
`0.8`; `0.8` equals `0.8.0`. Never compare strings or decimals. Unknown, upstream,
unverified and prerelease loader versions do not establish compatibility.

The minimum for Video 5G/5.5G **0.8.3** firmware is bootloader **0.8.3**,
including the revised awake-disk Apple handoff.
Classic 6G and Nano 3G 0.8.3 firmware still require **0.8**. This is not
proof that older loaders fail; their compatibility has not been verified.
Future requirements are maintained independently of release numbers in
`assets/installer/bootloader-requirements.json`. Do not automatically raise
them for theme-only or compatible firmware changes.

These files do **not** implement device-side bootloader version detection.
Do not infer the installed loader from the disk's firmware `rockbox-info.txt`:
firmware and NOR/disk bootloader can be updated independently. If a trusted
bootloader-version probe is unavailable, require a verified loader installation
or ask the user to establish the version before allowing firmware-only mode.
An old or unknown loader must not be silently retained or automatically flashed.

## Safe installation

Verify archive hashes against trusted release metadata. Internal SHA256SUMS
detect corruption, not maliciously substituted releases. Check actual hardware
and image model identifiers, reject unsafe archive paths/symlinks, and preserve
user settings/media. Copy only the intended firmware/theme tree, not metadata.
Back up before writing; stage and verify files with recovery on interrupted
updates. Keep bootloader flashing separate, explicit and model-specific.
Nano DFU/NOR payloads are not interchangeable with Classic/Video images.
The metadata itself never authorizes flashing or weakens NAND write safeguards.

## Release contents

Installable releases contain firmware, bootloaders/recovery payloads, themes,
`installer.config`, checksums and required license notices. They do not contain
Markdown guides, developer build/stack reports or embedded source archives.
Documentation stays in the repository; matching GPL source is published as a
separate release asset. Runtime metadata and functional plugin help/resources
remain part of the firmware where needed. This policy applies to subsequent
packaging; it does not retroactively alter previously published ZIPs.
