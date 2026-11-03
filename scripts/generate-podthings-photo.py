#!/usr/bin/env python3
"""Native Photo assets. Reuse the same palettes, logo, materials and licenses."""
import re


def generate(api):
    root = api["ROOT"]
    rgb, rounded, save = (api[name] for name in ("rgb", "rounded", "save"))
    themes = api["THEMES"]
    originals = {kind: (root / f"wps/podthings.220x176x16.{kind}").read_text()
                 for kind in ("wps", "sbs")}
    for variant, palette in themes.items():
        name = f"podthingsos-{variant}"
        colors = {themes["current"][key]: palette[key]
                  for key in ("bg", "fg", "accent", "soft", "secondary",
                              "muted", "card", "inset")}
        for kind, template in originals.items():
            skin = re.sub("|".join(colors), lambda m: colors[m[0]], template)
            if variant == "liquid-glass" and kind == "sbs":
                skin = skin.replace("%Fl(2,", "%X(photo-menu-backdrop.bmp)\n%Fl(2,", 1)
            api["write_text_if_changed"](root / f"wps/{name}.220x176x16.{kind}", skin)

        bg = [[rgb(palette["bg"])] * 220 for _ in range(176)]
        if variant == "liquid-glass":
            source = api["landscape_background"](palette)
            bg = [[source[y * 240 // 176][x * 320 // 220]
                   for x in range(220)] for y in range(176)]
            menu = [row[:] for row in bg]
            api["frosted_panel"](menu, palette, 5, 39, 210, 135, 12)
            api["glass_edge"](menu, 5, 39, 210, 135, 12, palette["soft"])
            save(menu, root / f"wps/{name}/photo-menu-backdrop.bmp")
            api["frosted_panel"](bg, palette, 8, 30, 204, 109, 10)
            api["glass_edge"](bg, 8, 30, 204, 109, 10, palette["soft"])
        else:
            rounded(bg, 8, 30, 204, 109, 10, rgb(palette["card"]))
        rounded(bg, 13, 39, 84, 84, 9, rgb(palette["inset"]))
        rounded(bg, 8, 148, 204, 7, 3, rgb(palette["inset"]))
        magenta = (255, 0, 255)
        mask = [[magenta if api["in_roundrect"](x, y, 80, 80, 7)
                 else bg[41 + y][15 + x] for x in range(80)] for y in range(80)]
        pill = [[magenta if variant == "liquid-glass" else rgb(palette["bg"])] * 204
                for _ in range(20)]
        rounded(pill, 0, 0, 204, 20, 8, rgb(palette["accent"]))
        if variant == "liquid-glass":
            api["glass_edge"](pill, 0, 0, 204, 20, 8, palette["soft"])
        branding = [[rgb(palette["bg"])] * 12 for _ in range(12)]
        api["svg"](branding, "podthings.svg", 0, 0, 12, 12)
        overlay = [[magenta] * 204 for _ in range(28)]
        rounded(overlay, 0, 0, 204, 28, 8, rgb(palette["card"]))
        track = [[rgb(palette["card"])] * 184 for _ in range(5)]
        fill = [row[:] for row in track]
        rounded(track, 0, 0, 184, 5, 2, rgb(palette["inset"]))
        rounded(fill, 0, 0, 184, 5, 2, rgb(palette["soft"]))
        dot = [[rgb(palette["fg"]) if (x-3)**2 + (y-3)**2 <= 9 else magenta
                for x in range(7)] for y in range(7)]
        battery = api["playback_assets"](palette)[2]
        for asset, pixels in (
            ("backdrop", bg), ("art-mask", mask), ("selection", pill),
            ("branding", branding), ("volume-panel", overlay),
            ("volume-track", track), ("volume-fill", fill),
            ("seek-dot", dot), ("battery", battery),
        ):
            save(pixels, root / f"wps/{name}/photo-{asset}.bmp")

    # Preserve logo colors and proportions; render at native Photo dimensions.
    splash = api["canvas"](220, 88)
    api["svg"](splash, "podthings.svg", 84, 0, 52, 52)
    font = api["load_font"]("15-Adobe-Helvetica.bdf")
    small = api["load_font"]("12-Adobe-Helvetica.bdf")
    for text, baseline, face, color in (
        ("PodThings OS", 70, font, (250, 248, 255)),
        ("Built by abrendan", 86, small, (167, 139, 250)),
    ):
        api["draw_text"](splash, face, text,
                         (220 - api["text_width"](face, text)) // 2, baseline, color)
    save(splash, root / "apps/bitmaps/native/rockboxlogo.220x88x16.podthings.bmp")
