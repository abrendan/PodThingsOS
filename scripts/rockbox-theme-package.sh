#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Create a theme-only archive. Never replaces firmware or flashes a device.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="${PODTHINGS_VERSION:-$(cat "$root/VERSION")}"
python3 "$root/scripts/generate-podthings-logo.py"
read -ra variants <<< "$(python3 -c "import runpy; print(' '.join(runpy.run_path('$root/scripts/generate-podthings-logo.py')['THEMES']))")"
for target in ipodvideo ipod6g ipodnano3g; do
    parser="$root/generated-artifacts/rockbox/$target-checkwps/checkwps.$target"
    # Incremental rebuild is essential when the fork adds a skin tag. Merely
    # finding an old executable can reject valid new skins or validate the
    # wrong grammar. The build wrapper supplies the host-tool adaptations.
    bash "$root/scripts/rockbox-build.sh" "$target" checkwps
done

stage="$root/generated-artifacts/podthings-theme-package"
archive="$root/generated-artifacts/podthingsos-themes-$version.zip"
mkdir -p "$stage/.podthingsloader"/{wps,themes,fonts,icons,backdrops}
(
    cd "$root/generated-artifacts/rockbox/ipodvideo-checkwps"
    "$root/rockbox-firmware/wps/wpsbuild.pl" \
        --root="$root/rockbox-firmware" --modelname=ipodvideo \
        --tempdir="$stage/.podthingsloader" --rbdir=.podthingsloader \
        "$root/rockbox-firmware/wps/WPSLIST" -DIPOD_VIDEO
)
# Check the installed filenames: source filenames have resolution suffixes,
# which otherwise make the native parser look in the wrong bitmap directory.
for target in ipodvideo ipod6g ipodnano3g; do
    parser="$root/generated-artifacts/rockbox/$target-checkwps/checkwps.$target"
    for variant in "${variants[@]}"; do
        "$parser" "$stage/.podthingsloader/wps/podthingsos-$variant."{wps,sbs}
    done
done
for variant in "${variants[@]}"; do
    cmp "$root/rockbox-firmware/wps/podthingsos-$variant.320x240x16.wps" \
        "$stage/.podthingsloader/wps/podthingsos-$variant.wps"
    test -s "$stage/.podthingsloader/themes/podthingsos-$variant.cfg"
    cmp "$root/rockbox-firmware/wps/podthingsos-$variant.320x240x16.sbs" \
        "$stage/.podthingsloader/wps/podthingsos-$variant.sbs"
    for image in "$root/rockbox-firmware/wps/podthingsos-$variant/"*.bmp; do
        [[ "${image##*/}" == photo-* ]] && continue # Native Photo assets are not installed here.
        cmp "$image" "$stage/.podthingsloader/wps/podthingsos-$variant/$(basename "$image")"
    done
done
test -s "$stage/.podthingsloader/fonts/22-PodThings-Sans.fnt"
test -s "$stage/.podthingsloader/fonts/16-PodThings-Sans.fnt"

licenses="$stage/.podthingsloader/themes/podthings-licenses"
mkdir -p "$licenses"
cp "$root/rockbox-firmware/docs/COPYING" "$licenses/GPL-2.0.txt"
cp "$root/rockbox-firmware/fonts/COPYING" "$licenses/fonts-COPYING.txt"
cp "$root/assets/fonts/DejaVu-COPYING.txt" "$licenses/"
cp "$root/assets/fonts/Unifont-LICENSE.txt" "$licenses/"
cp "$root/assets/wallpapers/Yosemite-LICENSE.txt" "$licenses/"
python3 "$root/scripts/installer_config.py" themes "$version" "$stage/installer.config"

rm -f "$archive"
members=()
for variant in "${variants[@]}"; do
    members+=(".podthingsloader/themes/podthingsos-$variant.cfg"
              ".podthingsloader/wps/podthingsos-$variant.wps"
              ".podthingsloader/wps/podthingsos-$variant.sbs")
    for image in "$stage/.podthingsloader/wps/podthingsos-$variant/"*.bmp; do
        [[ "${image##*/}" == photo-* ]] && continue # 220x176 assets belong in the Photo kit.
        members+=("${image#"$stage/"}")
    done
done
(
    cd "$stage"
    zip -q "$archive" \
        installer.config \
        "${members[@]}" \
        .podthingsloader/fonts/22-PodThings-Sans.fnt \
        .podthingsloader/fonts/16-PodThings-Sans.fnt \
        .podthingsloader/themes/podthings-licenses/*
)
printf 'Theme-only pack: %s\n' "$archive"
