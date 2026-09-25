"""실사용 음절 빈도로 가중해 89칸 부품을 배분한다.

11,172자 전체에 균등 가중을 주면 실제로 안 쓰이는 음절에 예산이 샌다.
⚠️ 현재 코퍼스는 `assets/corpus_sample.txt` (임시 표본). **번역이 나오면 실제 번역문으로 교체한다.**
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
import jamo_final as F

BUDGET = 89
CORPUS = os.path.join(project.ROOT, 'assets', 'corpus_sample.txt')


def load_weights():
    txt = open(CORPUS, encoding='utf-8').read()
    cnt = collections.Counter(ch for ch in txt if 0xAC00 <= ord(ch) <= 0xD7A3)
    w = {}
    for ch, n in cnt.items():
        idx = ord(ch) - 0xAC00
        w[(idx // 588, (idx % 588) // 28, idx % 28)] = n
    return w, len(cnt), sum(cnt.values())


def evaluate(sel, triples, parts, flat, weights):
    exact = wexact = err = werr = tot_w = 0
    for key, (pc, pj, pk) in triples.items():
        wt = weights.get(key, 0)
        made = np.zeros_like(parts[pc])
        orig = np.zeros_like(parts[pc])
        c, j, k = key
        for s, o in ((('cho', c), pc), (('jung', j), pj), (('jong', k), pk)):
            if o is None:
                continue
            orig |= parts[o]
            opts = sel.get(s) or {o}
            best = min(opts, key=lambda q: int(np.count_nonzero(flat[q] != flat[o])))
            made |= parts[best]
        d = int(np.count_nonzero(made != orig))
        err += d
        if wt:
            werr += d * wt
            tot_w += wt
            if d == 0:
                wexact += wt
        if d == 0:
            exact += 1
    return exact, err, wexact, werr, tot_w


def main():
    attr, H, W, parts, triples = O.build_triples()
    flat = {p: parts[p].ravel() for p in parts}
    weights, uniq, total = load_weights()
    print('코퍼스: 고유 음절 %d개, 총 %d자 (임시 표본)' % (uniq, total))

    sel = F.seed_selection(triples)
    used = sum(len(v) for v in sel.values())
    e, err, we, werr, tw = evaluate(sel, triples, parts, flat, weights)
    print('씨앗 %d부품: 코퍼스 정확 %.1f%%, 코퍼스 평균오차 %.2f px'
          % (used, we * 100.0 / tw, werr / tw))

    cand = collections.defaultdict(collections.Counter)
    for (c, j, k), (pc, pj, pk) in triples.items():
        wt = weights.get((c, j, k), 0) + 1        # 미등장 음절도 최소 가중 1
        cand[('cho', c)][pc] += wt
        cand[('jung', j)][pj] += wt
        if pk is not None:
            cand[('jong', k)][pk] += wt

    while used < BUDGET:
        best = None
        for s, cnt in cand.items():
            for p in cnt:
                if p in sel[s]:
                    continue
                sel[s].add(p)
                _e, _err, _we, w2, _tw = evaluate(sel, triples, parts, flat, weights)
                sel[s].remove(p)
                gain = werr - w2
                if best is None or gain > best[0]:
                    best = (gain, s, p, w2)
        if best is None or best[0] <= 0:
            break
        gain, s, p, werr = best
        sel[s].add(p)
        used += 1
        kind, i = s
        nm = {'cho': J.CHO_C, 'jung': J.JUNG_C, 'jong': J.JONG_C}[kind]
        print('  +%-4s %s (가중오차 -%d) -> %d부품, 코퍼스 평균오차 %.2f px'
              % (kind, nm[i] if i < len(nm) else '?', gain, used, werr / tw))

    e, err, we, werr, tw = evaluate(sel, triples, parts, flat, weights)
    print('\n최종 %d부품' % used)
    print('  코퍼스 정확 일치 %.1f%%,  코퍼스 평균오차 %.2f px' % (we * 100.0 / tw, werr / tw))
    print('  전체 11,150자 기준 정확 %.1f%%, 평균오차 %.2f px'
          % (e * 100.0 / len(triples), err / len(triples)))

    out = {'H': H, 'W': W, 'used': used,
           'sel': {'%s,%d' % s: sorted(v) for s, v in sel.items()}}
    json.dump(out, open(os.path.join(project.ROOT, 'work', 'jamo_weighted.json'), 'w'))
    print('-> work/jamo_weighted.json')


if __name__ == '__main__':
    main()
