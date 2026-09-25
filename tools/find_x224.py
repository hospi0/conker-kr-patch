"""×224 관용구(sll 3 ; subu ; sll 5)를 찾아 픽셀 버퍼 할당 지점을 짚는다.

ProcessGlyph 의 인덱싱이 idx*224 를 이렇게 계산한다:
    sll  t, idx, 3      ; idx*8
    subu t, t, idx      ; idx*7
    sll  t, t, 5        ; idx*224
할당도 count*224 를 같은 방식으로 계산할 가능성이 높다.
"""
import os
import sys

import numpy as np
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS64, CS_MODE_BIG_ENDIAN

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

RAM = 0x80000000


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else 'hard_rdram.bin'
    d = open(os.path.join(project.ROOT, 'work', name), 'rb').read()
    n = len(d) // 4
    w = np.frombuffer(d[:n * 4], dtype='>u4')
    op = w >> 26
    rs = (w >> 21) & 0x1F
    rt = (w >> 16) & 0x1F
    rd = (w >> 11) & 0x1F
    sa = (w >> 6) & 0x1F
    fn = w & 0x3F

    is_sll = (op == 0) & (fn == 0x00)
    is_sub = (op == 0) & ((fn == 0x22) | (fn == 0x23))

    hits = []
    for i in np.flatnonzero(is_sll & (sa == 3)):
        i = int(i)
        src = int(rt[i])          # sll rd, rt, sa  -> 소스는 rt
        dst = int(rd[i])
        # 다음 8개 안에서 subu dst, dst, src
        for j in range(i + 1, min(n, i + 9)):
            if is_sub[j] and int(rd[j]) == dst and int(rs[j]) == dst and int(rt[j]) == src:
                for k in range(j + 1, min(n, j + 9)):
                    if is_sll[k] and int(sa[k]) == 5 and int(rt[k]) == dst:
                        hits.append((i, j, k))
                        break
                break

    print('%s: ×224 관용구 %d곳' % (name, len(hits)))
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS64 | CS_MODE_BIG_ENDIAN)
    md.skipdata = True
    for i, j, k in hits:
        a = RAM + i * 4
        print('\n--- %08X ---' % a)
        s = i - 10
        for ins in md.disasm(d[s * 4:(k + 8) * 4], RAM + s * 4):
            mark = ' <==' if ins.address == a else ''
            print('   %08X  %-9s %s%s' % (ins.address, ins.mnemonic, ins.op_str, mark))


if __name__ == '__main__':
    main()
