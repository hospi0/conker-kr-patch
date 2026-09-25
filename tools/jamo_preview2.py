"""최종 조합형(89부품) · 픽셀탐욕(89부품) · 물마루 원본을 나란히 렌더한다."""
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import jamo_minset as J
import jamo_optimize as O

SAMPLE = [
    '안녕하세요 코너입니다',
    '이봐, 저기 뭔가 있는 것 같은데?',
    '돈을 모아야 집에 갈 수 있어.',
    '아 젠장, 또 시작이군.',
    '체크포인트를 통과했습니다',
    '다람쥐 왕국의 왕이 되었다',
    '그건 좀 곤란한데요, 여러분.',
]


def load_sel(path, key):
    d = json.load(open(path))
    sel = {}
    for k, v in d[key].items():
        kind, i = k.split(',')
        sel[(kind, int(i))] = set(v) if isinstance(v, list) else {v}
    return sel


def cell(parts, flat, sel, triples, H, W, c, j, k, mode):
    a = np.zeros((H, W), dtype=np.uint8)
    t = triples.get((c, j, k))
    if not t:
        return a
    for s, o in ((('cho', c), t[0]), (('jung', j), t[1]), (('jong', k), t[2])):
        if o is None:
            continue
        if mode == 'orig':
            a |= parts[o]
        else:
            opts = sel.get(s) or {o}
            best = min(opts, key=lambda q: int(np.count_nonzero(flat[q] != flat[o])))
            a |= parts[best]
    return a


def line(text, parts, flat, sel, triples, gs, H, W, mode):
    cells = []
    for ch in text:
        cp = ord(ch)
        if 0xAC00 <= cp <= 0xD7A3:
            idx = cp - 0xAC00
            cells.append(cell(parts, flat, sel, triples, H, W,
                              idx // 588, (idx % 588) // 28, idx % 28, mode))
        elif ch == ' ':
            cells.append(np.zeros((H, 4), dtype=np.uint8))
        else:
            g = gs.get(cp)
            a = J.grid(g, H, W) if g else np.zeros((H, 5), dtype=np.uint8)
            if a.any():
                xs = np.nonzero(a.any(axis=0))[0]
                a = a[:, xs.min():xs.max() + 1]
            cells.append(a)
    gap = 1
    out = np.zeros((H, sum(c.shape[1] + gap for c in cells) or 1), dtype=np.uint8)
    x = 0
    for c in cells:
        out[:, x:x + c.shape[1]] = c
        x += c.shape[1] + gap
    return out


def main():
    attr, H, W, parts, triples = O.build_triples()
    flat = {p: parts[p].ravel() for p in parts}
    _a, gs = J.load()

    sel_final = load_sel(os.path.join(project.ROOT, 'work', 'jamo_final.json'), 'sel')
    p2 = os.path.join(project.ROOT, 'work', 'jamo_optimized2.json')
    sel_px = load_sel(p2, 'parts') if os.path.exists(p2) else None

    modes = [('final', sel_final, '휴리스틱씨앗 89부품')]
    if sel_px:
        modes.append(('px', sel_px, '픽셀탐욕 89부품'))
    modes.append(('orig', None, '물마루 원본'))

    rows = []
    for s in SAMPLE:
        rows.append([line(s, parts, flat, sel or {}, triples, gs, H, W,
                          'orig' if m == 'orig' else 'sel')
                     for m, sel, _lab in modes])

    width = max(max(a.shape[1] for a in r) for r in rows) + 6
    blockh = (H + 2) * len(modes) + 6
    img = np.zeros((blockh * len(rows), width), dtype=np.uint8)
    for i, r in enumerate(rows):
        for m, a in enumerate(r):
            y = i * blockh + m * (H + 2) + 2
            img[y:y + H, 2:2 + a.shape[1]] = a
    im = Image.fromarray((img * 255).astype(np.uint8))
    Z = 4
    im = im.resize((im.width * Z, im.height * Z), Image.NEAREST)
    out = os.path.join(project.ROOT, 'work', 'jamo_preview2.png')
    im.save(out)
    print('wrote work/jamo_preview2.png (%dx 확대)' % Z)
    for m, _s, lab in modes:
        print('   각 묶음 %d행: %s' % (modes.index((m, _s, lab)) + 1, lab))


if __name__ == '__main__':
    main()
