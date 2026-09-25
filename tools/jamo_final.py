"""최종 조합형 부품 집합을 만든다.

씨앗 = 휴리스틱(초성 2벌: 중성계열 세로/가로·섞임, 중성 1벌, 종성 1벌) = 86부품
그 뒤 예산(89)까지 픽셀 오차가 가장 크게 주는 부품을 탐욕 추가.

인코더가 (초성,중성,종성)마다 선택집합에서 **가장 가까운 벌**을 고르므로
벌 배정 규칙은 룩업 테이블이면 된다.
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


def seed_selection(triples):
    """휴리스틱 씨앗: 초성 2벌(중성계열) + 중성 1벌 + 종성 1벌."""
    sel = collections.defaultdict(set)
    for c in range(19):
        for g2 in (0, 1):
            cnt = collections.Counter()
            for (cc, j, k), t in triples.items():
                if cc == c and (0 if J.JUNG_GROUP[j] == 0 else 1) == g2:
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
    exact = 0
    err = 0
    for (c, j, k), (pc, pj, pk) in triples.items():
        made = np.zeros_like(parts[pc])
        orig = np.zeros_like(parts[pc])
        for s, o in ((('cho', c), pc), (('jung', j), pj), (('jong', k), pk)):
            if o is None:
                continue
            orig |= parts[o]
            opts = sel[s]
            best = min(opts, key=lambda q: int(np.count_nonzero(flat[q] != flat[o])))
            made |= parts[best]
        if np.array_equal(made, orig):
            exact += 1
        err += int(np.count_nonzero(made != orig))
    return exact, err


def main():
    attr, H, W, parts, triples = O.build_triples()
    flat = {p: parts[p].ravel() for p in parts}
    sel = seed_selection(triples)
    used = sum(len(v) for v in sel.values())
    exact, err = evaluate(sel, triples, parts, flat)
    print('씨앗(휴리스틱) 부품 %d개 : 정확 %d (%.1f%%), 평균오차 %.2f px'
          % (used, exact, exact * 100.0 / len(triples), err / len(triples)))

    cand = collections.defaultdict(collections.Counter)
    for (c, j, k), (pc, pj, pk) in triples.items():
        cand[('cho', c)][pc] += 1
        cand[('jung', j)][pj] += 1
        if pk is not None:
            cand[('jong', k)][pk] += 1

    while used < BUDGET:
        best = None
        for s, cnt in cand.items():
            for p in cnt:
                if p in sel[s]:
                    continue
                sel[s].add(p)
                e2, err2 = evaluate(sel, triples, parts, flat)
                sel[s].remove(p)
                gain = err - err2
                if best is None or gain > best[0]:
                    best = (gain, s, p, e2, err2)
        if best is None or best[0] <= 0:
            break
        gain, s, p, exact, err = best
        sel[s].add(p)
        used += 1
        kind, i = s
        nm = {'cho': J.CHO_C, 'jung': J.JUNG_C, 'jong': J.JONG_C}[kind]
        print('  +%-4s %s (오차 -%d) -> %d부품, 정확 %d (%.1f%%), 평균오차 %.2f px'
              % (kind, nm[i] if i < len(nm) else '?', gain, used, exact,
                 exact * 100.0 / len(triples), err / len(triples)))

    print('\n최종 부품 %d개 / 예산 %d' % (used, BUDGET))
    print('  정확 일치 %d / %d (%.1f%%)' % (exact, len(triples), exact * 100.0 / len(triples)))
    print('  음절당 평균 픽셀오차 %.2f px (셀 %d px)' % (err / len(triples), H * W))

    out = {'H': H, 'W': W, 'used': used, 'exact': exact, 'total': len(triples),
           'sel': {'%s,%d' % s: sorted(v) for s, v in sel.items()}}
    json.dump(out, open(os.path.join(project.ROOT, 'work', 'jamo_final.json'), 'w'))
    print('-> work/jamo_final.json')


if __name__ == '__main__':
    main()
