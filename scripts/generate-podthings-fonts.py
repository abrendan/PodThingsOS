#!/usr/bin/env python3
"""Build licensed proportional Sans + full BMP Unifont fallback BDFs.

Large generated BDFs live outside Git. Source-tree symlinks let Rockbox's
unmodified native font builder consume them. No Python packages are needed.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "generated-artifacts/fonts"
FONTS = ((22, 18, 17, 5), (16, 12, 13, 3))


def glyphs(text):
    result = {}
    for block in re.findall(r"STARTCHAR [^\n]+\n.*?ENDCHAR", text, re.S):
        code = int(re.search(r"^ENCODING (-?\d+)", block, re.M)[1])
        if 32 <= code <= 0xfffd and not 0xd800 <= code <= 0xdfff:
            result[code] = block
    return result


def make_fonts():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    inputs = [
        Path(__file__), ROOT / "scripts/podthings-font-raster.c",
        ROOT / "assets/fonts/DejaVuSans.ttf",
        ROOT / "rockbox-firmware/fonts/16-GNU-Unifont.bdf",
    ]
    signature = hashlib.sha256(b"".join(p.read_bytes() for p in inputs)).hexdigest()
    with (OUTPUT / "build.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        outputs = [OUTPUT / f"{height}-PodThings-Sans.bdf"
                   for height, *_ in FONTS]
        cache = OUTPUT / "source.sha256"
        if not (cache.exists() and cache.read_text() == signature
                and all(p.exists() for p in outputs)):
            flags = shlex.split(subprocess.check_output(
                ["pkg-config", "--cflags", "--libs", "freetype2"], text=True))
            tool = OUTPUT / "font-raster"
            subprocess.run(["cc", "-O2", "-Wall", "-Wextra", "-Werror",
                            str(inputs[1]), *flags, "-o", str(tool)], check=True)
            fallback = glyphs(inputs[3].read_text())
            report = {}
            for height, pixels, ascent, descent in FONTS:
                merged = {}
                # Keep the original 16px CJK strokes sharp, not resampled.
                # Detail font moves the Unifont baseline up by one pixel.
                shift = min(0, ascent - 14)
                for code, block in fallback.items():
                    # FontForge's METRICSSET 2 file inherits a global 16px
                    # advance. Rockbox's converter requires it per glyph.
                    if not re.search(r"^DWIDTH ", block, re.M):
                        block = block.replace("\nBBX ", "\nDWIDTH 16 0\nBBX ", 1)
                    if int(re.search(r"^DWIDTH (-?\d+)", block, re.M)[1]) <= 0:
                        # Rockbox handles combining placement itself. A zero
                        # BDF advance invokes convbdf's global-box fallback
                        # instead of producing a valid zero-width glyph.
                        width = int(re.search(r"^BBX (\d+)", block, re.M)[1])
                        block = re.sub(r"^DWIDTH -?\d+ 0$", f"DWIDTH {max(1, width)} 0",
                                       block, flags=re.M)
                        block = re.sub(r"^(BBX \d+ \d+) -?\d+ ", r"\1 0 ",
                                       block, flags=re.M)
                    def move(match):
                        w, h, x, y = map(int, match.groups())
                        return f"BBX {w} {h} {x} {y + shift}"
                    merged[code] = re.sub(
                        r"^BBX (\d+) (\d+) (-?\d+) (-?\d+)$",
                        move, block, flags=re.M)
                raster = subprocess.check_output(
                    [str(tool), str(inputs[2]), str(pixels)], text=True)
                replaced = 0
                for line in raster.splitlines():
                    values = line.split()
                    code, w, h, left, top, advance = map(int, values[:6])
                    bitmap = values[6]
                    # Never clip a tall glyph. Keep its full Unifont fallback.
                    if top > ascent or top - h < -descent or w > 32:
                        continue
                    if not (32 <= code <= 0xfffd) or 0xd800 <= code <= 0xdfff:
                        continue
                    if advance <= 0:
                        advance = max(1, w)
                        left = 0
                    rowchars = ((w + 7) // 8) * 2
                    rows = ("\n".join(bitmap[n:n + rowchars]
                                     for n in range(0, len(bitmap), rowchars))
                            if bitmap != "-" and rowchars else "")
                    merged[code] = (
                        f"STARTCHAR uni{code:04X}\nENCODING {code}\n"
                        f"SWIDTH {advance * 1000 // pixels} 0\n"
                        f"DWIDTH {advance} 0\nBBX {w} {h} {left} {top - h}\n"
                        f"BITMAP\n{rows}\nENDCHAR")
                    replaced += 1
                name = f"{height}-PodThings-Sans"
                header = (
                    f"STARTFONT 2.1\nFONT {name}\nSIZE {height} 72 72\n"
                    f"FONTBOUNDINGBOX 32 {height} 0 -{descent}\n"
                    'COMMENT DejaVu Sans with GNU Unifont fallback; see font licenses.\n'
                    "STARTPROPERTIES 6\n"
                    f"FONT_ASCENT {ascent}\nFONT_DESCENT {descent}\n"
                    'CHARSET_REGISTRY "ISO10646"\nCHARSET_ENCODING "1"\n'
                    f'FAMILY_NAME "PodThings Sans"\nDEFAULT_CHAR 65533\n'
                    f"ENDPROPERTIES\nCHARS {len(merged)}\n")
                (OUTPUT / f"{name}.bdf").write_text(
                    header + "\n".join(merged[c] for c in sorted(merged)) +
                    "\nENDFONT\n")
                report[name] = dict(glyphs=len(merged), dejavu_glyphs=replaced,
                                    ascent=ascent, descent=descent)
            (OUTPUT / "coverage.json").write_text(json.dumps(report, indent=2))
            cache.write_text(signature)
            print("Generated PodThings Sans Unicode fonts.", flush=True)
        for output in outputs:
            link = ROOT / "rockbox-firmware/fonts" / output.name
            if link.is_symlink():
                if link.resolve() != output:
                    raise RuntimeError(f"Unexpected font symlink: {link}")
            elif link.exists():
                raise RuntimeError(f"Refusing to overwrite font source: {link}")
            else:
                link.symlink_to(os.path.relpath(output, link.parent))


if __name__ == "__main__":
    make_fonts()
