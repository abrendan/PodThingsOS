# Theme validation

The Current, Blue, Purple, Mint, Rose, Amber and Graphite skins share one
layout on Video 5G, Classic 6G and Nano 3G. Liquid Glass adds shaded blue-grey
panels and subtle light-catching rims over a public-domain Yosemite landscape,
using pre-rendered bitmaps, not live blur or dynamic transparency.
Current is the default in 0.9.0; `podthingsos-default` is now its alias.
`podthingsos-purple` remains available. Pearl, Sky and Lavender add bright backgrounds with dark
text. All twelve presets share the same playback and menu geometry.
Install matching firmware before using
the skins: their custom metadata, branding and scrub-mode tags are not part
of unmodified Rockbox. Ordinary legacy Rockbox themes remain loadable.

## Installing the expanded theme collection

For existing PodThings OS 0.8.3 or newer installations, merge the theme pack's
`.podthingsloader` folder into the same folder on the iPod and safely eject.
No firmware or bootloader image is included or needs flashing. Open
Settings > Appearance > Change Theme for the friendly theme list. For file
browsing and legacy Rockbox themes, use Advanced Theme Settings > Browse Theme Files and choose
`podthingsos-mint`, `podthingsos-rose`, `podthingsos-amber`,
`podthingsos-graphite`, `podthingsos-pearl`, `podthingsos-sky`,
`podthingsos-lavender`, `podthingsos-default` or `podthingsos-liquid-glass`. The original three
themes are still available. Installing the pack does not overwrite `config.cfg`
or switch the active theme; choose a theme explicitly to apply it.

The temporary volume overlay is a rounded card with a live volume line and
dB readout. It replaces the progress/time area for two seconds after adjusting
volume, then restores it. Scrubbing takes precedence over the overlay.
Selected menu text uses a flat foreground-painted fill; setting only a viewport
background does not protect a selection bitmap from an active wallpaper.

The glass style uses darkened, pre-blurred landscape panels for readable
text and a solid status strip. The photograph is Ted Wakabayashi's
public-domain "Tunnel view, Yosemite.jpg", not Apple's wallpaper.
Its source, public-domain dedication and modifications are documented in
`assets/wallpapers/Yosemite-LICENSE.txt` and the theme pack's license folder.
It preserves the existing menu padding,
multilingual fonts, centered playback clock, battery group, temporary volume
readout, scrub dot and branding controls. This is a Liquid Glass-inspired
design for a 320x240 display, not Apple's compositor or an official Apple theme.

## Native parser checks

```sh
bash scripts/rockbox-build.sh ipodvideo checkwps
bash scripts/rockbox-build.sh ipod6g checkwps
bash scripts/rockbox-build.sh ipodnano3g checkwps
bash scripts/rockbox-theme-package.sh
```

The wrapper rebuilds the checker and stages actual installed skin names and
bitmap paths. Validate both `.wps` and `.sbs`; checking only resolution-suffixed
source filenames can miss images or falsely reject valid paths.

## Physical checklist

- Text stays inside rounded menu highlights; padding and scrollbars behave.
- Clock alignment, battery percentage/icon and charging marker are correct.
- No persistent Playing/Stopped label or seeking-instruction text.
- Artwork corners, placeholder, file quality and long-title scrolling work.
- Metadata does not flash temporary loading filenames as real song titles.
- Scrub mode displays the seek dot; volume feedback is temporary.
- With Now Playing branding enabled, show the small PodThings OS logo/text.
- With it disabled, show **iPod** without the logo. Menu branding remains an
  independent setting. Third-party themes keep their own layout.
- Check readable multilingual glyphs and missing-glyph behavior separately
  from native parser success.

Parser/host success does not establish appearance or playback on real hardware.
Themes and fonts retain their original license notices.
