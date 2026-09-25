"""PixelFontProject(.pfp) 로더. 물마루 소스가 이 형식이다.

glyphs: [{name, unicode, data: ["###...", ...]}]  — 상단부터의 ASCII 아트
attr  : ascent/descent/maxWidth/letterSpacing 등
"""
import json
import os

import numpy as np


class PfpFont:
    def __init__(self, path):
        with open(path, encoding='utf-8') as f:
            d = json.load(f)
        self.attr = d['attr']
        self.glyphs = {}
        for g in d['glyphs']:
            cp = g.get('unicode')
            if cp is None:
                continue
            self.glyphs[cp] = g

    @property
    def cell_h(self):
        return self.attr['ascent'] + self.attr['descent']

    def grid(self, cp):
        """(H, W) 0/1 배열. 없으면 None."""
        g = self.glyphs.get(cp)
        if not g:
            return None
        rows = g['data']
        h = len(rows)
        w = max(len(r) for r in rows) if h else 0
        a = np.zeros((h, w), dtype=np.uint8)
        for y, r in enumerate(rows):
            for x, c in enumerate(r):
                if c != '.':
                    a[y, x] = 1
        return a

    def ink_box(self, cp):
        a = self.grid(cp)
        if a is None or not a.any():
            return None
        ys, xs = np.nonzero(a)
        return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def art(a):
    return ['|' + ''.join('#' if v else '.' for v in row) + '|' for row in a]


if __name__ == '__main__':
    import sys
    f = PfpFont(sys.argv[1] if len(sys.argv) > 1
                else 'C:/claude/utils/font/Mulmaru/Mulmaru.pfp')
    print('attr:', f.attr)
    print('글리프 %d개, 셀 높이 %d' % (len(f.glyphs), f.cell_h))
    for ch in (sys.argv[2] if len(sys.argv) > 2 else '가각고곡한글'):
        a = f.grid(ord(ch))
        if a is None:
            print('  %s 없음' % ch); continue
        print('  %s  %dx%d' % (ch, a.shape[1], a.shape[0]))
        for r in art(a):
            print('     ' + r)
