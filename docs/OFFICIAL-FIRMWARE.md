# Reboot to Official Firmware

This feature is implemented for the ATA-based Video 5G and Classic 6G only.
The Nano 3G uses NAND storage and needs its own one-time boot handoff; the
Settings option is intentionally absent there. Removing a device's release
labels does not add this missing hardware-specific implementation.

In **Settings**, select **Reboot to Official Firmware** and confirm.
This requests Apple's firmware for one boot only. PodThings OS remains the
normal default: after a full reset/reboot from Apple firmware, with no
boot-selection buttons held, PodThings OS should start again.

Waking from sleep or resuming Apple's hibernation is not a full reboot.
The existing hold-switch, button-selection, recovery, and hibernation
behaviors have not been replaced.

## Requirements and update safety

- Use matching firmware and bootloader for your exact model, with support for
  the one-time handoff protocol.
  The protocol was introduced in 0.4; pre-0.4 bootloaders do not understand it.
- Apple's original firmware must still be installed and usable. This package
  does not contain, reinstall, patch, or restore Apple's proprietary firmware.
- On Video 5G, the normal original-firmware path is reused: `apple_os.ipod`
  in the firmware folder/root, or the original retail firmware loaded by the
  device's boot chain. With the matching 0.8.3 Video loader, a one-time request
  also has a bounded, read-only fallback to a checksum-validated Apple OSOS/
  OSBK image in the existing firmware partition. Warm reboots do not rely on
  a retained RAM signature. A missing/invalid image, unsupported disk geometry,
  or failed read is rejected; it cannot restore an erased Apple image.
  Version 0.8.3 persists request deletion with a checked ATA flush while
  keeping the disk awake for the following image read. Earlier Video loaders
  used a standby barrier that forced an immediate disk reset/wake sequence.
  Update the flashed bootloader too; copying firmware files cannot replace it.
- On Classic 6G, the original Apple bootloader already in NOR is launched.
  The existing disk-size/LBA48 compatibility restriction is retained; this
  action does not enable the LEFT-button override or make an unsupported
  modified disk safe for Apple firmware.
- Back up the working installation and establish model-specific recovery
  before changing a bootloader. Follow `README.md` in the device package.
  No automatic flashing or disk-modification commands are supplied.
- Firmware/theme settings are preserved; this is not a factory reset.

## One-shot behavior and failure handling

The firmware writes a validated request to
`/.podthingsloader/boot-official-once`, synchronizes it, and uses the normal
clean-reboot flow to stop audio/recording and save settings/bookmarks.
If that flow returns without rebooting (for example, a busy database), the
firmware removes the request instead.

The matching bootloader reads, deletes, and flushes the request **before**
attempting to start Apple firmware. A missing request means normal startup.
It also waits for ATA storage standby, which flushes the drive's volatile
cache; an unsuccessful standby does not authorize the Apple handoff.
An invalid request, read error, or failure to clear/flush it never authorizes
an Apple handoff. Do not retry blindly if a storage error is reported.
If clearing fails, a request may remain pending until it can be cleared;
it is never treated as permission for repeated successful Apple boots.

Even when Apple firmware fails to load or fails the disk-compatibility check,
a successfully consumed request is already gone. A subsequent normal full
reboot therefore does not repeat that request.
The Video 0.8.1 loader returns to PodThings OS after a failed **one-time**
Apple request rather than stopping at its boot screen. Manual Hold/Menu
selection retains its usual behavior.

Do not use the action on an older bootloader: it will ignore the request.
If this happened, remove `/.podthingsloader/boot-official-once` before updating
the bootloader, to avoid a delayed, unexpected original-firmware boot.

## Verification

Host tests compile and execute the actual shared C protocol against temporary
files, including repeated boots, cancellation, invalid/trailing data, and
injected read/write/sync/close/remove/flush/standby failures. Tests cover
targets both with and without the optional storage-flush hook. Both model-specific ARM
firmware and bootloaders are built and validated separately.

Compilation and host tests do **not** verify real boot-ROM, original-firmware,
storage modification, or power-transition behavior.

On each physical model, verify:

1. Cancelling the confirmation leaves playback and normal boot unchanged.
2. Confirming the action saves state and reaches working Apple firmware.
3. The request file is absent after that handoff.
4. A full reboot without boot-selection buttons returns to PodThings OS.
5. Repeating the menu action permits one further Apple boot, not a new default.
6. Normal hold/Menu selection, USB/disk recovery, charging, and shutdown
   still work.
