"""갈무리 BDF 완성형 음절에서 조합형 자모를 역추출하고 벌수를 실측한다.

원칙: 자형을 직접 그리지 않는다. 기성 글꼴의 픽셀을 그대로 쓴다.
검증: 추출한 자모를 다시 OR 합성해 원본 음절과 **바이트 동일**해야 한다.
"""
import collections
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bdf

NCHO, NJUNG, NJONG = 19, 21, 28
CHO_C = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
JUNG_C = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'
JONG_C = ' ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ'

# 중성 계열: 0=세로(ㅏㅑㅓㅕㅣ...), 1=가로(ㅗㅛㅜㅠㅡ), 2=섞임(ㅘㅚㅝㅟㅢ...)
JUNG_GROUP = [0, 0, 0, 0, 0, 0, 0, 0,      # ㅏㅐㅑㅒㅓㅔㅕㅖ
              1, 2, 2, 2, 1, 1, 2, 2, 2, 1,  # ㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠ
              1, 2, 0]                     # ㅡㅢㅣ


def syl_cp(c, j, k):
    return 0xAC00 + (c * 21 + j) * 28 + k


def to_grid(g, W, H):
    """BDF 글리프를 (H,W) 0/1 배열로. 원점은 셀 좌상단."""
    a = np.zeros((H, W), dtype=np.uint8)
    if g is None:
        return a
    w, h, xo, yo = g.bbx
    bm = np.array(g.bitmap(), dtype=np.uint8) if h else np.zeros((0, 0), dtype=np.uint8)
    # BDF yoff 는 baseline 기준 하단. 여기서는 셀 상단 기준으로 옮긴다.
    top = (H - h) - (yo - 0)
    top = max(0, min(H - h, top))
    left = max(0, min(W - w, xo))
    if h and w:
        a[top:top + h, left:left + w] = bm
    return a


def main():
    path = sys.argv[1]
    f = bdf.BdfFont(path)
    print(os.path.basename(path))

    # 셀 크기: 음절 bbx 최대값
    W = H = 0
    for c in range(0xAC00, 0xD7A4):
        g = f.glyphs.get(c)
        if g:
            W = max(W, g.bbx[0] + max(0, g.bbx[2]))
            H = max(H, g.bbx[1])
    print('  셀 %dx%d' % (W, H))

    grid = {}
    for c in range(NCHO):
        for j in range(NJUNG):
            for k in range(NJONG):
                grid[(c, j, k)] = to_grid(f.glyphs.get(syl_cp(c, j, k)), W, H)

    # --- 종성이 순수 가산인가? (초성·중성이 줄어들지 않는가) ---
    lost_cases = 0
    for c in range(NCHO):
        for j in range(NJUNG):
            base = grid[(c, j, 0)]
            for k in range(1, NJONG):
                if np.any(base & ~grid[(c, j, k)]):
                    lost_cases += 1
    total = NCHO * NJUNG * (NJONG - 1)
    print('\n  종성 추가로 초성·중성이 바뀌는 경우: %d / %d (%.1f%%)'
          % (lost_cases, total, lost_cases * 100.0 / total))

    # --- 초성 벌수: (중성계열, 종성유무) 별로 초성 영역이 같은가 ---
    def cho_form(c, j, k):
        others = [grid[(c2, j, k)] for c2 in range(NCHO)]
        common = others[0].copy()
        for o in others[1:]:
            common &= o
        return grid[(c, j, k)] & ~common

    print('\n  === 초성 벌수 (분류 기준: 중성계열 x 종성유무) ===')
    cho_forms = collections.defaultdict(set)
    for c in range(NCHO):
        for j in range(NJUNG):
            for k in range(NJONG):
                cho_forms[c].add(cho_form(c, j, k).tobytes())
    dist = collections.Counter(len(v) for v in cho_forms.values())
    print('    초성별 서로 다른 모양 수 분포: %s' % dict(sorted(dist.items())))
    for c in range(NCHO):
        if len(cho_forms[c]) > 4:
            print('      %s : %d가지' % (CHO_C[c], len(cho_forms[c])))

    # 분류 규칙으로 묶으면 몇 벌인가
    cls = collections.defaultdict(set)
    for c in range(NCHO):
        for j in range(NJUNG):
            for k in range(NJONG):
                key = (JUNG_GROUP[j], 1 if k else 0)
                cls[(c, key)].add(cho_form(c, j, k).tobytes())
    bad = sum(1 for v in cls.values() if len(v) != 1)
    print('    (중성계열 x 종성유무) = 6분류로 묶었을 때 모양이 갈리는 칸: %d / %d'
          % (bad, len(cls)))


if __name__ == '__main__':
    main()
