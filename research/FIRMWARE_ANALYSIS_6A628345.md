# IBEX firmware `6A628345`: stick-calibration handler analysis

This note records the evidence and hardware results from investigating the firmware calibration workflow. It applies only to the exact image `IBEX_FW_6A628345.fw` and does not generalize to another build.

> **Hardware result:** A September 19, 2026 trial generated records whose center windows covered most of the stick travel, causing all processed axes to report zero. The original records were successfully restored byte-for-byte. The phase meanings were correct, but the utility printed its movement instruction and waited one second before sending phase 2. Movement during that interval was still collected as phase-1 center data. The ordering is corrected. Applying runs now check committed geometry and automatically restore the backup if it resembles this failure.

## Image identity

- Controller attribute 4: `0x6A628345` / July 23, 2026 21:10:29 UTC.
- Archive SHA-256: `865b4a7b1786c4a9990375759548331d313170c3e3b4c5897e16dc01b9ab12a8`.
- File size: 384,476 bytes; 32-byte header plus 384,444-byte payload.
- Header and independently computed payload CRC32: `0009e42d`.
- The archive index says this build first appeared in public beta on August 6 and stable on September 2, 2026.

The downloaded file passed its length, embedded payload length, CRC32, and archive SHA-256 checks. It is analyzed offline and is never flashed by this utility.

## Command registration table

The firmware image is loaded at `0x8000` after its 32-byte container header. Its operation table uses 12-byte records: opcode, SET handler pointer, GET handler pointer. At file offset `0x5DD4C` (runtime `0x65D2C`) the relevant records are:

```text
D8 00 00 00  69 EF 01 00  00 00 00 00   opcode D8, SET handler 0x1EF69
C3 00 00 00  AD F2 01 00  00 00 00 00   opcode C3, SET handler 0x1F2AD
C0 00 00 00  3D F5 01 00  00 00 00 00   opcode C0, SET handler 0x1F53D
```

There is no `0xBF` operation record in this build's table. SDL's shared `ID_CALIBRATE_JOYSTICK = 0xBF` name therefore does not identify the stock Ibex handler in this firmware.

The same table registers generic setting operations `0xED` (read), `0xEE` (stage), and `0xEF` (persist). The `0xEE` handler parses a NUL-terminated setting path followed by value bytes and dispatches the value to the registered setter. The `0xEF` handler accepts only a NUL-terminated path, obtains its current staged value through the getter, and passes that value to persistent storage.

The setting descriptor table registers `cal/joy_l` with getter `0x1E56D` and setter `0x1E691`, and `cal/joy_r` with getter `0x1E5D5` and setter `0x1E6B5`. Both getters return exactly 18 bytes. Both setters pass an exact expected size of 18 to their validation/copy routine. This supports byte-for-byte backup restoration without synthesizing a new record.

sc26re independently calls `0xD8` `CALIBRATE_TRACKPAD_STICK`; its names for `0xC3` and `0xC0` match pressure and trigger calibration. The image contains the persistent record names `cal/joy_l` and `cal/joy_r`.

## Handler behavior

Thumb handler `0x1EF68` reads the second byte of its payload and accepts phase values 0–3:

- Phase 1 initializes two 18-byte stick records, sets each type to 2, installs sampling callback `0x1EE85`, and records center minimum/maximum for X and Y.
- Phase 2 keeps the callback installed and records full-travel minimum/maximum for both axes of both sticks.
- Phase 3 causes the next sample callback to save the right record to `cal/joy_r`, save the left record to `cal/joy_l`, then remove the callback.

The first payload byte is not read by this build's handler. The utility sends zero:

```text
report ID  opcode  length  reserved  phase  zero padding to 64 bytes
01         D8      02      00        01|02|03
```

The sampling callback's offsets match the 18-byte structure found independently in sc26re: `type`, X min/max/center-min/center-max, then the corresponding Y values. Phase 1 updates offsets 6/8 and 14/16; phase 2 updates offsets 2/4 and 10/12; phase 3 writes both records.

## Safeguards derived from the analysis

- Direct USB runtime PID `28DE:1302` and vendor HID collection only.
- Supplied serial must match; attribute 4 must equal `0x6A628345`.
- Read and validate both existing records before phase 1.
- Write an immutable device/build-bound backup with a content fingerprint before phase 1.
- Passive centered-input preflight before any calibration command.
- Phase 2 requires both polarities past a threshold on all four processed HID axes.
- Phase 3 requires a separate exact `COMMIT` prompt.
- Read back and validate both records after phase 3; preserve before/after bytes in a new JSON file.
- Restore only the two allowlisted 18-byte stick records. Stage both, verify by reading them back, require a second confirmation, persist both, then verify again.
- No arbitrary command or setting path, delete, reset, reboot, or firmware flash interface.

If execution stops after phase 1 or 2, phase 3 has not persisted the candidate records. Power-cycle the controller before retrying. That recovery follows from the distinct phase-3 storage path; it has not been tested by intentionally interrupting a physical controller.

Likewise, restore staging through `0xEE` is volatile until `0xEF` is sent. The restore request layout and registered record handlers were established by static analysis and the persistent restore path subsequently succeeded on hardware. The utility keeps both write steps behind exact typed confirmations.

## Failed calibration record evidence

The hardware trial persisted type-2 records with valid numerical ordering but unusable center widths. Examples include left X travel `447..2943` with center `507..2710`, and right X travel `392..2868` with center `421..2636`. The earlier validator checked only `min < center_min <= center_max < max`, so it did not detect this failure after commit.

The callback at `0x1EE84` confirms that phase 1 updates center minima/maxima and phase 2 updates travel minima/maxima. The utility sent phase 1, collected center, printed the range instruction, waited one second, and only then sent phase 2. A user following the visible instruction naturally began moving while phase 1 was still active. Phase 2 must be sent before any movement instruction is displayed. This ordering bug explains the observed record values.

The firmware does not expose the candidate buffers through the normal record getter before phase 3, so candidate geometry cannot be checked before persistence. The applying workflow therefore validates immediately after commit. It requires at least 1500 raw counts of travel, limits center width to 10% of travel (with a 200-count floor), and requires at least 20% of the travel span on both sides of the center window. Failure invokes the validated stage/persist restore path using the immutable pre-calibration records.

## Capacitive stick-touch state at commit

A successful GUI calibration was observed to leave Steam Input's gyro-on-stick-touch activator on until the controller was power-cycled. Writing and committing the same records through the generic setting operations did not reproduce it. Static analysis shows that `0xD8` does not write gyro or capacitive-sensor settings: phase 3 saves the two records, changes the phase byte back to zero, and unregisters the sampling callback. This makes persistent calibration corruption an unlikely cause.

The automatic workflow ends immediately after the user has held and rotated both sticks. Committing while a stick-touch bit remains asserted can leave either the controller report state or Steam Input's touch activator latched across that transition. The GUI now requires eight consecutive reports with both stick-touch bits clear before sending phase 3, and records post-commit touch-bit counts in the session JSON. If the symptom recurs while those counts are clear, the remaining fault is on the Steam Input/host side rather than in the controller's capacitive report.

Restore was then exercised with the original type-129 records. Both records verified after staging, both persist requests completed, and post-commit readback matched the backup exactly. This validates the rollback mechanism on this controller and firmware build.
