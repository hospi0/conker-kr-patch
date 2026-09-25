"""부팅 시 폰트 전처리 루틴을 RDRAM 덤프에서 찾아 디스어셈블한다.

디버거(P64)에서 본 시작 명령열 (VA 0x15015A78):
    LBU   T7, 0(S3)
    SLL   S0, A3, 2
    ADDU  T6, T5, S0
    ADDIU T8, T7, 1
    SB    T8, 0(T6)
"""
import os
import struct
import sys

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS64, CS_MODE_BIG_ENDIAN

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

RAM = 0x80000000
SEQ = [0x926F0000, 0x00078080, 0x01B07021, 0x25F80001, 0xA1D80000]


def find_seq(ram, words):
    pat = b''.join(struct.pack('>I', w) for w in words)
    hits = []
    i = ram.find(pat)
    while i >= 0:
        hits.append(i)
        i = ram.find(pat, i + 1)
    return hits


def dis(ram, addr, count, back=0):
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS64 | CS_MODE_BIG_ENDIAN)
    md.skipdata = True
    s = addr - RAM - back * 4
    for ins in md.disasm(ram[s:s + (count + back) * 4], RAM + s):
        w = int.from_bytes(ram[ins.address - RAM:ins.address - RAM + 4], 'big')
        print('%08X  %08X  %-9s %s' % (ins.address, w, ins.mnemonic, ins.op_str))


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else 'hard_rdram.bin'
    ram = open(os.path.join(project.ROOT, 'work', name), 'rb').read()

    for n in (5, 4, 3, 2):
        hits = find_seq(ram, SEQ[:n])
        print('시작 %d워드 일치: %d곳  %s'
              % (n, len(hits), ['%08X' % (RAM + h) for h in hits[:6]]))
        if hits:
            addr = RAM + hits[0]
            print('\n=== %08X (VA 0x15015A78 대응) 앞뒤 ===' % addr)
            back = int(sys.argv[2]) if len(sys.argv) > 2 else 40
            cnt = int(sys.argv[3]) if len(sys.argv) > 3 else 90
            dis(ram, addr, cnt, back)
            return
    print('찾지 못했다.')


if __name__ == '__main__':
    main()
