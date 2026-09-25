"""초성 2벌의 분할 축을 비교한다: 「중성 계열」 vs 「종성 유무」.

관측: 종성용 납작한 초성이 종성 없는 음절(베)에 붙어 눈에 띄게 깨졌다.
초성 높이는 종성 유무에 크게 좌우되므로 그쪽이 더 중요한 축일 수 있다.
"""
import collections
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import jamo_minset as J
import jamo_optimize as O

BUDGET = 89


def seed(triples, axis):
    """axis: 'jung' = 중성계열(세로/가로섞임) , 'jong' = 종성유무"""
    sel = collections.defaultdict(set)
    for c in range(19):
        for g2 in (0, 1):
            cnt = collections.Counter()
            for (cc, j, k), t in triples.items():
                if cc != c:
                    continue
                key = (0 if J.JUNG_GROUP[j] == 0 else 1) if axis == 'jung' else (1 if k else 0)
                if key == g2:
                    cnt[t[0]] += 1
            if cnt:
                sel[('cho', c)].add(cnt.most_common(1)[0][0])
    for j in range(21):
        cnt = collections.Counter(t[1] for (c, jj, k), t in triples.items() if jj == j)
        if cnt:
            sel[('jung', j)].add(cnt.most_common(1)[0][0])
    for k in range(1, 28):
        cnt = collections.Counter(t[2] for (c, j, kk), t in triples.items()
                                  if kk == k and t[2] is not None)
        if cnt:
            sel[('jong', k)].add(cnt.most_common(1)[0][0])
    return sel


def evaluate(sel, triples, parts, flat):
    exact = err = 0
    for (c, j, k), (pc, pj, pk) in triples.items():
        made = np.zeros_like(parts[pc])
        orig = np.zeros_like(parts[pc])
        for s, o in ((('cho', c), pc), (('jung', j), pj), (('jong', k), pk)):
            if o is None:
                continue
            orig |= parts[o]
            best = min(sel[s], key=lambda q: int(np.count_nonzero(flat[q] != flat[o])))
            made |= parts[best]
        d = int(np.count_nonzero(made != orig))
        err += d
        exact += (d == 0)
    return exact, err


def grow(sel, triples, parts, flat, budget=BUDGET):
    cand = collections.defaultdict(collections.Counter)
    for (c, j, k), (pc, pj, pk) in triples.items():
        cand[('cho', c)][pc] += 1
        cand[('jung', j)][pj] += 1
        if pk is not None:
            cand[('jong', k)][pk] += 1
    used = sum(len(v) for v in sel.values())
    _e, err = evaluate(sel, triples, parts, flat)
    while used < budget:
        best = None
        for s, cnt in cand.items():
            for p in cnt:
                if p in sel[s]:
                    continue
                sel[s].add(p)
                _e2, e2 = evaluate(sel, triples, parts, flat)
                sel[s].remove(p)
                if best is None or (err - e2) > best[0]:
                    best = (err - e2, s, p, e2)
        if best is None or best[0] <= 0:
            break
        _g, s, p, err = best
        sel[s].add(p)
        used += 1
    return sel, used, err


def main():
    attr, H, W, parts, triples = O.build_triples()
    flat = {p: parts[p].ravel() for p in parts}
    out = {}
    for axis in ('jung', 'jong'):
        s = seed(triples, axis)
        n0 = sum(len(v) for v in s.values())
        e0, err0 = evaluate(s, triples, parts, flat)
        s, n, err = grow(s, triples, parts, flat)
        e, _ = evaluate(s, triples, parts, flat)
        print('초성 2벌 축 = %-5s : 씨앗 %d부품 -> %d부품, 정확 %d (%.1f%%), 평균오차 %.2f px'
              % (axis, n0, n, e, e * 100.0 / len(triples), err / len(triples)))
        out[axis] = {'sel': {'%s,%d' % k: sorted(v) for k, v in s.items()}, 'used': n}
    json.dump(out, open(os.path.join(project.ROOT, 'work', 'jamo_axis.json'), 'w'))
    print('-> work/jamo_axis.json')


if __name__ == '__main__':
    main()
