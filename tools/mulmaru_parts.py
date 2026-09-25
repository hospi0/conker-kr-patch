"""물마루 .pfp 의 조합형 부품(PUA 글리프)을 분석한다.

음절 글리프는 {"unicode": .., "components": [PUA...]} 로 부품을 참조한다.
실제 비트맵을 가진 PUA 글리프가 곧 자모 벌 조각이다.
"""
import collections
import json
import sys

import numpy as np

PATH = 'C:/claude/utils/font/Mulmaru/Mulmaru.pfp'
CHO_C = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
JUNG_C = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'
JONG_C = ' ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ'


def load(path=PATH):
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    return d['attr'], {g['unicode']: g for g in d['glyphs'] if 'unicode' in g}


def grid(g):
    rows = g.get('data')
    if rows is None:
        return None
    h = len(rows)
    w = max((len(r) for r in rows), default=0)
    a = np.zeros((h, w), dtype=np.uint8)
    for y, r in enumerate(rows):
        for x, c in enumerate(r):
            if c != '.':
                a[y, x] = 1
    return a


def main():
    attr, gs = load()
    print('물마루  ascent=%d descent=%d maxWidth=%d letterSpacing=%d'
          % (attr['ascent'], attr['descent'], attr['maxWidth'], attr['letterSpacing']))

    pua = {cp: g for cp, g in gs.items() if 0xE000 <= cp <= 0xF8FF}
    pua_data = {cp: g for cp, g in pua.items() if 'data' in g}
    print('PUA 글리프 %d개, 그중 비트맵 보유 %d개' % (len(pua), len(pua_data)))

    # 음절 -> 부품
    syls = {cp: g for cp, g in gs.items() if 0xAC00 <= cp <= 0xD7A3}
    ncomp = collections.Counter(len(g.get('components', [])) for g in syls.values())
    print('음절 %d개, 부품 개수 분포 %s' % (len(syls), dict(sorted(ncomp.items()))))

    used = collections.Counter()
    for g in syls.values():
        for c in g.get('components', []):
            used[c] += 1
    print('음절이 실제로 쓰는 서로 다른 부품: %d개' % len(used))
    print('  PUA 범위: %04X .. %04X' % (min(used), max(used)))

    # 부품을 자리(초/중/종)별로 분류: 음절의 몇 번째 부품으로 쓰이는가
    slot = collections.defaultdict(set)
    for cp, g in syls.items():
        comps = g.get('components', [])
        idx = cp - 0xAC00
        k = idx % 28
        for pos, c in enumerate(comps):
            slot[c].add(pos)
    pos_count = collections.Counter(tuple(sorted(v)) for v in slot.values())
    print('  부품이 나타나는 위치 분포: %s' % {str(k): v for k, v in pos_count.items()})

    # 초/중/종 별 부품 수 (음절 인덱스로 판정)
    cho_parts = collections.defaultdict(set)
    jung_parts = collections.defaultdict(set)
    jong_parts = collections.defaultdict(set)
    for cp, g in syls.items():
        comps = g.get('components', [])
        idx = cp - 0xAC00
        c, j, k = idx // 588, (idx % 588) // 28, idx % 28
        if k:
            if len(comps) >= 3:
                cho_parts[c].add(comps[0]); jung_parts[j].add(comps[1]); jong_parts[k].add(comps[2])
        else:
            if len(comps) >= 2:
                cho_parts[c].add(comps[0]); jung_parts[j].add(comps[1])

    for label, parts, names in (('초성', cho_parts, CHO_C), ('중성', jung_parts, JUNG_C),
                                ('종성', jong_parts, JONG_C)):
        tot = len(set().union(*parts.values())) if parts else 0
        dist = collections.Counter(len(v) for v in parts.values())
        print('\n%s: 총 부품 %d개, 자모당 벌수 분포 %s' % (label, tot, dict(sorted(dist.items()))))
        for i in sorted(parts):
            nm = names[i] if i < len(names) else '?'
            print('   %s %d벌' % (nm, len(parts[i])), end='   ')
        print()

    total = sum(len(set().union(*p.values())) for p in (cho_parts, jung_parts, jong_parts) if p)
    print('\n=> 조합형 부품 총합 %d개' % total)


if __name__ == '__main__':
    main()
