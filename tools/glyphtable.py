"""부팅 때 만들어지는 글리프 전처리 구조를 RDRAM 덤프에서 조사한다.

단서(P64 브레이크포인트 @ VA 15015A78, RDRAM 803B1A78):
    T5 = 0x80085994 ,  S0 = glyph_index * 4
    LBU t,0(S3) ; ADDIU t,t,1 ; SB t,0(T5 + idx*4)      <- w+1
    LW  p,0(T5) ; LBU t,1(S3) ; ADDIU t,t,1 ; SB t,1(p + idx*4)   <- h+1
    LBU s,0(S4) ; ADDIU x,s,7 ; ANDI x,x,0xFFF8         <- 폭을 8배수로 올림
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import font

RAM = 0x80000000


def rd(ram, addr, n):
    return ram[addr - RAM: addr - RAM + n]


def hexdump(ram, addr, n):
    for i in range(0, n, 16):
        b = rd(ram, addr + i, 16)
        print('  %08X  %-47s  %s' % (addr + i, ' '.join('%02X' % c for c in b),
              ''.join(chr(c) if 0x20 <= c < 0x7f else '.' for c in b)))


def main():
    ram = open(os.path.join(project.ROOT, 'work', 'rdram.bin'), 'rb').read()
    rom = project.load_rom()
    gs, _ = font.parse_chain(rom)

    print('=== 0x80085980 주변 ===')
    hexdump(ram, 0x80085980, 0x40)

    print('\n=== 0x80085994 가 가리키는 곳 ===')
    ptr = struct.unpack('>I', rd(ram, 0x80085994, 4))[0]
    print('  *(0x80085994) = %08X' % ptr)
    if RAM <= ptr < RAM + len(ram):
        hexdump(ram, ptr, 0x60)

    print('\n=== stride 4 배열이 (w+1, h+1, ?, ?) 인지 대조 ===')
    for base_label, base in (('0x80085994 직접', 0x80085994), ('*(0x80085994)', ptr)):
        if not (RAM <= base < RAM + len(ram) - 400):
            continue
        ok_w = ok_h = 0
        for g in gs:
            e = rd(ram, base + g.index * 4, 4)
            if e[0] == (g.w + 1) & 0xFF:
                ok_w += 1
            if e[1] == (g.h + 1) & 0xFF:
                ok_h += 1
        print('  %-16s  w+1 일치 %d/%d,  h+1 일치 %d/%d'
              % (base_label, ok_w, len(gs), ok_h, len(gs)))

    print('\n=== 디코드된 글리프 재탐색 (폭을 8배수로 패딩) ===')
    hits = 0
    for g in gs[:40]:
        px = g.pixels()
        stride = (g.w + 7) & ~7
        for fmt in ('i4', 'i8', 'i8x17'):
            buf = bytearray()
            for y in range(g.h):
                row = px[y * g.w:(y + 1) * g.w] + [0] * (stride - g.w)
                if fmt == 'i4':
                    for x in range(0, stride, 2):
                        buf.append((row[x] << 4) | row[x + 1])
                elif fmt == 'i8':
                    buf.extend(row)
                else:
                    buf.extend(v * 17 for v in row)
            if len(buf) < 12:
                continue
            i = ram.find(bytes(buf))
            if i >= 0:
                print('  glyph %-3d %dx%d stride=%d fmt=%-5s -> RAM %08X'
                      % (g.index, g.w, g.h, stride, fmt, RAM + i))
                hits += 1
                break
    print('  찾은 글리프: %d / 40' % hits)


if __name__ == '__main__':
    main()
