"""PoC 빌드: 조합형 겹쳐 그리기가 실기에서 되는지 증명한다.

증명 대상
  1) 렌더러 `lbu`->`lb` 2바이트 패치로 xoff 가 부호 있는 값이 되는가
  2) xoff 음수로 advance 0 을 만들어 초성·중성·종성을 한 칸에 겹칠 수 있는가
  3) 글리프 교체와 블록 재압축이 원본 크기 안에 들어가는가

방법
  글리프 17('H'), 18('I'/'i'), 40(',') 을 초성ㅎ / 중성ㅏ / 종성ㄴ 으로 교체.
  게임 첫 대사가 "Hi, you've reached," 이므로 화면에 「한」 이 떠야 한다.
  charmap 은 건드리지 않는다 (변경 최소화).

Expected Write 규칙: 모든 변경을 불변 원본 기준으로 계획·검증한 뒤 한 번에 적용한다.
"""
import json
import os
import struct
import sys
import zlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import rzip
import font as fontmod
import jamo_minset as J
import jamo_optimize as O

RENDER_BLOCK = 0x6BDA2
# 블록 66 로드베이스 = 0x802D0000
#   +0x210  draw   : lbu $t9,2($a0)  -> lb   (xoff 부호화)
#   +0x21C  draw   : bgez $t9, +4    -> b +4 (unsigned->float 보정 건너뛰기)
#           ★ +0x210 만 바꾸면 음수 xoff 에 2^32 가 더해져 글리프가 화면 밖으로 간다.
#             0x4F800000(2^32) 을 더하는 보정은 lbu 전제이므로 함께 무력화해야 한다.
#   +0xB2C  layout : lbu $t5,2($v0)  -> lb   (advance = w + xoff)
#   +0xC60  룩업   : addiu $v0,$a0,-0x20 -> addiu $v0,$a0,0   (소문자→대문자 접기 제거)
#           ★접기를 없애야 코드 0x21~0x7F 95개가 전부 구별된다.
#             그래야 **모든 자모 코드를 0x80 미만**으로 넣을 수 있다.
#             프론트엔드(메뉴·타이틀) 렌더러는 0x80 이상을 토큰으로 보기 때문에,
#             자모를 0x80~0xA0 에 두면 그 화면에서 P1/P2 버튼 아이콘이 튀어나오고
#             글자가 통째로 빠진다 (「진동팩 꽂기」-> 「진돟기」). 대사 렌더러만 0xA1 기준이다.
RENDER_PATCH_BYTES = [(0x210, b'\x90', b'\x80'), (0xB2C, b'\x90', b'\x80')]
RENDER_PATCH_WORDS = [(0x21C, 0x07210004, 0x10000004),   # bgez $t9 -> b
                      (0xC60, 0x2482FFE0, 0x24820000)]   # 대소문자 접기 제거
DATA_BLOCK = 0x188328            # 폰트 서술자 +0x460, charmap +0x2E10
FONT_ROM = 0x40F10
FONT_END_HARD = 0x42450          # 이 뒤는 재배치/포인터 테이블. 넘으면 안 된다.
PIX_SLOT = 224                   # 글리프당 픽셀 버퍼 슬롯


def simulate_boot_loop(blob, region_len):
    """부팅 루프를 그대로 재현해 종료·글리프 수·슬롯 초과를 검증한다.

        ptr = 0 ; idx = 0
        do { ProcessGlyph ; ptr += BE32(ptr+4) ; idx++ }
        while (ptr + 0xF) < region_len
    """
    ptr = 0
    idx = 0
    seen = []
    while True:
        assert ptr + 8 <= len(blob), '엔트리 헤더가 영역을 넘는다 (ptr=%d)' % ptr
        w, h = blob[ptr], blob[ptr + 1]
        size = struct.unpack('>I', blob[ptr + 4:ptr + 8])[0]
        assert size > 8, '엔트리 크기 %d — 무한루프 위험 (idx=%d, ptr=%d)' % (size, idx, ptr)
        assert w and h, 'w/h 가 0 (idx=%d, ptr=%d)' % (idx, ptr)
        stride = (w + 1 + 7) & ~7
        assert stride * h <= PIX_SLOT, \
            '픽셀 슬롯 초과: idx=%d w=%d h=%d stride=%d -> %d B > %d' % (
                idx, w, h, stride, stride * h, PIX_SLOT)
        seen.append((idx, w, h, size))
        ptr += size
        idx += 1
        if not ((ptr + 0xF) < region_len):
            break
    assert ptr == len(blob), \
        '루프 종료 위치 %d != 체인 길이 %d (중간에 멈췄거나 넘어갔다)' % (ptr, len(blob))
    print('부팅 루프 시뮬레이션: 글리프 %d개 처리 후 정상 종료 (ptr=%d, len=%d)'
          % (idx, ptr, region_len))
    return idx

# 교체 대상: (글리프 인덱스, 자모 종류, 자모 인덱스, xoff, 설명)
#   초성 : 셀 폭 12 + 자간 1 -> advance 13  => w=12, xoff=1
#   중성/종성 : advance 0    => xoff = -w
TARGETS = [
    (17, 'cho', 18, '초성 ㅎ'),      # 'H'
    (18, 'jung', 0, '중성 ㅏ'),      # 'I' (소문자 i 도 여기로 접힘)
    (40, 'jong', 4, '종성 ㄴ'),      # ','
]


def jamo_bitmaps():
    """물마루 부품에서 PoC 용 자모 3개를 뽑는다 (셀 12x12, 하단 정렬)."""
    attr, H, W, parts, triples = O.build_triples()
    sel = {}
    import collections
    cand = collections.defaultdict(collections.Counter)
    for (c, j, k), (pc, pj, pk) in triples.items():
        cand[('cho', c)][pc] += 1
        cand[('jung', j)][pj] += 1
        if pk is not None:
            cand[('jong', k)][pk] += 1
    out = {}
    for gi, kind, idx, desc in TARGETS:
        cp = cand[(kind, idx)].most_common(1)[0][0]
        out[gi] = (parts[cp], desc)
    return H, W, out


def to_glyph_entry(bmp, xoff_signed, orig_flag=0):
    """12x12 0/1 비트맵 -> Conker 글리프 엔트리 (잉크 박스로 자르고 RLE)."""
    ys, xs = np.nonzero(bmp)
    if len(ys) == 0:
        raise ValueError('빈 비트맵')
    # 가로는 자르지 않는다: advance 계산이 w 에 걸리므로 셀 폭을 유지한다
    y0, y1 = ys.min(), ys.max() + 1
    sub = bmp[y0:y1, :]
    h, w = sub.shape
    px = [(15 if v else 0) for v in sub.ravel()]
    payload = fontmod.encode_rle(px, w, h)
    size = fontmod.ENTRY_HEADER + len(payload)
    xb = xoff_signed & 0xFF
    return struct.pack('>BBBBI', w, h, xb, int(y0), size) + payload, (w, h, xoff_signed, int(y0))


def main():
    rom = bytearray(project.load_rom())
    orig = bytes(rom)
    plan = []

    # ---- 1) 렌더러 패치 ----
    r = rzip.decode_at(orig, RENDER_BLOCK)
    assert r, '렌더러 블록 해제 실패'
    used, raw = r
    m = bytearray(raw)
    for off, exp, new in RENDER_PATCH_BYTES:
        assert m[off:off + 1] == exp, ('블록 %08X +%X 기대 %s, 실제 %s'
                                       % (RENDER_BLOCK, off, exp.hex(), m[off:off + 1].hex()))
        m[off:off + 1] = new
    for off, expw, neww in RENDER_PATCH_WORDS:
        cur = struct.unpack('>I', m[off:off + 4])[0]
        assert cur == expw, ('블록 %08X +%X 기대 %08X, 실제 %08X'
                             % (RENDER_BLOCK, off, expw, cur))
        m[off:off + 4] = struct.pack('>I', neww)
    body = rzip.deflate_raw(bytes(m))
    assert zlib.decompressobj(-15).decompress(body) == bytes(m)
    assert len(body) <= used - 4, '렌더러 블록이 원본보다 크다 (%d > %d)' % (len(body), used - 4)
    newblk = struct.pack('>I', len(m)) + body
    newblk += b'\x00' * ((used) - len(newblk))          # 남는 공간은 0으로
    plan.append((RENDER_BLOCK, orig[RENDER_BLOCK:RENDER_BLOCK + used], bytes(newblk),
                 '렌더러 xoff 부호화 3곳 (재압축 %d/%d B)' % (len(body), used - 4)))

    # ---- 2) 글리프 교체 ----
    H, W, jam = jamo_bitmaps()
    gs, end = fontmod.parse_chain(orig)
    entries = []
    info = []
    for g in gs:
        if g.index in jam:
            bmp, desc = jam[g.index]
            xoff = 1 if g.index == 17 else -W          # 초성만 +1, 나머지 advance 0
            e, meta = to_glyph_entry(bmp, xoff)
            entries.append(e)
            info.append('  글리프 %-3d <- %s  w=%d h=%d xoff=%d yoff=%d  (%d B)'
                        % (g.index, desc, meta[0], meta[1], meta[2], meta[3], len(e)))
        else:
            # 손대지 않는 글리프는 탐욕 재인코딩으로 공간을 번다
            pl = fontmod.encode_rle(g.pixels(), g.w, g.h)
            entries.append(fontmod.serialize(g, pl))
    blob = b''.join(entries)
    print('폰트 체인: 원본 %d B -> 신규 %d B  (한도 %d B)'
          % (sum(g.size for g in gs), len(blob), FONT_END_HARD - FONT_ROM))
    for s in info:
        print(s)
    assert FONT_ROM + len(blob) <= FONT_END_HARD, \
        '폰트가 %d B 초과 (재배치 필요)' % (FONT_ROM + len(blob) - FONT_END_HARD)
    pad = (FONT_END_HARD - FONT_ROM) - len(blob)
    plan.append((FONT_ROM, orig[FONT_ROM:FONT_END_HARD], blob + b'\x00' * pad,
                 '글리프 체인 교체 (뒤 %d B 는 0 패딩)' % pad))

    # ---- 2b) 서술자 end 를 새 체인 길이에 맞춘다 ----
    #
    # ★부팅 루프 종료 조건: (ptr + 0xF) < buf + (end - start)
    #   체인이 짧아졌는데 end 를 그대로 두면 루프가 0 패딩을 글리프로 읽고
    #   size=0 이 되어 ptr 이 전진하지 않는다 -> 무한루프 -> 부팅 불가.
    new_len = len(blob) + 15   # do-while 여유
    desc_off = 0x460
    r507 = rzip.decode_at(orig, DATA_BLOCK)
    assert r507, '데이터 블록 해제 실패'
    used507, raw507 = r507
    cur_s, cur_e = struct.unpack('>II', raw507[desc_off:desc_off + 8])
    assert (cur_s, cur_e) == (FONT_ROM, FONT_END_HARD), \
        '서술자 기대값 불일치: %08X %08X' % (cur_s, cur_e)
    new_e = FONT_ROM + new_len
    m507 = bytearray(raw507)
    m507[desc_off:desc_off + 8] = struct.pack('>II', FONT_ROM, new_e)
    body507 = rzip.deflate_raw(bytes(m507))
    assert zlib.decompressobj(-15).decompress(body507) == bytes(m507)
    assert len(body507) <= used507 - 4, '데이터 블록이 원본보다 크다'
    nb507 = struct.pack('>I', len(m507)) + body507
    nb507 += b'\x00' * (used507 - len(nb507))
    plan.append((DATA_BLOCK, orig[DATA_BLOCK:DATA_BLOCK + used507], bytes(nb507),
                 '서술자 end %08X -> %08X (재압축 %d/%d B)'
                 % (cur_e, new_e, len(body507), used507 - 4)))

    # ---- 2c) 부팅 루프 시뮬레이션 ----
    simulate_boot_loop(blob, new_len)

    # ---- 3) 적용 ----
    for addr, expect, new, desc in plan:
        assert orig[addr:addr + len(expect)] == expect, '기대 원본 불일치 @%08X' % addr
        assert len(new) == len(expect), '길이 변경 금지 @%08X' % addr
        rom[addr:addr + len(new)] = new
        print('WRITE %08X  %d B  %s' % (addr, len(new), desc))

    out = os.path.join(project.ROOT, 'work', 'conker_poc.z64')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'wb').write(bytes(rom))
    print('\n-> work/conker_poc.z64  (CRC 재계산 전)')

    # 최종 diff 감사
    diff = [i for i in range(len(orig)) if orig[i] != rom[i]]
    covered = set()
    for addr, expect, new, _d in plan:
        covered |= set(range(addr, addr + len(new)))
    stray = [i for i in diff if i not in covered]
    print('최종 diff %d B, 계획 밖 변경 %d B' % (len(diff), len(stray)))
    assert not stray, '계획에 없는 변경이 있다'


if __name__ == '__main__':
    main()
