# Conker's Bad Fur Day (N64 북미판) 한글 패치

> **내려받기:** [릴리즈 페이지](https://github.com/hospi0/conker-kr-patch/releases/latest) — 최신 v0.9. 적용 방법·원본 MD5 는 패치 묶음의 readme 에 있습니다.
>
> 이 저장소에는 도구·번역 텍스트·작업 문서만 있습니다(ROM·빌드 결과물 없음).

---

# Conker's Bad Fur Day (N64) 한글 패치

대상 원본: **Conker's Bad Fur Day (USA)** — CRC32 `CE8CC172` / 64MB / CIC-6105
(전체 식별 해시는 `config/rom.json`)

현재 단계: **조사 완료, 실행 계획 확정** (`docs/plan.md`). 번역·빌드는 시작하지 않았다.

## 시작하기

```bash
cp config/local.example.json config/local.json    # 각자 환경 경로를 넣는다
python tools/selftest.py                          # 라운드트립·불변식 검증
```

원본 ROM 경로는 코드에 박지 않는다. 우선순위는
인자 → 환경변수 `CONKER_ROM` → `config/local.json` 의 `rom_path`.
모든 도구는 읽기 전에 리비전 해시를 검증하고 다르면 실패한다.

## 도구

| 명령 | 하는 일 |
|---|---|
| `python tools/project.py` | 원본 식별 확인 |
| `python tools/selftest.py` | RLE·rzip 라운드트립, 폰트 체인, 문자 매핑 검증 |
| `python tools/blocks.py` | rzip 애셋 뱅크 추출 → `extract/blocks.json`, `extract/raw.bin` |
| `python tools/font.py` | 폰트 체인 요약 |
| `python tools/charmap.py` | 문자 매핑 테이블을 원본에서 추출·출력 |
| `python tools/font_budget.py` | 폰트 영역 예산 측정 |
| `python tools/glyph_addrs.py [idx...]` | 글리프별 ROM/RAM 주소 + 문자코드 (디버거용) |
| `python tools/state.py` | RetroArch 세이브스테이트 → `work/rdram.bin` |
| `python tools/glyphtable.py` | 부팅 전처리 구조(글리프 메타 배열) 조사 |
| `python tools/findcode.py` | 디버거에서 본 명령열을 RDRAM 에서 역추적 |
| `python tools/pjstate.py <file.pj>` | Project64 세이브스테이트 → `work/*_rdram.bin` |
| `python tools/block507.py` | 편집 지점(서술자·charmap·버퍼 포인터) 위치 검증 |
| `python tools/font_descriptor.py` | 폰트 서술자 테이블·예산 확인 |
| `python tools/dis_ram.py <dump> <addr>` | RDRAM 임의 주소 디스어셈블 |
| `python tools/find_renderer.py <dump>` | 글리프 메타를 읽는 렌더러 코드 찾기 |
| `python tools/locate_code.py <dump> <addr>` | RDRAM 코드가 어느 rzip 블록인지 역추적 |
| `python tools/heap_walk.py` | 게임 힙 순회 (블록 헤더 = next/prev/inuse\|size) |
| `python tools/corpus.py` | 번역 모집단 추출 → `extract/strings.json` (자막·말풍선·예산) |
| `python tools/trans_split.py` | 번역 작업 파일 생성 → `trans/conker_kr_*.json` (말풍선 단위, 30 KB) |
| `python tools/trans_check.py` | 번역 검증 (인코딩·바이트·폭·부분번역). 넣기 전에 반드시 통과할 것 |
| `python tools/bubble.py` | 말풍선 폭 모델 자체검증 (실기 스테이트 5종 대조) |
| `python tools/linewidth.py` | 줄 폭 계산 (단일 문자열) |

빌드 스크립트는 아직 없다. **빌드는 만들어지면 매번 허락을 받고 실행한다.**

## 번역 작업 흐름

```bash
python tools/corpus.py         # 모집단 추출 (자막 3,205 / 말풍선 973)
python tools/trans_split.py    # trans/*.json 생성 — ko 는 비어 있다
#   ... trans/*.json 의 ko 를 채운다 ...
python tools/trans_check.py    # 인코딩·바이트·폭·부분번역 검증
python tools/build_kr.py       # 빌드 (매번 허락)
```

⚠️`trans_split.py` 는 `ko` 를 비운 채로 새로 만든다. **번역 도중에 다시 돌리지 말 것.**
⚠️**말풍선은 메시지 단위로 통째 번역해야 한다.** 한 자막이라도 영문으로 남기면 그 영문이
자모 글리프로 측정되어 말풍선이 부푼다 — `trans_check.py` 가 「부분번역」으로 잡는다.

## 문서

| 문서 | 내용 |
|---|---|
| [`docs/survey.md`](docs/survey.md) | ROM 맵, rzip 코덱, 애셋 컨테이너, 오디오, 텍스트 위치 |
| [`docs/font.md`](docs/font.md) | 폰트 포맷·RLE 코덱·문자 매핑표·예산 |
| [`docs/plan.md`](docs/plan.md) | **한글화 실행 계획 — 변경 대상과 예산** |
| [`docs/bubble-width.md`](docs/bubble-width.md) | **말풍선 폭 규칙 — 번역 예산의 근거** |
| [`docs/open-questions.md`](docs/open-questions.md) | 미해결 과제 |

## 알려진 함정

- **rzip 은 매직 바이트가 없다.** 시그니처 스캔이 0건이라고 deflate 를 배제하면 안 된다.
  탐지법은 크기 필드 후보마다 raw inflate 를 시도하는 것.
- **rzip 블록은 정렬 제약이 없다.** 4바이트 정렬을 가정하면 블록 하나를 놓칠 때
  뒤가 통째로 갭이 된다. 반드시 1바이트 스캔 + 크기만큼 건너뛰기.
- **★블록은 줄일 수는 있어도 키울 수 없다.** 블록 시작 위치를 애셋 테이블이 정한다.
  실제 출시된 스페인어 패치가 rzip 블록 295개를 고치면서 **압축크기 델타 최댓값 0**
  (단 하나도 키우지 않음)을 지켰다. 검증된 하드 룰로 취급한다.
- **애셋 테이블은 오름차순 BE32 런 스캔으로 못 찾는다.** offset 과 size 가 번갈아 나온다.
- **한글화는 글리프 95칸을 전부 쓴다.** 영문 글리프를 남길 이유가 없다.
  1벌식 조합형(67자모)은 여유롭고 초성 2벌식(86자모)까지 들어간다 → 버퍼 확장 불필요.
- **★zopfli 없이는 블록을 못 되돌린다.** zlib 은 블록 66 에서 *무수정* 재압축조차
  원본보다 1 B 크다(Rare 인코더가 더 좋다). `pip install zopfli`.
- **렌더러 advance = `w + xoff` 이고 `xoff` 는 부호 없음.** 겹쳐 그리려면
  `lbu`→`lb` 2곳 패치가 필요하다 (블록 66 `+0x210`, `+0xB2C`).
- **★말풍선 폭은 「메시지 전체 자막의 최대 줄 폭」으로 정해진다.** 화면에 뜬 문장이 아니다.
  따라서 **부분 번역 상태에서 말풍선이 깨지는 것은 버그가 아니다** — 남은 영문이 자모 글리프로
  측정된다(문자당 advance 13). 예산은 줄 단위가 아니라 메시지 단위. `docs/bubble-width.md`.
- **`0xBD` 는 자막 분리자가 아니다.** 자막을 나누는 것은 `0x00` 뿐이다.
- **★버튼 아이콘·욕설 검열 기호(`0xA1`~`0xBF`)도 텍스트다.** 추출에서 빼면 그게 든 자막이
  잘려 나가고, 잘린 뒷부분이 미번역 영문으로 남아 자모로 깨진다(실기에서 `press ©` 로 발각).
  인코더도 이 범위를 그대로 통과시켜야 아이콘이 사라지지 않는다.
- **★자막 id 는 순서가 아니라 대장(`extract/ids.json`)에서 온다.** 추출기를 고쳐 문자열이
  하나만 늘어도 순서 기반 id 는 전부 밀려 번역 파일이 통째로 어긋난다.
  추출기를 고친 뒤에는 `tools/trans_resync.py` 를 돌릴 것.
- **코드는 TLB 오버레이라 `jal` 이 VA 로 인코딩된다.** RDRAM 주소로 jal 을 검색하면 0건이 나온다.
  블록마다 매핑이 다르므로, 함수 안의 기존 jal 로 그 블록의 페이지 매핑을 먼저 얻을 것.
- **폰트는 대문자만 있고 렌더러가 단일 케이스로 찍는다.** 원문의 소문자에 속으면 안 된다.
- **★매핑 테이블은 `table[glyph_index] = charcode` 다.** 방향이 반대라고 가정하고
  `table[charcode] = index` 로 검색하면 ROM·RAM 전수를 뒤져도 0건이 나온다.
- **폰트는 부팅 때 한 번만 읽힌다.** 렌더 시점에 글리프 체인을 순회하지 않으므로,
  대사 중에 폰트 주소 브레이크포인트를 걸어도 안 걸린다.
- **★한글화 편집 지점은 rzip 블록 507(ROM `0x188328`) 한 곳에 모여 있다.**
  폰트 서술자 `+0x460` · charmap `+0x2E10` · 버퍼 포인터 `+0x2E70`/`+0x2E74`.
  이 블록은 RAM `0x80082B20` 에 189,088 B 가 그대로 올라간다.
- **디버거 주소는 TLB 가상주소다.** RDRAM − VA = `0x6B2B8000`.
  jal 은 하위 26비트만 담으므로 capstone 이 `0x8...` 로 잘못 보여준다.
- **게임 중반 스테이트로 부팅 코드를 읽으려 하지 말 것.** 그 영역은 다른 오버레이로 덮인다.
- **CIC-6105 전용 CRC 재계산**이 필요하다. 일반 N64 CRC 루틴을 쓰면 안 된다.

## 선행 자료

- 디컴파일: `github.com/mkst/conker`, `github.com/x1nixmzeng/conker`
- 스페인어 패치 v1.1 / v1.1beta (blade133bo, 폰트 Mairtrus)
  — **오라클로만 사용하며 빌드 입력으로 채택하지 않는다.**

## 저장소 규칙

원본 ROM·패치 적용된 전체 이미지·원본에서 통째로 뽑은 자산은 커밋하지 않는다.
`work/`, `extract/`, `config/local.json` 은 무시 대상이다.
