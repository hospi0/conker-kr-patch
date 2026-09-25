"""음절 단위 배정: 조합 결과의 오차로 벌을 고른다.

자모를 각각 독립적으로 「자기와 가장 닮은 벌」로 고르면,
납작한 초성이 자기 기준으론 최선이어도 키 큰 중성과 붙어 깨져 보인다(베).
조합된 음절 전체의 픽셀 오차로 고르면 그런 부조화가 사라진다.
"""
import itertools
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import jamo_optimize as O


def load_sel(path=None, key='parts'):
    path = path or os.path.join(project.ROOT, 'work', 'jamo_optimized2.json')
    d = json.load(open(path))
    sel = {}
    for k, v in d[key].items():
        kind, i = k.split(',')
        sel[(kind, int(i))] = list(v)
    return sel


def build(sel=None):
    # ★기준 비트맵은 refs 를 쓴다. 부품 조합이 없는 통글자 22자(래 레 의 씨 제 피 …)까지
    #   배정 대상에 들어온다 — 이걸 빼면 그 음절이 인코딩 불가가 된다.
    attr, H, W, parts, triples, refs, whole = O.build_refs()
    sel = sel or load_sel()
    choice = {}
    for (c, j, k), orig in refs.items():
        slots = [('cho', c), ('jung', j)] + ([('jong', k)] if k else [])
        opts = [sel[s] for s in slots]
        best = None
        for combo in itertools.product(*opts):
            made = np.zeros_like(orig)
            for p in combo:
                made |= parts[p]
            e = int(np.count_nonzero(made != orig))
            if best is None or e < best[0]:
                best = (e, combo)
        choice[(c, j, k)] = best[1]
    return H, W, parts, triples, sel, choice


def main():
    H, W, parts, triples, sel, choice = build()
    # 비교: 독립 배정 vs 음절 배정
    flat = {p: parts[p].ravel() for p in parts}
    ind_err = syl_err = 0
    ind_ex = syl_ex = 0
    for (c, j, k), t in triples.items():
        orig = np.zeros_like(parts[t[0]])
        for p in t:
            if p is not None:
                orig |= parts[p]
        # 독립
        made = np.zeros_like(orig)
        for s, o in ((('cho', c), t[0]), (('jung', j), t[1]), (('jong', k), t[2])):
            if o is None:
                continue
            made |= parts[min(sel[s], key=lambda q: int(np.count_nonzero(flat[q] != flat[o])))]
        d = int(np.count_nonzero(made != orig)); ind_err += d; ind_ex += (d == 0)
        # 음절
        made = np.zeros_like(orig)
        for p in choice[(c, j, k)]:
            made |= parts[p]
        d = int(np.count_nonzero(made != orig)); syl_err += d; syl_ex += (d == 0)
    n = len(triples)
    print('독립 배정 : 정확 %d (%.1f%%), 평균오차 %.2f px' % (ind_ex, ind_ex * 100.0 / n, ind_err / n))
    print('음절 배정 : 정확 %d (%.1f%%), 평균오차 %.2f px' % (syl_ex, syl_ex * 100.0 / n, syl_err / n))

    # 베 확인
    for ch in '베리네집이에요안녕하세요':
        cp = ord(ch) - 0xAC00
        c, j, k = cp // 588, (cp % 588) // 28, cp % 28
        combo = choice[(c, j, k)]
        hs = [int(np.count_nonzero(parts[p].any(axis=1))) for p in combo]
        print('  %s : 부품 %s  높이 %s' % (ch, [hex(p) for p in combo], hs))


if __name__ == '__main__':
    main()
