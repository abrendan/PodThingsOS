# Upstream provenance

- Project: Rockbox
- Public read-only mirror: https://github.com/Rockbox/rockbox
- Authoritative upstream: https://www.rockbox.org/
- Imported branch: `master`
- Imported revision: `6a0cbd821252c9951101a066c5af2b154444a7bd`
- Imported date: 2026-10-19

Upstream licenses and copyright notices remain in place. This fork is not an
official Rockbox release, and the PodThings OS name does not imply
endorsement by the Rockbox project or Apple.

## Current fork

The current fork supports Video 5G, Classic 6G and Nano 3G. Native branding
reads PodThings OS, credits abrendan and acknowledges Rockbox. The supplied
themes display **iPod** when Now Playing branding is disabled. This does not
remove upstream authorship, source identifiers, license notices or compatibility
signatures.

Nano support builds on the upstream experimental NAND/FTL port. Installation
and playback are confirmed on the tester's Micron two-bank 4 GB unit, not every
recognized NAND row. The explicit write opt-in and diagnostic protections are
documented in `../docs/RELEASE-0.8.md`. Removing device labels is not a claim
of universal hardware validation.

## Historical fork changes

The PodThings OS skin is bundled through `wps/WPSLIST`. The iPod Video and iPod 6G
targets select it by default in `apps/settings_list.c`; other device defaults
remain upstream's. Their default menu palette and backdrop are also adjusted.

The menu title, firmware version label, and target-specific bootloader banner
use the PodThings OS name while retaining Rockbox attribution. The compiled
firmware splash and bootloader now embed the supplied purple card logo and
acknowledge "Built by abrendan" and "based on Rockbox". These compiled images do not need a disk theme
to display during early boot.

Version 0.3 intentionally changes firmware lookup and resource paths to
`/.podthingsloader/podthingsos.ipod`. Hardware storage/recovery drivers are not
redesigned, but the new path requires a matched bootloader/firmware migration.
Installed fallback, metadata, font-config and debug-map filenames use the
PodThings prefix. Upstream internal identifiers and copyright/license notices
remain intact.

Padded non-touchscreen lists change the plugin settings ABI, so these targets
use a separate plugin API version and reject older plugins. The default theme
uses larger text, rounded highlights, the supplied logo, and purple cards.
Current, Blue, and logo-coordinated Purple presets share this layout; Purple
is the factory default. Version labels use 0.3 without a development suffix,
and the Classic service menu is named Advanced menu.

The native Credits screen names abrendan and Rockbox Team and displays the
supplied abrendan logo. Original contributor credits remain accessible as
Rockbox Credits. This preserves acknowledgment rather than removing authorship.

Bundled plugin product labels and generated-file producer labels use the
PodThings name. The old wordmark-only Bounce demo is omitted from the runtime
package; its upstream source and notices are preserved. File-format signatures,
hardware IDs, upstream URLs, and source/debug identifiers are not product
branding and remain compatible.

The two target keymaps use Menu to go back, Select to enter, and a held Menu
to reach the main menu from core lists and Now Playing. Previous/Next retain
track/seek controls during playback and no longer act as Back/Enter in menus.
Other device keymaps retain upstream behavior. Specialized editing widgets
keep their context-specific controls.
