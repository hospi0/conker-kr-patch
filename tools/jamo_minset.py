"""물마루 조합형 부품에서 최소 벌 집합(초성2 + 중성1 + 종성1 = 86)을 고르고,
그 집합만으로 음절을 조합해 원본과 얼마나 다른지 측정한다.

자형은 물마루(OFL) 픽셀을 그대로 쓴다. 직접 그리지 않는다.
"""
import collections
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

PATH = 'C:/claude/utils/font/Mulmaru/Mulmaru.pfp'
CHO_C = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
JUNG_C = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'
JONG_C = ' ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ'

# 중성 계열: 0=세로모음, 1=가로모음, 2=섞임
JUNG_GROUP = [0, 0, 0, 0, 0, 0, 0, 0,
              1, 2, 2, 2, 1, 1, 2, 2, 2, 1,
              1, 2, 0]


def load(path=PATH):
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    attr = d['attr']
    gs = {g['unicode']: g for g in d['glyphs'] if 'unicode' in g}
    return attr, gs


def grid(g, H, W):
    """부품·글리프를 (H,W) 격자에 놓는다.

    ★.pfp 의 data 는 **셀 하단 정렬**이다. 행 수가 셀보다 적은 부품(종성 등)을
      위 정렬로 놓으면 초성 자리에 찍혀 글자가 깨진다.
    """
    rows = g.get('data')
    a = np.zeros((H, W), dtype=np.uint8)
    if rows is None:
        return a
    top = H - len(rows)
    for y, r in enumerate(rows):
        yy = top + y
        if not (0 <= yy < H):
            continue
        for x, c in enumerate(r[:W]):
            if c != '.':
                a[yy, x] = 1
    return a


def build():
    attr, gs = load()
    H = attr['ascent'] + attr['descent']
    W = attr['maxWidth']

    parts = {cp: grid(g, H, W) for cp, g in gs.items()
             if 0xE000 <= cp <= 0xF8FF and 'data' in g}

    # 음절 -> (cho_part, jung_part, jong_part)
    triples = {}
    for cp, g in gs.items():
        if not (0xAC00 <= cp <= 0xD7A3):
            continue
        comps = g.get('components', [])
        idx = cp - 0xAC00
        c, j, k = idx // 588, (idx % 588) // 28, idx % 28
        if k and len(comps) == 3:
            triples[(c, j, k)] = tuple(comps)
        elif not k and len(comps) == 2:
            triples[(c, j, k)] = (comps[0], comps[1], None)

    # --- 최소 벌 선택 ---
    cho_pick = {}          # (cho, group2) -> part
    for c in range(19):
        for g2 in (0, 1):   # 0 = 세로모음, 1 = 가로/섞임
            cnt = collections.Counter()
            for (cc, j, k), t in triples.items():
                if cc != c:
                    continue
                grp = 0 if JUNG_GROUP[j] == 0 else 1
                if grp == g2:
                    cnt[t[0]] += 1
            if cnt:
                cho_pick[(c, g2)] = cnt.most_common(1)[0][0]

    jung_pick = {}
    for j in range(21):
        cnt = collections.Counter(t[1] for (c, jj, k), t in triples.items() if jj == j)
        if cnt:
            jung_pick[j] = cnt.most_common(1)[0][0]

    jong_pick = {}
    for k in range(1, 28):
        cnt = collections.Counter(t[2] for (c, j, kk), t in triples.items()
                                  if kk == k and t[2] is not None)
        if cnt:
            jong_pick[k] = cnt.most_common(1)[0][0]

    return attr, H, W, parts, triples, cho_pick, jung_pick, jong_pick


def compose(parts, cho_pick, jung_pick, jong_pick, H, W, c, j, k):
    a = np.zeros((H, W), dtype=np.uint8)
    g2 = 0 if JUNG_GROUP[j] == 0 else 1
    for p in (cho_pick.get((c, g2)), jung_pick.get(j), jong_pick.get(k) if k else None):
        if p is not None and p in parts:
            a |= parts[p]
    return a


def main():
    attr, H, W, parts, triples, cho_pick, jung_pick, jong_pick = build()
    n = len(set(cho_pick.values())) + len(set(jung_pick.values())) + len(set(jong_pick.values()))
    print('셀 %dx%d' % (W, H))
    print('선택된 부품: 초성 %d + 중성 %d + 종성 %d = %d개'
          % (len(set(cho_pick.values())), len(set(jung_pick.values())),
             len(set(jong_pick.values())), n))

    same = diff = 0
    for (c, j, k), t in triples.items():
        orig = np.zeros((H, W), dtype=np.uint8)
        for p in t:
            if p is not None and p in parts:
                orig |= parts[p]
        made = compose(parts, cho_pick, jung_pick, jong_pick, H, W, c, j, k)
        if np.array_equal(orig, made):
            same += 1
        else:
            diff += 1
    print('원본과 동일한 음절 %d / %d (%.1f%%)' % (same, same + diff, same * 100.0 / (same + diff)))

    out = os.path.join(project.ROOT, 'work', 'jamo_minset.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({'H': H, 'W': W,
               'cho': {'%d,%d' % k_: v for k_, v in cho_pick.items()},
               'jung': {str(k_): v for k_, v in jung_pick.items()},
               'jong': {str(k_): v for k_, v in jong_pick.items()}},
              open(out, 'w'))
    print('-> work/jamo_minset.json')


if __name__ == '__main__':
    main()
