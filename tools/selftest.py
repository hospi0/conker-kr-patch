"""라운드트립·불변식 자체 검증.

원본이 없는 환경에서는 원본이 필요한 검사를 '실행하지 않음'으로 보고하고,
남은 검사는 계속 수행한다. 빠진 검사를 전체 통과로 표시하지 않는다.
"""
import os
import sys
import traceback
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import rzip
import font
import blocks

RESULTS = []


def check(name, fn):
    try:
        detail = fn()
        RESULTS.append(('PASS', name, detail or ''))
    except project.RomIdentityError as e:
        RESULTS.append(('SKIP', name, '원본 없음/불일치: %s' % str(e).splitlines()[0]))
    except Exception as e:
        RESULTS.append(('FAIL', name, '%s: %s' % (type(e).__name__, e)))
        if os.environ.get('CONKER_TRACE'):
            traceback.print_exc()


# ---------------------------------------------------------------- 원본 무관

def t_rle_roundtrip_synthetic():
    import random
    rnd = random.Random(1234)
    for _ in range(2000):
        n = rnd.randint(1, 200)
        px = [rnd.randint(0, 15) for _ in range(n)]
        if rnd.random() < 0.5:                      # 긴 런을 섞는다
            px = [px[0]] * rnd.randint(1, 40) + px
        enc = font.encode_rle(px, len(px), 1)
        dec = font.decode_rle(enc, len(px), 1)
        assert dec == px, 'RLE 왕복 실패'
    # 경계: 런 17 이상은 반드시 쪼개져야 한다
    px = [7] * 33
    enc = font.encode_rle(px, 33, 1)
    assert len(enc) == 3 and enc[0] == 0x7F, '런 16 상한이 지켜지지 않았다: %s' % enc.hex()
    assert font.decode_rle(enc, 33, 1) == px
    # 범위 밖 값은 실패해야 한다
    try:
        font.encode_rle([16], 1, 1)
        raise AssertionError('4비트 범위 초과를 실패시키지 않았다')
    except font.FontError:
        pass
    return '합성 2000건 + 경계'


def t_rzip_roundtrip_synthetic():
    import os as _os
    for raw in (b'', b'A', b'A' * 100000, _os.urandom(5000), bytes(range(256)) * 40):
        if len(raw) < rzip.MIN_RAW:
            continue
        blob = rzip.encode(raw)
        r = rzip.decode_at(blob, 0)
        assert r is not None, 'rzip 왕복 실패 (len=%d)' % len(raw)
        assert r[1] == raw and r[0] == len(blob)
    # 잘린 입력은 성공으로 흡수되면 안 된다
    blob = rzip.encode(b'X' * 1000)
    assert rzip.decode_at(blob[:len(blob) // 2], 0) is None, '잘린 입력을 성공 처리했다'
    return '합성 + 잘린 입력'


# ---------------------------------------------------------------- 원본 필요

def t_rom_identity():
    d = project.load_rom()
    return 'crc32=%s' % project.rom_identity(d)['crc32']


def t_font_chain():
    d = project.load_rom()
    gs, end = font.parse_chain(d)
    cfg = project.load_config()['font']
    assert len(gs) == cfg['glyph_count'], '글리프 수 %d != %d' % (len(gs), cfg['glyph_count'])
    assert end == project.cint(cfg['rom_end']), '체인 종료 %08X != %s' % (end, cfg['rom_end'])
    assert sum(g.size for g in gs) == cfg['bytes']
    return '%d글리프 / %dB, RLE 정합 전건' % (len(gs), cfg['bytes'])


def t_font_entry_roundtrip():
    """엔트리 직렬화가 원본 바이트와 동일해야 한다."""
    d = project.load_rom()
    gs, _ = font.parse_chain(d)
    for g in gs:
        orig = d[g.rom_off:g.rom_off + g.size]
        assert font.serialize(g) == orig, '엔트리 %d 직렬화 불일치' % g.index
    return '%d/%d 바이트 동일' % (len(gs), len(gs))


def t_font_rle_reencode():
    """원본 페이로드를 다시 인코딩했을 때 바이트가 같은지 측정한다.

    같지 않아도 결함은 아니다(여러 직렬화가 가능한 형식). 다만 재삽입에서
    '건드리지 않은 글리프는 원본 페이로드를 그대로 쓴다'는 규칙이 필요한지
    판정하는 근거가 되므로 수치를 남긴다.
    """
    d = project.load_rom()
    gs, _ = font.parse_chain(d)
    same = 0
    grew = 0
    for g in gs:
        re_ = font.encode_rle(g.pixels(), g.w, g.h)
        if re_ == g.payload:
            same += 1
        elif len(re_) > len(g.payload):
            grew += 1
    return '바이트 동일 %d/%d, 재인코딩이 커진 글리프 %d개' % (same, len(gs), grew)


def t_font_charmap():
    """매핑 테이블을 원본에서 추출하고 글리프 수·의미를 대조한다."""
    import charmap
    d = project.load_rom()
    tab = charmap.extract(d)
    gs, _ = font.parse_chain(d)
    assert len(tab) == len(gs), '테이블 %d != 글리프 %d' % (len(tab), len(gs))
    assert bytes(tab[:10]) == b'0123456789'
    assert bytes(tab[10:36]) == b'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    assert font.glyph_index('0', d) == 0
    assert font.glyph_index('A', d) == 10
    assert font.glyph_index('a', d) == 10        # 단일 케이스
    assert font.glyph_index('Z', d) == 35
    assert font.glyph_index('z', d) == 35
    assert font.glyph_index(0xC4, d) == 63       # Ä
    assert font.glyph_index('@', d) == 94
    assert font.glyph_index(' ', d) is None      # 공백은 글리프가 아니다
    dups, missing = charmap.unreachable_codes(tab)
    return '95엔트리, 중복 %s, 도달불가 %s' % (
        ' '.join('%02X' % c for c in dups) or '없음',
        ' '.join('%02X' % c for c in missing) or '없음')


def t_charmap_runtime_match():
    """세이브스테이트가 있으면 RAM 상주본과 원본 추출본이 같은지 대조한다."""
    p = os.path.join(project.ROOT, 'work', 'rdram.bin')
    if not os.path.exists(p):
        raise project.RomIdentityError('work/rdram.bin 없음 (tools/state.py 먼저)')
    import charmap
    ram = open(p, 'rb').read()
    off = charmap.RUNTIME_RAM - 0x80000000
    live = list(ram[off:off + charmap.TABLE_LEN])
    tab = charmap.extract(project.load_rom())
    assert live == tab, 'RAM 상주 테이블이 원본 추출본과 다르다'
    return 'RAM %08X 와 일치' % charmap.RUNTIME_RAM


def t_rzip_sample():
    d = project.load_rom()
    cfg = project.load_config()['rzip']
    lo = project.cint(cfg['scan_range']['start'])
    hi = min(lo + 0x40000, project.cint(cfg['scan_range']['end']))
    bs, _ = blocks.scan(d, lo, hi)
    assert bs, '표본 구간에서 rzip 블록을 찾지 못했다'
    for off, cs, rs in bs[:40]:
        assert rzip.roundtrip_ok(d, off), '블록 %08X 왕복 실패' % off
    # 연속성: off + comp == 다음 off (블록이 빈틈없이 붙어 있는 구간에서)
    contig = sum(1 for a, b in zip(bs, bs[1:]) if a[0] + a[1] == b[0])
    return '%d블록 표본, 왕복 40건, 연속쌍 %d/%d' % (len(bs), contig, max(len(bs) - 1, 1))


def t_zopfli_budget():
    """패치 대상 블록이 원본 압축 크기 안에 들어가는지 확인한다.

    zlib 은 블록 66 에서 무수정 재압축조차 원본보다 1 B 크다. zopfli 가 필요하다.
    """
    if not rzip.has_zopfli():
        raise project.RomIdentityError('zopfli 미설치 (pip install zopfli)')
    d = project.load_rom()
    out = []
    for blk in (0x6BDA2, 0x188328):
        r = rzip.decode_at(d, blk)
        assert r, '블록 %08X 해제 실패' % blk
        used, raw = r
        body = rzip.deflate_raw(raw)
        assert zlib.decompressobj(-15).decompress(body) == raw, '재압축 왕복 실패'
        room = (used - 4) - len(body)
        assert room >= 0, '블록 %08X 가 원본보다 %d B 크다' % (blk, -room)
        out.append('%08X %+d B' % (blk, room))
    return ' / '.join(out)


def main():
    check('RLE 왕복 (합성)', t_rle_roundtrip_synthetic)
    check('rzip 왕복 (합성)', t_rzip_roundtrip_synthetic)
    check('원본 식별', t_rom_identity)
    check('폰트 체인 파싱', t_font_chain)
    check('폰트 엔트리 직렬화 동일성', t_font_entry_roundtrip)
    check('폰트 RLE 재인코딩 측정', t_font_rle_reencode)
    check('문자 매핑 테이블 추출', t_font_charmap)
    check('매핑 테이블 런타임 대조', t_charmap_runtime_match)
    check('rzip 표본 왕복·연속성', t_rzip_sample)
    check('zopfli 압축 예산', t_zopfli_budget)

    w = max(len(n) for _s, n, _d in RESULTS)
    for s, n, d in RESULTS:
        print('[%s] %-*s  %s' % (s, w, n, d))
    n_fail = sum(1 for s, _, _ in RESULTS if s == 'FAIL')
    n_skip = sum(1 for s, _, _ in RESULTS if s == 'SKIP')
    print('\n통과 %d / 실패 %d / 미실행 %d'
          % (len(RESULTS) - n_fail - n_skip, n_fail, n_skip))
    return 1 if n_fail else 0


if __name__ == '__main__':
    sys.exit(main())
