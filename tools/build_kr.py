"""한글 폰트 전량 빌드: 자모 89 + 문장부호 6 = 95 글리프, charmap 재배정, 시험 문자열 삽입.

기하 (셀 12x12, 자간 1 -> 진행폭 13)
    초성      : w=12, xoff=+1   -> advance 13
    중성/종성 : w=12, xoff=-12  -> advance 0   (같은 칸에 겹침)
    yoff 는 부품의 잉크 상단 (물마루 부품은 셀 하단 정렬)

RLE 는 반드시 행 단위로 끊는다 (tools/font.py 참조).
"""
import collections
import glob
import io
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
import charmap as cmapmod
import jamo_minset as J
import jamo_optimize as O
import jamo_assign as A
import build_poc as B
import bubble


def _entry_meta(e):
    """직렬화된 글리프 엔트리 헤더 [w][h][xoff][yoff] 를 그대로 돌려준다.

    런타임 메타는 ProcessGlyph 가 [w+1][h+1][xoff][yoff] 로 저장한다.
    """
    return e[0], e[1], e[2], e[3]

CELL_W = 12
ADVANCE = 13                     # 셀 12 + 자간 1

# 유지할 비한글 (원본 글리프를 그대로 쓴다).
# ★숫자 0-9 를 반드시 남길 것. 게임에 폰트가 이것 하나뿐이라 슬롯을 자모로 덮으면
#   원문 대사의 숫자(`08:30 boat must arrive`, `u47`, `8mm` 등 26곳)는 물론
#   런타임에 찍히는 숫자까지 자모로 깨진다.
#   대신 자모 예산이 89 -> 79 로 준다 (정확일치 31.7% -> 25.9%, 평균오차 13.14 -> 14.11 px).
#   jamo_optimize2.BUDGET 과 반드시 맞출 것.
KEEP = [('.', 0x2E), (',', 0x2C), ('!', 0x21), ('?', 0x3F), ('-', 0x2D)] + \
       [(chr(0x30 + d), 0x30 + d) for d in range(10)]

# ★널 글리프: 폭 0 진행, 완전 투명.
#   번역문이 원본보다 짧을 때 남는 바이트를 이걸로 채운다.
#   advance = w + xoff = 1 + (-1) = 0 이라 줄 폭에 영향이 없다.
#   (뒤를 공백으로 채우면 렌더러가 버리지 않아 줄이 넓어지고 정렬이 밀린다.)
NULL_W, NULL_H, NULL_XOFF = 1, 1, -1

# ★charmap 은 건드리지 않는다.
#   전량 재배정하면 영문 코드가 미매핑이 되고, 렌더러가 없는 글리프의 메타를 읽어
#   RDP 에 쓰레기 치수를 넘긴다 -> 화면 전체가 깨진다 (2026-08-24 실기 확인).
#   자모는 **기존 코드를 그대로 물려받는다**. 영문은 자모로 보이지만 깨지지는 않는다.
#   단, 원본 charmap 의 중복(EA@81,83 / F4@89,91)만 고쳐 95칸을 모두 주소지정 가능하게 한다.
# ★★코드 0xA8 이상은 일반 글리프 경로가 아니다 (렌더러 0x802D09A0~):
#     코드 < 0xA1      -> 정상 글리프
#     0xA1 ~ 0xA7      -> 건너뜀
#     0xA8 ~ 0xFF      -> jal 0x850415e0 (특수 토큰 경로)
#   원본 charmap 의 악센트 코드 31개가 전부 0xA8 이상이라, 그 슬롯을 자모로 쓰면
#   특수 경로로 빠져 줄 폭이 부풀고 렌더가 어긋난다.
#   -> 0x80~0xA0 (비어 있고 0xA1 미만) 으로 옮긴다. 원래 코드는 영문에 안 쓰이므로 안전.
SAFE_HI = list(range(0x80, 0xA1))    # 33개

# --- 번역문 소스 ---
#
# ★★말풍선은 「지금 화면에 뜬 자막」이 아니라 **메시지에 속한 자막 전체의 최대 폭**으로
#   정해진다 (docs/bubble-width.md).  글리프 95칸을 자모로 덮었으므로, 한 자막이라도
#   영문으로 남기면 그 영문이 자모 글리프(문자당 advance 13)로 측정되어 말풍선이 부풀고
#   텍스트 원점이 화면 밖으로 계산된다.
#   -> **삽입 단위는 메시지다.** 자막 하나라도 문제가 있으면 그 메시지는 통째로 건너뛴다
#      (통째로 영문이면 원본 그대로라 최소한 깨지지는 않는다).
#
# 각 자막은 원문과 **같은 바이트 수**로 채운다 (rzip 블록을 키울 수 없으므로).
# 남는 자리는 널 글리프(advance 0)로 패딩한다.
# 번역 파일은 trans/ 와 trans/번역완/ 양쪽에서 읽는다.
# ko 가 빈 자막은 무시하므로 같은 파일이 양쪽에 있어도 안전하다.
TRANS_GLOBS = [os.path.join(project.ROOT, 'trans', '*.json'),
               os.path.join(project.ROOT, 'trans', '번역완', '*.json')]

# --- 비압축 도움말 (rzip 밖) ---
#
# ★코퍼스(rzip 블록)에 없는 텍스트 계통이다. ROM `0x3F82000~0x3F8C000` 에 5개국어 변형이
#   평문으로 나란히 있고, 그중 첫 블록이 영어판이다. 스페인어 패치도 이 블록을 번역했다
#   (`\nAhh ! Seems to be...` -> `\n  ah ! una simple...`) — 화면에 나온다는 뜻이다.
# 페이지 구분은 `0xBA 0xBD`, 블록 종료는 `0xBA`. 구분자와 아이콘(0xAF/0xA9)은 그대로 둔다.
# 각 페이지는 원문과 같은 바이트 수로 채운다 (영역을 키울 수 없다).
HELP_PAGES = [
    (0x3F88557, 41, '\n아 ! 설명서\n같은 거네.\n'),
    (0x3F88582, 49, '아, 그렇군. . .\n복잡한 조작\n설명이구나.\n'),
    (0x3F885B5, 57, '복잡한 구역을\n처음 쓸 때\n나타난다.\n'),
    (0x3F885F0, 47, '다시 보고 싶으면\n¯ 와 © 를\n누르면 된다.\n'),
    (0x3F88621, 28, '건너뛰려면\n© 누르기.\n'),
]


def load_trans():
    """코퍼스(자막 id·위치·예산) + 번역 파일의 ko 를 합친다."""
    import corpus
    strings = corpus.extract(verbose=False)
    corpus.add_budgets(strings)
    corpus.assign_ids(strings)          # ★순서가 아니라 대장에서 (corpus.assign_ids 주석 참조)
    msgs = corpus.group_messages(strings)
    ko = {}
    files = sorted(set(sum((glob.glob(g) for g in TRANS_GLOBS), [])))
    for p in files:
        doc = json.load(io.open(p, encoding='utf-8'))
        for m in doc['messages']:
            for s in m['subs']:
                if s.get('ko'):
                    ko[s['id']] = s['ko']
    return strings, msgs, ko, files


def load_selection():
    p = os.path.join(project.ROOT, 'work', 'jamo_optimized2.json')
    d = json.load(open(p))
    sel = {}
    for k, v in d['parts'].items():
        kind, i = k.split(',')
        sel[(kind, int(i))] = list(v)
    return sel


def build_parts():
    # ★배정은 음절 단위로 한다. 자모를 독립적으로 고르면 납작한 초성이
    #   키 큰 중성과 붙어 깨져 보인다(베). jamo_assign 참조.
    H, W, parts, triples, sel, choice = A.build(load_selection())
    flat = {p: parts[p].ravel() for p in parts}
    assign = choice

    used = []
    kind_of = {}
    for s in sorted(sel, key=lambda x: ({'cho': 0, 'jung': 1, 'jong': 2}[x[0]], x[1])):
        for p in sel[s]:
            if p not in kind_of:
                kind_of[p] = s[0]
                used.append(p)
    return H, W, parts, triples, sel, assign, used, kind_of, flat


def entry_for(bmp, kind):
    ys = np.nonzero(bmp.any(axis=1))[0]
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    sub = bmp[y0:y1, :CELL_W]
    h, w = sub.shape
    if w < CELL_W:
        sub = np.pad(sub, ((0, 0), (0, CELL_W - w)))
        w = CELL_W
    xoff = 1 if kind == 'cho' else -CELL_W
    px = [(15 if v else 0) for v in sub.ravel()]
    payload = fontmod.encode_rle(px, w, h)
    return (struct.pack('>BBBBI', w, h, xoff & 0xFF, y0,
                        fontmod.ENTRY_HEADER + len(payload)) + payload,
            (w, h, xoff, y0))


def encode_kr(text, part_code, assign, triples, null_code=None, pad_to=None):
    """한글 문자열 -> 게임 코드 바이트열.

    음절마다 물마루 원본이 쓰는 부품을 찾고, 선택집합에서 가장 가까운 벌로 치환한다.
    """
    out = bytearray()
    for ch in text:
        cp = ord(ch)
        if 0xAC00 <= cp <= 0xD7A3:
            idx = cp - 0xAC00
            c, j, k = idx // 588, (idx % 588) // 28, idx % 28
            combo = assign.get((c, j, k))
            if combo is None:
                raise ValueError('부품 조합이 없는 음절: %r' % ch)
            for p in combo:
                out.append(part_code[p])
        elif ch == '\n':
            out.append(0x0A)
        elif ch == ' ':
            out.append(0x20)
        elif 0xA1 <= cp <= 0xBF and cp not in (0xBD, 0xBF):
            # ★버튼 아이콘(`©`=0xA9 = B버튼)과 욕설 검열 기호는 글리프가 아니라
            #   디스패처가 그리는 토큰이다. 그대로 통과시킨다.
            #   0xBD(자막 분리자)·0xBF(블록 시작)는 자막 안에 있으면 안 되므로 막는다.
            out.append(cp)
        else:
            for c2, code in KEEP:
                if ch == c2:
                    out.append(code)
                    break
            else:
                raise ValueError('인코딩 불가 문자: %r' % ch)
    if pad_to is not None:
        if len(out) > pad_to:
            raise ValueError('인코딩 결과 %d B > 목표 %d B' % (len(out), pad_to))
        if len(out) < pad_to:
            if null_code is None:
                raise ValueError('널 글리프 코드가 없어 채울 수 없다')
            out.extend([null_code] * (pad_to - len(out)))
    return bytes(out)


def main():
    orig = project.load_rom()
    rom = bytearray(orig)
    plan = []

    H, W, parts, triples, sel, assign, used, kind_of, flat = build_parts()
    print('자모 부품 %d개 (초성 %d / 중성 %d / 종성 %d)'
          % (len(used),
             sum(1 for p in used if kind_of[p] == 'cho'),
             sum(1 for p in used if kind_of[p] == 'jung'),
             sum(1 for p in used if kind_of[p] == 'jong')))
    assert len(used) + len(KEEP) <= 95, '슬롯 초과: %d' % (len(used) + len(KEEP))

    # --- 글리프 체인 + charmap ---
    gs, _ = fontmod.parse_chain(orig)
    orig_by_code = {}
    tab = cmapmod.extract(orig)
    for i, code in enumerate(tab):
        orig_by_code[code] = gs[i]

    # ★★모든 코드를 0x80 미만(0x21~0x7F)으로 넣는다.
    #   프론트엔드(메뉴·타이틀) 렌더러는 0x80 이상을 토큰으로 취급해 버튼 아이콘을 그린다.
    #   자모를 0x80~0xA0 에 두면 그 화면에서 자모가 통째로 사라지고 P1/P2 아이콘이 튀어나온다.
    #   대소문자 접기를 없앴으므로(블록66 +0xC60) 0x21~0x7F 95개가 전부 구별된다 —
    #   필요한 수(95)와 정확히 같다.
    keep_codes = {code for _ch, code in KEEP}
    newtab = list(tab)
    keep_slots = {}                       # slot -> 원본 글리프 유지
    for ch, code in KEEP:
        keep_slots[tab.index(code)] = ch
    # ★★0x23('#')은 **프론트엔드 렌더러의 제어문자**다 — 다음 바이트까지 삼키고
    #   그 자리에 그래픽을 그린다. 여기에 자모를 배정하면 그 글자가 통째로 사라지고
    #   엉뚱한 그래픽이 뜬다(「진동팩 꽂기」의 `꽂` 초성이 0x23 이라 벙커 간판이 떴다).
    #   RAM 실측으로 확정: 블록엔 `... 20 23 57 79 ...`, 스크래치 복사본엔 `... 20 79 ...`.
    #   0x25('%')도 같은 계열이다 — printf 서식 문자라 다음 바이트를 먹고 문자열을 잇는다
    #   (의 =25 63 가 사라지고 다음 문장과 붙어버렸다).
    CTRL = {0x23, 0x25}
    pool = [c for c in range(0x21, 0x80) if c not in keep_codes and c not in CTRL]
    free = [i for i in range(95) if i not in keep_slots]
    # 실제로 쓰는 칸(자모 + 널)만 고유 코드가 필요하다. 남는 칸은 중복 코드여도 무해하다.
    assert len(pool) >= len(used) + 1, \
        '자유 코드 %d < 자모+널 %d' % (len(pool), len(used) + 1)
    for n, i in enumerate(free):
        # 코드가 하나 모자라면 마지막 한 칸은 **중복 코드**를 준다.
        # 룩업은 선형 스캔이라 먼저 나오는 슬롯이 이기므로 그 칸은 도달하지 않는다(무해).
        newtab[i] = pool[n] if n < len(pool) else pool[0]
    assert all(0x21 <= c < 0x80 for c in newtab), '0x80 이상 코드가 남았다'
    assert all(c not in CTRL for c in newtab), '제어문자 코드가 남았다'
    print('  charmap 전량 0x21~0x7F 재배정 (유지 %d칸, 제어문자 %s 제외, 고유 %d)'
          % (len(keep_slots), ' '.join('%02X' % c for c in sorted(CTRL)), len(set(newtab))))
    free_slots = [i for i in range(95) if i not in keep_slots]
    assert len(free_slots) >= len(used) + 1,         '자유 슬롯 %d < 자모 %d + 널 1' % (len(free_slots), len(used))

    entries = [None] * 95
    part_code = {}
    for n, p in enumerate(used):
        slot = free_slots[n]
        e, meta = entry_for(parts[p], kind_of[p])
        entries[slot] = e
        part_code[p] = newtab[slot]
    null_slot = free_slots[len(used)]
    null_payload = fontmod.encode_rle([0] * (NULL_W * NULL_H), NULL_W, NULL_H)
    entries[null_slot] = struct.pack('>BBBBI', NULL_W, NULL_H, NULL_XOFF & 0xFF, 0,
                                     fontmod.ENTRY_HEADER + len(null_payload)) + null_payload
    null_code = newtab[null_slot]
    for slot in range(95):
        if entries[slot] is None:
            g = gs[slot]
            entries[slot] = fontmod.serialize(g, fontmod.encode_rle(g.pixels(), g.w, g.h))
    print('  유지 슬롯 %s / 자모 %d개 / 널 글리프 슬롯 %d (코드 %02X)'
          % (sorted(keep_slots), len(used), null_slot, null_code))

    blob = b''.join(entries)
    # ★부팅 루프는 do-while 이라 마지막 글리프까지 돌려면 영역 길이에 여유가 필요하다.
    #   glyph94 처리 조건: (L - size94) + 15 < region_len
    #   glyph95 없이 종료 조건: L + 15 >= region_len
    #   => region_len = L + 15 이면 항상 성립한다.
    region_len = len(blob) + 15
    print('글리프 체인 %d B, 영역 %d B (한도 %d B)'
          % (len(blob), region_len, B.FONT_END_HARD - B.FONT_ROM))
    assert B.FONT_ROM + region_len <= B.FONT_END_HARD, '영역이 한도를 넘었다'
    B.simulate_boot_loop(blob, region_len)
    pad = (B.FONT_END_HARD - B.FONT_ROM) - len(blob)
    plan.append((B.FONT_ROM, orig[B.FONT_ROM:B.FONT_END_HARD], blob + b'\x00' * pad,
                 '글리프 체인 (%d B)' % len(blob)))

    # --- 블록 편집 버퍼 ---
    # ★같은 블록을 두 번 계획하면 안 된다. 코퍼스의 블록 507 이 곧 DATA_BLOCK(0x188328)
    #   이라, 그 블록의 UI 문자열을 따로 계획하면 charmap·서술자 패치를 덮어써 버린다.
    #   블록마다 raw 를 한 번만 열고 모든 편집을 모은 뒤 마지막에 한 번 재압축한다.
    blk_used = {}
    blk_raw = {}

    def get_raw(rom_off):
        if rom_off not in blk_raw:
            u, r = rzip.decode_at(orig, rom_off)
            blk_used[rom_off] = u
            blk_raw[rom_off] = bytearray(r)
        return blk_raw[rom_off]

    # --- 렌더러 패치 ---
    m66 = get_raw(B.RENDER_BLOCK)
    for off, exp, new in B.RENDER_PATCH_BYTES:
        assert m66[off:off + 1] == exp
        m66[off:off + 1] = new
    for off, expw, neww in B.RENDER_PATCH_WORDS:
        assert struct.unpack('>I', m66[off:off + 4])[0] == expw
        m66[off:off + 4] = struct.pack('>I', neww)

    # --- 블록 507: charmap + 서술자 end ---
    m507 = get_raw(B.DATA_BLOCK)
    m507[cmapmod.TABLE_OFFSET:cmapmod.TABLE_OFFSET + 95] = bytes(newtab)   # 중복 2칸만 수정
    m507[0x460:0x468] = struct.pack('>II', B.FONT_ROM, B.FONT_ROM + region_len)
    print('charmap 재배정 + 서술자 end -> %08X' % (B.FONT_ROM + region_len))

    # --- 대사 삽입 ---
    new_meta = [(w1 + 1, h1 + 1, xo & 0xFF, yo)
                for w1, h1, xo, yo in (_entry_meta(e) for e in entries)]
    m_new = bubble.Metrics(newtab, new_meta)

    strings, msgs, ko, tfiles = load_trans()
    print('번역 파일 %d개, 번역된 자막 %d개' % (len(tfiles), len(ko)))

    by_block = collections.defaultdict(list)
    skipped = []
    n_msg = n_sub = 0
    for msg in msgs:
        ids = [r['id'] for r in msg]
        if not any(i in ko for i in ids):
            continue
        if not all(i in ko for i in ids):
            # ★부분 번역은 말풍선을 부풀리므로 원칙적으로 건너뛴다.
            #   단 **표시용이 아닌 데이터 문자열**(치트 코드표 `VCBSEWCEBB...` 처럼
            #   소문자·공백이 없는 대문자 덩어리)은 화면에 안 나오므로 예외로 둔다.
            #   이걸 번역하면 치트 입력이 깨진다.
            rest = [r for r in msg if r['id'] not in ko]
            datalike = all(t.isupper() and ' ' not in t and len(t) >= 8
                           for t in (r['text'] for r in rest))
            if not datalike:
                skipped.append((msg[0]['msg'], '부분번역 (%d/%d)'
                                % (sum(1 for i in ids if i in ko), len(ids))))
                continue
            msg = [r for r in msg if r['id'] in ko]
        limit = msg[0]['msg_wmax']
        enc = []
        bad = None
        for r in msg:
            try:
                b = encode_kr(ko[r['id']], part_code, assign, triples)
            except ValueError as ex:
                bad = 'id %d: %s' % (r['id'], ex)
                break
            w = bubble.measure(b, m_new)[0]
            if w > limit:
                bad = 'id %d: 폭 %d > 한도 %d' % (r['id'], w, limit)
                break
            enc.append((r, b))
        if bad:
            skipped.append((msg[0]['msg'], bad))
            continue

        # ★바이트 예산은 **자막 단위가 아니라 메시지 단위**다.
        #   게임은 자막을 구분자(0x00/0xBD)를 세어 찾지 고정 오프셋으로 찾지 않는다
        #   (추출 함수 0x80380878). 따라서 메시지 안에서 경계를 옮겨도 된다 —
        #   짧은 자막이 남긴 자리를 긴 자막이 쓸 수 있다.
        #   자막마다 원문 길이에 맞춰 패딩하면 19.7%가 널 글리프로 버려진다.
        #   불변식: **구분자 바이트와 개수, 메시지 전체 span 을 그대로 유지**하고
        #   남는 자리는 마지막 자막 뒤에 널 글리프로 채운다.
        #   ★재분배는 **필요할 때만** 한다. 전부 개별 예산에 들어가면 기존 배치를 유지해
        #     이미 실기 검증한 빌드와 바이트가 달라지지 않게 한다.
        need = any(len(b) > r['bytes'] for r, b in enc)
        same_blk = len(set(r['rom'] for r in msg)) == 1
        contig = all(msg[i + 1]['off'] == msg[i]['off'] + msg[i]['bytes'] + 1
                     for i in range(len(msg) - 1))
        total = sum(r['bytes'] for r in msg)
        if need and same_blk and contig and sum(len(b) for _, b in enc) <= total:
            span_start = msg[0]['off']
            span_end = msg[-1]['off'] + msg[-1]['bytes']
            blkraw = get_raw(msg[0]['rom'])
            seps = [blkraw[msg[i]['off'] + msg[i]['bytes']] for i in range(len(msg) - 1)]
            buf = bytearray()
            for i, (r, b) in enumerate(enc):
                buf += b
                if i < len(enc) - 1:
                    buf.append(seps[i])
            buf += bytes([null_code]) * (span_end - span_start - len(buf))
            assert len(buf) == span_end - span_start
            by_block[msg[0]['rom']].append(
                (span_start, bytes(blkraw[span_start:span_end]), bytes(buf)))
            n_msg += 1
            n_sub += len(enc)
            continue

        for r, b in enc:
            if len(b) > r['bytes']:
                skipped.append((msg[0]['msg'], 'id %d: %d B > %d B (재분배 불가)'
                                % (r['id'], len(b), r['bytes'])))
                bad = True
                break
            b = b + bytes([null_code]) * (r['bytes'] - len(b))
            by_block[r['rom']].append((r['off'], r['text'].encode('latin-1'), b))
        if bad:
            continue
        n_msg += 1
        n_sub += len(enc)

    print('삽입: 메시지 %d개 / 자막 %d개, %d블록' % (n_msg, n_sub, len(by_block)))
    if skipped:
        print('건너뛴 메시지 %d개 (통째로 영문 유지):' % len(skipped))
        for mid, why in skipped[:20]:
            print('   msg %-5d %s' % (mid, why))
        if len(skipped) > 20:
            print('   ... 외 %d개' % (len(skipped) - 20))

    for rom_off in sorted(by_block):
        mT = get_raw(rom_off)
        for off, ob, kr in sorted(by_block[rom_off]):
            assert bytes(mT[off:off + len(ob)]) == ob, \
                '원문 불일치 블록 %08X +0x%X' % (rom_off, off)
            assert len(kr) == len(ob), '길이 불일치 블록 %08X +0x%X' % (rom_off, off)
            # ★남는 자리를 공백으로 채우면 안 된다. 렌더러가 뒤 공백을 버리지 않아
            #   줄 폭이 늘고 정렬이 밀린다. 널 글리프(advance 0)로 채운다.
            mT[off:off + len(ob)] = kr

    # --- 비압축 도움말 (rzip 밖이라 블록 편집 경로를 안 탄다) ---
    wo = wn = 0
    for off, n, ko in HELP_PAGES:
        ob = orig[off:off + n]
        kr = encode_kr(ko, part_code, assign, triples, null_code=null_code, pad_to=n)
        assert len(kr) == n
        wo = max(wo, bubble.measure(ob, bubble.Metrics.from_rom(orig))[0])
        wn = max(wn, bubble.measure(kr, m_new)[0])
        plan.append((off, ob, kr, '도움말'))
    if HELP_PAGES:
        print('비압축 도움말 %d페이지 (Wmax %d -> %d)' % (len(HELP_PAGES), wo, wn))
        assert wn <= wo, '도움말 폭 초과 (%d > %d)' % (wn, wo)

    # --- 편집한 블록을 한 번씩만 재압축 ---
    for rom_off in sorted(blk_raw):
        mT = blk_raw[rom_off]
        u = blk_used[rom_off]
        bT = rzip.deflate_raw(bytes(mT))
        assert len(bT) <= u - 4, \
            '블록 %08X 재압축이 원본보다 크다 (%d > %d)' % (rom_off, len(bT), u - 4)
        nb = struct.pack('>I', len(mT)) + bT
        nb += b'\x00' * (u - len(nb))
        what = []
        if rom_off == B.RENDER_BLOCK:
            what.append('렌더러')
        if rom_off == B.DATA_BLOCK:
            what.append('charmap+서술자')
        if rom_off in by_block:
            what.append('대사 %d' % len(by_block[rom_off]))
        plan.append((rom_off, orig[rom_off:rom_off + u], bytes(nb), ' + '.join(what)))

    # --- 적용 ---
    # ★모든 변경을 불변 원본 기준으로 계획·검증한 뒤 한 번에 적용한다.
    total = 0
    for addr, expect, new, desc in plan:
        assert orig[addr:addr + len(expect)] == expect, '기대 원본 불일치 @%08X' % addr
        assert len(new) == len(expect)
        rom[addr:addr + len(new)] = new
        total += len(new)
        if len(plan) <= 12 or addr in (B.FONT_ROM, B.RENDER_BLOCK, B.DATA_BLOCK):
            print('WRITE %08X %6d B  %s' % (addr, len(new), desc))
    if len(plan) > 12:
        print('WRITE ... 대사 블록 %d개 포함, 계획 %d건 / %d B'
              % (len(by_block), len(plan), total))

    out = os.path.join(project.ROOT, 'work', 'conker_kr.z64')
    open(out, 'wb').write(bytes(rom))
    print('-> work/conker_kr.z64')

    json.dump({'part_code': {str(k): v for k, v in part_code.items()},
               'charmap': newtab, 'null_code': null_code},
              open(os.path.join(project.ROOT, 'work', 'kr_codes.json'), 'w'))


if __name__ == '__main__':
    main()
