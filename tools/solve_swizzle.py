"""원본 글리프로 ROM 픽셀 -> RAM 픽셀버퍼 변환 규칙을 역산한다.

RAM 값 = ROM 니블 * 0x10 이므로 값이 특이한 픽셀을 짝지어 대응을 찾는다.
추측하지 말고 실제 대응을 뽑아 규칙을 확정한다.
"""
import collections
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import font

RAM = 0x80000000
SLOT = 224


def main():
    ram = open(os.path.join(project.ROOT, 'work', 'poc_rdram.bin'), 'rb').read()
    pix, meta = struct.unpack('>II', ram[0x80085990 - RAM:0x80085990 - RAM + 8])
    rom = project.load_rom()
    gs, _ = font.parse_chain(rom)

    # 패치로 바꾸지 않은 글리프만 사용
    skip = {17, 18, 40}
    votes = collections.Counter()
    checked = 0
    for g in gs:
        if g.index in skip:
            continue
        m = ram[meta - RAM + g.index * 4: meta - RAM + g.index * 4 + 4]
        w1, h1 = m[0], m[1]
        if w1 != g.w + 1 or h1 != g.h + 1:
            continue
        stride = (w1 + 7) & ~7
        buf = ram[pix - RAM + g.index * SLOT: pix - RAM + g.index * SLOT + SLOT]
        rows = g.rows()
        checked += 1
        for y in range(g.h):
            for x in range(g.w):
                v = rows[y][x]
                if v == 0:
                    continue
                target = v * 0x10
                for by in range(min(SLOT // stride, 15)):
                    for bx in range(stride):
                        if buf[by * stride + bx] == target:
                            votes[(by - y, bx - x, y & 1, (bx ^ x))] += 1
    print('대조한 글리프 %d개' % checked)
    print('\n(dy, dx, y홀짝, bx^x) 상위 후보:')
    for k, n in votes.most_common(12):
        print('   dy=%+d dx=%+d yodd=%d bx^x=%d : %d표' % (k[0], k[1], k[2], k[3], n))

    # 가장 유력한 규칙을 뽑아 전수 검증
    print('\n규칙 후보 전수 검증:')
    for dy in (0, 1):
        for xor_even, xor_odd in ((0, 0), (0, 4), (4, 0), (0, 8), (8, 0)):
            ok = bad = 0
            for g in gs:
                if g.index in skip:
                    continue
                m = ram[meta - RAM + g.index * 4: meta - RAM + g.index * 4 + 4]
                w1, h1 = m[0], m[1]
                if w1 != g.w + 1:
                    continue
                stride = (w1 + 7) & ~7
                buf = ram[pix - RAM + g.index * SLOT: pix - RAM + g.index * SLOT + SLOT]
                rows = g.rows()
                for y in range(g.h):
                    by = y + dy
                    if by * stride >= SLOT:
                        break
                    xr = xor_odd if (by & 1) else xor_even
                    for x in range(g.w):
                        bx = x ^ xr
                        if bx >= stride:
                            continue
                        if buf[by * stride + bx] == rows[y][x] * 0x10:
                            ok += 1
                        else:
                            bad += 1
            if ok + bad:
                print('   dy=%d xor(even,odd)=(%d,%d) : 일치 %d / 불일치 %d  (%.1f%%)'
                      % (dy, xor_even, xor_odd, ok, bad, ok * 100.0 / (ok + bad)))


if __name__ == '__main__':
    main()
