#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Generate the font fixtures needed by the host tests; no ARM toolchain needed.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$root/scripts/generate-podthings-fonts.py"
make -C "$root/rockbox-firmware/tools" convbdf CC=cc
stage="$root/generated-artifacts/podthings-theme-package/.podthingsloader/fonts"
mkdir -p "$stage"
for height in 16 22; do
    "$root/rockbox-firmware/tools/convbdf" -f \
        -o "$stage/$height-PodThings-Sans.fnt" \
        "$root/rockbox-firmware/fonts/$height-PodThings-Sans.bdf"
done
