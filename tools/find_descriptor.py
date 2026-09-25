"""폰트 영역 서술자(ROM start/end 8바이트)의 저장 위치를 찾는다."""
import bisect
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project


def locate(blob, idx, starts, pat, label):
    i = blob.find(pat)
    n = 0
    while i >= 0 and n < 6:
        k = bisect.bisect_right(starts, i) - 1
        rom_off, cs, rs = idx[k]
        print('  %-22s blob +%08X  -> 블록 %d (ROM %08X, comp %d, raw %d) 안의 +%X'
              % (label, i, k, rom_off, cs, rs, i - starts[k]))
        n += 1
        i = blob.find(pat, i + 1)
    if n == 0:
        print('  %-22s 없음' % label)
    return n


def main():
    rom = project.load_rom()
    cfg = project.load_config()['font']
    f_start = project.cint(cfg['rom_start'])
    desc = struct.pack('>II', f_start, 0x00042450)
    print('서술자 바이트: %s' % desc.hex())

    i = rom.find(desc)
    print('\nROM 평문 검색: %s' % (('%08X' % i) if i >= 0 else '없음'))

    blob_path = os.path.join(project.ROOT, 'extract', 'raw.bin')
    if not os.path.exists(blob_path):
        print('extract/raw.bin 이 없다. python tools/blocks.py 먼저.')
        return
    blob = open(blob_path, 'rb').read()
    idx = json.load(open(os.path.join(project.ROOT, 'extract', 'blocks.json')))
    starts = []
    acc = 0
    for _r, _c, rs in idx:
        starts.append(acc)
        acc += rs

    print('\n압축 해제 데이터 검색:')
    locate(blob, idx, starts, desc, '서술자 8B')
    # 서술자 테이블 전체(뒤 4개 엔트리가 0) 로도 시도
    locate(blob, idx, starts, desc + b'\x00' * 16, '서술자 + 0 패딩')


if __name__ == '__main__':
    main()
