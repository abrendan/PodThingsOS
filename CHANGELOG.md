# Changelog

## 0.9.6

- Correct padded iTunes thumbnail bounds in the shared artwork reader.
- Isolate malformed image headers with valid record boundaries.
- Refresh derived artwork and Cover Flow caches automatically.
- Ship firmware-only updates with matching plugins; bootloaders are unchanged.

## 0.9.5 — iPod Photo / Color

- Add the native 32 MB Photo/Color target without changing upstream hardware
  drivers, LCD format, codec/plugin buffers or bootloader memory boundaries.
- Enable the shared PodThings OS menus, navigation, credits, iTunes playlists,
  artwork, Cover Flow, seek/volume overlays, branding controls and boot choices.
- Port all 12 themes to native 220×176 viewports, artwork masks, materials,
  selection pills and overlays. Use the 16px Unicode font for menus/metadata.
- Support the Photo's RGB565-LE iTunes cover formats 1017 (56px) and 1016 (140px).
- Reuse bounded elapsed-time Cover Flow animation for the older processor.
- Add the matching PortalPlayer bootloader with persistent defaults, one-time
  Apple/Rockbox selection, read-only Apple partition recovery and the PP5020
  Apple Disk Mode cookie. Require Photo bootloader 0.9.5 in installer metadata.
- New model: physical playback, Apple handoff and disk-mode operation are
  unconfirmed. Other models are not rebuilt as part of this Photo-only release.

## 0.9.4 — Restore native font rendering

- Completely remove Smooth Text (Beta), its saved setting, language entry,
  renderer hook and glyph filter. Restore the original mono/native-alpha paths
  on every model, retaining Unicode fonts and theme layouts.
- Advance the plugin ABI after removing the shared settings field. Install the
  complete matching firmware and plugins.
- Remove Reboot to Disk Mode from Classic/Nano Settings rather than substitute
  bootloader USB mode. Their updated loaders consume obsolete disk requests
  and return to PodThings OS without entering that substitute.
- Keep Video's Apple Disk Mode path. Minimum bootloader is 0.9.3 for Video and
  0.9.4 for Classic/Nano. Automatic Apple Disk Mode on those S5L8702 models
  remains unresolved.

## 0.9.3 — Artwork recovery and disk-mode reboot

- Fit the default-boot confirmation into the themed card with stock fonts.
- Add one-time Reboot to Disk Mode with safe shutdown, persisted request
  consumption, unchanged boot defaults and Hold recovery.
- Try duplicate artwork identities and isolate bounded invalid image records.
- Preserve usable Cover Flow slides on refresh failure, use checked atomic
  cache writes, and retry interrupted rebuilds instead of marking them complete.
- Remove per-album modal decode warnings and accidental Select-release
  cancellation during cache preparation.
- Make grayscale font edge treatment apply visibly to outside edges.
- Require matching 0.9.3 bootloaders for disk-mode request handling.

## 0.9.2 — Artwork, Video transitions and text rendering

- Retry legacy artwork identity when an iTunes shared link has no usable cover;
  invalidate source fingerprints after USB disconnection without blocking USB.
- Refresh the Cover Flow artwork cache for the corrected reader.
- Advance Video Cover Flow transitions by elapsed time rather than render frames;
  retain the existing Classic/Nano timing.
- Use themed rounded confirmation cards and show the reboot destination during
  safe shutdown, retaining request cancellation and storage flush behavior.
- Add Appearance > Smooth Text (Beta), off by default, with conservative
  grayscale smoothing of bitmap glyph edges. Keep existing Unicode glyphs,
  advances, native antialiased fonts and transparent combining marks intact.
- Bump the plugin ABI for the appended setting; install the matching plugins.
- Boot protocol and minimum bootloader remain unchanged at 0.9.1.

## 0.9.1 — Restore boot choice handling

- Preserve the original filesystem error when cleaning up a failed native
  file open. Missing one-time request files must report ENOENT, not EBADF.
- This prevents an absent request from vetoing saved defaults, Hold selection
  and a valid one-time Apple or Rockbox request.
- Report an actual rejected request as "Boot request rejected", not "Apple
  boot failed" before Apple launch has even been attempted.
- Add a regression harness using the native filesystem opening and cleanup
  functions, rather than relying only on POSIX file-operation shims.
- Require the corrected 0.9.1 bootloader in release installer metadata.

## 0.9.0 — Boot choices and simpler appearance settings

- Current is the fresh-install default; Default is now its compatibility alias.
  Named Purple and other saved selections remain available.
- Boot stock Rockbox from `/.rockbox/rockbox.ipod`, with a conditional one-time
  Settings action and fallback to PodThings OS if the image cannot load.
- Save the default firmware independently of one-time reboot requests.
  Hold always recovers PodThings OS when Apple or Rockbox is the default.
- Add Appearance > Change Theme with friendly installed-theme names; retain
  all legacy controls under Advanced Theme Settings at the bottom.
- Correct the two Branding menu labels.
- Require the matching 0.9.0 bootloader for all models.

## 0.8.5 — Clearer menus, light palettes and volume overlay

- Fix Liquid Glass selected text clearing a rectangular hole in its highlight.
  Paint the text well in foreground mode so the landscape cannot erase it.
- Name the purple default `podthingsos-default`; retain `podthingsos-purple`
  as a compatibility preset so existing saved themes continue working.
- Add bright Pearl, Sky and Lavender themes with dark, high-contrast text.
- Replace the tiny volume readout with a centered, rounded overlay, live
  volume line and dB value. It replaces the time/progress area for two seconds,
  then restores it; seek mode takes precedence.
- Keep bootloader minimums and storage/handoff behavior unchanged.

## 0.8.4 — Expanded themes and landscape Liquid Glass

- Ship matching firmware and bootloaders for Video 5G/5.5G (one 32/64 MB
  image), Classic 6G and Nano 3G.
- Add Mint, Rose, Amber and Graphite alongside Current, Blue and Purple.
- Add Liquid Glass with shaded panels and reflective rims over a
  public-domain Yosemite photograph by Ted Wakabayashi. Panel blur and
  tinting are pre-rendered; no runtime blur is required.
- Bundle wallpaper provenance and license details with the themes and
  firmware; preserve the Purple default and saved theme selections.
- Discover every bundled palette during theme packaging and native checks,
  including the Liquid Glass menu backdrop.
- Keep bootloader minimums and all storage/handoff behavior unchanged:
  Video 0.8.3, Classic/Nano 0.8. Nano retains the authorized recognized-NAND
  write opt-in, with unknown combinations rejected.

## 0.8.3 — New iPod identity and Video handoff revision

- Replace the PodThings OS logo in firmware, bootloaders, theme palettes and
  repository branding with the new cream-to-lavender iPod SVG; fix its missing
  body gradient while preserving the supplied colors and proportions.
- Keep Video storage awake while persisting one-time Apple request deletion,
  avoiding the immediate standby → reset → read sequence. Reject failed cache
  barriers and show Apple loading progress. Physical Apple boot is unconfirmed.
- Require Video bootloader 0.8.3; Classic and Nano minimums remain 0.8.
- Rebuild all three targets, retaining the Nano recognized-NAND write policy.
- Recapture simulator feature screenshots with the new assets.

## 0.8.2 — Video and Classic navigation patch

- Fix MENU trapping users between Cover Flow, Music and the previous browser.
  Music and Extras always return to Home rather than reopening their last child.
- Keep the Now Playing → selected album → Cover Flow overview → Music → Home
  return chain; database-unavailable exits also return to Music.
- Rebuild Video 5G/5.5G and Classic 6G firmware and matching plugins. Existing
  compatible bootloaders can be retained; minimum versions are unchanged.

## 0.8.1 — Video 5G/5.5G patch

- Enable the modern default status bar and migrate early bundled Video theme
  configurations once, preserving palettes, custom themes and branding choices.
- Add a read-only, validated Apple firmware-partition fallback to the Video
  loader; failed one-time requests fall back to PodThings instead of stopping.
- Require Video bootloader 0.8.1 in installer metadata; other model minimums
  remain unchanged. Add model-specific patch packaging and regression tests.

## 0.8

- Unified Video 5G, Classic 6G and Nano 3G release naming.
- Show **iPod** when the supplied Now Playing theme's branding is disabled.
- Remove the Nano's experimental on-device label; retain documented NAND
  validation limits and the explicit opt-in write policy.
- Include the Nano artwork/audio-stack fix confirmed by the physical tester.
- Prepare a firmware-only GitHub repository with host-test CI and clean source
  packaging; remove old local downloads and obsolete release-note files.

## Earlier development

- PodThings OS branding, native splash/credits and `/.podthingsloader` layout.
- Menu-as-Back iPod navigation; wheel seeking with a temporary scrub mode.
- Modern Current, Blue and Purple themes, Unicode fonts and battery/volume UI.
- Read-only use of iTunes playlists and artwork, Cover Flow, Shuffle Songs,
  playback metadata guards, theme-independent branding settings.
- One-time Apple firmware reboot for supported ATA-based iPods.
- Nano 3G builds based on the upstream port, RAM-only NAND diagnostics and
  opt-in write support for recognized NAND ID/bank combinations.

Historical source acknowledgments remain in `rockbox-firmware/UPSTREAM.md`.
Old binary downloads are not retained in this repository.
