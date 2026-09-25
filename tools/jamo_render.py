"""나눔고딕 U+1100 자모를 조합형 글리프로 렌더링한다.

초성 U+1100-1112 (19), 중성 U+1161-1175 (21), 종성 U+11A8-11C2 (27) = 67자모.
Conker 폰트는 4비트 안티에일리어싱이므로 8비트 렌더 결과를 4비트로 줄인다.

⚠️ U+1100 자모는 OpenType 합성(GSUB/GPOS)을 전제로 만들어진 경우가 많다.
   낱자 렌더가 실제 조합 위치와 맞는지 반드시 대조한다.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

FONT_DIR = 'C:/claude/utils/font/nanum-gothic'
CHO = [chr(0x1100 + i) for i in range(19)]
JUNG = [chr(0x1161 + i) for i in range(21)]
JONG = [chr(0x11A8 + i) for i in range(27)]

CHO_C = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
JUNG_C = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'
JONG_C = 'ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ'


def load(name='NanumGothic.ttf', px=12):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), px)


def mask(font, s):
    """문자열의 8비트 알파 마스크와 오프셋을 돌려준다."""
    m = font.getmask(s, mode='L')
    w, h = m.size
    if w == 0 or h == 0:
        return np.zeros((0, 0), dtype=np.uint8), (0, 0)
    a = np.frombuffer(bytes(m), dtype=np.uint8).reshape(h, w)
    try:
        bbox = font.getbbox(s)
        off = (bbox[0], bbox[1])
    except Exception:
        off = (0, 0)
    return a, off


def art(a, thr=96):
    return ['|' + ''.join('#' if v >= 160 else ('+' if v >= thr else '.') for v in row) + '|'
            for row in a]


def main():
    px = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    name = sys.argv[2] if len(sys.argv) > 2 else 'NanumGothic.ttf'
    f = load(name, px)
    print('%s @ %dpx' % (name, px))

    print('\n=== 진행폭(advance) ===')
    for label, arr in (('초성', CHO), ('중성', JUNG), ('종성', JONG)):
        ws = sorted({int(f.getlength(c)) for c in arr})
        print('  %s: advance 값 %s' % (label, ws))

    print('\n=== 낱자 렌더 vs 실제 음절 대조 (가) ===')
    a_syl, _ = mask(f, '가')
    print('  음절 "가"  %dx%d' % (a_syl.shape[1], a_syl.shape[0]))
    for r in art(a_syl):
        print('    ' + r)

    a_seq, _ = mask(f, '\u1100\u1161')       # 초성ㄱ + 중성ㅏ
    print('  자모열 U+1100 U+1161  %dx%d' % (a_seq.shape[1], a_seq.shape[0]))
    for r in art(a_seq):
        print('    ' + r)

    print('\n=== 낱자 단독 렌더 ===')
    for label, cp, comp in (('초성ㄱ', '\u1100', 'ㄱ'), ('중성ㅏ', '\u1161', 'ㅏ'),
                            ('종성ㄱ', '\u11A8', 'ㄱ')):
        a, off = mask(f, cp)
        print('  %s (%s)  %dx%d  advance=%d' % (label, comp, a.shape[1], a.shape[0],
                                                int(f.getlength(cp))))
        for r in art(a):
            print('    ' + r)


if __name__ == '__main__':
    main()
