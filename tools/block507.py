"""블록 507 (ROM 0x188328) 의 RAM 로드 주소와 그 안의 편집 대상들을 확정한다.

charmap  : raw +0x2E10  -> RAM 0x80085930
서술자   : raw +0x0460  -> RAM 0x80082F80
=> 로드 베이스 = 0x80085930 - 0x2E10 = 0x80082B20
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import rzip

BLOCK_ROM = 0x188328
LOAD_BASE = 0x80082B20
RAM = 0x80000000

POINTS = [
    (0x2E10, 0x80085930, 'charmap (95B + 0x00)'),
    (0x0460, 0x80082F80, '폰트 서술자 [rom_start][rom_end]'),
    (0x2E70, 0x80085990, 'pix 버퍼 포인터'),
    (0x2E74, 0x80085994, 'meta 배열 포인터'),
]


def main():
    rom = project.load_rom()
    ram_path = os.path.join(project.ROOT, 'work', 'hard_rdram.bin')
    ram = open(ram_path, 'rb').read() if os.path.exists(ram_path) else None

    r = rzip.decode_at(rom, BLOCK_ROM)
    assert r, '블록을 풀 수 없다'
    used, raw = r
    print('블록 507  ROM %08X  comp=%d  raw=%d' % (BLOCK_ROM, used, len(raw)))
    print('로드 베이스 = %08X   범위 %08X .. %08X'
          % (LOAD_BASE, LOAD_BASE, LOAD_BASE + len(raw)))
    print()

    ok = 0
    for off, expect_ram, label in POINTS:
        calc = LOAD_BASE + off
        blk = raw[off:off + 8]
        live = ram[expect_ram - RAM: expect_ram - RAM + 8] if ram else None
        same = (live == blk) if live is not None else None
        print('  +%05X -> RAM %08X %s  %-34s' % (off, calc, 'OK ' if calc == expect_ram else 'MIS', label))
        print('        블록 : %s' % blk.hex())
        if live is not None:
            print('        RAM  : %s   일치=%s' % (live.hex(), same))
            ok += bool(same)
    print()
    if ram:
        print('블록 내용과 RAM 상주본 일치: %d / %d 지점' % (ok, len(POINTS)))

    # 로드 베이스 전체 검증: 블록 전체가 그 주소에 그대로 있는가
    if ram:
        seg = ram[LOAD_BASE - RAM: LOAD_BASE - RAM + len(raw)]
        same_bytes = sum(1 for a, b in zip(seg, raw) if a == b)
        print('블록 전체 %d B 중 RAM 과 같은 바이트: %d (%.1f%%)'
              % (len(raw), same_bytes, same_bytes * 100.0 / len(raw)))
        print('  (BSS·런타임 변경분이 있으므로 100%% 는 아니다)')


if __name__ == '__main__':
    main()
