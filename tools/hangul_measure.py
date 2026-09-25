"""갈무리 BDF 의 한글 음절 비트맵 크기를 재고 구조를 눈으로 확인한다.

목표 제약 (Conker 폰트):
    stride = (w + 1 + 7) & ~7,  픽셀 슬롯 224 B  ->  stride 16 이면 h <= 14
    즉 w <= 14, h <= 14 이면 안전하다.
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bdf

CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
JUNG = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'
JONG = ' ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ'


def syl(ci, ji, ki):
    return chr(0xAC00 + (ci * 21 + ji) * 28 + ki)


def show(f, ch, label=''):
    g = f.glyphs[ord(ch)]
    w, h, xo, yo = g.bbx
    bm = g.bitmap()
    print('  %s %s  bbx=%dx%d off=(%d,%d) dwidth=%d' % (ch, label, w, h, xo, yo, g.dwidth[0]))
    for row in bm:
        print('      ' + ''.join('#' if v else '.' for v in row))


def main():
    path = sys.argv[1]
    f = bdf.BdfFont(path)
    print(os.path.basename(path))
    print('  ascent=%s descent=%s fbbx=%s' % (f.props.get('ascent'), f.props.get('descent'),
                                              f.props.get('fbbx')))

    sizes = collections.Counter()
    offs = collections.Counter()
    dws = collections.Counter()
    for cp in range(0xAC00, 0xD7A4):
        g = f.glyphs.get(cp)
        if not g:
            continue
        sizes[(g.bbx[0], g.bbx[1])] += 1
        offs[(g.bbx[2], g.bbx[3])] += 1
        dws[g.dwidth[0]] += 1
    print('\n  음절 bbx 크기 분포:', sizes.most_common(6))
    print('  음절 오프셋 분포  :', offs.most_common(4))
    print('  음절 진행폭 분포  :', dws.most_common(4))

    print('\n  샘플:')
    for ch, lab in (('가', '초ㄱ + 중ㅏ'), ('각', '+ 종ㄱ'), ('고', '초ㄱ + 중ㅗ'),
                    ('곡', '+ 종ㄱ'), ('과', '초ㄱ + 중ㅘ'), ('괅', '+ 종ㄼ')):
        if ord(ch) in f.glyphs:
            show(f, ch, lab)


if __name__ == '__main__':
    main()
