"""문자 매핑 테이블(글리프 인덱스 -> 문자코드, 95바이트)의 저장 위치를 찾는다."""
import bisect
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

RAM = 0x80000000
TABLE_RAM = 0x80085930
TABLE_LEN = 96          # 95 + 종단 0x00


def main():
    ram = open(os.path.join(project.ROOT, 'work', 'rdram.bin'), 'rb').read()
    tab = ram[TABLE_RAM - RAM: TABLE_RAM - RAM + TABLE_LEN]
    print('테이블 (%d B): %s' % (len(tab), tab.hex()))

    rom = project.load_rom()
    print('\nROM 평문 검색      :', ('%08X' % rom.find(tab[:40])) if rom.find(tab[:40]) >= 0 else '없음')

    blob_path = os.path.join(project.ROOT, 'extract', 'raw.bin')
    idx_path = os.path.join(project.ROOT, 'extract', 'blocks.json')
    if not os.path.exists(blob_path):
        print('extract/raw.bin 이 없다. 먼저 python tools/blocks.py 실행.')
        return
    blob = open(blob_path, 'rb').read()
    idx = json.load(open(idx_path))
    starts = []
    acc = 0
    for _rom, _cs, rs in idx:
        starts.append(acc)
        acc += rs

    for probe_len, label in ((40, '앞 40B'), (TABLE_LEN, '전체')):
        i = blob.find(tab[:probe_len])
        if i < 0:
            print('압축해제 검색(%s): 없음' % label)
            continue
        k = bisect.bisect_right(starts, i) - 1
        rom_off, cs, rs = idx[k]
        print('압축해제 검색(%s): blob +%08X  -> 블록 %d (ROM %08X, raw %d) 안의 +%X'
              % (label, i, k, rom_off, rs, i - starts[k]))

    # 부분 일치도 확인: 영문/숫자 구간만
    core = tab[:36]
    n = 0
    i = blob.find(core)
    while i >= 0 and n < 5:
        k = bisect.bisect_right(starts, i) - 1
        print('   core(36B) hit: blob +%08X  블록 %d ROM %08X +%X'
              % (i, k, idx[k][0], i - starts[k]))
        n += 1
        i = blob.find(core, i + 1)
    if n == 0:
        print('   core(36B) 도 없음 -> 런타임에 만들어지는 테이블일 가능성')


if __name__ == '__main__':
    main()
