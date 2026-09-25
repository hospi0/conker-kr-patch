"""프로젝트 공통: 설정 로드와 원본 식별 검증.

원본 경로는 코드에 박지 않는다. 우선순위:
  1) 함수 인자
  2) 환경변수 CONKER_ROM
  3) config/local.json 의 rom_path
"""
import hashlib
import json
import os
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(ROOT, 'config')


class RomIdentityError(Exception):
    pass


def load_config():
    with open(os.path.join(CONFIG_DIR, 'rom.json'), encoding='utf-8') as f:
        return json.load(f)


def load_local():
    p = os.path.join(CONFIG_DIR, 'local.json')
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    return {}


def resolve_rom_path(path=None):
    if path:
        return path
    env = os.environ.get('CONKER_ROM')
    if env:
        return env
    local = load_local().get('rom_path')
    if local:
        return local
    raise RomIdentityError(
        '원본 ROM 경로를 찾을 수 없다. 인자, 환경변수 CONKER_ROM, '
        '또는 config/local.json 의 rom_path 중 하나로 지정할 것.')


def load_rom(path=None, verify=True):
    """원본을 읽고 리비전 식별 해시를 검증한다. 다르면 명확히 실패한다."""
    p = resolve_rom_path(path)
    with open(p, 'rb') as f:
        d = f.read()
    if verify:
        verify_identity(d, p)
    return d


def verify_identity(data, label='<bytes>'):
    cfg = load_config()['rom']
    problems = []
    if len(data) != cfg['size']:
        problems.append('size %d != %d' % (len(data), cfg['size']))
    crc = '%08X' % (zlib.crc32(data) & 0xFFFFFFFF)
    if crc != cfg['crc32']:
        problems.append('crc32 %s != %s' % (crc, cfg['crc32']))
    md5 = hashlib.md5(data).hexdigest().upper()
    if md5 != cfg['md5']:
        problems.append('md5 %s != %s' % (md5, cfg['md5']))
    sha1 = hashlib.sha1(data).hexdigest().upper()
    if sha1 != cfg['sha1']:
        problems.append('sha1 %s != %s' % (sha1, cfg['sha1']))
    if problems:
        raise RomIdentityError(
            '지원하지 않는 원본이다 (%s):\n  %s\n지원 리비전: %s'
            % (label, '\n  '.join(problems), cfg['title']))
    return True


def rom_identity(data):
    return {
        'size': len(data),
        'crc32': '%08X' % (zlib.crc32(data) & 0xFFFFFFFF),
        'md5': hashlib.md5(data).hexdigest().upper(),
        'sha1': hashlib.sha1(data).hexdigest().upper(),
    }


def cint(v):
    """config 의 '0x...' 문자열이나 int 를 int 로."""
    if isinstance(v, int):
        return v
    return int(v, 0)


if __name__ == '__main__':
    import sys
    d = load_rom(sys.argv[1] if len(sys.argv) > 1 else None)
    print('원본 확인 OK')
    for k, v in rom_identity(d).items():
        print('  %-6s %s' % (k, v))
