"""89칸 예산 안에서 조합형 부품을 최적 배분한다.

인코더가 우리 코드이므로 벌 배정 규칙은 임의여도 된다((c,j,k) -> 부품 룩업).
따라서 「어느 부품을 몇 개 살릴 것인가」의 집합 선택 문제가 된다.

목표: 원본 물마루 음절과 **완전히 같은** 음절 수를 최대화.
방법: 자모마다 최빈 부품 1개로 시작(67개) 후, 예산까지 이득이 큰 부품을 탐욕적으로 추가.
"""
import collections
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import jamo_minset as J

BUDGET = 89          # 95칸 - 비한글 6칸 (. , ! ? ' -)


def build_triples():
    attr, gs = J.load()
    H = attr['ascent'] + attr['descent']
    W = attr['maxWidth']
    parts = {cp: J.grid(g, H, W) for cp, g in gs.items()
             if 0xE000 <= cp <= 0xF8FF and 'data' in g}
    triples = {}
    for cp, g in gs.items():
        if not (0xAC00 <= cp <= 0xD7A3):
            continue
        comps = g.get('components', [])
        idx = cp - 0xAC00
        c, j, k = idx // 588, (idx % 588) // 28, idx % 28
        if k and len(comps) == 3:
            triples[(c, j, k)] = (comps[0], comps[1], comps[2])
        elif not k and len(comps) == 2:
            triples[(c, j, k)] = (comps[0], comps[1], None)
    return attr, H, W, parts, triples


def build_refs():
    """모든 음절의 기준 비트맵.

    ★물마루에는 부품 조합 없이 **직접 그린 통글자**가 22자 있다
      (래 럐 레 례 뫼 믜 뵈 븨 삐 쏴 쐬 씌 씨 외 의 제 졔 쫘 쬐 쯰 찌 피).
      `build_triples` 는 `len(components)` 가 2/3 이 아닌 것을 버리므로 이들이 통째로 빠졌고,
      그 결과 「의」「래」「씨」 같은 필수 음절이 인코딩 불가였다.
      여기서는 통글자의 `data` 를 기준 비트맵으로 삼아 배정 대상에 포함시킨다.
      부품 선택집합(89칸)은 건드리지 않으므로 폰트는 바뀌지 않는다.
    """
    attr, gs = J.load()
    H = attr['ascent'] + attr['descent']
    W = attr['maxWidth']
    parts = {cp: J.grid(g, H, W) for cp, g in gs.items()
             if 0xE000 <= cp <= 0xF8FF and 'data' in g}
    triples = {}
    refs = {}
    whole = []
    for cp, g in gs.items():
        if not (0xAC00 <= cp <= 0xD7A3):
            continue
        idx = cp - 0xAC00
        c, j, k = idx // 588, (idx % 588) // 28, idx % 28
        comps = g.get('components', [])
        t = None
        if k and len(comps) == 3:
            t = (comps[0], comps[1], comps[2])
        elif not k and len(comps) == 2:
            t = (comps[0], comps[1], None)
        if t is not None:
            triples[(c, j, k)] = t
            r = np.zeros_like(parts[t[0]])
            for p in t:
                if p is not None:
                    r |= parts[p]
            refs[(c, j, k)] = r
        elif 'data' in g:
            refs[(c, j, k)] = J.grid(g, H, W)
            whole.append(chr(cp))
    return attr, H, W, parts, triples, refs, whole


def optimize(triples, budget=BUDGET, verbose=True):
    # 슬롯 = ('cho', c) / ('jung', j) / ('jong', k)
    cand = collections.defaultdict(collections.Counter)
    for (c, j, k), (pc, pj, pk) in triples.items():
        cand[('cho', c)][pc] += 1
        cand[('jung', j)][pj] += 1
        if pk is not None:
            cand[('jong', k)][pk] += 1

    sel = {s: {cnt.most_common(1)[0][0]} for s, cnt in cand.items()}
    used = sum(len(v) for v in sel.values())
    if verbose:
        print('자모 슬롯 %d개, 최빈 1벌로 시작 -> 부품 %d개' % (len(sel), used))

    def exact_count(sel):
        n = 0
        for (c, j, k), (pc, pj, pk) in triples.items():
            if pc not in sel[('cho', c)]:
                continue
            if pj not in sel[('jung', j)]:
                continue
            if k and pk not in sel[('jong', k)]:
                continue
            n += 1
        return n

    base = exact_count(sel)
    if verbose:
        print('  시작 정확 일치 %d / %d (%.1f%%)'
              % (base, len(triples), base * 100.0 / len(triples)))

    while used < budget:
        best = None
        for slot, cnt in cand.items():
            for p in cnt:
                if p in sel[slot]:
                    continue
                sel[slot].add(p)
                g = exact_count(sel)
                sel[slot].remove(p)
                if best is None or g > best[0]:
                    best = (g, slot, p)
        if best is None or best[0] <= base:
            break
        base, slot, p = best
        sel[slot].add(p)
        used += 1
        if verbose:
            kind, i = slot
            name = {'cho': J.CHO_C, 'jung': J.JUNG_C, 'jong': J.JONG_C}[kind]
            print('  +%-4s %s  -> 부품 %d개, 정확 일치 %d (%.1f%%)'
                  % (kind, name[i] if i < len(name) else '?', used, base,
                     base * 100.0 / len(triples)))
    return sel, base


def main():
    attr, H, W, parts, triples = build_triples()
    sel, exact = optimize(triples)
    total = sum(len(v) for v in sel.values())
    print('\n최종: 부품 %d개 / 예산 %d, 정확 일치 %d / %d (%.1f%%)'
          % (total, BUDGET, exact, len(triples), exact * 100.0 / len(triples)))

    out = {'H': H, 'W': W, 'budget': BUDGET, 'total_parts': total,
           'exact': exact, 'syllables': len(triples),
           'sel': {'%s,%d' % s: sorted(v) for s, v in sel.items()}}
    p = os.path.join(project.ROOT, 'work', 'jamo_optimized.json')
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(out, open(p, 'w'))
    print('-> work/jamo_optimized.json')


if __name__ == '__main__':
    main()
