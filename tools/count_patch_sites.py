"""패치 지점이 압축 해제 데이터 전체에서 몇 곳인지 센다.

코드는 TLB 오버레이라 RAM 주소가 바뀐다. ROM(=rzip 블록) 쪽이 유일한 진실이므로
27MB 압축 해제 데이터 전체에서 같은 명령 문맥이 몇 번 나오는지 확인해야
「한 곳만 고치면 되는가」를 판정할 수 있다.
"""
import bisect
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

# 패치 대상과 그 앞뒤 문맥 (블록 66 로드베이스 0x802D0000 기준)
SITES = [
    (0x210, 'draw: lbu xoff',
     [0x8FA40130, 0x90990002, 0x3C014F80, 0x44992000]),      # 앞 1 + 대상 + 뒤 2
    (0xB2C, 'layout: lbu xoff',
     [0x904B0000, 0x904D0002, 0x3C188008, 0x014B6021]),
]


def main():
    blob = open(os.path.join(project.ROOT, 'extract', 'raw.bin'), 'rb').read()
    idx = json.load(open(os.path.join(project.ROOT, 'extract', 'blocks.json')))
    starts = []
    acc = 0
    for _r, _c, rs in idx:
        starts.append(acc)
        acc += rs

    rom = project.load_rom()
    print('압축 해제 데이터 %d B (%.1f MB), 블록 %d개\n'
          % (len(blob), len(blob) / 1048576, len(idx)))

    for off, label, words in SITES:
        pat = b''.join(struct.pack('>I', w) for w in words)
        hits = []
        i = blob.find(pat)
        while i >= 0:
            hits.append(i)
            i = blob.find(pat, i + 1)
        print('%-20s 문맥 %d워드 -> 압축해제 전체에서 %d곳' % (label, len(words), len(hits)))
        for h in hits:
            k = bisect.bisect_right(starts, h) - 1
            rom_off, cs, rs = idx[k]
            in_off = h - starts[k]
            # 대상 명령은 문맥의 두번째 워드
            target = in_off + 4
            print('     블록 %-4d ROM %08X  블록내 +%04X  (패치할 opcode 바이트 +%04X)'
                  % (k, rom_off, in_off, target))
        # ROM 평문에도 있는지
        j = rom.find(pat)
        print('     ROM 평문: %s' % (('%08X' % j) if j >= 0 else '없음'))
        print()


if __name__ == '__main__':
    main()
