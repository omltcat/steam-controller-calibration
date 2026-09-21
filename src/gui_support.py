"""Shared GUI constants, paths, and manual-record validation helpers."""
from datetime import datetime
from pathlib import Path
import sys

from .protocol import calibration_issues, decode_calibration, encode_calibration

def _runtime_root():
    """Use the executable directory for frozen builds, never PyInstaller's temp tree."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


ROOT = _runtime_root()
CAPTURES = ROOT / 'captures'


def asset_path(name):
    """Resolve a bundled asset in development and in a frozen PyInstaller app."""
    if getattr(sys, 'frozen', False):
        return Path(getattr(sys, '_MEIPASS', Path(sys.executable).resolve().parent)) / 'assets' / name
    return ROOT / 'assets' / name
# Firmware setting paths are an allowlist shared by every GUI write operation.
PATHS = ('cal/joy_l', 'cal/joy_r')
CENTER_SECONDS = 5.0
RANGE_SECONDS = 12.0
RECONNECT_SECONDS = 2.0
ROWS = (('Left X', 'cal/joy_l', 'x'), ('Left Y', 'cal/joy_l', 'y'),
        ('Right X', 'cal/joy_r', 'x'), ('Right Y', 'cal/joy_r', 'y'))


def new_capture_path(label):
    """Return a millisecond-stamped path that will not overwrite an earlier session."""
    # One-file builds start without a project directory beside the executable;
    # create it before the caller writes the immutable backup or session JSON.
    CAPTURES.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:-3]
    return CAPTURES / f'{stamp}-{label}.json'


def display_path(path):
    """Keep long absolute capture paths out of the compact status area."""
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return Path(path).name


def encode_manual_record(fields):
    """Encode and safety-check values entered in the calibration table."""
    data = encode_calibration(fields)
    issues = calibration_issues(decode_calibration(data))
    if issues:
        raise ValueError('\n'.join(issues))
    return data
