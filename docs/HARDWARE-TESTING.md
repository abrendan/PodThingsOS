# Hardware validation

Host tests and successful ARM builds are not device validation. Do not claim
one model, NAND variant or storage modification works because another does.

## Evidence supplied by the tester

| Target | Physical evidence |
| --- | --- |
| Classic 6G | User-reported use/testing |
| Video 5G | No separate physical confirmation supplied |
| Nano 3G, 4 GB | Installed bootloader/firmware and music playback confirmed after the audio-stack fix |

The tested Nano has Micron `3E94D52C`, two banks and 4096-byte NAND pages.
Its RAM diagnostic mounted the FTL successfully read-only before installation.
No general validation of all 18 recognized NAND combinations, interruption
recovery or write endurance follows from this result.

## Before testing an update

- Back up accessible files, know your exact model, and keep an Apple recovery
  route available. Recovery/restoration may erase everything.
- Use the complete matching firmware package, including codecs and plugins.
- Do not format a disk merely because Windows prompts you to initialize it.
- A firmware update cannot replace bootloader code in NOR boot flash.
- Do not repeatedly flash a bootloader to try to fix a playback panic.

## Useful checks

1. Startup, credits/version, normal shutdown and restart.
2. Menu-as-Back controls, Music navigation, Cover Flow and return paths.
3. Playback, rapid skipping, embedded/iTunes/missing artwork and playlists.
4. Scrub-mode entry/timeout, volume feedback, clocks and battery display.
5. All three palettes, long text, CJK glyphs, and the Now Playing **iPod**
   fallback when branding is disabled.
6. USB transfers and persistence of ordinary settings after safe eject/reboot.
7. Video/Classic one-time Apple reboot, followed by normal PodThings OS boot.
   The Nano Settings handoff is not implemented.

Report exact firmware version, target, reproduction steps and a panic photo.
Share diagnostic metadata selectively; do not post full NAND dumps, device
serial numbers or personal libraries.

See [installation and recovery notes](INSTALLATION.md).
