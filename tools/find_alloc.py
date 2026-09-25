"""메타 배열(0x80085994)·픽셀 버퍼(0x80085990) 포인터에 쓰는 코드를 찾는다.

글리프 개수를 늘리면 이 두 버퍼도 커져야 한다. 할당 크기가 상수라면 그 상수도 패치 대상.
"""
import os
import sys

import numpy as np
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS64, CS_MODE_BIG_ENDIAN

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

RAM = 0x80000000
TARGETS = {0x5990: 'PIX_PTRS 0x80085990', 0x5994: 'META_PTRS 0x80085994'}


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else 'hard_rdram.bin'
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
    print('lui *,0x8008 : %d곳' % sum(len(v) for v in lui.values()))

    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS64 | CS_MODE_BIG_ENDIAN)
    md.skipdata = True
    STORE = {0x2B: 'sw', 0x29: 'sh', 0x28: 'sb'}
    LOAD = {0x23: 'lw', 0x25: 'lhu', 0x24: 'lbu', 0x21: 'lh', 0x20: 'lb', 0x09: 'addiu'}

    for off, label in TARGETS.items():
        print('\n=== %s ===' % label)
        sites = np.flatnonzero(np.isin(op, list(STORE) + list(LOAD)) & (imm == off))
        found = 0
        for i in sites:
            i = int(i)
            src = int(rs[i])
            for j in lui.get(src, []):
                if 0 < i - j <= 14:
                    kind = STORE.get(int(op[i])) or LOAD.get(int(op[i]))
                    a = RAM + i * 4
                    print('  %-4s @ %08X' % (kind, a))
                    if kind in STORE.values():
                        # 앞 24개 명령을 보여 할당 크기를 찾는다
                        s = i - 24
                        for ins in md.disasm(d[s * 4:(i + 3) * 4], RAM + s * 4):
                            print('      %08X  %-9s %s' % (ins.address, ins.mnemonic, ins.op_str))
                        print()
                    found += 1
                    break
        if not found:
            print('  참조 없음')


if __name__ == '__main__':
    main()
