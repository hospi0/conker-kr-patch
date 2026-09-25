"""진단 빌드: 글리프 폭 한계와 RLE 행 배치를 한 번에 가른다.

넓은 폭이 되는지가 조합형 가능 여부를 결정한다.
  advance = w + xoff,  그리기 이동 = xoff  -> 겹치려면 세 조각 모두 w = 진행폭
  12px 셀이면 w = 13 이 필요한데 원본 최대 폭은 11 이다.

시험 도형 (전부 xoff=0 이라 나란히 그려진다)
  글리프 17('H') : w=13 h=6  속이 빈 사각 테두리   <- 폭 13 이 되는가
  글리프 18('I') : w=11 h=6  같은 도형             <- 폭 11 기준선
  글리프 40(',') : w=13 h=6  왼쪽 세로줄 + 위 가로줄  <- 행/열 배치 확인

첫 대사 "Hi, you've reached," 의 앞 세 글자로 세 도형이 나란히 보인다.
"""
import os
import struct
import sys
import zlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import rzip
import font as fontmod
import build_poc as B


def rect(w, h):
    a = np.zeros((h, w), dtype=np.uint8)
    a[0, :] = 1
    a[-1, :] = 1
    a[:, 0] = 1
    a[:, -1] = 1
    return a


def corner(w, h):
    a = np.zeros((h, w), dtype=np.uint8)
    a[0, :] = 1          # 위 가로줄
    a[:, 0] = 1          # 왼쪽 세로줄
    a[2, 2] = 1          # 안쪽 점 (열 위치 확인용)
    return a


SHAPES = {
    17: (rect(13, 6), 0, '테두리 w=13'),
    18: (rect(11, 6), 0, '테두리 w=11'),
    40: (corner(13, 6), 0, 'ㄱ자 w=13'),
}


def entry(bmp, xoff):
    h, w = bmp.shape
    px = [(15 if v else 0) for v in bmp.ravel()]
    payload = fontmod.encode_rle(px, w, h)
    return struct.pack('>BBBBI', w, h, xoff & 0xFF, 0,
                       fontmod.ENTRY_HEADER + len(payload)) + payload


def main():
    orig = project.load_rom()
    rom = bytearray(orig)
    plan = []

    # 렌더러 패치 (advance/그리기 부호화) — PoC 와 동일
    r = rzip.decode_at(orig, B.RENDER_BLOCK)
    used, raw = r
    m = bytearray(raw)
    for off, exp, new in B.RENDER_PATCH_BYTES:
        assert m[off:off + 1] == exp
        m[off:off + 1] = new
    for off, expw, neww in B.RENDER_PATCH_WORDS:
        assert struct.unpack('>I', m[off:off + 4])[0] == expw
        m[off:off + 4] = struct.pack('>I', neww)
    body = rzip.deflate_raw(bytes(m))
    assert len(body) <= used - 4
    nb = struct.pack('>I', len(m)) + body
    nb += b'\x00' * (used - len(nb))
    plan.append((B.RENDER_BLOCK, orig[B.RENDER_BLOCK:B.RENDER_BLOCK + used], bytes(nb),
                 '렌더러 xoff 부호화'))

    # 글리프 교체
    gs, _ = fontmod.parse_chain(orig)
    entries = []
    for g in gs:
        if g.index in SHAPES:
            bmp, xoff, desc = SHAPES[g.index]
            e = entry(bmp, xoff)
            h, w = bmp.shape
            stride = (w + 1 + 7) & ~7
            print('  글리프 %-3d <- %-12s w=%d h=%d stride=%d slot=%d/%d B (%d B)'
                  % (g.index, desc, w, h, stride, stride * (h + 1), B.PIX_SLOT, len(e)))
            entries.append(e)
        else:
            entries.append(fontmod.serialize(g, fontmod.encode_rle(g.pixels(), g.w, g.h)))
    blob = b''.join(entries)
    assert B.FONT_ROM + len(blob) <= B.FONT_END_HARD
    B.simulate_boot_loop(blob, len(blob))
    pad = (B.FONT_END_HARD - B.FONT_ROM) - len(blob)
    plan.append((B.FONT_ROM, orig[B.FONT_ROM:B.FONT_END_HARD], blob + b'\x00' * pad,
                 '글리프 체인 (%d B)' % len(blob)))

    # 서술자 end
    r507 = rzip.decode_at(orig, B.DATA_BLOCK)
    used507, raw507 = r507
    m507 = bytearray(raw507)
    m507[0x460:0x468] = struct.pack('>II', B.FONT_ROM, B.FONT_ROM + len(blob))
    body507 = rzip.deflate_raw(bytes(m507))
    assert len(body507) <= used507 - 4
    nb507 = struct.pack('>I', len(m507)) + body507
    nb507 += b'\x00' * (used507 - len(nb507))
    plan.append((B.DATA_BLOCK, orig[B.DATA_BLOCK:B.DATA_BLOCK + used507], bytes(nb507),
                 '서술자 end -> %08X' % (B.FONT_ROM + len(blob))))

    for addr, expect, new, desc in plan:
        assert orig[addr:addr + len(expect)] == expect
        assert len(new) == len(expect)
        rom[addr:addr + len(new)] = new
        print('WRITE %08X %d B  %s' % (addr, len(new), desc))

    out = os.path.join(project.ROOT, 'work', 'conker_probe.z64')
    open(out, 'wb').write(bytes(rom))
    print('-> work/conker_probe.z64')


if __name__ == '__main__':
    main()
