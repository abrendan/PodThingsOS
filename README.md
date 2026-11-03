<p align="center">
  <img src="assets/branding/podthings.svg" width="88" alt="PodThings OS logo">
</p>

<h1 align="center">PodThings OS</h1>
<p align="center">A modern, click-wheel-first firmware for classic iPods.<br>Built by abrendan. Based on Rockbox.</p>

---

**PodThings OS** is a native Rockbox fork with iPod-style navigation, a modern
interface and support for existing iTunes music libraries. This repository
contains the actual firmware, bootloader, themes and native build tools.
The desktop installer is maintained separately and is available at
[podthings.space](https://podthings.space/).

## Supported iPods

| Model | Build target | Current test evidence |
| --- | --- | --- |
| iPod Video 5G | `ipodvideo` | User-reported physical navigation/theme testing; patched Apple handoff not yet confirmed |
| iPod Classic 6G | `ipod6g` | User-reported physical testing |
| iPod Nano 3G, A1236 | `ipodnano3g` | Installation and playback confirmed on one 4 GB NAND variant |
| iPod Photo / Color 4G | `ipodcolor` | New native port; builds/host checks, not yet physically tested |

**Current release: 0.9.6** for all four targets. Includes corrected iTunes
thumbnail padding, isolation of malformed artwork headers and automatic cover
cache refreshes. See the [changelog](CHANGELOG.md) for release history.

Photo/Color includes the same core features and 12 themes at its native 220×176
resolution. It is not for the monochrome 4G or iPod Mini. See
[Photo installation and limitations](docs/IPOD-PHOTO.md).

Use the matching model's complete firmware, including plugins. A working build
does not establish physical-device compatibility. Nano write support for
untested recognized NAND variants can cause data loss or require an Apple
restore. Read the [installation and recovery guide](docs/INSTALLATION.md) first.

## Highlights

- **Familiar controls:** Menu goes back, Center enters, and the wheel navigates.
- **Modern themes:** rounded menus, album artwork, readable typography and
  Current (default), Blue, Purple, Mint, Rose, Amber,
  Graphite, Pearl, Sky and Lavender palettes, plus a
  Liquid Glass–inspired style with shaded panels and subtle reflective rims.
  Choose themes in Settings > Appearance > Change Theme.
  See [theme installation](docs/THEME-TESTING.md).
- **Boot choices:** normal boot uses your chosen firmware; Hold selects Apple
  with the PodThings default, or PodThings OS with either alternative default.
  Stock Rockbox lives separately in `/.rockbox/rockbox.ipod`.
- **Music integration:** use iTunes playlists without editing them, prefer
  iTunes artwork, then embedded art, then a placeholder.
- **Cover Flow and Shuffle Songs:** browse albums and start playback directly.
- **Now Playing:** wheel scrubbing, temporary volume feedback, guarded metadata
  while tracks load, and an **iPod** label when branding is disabled.
- **Unicode fonts:** broad CJK and other language coverage with bundled
  license notices; coverage is not a promise of full complex-script shaping.
- **Compatibility:** matching bundled codecs/plugins and loadable Rockbox
  themes. Third-party themes retain their own layouts.

## Install or update

Use the **PodThings OS Installer** from
**[https://podthings.space/](https://podthings.space/)** for installation and
updates on **Video, Classic, and Photo/Color—not Nano 3G**.
Nano users should follow the [Nano installation instructions](docs/INSTALLATION.md#nano-3g-a1236).
Back up your iPod first, choose your exact model, and follow the
installer's instructions. If your model is not offered, stop rather than
selecting a different one.

Firmware lives at:

```text
/.podthingsloader/podthingsos.ipod
```

A firmware update is not a bootloader flash. On Video, Classic, and Photo/Color,
use the PodThings OS Installer
instead of generic third-party flashing tools or manually sending bootloader
payloads. **Never flash the main firmware `.ipod` file to boot flash or mix
model images.** Safely eject when the installer says the operation is complete.

See [installation and recovery](docs/INSTALLATION.md). The one-time
**Reboot to Official Firmware** setting is implemented on Video, Classic and
Photo; Photo hardware handoff is unconfirmed, and Nano's NAND-based equivalent
is not implemented. Reboot to Apple's Disk Mode is available on Video and has
an unconfirmed Photo path; it is not exposed on Classic or Nano.

Generated downloads belong in **GitHub Releases**, not the source repository.
Local builds are written to the ignored `generated-artifacts/` directory.

## Build from source

Release ZIPs include a small JSON `installer.config` identifying the model and
minimum bootloader needed for a firmware-only update. See the
[installer package contract](docs/INSTALLER.md). Bootloader requirements are
maintained separately from firmware versions; an unknown installed loader must
not be assumed compatible.

Linux is the documented build host; use WSL2 on Windows. You need Python 3,
Perl, GNU Make, a host C/C++ compiler, zip/unzip, pkg-config, FreeType development
files, librsvg (`rsvg-convert`), and the Rockbox ARM toolchain. Building the
toolchain also needs the prerequisites listed by `rockboxdev.sh` (including
bison, flex, texinfo and GMP/MPFR/MPC development libraries).
Skin checking/simulation additionally needs SDL development files.

On Debian/Ubuntu, a typical host setup is:

```sh
sudo apt-get install build-essential python3 perl zip unzip pkg-config \
  libfreetype6-dev librsvg2-bin libsdl2-dev bison flex texinfo \
  libgmp-dev libmpfr-dev libmpc-dev autoconf automake libtool
```

Install the toolchain with the upstream helper and select its ARM toolchain:

```sh
RBDEV_PREFIX="$PWD/.local/rockbox-toolchain" \
  bash rockbox-firmware/tools/rockboxdev.sh
```

The wrapper also accepts an existing `arm-elf-eabi-gcc` on `PATH`. Builds never
flash a connected device.

```sh
bash scripts/rockbox-build.sh ipodvideo firmware
bash scripts/rockbox-build.sh ipodvideo bootloader
bash scripts/rockbox-build.sh ipodvideo checkwps
```

Replace `ipodvideo` with `ipod6g` for Classic or `ipodcolor` for Photo/Color.
Build firmware and bootloader for each target before packaging a combined
release. To reproduce the Nano release's explicit opt-in write policy:

```sh
PODTHINGS_NANO_UNVALIDATED_WRITES=1 PODTHINGS_STACK_USAGE=1 \
  bash scripts/rockbox-build.sh ipodnano3g firmware
PODTHINGS_NANO_UNVALIDATED_WRITES=1 \
  bash scripts/rockbox-build.sh ipodnano3g bootloader
bash scripts/rockbox-build.sh ipodnano3g nandcheck
bash scripts/rockbox-build.sh ipodnano3g checkwps
```

Omitting the write switch preserves the protected default. The RAM-only
diagnostic rejects NAND writes regardless of that policy. Unknown chip/bank
combinations remain rejected. Do not treat label removal as validation.

`VERSION` supplies the default release number. Set `PODTHINGS_VERSION` only
when intentionally building a different version.

### Tests and release packages

```sh
bash scripts/prepare-host-tests.sh
python3 scripts/check-public-repo.py
ASAN_OPTIONS=detect_leaks=0 python3 -m unittest discover -s tests -p 'test_*.py'

# After building all targets above:
bash scripts/rockbox-theme-package.sh
python3 scripts/package-podthings-release.py
```

The release packager checks all four already-built targets, invokes the Nano
packager, and creates the combined download. To package Nano alone, run
`PODTHINGS_NANO_UNVALIDATED_WRITES=1 python3 scripts/package-podthings-nano.py`.

Nano DFU packaging needs the host `mks5lboot` builder before packaging:

```sh
make -C rockbox-firmware/utils/mks5lboot
```

On Linux, install `libusb-1.0-0-dev` first. Packaging validates ARM images,
model/API compatibility, skins, fonts and archive contents, and publishes
corresponding GPL source separately with hashes. Binary kits contain no
developer documents. Host checks do not prove physical
playback, write endurance or recovery. GitHub Actions runs the host tests only.

## Repository layout

```text
rockbox-firmware/   Native fork, bootloader, codecs, plugins and themes
assets/            Branding sources, fonts and their licenses
scripts/           Build, asset generation, test preparation and packaging
tests/             Host-side regression tests and native C harnesses
docs/              Current release, hardware, theme and music documentation
.github/workflows/ Host-test CI
VERSION            Current release number
```

Development uploads, Replit metadata, caches, toolchains and generated releases
are kept out of the GitHub source tree. Git history is not rewritten by cleanup.

## Contributing and credits

See [CONTRIBUTING.md](CONTRIBUTING.md), [CHANGELOG.md](CHANGELOG.md) and
[upstream provenance](rockbox-firmware/UPSTREAM.md).

Created by **abrendan**, based on the work of the **Rockbox Team** and the
upstream Nano port contributors. Original author credits and copyright notices
remain intact.

The firmware is distributed under **GPL-2.0-or-later**, subject to the original
per-file notices. See [LICENSE](LICENSE) and the individual font/library
licenses. Bundled fonts and other third-party components retain their own terms.
