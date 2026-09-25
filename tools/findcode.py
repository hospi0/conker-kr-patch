"""디버거에서 본 명령열을 RDRAM 덤프에서 찾는다.

Project64 가 보여주는 실행 주소(예: 0x1501xxxx)는 TLB 매핑된 가상주소라
RDRAM 오프셋과 직접 대응하지 않는다. 명령 바이트로 찾아야 물리 위치가 나온다.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

RAM_BASE = 0x80000000


def mips_words(asm_words):
    return b''.join(struct.pack('>I', w) for w in asm_words)


def find(ram, words, label=''):
    pat = mips_words(words)
    hits = []
    i = ram.find(pat)
    while i >= 0:
        hits.append(RAM_BASE + i)
        i = ram.find(pat, i + 1)
    print('%-28s %d hit(s)  %s' % (label or '(pattern)', len(hits),
                                   ['%08X' % h for h in hits[:8]]))
    return hits


if __name__ == '__main__':
    ram = open(os.path.join(project.ROOT, 'work', 'rdram.bin'), 'rb').read()

    # 디버거 화면의 15015A78 부터 (LBU T7,0(S3) / SLL S0,A3,2 / ADDU T6,T5,S0 / ADDIU T8,T7,1 / SB T8,0(T6))
    seq = [0x926F0000, 0x00078080, 0x01B07021, 0x25F80001, 0xA1D80000]
    hits = find(ram, seq, 'font-setup @15015A78')

    if not hits:
        # 앞 3개만으로 완화
        find(ram, seq[:3], '  relaxed (3 words)')
        find(ram, seq[:2], '  relaxed (2 words)')
    else:
        a = hits[0]
        print('\n=> RDRAM 위치 %08X  (디버거 표기 15015A78 과의 차 %08X)'
              % (a, (a - 0x15015A78) & 0xFFFFFFFF))
