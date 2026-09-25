"""RDRAM 에서 문자 매핑 테이블을 뜬다.

0x80085994 = 글리프 메타 배열 포인터 ( -> [w+1][h+1][00][flag] * 95 )
그 바로 앞에 Latin-1 (대문자, 소문자) 코드 쌍 목록이 붙어 있다.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import font

RAM = 0x80000000
META_PTR = 0x80085994


def rd(ram, addr, n):
    return ram[addr - RAM: addr - RAM + n]


def main():
    ram = open(os.path.join(project.ROOT, 'work', 'rdram.bin'), 'rb').read()
    rom = project.load_rom()
    gs, _ = font.parse_chain(rom)

    print('=== 0x80085894 .. 0x80085998 (매핑 테이블 후보) ===')
    for a in range(0x80085894, 0x80085998, 16):
        b = rd(ram, a, 16)
        print('  %08X  %s' % (a, ' '.join('%02X' % c for c in b)))

    # 쌍 구조 해석: 뒤에서부터 (upper, lower) Latin-1 쌍이 이어지는 구간을 찾는다
    print('\n=== (대문자, 소문자) Latin-1 쌍으로 읽기 ===')
    end = 0x8008598E          # 0x40 00 직전
    pairs = []
    a = end
    while a > 0x80085800:
        u, l = rd(ram, a - 2, 2)
        if u >= 0xC0 and l >= 0xC0 and (l - u) in (0x20, 0x00):
            pairs.append((a - 2, u, l))
            a -= 2
        elif u >= 0x20 and l >= 0x20:
            pairs.append((a - 2, u, l))
            a -= 2
        else:
            break
    pairs.reverse()
    print('  연속 %d쌍, 시작 %08X' % (len(pairs), pairs[0][0] if pairs else 0))
    for addr, u, l in pairs:
        try:
            cu = bytes([u]).decode('latin1')
            cl = bytes([l]).decode('latin1')
        except Exception:
            cu = cl = '?'
        print('     %08X  %02X %02X   %s %s' % (addr, u, l, cu, cl))

    print('\n=== 글리프 메타 배열 대조 (0x800CBBD0) ===')
    meta = struct.unpack('>I', rd(ram, META_PTR, 4))[0]
    bad = 0
    for g in gs:
        e = rd(ram, meta + g.index * 4, 4)
        if e[0] != (g.w + 1) or e[1] != (g.h + 1) or e[3] != g.flag:
            bad += 1
            if bad <= 5:
                print('     불일치 idx %d: RAM %s vs ROM w=%d h=%d flag=%d'
                      % (g.index, e.hex(), g.w, g.h, g.flag))
    print('  메타 배열 %08X, 불일치 %d / %d' % (meta, bad, len(gs)))


if __name__ == '__main__':
    main()
