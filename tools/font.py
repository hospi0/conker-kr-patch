"""게임 폰트: 글리프 체인 파싱, RLE 픽셀 코덱, 문자코드 매핑.

엔트리 = [w][h][b2][flag][BE32 엔트리총크기] + RLE 픽셀
RLE    = 바이트마다 (명암4비트 << 4) | (런길이 - 1),  런길이 1..16
         런 합계는 반드시 w*h 와 같다.

게임 전체에 폰트는 이것 하나뿐이다 (ROM 전수 + 압축해제 27MB 전수 스캔으로 확인).
렌더러는 단일 케이스 — 소문자를 대문자 글리프로 찍는다 (실기 스크린샷 확인).
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

ENTRY_HEADER = 8
MAX_ENTRY = 0x400


class FontError(Exception):
    pass


# ---------------------------------------------------------------- 픽셀 코덱

def decode_rle(payload, w, h):
    """RLE 페이로드 -> 명암(0..15) 리스트. 픽셀 수가 w*h 와 다르면 실패."""
    px = []
    for b in payload:
        px.extend([b >> 4] * ((b & 0xF) + 1))
    if len(px) != w * h:
        raise FontError('RLE 픽셀 수 불일치: %d != %d (%dx%d)' % (len(px), w * h, w, h))
    return px


def encode_rle(px, w=None, h=None):
    """명암 리스트 -> RLE 페이로드.

    ★런이 행 경계를 넘으면 안 된다.
      디코더의 열 루프는 `while t1 < w+1` 로 행 끝에서 그냥 끊고,
      넘친 픽셀은 버려진 뒤 다음 행이 **그 다음 RLE 바이트**부터 시작한다.
      행을 넘나드는 런을 쓰면 둘째 행부터 전부 어긋난다.
      (원본 95글리프를 행 단위로 재인코딩하면 바이트까지 완전히 일치한다.)

    w 를 주지 않으면 한 행으로 간주한다.
    """
    if w is None:
        w = len(px)
        h = 1
    if h is None:
        h = len(px) // w if w else 0
    if w * h != len(px):
        raise FontError('픽셀 수 %d != w*h = %d' % (len(px), w * h))
    out = bytearray()
    for y in range(h):
        row = px[y * w:(y + 1) * w]
        i = 0
        while i < len(row):
            v = row[i]
            if not 0 <= v <= 15:
                raise FontError('명암 값이 4비트 범위를 벗어났다: %r' % (v,))
            run = 1
            while i + run < len(row) and row[i + run] == v and run < 16:
                run += 1
            out.append((v << 4) | (run - 1))
            i += run
    return bytes(out)


# ---------------------------------------------------------------- 체인

class Glyph:
    __slots__ = ('index', 'rom_off', 'w', 'h', 'b2', 'flag', 'size', 'payload')

    def __init__(self, index, rom_off, w, h, b2, flag, size, payload):
        self.index, self.rom_off = index, rom_off
        self.w, self.h, self.b2, self.flag = w, h, b2, flag
        self.size, self.payload = size, payload

    def pixels(self):
        return decode_rle(self.payload, self.w, self.h)

    def rows(self):
        px = self.pixels()
        return [px[y * self.w:(y + 1) * self.w] for y in range(self.h)]

    def __repr__(self):
        return '<Glyph %d @%06X %dx%d size=%d>' % (
            self.index, self.rom_off, self.w, self.h, self.size)


def parse_chain(data, start=None, end=None):
    cfg = project.load_config()['font']
    start = project.cint(cfg['rom_start']) if start is None else start
    end = project.cint(cfg['rom_end']) if end is None else end
    glyphs = []
    p = start
    while p + ENTRY_HEADER <= end:
        w, h, b2, flag = data[p], data[p + 1], data[p + 2], data[p + 3]
        size = struct.unpack('>I', data[p + 4:p + 8])[0]
        if not (0 < w <= 64 and 0 < h <= 64):
            break
        if not (ENTRY_HEADER < size <= MAX_ENTRY) or p + size > end + ENTRY_HEADER:
            break
        payload = data[p + ENTRY_HEADER:p + size]
        g = Glyph(len(glyphs), p, w, h, b2, flag, size, payload)
        g.pixels()          # RLE 정합성을 여기서 강제한다
        glyphs.append(g)
        p += size
    return glyphs, p


def serialize(glyph, payload=None):
    """글리프를 바이트로. payload 를 주면 크기를 다시 계산한다."""
    pl = glyph.payload if payload is None else payload
    size = ENTRY_HEADER + len(pl)
    if size > MAX_ENTRY:
        raise FontError('엔트리가 최대 크기를 넘었다: %d' % size)
    return struct.pack('>BBBBI', glyph.w, glyph.h, glyph.b2, glyph.flag, size) + pl


# ---------------------------------------------------------------- 문자 매핑
#
# 매핑은 코드 계산이 아니라 **데이터 테이블**이다.
#   저장 위치 : rzip 블록 ROM 0x188328 의 압축 해제 데이터 +0x2E10, 95바이트 + 0x00 종단
#   런타임    : RAM 0x80085930
# 테이블을 여기에 복사해 두지 않고 charmap.py 로 원본에서 다시 추출한다.

import charmap  # noqa: E402  (project 경로 삽입 뒤에 import)

_TABLE = None
_CODE_TO_INDEX = None


def _load(rom=None):
    global _TABLE, _CODE_TO_INDEX
    if _TABLE is None:
        _TABLE = charmap.extract(rom)
        _CODE_TO_INDEX, _ = charmap.build_maps(_TABLE)
    return _TABLE, _CODE_TO_INDEX


def char_table(rom=None):
    """[glyph_index] -> 문자코드."""
    return list(_load(rom)[0])


def glyph_index(ch, rom=None):
    """문자 -> 글리프 인덱스. 렌더러와 같이 단일 케이스로 접어서 조회한다."""
    _t, c2i = _load(rom)
    code = ord(ch) if isinstance(ch, str) else ch
    return c2i.get(charmap.fold(code))


def reusable_slots(rom=None):
    """한글 등으로 덮어쓸 후보 슬롯 [(glyph_index, 현재 문자코드)].

    악센트 블록(코드 >= 0xC0)과 '@' 를 후보로 본다. 본문 문자·문장부호는 제외.
    """
    t = char_table(rom)
    return [(i, c) for i, c in enumerate(t) if c >= 0xC0 or c == 0x40]


def load_glyphs(rom_path=None):
    return parse_chain(project.load_rom(rom_path))


if __name__ == '__main__':
    data = project.load_rom()
    gs, end = parse_chain(data)
    cfg = project.load_config()['font']
    print('글리프 %d개, 체인 종료 %08X (기대 %s)' % (len(gs), end, cfg['rom_end']))
    print('w 범위 %d..%d, h 범위 %d..%d'
          % (min(g.w for g in gs), max(g.w for g in gs),
             min(g.h for g in gs), max(g.h for g in gs)))
    print('총 바이트 %d' % sum(g.size for g in gs))
    slots = reusable_slots(data)
    print('재활용 후보 슬롯 %d개 (인덱스 %d..%d)'
          % (len(slots), slots[0][0], slots[-1][0]))
