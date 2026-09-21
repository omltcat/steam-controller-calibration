"""Firmware compatibility registry loaded when the application starts."""

HARDWARE_TESTED = 'hardware_tested'
REVIEWED = 'reviewed'
UNKNOWN = 'unknown'

# Hardware-tested means calibration and rollback were exercised on a controller.
# Reviewed means the relevant firmware handlers were compared offline, but the
# complete workflow has not yet been exercised on that build.
FIRMWARE_SUPPORT = {
    0x6A628345: {
        'level': HARDWARE_TESTED,
        'note': 'Calibration and byte-for-byte rollback tested on hardware.',
    },
    0x6AA43B55: {
        'level': REVIEWED,
        'note': 'Calibration and setting handlers reviewed; hardware workflow untested.',
    },
}


def firmware_support(build):
    """Return a copy of the compatibility entry for a firmware build."""
    entry = FIRMWARE_SUPPORT.get(build)
    if entry:
        return dict(build=build, **entry)
    return dict(build=build, level=UNKNOWN,
                note='This firmware has not been reviewed or tested.')

