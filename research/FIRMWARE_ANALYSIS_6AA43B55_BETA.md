# Beta calibration comparison: 6AA43B55

Offline comparison on September 20, 2026 against the hardware-tested
6A628345 build. No controller was updated or written during this investigation.

## Image identity

Source: https://opensteamcontroller.github.io/Ibex-Firmware/Controller/IBEX_FW_6AA43B55.fw

The image matches the previously downloaded archive catalog:

- Size: 395172 bytes, including a 32-byte container header.
- SHA-256: `51e0af41cc95d93044bde0ac33c672ce43711075fe5adb5217eb06745785d226`.
- Payload CRC32: `2a7a3350`, matching the header.
- The archived catalog records its first publicbeta appearance on September 17, 2026.

This identifies the investigated image; it does not establish which build a
particular tester has installed or whether the archive includes every later beta.

## Relevant handlers

Addresses below are Thumb instruction addresses (registration pointers have bit 0 set).

| Function | 6A628345 | 6AA43B55 |
| --- | --- | --- |
| D8 phase handler | 0x1EF68 | 0x1F348 |
| Stick sampling callback | 0x1EE84 | 0x1F264 |
| Left getter / setter | 0x1E56C / 0x1E690 | 0x1E94C / 0x1EA70 |
| Right getter / setter | 0x1E5D4 / 0x1E6B4 | 0x1E9B4 / 0x1EA94 |
| ED read | 0x42B1A | 0x438DE |
| EE stage | 0x42B54 | 0x43918 |
| EF persist | 0x42B80 | 0x43944 |

Disassembly of these nine code ranges has matching instructions and operands
except branch/call destinations. Literal pools are excluded from instruction
comparison. The setting descriptors still associate the getter/setter pairs with
`cal/joy_l` and `cal/joy_r`.

The phase handler reads payload byte 1, accepts phases 0–3, and initializes two
type-2 records for phase 1. The callback uses an 18-byte record stride. Phase 1
updates center bounds at offsets 6/8 and 14/16; phase 2 updates travel bounds at
2/4 and 10/12. Phase 3 invokes the storage path for both records, clears the phase,
and unregisters the callback. Both getters return 18 bytes and setters supply
18 as the expected size to their copy/validation helper. ED/EE/EF retain their
path parsing, value-length handling, and getter/stage/persist call structure.

This is strong evidence that the immediate calibration interface is unchanged.
It is not a whole-firmware equivalence proof: called storage/validation routines,
literal targets, report generation, and all runtime interactions have not been
exhaustively compared. Beta hardware calibration and restoration remain untested.

## Utility policy implications

The current utility deliberately rejects builds other than 6A628345 at connection.
This alone explains an unsupported-firmware error on this beta. It does not prove
the cause of any other error a tester may have encountered.

Removing only that gate leaves inconsistent behavior: backup validation still
rejects other builds, and the GUI connection label and automatic session metadata
use a constant old build number. GUI restore currently checks serial identity
but relies on the single-build gate for firmware compatibility.

A future version policy should distinguish hardware-tested builds, statically
reviewed builds, and unknown builds. An explicit per-controller-session opt-in
can permit experimental use, while retaining actual firmware identity in backups
and logs, same-device/same-build restore checks, immutable backups, record
validation, and readback verification. A warning cannot guarantee rollback on
an unknown protocol: successful transport is not proof of safe write semantics.

Reproduce the handler comparison with `python research/compare_beta.py` from the
utility folder, using the steam-controller environment with Capstone installed
and both ignored firmware images available locally. The script performs no HID I/O.
