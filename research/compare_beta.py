"""Offline Thumb disassembly of calibration handlers; never opens a controller.

Run with the steam-controller environment (requires capstone). Images remain
local, ignored research inputs. Addresses are from each image's registration
table, not assumed to be stable between builds.
"""
from pathlib import Path
import struct
import difflib
import re
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

ROOT = Path(__file__).resolve().parent
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)


def read(build):
    return (ROOT / f'IBEX_FW_{build}.fw').read_bytes()


def disasm(data, start, end):
    return [f'{i.mnemonic} {i.op_str}' for i in
            md.disasm(data[start - 0x8000 + 32:end - 0x8000 + 32], start)]


if __name__ == '__main__':
    old, new = read('6A628345'), read('6AA43B55')
    for label, data, table in [('old', old, 0x5DD4C), ('beta', new, 0x60714)]:
        print(label, 'table')
        for offset in range(table - 120, min(table + 240, len(data) - 11), 12):
            op, put, get = struct.unpack_from('<III', data, offset)
            print(hex(offset), hex(op), hex(put), hex(get))
        for name in (b'cal/joy_l\0', b'cal/joy_r\0'):
            address = data.index(name) + 0x8000 - 32
            needle = struct.pack('<I', address)
            for offset in range(0, len(data) - 24, 4):
                if data[offset:offset+4] == needle:
                    print(name, 'reference', hex(offset),
                          [hex(x) for x in struct.unpack_from('<6I', data, offset)])
    # End each range before its literal pool. Decoding pools as instructions
    # can create misleading differences or stop the disassembler early.
    regions = (
        ('phase handler', 0x1EF68, 0x1F348, 0x7C),
        ('sample callback', 0x1EE84, 0x1F264, 0xCC),
        ('left getter', 0x1E56C, 0x1E94C, 0x34),
        ('right getter', 0x1E5D4, 0x1E9B4, 0x38),
        ('left setter', 0x1E690, 0x1EA70, 0x20),
        ('right setter', 0x1E6B4, 0x1EA94, 0x20),
        ('read ED', 0x42B1A, 0x438DE, 0x3A),
        ('stage EE', 0x42B54, 0x43918, 0x2C),
        ('persist EF', 0x42B80, 0x43944, 0x38),
    )
    for label, a, b, length in regions:
        print('\n', label)
        left, right = disasm(old, a, a + length), disasm(new, b, b + length)
        print('\n'.join(difflib.unified_diff(left, right)))
        # Normalize only destinations of control-transfer instructions. This
        # checks instruction shape, NOT equivalence of the called functions.
        def shape(lines):
            return [re.sub(r'#0x[0-9a-f]+', '<destination>', line)
                    if line.split(' ')[0].startswith(('b', 'cb')) else line
                    for line in lines]
        print('Same instructions except branch destinations:', shape(left) == shape(right))
