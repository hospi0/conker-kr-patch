"""글리프별 ROM/RAM 주소표. 디버거 브레이크포인트 대상을 고를 때 쓴다."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import font


def main():
    data = project.load_rom()
    cfg = project.load_config()['font']
    base_rom = project.cint(cfg['rom_start'])
    base_ram = project.cint(cfg['runtime_ram'])
    gs, _ = font.parse_chain(data)

    table = font.char_table(data)
    labels = {}
    for idx, code in enumerate(table):
        ch = bytes([code]).decode('latin1')
        labels[idx] = "%02X %r" % (code, ch)

    only = sys.argv[1:] or None
    print('idx  ROM       RAM        w x h   label')
    for g in gs:
        if only and str(g.index) not in only:
            continue
        off = g.rom_off - base_rom
        print('%-4d %08X  %08X  %2dx%-2d  %s'
              % (g.index, g.rom_off, base_ram + off, g.w, g.h, labels.get(g.index, '')))


if __name__ == '__main__':
    main()
