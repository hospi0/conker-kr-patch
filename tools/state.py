"""RetroArch (Mupen64Plus-Next) 세이브스테이트 -> RDRAM.

스테이트는 '#RZIPv' 컨테이너:
    헤더 20B: "#RZIPv" + ver + pad + LE32 chunk_size + LE64 total
    이후 [LE32 압축크기][zlib 데이터] 청크 반복
푼 결과는 RASTATE / MEM / M64+SAVE + ROM MD5 로 시작한다.

RDRAM 은 스테이트 오프셋 0x1CC 부터 8MB, 32비트 워드 바이트역순으로 들어 있다.
되돌려야 CPU 가 보는 바이트가 된다.
"""
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project


class StateError(Exception):
    pass


def decompress_state(path=None):
    path = path or project.load_local().get('savestate_path')
    if not path:
        raise StateError('세이브스테이트 경로가 없다 (config/local.json 의 savestate_path).')
    with open(path, 'rb') as f:
        d = f.read()
    if d[:6] != b'#RZIPv':
        raise StateError('RZIP 스테이트가 아니다: %r' % d[:8])
    chunk_size = struct.unpack('<I', d[8:12])[0]
    total = struct.unpack('<Q', d[12:20])[0]
    out = bytearray()
    p = 20
    while p < len(d) and len(out) < total:
        csz = struct.unpack('<I', d[p:p + 4])[0]
        p += 4
        if csz == 0:
            break
        out.extend(zlib.decompress(d[p:p + csz]))
        p += csz
    if len(out) != total:
        raise StateError('스테이트 크기 불일치: %d != %d' % (len(out), total))
    return bytes(out), {'chunk_size': chunk_size, 'total': total}


def extract_rdram(state_bytes):
    cfg = project.load_config()['savestate']
    off = project.cint(cfg['rdram_offset_in_state'])
    size = project.cint(cfg['rdram_size'])
    raw = bytearray(state_bytes[off:off + size])
    if len(raw) != size:
        raise StateError('RDRAM 영역이 부족하다: %d < %d' % (len(raw), size))
    if cfg['word_swap']:
        for i in range(0, len(raw) - 3, 4):
            raw[i:i + 4] = raw[i:i + 4][::-1]
    return bytes(raw)


def verify_against_rom(rdram, rom):
    """RAM = ROM + 0x80000000 인 부트 세그먼트로 정렬을 확인한다."""
    return rdram[0x2000:0x2020] == rom[0x2000:0x2020]


def ram_read(rdram, addr, n):
    return rdram[addr - 0x80000000: addr - 0x80000000 + n]


if __name__ == '__main__':
    st, meta = decompress_state(sys.argv[1] if len(sys.argv) > 1 else None)
    print('스테이트 %d B (chunk=%d)' % (meta['total'], meta['chunk_size']))
    rd = extract_rdram(st)
    rom = project.load_rom()
    print('RDRAM %d B, 부트세그먼트 정합: %s' % (len(rd), verify_against_rom(rd, rom)))
    out = os.path.join(project.ROOT, 'work', 'rdram.bin')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'wb') as f:
        f.write(rd)
    print('-> work/rdram.bin')
    cfg = project.load_config()['font']
    fr = project.cint(cfg['runtime_ram'])
    fs = project.cint(cfg['rom_start'])
    same = ram_read(rd, fr, 0x40) == rom[fs:fs + 0x40]
    print('폰트 런타임 사본 %08X 일치: %s' % (fr, same))
