"""Project64 .pj 세이브스테이트 -> RDRAM.

헤더:
    0x00  u32 magic
    0x04  u32 RdramSize      (0x800000)
    0x08  0x40  ROM 헤더 (32비트 워드 바이트역순으로 저장)
    ...   레지스터 블록
    ...   RDRAM (RdramSize 바이트)

RDRAM 이 그대로 들어 있는지 워드역순인지는 원본 부트 세그먼트와 대조해 판정한다.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

RAM = 0x80000000


def swap32(b):
    a = bytearray(b)
    for i in range(0, len(a) - 3, 4):
        a[i:i + 4] = a[i:i + 4][::-1]
    return bytes(a)


def load(path, rom=None):
    with open(path, 'rb') as f:
        d = f.read()
    magic, rdram_size = struct.unpack('<II', d[:8])
    rom = project.load_rom() if rom is None else rom

    # 부트 세그먼트(ROM 0x2000)로 RDRAM 시작 오프셋과 바이트순서를 동시에 판정한다
    probe = rom[0x2000:0x2040]
    for name, conv in (('raw', lambda x: x), ('swap32', swap32)):
        buf = conv(d)
        i = buf.find(probe)
        if i >= 0 and i > 0x100:
            base = i - 0x2000
            if base + rdram_size <= len(buf):
                ram = buf[base:base + rdram_size]
                if ram[0x2000:0x2040] == probe:
                    return {
                        'magic': magic, 'rdram_size': rdram_size,
                        'byteorder': name, 'rdram_offset': base,
                        'rdram': ram, 'header': d[:0x100],
                    }
    raise RuntimeError('RDRAM 을 찾지 못했다 (magic=%08X size=%08X, 파일 %d B)'
                       % (magic, rdram_size, len(d)))


def main():
    path = sys.argv[1]
    st = load(path)
    print('magic %08X  RdramSize %08X  byteorder %s  RDRAM offset %08X'
          % (st['magic'], st['rdram_size'], st['byteorder'], st['rdram_offset']))
    out = os.path.join(project.ROOT, 'work',
                       os.path.splitext(os.path.basename(path))[0] + '_rdram.bin')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'wb') as f:
        f.write(st['rdram'])
    print('-> %s' % os.path.relpath(out, project.ROOT))

    rom = project.load_rom()
    cfg = project.load_config()['font']
    fr = project.cint(cfg['runtime_ram'])
    fs = project.cint(cfg['rom_start'])
    ram = st['rdram']
    print('폰트 런타임 사본 %08X 일치: %s'
          % (fr, ram[fr - RAM:fr - RAM + 0x40] == rom[fs:fs + 0x40]))


if __name__ == '__main__':
    main()
