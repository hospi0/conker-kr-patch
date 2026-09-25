"""번역 작업 파일 생성 — 말풍선(메시지) 단위로 묶어 30 KB 씩 나눈다.

    trans/conker_kr_001.json ...

각 자막은 `en`(원문) / `ko`(번역 자리, 비어 있음) 한 쌍이다.
예산 두 개가 함께 들어간다 — 이게 없으면 번역이 들어갈 수 없다.

    bytes  그 자막의 **바이트 한도**. 원문과 같은 길이로 채워 넣어야 한다
           (rzip 블록을 키울 수 없다). 모자라면 널 글리프로 패딩하므로 이하면 된다.
           한글은 받침 있으면 3바이트, 없으면 2바이트. 공백·문장부호·줄바꿈은 1바이트.
    width  그 **말풍선의 줄 폭 한도**. 한글 한 글자 = 13, 공백 = 4.
           말풍선은 메시지에 속한 자막 전체의 최대 줄 폭으로 정해지므로 한도가 말풍선 단위다
           (docs/bubble-width.md). `\\n` 으로 나뉜 **각 줄**이 이 한도 이하여야 한다.

메시지 안의 자막은 화면에 차례로 뜨는 한 말풍선의 페이지들이다 — 맥락이 이어진다.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import corpus

CHUNK = 30 * 1024
OUT_DIR = os.path.join(project.ROOT, 'trans')

NOTE = ('ko 에 번역을 넣으세요. bytes=자막의 바이트 한도(한글 받침o 3B/받침x 2B, 그 외 1B), '
        'width=말풍선의 줄 폭 한도(한글 1자=13, 공백=4, \\n 으로 나뉜 각 줄이 이하일 것). '
        'id 는 건드리지 마세요.')


def build():
    strings = corpus.extract(verbose=False)
    corpus.add_budgets(strings)
    corpus.assign_ids(strings)          # ★순서가 아니라 대장에서
    msgs = corpus.group_messages(strings)
    return msgs


def main():
    msgs = build()
    os.makedirs(OUT_DIR, exist_ok=True)
    for old in os.listdir(OUT_DIR):
        if old.startswith('conker_kr_') and old.endswith('.json'):
            os.remove(os.path.join(OUT_DIR, old))

    part = []
    files = []

    def serialize(ms, n):
        return json.dumps({'_': NOTE, 'part': n, 'messages': ms},
                          ensure_ascii=False, indent=1)

    def flush():
        if not part:
            return
        n = len(files) + 1
        p = os.path.join(OUT_DIR, 'conker_kr_%03d.json' % n)
        # newline='\n' — 텍스트 모드가 CRLF 로 늘리면 파일이 목표보다 6% 커진다
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(serialize(part, n))
        files.append((p, os.path.getsize(p), sum(len(m['subs']) for m in part)))

    for m in msgs:
        entry = {
            'id': m[0]['msg'],
            'width': m[0]['msg_wmax'],
            'subs': [{'id': r['id'], 'bytes': r['bytes'], 'en': r['text'], 'ko': ''}
                     for r in m],
        }
        # ★크기는 **파일 전체를 실제 출력 형태로 직렬화해서** 잰다.
        #   엔트리 단위로 근사하면 들여쓰기·래퍼 때문에 25% 어긋난다(30 KB 목표가 37 KB 로 나왔다).
        if part and len(serialize(part + [entry], len(files) + 1).encode('utf-8')) > CHUNK:
            flush()
            part = []
        part.append(entry)
    flush()

    tot = sum(f[2] for f in files)
    print('메시지 %d개 / 자막 %d개 -> 파일 %d개' % (len(msgs), tot, len(files)))
    for p, sz, n in files:
        print('  %-28s %6.1f KB  자막 %d개'
              % (os.path.relpath(p, project.ROOT), sz / 1024, n))


if __name__ == '__main__':
    main()
