"""RDRAM 의 코드 주소가 어느 rzip 블록에서 왔는지 찾는다."""
import bisect
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

RAM = 0x80000000


def main():
    dump = sys.argv[1]
    addr = int(sys.argv[2], 16)
    span = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x40

    ram = open(os.path.join(project.ROOT, 'work', dump), 'rb').read()
    sig = ram[addr - RAM: addr - RAM + span]
    print('%08X 에서 %d B: %s...' % (addr, span, sig[:16].hex()))

    rom = project.load_rom()
    i = rom.find(sig)
    print('ROM 평문: %s' % (('%08X' % i) if i >= 0 else '없음'))

    blob = open(os.path.join(project.ROOT, 'extract', 'raw.bin'), 'rb').read()
    idx = json.load(open(os.path.join(project.ROOT, 'extract', 'blocks.json')))
    starts = []
    acc = 0
    for _r, _c, rs in idx:
        starts.append(acc)
        acc += rs

    j = blob.find(sig)
    if j < 0:
        print('압축 해제 데이터: 없음')
        return
    n = 0
    while j >= 0 and n < 4:
        k = bisect.bisect_right(starts, j) - 1
        rom_off, cs, rs = idx[k]
        off_in = j - starts[k]
        print('압축 해제: blob +%08X -> 블록 %d (ROM %08X, comp %d, raw %d) 안의 +%X'
              % (j, k, rom_off, cs, rs, off_in))
        print('   => 이 블록의 로드 베이스 = %08X' % (addr - off_in))
        n += 1
        j = blob.find(sig, j + 1)


if __name__ == '__main__':
    main()
