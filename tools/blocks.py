"""애셋 뱅크의 rzip 블록 인덱스를 만든다.

블록은 정렬이 없으므로 1바이트씩 훑되, 블록을 찾으면 그 크기만큼 건너뛴다
(체이닝). 4바이트 정렬을 가정하면 블록 하나를 놓칠 때 그 뒤가 통째로 날아간다 —
초기 조사에서 커버리지가 36.7% 에 그쳤던 원인이다.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import rzip

ROOT = project.ROOT


def scan(data, lo, hi, keep_raw=False):
    """[(rom_off, comp_size, raw_size)] 와, keep_raw 면 원본 바이트 목록도 반환."""
    blocks = []
    raws = []
    p = lo
    while p < hi - 8:
        r = rzip.decode_at(data, p)
        if r is not None:
            used, raw = r
            blocks.append((p, used, len(raw)))
            if keep_raw:
                raws.append(raw)
            p += used
        else:
            p += 1
    return (blocks, raws) if keep_raw else (blocks, None)


# ★비압축 애셋 영역 안에도 rzip 블록이 있다. 메인메뉴·힌트 문구·성인 경고·러블팩 안내가
#   전부 여기 들어 있었다 (`0x3F88270` 힌트 7개 / `0x3F8AB60` 메뉴 전부).
#   「비압축 영역」이라는 이름에 속아 평문 검색만 하다가 한참을 놓쳤다.
#   ★새 블록은 **인덱스 뒤에 붙인다** — 앞 인덱스가 밀리면 id 대장(extract/ids.json)이 깨진다.
EXTRA_RANGES = [(0x3F82000, 0x3F8C000)]


def build_index(rom_path=None, out_dir=None):
    cfg = project.load_config()
    data = project.load_rom(rom_path)
    lo = project.cint(cfg['rzip']['scan_range']['start'])
    hi = project.cint(cfg['rzip']['scan_range']['end'])
    blocks, raws = scan(data, lo, hi, keep_raw=True)

    out_dir = out_dir or os.path.join(ROOT, 'extract')
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'blocks.json'), 'w', encoding='utf-8') as f:
        json.dump(blocks, f)
    blob = b''.join(raws)
    with open(os.path.join(out_dir, 'raw.bin'), 'wb') as f:
        f.write(blob)

    exp = cfg['rzip']
    stats = {
        'blocks': len(blocks),
        'compressed_bytes': sum(b[1] for b in blocks),
        'raw_bytes': sum(b[2] for b in blocks),
    }
    mismatch = []
    if stats['blocks'] != exp['expected_blocks']:
        mismatch.append('blocks %d != %d' % (stats['blocks'], exp['expected_blocks']))
    if stats['compressed_bytes'] != exp['expected_compressed_bytes']:
        mismatch.append('compressed %d != %d' % (stats['compressed_bytes'],
                                                 exp['expected_compressed_bytes']))
    if stats['raw_bytes'] != exp['expected_raw_bytes']:
        mismatch.append('raw %d != %d' % (stats['raw_bytes'], exp['expected_raw_bytes']))
    if mismatch:
        raise RuntimeError('추출 결과가 config/rom.json 의 기대값과 다르다:\n  '
                           + '\n  '.join(mismatch))

    # --- 추가 영역 (검증 뒤에 붙인다: 기대값은 본 영역 기준이다) ---
    n_main = len(blocks)
    for lo, hi in EXTRA_RANGES:
        eb, er = scan(data, lo, hi, keep_raw=True)
        blocks.extend(eb)
        raws.extend(er)
    if len(blocks) > n_main:
        with open(os.path.join(out_dir, 'blocks.json'), 'w', encoding='utf-8') as f:
            json.dump(blocks, f)
        with open(os.path.join(out_dir, 'raw.bin'), 'wb') as f:
            f.write(b''.join(raws))
        stats['extra_blocks'] = len(blocks) - n_main
        stats['blocks'] = len(blocks)
        stats['raw_bytes'] = sum(b[2] for b in blocks)
    return blocks, stats


def blob_offsets(blocks):
    """블록 인덱스 -> raw.bin 안에서의 시작 오프셋."""
    starts = []
    acc = 0
    for _rom, _cs, rs in blocks:
        starts.append(acc)
        acc += rs
    return starts


if __name__ == '__main__':
    b, s = build_index()
    print('rzip 블록 %d개' % s['blocks'])
    print('  압축 %d B (%.2f MB)' % (s['compressed_bytes'], s['compressed_bytes'] / 1048576))
    print('  원본 %d B (%.2f MB)' % (s['raw_bytes'], s['raw_bytes'] / 1048576))
    print('  -> extract/blocks.json, extract/raw.bin')
