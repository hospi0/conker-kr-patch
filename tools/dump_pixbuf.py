"""패치본 세이브스테이트에서 디코드된 글리프를 그대로 뜬다.

ProcessGlyph 가 만든 결과를 직접 보면 RLE·치수 해석이 맞는지 즉시 판정된다.
    meta = *(0x80085994)  ->  [w+1][h+1][xoff][yoff] x N
    pix  = *(0x80085990)  ->  글리프당 224 B, stride = (w+1+7) & ~7
"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import pjstate

RAM = 0x80000000
META_PTRS = 0x80085990          # +0 = pix, +4 = meta
SLOT = 224


def main():
    path = sys.argv[1]
    idxs = [int(x) for x in sys.argv[2:]] or [17, 18, 40, 10, 0]
    st = pjstate.load(path)
    ram = st['rdram']
    pix = struct.unpack('>I', ram[META_PTRS - RAM:META_PTRS - RAM + 4])[0]
    meta = struct.unpack('>I', ram[META_PTRS - RAM + 4:META_PTRS - RAM + 8])[0]
    print('pix=%08X  meta=%08X' % (pix, meta))

    for i in idxs:
        m = ram[meta - RAM + i * 4: meta - RAM + i * 4 + 4]
        w1, h1, xo, yo = m[0], m[1], m[2], m[3]
        w, h = w1 - 1, h1 - 1
        stride = (w1 + 7) & ~7
        buf = ram[pix - RAM + i * SLOT: pix - RAM + i * SLOT + SLOT]
        print('\n=== 글리프 %d ===' % i)
        print('  meta: w+1=%d h+1=%d xoff=%d(%+d) yoff=%d   -> w=%d h=%d stride=%d'
              % (w1, h1, xo, xo - 256 if xo >= 128 else xo, yo, w, h, stride))
        rows = min(SLOT // stride, 16)
        for y in range(rows):
            r = buf[y * stride:(y + 1) * stride]
            print('   %2d |%s|' % (y, ''.join('#' if v >= 12 else ('+' if v else '.')
                                              for v in r)))


if __name__ == '__main__':
    main()
