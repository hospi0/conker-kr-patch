"""89칸 예산 안에서 조합형 부품을 픽셀 오차 최소화로 배분한다.

「정확 일치 수」는 세 부품이 모두 맞아야 인정돼 탐욕 최적화에 부적합하다.
자형 품질에 직결되는 **픽셀 오차**를 목표로 바꾼다.

부품은 자리별로 거의 겹치지 않으므로 오차를 자리별로 분리해 다룬다:
    cost(자모슬롯 s, 선택집합 S) = Σ_p 사용횟수[p] · min_{q∈S} Hamming(p, q)
슬롯별 k-medoid + 전역 탐욕 배분.
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

# 자모에 쓸 슬롯 수. 95칸 - 비한글 유지칸 - 널 글리프 1칸.
# 숫자 0-9 를 되살리면서 89 -> 79 로 줄었다 (build_kr.KEEP 과 반드시 맞출 것).
BUDGET = 79


def main():
    global BUDGET
    if len(sys.argv) > 1:
        BUDGET = int(sys.argv[1])
    attr, H, W, parts, triples = O.build_triples()
    print('예산 %d 부품' % BUDGET)
    print('셀 %dx%d, 음절 %d개, 부품 후보 %d개' % (W, H, len(triples), len(parts)))

    cand = collections.defaultdict(collections.Counter)
    for (c, j, k), (pc, pj, pk) in triples.items():
        cand[('cho', c)][pc] += 1
        cand[('jung', j)][pj] += 1
        if pk is not None:
            cand[('jong', k)][pk] += 1

    flat = {p: parts[p].ravel().astype(np.int16) for p in parts}

    def dist(a, b):
        return int(np.count_nonzero(flat[a] != flat[b]))

    # 슬롯별 거리행렬
    D = {}
    for s, cnt in cand.items():
        ps = list(cnt)
        D[s] = (ps, np.array([[dist(a, b) for b in ps] for a in ps], dtype=np.int32),
                np.array([cnt[p] for p in ps], dtype=np.int64))

    def slot_cost(s, chosen_idx):
        ps, dm, w = D[s]
        if not chosen_idx:
            return int((w * dm.max()).sum())
        sub = dm[:, list(chosen_idx)].min(axis=1)
        return int((w * sub).sum())

    sel = {}
    for s in D:
        ps, dm, w = D[s]
        best = min(range(len(ps)), key=lambda i: int((w * dm[:, i]).sum()))
        sel[s] = {best}
    used = sum(len(v) for v in sel.values())
    cost = sum(slot_cost(s, sel[s]) for s in D)
    print('최빈 1벌 시작: 부품 %d개, 총 픽셀오차 %d' % (used, cost))

    while used < BUDGET:
        best = None
        for s in D:
            ps, dm, w = D[s]
            cur = slot_cost(s, sel[s])
            for i in range(len(ps)):
                if i in sel[s]:
                    continue
                gain = cur - slot_cost(s, sel[s] | {i})
                if gain > 0 and (best is None or gain > best[0]):
                    best = (gain, s, i)
        if best is None:
            break
        gain, s, i = best
        sel[s].add(i)
        used += 1
        cost -= gain
        kind, idx = s
        name = {'cho': J.CHO_C, 'jung': J.JUNG_C, 'jong': J.JONG_C}[kind]
        print('  +%-4s %s (오차 -%d) -> 부품 %d개, 총오차 %d'
              % (kind, name[idx] if idx < len(name) else '?', gain, used, cost))

    # 최종 선택을 코드포인트로
    chosen = {}
    for s, idxs in sel.items():
        ps, dm, w = D[s]
        chosen[s] = [ps[i] for i in idxs]

    # 음절별 최선 부품 배정 + 정확 일치·픽셀오차 재측정
    exact = 0
    total_err = 0
    for (c, j, k), (pc, pj, pk) in triples.items():
        pick = []
        for s, orig in ((('cho', c), pc), (('jung', j), pj), (('jong', k), pk)):
            if orig is None:
                continue
            opts = chosen[s]
            pick.append(min(opts, key=lambda q: int(np.count_nonzero(flat[q] != flat[orig]))))
        made = np.zeros_like(parts[pc])
        for p in pick:
            made |= parts[p]
        orig_img = np.zeros_like(parts[pc])
        for p in (pc, pj, pk):
            if p is not None:
                orig_img |= parts[p]
        if np.array_equal(made, orig_img):
            exact += 1
        total_err += int(np.count_nonzero(made != orig_img))

    print('\n최종: 부품 %d개 / 예산 %d' % (used, BUDGET))
    print('  정확 일치 %d / %d (%.1f%%)' % (exact, len(triples), exact * 100.0 / len(triples)))
    print('  음절당 평균 픽셀오차 %.2f px (셀 %d px 중)'
          % (total_err / len(triples), H * W))

    out = {'H': H, 'W': W, 'parts': {'%s,%d' % s: v for s, v in chosen.items()},
           'exact': exact, 'total': len(triples), 'used': used}
    p = os.path.join(project.ROOT, 'work', 'jamo_optimized2.json')
    json.dump(out, open(p, 'w'))
    print('-> work/jamo_optimized2.json')


if __name__ == '__main__':
    main()
