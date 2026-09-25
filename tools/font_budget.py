"""폰트 영역의 실제 예산을 측정한다.

원본 RLE 인코더는 탐욕적이지 않다. 같은 픽셀을 다시 인코딩하면 더 짧아지는
글리프가 있어서, 재인코딩만으로 확보되는 공간이 있다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import font


def main():
    data = project.load_rom()
    cfg = project.load_config()['font']
    gs, end = font.parse_chain(data)

    orig_bytes = sum(g.size for g in gs)
    re_bytes = 0
    saved = []
    for g in gs:
        pl = font.encode_rle(g.pixels(), g.w, g.h)
        sz = font.ENTRY_HEADER + len(pl)
        re_bytes += sz
        if sz != g.size:
            saved.append((g.index, g.size, sz, g.size - sz))

    slack = project.cint(cfg['next_structure_rom']) - end
    print('폰트 영역   : %s .. %08X' % (cfg['rom_start'], end))
    print('다음 구조물 : %s  (뒤에 붙은 여유 %d B)' % (cfg['next_structure_rom'], slack))
    print()
    print('글리프 %d개' % len(gs))
    print('  원본 총합      : %d B' % orig_bytes)
    print('  탐욕 재인코딩  : %d B' % re_bytes)
    print('  재인코딩 이득  : %d B  (%d개 글리프에서)' % (orig_bytes - re_bytes, len(saved)))
    print()
    total = (orig_bytes - re_bytes) + slack
    print('=> 재인코딩 + 기존 여유 = %d B 를 폰트 영역 안에서 쓸 수 있다.' % total)

    avg = sum(font.ENTRY_HEADER + len(font.encode_rle(g.pixels(), g.w, g.h)) for g in gs) / len(gs)
    print('   현재 평균 글리프 %.1f B → 그 예산으로 약 %d글리프 추가 가능(같은 크기 기준).'
          % (avg, int(total // avg)))
    print()
    print('절약 상위 10 (index, 원본, 재인코딩, 절약):')
    for row in sorted(saved, key=lambda r: -r[3])[:10]:
        print('   %-3d  %4d -> %4d   -%d' % row)


if __name__ == '__main__':
    main()
