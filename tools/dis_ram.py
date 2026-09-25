"""RDRAM 덤프의 임의 주소를 디스어셈블한다."""
import os
import sys

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS64, CS_MODE_BIG_ENDIAN

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

RAM = 0x80000000


def dis(ram, addr, count, back=0, mark=None):
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS64 | CS_MODE_BIG_ENDIAN)
    md.skipdata = True
    s = addr - RAM - back * 4
    for ins in md.disasm(ram[s:s + (count + back) * 4], RAM + s):
        w = int.from_bytes(ram[ins.address - RAM:ins.address - RAM + 4], 'big')
        m = '  <==' if mark and ins.address == mark else ''
        print('%08X  %08X  %-9s %s%s' % (ins.address, w, ins.mnemonic, ins.op_str, m))


if __name__ == '__main__':
    name = sys.argv[1]
    addr = int(sys.argv[2], 16)
    cnt = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    back = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    ram = open(os.path.join(project.ROOT, 'work', name), 'rb').read()
    dis(ram, addr, cnt, back)
