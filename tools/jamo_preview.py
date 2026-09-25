"""최소 벌 조합형 vs 물마루 원본을 나란히 렌더해 판독성을 판정한다."""
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import jamo_minset as J

SAMPLE = [
    '안녕하세요 코너입니다',
    '이봐, 저기 뭔가 있는 것 같은데?',
    '돈을 모아야 집에 갈 수 있어.',
    '아 젠장, 또 시작이군.',
    '체크포인트를 통과했습니다',
    '다람쥐 왕국의 왕이 되었다',
]


def render_line(text, parts, cho, jung, jong, H, W, mode):
    cells = []
    for ch in text:
        cp = ord(ch)
        if 0xAC00 <= cp <= 0xD7A3:
            idx = cp - 0xAC00
            c, j, k = idx // 588, (idx % 588) // 28, idx % 28
            if mode == 'min':
                a = J.compose(parts, cho, jung, jong, H, W, c, j, k)
            else:
                a = np.zeros((H, W), dtype=np.uint8)
                t = ORIG_TRIPLES.get((c, j, k))
                if t:
                    for p in t:
                        if p is not None and p in parts:
                            a |= parts[p]
            cells.append(a)
        elif ch == ' ':
            cells.append(np.zeros((H, 4), dtype=np.uint8))
        else:
            g = ORIG_GS.get(cp)
            a = J.grid(g, H, W) if g else np.zeros((H, 6), dtype=np.uint8)
            if a.any():
                xs = np.nonzero(a.any(axis=0))[0]
                a = a[:, xs.min():xs.max() + 1]
            cells.append(a)
    if not cells:
        return np.zeros((H, 1), dtype=np.uint8)
    gap = 1
    total = sum(c.shape[1] + gap for c in cells)
    out = np.zeros((H, total), dtype=np.uint8)
    x = 0
    for c in cells:
        out[:, x:x + c.shape[1]] = c
        x += c.shape[1] + gap
    return out


def main():
    global ORIG_TRIPLES, ORIG_GS
    attr, H, W, parts, triples, cho, jung, jong = J.build()
    ORIG_TRIPLES = triples
    _a, ORIG_GS = J.load()

    rows = []
    for s in SAMPLE:
        a_min = render_line(s, parts, cho, jung, jong, H, W, 'min')
        a_org = render_line(s, parts, cho, jung, jong, H, W, 'orig')
        rows.append((a_min, a_org))

    width = max(max(a.shape[1] for a in r) for r in rows) + 8
    rowh = H * 2 + 6
    img = np.zeros((rowh * len(rows) + 4, width), dtype=np.uint8)
    for i, (a_min, a_org) in enumerate(rows):
        y = i * rowh + 2
        img[y:y + H, 2:2 + a_min.shape[1]] = a_min            # 위: 최소 벌
        img[y + H + 3:y + H + 3 + H, 2:2 + a_org.shape[1]] = a_org  # 아래: 원본
    im = Image.fromarray((img * 255).astype(np.uint8))
    Z = 4
    im = im.resize((im.width * Z, im.height * Z), Image.NEAREST)
    out = os.path.join(project.ROOT, 'work', 'jamo_preview.png')
    im.save(out)
    print('wrote work/jamo_preview.png  %dx%d  (%dx 확대)' % (im.width, im.height, Z))
    print('각 줄: 위 = 최소 벌 86부품 조합 / 아래 = 물마루 원본')


if __name__ == '__main__':
    main()
