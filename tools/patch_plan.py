"""한글화 변경 계획을 원본에 대고 검증한다 (아직 쓰지는 않는다).

Expected Write 규칙: 모든 변경은 적용 전에 불변 원본을 기준으로 검증 가능해야 한다.
여기서는 각 변경의 기대 원본 바이트·최종 바이트·허용 범위를 확인만 한다.
"""
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import rzip
import font
import charmap

# (블록 ROM 오프셋, 블록내 오프셋, 기대 원본 바이트, 최종 바이트, 설명)
CODE_WRITES = [
    (0x6BDA2, 0x210, b'\x90', b'\x80', 'draw: lbu -> lb  (xoff 부호화)'),
    (0x6BDA2, 0xB2C, b'\x90', b'\x80', 'layout: lbu -> lb  (xoff 부호화)'),
]


def check_code_writes(rom):
    print('=== 코드 변경 (렌더러 xoff 부호화) ===')
    by_block = {}
    for blk, off, exp, new, desc in CODE_WRITES:
        by_block.setdefault(blk, []).append((off, exp, new, desc))
    ok = True
    for blk, writes in by_block.items():
        r = rzip.decode_at(rom, blk)
        assert r, '블록 %08X 해제 실패' % blk
        used, raw = r
        m = bytearray(raw)
        for off, exp, new, desc in writes:
            cur = raw[off:off + len(exp)]
            good = cur == exp
            ok &= good
            word = struct.unpack('>I', raw[off & ~3:(off & ~3) + 4])[0]
            print('  블록 %08X +%04X : %s -> %s   %s   %s'
                  % (blk, off, cur.hex(), new.hex(), 'OK' if good else '기대와 다름', desc))
            print('        해당 워드 %08X  (opcode %02X -> %02X)'
                  % (word, word >> 26, int.from_bytes(new, 'big') >> 2))
            m[off:off + len(new)] = new
        body = rzip.deflate_raw(bytes(m))
        assert zlib.decompressobj(-15).decompress(body) == bytes(m), '재압축 왕복 실패'
        room = (used - 4) - len(body)
        print('  블록 %08X 재압축 %d B / 원본 %d B  -> 여유 %+d B  %s'
              % (blk, len(body), used - 4, room, 'OK' if room >= 0 else '초과!'))
        ok &= room >= 0
    return ok


def check_font_budget(rom):
    print('\n=== 글리프 예산 ===')
    gs, end = font.parse_chain(rom)
    cfg = project.load_config()
    desc_len = 0x42450 - 0x40F10
    cur = sum(g.size for g in gs)
    greedy = sum(font.ENTRY_HEADER + len(font.encode_rle(g.pixels())) for g in gs)
    print('  글리프 %d개, 현재 %d B, 서술자 len %d B' % (len(gs), cur, desc_len))
    print('  탐욕 재인코딩 시 %d B (이득 %d B)' % (greedy, cur - greedy))
    print('  => 자모 %d개를 %d B 안에 그려야 한다 (평균 %.1f B/글리프)'
          % (len(gs), desc_len, desc_len / len(gs)))
    return True


def check_charmap_budget(rom):
    print('\n=== charmap 예산 ===')
    tab = charmap.extract(rom)
    print('  엔트리 %d개, 저장 위치 블록 %08X +%04X (길이 불변으로 교체)'
          % (len(tab), charmap.BLOCK_ROM, charmap.TABLE_OFFSET))
    # 쓰면 안 되는 코드
    banned = set(range(0x61, 0x7B)) | {0x0A, 0x20, 0xBA, 0xBD, 0xBF, 0x00}
    avail = [c for c in range(0x21, 0x100) if c not in banned]
    print('  쓸 수 없는 코드: 0x61-0x7A(단일케이스 접힘), 0x0A/0x20/0xBA/0xBD/0xBF/0x00')
    print('  가용 1바이트 코드 %d개 -> 95칸 배정에 충분' % len(avail))
    keep = [ord(c) for c in ".,!?'-"]
    print('  유지 권장 비한글 %d칸 (%s) -> 자모 가용 %d칸'
          % (len(keep), ' '.join(chr(c) for c in keep), len(tab) - len(keep)))
    return len(avail) >= len(tab)


def main():
    rom = project.load_rom()
    ok = True
    ok &= check_code_writes(rom)
    ok &= check_font_budget(rom)
    ok &= check_charmap_budget(rom)
    print('\n계획 검증: %s' % ('통과' if ok else '실패'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
