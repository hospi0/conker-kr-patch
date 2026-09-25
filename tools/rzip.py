"""Rare 'rzip' 코덱.

포맷:  [BE32 원본크기][raw deflate 스트림]
       gzip 에서 헤더·트레일러만 제거한 것. 매직 바이트가 없다.
       그래서 시그니처 스캔으로는 절대 찾을 수 없고, 크기 필드 후보마다
       raw inflate 를 시도해야 한다.

블록은 정렬이 없고 빈틈없이 연속한다 (off + comp_size == 다음 블록 off).
"""
import struct
import zlib

HEADER_SIZE = 4
WBITS = -15
MIN_RAW = 0x20
MAX_RAW = 0x800000


class RzipError(Exception):
    pass


def decode_at(data, pos, max_window=0x800000):
    """pos 에서 rzip 블록을 읽는다.

    성공하면 (comp_size, raw_bytes) 를 돌려준다. comp_size 는 헤더 4바이트를 포함한다.
    유효한 블록이 아니면 None. 예외를 성공으로 흡수하지 않는다.
    """
    if pos + HEADER_SIZE + 2 > len(data):
        return None
    size = struct.unpack('>I', data[pos:pos + HEADER_SIZE])[0]
    if not (MIN_RAW <= size <= MAX_RAW):
        return None
    window = min(size + 0x40000, max_window)
    chunk = data[pos + HEADER_SIZE: pos + HEADER_SIZE + window]
    obj = zlib.decompressobj(WBITS)
    try:
        out = obj.decompress(chunk, size + 16)
    except zlib.error:
        return None
    if len(out) != size or not obj.eof:
        return None
    used = HEADER_SIZE + (len(chunk) - len(obj.unused_data))
    return used, out


try:
    import zopfli.zlib as _zopfli
except ImportError:
    _zopfli = None


def deflate_raw(raw, iterations=100):
    """raw deflate. zopfli 가 있으면 그것을 쓴다.

    zlib 은 Rare 의 인코더보다 나쁠 때가 있어 원본 크기를 못 맞추는 블록이 있다
    (예: 블록 66 은 무수정 재압축도 zlib 최선이 +1 B). zopfli 는 -40 B 수준으로 이긴다.
    """
    if _zopfli is not None:
        c = _zopfli.compress(raw, numiterations=iterations)
        return c[2:-4]          # zlib 헤더 2B + adler32 4B 제거
    co = zlib.compressobj(9, zlib.DEFLATED, WBITS)
    return co.compress(raw) + co.flush()


def encode(raw, iterations=100):
    """rzip 블록을 만든다. 원본과 같은 바이트를 보장하지는 않는다.

    재삽입에서는 반드시 원본 comp_size 이하인지 확인할 것
    (블록 시작 위치가 테이블로 고정이라 늘릴 수 없다).
    """
    return struct.pack('>I', len(raw)) + deflate_raw(raw, iterations)


def has_zopfli():
    return _zopfli is not None


def roundtrip_ok(data, pos):
    """decode → encode → decode 로 의미 동등성을 확인한다."""
    r = decode_at(data, pos)
    if r is None:
        return False
    _, raw = r
    blob = encode(raw)
    r2 = decode_at(blob, 0)
    return r2 is not None and r2[1] == raw
