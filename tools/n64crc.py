"""N64 부트 체크섬(CRC1/CRC2) 재계산. CIC-6105 변형 포함.

6105 는 다른 칩과 달리 t1 누적에 ROM 0x40+0x0710 영역을 참조한다.
이 게임은 6105 이므로 일반 루틴을 쓰면 안 된다.
"""
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

CHECKSUM_START = 0x1000
CHECKSUM_LENGTH = 0x100000
SEEDS = {6101: 0xF8CA4DDC, 6102: 0xF8CA4DDC, 6103: 0xA3886759,
         6105: 0xDF26F436, 6106: 0x1FEA617A}
M32 = 0xFFFFFFFF


def rol(v, b):
    b &= 31
    return ((v << b) | (v >> (32 - b))) & M32


def calc(rom, cic=6105):
    seed = SEEDS[cic]
    t1 = t2 = t3 = t4 = t5 = t6 = seed
    for i in range(0, CHECKSUM_LENGTH, 4):
        d = struct.unpack('>I', rom[CHECKSUM_START + i:CHECKSUM_START + i + 4])[0]
        if ((t6 + d) & M32) < t6:
            t4 = (t4 + 1) & M32
        t6 = (t6 + d) & M32
        t3 ^= d
        r = rol(d, d & 0x1F)
        t5 = (t5 + r) & M32
        if t2 > d:
            t2 ^= r
        else:
            t2 ^= t6 ^ d
        if cic == 6105:
            o = 0x40 + 0x0710 + (i & 0xFF)
            t1 = (t1 + (struct.unpack('>I', rom[o:o + 4])[0] ^ d)) & M32
        else:
            t1 = (t1 + (t5 ^ d)) & M32
    return (t6 ^ t4 ^ t3) & M32, (t5 ^ t2 ^ t1) & M32


def fix(path, cic=6105):
    d = bytearray(open(path, 'rb').read())
    old = struct.unpack('>II', d[0x10:0x18])
    c1, c2 = calc(d, cic)
    d[0x10:0x18] = struct.pack('>II', c1, c2)
    open(path, 'wb').write(bytes(d))
    return old, (c1, c2)


if __name__ == '__main__':
    # 자체 검증: 원본 ROM 은 계산값이 헤더와 같아야 한다
    rom = project.load_rom()
    c1, c2 = calc(rom, 6105)
    h1, h2 = struct.unpack('>II', rom[0x10:0x18])
    print('원본 검증: 계산 %08X %08X / 헤더 %08X %08X  -> %s'
          % (c1, c2, h1, h2, 'OK' if (c1, c2) == (h1, h2) else '불일치'))
    if (c1, c2) != (h1, h2):
        sys.exit(1)
    if len(sys.argv) > 1:
        old, new = fix(sys.argv[1])
        print('%s : %08X %08X -> %08X %08X' % (sys.argv[1], old[0], old[1], new[0], new[1]))
