"""TLB 가상주소 기준 jal 로 특정 함수의 호출자를 찾는다.

관측:  VA 0x15015A38  =  RDRAM 0x802CDA38   (ProcessGlyph)
       delta = RDRAM - VA = 0x6B2B8000
jal 은 하위 26비트만 담으므로 상위 4비트는 PC 에서 온다. capstone 은 0x8... 로 보여준다.
"""
import os
import sys

import numpy as np
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS64, CS_MODE_BIG_ENDIAN

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

RAM = 0x80000000
DELTA = 0x6B2B8000          # RDRAM - VA


def va_of(rdram_addr):
    return (rdram_addr - DELTA) & 0xFFFFFFFF


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else 'hard_rdram.bin'
    target_rdram = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x802CD920
    d = open(os.path.join(project.ROOT, 'work', name), 'rb').read()
    n = len(d) // 4
    w = np.frombuffer(d[:n * 4], dtype='>u4')
    op = w >> 26
    idx26 = w & 0x03FFFFFF

    va = va_of(target_rdram)
    enc = (va >> 2) & 0x03FFFFFF
    print('대상 RDRAM %08X  ->  VA %08X  ->  jal index %07X' % (target_rdram, va, enc))

    hits = np.flatnonzero(((op == 3) | (op == 2)) & (idx26 == enc))
    print('호출/점프 %d곳' % len(hits))
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS64 | CS_MODE_BIG_ENDIAN)
    md.skipdata = True
    for h in hits[:6]:
        a = RAM + int(h) * 4
        print('\n--- 호출자 %08X (VA %08X) ---' % (a, va_of(a)))
        s = int(h) - 30
        for ins in md.disasm(d[s * 4:(int(h) + 4) * 4], RAM + s * 4):
            mark = ' <==' if ins.address == a else ''
            print('   %08X  %-9s %s%s' % (ins.address, ins.mnemonic, ins.op_str, mark))


if __name__ == '__main__':
    main()
