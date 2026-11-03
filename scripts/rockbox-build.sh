#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Build the actual Rockbox targets. This never flashes a connected device.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="${1:-}"
kind="${2:-}"
case "$target" in
    ipodvideo|ipod6g|ipodnano3g|ipodcolor) ;;
    *) echo "Usage: $0 {ipodvideo|ipod6g|ipodnano3g|ipodcolor} {firmware|bootloader|nandcheck|checkwps|simulator}" >&2; exit 2 ;;
esac
case "$kind" in
    firmware) type=n ;;
    bootloader) type=b ;;
    nandcheck)
        [[ "$target" == ipodnano3g ]] || { echo "nandcheck is Nano 3G only" >&2; exit 2; }
        type=b ;;
    checkwps) type=C ;;
    simulator) type=s ;;
    *) echo "Usage: $0 {ipodvideo|ipod6g|ipodnano3g|ipodcolor} {firmware|bootloader|nandcheck|checkwps|simulator}" >&2; exit 2 ;;
esac

python3 "$root/scripts/generate-podthings-logo.py"
export PATH="$root/.local/rockbox-toolchain/bin:$PATH"
if [[ "$kind" == checkwps || "$kind" == simulator ]] && command -v pkg-config >/dev/null; then
    # Nix's sdl2-compat config helper expects SDL2_PATH for its header path.
    if pkg-config --exists sdl2; then
        export SDL2_PATH="$(pkg-config --variable=includedir sdl2)/SDL2"
    fi
fi
if [[ "$kind" == firmware || "$kind" == bootloader || "$kind" == nandcheck ]] && ! command -v arm-elf-eabi-gcc >/dev/null; then
    echo "Missing Rockbox arm-elf-eabi toolchain. See README.md." >&2
    exit 1
fi

build="$root/generated-artifacts/rockbox/$target-$kind"
experimental="${PODTHINGS_NANO_UNVALIDATED_WRITES:-0}"
if [[ "$experimental" != 0 && "$experimental" != 1 ]]; then
    echo "PODTHINGS_NANO_UNVALIDATED_WRITES must be 0 or 1" >&2; exit 2
fi
if [[ "$experimental" == 1 ]]; then
    [[ "$target" == ipodnano3g && ( "$kind" == firmware || "$kind" == bootloader ) ]] || {
        echo "Experimental NAND writes are only for Nano firmware/bootloader builds" >&2; exit 2;
    }
    # Never reuse safe/diagnostic objects for the write-enabled experiment.
    build+="-experimental-writes"
fi
mkdir -p "$build"
cd "$build"
configure_args=(--target="$target" --type="$type" --rbdir=/.podthingsloader)
if [[ "$kind" == simulator ]]; then
    # Use SDL's host threads instead of signal-stack context switching.
    configure_args+=(--sdl-threads)
fi
"$root/rockbox-firmware/tools/configure" "${configure_args[@]}"
version="${PODTHINGS_VERSION:-$(cat "$root/VERSION")}"
make_args=(-j"${JOBS:-4}" VERSION="$version")
if [[ "${PODTHINGS_STACK_USAGE:-0}" == 1 ]]; then
    gccopts="$(sed -n 's/^export GCCOPTS=//p' Makefile)"
    make_args+=("GCCOPTS=$gccopts -fstack-usage")
fi
if [[ "$kind" == nandcheck ]]; then
    extra_defines="$(sed -n 's/^export EXTRA_DEFINES=//p' Makefile)"
    grep -q '^export TARGET=-DIPOD_NANO3G$' Makefile || { echo "Missing Nano target defines" >&2; exit 1; }
    make_args+=("EXTRA_DEFINES=$extra_defines -DNAND_CHECK")
elif [[ "$experimental" == 1 ]]; then
    extra_defines="$(sed -n 's/^export EXTRA_DEFINES=//p' Makefile)"
    grep -q '^export TARGET=-DIPOD_NANO3G$' Makefile || { echo "Missing Nano target defines" >&2; exit 1; }
    make_args+=("EXTRA_DEFINES=$extra_defines -DPODTHINGS_NANO_UNVALIDATED_WRITES")
fi
# The host compiler supplied here lacks gcc-ar/gcc-ranlib. These native
# builds are non-LTO, so the native archiver and ranlib are sufficient.
if [[ "$kind" == checkwps || "$kind" == simulator ]]; then
    make_args+=(AR=ar RANLIB=ranlib)
fi
make "${make_args[@]}"
if [[ "$kind" == firmware ]]; then
    rm -f "$build/rockbox.zip"
    make zip "${make_args[@]}"
    python3 "$root/scripts/brand-podthings-package.py" \
        "$build/rockbox.zip" "$build/podthingsos-firmware.zip"
elif [[ "$kind" == checkwps ]]; then
    stage="$build/skin-check/.podthingsloader"
    mkdir -p "$stage"/{wps,themes,fonts,icons,backdrops}
    case "$target" in
        ipodvideo) model_define=IPOD_VIDEO ;;
        ipodcolor) model_define=IPOD_COLOR ;;
        ipod6g) model_define=IPOD_6G ;;
        ipodnano3g) model_define=IPOD_NANO3G ;;
    esac
    "$root/rockbox-firmware/wps/wpsbuild.pl" \
        --root="$root/rockbox-firmware" --modelname="$target" \
        --tempdir="$stage" --rbdir=.podthingsloader \
        "$root/rockbox-firmware/wps/WPSLIST" "-D$model_define"
    read -ra variants <<< "$(python3 -c "import runpy; print(' '.join(runpy.run_path('$root/scripts/generate-podthings-logo.py')['THEMES']))")"
    for variant in "${variants[@]}"; do
        for extension in wps sbs; do
            "./checkwps.$target" "$stage/wps/podthingsos-$variant.$extension"
        done
    done
elif [[ "$kind" == simulator ]]; then
    make install "${make_args[@]}"
    printf 'Simulator ready: %s/rockboxui\n' "$build"
fi
