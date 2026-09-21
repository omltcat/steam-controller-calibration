"""Command-line entry point for the guarded Steam Controller calibration utility."""
import argparse
import json
from pathlib import Path
import sys

from .cli_actions import analyze, backup_controller, calibrate, capture, inspect, restore
from .hid_transport import HID, select
from .protocol import decode_calibration


def main():
    """Parse CLI arguments, open one controller, and dispatch a workflow."""
    # Keep this entry point declarative; implementation lives in focused modules.
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('list', help='Enumerate Valve 2026 HID interfaces without opening a joystick')
    record = sub.add_parser('decode-record', help='Decode an offline 18-byte record as hex')
    record.add_argument('hex')
    analysis = sub.add_parser('analyze', help='Summarize a saved JSONL input capture')
    analysis.add_argument('file')
    for name in ('capture', 'inspect'):
        child = sub.add_parser(name)
        child.add_argument('--path', required=True, help='Exact HID path returned by list')
        child.add_argument('--output', required=True, help='New output filename (never overwritten)')
        if name == 'capture':
            child.add_argument('--seconds', type=float, default=5)
        else:
            child.add_argument('--experimental-stick-read', action='store_true',
                help='Try RE opcode 0xED for cal/joy_l and cal/joy_r; stock support unverified')
    backup = sub.add_parser('backup', help='Create an immutable, device-bound stick backup')
    backup.add_argument('--path', required=True)
    backup.add_argument('--output', required=True, help='New backup filename (never overwritten)')
    restoration = sub.add_parser('restore', help='Validate or restore an immutable stick backup')
    restoration.add_argument('--path', required=True)
    restoration.add_argument('--backup', required=True)
    restoration.add_argument('--output', required=True, help='New restore-session filename')
    restoration.add_argument('--apply', action='store_true', help='Allow prompted stage and commit')
    calibration = sub.add_parser('calibrate', help='Guided exact-build firmware calibration')
    calibration.add_argument('--path', required=True)
    calibration.add_argument('--serial', required=True, help='Must exactly match the target controller')
    calibration.add_argument('--output', required=True, help='New JSON backup/session filename')
    calibration.add_argument('--backup', help='New immutable backup filename; defaults beside --output')
    calibration.add_argument('--apply', action='store_true',
        help='Run corrected experimental phases with post-commit validation and automatic rollback')
    calibration.add_argument('--center-seconds', type=float, default=5.0)
    calibration.add_argument('--range-seconds', type=float, default=12.0)
    calibration.add_argument('--center-limit', type=int, default=5000)
    calibration.add_argument('--center-noise-limit', type=int, default=3000)
    calibration.add_argument('--range-threshold', type=int, default=20000)
    args = parser.parse_args()
    # Offline commands return before SDL/HID is initialized.
    if args.command == 'decode-record':
        print(json.dumps(decode_calibration(bytes.fromhex(args.hex)), indent=2))
        return
    if args.command == 'analyze':
        analyze(args.file)
        return
    if args.command == 'capture' and not 0 < args.seconds <= 3600:
        parser.error('--seconds must be > 0 and <= 3600')
    # Session files are evidence and rollback material; never overwrite them.
    if args.command in ('capture', 'inspect', 'backup', 'restore', 'calibrate') and Path(args.output).exists():
        raise ValueError('Output already exists; choose a new filename')
    if args.command == 'calibrate':
        backup_path = args.backup or (args.output + '.backup.json')
        if Path(backup_path).exists():
            raise ValueError('Backup output already exists; choose a new --backup or --output filename')
    if args.command == 'calibrate' and not (0.5 <= args.center_seconds <= 10 and
                                            5 <= args.range_seconds <= 60 and
                                            1000 <= args.range_threshold <= 30000):
        parser.error('Calibration timing/threshold arguments are outside supported bounds')
    # A single owner keeps feature-report ordering deterministic for each command.
    with HID() as hid:
        devices = hid.devices()
        if args.command == 'list':
            print(json.dumps(devices, indent=2))
            return
        info = select(devices, args.path)
        device = hid.open(info['path'])
        try:
            if args.command == 'capture':
                capture(hid, device, info, args.seconds, args.output)
            elif args.command == 'inspect':
                inspect(hid, device, info, args.output, args.experimental_stick_read)
            elif args.command == 'backup':
                backup_controller(hid, device, info, args.output)
            elif args.command == 'restore':
                restore(hid, device, info, args)
            else:
                calibrate(hid, device, info, args)
        finally:
            hid.s.SDL_hid_close(device)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)

