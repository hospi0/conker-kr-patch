"""텍스트 렌더러를 찾는다.

렌더러는 글리프 메타 배열을 읽어야 한다.
    meta_ptr_array = 0x80085994          ( *(0x80085994 + fontid*4) = meta 배열 )
    meta[idx] = [w+1][h+1][xoff][yoff]
따라서 `lui *,0x8008` + `... 0x5994(*)` 를 참조하는 코드가 렌더러 후보다.
글리프 전처리 루틴(0x802CDA38)은 제외한다.
"""
import os
import sys

import numpy as np
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS64, CS_MODE_BIG_ENDIAN

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

RAM = 0x80000000
KNOWN_LOADER = range(0x802CD900, 0x802CE000)


def main():
    name = sys.argv[1]
    d = open(os.path.join(project.ROOT, 'work', name), 'rb').read()
    n = len(d) // 4
    w = np.frombuffer(d[:n * 4], dtype='>u4')
    op = w >> 26
    rs = (w >> 21) & 0x1F
    rt = (w >> 16) & 0x1F
    imm = w & 0xFFFF

    lui = {}
    for i in np.flatnonzero((op == 0x0F) & (imm == 0x8008)):
        lui.setdefault(int(rt[i]), []).append(int(i))

    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS64 | CS_MODE_BIG_ENDIAN)
    md.skipdata = True

    for off, label in ((0x5994, 'meta 포인터 배열'), (0x5990, 'pix 포인터 배열')):
        print('=== %s (0x8008%04X) 참조 ===' % (label, off))
        sites = np.flatnonzero(np.isin(op, [0x09, 0x23, 0x25, 0x24, 0x21, 0x20, 0x2B, 0x29, 0x28])
                               & (imm == off))
        found = []
        for i in sites:
            i = int(i)
            src = int(rs[i])
            for j in lui.get(src, []):
                if 0 < i - j <= 14:
                    a = RAM + i * 4
                    if a in KNOWN_LOADER:
                        continue
                    found.append(a)
                    break
        print('  로더 밖 참조: %d곳  %s' % (len(found), ['%08X' % a for a in found[:10]]))
        for a in found[:3]:
            print('\n  --- %08X 주변 ---' % a)
            s = (a - RAM) // 4 - 12
            for ins in md.disasm(d[s * 4:(s + 44) * 4], RAM + s * 4):
                mark = ' <==' if ins.address == a else ''
                print('     %08X  %-9s %s%s' % (ins.address, ins.mnemonic, ins.op_str, mark))
        print()


if __name__ == '__main__':
    main()
