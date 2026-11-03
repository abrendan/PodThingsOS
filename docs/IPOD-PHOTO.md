# iPod Photo / Color installation

## Exact model

This kit is for the color-screen fourth-generation iPod Photo and iPod with
color display, target `ipodcolor`, 220×176 RGB565 LCD, 32 MB RAM. It is not for
the monochrome 4G, Mini, Video, Classic or Nano. Identify the model independently;
disk capacity alone is not sufficient.

## Back up first

Back up the accessible disk and preserve a working restore path. Installation
changes the hidden Apple firmware partition. Use the **PodThings OS Installer**
from **[https://podthings.space/](https://podthings.space/)** and follow its
instructions for Photo/Color. Do not select another model if Photo/Color is
not offered. The installer is separate from this firmware repository; build
and packaging commands do not access a device.

## Files

- `firmware/podthingsos-firmware.zip`: complete firmware and resources for
  installation by the PodThings OS Installer.
- `bootloader/bootloader-ipodcolor.ipod`: Photo/Color bootloader payload for
  the PodThings OS Installer, not a Classic/Nano DFU/NOR payload.
  Do not use a Video loader or a generic third-party flashing tool.
- `installer.config`: exact target `ipodcolor`, minimum bootloader 0.9.5.
- `COPYING`: GPL license. Matching source is distributed separately; installation
  guidance and release history are in this repository.

The main file `.podthingsloader/podthingsos.ipod` is firmware, not a bootloader.
Copying it does not install or update the bootloader.
All 12 native Photo themes are included in the complete firmware folder.
The separate shared 320×240 theme-only ZIP is not a Photo theme update.

## Features and recovery

The default cold start is PodThings OS; Hold selects Apple firmware. Selecting
Apple or stock Rockbox as the default reverses Hold to PodThings OS recovery.
Stock Rockbox is offered only when `/.rockbox` exists, and its image/resources
remain separate. One-time reboot actions never change the saved default.

The Apple firmware partition fallback is read-only and bounds/checksum checked.
Apple Disk Mode uses the upstream PP5020 cookie at `0x40017f00`. No Apple NOR
patching, guessed S5L addresses or USB substitute is used.

## Validation limits

Native builds and host/simulator tests cannot establish physical ATA/adapter
compatibility, charging behavior, audio playback, Apple boot or Disk Mode.
This is a new, not-yet-hardware-tested target. Start with a complete backup.
Performance and text capacity cannot be identical to a 320×240 Classic.

## Build from the supplied source

Use the toolchain and host dependencies described in the root README, then:

```sh
JOBS=3 bash scripts/rockbox-build.sh ipodcolor firmware
JOBS=3 bash scripts/rockbox-build.sh ipodcolor bootloader
JOBS=3 bash scripts/rockbox-build.sh ipodcolor checkwps
JOBS=3 bash scripts/rockbox-build.sh ipodcolor simulator
python3 scripts/package-podthings-release.py --target ipodcolor
```

These commands build or package local files only; they do not flash a device.
