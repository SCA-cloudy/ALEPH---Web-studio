# 과제 3 — Quiplet(짤·카드 스튜디오) 테스트 기록

모든 테스트는 Playwright(Chromium)로 실제 화면을 조작해 자동 검증했습니다. 스크린샷과 원본 로그는
`test-assets/results/`(화면 캡처, `log.json`), 다운로드된 파일은 `test-assets/downloads/`,
완성 이미지는 `test-assets/finished/`에 있습니다. 재실행: `python3 scripts/test_playwright.py`.

## 카드 1 — 편집과 미리보기

| 통과기준 | 확인 방법 | 결과 |
|---|---|---|
| T03-C04 PNG 로드 | `sample_portrait.png` 업로드 | PASS |
| T03-C05 JPEG 로드 | `sample_landscape.jpg` 업로드 | PASS |
| T03-C06 문구 위치 즉시 반영 | 가로 위치 슬라이더 20→80 이동, 캔버스 픽셀 변화 확인 | PASS |
| T03-C07 문구 크기 즉시 반영 | 글자 크기 슬라이더 변경, 캔버스 픽셀 변화 확인 | PASS |
| T03-C08 문구 색 즉시 반영 | 색상 `#ff0000`로 변경, 캔버스 픽셀 변화 확인 | PASS |
| T03-C09 잘못된 파일 후 기존 작업 유지 | 정상 이미지 로드 후 `fake_image.png`(텍스트를 png로 위장) 업로드 → 파일 정보 문자열 불변 | PASS |
| T03-C10 거부 이유 표시 | `fake_image.png`, `unsupported.gif` 각각 업로드 → 오류 메시지 노출 | PASS |

파일 검증은 확장자가 아니라 실제 바이트(매직 넘버: PNG `89 50 4E 47…`, JPEG `FF D8 FF`)를 확인하므로
확장자만 `.png`로 바꾼 텍스트 파일도 정확히 걸러냅니다(스크린샷: `card1_reject_fake_png.png`,
`card1_reject_gif.png`).

## 카드 2 — 화면과 파일의 일치

미리보기 캔버스와 다운로드 파일이 **같은 캔버스 객체**를 그대로 내려받도록 구현해, 두 값이 다를 수
없는 구조입니다. 실제로도 SHA-256 해시가 100% 일치함을 확인했습니다.

| 비율 | 미리보기 캔버스 SHA-256 | 다운로드 파일 SHA-256 | 결과 |
|---|---|---|---|
| 1:1 | `d6a6fed0...a3383e` | `d6a6fed0...a3383e` | PASS(T03-C11) |
| 4:5 | `50014c5e...053c13b` | `50014c5e...053c13b` | PASS(T03-C12) |
| 9:16 | `6158d9eb...c274eb` | `6158d9eb...c274eb` | PASS(T03-C13) |

테스트 조건: 두 줄짜리 검사 문구("가장자리 확인용 문구입니다 EDGE-CHECK / 두번째 줄도 있음")를
가로 중앙, 세로 90% 위치에 배치해 세 비율 모두에서 잘림·줄바꿈이 그대로 재현되는지 확인했습니다.
스크린샷: `card2_preview_all_ratios.png`.

## 카드 3 — 극단 입력 12건

| 코드 | 케이스 | 입력 문구 | 사용 이미지 | 결과 | 스크린샷 |
|---|---|---|---|---|---|
| EC01 | 매우 긴 한글 문구 | "이것은 매우 매우 매우 매우 매우 매우 매우 매우 긴 한글 문구 테스트입니다 줄바꿈이 잘 되는지 확인합니다" | 가로형 | PASS | card3_EC01.png |
| EC02 | 매우 긴 영문 문구(단어 단위 줄바꿈) | "This is a very very very very very very very long English caption used to test wrapping behavior" | 세로형 | PASS | card3_EC02.png |
| EC03 | 한글/영문 혼합 | "오늘의 MOOD는 totally 완전 랜덤 chaos 그 자체" | 투명 배경 | PASS | card3_EC03.png |
| EC04 | 명시적 줄바꿈(Enter) 3줄 | "첫째 줄\n둘째 줄\n셋째 줄" | 가로형 | PASS | card3_EC04.png |
| EC05 | 이모지 포함 | "오늘도 완전 승리 🎉🔥🥳 GG" | 세로형 | PASS | card3_EC05.png |
| EC06 | 빈 문구 | "" | 투명 배경 | PASS | card3_EC06.png |
| EC07 | 특수문자/기호 다수 | `!@#$%^&*()_+-=[]{}|;:'",.<>/?~\`` | 가로형 | PASS | card3_EC07.png |
| EC08 | 숫자+단위 혼합 | "2026년 9월 7일 오후 3:07, 할인 -87%" | 세로형 | PASS | card3_EC08.png |
| EC09 | 공백만 있는 문구 | "     "(공백 5개) | 투명 배경 | PASS | card3_EC09.png |
| EC10 | 따옴표/이스케이프 문자 | `그가 말했다: "괜찮아" \n 정말?` | 가로형 | PASS | card3_EC10.png |
| EC11 | 탭/연속 공백 혼합 | "가\t나          다" | 세로형 | PASS | card3_EC11.png |
| EC12 | 끊어쓰기 없는 매우 긴 영단어 | "Supercalifragilisticexpialidociousandalsoevenlongerwordwithnobreaks" | 투명 배경 | **FAIL→수정→PASS** | 아래 참고 |

각 케이스는 "앱이 죽지 않고 정상적으로 렌더되는가"와 "화면에 실제로 반영되는가"를 캔버스 크기/픽셀
변화로 확인했습니다(T03-C14).

### T03-C15 — 결함 전후 (EC12)

**증상**: 공백이 하나도 없는 매우 긴 영단어를 넣으면, 줄바꿈 로직이 "공백/문자 단위로만" 끊어서
해당 토큰 하나가 프레임 폭(`maxWidth`)보다 넓어도 줄을 나누지 못하고 그대로 한 줄에 그려버려서,
글자가 캔버스(=출력 이미지) 양쪽 바깥으로 잘려 나가 알아볼 수 없는 상태가 되었습니다.

- 수정 전(FAIL): `test-assets/results/card3_EC12_BEFORE_FAIL.png` — 문구가 프레임 좌우 바깥까지
  튀어나가 절반 이상이 보이지 않음.
- 원인 코드: `app.js`의 `wrapParagraph()`가 ascii 단어 토큰을 통째로 한 줄에 올려서, 토큰 자체가
  `maxWidth`보다 넓은 경우를 처리하지 못했음.
- 수정 내용: 토큰 하나의 폭이 `maxWidth`보다 넓으면 그 토큰만 글자 단위로 다시 쪼개서(강제 줄바꿈)
  일반 줄바꿈 로직에 태우도록 `expandedTokens` 처리를 추가.
- 수정 후(PASS): `test-assets/results/card3_EC12.png` — 같은 문구가 여러 줄로 정상 줄바꿈되어
  프레임 안에 온전히 보임.

같은 검사 입력(EC12, "Supercalifragilisticexpialidociousandalsoevenlongerwordwithnobreaks")으로
수정 전 FAIL → 수정 후 PASS를 재현했습니다.

### T03-C16 — 기존 편집 유지

정상 문구("삭제되면 안 되는 소중한 문구")를 입력한 뒤 위장 파일(`fake_image.png`)을 업로드해도
텍스트 입력값이 그대로 유지되는 것을 확인했습니다. (결과: PASS)

## 카드 4 — 실제 템플릿 관리

| 통과기준 | 확인 방법 | 결과 |
|---|---|---|
| T03-C17 템플릿 3개 이상 생성 | "템플릿A/B/C" 3개 저장 → 목록 3개 확인 | PASS |
| T03-C18 재로드 | "템플릿A" 불러오기 → 입력창에 원래 문구 복원 | PASS |
| T03-C19 수정 | 불러온 템플릿 문구를 수정 후 "업데이트" 클릭 → 목록 반영 | PASS |
| T03-C20 삭제 | "템플릿C" 삭제 → 목록 2개로 감소 | PASS |
| T03-C21 새로고침 후 유지 | 페이지 새로고침(`location.reload`) 후 목록 개수 동일 | PASS |

스크린샷: `card4_three_templates.png`, `card4_after_reload.png`. 템플릿은 브라우저의
`localStorage`에만 저장되며 서버로 전송되지 않습니다.

## 카드 5 — 옮겨 쓰기와 완성본

| 통과기준 | 확인 방법 | 결과 |
|---|---|---|
| T03-C22 정상 JSON 복원 | `valid_templates.json`(템플릿 3개) 가져오기 → 목록 3개로 복원 | PASS |
| T03-C23 문법 손상 JSON 거부 | `broken_syntax.json`(중괄호 미종료) 가져오기 → 오류 표시, 템플릿 개수 불변 | PASS |
| T03-C24 필수 항목 누락 JSON 거부 | `missing_required.json`(`color` 필드 누락) 가져오기 → 오류 표시, 템플릿 개수 불변 | PASS |

스크린샷: `card5_valid_import.png`, `card5_broken_import.png`, `card5_missing_field_import.png`.

### 완성 이미지 3개 (T03-C25~C27)

`test-assets/finished/`에 저장되어 있으며, 서로 다른 문구와 비율을 사용합니다.

| 파일 | 비율 | 문구 | 배경 이미지 출처 |
|---|---|---|---|
| finished_1_1x1.png | 1:1 | "오늘도 무사히" (화이트 글씨) | **커미션 작업물** — 본인이 의뢰해 받은 일러스트, 이미지 안에 작가 서명("xio")이 그대로 남아있음. 문구는 서명을 가리지 않도록 위쪽 여백에 배치. *(작가에게 확인한 실제 사용 허가 범위를 아래 빈칸에 채워 넣어야 제출용으로 완전함 — 예: 작가명/활동명, 허용 범위(개인 프로젝트·과제 게시 가능 여부, 크레딧 표기 조건 등))* → 작가: `______`, 허용 범위: `______` |
| finished_2_4x5.png | 4:5 | "오늘의 한마디 / "작게 시작해도 괜찮다"" | 본인 제작 (scripts/gen_assets.py 로 코드가 직접 그린 그라디언트+도형, 실사진 아님) |
| finished_3_9x16.png | 9:16 | "월요일의 나 vs 금요일의 나" | 본인 제작 (위와 동일 방식) |

finished_2·3의 배경은 사진이 아니라 파이썬 스크립트(`scripts/gen_assets.py`)가 그라디언트와 도형을
그려서 만든 것이라 원본에도 인물·장소가 없고 위치정보(EXIF GPS)도 존재하지 않습니다.
finished_1의 배경(커미션 이미지 `test-assets/commission_skull_xio.jpg`)도 Pillow `Image.getexif()`로
확인한 결과 EXIF 항목 0건입니다. 세 완성 이미지 모두 정상적으로 열리는 PNG임을 Pillow로
재확인했습니다(T03-C26).

### 위치정보 · 개인정보 · 비밀값 점검 (T03-C28~C30)

- 완성 이미지 3개 + 원본 배경 이미지 전체를 Pillow `Image.getexif()`로 확인한 결과 EXIF 항목 0건
  (위치정보 포함 메타데이터 없음, T03-C28).
- 앱은 순수 클라이언트 코드이며 서버·API 키·비밀값을 전혀 사용하지 않고, 리포지토리 전체에도
  이메일·전화번호 등 개인정보나 토큰·키 문자열이 없습니다(T03-C29, T03-C30).

### 짧은 확인 방법 / AI-본인 판단 (T03-C31, T03-C32)

`SUBMISSION.md`에 4줄 확인 방법과 3줄 AI-본인 판단을 구분해 작성했습니다.

## 추가 기능 (통과기준 32개와는 별도 — 개인 사용성 향상 요청 반영)

과제 통과기준에는 없지만, 실제로 짤을 만들 때 쓰고 싶다고 요청하신 두 가지를 추가했습니다.
자동 검증: `python3 scripts/test_font_ink.py` (결과: `test-assets/results/log_font_ink.json`).

### 글꼴 선택

기본 굵은 고딕 외에 Noto Sans KR, Black Han Sans, Jua, Do Hyeon, Gaegu, Nanum Pen Script(손글씨),
Poor Story(손글씨) 등 7종을 추가로 고를 수 있습니다(Google Fonts, `index.html`의 `<link>`로 불러옴).

| 확인 항목 | 결과 |
|---|---|
| 글꼴 변경 시 캔버스 픽셀이 실제로 바뀜(FONT-change) | PASS |
| 손글씨체(Nanum Pen Script) 적용 시 다른 글꼴과 구분되게 렌더됨(FONT-pen) | **이 샌드박스에서는 FAIL** — 아래 설명 참고 |

> **왜 FONT-pen만 실패로 나오는가**: 이 개발 샌드박스는 외부 네트워크가 허용 목록 방식이라
> `fonts.googleapis.com`/`fonts.gstatic.com`으로의 요청이 막혀 있습니다(`curl` 결과 403 Forbidden,
> 설치된 시스템 폰트에도 Nanum Pen Script나 별도 cursive 폰트가 없음을 `fc-list`로 확인). 그래서 이
> 샌드박스 안에서는 구글 폰트를 못 받아와 두 글꼴이 같은 대체 글꼴로 보이는 것뿐이며, 코드 자체의
> 결함이 아닙니다(실제로 "기본" vs "Black Han Sans"처럼 대체 글꼴이 다르게 매핑되는 조합은 정상적으로
> 다르게 렌더되는 것도 함께 확인했습니다 — FONT-change PASS). GitHub Pages로 배포하면 방문자의
> 브라우저는 일반적인 인터넷 환경이라 Google Fonts를 정상적으로 받아오므로, 배포 후 실제 화면에서
> 8종 글꼴이 각각 다르게 보이는지 한 번 직접 확인해 보시는 걸 권장합니다.

### 손글씨(직접 쓰기) — 문구 레이어와 나란한 입력 방식 (Pointer Events 기반, 압력 지원)

손글씨는 "2. 문구"의 "+ 손글씨" 버튼으로 추가하는 **레이어**입니다. 즉, 레이어마다 입력 방식을
"타이핑"(문구 레이어) 또는 "손글씨"(손글씨 레이어) 중 고르는 구조입니다. 손글씨 레이어를 선택하고
있는 동안 왼쪽 컨트롤이 펜 색·굵기·"마지막 선 취소"·"이 레이어 지우기"로 바뀌고, 그 상태에서
미리보기 캔버스에 직접 그리면 그려집니다(레이어를 고르는 것 자체가 곧 "그리기 모드"라, 별도의
"필기 모드 켜기" 체크박스가 필요 없습니다). 표준
[Pointer Events](https://developer.mozilla.org/docs/Web/API/Pointer_events) API만 사용했기 때문에
별도 SDK 연동 없이도 애플펜슬(iPadOS Safari), 와콤 등 펜 태블릿이 보내는 압력값(pressure)을 그대로
읽어 선 굵기에 반영합니다. 세 비율(1:1/4:5/9:16)은 손글씨 레이어 안에서도 각각 독립적으로 저장되어,
어느 캔버스에 그렸는지에 따라 그 비율의 결과 파일에만 반영됩니다.

| 확인 항목 | 결과 |
|---|---|
| "+ 손글씨"로 레이어를 추가하면 컨트롤이 문구용에서 펜(손글씨)용으로 바뀜(INPUT-METHOD-ink-layer, `test_layers_effects.py`) | PASS |
| 손글씨 레이어를 선택하지 않은 상태(문구 레이어 선택 중)에서는 캔버스에 그려지지 않음 | PASS |
| 손글씨 레이어 선택 + 압력이 변하는 펜 스트로크 → 캔버스에 반영 | PASS |
| 펜/태블릿 없이 일반 마우스 클릭+드래그만으로도 그려짐(와콤펜·애플펜슬 같은 감압 방식 외에 마우스 드래그도 지원, INK-mouse-drag, `test_layers_effects.py`) | PASS |
| 손글씨가 포함된 상태에서도 미리보기==다운로드 파일 일치(카드2 회귀 확인) | PASS |
| 마지막 선 취소 → 취소 직전 상태와 픽셀 완전히 동일 | PASS |
| "이 레이어 지우기" → 그리기 전 상태와 픽셀 완전히 동일 | PASS |
| 손글씨 추가/실행취소/레이어 지우기가 "편집 기록" 패널에 순서대로 남음 | PASS |
| 템플릿으로 저장 → 다른 상태로 바꿈 → 다시 불러오기 → 저장 시점과 픽셀 동일(글꼴+손글씨 포함) | PASS |
| 내보낸 JSON에 문구 레이어의 `fontFamily`와 손글씨 레이어의 `strokes`가 그대로 담김 | PASS |
| 손글씨 데이터가 비율마다 독립적으로 저장됨(한 비율에만 그리면 다른 비율엔 안 남음) | PASS |

자동 검증: `python3 scripts/test_font_ink.py`. 예전 형식(레이어 개념이 없던 시절, 화면 전체에 그리는
방식이었던 필기 데이터)의 템플릿·JSON을 가져오면 자동으로 손글씨 레이어 하나로 변환해 복원하고,
글꼴이 없던 시절의 템플릿은 `fontFamily`가 "기본"으로 자동 채워집니다.

### 손글씨 인식(OCR) → 문구로 변환 (다국어 지원)

손글씨 레이어 컨트롤에 "인식 언어" 드롭다운(한국어+영어 기본 / 한국어만 / 영어만 / 일본어 /
중국어(간체) / 중국어(번체))과 "손글씨 인식 → 문구로 변환" 버튼이 있습니다. 처음엔 "한글이 아니어도
괜찮다"고 하셨지만, 실제로 한글로 써봤더니 영어로만 인식되는 걸 확인하고 다국어 지원을 요청하셔서
언어 선택 기능을 추가했습니다. 고른 언어는 Tesseract.js(브라우저 안에서만 동작하는 오픈소스 OCR,
서버 전송 없음)의 `recognize()` 호출에 그대로 전달됩니다. 자동 검증: `python3 scripts/test_ocr.py`.

| 확인 항목 | 결과 |
|---|---|
| 문구 레이어에서는 인식 버튼(손글씨 컨트롤 안)이 보이지 않음(OCR-button-scoped-to-ink-layer) | PASS |
| 손글씨 레이어 선택 시 인식 버튼이 보임(OCR-button-visible-on-ink-layer) | PASS |
| 손글씨 없이 눌러도 앱이 죽지 않고 안내 메시지가 뜸(OCR-empty-ink-guard) | PASS |
| 인식 엔진을 못 불러온 경우에도 죽지 않고 안내 메시지 + 버튼 재사용 가능(OCR-graceful-failure) | PASS |
| 레이어를 바꾸면 이전 인식 상태 메시지가 사라짐(OCR-status-clears-on-layer-switch) | PASS |
| 인식 언어 드롭다운의 기본값이 "한국어+영어"(kor+eng)임(OCR-lang-default) | PASS |
| 드롭다운에서 고른 언어(예: 일본어)가 그대로 `Tesseract.recognize()`에 전달되고 결과가 새 문구 레이어에 담김(OCR-lang-selection-passed-through) | PASS |
| 언어를 다시 바꿔도(중국어 간체) 매번 그 선택이 그대로 전달됨(OCR-lang-selection-switches) | PASS |

> **왜 실패 경로 + 가짜(stub) Tesseract로 확인했는가**: 이 개발 샌드박스는 외부 네트워크가 허용
> 목록 방식이라 Tesseract.js를 불러오는 `cdn.jsdelivr.net`으로의 요청이 막혀 있습니다(`curl` 결과
> 403 Forbidden — Google Fonts 때와 동일한 제약, 이 문서의 FONT-pen 설명 참고). 그래서 실제 인식
> 정확도 자체는 여기서 확인할 수 없어 두 가지로 나눠 검증했습니다: (1) 엔진을 못 불러왔을 때 앱이
> 안전하게 안내하고 계속 쓸 수 있는지(OCR-graceful-failure 등, 실제 실패 경로), (2) 언어 선택이라는
> "배선"이 맞게 연결됐는지는 `window.Tesseract`를 가짜 함수로 심어(`page.evaluate`) 실제 CDN 없이도
> 확인했습니다(OCR-lang-selection-*). 코드 자체의 결함이 아니며, GitHub Pages로 배포하면 방문자
> 브라우저는 일반적인 인터넷 환경이라 엔진이 정상적으로 로드되어 실제 인식까지 이어집니다. 배포 후
> 언어별 정확도(특히 흘려 쓴 글씨)를 직접 확인해 보시는 걸 권장합니다.

### 화면 정리("+ 기능 추가") · 문구 레이어(복사/삭제) · 회전 · 그림자 · 네온

화면이 너무 복잡해 보인다는 의견을 반영해 회전·그림자·네온은 기본적으로 접혀 있고 "+ 기능 추가"
메뉴에서 체크해야 펼쳐지도록 바꿨고, 템플릿 저장/업데이트/내보내기/가져오기 버튼을 왼쪽에서
오른쪽(저장된 템플릿·편집 기록과 같은 패널)으로 옮겼습니다. 또한 문구를 여러 개(레이어) 만들어
각각 독립적으로 편집할 수 있게 했고, "복사"는 **선택된 레이어를 그대로 복제해 새 레이어로 만드는
기능**(포토샵의 레이어 복제와 같은 개념)으로 구현했습니다 — 클립보드로 텍스트를 복사하는 기능이
아니니, 원하신 의미와 다르면 말씀해 주세요. 손글씨는 "+ 기능 추가" 메뉴가 아니라 문구와 나란한
별도의 레이어/입력 방식으로 옮겼습니다(자세한 내용은 아래 "손글씨" 항목 참고). 자동 검증:
`python3 scripts/test_layers_effects.py`.

| 확인 항목 | 결과 |
|---|---|
| 기본 화면에서 회전·그림자·네온 컨트롤이 모두 접혀 있음(DECLUTTER-default-hidden) | PASS |
| "+ 손글씨"로 레이어를 추가하면 2.문구 영역이 손글씨(펜) 입력 방식으로 바뀜(INPUT-METHOD-ink-layer) | PASS |
| "+ 기능 추가" 클릭 시 메뉴가 펼쳐짐(DECLUTTER-menu-open) | PASS |
| 템플릿 저장/업데이트/내보내기/가져오기가 왼쪽이 아닌 오른쪽 패널에 있음(TEMPLATE-panel-right) | PASS |
| 회전 체크 시 컨트롤이 나타나고, 각도를 바꾸면 실제로 캔버스가 회전함(ROTATION) | PASS |
| 그림자 체크 시 픽셀이 바뀌고, 체크 해제하면 정확히 원래 픽셀로 돌아옴(SHADOW) | PASS |
| 네온 체크 시 은은하게 빛나는 효과로 픽셀이 바뀜(NEON) | PASS |
| "+ 복사"로 만든 새 레이어가 원래 레이어와 완전히 독립적으로 문구를 유지함(LAYER-duplicate-independent) | PASS |
| 문구 레이어가 2개인 상태에서도 미리보기==다운로드 파일 일치(카드2 회귀 확인, LAYER-multi-download-match) | PASS |
| 레이어 삭제 후 1개만 남으면 삭제 버튼이 비활성화됨(LAYER-delete) | PASS |

회전·그림자·네온은 문구 레이어마다 각각 독립적으로 켜고 끌 수 있고, 그 값은 템플릿 저장과 JSON
내보내기/가져오기에도 그대로 담깁니다(레이어 배열 안에 `rotation`/`shadow`/`neon` 필드로 저장).
예전 형식의 템플릿·JSON을 가져와도 각 항목이 회전 0°·그림자 꺼짐·네온 꺼짐으로 자동 채워져 오류
없이 복원됩니다. 스크린샷: `test-assets/results/effects_demo.png`(그림자·네온 등 효과 적용 화면),
`test-assets/results/two_layers_demo.png`(문구 레이어 2개 동시 편집 화면).

### 도형(하트·별·폭죽) 레이어 + 색상 컨트롤(HEX/RGB/그라데이션)

과제 통과기준에는 없지만, "짤·카드 스튜디오"답게 문구뿐 아니라 가벼운 장식 도형도 넣고 싶다는
요청과, 문구 색을 HEX/RGB/그라데이션으로 세밀하게 고르고 싶다는 요청을 반영했습니다. 자동 검증:
`python3 scripts/test_shapes_and_color.py`.

도형은 "2. 문구"의 "+ 도형" 버튼으로 추가하는 레이어입니다(하트/별/폭죽 중 선택). 이미지나 이모지가
아니라 Canvas 2D 경로(하트=베지어 곡선, 별·폭죽=좌표 계산)로 직접 그리는 **벡터 도형**이라 크기를
키워도 흐려지지 않습니다. 색은 문구 레이어와 같은 재사용 색상 컨트롤을 씁니다 — 클릭하면 펼쳐지는
패널에서 "단색"(HEX 코드 직접 입력 또는 R/G/B 숫자 입력, 서로 실시간 동기화) 또는 "그라데이션"
(시작색·끝색·각도)을 고를 수 있고, 그라데이션은 레이어가 회전돼 있으면 방향도 함께 회전합니다.

| 확인 항목 | 결과 |
|---|---|
| "+ 도형" 클릭 시 2.문구 영역이 도형 컨트롤(모양/색/위치/크기/회전)로 바뀜(SHAPE-controls-visible) | PASS |
| 도형 모양(하트/별/폭죽) 변경 시 서로 다른 픽셀로 렌더됨(SHAPE-kind-change) | PASS |
| 도형 크기/회전/위치 슬라이더가 각각 렌더에 반영됨(SHAPE-transform) | PASS |
| 도형 색상 컨트롤의 HEX 입력이 렌더에 반영되고 RGB 입력칸과 동기화됨(SHAPE-color-hex) | PASS |
| 도형 색상 컨트롤의 RGB 입력이 렌더에 반영되고 HEX 입력칸과 동기화됨(SHAPE-color-rgb) | PASS |
| 도형 색상을 그라데이션으로 바꾸면 필드가 나타나고 픽셀이 바뀌며, 각도 변경도 반영됨(SHAPE-color-gradient) | PASS |
| 문구 색상도 같은 컨트롤로 그라데이션 전환 가능(TEXT-color-gradient) | PASS |
| 도형 + 그라데이션 문구가 함께 있어도 미리보기==다운로드 파일 일치(카드2 회귀 확인, SHAPE-download-match) | PASS |
| 내보낸 JSON에 도형 레이어(`shapeKind`/`color`)와 문구 레이어의 그라데이션 색상이 그대로 담김(EXPORT-shape-and-gradient-fields) | PASS |
| 템플릿 저장 → 다른 상태로 바꿈 → 다시 불러오기 → 저장 시점과 픽셀 동일(도형+그라데이션 포함, TEMPLATE-shape-roundtrip) | PASS |
| 도형 레이어도 "+ 복사"/삭제가 문구·손글씨 레이어와 동일하게 동작함(SHAPE-duplicate-delete) | PASS |

"폭죽"은 정지 이미지 특성상 애니메이션이 아니라 중심에서 사방으로 뻗어나가는 빛줄기 형태의 장식
모티프로 해석해 구현했습니다. 스크린샷: `test-assets/results/shape_gradient_demo.png`(도형+그라데이션
문구가 함께 있는 화면).

### 화면 테마 (라이트 / 다크)

과제 통과기준에는 없지만, 편집기 화면 자체의 밝기를 취향에 맞게 고르고 싶다는 요청을 반영했습니다.
화면 맨 위에 "☀️ 라이트 / 🌙 다크" 버튼을 두고, CSS 커스텀 속성(`--bg`/`--panel`/`--text` 등)을
`data-theme` 속성으로 한 번에 바꾸는 방식으로 구현했습니다. 자동 검증: `python3 scripts/test_theme.py`.

| 확인 항목 | 결과 |
|---|---|
| 저장된 설정이 없는 첫 방문 시 기본은 라이트 테마(THEME-default-light) | PASS |
| "다크" 버튼 클릭 시 즉시 어두운 배색으로 전환되고 버튼 활성 표시도 바뀜(THEME-switch-to-dark) | PASS |
| 테마를 바꿔도 미리보기 캔버스(합성 결과물) 픽셀은 전혀 바뀌지 않음(앱 UI에만 적용, THEME-canvas-unaffected) | PASS |
| 선택한 테마가 이 브라우저에 저장되어 새로고침해도 유지됨(THEME-persist-reload) | PASS |
| "라이트" 버튼으로 다시 되돌릴 수 있음(THEME-switch-back-to-light) | PASS |

편집기 UI(조작 패널·미리보기 틀·템플릿/기록 패널 등)의 배색만 바뀌고, 만들고 있는 밈·카드 이미지
자체나 다운로드 파일에는 영향이 없습니다 — 미리보기 캔버스 둘레의 투명도 체크무늬는 다운로드 파일의
실제 투명 영역을 나타내는 표시라 테마와 무관하게 항상 동일하게 둡니다(THEME-canvas-unaffected로
확인). 처음 방문 시 저장된 값이 없으면 운영체제/브라우저의 다크 모드 설정(`prefers-color-scheme`)을
따라갑니다. 스크린샷: `test-assets/results/theme_light_demo.png`, `test-assets/results/theme_dark_demo.png`.

### 이름 확정: Quiplet + 더스크 라벤더 기본 테마

작업용 가제 "짤·카드 스튜디오"와 기본 흰색 라이트 테마가 꼭 정답일 필요는 없다는 의견을 받아, 영어
이름 5안(로고 마크 포함)과 화이트가 아닌 라이트 테마 5안을 시안 페이지로 만들어 비교한 뒤 이름은
**Quiplet**(quip=위트있는 한마디 + -let=작은 조각), 테마는 **더스크 라벤더**로 확정했습니다.

반영한 곳: `index.html`의 `<title>`/헤더 로고·이름(말풍선+스파크 아이콘, `.brand-mark`)/`favicon.svg`,
`styles.css`의 `:root` 라이트 테마 색상 전체(`--bg #efe9f5`, `--panel #f8f4fb`, `--accent #7952b3` 등)와
다크 테마의 강조색(브랜드와 어울리는 보라 계열 `#a78bfa`로 조정), `app.js`의 다운로드 파일명
(`quiplet-1-1.png` 등, `quiplet-templates.json`). 저장된 템플릿을 찾는 `localStorage` 키 이름은
기존 사용자의 저장 데이터가 사라지지 않도록 그대로 두었습니다.

색 값만 바뀐 변경이라 캔버스 렌더링 로직에는 영향이 없고, 기존 자동 테스트 전체(`test_playwright.py`
20건, `test_history.py`, `test_layers_effects.py` 11건, `test_font_ink.py`, `test_ocr.py` 5건,
`test_shapes_and_color.py` 11건, `test_theme.py` 5건)를 다시 돌려 회귀가 없음을 확인했습니다.
스크린샷: `test-assets/results/quiplet_lavender_light.png`.

### 위치(가로/세로) 슬라이더를 미리보기 바로 아래로 이동

왼쪽 조작 패널에 컨트롤이 많아 스크롤이 길어지면, 슬라이더를 조정하는 동안 가운데 미리보기가 화면
밖으로 벗어나 변화를 바로 확인하기 어렵다는 의견을 받았습니다. 전체 레이아웃(좌: 조작 / 중앙:
미리보기 / 우: 템플릿)은 그대로 두고, 문구·도형 레이어의 가로·세로 위치 슬라이더만 왼쪽 패널에서
떼어내 가운데 미리보기 패널 바로 아래(원래 비어 있던 공간)에 새 "위치" 패널로 옮겼습니다. 자동
검증: `python3 scripts/test_layers_effects.py`.

| 확인 항목 | 결과 |
|---|---|
| 가로·세로 위치 슬라이더가 좌측 조작 패널이 아니라 가운데 미리보기 바로 아래 "위치" 패널에 있음(POSITION-panel-in-preview-column) | PASS |
| "위치" 패널이 문구/도형 선택 시 각각의 위치 슬라이더로, 손글씨 선택 시 안내 문구로 바뀜(POSITION-panel-switches-with-layer-type) | PASS |
| 옮긴 위치 슬라이더를 움직이면 지금까지처럼 캔버스에 바로 반영됨(POSITION-panel-still-updates-canvas) | PASS |

id는 그대로 두고 DOM 위치만 옮긴 변경이라(`posX`/`posY`/`shapeX`/`shapeY`), 렌더링·템플릿·JSON
내보내기 등 기존 동작에는 영향이 없습니다. 스크린샷: `test-assets/results/position_panel_layout.png`.
