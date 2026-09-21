# Firmware joystick calibration feasibility — 2026 Steam Controller / Windows

Research date: September 19, 2026. Context recovered from the earlier task **Calibrate Steam Joystick** (`6aae2138-b870-83e8-aa7d-cc089ef4f222`). The relevant request was specifically for firmware-level calibration of the 2026 controller, independent of the SDL input-display prototype. The old conversation's initial 2015-controller instructions do not apply.

## What we can conclude

**A small Windows utility can communicate with the controller, read its persistent stick calibration, and now implements the calibration state machine found in the exact matching stock firmware.** The workflow passed a read-only hardware preflight but has not yet committed new records.

The inspection utility in this folder establishes transport and measurement groundwork. It intentionally does not replace the requested firmware calibration with application-side normalization.

## Evidence and confidence

| Question | Finding | Evidence / limit |
|---|---|---|
| Does a joystick-calibration command name exist? | Yes: shared SDL headers define `ID_CALIBRATE_JOYSTICK = 0xBF`. | Valve-copyrighted SDL protocol header; this shared enum is not a list of handlers verified on every Valve device. |
| Does `0xBF` work on this Ibex build? | No handler is registered. | Exact firmware `6A628345` has no `0xBF` operation-table entry. Its stick handler is SET opcode `0xD8`. |
| Is `0xC3` a fallback joystick calibration? | No evidence for that. | sc26re explicitly annotates the stock handler as pressure-sensor calibration, despite SDL naming it `CALIBRATE_ANALOG`. |
| Are stick calibration values stored on the device? | Strong RE evidence says yes. | sc26re imports stock records named `cal/joy_l` and `cal/joy_r` and uses their bounds for stick scaling. Not independently verified on this controller. |
| Can the values be read? | Yes, verified on this controller. | Stock `0xED` returned valid 18-byte `cal/joy_l` and `cal/joy_r` records. Manual stage/commit writes remain unimplemented. |
| Can Windows read the input directly? | Yes, tested here through the Puck. | Low-level SDL HIDAPI captured 531 native stick reports in two seconds without sending controller configuration commands. |

## Primary source collection

Each downloaded file's revision, exact URL, byte count and SHA-256 is recorded in [manifest.json](manifest.json). Browse [sources](sources) for the original files. The counts below describe the downloaded subset, not entire repositories.

| Source | Archived | Why it matters |
|---|---:|---|
| [SDL / Valve controller definitions](https://github.com/libsdl-org/SDL/tree/main/src/joystick/hidapi/steam) | 4 files | `controller_constants.h`, `controller_structs.h`, the Triton HID driver and SDL license. Defines the shared commands, report layouts and actual Triton driver framing. |
| [mwdmwd/sc26re](https://github.com/mwdmwd/sc26re) | 63 files | Relevant C/header/Markdown sources and license. Most useful evidence for factory calibration storage, named settings, and the distinction between original and replacement firmware. |
| [CouchTurtle/sc2-research](https://github.com/CouchTurtle/sc2-research) | 10 files | All seven documentation pages, README, license and attribute-query utility. Covers updater, HID layouts, methods, firmware differences and uncertain conclusions. |
| [iczero/steam-controller-stuff](https://github.com/iczero/steam-controller-stuff) | 2 files | Protocol overview and license. Useful companion project for HID dissector/audio research; it does not provide a verified stick-calibration procedure. |
| [safijari/openpuck](https://github.com/safijari/openpuck) | 13 files | Markdown documentation and license. Describes USB/RF relay framing, slot routing and host/controller communication. |
| [OpenSteamController/Ibex-Firmware](https://github.com/OpenSteamController/Ibex-Firmware) | 1 file | Archive README: provenance, firmware header/checksum and catalog schema. Firmware binaries were not downloaded or flashed. |

Valve's current [2026 feature and troubleshooting guide](https://help.steampowered.com/en/faqs/view/33E8-5EDF-24E6-4CFB) describes connection modes, firmware updates and support, but does not publish a stick-calibration HID transaction or payload. The [2015 troubleshooting page](https://help.steampowered.com/en/faqs/view/41EA-7E25-B1F0-67E9) describes an old calibration UI and explicitly directs 2026 owners elsewhere. These support pages were reviewed online and are linked here rather than archived in full.

The [SDL HID read API](https://wiki.libsdl.org/SDL3/SDL_hid_read_timeout), [enumeration API](https://wiki.libsdl.org/SDL3/SDL_hid_enumerate), and [feature read API](https://wiki.libsdl.org/SDL3/SDL_hid_get_feature_report) provide the supported host API used by this utility. PySDL3 is already installed in the requested Conda environment, so a second HID library is unnecessary.

Other leads found during discovery: [SteamHapticsPlayer](https://github.com/Pixel1011/SteamHapticsPlayer), [SteamlessController](https://github.com/ddeverill/SteamlessController), [Rune580/sc-evdev](https://github.com/Rune580/sc-evdev), and [steam-controller-dsu](https://github.com/njanke96/steam-controller-dsu). These are further transport/driver leads, not independently verified calibration implementations in this investigation. Older [OpenSteamController](https://github.com/greggersaurus/OpenSteamController) and [cyrozap/steam-controller-re](https://github.com/cyrozap/steam-controller-re) concern the 2015 generation and must not supply assumed Ibex write packets.

## Specific firmware leads

### Factory stick records

See sc26re `app/src/calibration.h` (`struct stick_calibration`) and `calibration.c` (`calibration_import_valve_storage`). The described packed record is nine little-endian unsigned 16-bit fields, 18 bytes total:

| Offset | Field |
|---:|---|
| 0 | type |
| 2, 4 | X minimum, maximum |
| 6, 8 | X center minimum, maximum |
| 10, 12 | Y minimum, maximum |
| 14, 16 | Y center minimum, maximum |

The replacement firmware validates `min < center_min <= center_max < max` for each axis. Its analog processing consumes these sensor-domain bounds. A normal HID stick report already reflects firmware processing; an output like `+2441` is not a value we can simply write into one of these fields. The `type` field's full stock semantics and valid range are not established here.

sc26re's application README describes the stock storage region separately from its own settings partition. Its factory-data import path reads stock storage; its own stage/commit behavior is not proof of how Valve's firmware persists changes. In particular, `valve_settings.c` implements trigger and pressure calibration paths while stick records are imported elsewhere. Do not mistake successful compilation of replacement firmware for a validated stock stick-write recipe.

### HID and named settings

See sc26re `app/src/valve_feature.h` / `valve_feature.c` and sc2-research `docs/FIRMWARE_PROTOCOL.md`.

The candidate read transaction is report ID `01`, opcode `ED`, one-byte payload length, then a NUL-terminated setting path. For `cal/joy_l`, the length is 10. The utility constructs a 64-byte send buffer including report ID, matching the inspected SDL Triton driver, and permits a 65-byte receive buffer. A response must match report ID and opcode and contain an in-bounds declared payload before it is interpreted.

This read is verified on the directly attached controller running `6A628345`. It remains restricted to direct USB runtime PID `1302`; it does not route queries to a Puck. Automatic restoration remains unavailable because the manual write path is not validated.

The Puck has multiple slots and a separate device feature channel. OpenPuck's protocol documentation shows why a controller command and a Puck command cannot be interchanged merely because their numeric opcode matches. That is also why the inspection tool does not expose arbitrary command entry or automatic opcode scanning.

## Exact firmware result and remaining work

The matching image was verified by length, CRC32 and archive SHA-256. Its operation table maps `0xD8` to a three-phase stick-calibration handler: phase 1 samples center bands, phase 2 samples extrema, and phase 3 stores both named records. See [FIRMWARE_ANALYSIS_6A628345.md](FIRMWARE_ANALYSIS_6A628345.md).

The utility implements that sequence with original-record capture, build/serial checks, centered-input preflight, observed-range thresholds, an explicit commit prompt and readback. Still needed: a user-authorized hardware calibration, post-power-cycle verification, and before/after centered and full-travel comparison. Puck routing and arbitrary firmware builds remain outside the implementation.

## Hardware observations from this session

The only enumerated 2026 hardware was a `28DE:1304` Puck, with four vendor controller-slot collections and a status collection. No directly connected `28DE:1302` controller was available, so the experimental record reads were not attempted.

A passive two-second capture on slot interface 2 contained 531 `0x42` inputs and 3 `0x7B` statuses. Stick medians were LX 43, LY 1572, RX 205, RY 2441. The user had not been instructed to release the sticks during this smoke test, so these values are transport evidence, not a drift diagnosis or a calibration baseline.

## Source limitations

The previous answer's statement that the command constant proves a built-in Ibex calibration implementation was too strong. Shared definitions, firmware strings, replacement firmware and live stock-firmware behavior are distinct levels of evidence. Some community documentation explicitly discloses heavy AI assistance and prior corrected interpretations; corroboration matters. Public web searches did not locate a verified stock 2026 joystick calibration payload or complete procedure. That is a bounded search result, not proof that none exists.
