# Installation and recovery

Use the package for your exact iPod model. Back up your files and have an Apple
recovery/restore route available before installing a bootloader. Restore may
erase the device. The installer is maintained separately from this firmware
repository.

## Install or update with the PodThings OS Installer

These steps apply to **Video, Classic, and Photo/Color**. The installer does
**not** support Nano 3G; use the [Nano-specific steps below](#nano-3g-a1236).

1. Back up your iPod's files.
2. Visit **[https://podthings.space/](https://podthings.space/)** and download
   the **PodThings OS Installer**.
3. Connect your iPod, choose the exact model, and follow the installer's
   instructions for installation or an update.
4. Wait for completion and safely eject as directed by the installer.

If your model is not offered, stop rather than selecting another model.
For these models, do not substitute generic PortalPlayer/Classic installers or
manually send DFU payloads. Use the PodThings OS Installer instead.

## Firmware and bootloader compatibility

The package's `installer.config` identifies the minimum bootloader compatible
with a firmware-only update. The minimum
compatible versions for 0.9.6 are:

| Model | Minimum bootloader |
| --- | --- |
| Video 5G / 5.5G | 0.9.3 |
| Classic 6G | 0.9.4 |
| Nano 3G | 0.9.4 |
| Photo / Color 4G | 0.9.5 |

A disk firmware version does not establish the installed bootloader version.
Updating files cannot update a bootloader stored in boot flash or the firmware
partition. Never use the main firmware `.ipod` image as a bootloader.

Do not mix model images, bypass model checks, or format an unexpectedly exposed
disk. Disconnect other iPods during installation. Photo/Color users should also
read the [model limitations](IPOD-PHOTO.md).

## Nano 3G (A1236)

**Nano 3G is not supported by the PodThings OS Installer.**
Back up your files and copy the complete firmware folder using a working Apple
disk mode before installing the bootloader. For later firmware-only updates,
extract the matching Nano firmware-update ZIP to the iPod's root, merging
`.podthingsloader` and replacing its bundled files, including codecs and plugins.
Safely eject before restarting.

The Nano kit includes these model-specific payloads:

- `bootloader/bootloader-ipodnano3g.ipod`
- `bootloader/install-nano3g-dualboot.dfu`
- `bootloader/uninstall-nano3g-dualboot.dfu`
- `diagnostic/podthings-nano3g-readonly.dfu` (RAM diagnostic, not an installer)

Send the prebuilt Nano installer DFU with a compatible generic DFU sender.
With the community `mks5lboot64.exe` sender, from the extracted Nano kit:

```powershell
.\mks5lboot64.exe --dfusend .\bootloader\install-nano3g-dualboot.dfu
```

Use only the sender's generic DFU transfer mode with the Nano payload. Its
Classic-specific `.ipod` installer/uninstaller modes are not Nano-compatible.
Never substitute Classic images or send the main firmware as a bootloader.

Bootloader installation **writes NOR boot flash**; it is not RAM-only.
Disconnect other iPods, close Apple desktop software, enter Nano DFU mode, and
confirm detection before sending. Keep power connected during installation.
Successful USB transfer alone does not prove successful installation; retain
any on-device error for troubleshooting.

The matching uninstaller also writes NOR. It cannot repair NAND corruption.
The RAM diagnostic always rejects NAND writes.

Nano release builds explicitly enable writes for the recognized NAND ID/bank
combinations. Only one 4 GB variant has user-reported installation and playback
testing; other recognized variants can still corrupt data and require a restore.
Unknown combinations remain rejected. The normal bootloader mounts the FTL
read-only; its NOR installer is separate.

## Boot choices and limitations

One-time firmware requests do not change the saved boot default. Hold provides
a route back into PodThings OS when another firmware is the default.

Reboot to Official Firmware is implemented on Video, Classic and Photo, not
Nano. Photo's physical Apple handoff and Apple Disk Mode remain unconfirmed.
Classic and Nano do not expose Reboot to Disk Mode: their real Apple software
entry path is unresolved, and bootloader USB is not a substitute.

## Packages and source

Complete model kits contain firmware, bootloader, themes, plugins, installer
metadata, checksums, licenses and necessary safety notices. Developer documents
are kept in this repository, not embedded in binary packages. Corresponding GPL
source is distributed separately.

See [hardware testing](HARDWARE-TESTING.md), [installer metadata](INSTALLER.md),
and [release history](../CHANGELOG.md).
