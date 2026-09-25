"""문자 매핑 테이블: 글리프 인덱스 -> 문자코드 (ISO-8859-1).

저장 위치: rzip 블록 ROM 0x188328 의 압축 해제 데이터 +0x2E10
          95 바이트 + 0x00 종단
런타임   : RAM 0x80085930 에 그대로 상주

렌더러는 단일 케이스라 소문자 'a'-'z' 는 표에 없다. 대문자로 접은 뒤 조회한다.

테이블은 하드코딩하지 않고 선언한 원본에서 다시 추출한다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import rzip

BLOCK_ROM = 0x188328
TABLE_OFFSET = 0x2E10
TABLE_LEN = 95
RUNTIME_RAM = 0x80085930
META_PTR_RAM = 0x80085994          # -> [w+1][h+1][00][flag] * 95

# 원본 테이블이 실제로 이 바이트인지 확인하는 기준선 (다른 리비전이면 실패해야 한다)
EXPECTED_SHA1_PREFIX = None        # 필요해지면 고정한다


class CharmapError(Exception):
    pass


def extract(rom=None):
    """원본에서 매핑 테이블을 추출한다. [glyph_index] -> char_code."""
    data = project.load_rom() if rom is None else rom
    r = rzip.decode_at(data, BLOCK_ROM)
    if r is None:
        raise CharmapError('블록 %08X 를 rzip 으로 풀 수 없다' % BLOCK_ROM)
    _used, raw = r
    tab = raw[TABLE_OFFSET:TABLE_OFFSET + TABLE_LEN]
    if len(tab) != TABLE_LEN:
        raise CharmapError('테이블 길이 부족: %d' % len(tab))
    if raw[TABLE_OFFSET + TABLE_LEN] != 0x00:
        raise CharmapError('종단 0x00 이 없다 (offset %X)' % (TABLE_OFFSET + TABLE_LEN))
    if bytes(tab[:10]) != b'0123456789':
        raise CharmapError('테이블 시작이 예상과 다르다: %r' % tab[:10])
    return list(tab)


def build_maps(table):
    """(code -> index, index -> code). 중복 코드는 먼저 나온 인덱스를 쓴다."""
    code_to_index = {}
    for i, c in enumerate(table):
        code_to_index.setdefault(c, i)
    return code_to_index, dict(enumerate(table))


def fold(code):
    """렌더러의 단일 케이스 접기: 'a'-'z' -> 'A'-'Z'."""
    return code - 0x20 if 0x61 <= code <= 0x7A else code


def glyph_index(ch, code_to_index):
    code = ord(ch) if isinstance(ch, str) else ch
    return code_to_index.get(fold(code))


def unreachable_codes(table):
    """글리프가 중복 배정돼서 도달할 수 없게 된 Latin-1 코드들."""
    present = set(table)
    dups = [c for c in set(table) if table.count(c) > 1]
    # 쌍 구조상 있어야 할 소문자 짝
    pairs = {0xC4: 0xE4, 0xD6: 0xF6, 0xDC: 0xFC, 0xC0: 0xE0, 0xC2: 0xE2,
             0xC7: 0xE7, 0xC9: 0xE9, 0xC8: 0xE8, 0xCA: 0xEA, 0xCB: 0xEB,
             0xCE: 0xEE, 0xCF: 0xEF, 0xD4: 0xF4, 0xDB: 0xFB, 0xD9: 0xF9}
    missing = [lo for up, lo in pairs.items() if up in present and lo not in present]
    return sorted(dups), sorted(missing)


def main():
    tab = extract()
    c2i, i2c = build_maps(tab)
    print('테이블 %d엔트리 (rzip 블록 %08X +%X, 런타임 RAM %08X)'
          % (len(tab), BLOCK_ROM, TABLE_OFFSET, RUNTIME_RAM))
    print()
    for base in range(0, len(tab), 16):
        row = tab[base:base + 16]
        codes = ' '.join('%02X' % c for c in row)
        chars = ''.join(bytes([c]).decode('latin1') for c in row)
        print('  idx %-3d  %-47s  %s' % (base, codes, chars))

    dups, missing = unreachable_codes(tab)
    print()
    if dups:
        print('중복 배정된 코드: %s' % ' '.join('%02X' % c for c in dups))
        for d in dups:
            idxs = [i for i, c in enumerate(tab) if c == d]
            print('   %02X (%s) -> 글리프 %s' % (d, bytes([d]).decode('latin1'), idxs))
    if missing:
        print('도달 불가 Latin-1 소문자: %s'
              % ' '.join('%02X(%s)' % (c, bytes([c]).decode('latin1')) for c in missing))
    print()
    print('재활용 가능 슬롯(한글 등으로 덮어쓸 후보) = 악센트 블록 %d칸'
          % sum(1 for c in tab if c >= 0xC0))


if __name__ == '__main__':
    main()
