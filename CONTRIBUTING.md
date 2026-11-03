# Contributing

PodThings OS is native iPod firmware, not a web application. Keep changes scoped
to the relevant target and preserve upstream copyright and license notices.

## Before submitting

1. Read the [README](README.md), [changelog](CHANGELOG.md), and
   [installation notes](docs/INSTALLATION.md).
2. Prepare fixtures and run the host checks:

   ```sh
   bash scripts/prepare-host-tests.sh
   ASAN_OPTIONS=detect_leaks=0 python3 -m unittest discover -s tests -p 'test_*.py'
   ```

3. Build affected firmware/bootloader targets and check installed-layout skins.
   Host tests, ARM compilation and simulators are not physical-device tests.
4. Include the target, exact NAND ID/bank count where relevant, reproduction
   steps and panic-screen photo or exact text in a bug report. Do not post
   full NAND dumps, device serial numbers or personal music libraries.

## Safety and compatibility

- Never alias Nano hardware to Classic merely because CPU/display are similar.
- Keep default NAND validation, unknown-chip rejection, diagnostic write
  rejection and read-only bootloader FTL mounts intact.
- The documented Nano write opt-in is not permission to call untested variants
  validated or silently remove consistency checks.
- Shared readers may run on the small audio stack. Inspect ARM stack use and
  guard shared scratch buffers across yielding/concurrent calls.
- Plugins must match the firmware's model and API version. Do not mix `.rock`
  files from upstream builds or different targets.
- Preserve license/author notices, file-format compatibility and truthful
  release documentation.

## Releases

Change `VERSION`, update `CHANGELOG.md`, build and validate each target, then
attach generated downloads to a GitHub Release. Keep binaries and build caches
out of Git. Source packages must correspond to the distributed binaries.
Never publish a release or flash a connected device automatically from CI.

Run `python3 scripts/check-public-repo.py` before publishing source. Keep local
tools, uploads, assistant instructions, caches and `generated-artifacts/`
out of Git. Do not remove upstream sources or license notices to reduce size.
