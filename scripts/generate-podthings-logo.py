#!/usr/bin/env python3
"""Generate the native splash asset from bundled, licensed BDF fonts."""
import struct
import subprocess
import hashlib
import json
import fcntl
from functools import lru_cache
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "rockbox-firmware"
WIDTH, HEIGHT = 320, 98
BACKGROUND = (14, 11, 22)
THEMES = {
    "current": dict(bg="0E0B16", fg="FAF8FF", accent="7C3AED", soft="A78BFA",
                    secondary="C4B4E8", muted="9D8EB7", card="20182F", inset="2D2140"),
    "blue": dict(bg="0B1424", fg="F1F7FF", accent="2563EB", soft="93C5FD",
                 secondary="C7D9F2", muted="8FAACB", card="132A45", inset="1D3858"),
    "purple": dict(bg="160B29", fg="FAF8FF", accent="7C3AED", soft="A78BFA",
                   secondary="D1BDF2", muted="A98FCE", card="2C1848", inset="3A2259"),
    "mint": dict(bg="091C19", fg="F1FFF9", accent="176650", soft="79E2BC",
                 secondary="C0E8D9", muted="91BAAF", card="15342C", inset="22483D"),
    "rose": dict(bg="24101C", fg="FFF5FA", accent="963F6B", soft="F3A5CC",
                 secondary="EDC6DA", muted="C19BAD", card="3E2032", inset="553047"),
    "amber": dict(bg="21170B", fg="FFF9EE", accent="805516", soft="F4C57A",
                  secondary="EAD6B5", muted="C4AB86", card="392A16", inset="4D3920"),
    "graphite": dict(bg="12161C", fg="F5F7FB", accent="45556B", soft="BDCCDF",
                     secondary="D3DCE8", muted="A5B2C3", card="252D38", inset="354151"),
    "liquid-glass": dict(bg="0D1929", fg="F3FAFF", accent="345C79", soft="A6E4EF",
                         secondary="D3E8F5", muted="A2C0D8", card="22394E", inset="304A61"),
    "pearl": dict(bg="F4F5F8", fg="182235", accent="D9DDE8", soft="445575",
                  secondary="33435C", muted="536078", card="FFFFFF", inset="E3E7EF"),
    "sky": dict(bg="EAF5FC", fg="132840", accent="C6E3F7", soft="24577C",
                secondary="244560", muted="48657B", card="F8FCFF", inset="D5E7F3"),
    "lavender": dict(bg="F4EEFC", fg="2B2043", accent="E0D5F5", soft="65448A",
                     secondary="49365F", muted="69557E", card="FDFBFF", inset="E8DFF3"),
}
# Keep all named presets compatible; Default follows Current from 0.9.0.
THEMES["default"] = THEMES["current"].copy()


def rgb(value):
    return tuple(bytes.fromhex(value))


def write_text_if_changed(path, text):
    if not path.exists() or path.read_text() != text:
        path.write_text(text)


def generate_themes():
    """Shared accessible layout with color palettes and a shaded glass style."""
    template = (ROOT / "wps/podthings.320x240x16.wps").read_text()
    status_template = (ROOT / "wps/podthings.320x240x16.sbs").read_text()
    blocks = []
    for variant, palette in THEMES.items():
        name = f"podthingsos-{variant}"
        skin = template.replace("purple card playback", f"{variant} card playback")
        # Substitute in one pass so shared colors cannot cascade into each other.
        import re
        colors = {THEMES["current"][key]: palette[key]
                  for key in ("bg", "fg", "accent", "soft", "secondary", "muted",
                              "card", "inset")}
        skin = re.sub("|".join(colors), lambda match: colors[match[0]], skin)
        write_text_if_changed(ROOT / f"wps/{name}.320x240x16.wps", skin)
        status = status_template.replace("purple menus", f"{variant} menus")
        status = re.sub("|".join(colors), lambda match: colors[match[0]], status)
        if variant == "liquid-glass":
            # All landscape tinting and panel blur is baked into the bitmap.
            status = status.replace("%Fl(2,", "%X(menu-backdrop.bmp)\n%Fl(2,", 1)
            status = status.replace("liquid-glass menus",
                                    "Liquid Glass inspired menus")
        write_text_if_changed(ROOT / f"wps/{name}.320x240x16.sbs", status)
        backdrop, mask, battery = playback_assets(palette)
        save(backdrop, ROOT / f"wps/{name}/backdrop.bmp")
        save(mask, ROOT / f"wps/{name}/art-mask.bmp")
        save(battery, ROOT / f"wps/{name}/battery.bmp")
        # Separate overlay material, track and fill: native progress rendering
        # restores the track first, then crops the live fill to actual volume.
        overlay = [[(255, 0, 255)] * 296 for _ in range(40)]
        rounded(overlay, 0, 0, 296, 40, 10, rgb(palette["card"]))
        track = [[rgb(palette["card"])] * 264 for _ in range(6)]
        fill = [[rgb(palette["card"])] * 264 for _ in range(6)]
        rounded(track, 0, 0, 264, 6, 3, rgb(palette["inset"]))
        rounded(fill, 0, 0, 264, 6, 3, rgb(palette["soft"]))
        for asset, pixels in (("volume-panel", overlay), ("volume-track", track),
                              ("volume-fill", fill)):
            save(pixels, ROOT / f"wps/{name}/{asset}.bmp")
            if variant == "current":
                save(pixels, ROOT / f"wps/podthings/{asset}.bmp")
        branding=[[rgb(palette["bg"])]*16 for _ in range(16)]
        svg(branding,"podthings.svg",0,0,16,16)
        save(branding,ROOT / f"wps/{name}/branding.bmp")
        dot=[[(255,0,255)]*9 for _ in range(9)]
        for y in range(9):
            for x in range(9):
                if (x-4)**2+(y-4)**2<=16: dot[y][x]=rgb(palette["fg"])
        save(dot,ROOT / f"wps/{name}/seek-dot.bmp")
        selection = [[rgb(palette["bg"])] * 296 for _ in range(26)]
        rounded(selection, 0, 0, 296, 26, 10, rgb(palette["accent"]))
        if variant == "liquid-glass":
            selection = [[(255, 0, 255)] * 296 for _ in range(26)]
            rounded(selection, 0, 0, 296, 26, 10, rgb(palette["accent"]))
            glass_edge(selection, 0, 0, 296, 26, 10, palette["soft"])
            menu = landscape_background(palette)
            frosted_panel(menu, palette, 8, 46, 304, 190, 16)
            glass_edge(menu, 8, 46, 304, 190, 16, palette["soft"])
            save(menu, ROOT / f"wps/{name}/menu-backdrop.bmp")
        save(selection, ROOT / f"wps/{name}/selection.bmp")
        if variant == "current":
            save(backdrop, ROOT / "wps/podthings/backdrop.bmp")
            save(branding, ROOT / "wps/podthings/branding.bmp")
            save(dot, ROOT / "wps/podthings/seek-dot.bmp")
        blocks.append(f"""<theme>
Name: {name}
Authors: PodThings OS contributors
WPS: yes
SBS: yes
<main>
wps.320x240x(16|24|32): {name}.320x240x16.wps
sbs.320x240x(16|24|32): {name}.320x240x16.sbs
Font.320x240x(16|24|32): 22-PodThings-Sans.fnt
wps.220x176x16: {name}.220x176x16.wps
sbs.220x176x16: {name}.220x176x16.sbs
Font.220x176x16: 16-PodThings-Sans.fnt
statusbar: top
foreground color: {palette["fg"]}
background color: {palette["bg"]}
line selector start color: {palette["accent"]}
line selector end color: {palette["accent"]}
line selector text color: {palette["fg"]}
selector type: bar (color)
list padding: 8
list separator height: off
list separator color: {palette["inset"]}
backdrop: -
ui viewport: -
</main>
</theme>""")
    listing = ROOT / "wps/WPSLIST"
    begin, end = "# PODTHINGS_OS_THEMES_BEGIN", "# PODTHINGS_OS_THEMES_END"
    text = listing.read_text()
    first, last = text.index(begin) + len(begin), text.index(end)
    write_text_if_changed(listing, text[:first] + "\n" + "\n\n".join(blocks) +
                          "\n" + text[last:])


def playback_assets(palette):
    backdrop = [[rgb(palette["bg"])] * 320 for _ in range(240)]
    rounded(backdrop, 12, 42, 296, 148, 14, rgb(palette["card"]))
    rounded(backdrop, 22, 56, 116, 116, 12, rgb(palette["inset"]))
    rounded(backdrop, 12, 201, 296, 9, 4, rgb(palette["inset"]))
    if palette is THEMES["liquid-glass"]:
        backdrop = landscape_background(palette)
        frosted_panel(backdrop, palette, 12, 42, 296, 148, 14)
        glass_edge(backdrop, 12, 42, 296, 148, 14, palette["soft"])
        rounded(backdrop, 22, 56, 116, 116, 12, rgb(palette["inset"]))
        glass_edge(backdrop, 22, 56, 116, 116, 12, palette["soft"])
        rounded(backdrop, 12, 201, 296, 9, 4, rgb(palette["inset"]))
        glass_edge(backdrop, 12, 201, 296, 9, 4, palette["soft"])
    # Native skin rendering draws these images AFTER album art. Magenta is
    # Rockbox's transparent bitmap key; opaque corners restore the backdrop.
    mask = [[(255, 0, 255) if in_roundrect(x, y, 112, 112, 10)
             else backdrop[58 + y][24 + x] for x in range(112)]
            for y in range(112)]
    # Skin images are drawn AFTER bars. Keep the whole interior transparent
    # so this frame cannot repaint over the live battery-level bar.
    transparent = (255, 0, 255)
    battery = [[transparent] * 22 for _ in range(12)]
    rounded(battery, 0, 1, 20, 10, 2, rgb(palette["soft"]))
    rounded(battery, 1, 2, 18, 8, 1, transparent)
    for y in range(4, 8):
        for x in range(20, 22):
            battery[y][x] = rgb(palette["soft"])
    return backdrop, mask, battery


def blend(first, second, amount):
    return tuple(round(a + (b - a) * amount) for a, b in zip(first, second))


@lru_cache(maxsize=2)
def landscape_pixels(blur=False):
    """Offline, public-domain source; return immutable 320x240 RGB pixels."""
    image = ROOT.parent / "assets/wallpapers/yosemite.png"
    command = ["ffmpeg", "-loglevel", "error", "-i", str(image)]
    if blur:
        command += ["-vf", "gblur=sigma=3"]
    raw = subprocess.check_output(command + ["-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])
    if len(raw) != 320 * 240 * 3:
        raise ValueError("Landscape wallpaper must be exactly 320x240")
    return tuple(tuple(tuple(raw[(y * 320 + x) * 3:(y * 320 + x) * 3 + 3])
                       for x in range(320)) for y in range(240))


def landscape_background(palette):
    photo = landscape_pixels()
    bg = rgb(palette["bg"])
    # A solid status strip preserves logo anti-aliasing and battery readability.
    return [[bg if y < 24 else blend(photo[y][x], bg, .68 if y < 50 or y >= 212 else .42)
             for x in range(320)] for y in range(240)]


def frosted_panel(pixels, palette, x, y, width, height, radius):
    blurred = landscape_pixels(blur=True)
    for row in range(height):
        for column in range(width):
            if in_roundrect(column, row, width, height, radius):
                # Preserve the landscape through the sheet but cap highlights
                # for small white text. No runtime blur or alpha compositing.
                pixels[y + row][x + column] = blend(
                    blurred[y + row][x + column], rgb(palette["bg"]), .68)


def glass_edge(pixels, x, y, width, height, radius, tint):
    """One-pixel refracted rim; never obscure the usable text/bar interior."""
    for row in range(height):
        for column in range(width):
            outer = in_roundrect(column, row, width, height, radius)
            inner = (0 < column < width - 1 and 0 < row < height - 1 and
                     in_roundrect(column - 1, row - 1, width - 2, height - 2,
                                  max(0, radius - 1)))
            if outer and not inner:
                amount = .6 if row < height / 2 else .22
                old = pixels[y + row][x + column]
                pixels[y + row][x + column] = blend(old, rgb(tint), amount)


def load_font(name):
    glyphs = {}
    glyph = None
    bitmap = False
    for line in (ROOT / "fonts" / name).read_text().splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "STARTCHAR":
            glyph = {"rows": []}
        elif glyph is not None:
            if parts[0] == "ENCODING":
                glyph["code"] = int(parts[1])
            elif parts[0] == "DWIDTH":
                glyph["advance"] = int(parts[1])
            elif parts[0] == "BBX":
                glyph["box"] = tuple(map(int, parts[1:]))
            elif parts[0] == "BITMAP":
                bitmap = True
            elif parts[0] == "ENDCHAR":
                glyphs[glyph["code"]] = glyph
                glyph = None
                bitmap = False
            elif bitmap:
                glyph["rows"].append(bytes.fromhex(parts[0]))
    return glyphs


def text_width(font, text):
    return sum(font[ord(char)]["advance"] for char in text)


def draw_text(pixels, font, text, x, baseline, color):
    for char in text:
        glyph = font[ord(char)]
        width, height, xoff, yoff = glyph["box"]
        for row, data in enumerate(glyph["rows"]):
            y = baseline - height - yoff + row
            for column in range(width):
                px = x + xoff + column
                if data[column // 8] & (128 >> (column % 8)):
                    if 0 <= px < len(pixels[0]) and 0 <= y < len(pixels):
                        pixels[y][px] = color
        x += glyph["advance"]
    return x


def canvas(width, height):
    return [[BACKGROUND] * width for _ in range(height)]


def svg(pixels, name, x, y, width, height):
    source = ROOT.parent / "assets/branding" / name
    # rsvg's separate width/height overrides otherwise stretch the tall iPod
    # into a square. Fit its viewBox into the existing asset/memory budget.
    viewbox = list(map(float, ET.fromstring(source.read_text()).attrib["viewBox"].split()))
    scale = min(width / viewbox[2], height / viewbox[3])
    draw_width, draw_height = viewbox[2] * scale, viewbox[3] * scale
    png = subprocess.check_output([
        "rsvg-convert", "-w", str(draw_width), "-h", str(draw_height),
        "--page-width", str(width), "--page-height", str(height),
        "--left", str((width - draw_width) / 2),
        "--top", str((height - draw_height) / 2), str(source)
    ])
    rgba = subprocess.run([
        "ffmpeg", "-loglevel", "error", "-i", "pipe:0",
        "-f", "rawvideo", "-pix_fmt", "rgba", "pipe:1",
    ], input=png, stdout=subprocess.PIPE, check=True).stdout
    if len(rgba) != width * height * 4:
        raise ValueError("Unexpected rasterized SVG dimensions")
    for row in range(height):
        for column in range(width):
            offset = (row * width + column) * 4
            red, green, blue, alpha = rgba[offset:offset + 4]
            background = pixels[y + row][x + column]
            pixels[y + row][x + column] = tuple(
                (channel * alpha + bg * (255 - alpha) + 127) // 255
                for channel, bg in zip((red, green, blue), background)
            )


def in_roundrect(column, row, width, height, radius):
    dx = max(radius - column, column - (width - radius - 1), 0)
    dy = max(radius - row, row - (height - radius - 1), 0)
    return dx * dx + dy * dy <= radius * radius


def rounded(pixels, x, y, width, height, radius, color):
    for row in range(height):
        for column in range(width):
            if in_roundrect(column, row, width, height, radius):
                pixels[y + row][x + column] = color


def save(pixels, output):
    width, height = len(pixels[0]), len(pixels)
    row_size = (width * 3 + 3) & ~3
    body = bytearray()
    for row in reversed(pixels):
        for red, green, blue in row:
            body.extend((blue, green, red))
        body.extend(bytes(row_size - width * 3))
    header = struct.pack("<2sIHHI", b"BM", 54 + len(body), 0, 0, 54)
    header += struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24,
                          0, len(body), 2835, 2835, 0, 0)
    output.parent.mkdir(parents=True, exist_ok=True)
    image = header + body
    if not output.exists() or output.read_bytes() != image:
        output.write_bytes(image)


def main():
    native = ROOT / "apps/bitmaps/native"
    medium = load_font("27-Adobe-Helvetica-Bold.bdf")
    small = load_font("12-Adobe-Helvetica.bdf")
    compact = load_font("15-Adobe-Helvetica.bdf")
    splash = canvas(320, 128)
    svg(splash, "podthings.svg", 124, 2, 72, 72)
    title = "PodThings OS"
    draw_text(splash, medium, title,
              (320 - text_width(medium, title)) // 2, 100, (250, 248, 255))
    credit = "Built by abrendan"
    draw_text(splash, small, credit,
              (320 - text_width(small, credit)) // 2, 122, (167, 139, 250))
    save(splash, native / "rockboxlogo.320x128x16.podthings.bmp")

    boot = canvas(160, 64)
    svg(boot, "podthings.svg", 0, 0, 64, 64)
    draw_text(boot, compact, "PodThings", 65, 29, (250, 248, 255))
    draw_text(boot, compact, "OS", 65, 48, (167, 139, 250))
    save(boot, native / "rockboxlogo.160x64x16.podthings.bmp")
    nano_boot=canvas(80,32)
    svg(nano_boot,"podthings.svg",24,0,32,32)
    save(nano_boot,native / "rockboxlogo.80x32x16.podthings.bmp")

    credits = canvas(96, 100)
    svg(credits, "abrendan.svg", 0, 0, 96, 100)
    save(credits, native / "podthings_credits.96x100x16.bmp")

    generate_themes()
    import runpy
    runpy.run_path(str(ROOT.parent / "scripts/generate-podthings-photo.py"))["generate"](globals())


def build_assets():
    # Four device builds share these outputs. Render once, with a lock, and
    # invalidate the cache when any source or generated asset changes.
    cache = ROOT.parent / "generated-artifacts/podthings-assets-cache.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    paths = [
        Path(__file__), ROOT / "wps/WPSLIST",
        ROOT.parent / "scripts/generate-podthings-photo.py",
        ROOT / "wps/podthings.220x176x16.wps",
        ROOT / "wps/podthings.220x176x16.sbs",
        ROOT / "wps/podthings.320x240x16.wps",
        ROOT / "wps/podthings.320x240x16.sbs",
        ROOT.parent / "assets/branding/podthings.svg",
        ROOT.parent / "assets/branding/abrendan.svg",
        ROOT.parent / "assets/wallpapers/yosemite.png",
        *(ROOT / "fonts" / name for name in (
            "27-Adobe-Helvetica-Bold.bdf", "12-Adobe-Helvetica.bdf",
            "15-Adobe-Helvetica.bdf")),
        *(ROOT / "apps/bitmaps/native" / name for name in (
            "rockboxlogo.320x128x16.podthings.bmp",
            "rockboxlogo.160x64x16.podthings.bmp",
            "rockboxlogo.80x32x16.podthings.bmp",
            "rockboxlogo.220x88x16.podthings.bmp",
            "podthings_credits.96x100x16.bmp")),
        ROOT / "wps/podthings/backdrop.bmp",
    ]
    for variant in THEMES:
        paths += [ROOT / f"wps/podthingsos-{variant}.320x240x16.{kind}"
                  for kind in ("wps", "sbs")]
        paths += [ROOT / f"wps/podthingsos-{variant}.220x176x16.{kind}"
                  for kind in ("wps", "sbs")]
        paths += [ROOT / f"wps/podthingsos-{variant}/photo-{name}.bmp"
                  for name in ("backdrop", "art-mask", "battery", "selection",
                               "branding", "seek-dot", "volume-panel",
                               "volume-track", "volume-fill")]
        paths += [ROOT / f"wps/podthingsos-{variant}/{name}.bmp"
                  for name in ("backdrop", "art-mask", "battery", "selection",
                               "branding", "seek-dot", "volume-panel",
                               "volume-track", "volume-fill")]
    paths.append(ROOT / "wps/podthingsos-liquid-glass/menu-backdrop.bmp")
    paths.append(ROOT / "wps/podthingsos-liquid-glass/photo-menu-backdrop.bmp")

    def state():
        return {str(path.relative_to(ROOT.parent)):
                hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
                for path in paths}

    with cache.with_suffix(".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            previous = json.loads(cache.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            previous = None
        if previous == state():
            print("Reusing verified PodThings OS bitmap and theme assets.", flush=True)
            return
        print("Generating PodThings OS bitmap and theme assets.", flush=True)
        main()
        cache.write_text(json.dumps(state(), sort_keys=True))


if __name__ == "__main__":
    subprocess.run(["python3", str(ROOT.parent / "scripts/generate-podthings-fonts.py")],
                   check=True)
    build_assets()
