"""폰트 영역 서술자 테이블과 디코드된 글리프 버퍼를 확인한다.

부팅 루프(RDRAM 0x802CD964~):
    s2  = 0x80082F80 + fontid*8
    a0  = *(s2)      ROM start
    t9  = *(s2+4)    ROM end
    buf = alloc(0x2800)              <- 임시 버퍼 상한 10,240 B
    load(a0, buf, t9 - a0, 1)
    ptr = buf ; idx = 0
    do { ProcessGlyph(ptr, idx, fontid); ptr += BE32(ptr+4); idx++ }
    while (ptr + 0xF) < buf + (end - start)      <- 길이 기반

ProcessGlyph(RDRAM 0x802CDA38):
    meta = *(0x80085994 + fontid*4)     meta[idx] = [w+1][h+1][b2][flag]
    pix  = *(0x80085990 + fontid*4)     pix + idx*224 에 224바이트 슬롯
    stride = (w+1 + 7) & ~7
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import font

RAM = 0x80000000
DESC_TABLE = 0x80082F80
META_PTRS = 0x80085994
PIX_PTRS = 0x80085990
SLOT = 224
ALLOC_LIMIT = 0x2800


def rd(ram, addr, n):
    return ram[addr - RAM: addr - RAM + n]


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else 'hard_rdram.bin'
    ram = open(os.path.join(project.ROOT, 'work', name), 'rb').read()
    rom = project.load_rom()
    cfg = project.load_config()['font']
    f_start = project.cint(cfg['rom_start'])
    f_end = project.cint(cfg['rom_end'])

    print('=== 서술자 테이블 %08X (8바이트 × N) ===' % DESC_TABLE)
    hit = None
    for i in range(16):
        a = DESC_TABLE + i * 8
        s, e = struct.unpack('>II', rd(ram, a, 8))
        mark = ''
        if s == f_start:
            mark = '  <== 폰트 (config 의 rom_start 와 일치)'
            hit = (i, s, e)
        print('  id %-2d  %08X  start=%08X  end=%08X  len=%-6d%s'
              % (i, a, s, e, e - s, mark))

    if hit:
        i, s, e = hit
        print('\n폰트 id=%d   ROM %08X..%08X   len=%d' % (i, s, e, e - s))
        print('  글리프 체인 실제 끝 : %08X' % f_end)
        print('  서술자 end 와의 차  : %d B' % (e - f_end))
        print('  임시 버퍼 상한      : %d B (alloc 상수 0x2800)' % ALLOC_LIMIT)
        print('  => 코드 패치 없이 늘릴 수 있는 폰트 데이터 = %d B' % (ALLOC_LIMIT - (e - s)))
        gs, _ = font.parse_chain(rom)
        avg = sum(g.size for g in gs) / len(gs)
        print('     현재 평균 글리프 %.1f B -> 약 %d글리프 추가 여지'
              % (avg, int((ALLOC_LIMIT - (e - s)) // avg)))

        meta = struct.unpack('>I', rd(ram, META_PTRS + i * 4, 4))[0]
        pix = struct.unpack('>I', rd(ram, PIX_PTRS + i * 4, 4))[0]
        print('\n  메타 배열 : %08X' % meta)
        print('  픽셀 버퍼 : %08X  (글리프당 %d B)' % (pix, SLOT))

        # 디코드된 글리프 확인
        print('\n=== 디코드 결과 대조 (픽셀 버퍼) ===')
        ok = 0
        for g in gs:
            stride = (g.w + 1 + 7) & ~7
            px = g.pixels()
            buf = rd(ram, pix + g.index * SLOT, SLOT)
            match = all(buf[y * stride + x] in (px[y * g.w + x], px[y * g.w + x] * 17)
                        for y in range(g.h) for x in range(g.w))
            ok += match
        print('  stride=(w+1+7)&~7 로 %d/%d 글리프 일치' % (ok, len(gs)))
        if ok < len(gs):
            g = gs[10]
            stride = (g.w + 1 + 7) & ~7
            print('  참고: 글리프 10 (A, %dx%d, stride %d) 버퍼 앞 32B: %s'
                  % (g.w, g.h, stride, rd(ram, pix + 10 * SLOT, 32).hex()))
            print('        원본 픽셀 앞 %d개: %s' % (g.w, g.pixels()[:g.w]))


if __name__ == '__main__':
    main()
