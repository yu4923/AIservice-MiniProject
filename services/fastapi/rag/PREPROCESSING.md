# 청년정책 PDF·공식 웹 전처리

기존 `/upload-paper` 역할은 `scripts/ingest_papers.py`, `/upload-topic` 역할은
`scripts/ingest_topics.py`가 맡습니다. 업로드 HTTP 엔드포인트를 추가하지 않습니다.
공통 함수 `ingest_paper()` / `ingest_topic()`의 `(store, result)` 반환 형식은 유지합니다.
기본 PDF 위치는 종전과 같은 `services/rag/documents/`입니다.

## 실행 환경

Python 3.11 이상. 프로젝트 가상환경에서 `requirements.txt`를 설치하세요.
PDF 처리는 `pdfplumber`, `pypdfium2`, 임베딩은 `langchain-huggingface`와
`sentence-transformers`·`transformers`·`torch`를 사용합니다.
전처리·임베딩·검색에는 OpenAI 키가 필요하지 않습니다.

```bash
python -m pip install -r services/rag/requirements.txt
```

아래 명령은 프로젝트 루트 `AIservice-MiniProject/`에서 실행합니다.
스크립트 자체는 어느 디렉터리에서 호출해도 동작합니다.

## PDF/ZIP: 먼저 비용 없는 검사

```bash
python services/rag/scripts/ingest_papers.py --dry-run
```

문서 디렉터리의 모든 PDF와 ZIP 내부 PDF를 처리합니다. ZIP 경로를 파일시스템에
그대로 풀지 않으며, 원본은 수정하지 않습니다. `.pdf` 확장자는 대소문자 무관합니다.

특정 파일 또는 여러 ZIP을 직접 지정할 수 있습니다.

```bash
python services/rag/scripts/ingest_papers.py --input "/path/to/central.pdf" "/path/to/regions.zip" "/path/to/cards.zip" --dry-run
```

검사 범위를 줄이려면 다음 옵션을 사용하세요. 페이지는 원본 PDF의 1부터 시작합니다.

```bash
python services/rag/scripts/ingest_papers.py --input "/path/to/cards.zip" --dry-run --max-documents 3 --max-pages 5 --ocr off
```

`--max-pages` 또는 `--first-page`를 지정한 결과는 일부 문서이므로 실제 인덱스 적재가
차단됩니다. `--chunk-chars` 기본값은 2200자이며 토큰 수가 아닙니다. 표와 각주는 경계를
보존하기 위해 이 길이를 초과할 수 있습니다. `--output-dir`로 결과 위치를 지정합니다.

검토 후 임베딩·FAISS 적재:

```bash
python services/rag/scripts/ingest_papers.py --input "/path/to/cards.zip"
```

임베딩은 로컬 `nlpai-lab/KURE-v1`으로 실행합니다. 첫 실행에는 Hugging Face 모델 다운로드와
저장 공간이 필요하며, 이후에는 캐시된 모델을 사용합니다. 모델 다운로드·실제 추론은 별도 확인이 필요합니다.
문서 출처명은 기본적으로 입력 디렉터리 기준 상대경로, ZIP은 `archive.zip!/member.pdf`입니다.
같은 원본을 직접 PDF로 주거나 ZIP으로 주면 별도 출처로 간주하므로 적재 경로를 일관되게
유지하세요. 입력 파일을 다른 출처명으로 바꾼 경우 이전 출처를 자동으로 삭제하지 않습니다.

## OCR

`--ocr auto`는 로컬 `tesseract` 실행파일과 `kor`, `eng` 언어 데이터가 있을 때 OCR을
수행합니다. 별도 시스템 설치가 필요합니다. `tesseract --list-langs`로 확인할 수 있습니다.
이미지와 텍스트가 혼합된 페이지에서는 이미지 영역에서 복구한 글자를 네이티브 글자와
좌표 기준으로 병합합니다. 이미지 없는 빈 페이지는 OCR 대상이 아닙니다.

- `off`: OCR을 실행하지 않고 이미지 페이지에 검토 플래그를 기록합니다.
- `auto`: OCR이 없거나 실패하면 검토 목록을 남깁니다. 스캔 페이지를 전혀 읽지 못했다면 적재를 차단합니다.
- `required`: OCR이 필요한 페이지에서 한글 OCR을 실행할 수 없으면 실패합니다.

OCR 결과도 검수 대상입니다. `auto`는 이미지 안의 숫자가 완벽히 복구되었다는 보장이
아닙니다. 현재 검증 환경에는 Tesseract가 없어 실제 OCR 품질을 검증하지 못했습니다.
실서비스 적재 전 이미지 숫자·나이·금액을 검수하세요. `reviews.jsonl`을 확인해야 합니다.

## 결과 파일

기본 위치: `services/rag/data/preprocessed/pdf/<document_id>/<run_id>/`

| 파일 | 내용 |
|---|---|
| `manifest.json` | 원본 SHA-256, 처리 버전·시각·설정, 페이지/정책/청크 수, 부분처리 여부 |
| `pages.jsonl` | 원본 추출 텍스트, 정제 블록·표 셀, 원본 좌표, OCR/품질 플래그 |
| `policies.jsonl` | 과제별 전체 원문, 과제번호·발행지역·분야·연도, 조건 후보, 금액 언급 |
| `chunks.jsonl` | 검색용 텍스트와 정책·구간·페이지·근거 메타데이터 |
| `reviews.jsonl` | 조건 적용범위 충돌, 과제번호 미검증, 이미지 글자 미검증, OCR·표 추출 실패 등 |
| `supplements.jsonl` | 정책에서 분리한 사업 총괄표·붙임·법령·통계 원문, 표 행과 연결 검토 후보 |

좌표는 PDF 포인트 단위 `[x0, top, x1, bottom]`이며 위쪽이 원점입니다.
`page`는 실제 PDF 쪽(1-based), `printed_page`는 인쇄된 페이지 표기입니다.
표의 빈 셀을 임의로 채우지 않고 행·열·단위·각주를 보존합니다.

### 자동 해석의 범위

- 중앙 과제번호 `Ⅲ-1-1-(1)` 및 지역 과제번호 `1-1-서울-3`를 기준으로 정책을 묶습니다.
- 충남의 `1-1-1` / `[1-3-충남-15]`처럼 나뉜 번호·참조번호와 여러 줄 제목도 인식합니다.
  인천의 `1--인천-1`처럼 사설영역 문자로 추출된 번호는 원문 그대로 보존하고
  `task_number_unverified` 검토 항목을 남깁니다. 숫자를 추측해 복원하지 않습니다.
- `policy-preprocess-v3`는 울산의 제목 뒤 `공통`, 세종의 `기타`, 전북의 `1-4`,
  제주의 `1-3-제주-1-①`·`②`도 인식합니다. `공동캠퍼스`처럼 제목 자체에 들어간 단어는 보존합니다.
- `공통` 또는 사설영역 기호만 있는 제목도 이어지는 `1. 사업 개요`를 확인해 구분합니다.
  목차·예산표 행을 정책 제목으로 복원하지 않으며, 같은 과제번호가 재사용돼도 제목과
  시작 페이지로 정책을 구분합니다. `policy_id`에는 시작 페이지가 포함됩니다.
- 지원대상 연령·소득비율·취업/학력/주거/거주 관련 언급을 근거와 함께 후보로 저장합니다.
- `만`이 명시되지 않으면 만 나이로 가정하지 않습니다. 적용범위·예외·부정조건은 원문으로 남깁니다.
- 예: 요약표 `연령무관`과 상세 `19~39세(청년특공 기준)`는 `age_scope_conflict`로 검토합니다.
- 발행지역은 신청자 거주요건이 아닙니다. 법정지역 코드 매핑·최종 자격 판정은 별도 구현 대상입니다.
- 기업/개인 신청 주체, 수혜자, 모집 여부는 `unverified`로 남깁니다. 단어 출현만으로 확정하지 않습니다.
- 금액은 원 단위로 환산하되 `benefit_status=unverified`로 저장합니다. 사업예산을 수혜액으로 확정하지 않습니다.
- 숫자 형식을 검증한 뒤 변환합니다. `23.08.07.원` 같은 날짜·비정상 숫자와
  `원스톱`은 금액으로 처리하지 않으며, 해당 원문은 추출 결과에 보존합니다.
- 과거 실적·추진경과·예산·일정·성과지표는 구간 유형으로 분리합니다. 혼합 표에는 여러 연도가 함께 남습니다.
- `19세 이상~34세 이하`, `19~34세 이하`, `만 15세~만 39세`는 하나의 범위로 추출합니다.
  `min`, `max`, `lower_inclusive`, `upper_inclusive`, `age_basis`를 보존하며 상한을 중복 추출하지 않습니다.
  대상별 표 행에는 `subject`, `condition_group`을 붙여 연령·소득 조건이 섞이지 않게 합니다.
  예외·우선선발·병역·다자녀 등의 원문과 뒤따르는 조건은 `qualifiers`, `exceptions`,
  `selection_text` 근거로 보존하며 적용 범위를 임의로 확정하지 않습니다.
- `연도별 추진계획 (‘27년 이후)`는 `future_plan`으로 분류해 현재 자격조건에서 제외합니다.
  문서연도와 당해 추진계획 제목의 연도가 다르면 `plan_year_mismatch` 검토 항목을 남깁니다.
- 연령·소득의 적용범위가 충돌하면 양쪽 근거를 남깁니다. 명시적으로 다른 대상 집단의 범위는
  하나로 합치지 않습니다. OCR·이미지 검수 플래그가 있는 숫자는 `verification_status=requires_review`입니다.
  OCR을 수행했다는 이유로 숫자·소득·자격을 확정하지 않습니다.
- LLM으로 빠진 숫자를 추측하거나 자격을 확정하지 않습니다.
- 모든 청크에는 시행계획은 현재 모집공고가 아니라는 안내와 원본 출처·PDF 쪽을 포함합니다.
- 완전한 조항 해석기가 아닙니다. 다른 지역의 비표준 과제번호, 복잡한 병합표, OCR 수식은 검수 후 확장해야 합니다.

## 공식 웹 본문 수집

기존 네이버 **뉴스 요약** 수집을 **웹문서 검색 → 공식 도메인 검증 → 원문 HTML 수집**으로
바꿨습니다. 검색 요약은 임베딩하지 않습니다.

```bash
python services/rag/scripts/ingest_topics.py --dry-run
python services/rag/scripts/ingest_topics.py --topic "2026 서울 청년수당 모집공고 site:seoul.go.kr" --dry-run
```

검색에는 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`이 필요합니다.
찾을 URL을 이미 알고 있다면 네이버 없이 공식 페이지를 직접 처리합니다.

```bash
python services/rag/scripts/ingest_topics.py --url "https://www.seoul.go.kr/news/news_notice.do?bbsNo=277&nttNo=453234" --dry-run
```

`--dry-run`을 빼면 전처리 후 로컬 KURE-v1 임베딩과 FAISS 갱신을 수행합니다.
`--url`은 여러 번 지정할 수 있습니다. `--config`로 다른 주제 JSON을 지정할 수 있으며
기존 문자열 배열 또는 아래 배열을 모두 지원합니다.

```json
[
  "2026 청년 주거 지원 모집공고 site:go.kr",
  {"topic": "공식 정책 공고", "urls": ["https://www.seoul.go.kr/news/news_notice.do?bbsNo=277&nttNo=453234"]}
]
```

공식 도메인 목록은 `config/official_domains.json`에 있습니다. 공식 기관이어도 목록에
없으면 추가해야 합니다. HTTPS, 호스트 경계, 리다이렉트 목적지, 공개 IP를 검증합니다.
수집 제한·이용조건은 출처별로 확인하세요. 로그인·자바스크립트 전용 페이지를 우회하지 않습니다.

결과는 `data/preprocessed/web/`에 원본 HTML, 추출 본문·표·첨부링크, 출처·게시일·수집시각,
실패 목록과 청크로 저장합니다. 첨부 PDF는 **링크만 발견**하며 자동 다운로드/적재하지 않습니다.
필요한 PDF를 확인·다운로드한 뒤 `ingest_papers.py`로 처리하세요.
네이버 검색은 최대 100개 후보 중 공식 본문을 최대 `--limit`개 수집합니다. 전수 수집이나
현재 모집 중 여부 판정은 제공하지 않습니다. 게시판별 본문 선택자는 실제 페이지에 맞춰 보완하세요.

## FAISS 갱신과 서버 연결

- 동일 출처 갱신 시 그 출처의 이전 청크를 교체합니다. 다른 출처와 수집 실패 출처는 보존합니다.
- PDF의 조건 충돌은 검수 플래그로 남기고 검색 응답의 문서 메타데이터로 전달합니다.
- 쓰기 잠금 + 새 세대 저장 + `current.json` 원자적 전환으로 실패한 적재를 공개하지 않습니다.
- 기본 인덱스 위치는 프로젝트의 `data/faiss-kure-v1/{pdf,web}/`입니다.
  기존 `data/faiss/`는 보존하며, 모델 메타데이터가 없는 과거 인덱스는 재적재해야 합니다.
  새 저장은 `generations/`와 `current.json`을 사용합니다.
- 서버는 `load_vectorstore()`로 활성 세대를 읽고 질의마다 변경 여부를 확인합니다.
- `RAG_FAISS_DIR`, `RAG_PREPROCESS_DIR`로 경로를, `RAG_EMBEDDING_MODEL`로 모델을 설정합니다.
- 모델 변경은 기존 벡터와 섞지 않습니다. 새 인덱스 디렉터리에서 다시 적재해야 합니다.
- 세대 기록은 자동 삭제하지 않습니다. 운영자가 백업·보관 정책에 따라 관리하세요.
- 신뢰할 수 있는 로컬 FAISS 파일만 사용하세요. 메타데이터 로딩에 pickle을 사용합니다.
- 검색 API는 `services/rag/.env`를 읽으며 KURE-v1을 로컬 실행합니다. OpenAI 키는 필요하지 않습니다.
  DB 연결과 LLM 답변 생성은 검색 API에서 수행하지 않습니다.

## 검증

서비스 디렉터리에서 실행합니다. 외부 API를 사용하지 않는 테스트입니다.

```bash
python -m unittest discover -s tests -v
```

나이 적용범위 충돌·정책 경계·연도 구분·금액 단위·표·각주·페이지 근거·공식 URL 검증,
출처 교체·재실행 중복 방지·임베딩 실패 시 기존 인덱스 보존을 확인합니다.
실제 첨부 주거 과제카드 전체 145쪽, 서울 문서 30쪽, 분야별 과제카드 일부와 서울시 공식
공고 HTML로 전처리를 검증했습니다. 유료 OpenAI 임베딩·LLM·네이버 인증 검색 호출은 하지 않았습니다.

### 이전 v2: 배포 피드백 세 문서 재검사

`policy-preprocess-v2`에서 인천·충남의 정책 제목 인식 누락과 부산의 금액 변환 오류를
수정했습니다. 부산 파일 기준 276쪽의 `23.08.07. 원스톱전세피해지원센터`가 기존 패턴에서는
`23.08.07. 원`으로 잡혀 `Decimal` 변환에 실패했습니다. 수정 후 날짜는 제외하고
같은 과제의 `145백만원`은 정상적으로 추출합니다.

전체 PDF를 `--dry-run --ocr off`로 검사한 결과입니다. 임베딩·FAISS 적재는 실행하지 않았으며
이미지와 OCR 품질은 별도 검수가 필요합니다.

| 문서 | 전체 쪽 | 정책 수 | 청크 수 |
|---|---:|---:|---:|
| 인천 | 349 | 90 | 907 |
| 충남 | 338 | 121 | 1,199 |
| 부산 | 423 | 117 | 1,214 |

배포 시에도 실제 마운트 경로와 기존 출처명을 유지해 먼저 검사하세요.

```bash
python services/rag/scripts/ingest_papers.py --input "/mount/인천.pdf" "/mount/충남.pdf" "/mount/부산.pdf" --dry-run --ocr off
```

정책·청크 수와 `reviews.jsonl`을 검토한 뒤 `--dry-run`을 빼고 적재합니다.
OCR이 필요한 문서는 `--ocr auto` 또는 `required`로 검수하세요. 본문은 있지만 제목 규칙이
맞지 않아 청크가 없는 문서는 `policy_heading_not_found`로 구분합니다.

## 검색 전용 API 연결

원격 `rag` 브랜치의 검색 역할 분리를 유지합니다. `/rag-query`는
`RAGRequest(prompt, source, top_k)`를 받아 `prompt`, `source`, `documents`, `context`,
`index_available`을 반환합니다. `source`는 `web` 또는 `pdf`, `top_k`는 1~50입니다.
각 검색 문서는 `content`, `metadata`, `distance`를 포함합니다. 출처·PDF 페이지·게시/수집
시각·검수 상태는 `metadata`로 전달하며, `distance`는 지원 자격 점수가 아닌 FAISS 거리입니다.
LLM 답변·추천 생성은 이후 그래프에서 담당합니다. 인덱스가 없으면 HTTP 200과
`index_available: false`, 빈 문서·컨텍스트를 반환합니다. 인덱스 로딩 오류는 HTTP 503,
검색 오류는 HTTP 500으로 반환합니다.

`app/main.py`는 이 패키지의 `app/retrieval/faiss_store.py`에 있는 `load_vectorstore()`를
사용하므로 함께 적용해야 합니다. 기존 append_documents 전용 파일과 main.py만 조합하면
import 오류가 납니다. 웹 수집은 ingest_topics.py에서 수행하고 질의 API는 저장된 웹
인덱스를 검색합니다. 요청할 때마다 웹 검색을 새로 실행하지는 않습니다.

검색 API 테스트 10개, 전처리·저장소 테스트 45개, KURE 연결 테스트 6개로 총 61개입니다.
API 테스트는 인덱스를 모의 객체로 대체하고 실제 FastAPI HTTP 요청/응답, 메타데이터 보존,
입력 검증, 오류 처리, 적재 후 다음 요청에서 최신 인덱스를 읽는 동작을 확인합니다.
실제 모델 가중치 다운로드·KURE 추론 및 OpenAI/DB 서버 연결은 실행하지 않았습니다.

## v3: 전체 22개 정책자료의 경계·조건 검수

지역 17개와 중앙 과제카드 5개 전체 7,768쪽을 검사했습니다. 수정 범위는 전처리 코드,
전처리 테스트, 이 문서입니다. FAISS 적재·모델 다운로드·실제 임베딩·LLM 호출·배포는 실행하지 않았습니다.

서울을 제외한 지역 16개의 뒤쪽 자체사업 총괄표와 전북의 붙임·법령·통계는
`pages.jsonl`의 `document_role`로 구분하고 `supplements.jsonl`에 보존합니다.
이 페이지들은 마지막 정책의 `pages`, `raw_text`, 지원조건, 검색 청크에 들어가지 않습니다.
목차의 총괄표 항목과 개별 정책에 속한 내부 붙임은 문서 전체의 부록 시작으로 처리하지 않습니다.

총괄표 후보 행은 사업명, `issuer_raw`, `conditions_raw`, `year_values_raw`, 원본 셀·쪽·bbox를
각각 보존합니다. 지자체명이나 빈 셀을 추측해 채우지 않으며 발행지역을 신청자 거주요건으로
변환하지 않습니다. 동명 사업은 `name_candidates`로만 표시하고 `link_status=requires_review`를
유지합니다. 발행기관까지 일치하는 후보라도 총괄표와 본문 조건이 다르면
`summary_body_condition_difference`에 양쪽 근거를 기록하며 하나를 선택하지 않습니다.
표 머리글의 연도가 `2‘6예산`처럼 깨진 경우 원문 머리글을 보존하고
`year_mapping_status=requires_review`로 남깁니다. 숫자 순서를 추측해 예산 연도를 채우지 않습니다.

구조 검사에서는 22개 모두 정책·청크가 생성되고 출처·정책명·발행지역·문서연도·페이지 연결,
분리 페이지와 정책/청크의 교집합 0, RAG 응답의 메타데이터 전달을 확인했습니다.
RAG 검사는 실제 결과 청크와 모의 저장소를 사용하며 실제 검색 순위나 LLM 답변 품질을 보증하지 않습니다.
울산 180쪽 청년내일저축계좌, 세종 124쪽 공동캠퍼스, 전북 28쪽 직무인턴,
제주 55·58·71·73쪽의 별도 사업을 원본 배치와 함께 확인했습니다.

기존과 동일한 입력 경로·출처명으로 재검사하세요. 출력 위치를 분리하면 이전 결과와 비교하기 쉽습니다.

```bash
python services/rag/scripts/ingest_papers.py --input "/mount/지역자료" "/mount/중앙과제카드" --dry-run --ocr off --output-dir "/tmp/policy-v3-review"
```

`reviews.jsonl`의 `age_scope_conflict`, `income_scope_conflict`,
`numeric_evidence_requires_review`, `unparsed_age_condition`, `plan_year_mismatch`,
`summary_body_condition_difference`는 원문과 대조해야 합니다. 서로 다른 대상·예외·연도일 가능성도
있으므로 검토 항목 수를 확정 오류 수로 해석하지 마세요. OCR은 off로 검사했으며 실제 OCR
출력의 숫자 정확도는 별도 검수 대상입니다.

RAG·LLM 담당자에게는 질의별 정책명·출처·쪽·대상별 조건과 검토 플래그가 함께 유지되는지,
충돌/OCR 미검증 근거를 확정 자격으로 답하지 않는지 확인 요청해야 합니다. 이 검증과
배포 측 보고서 전체 사례 대조가 끝난 뒤 운영자가 FAISS 적재와 배포 점검을 진행합니다.

## KURE-v1 설정과 기존 인덱스 전환

환경설정 없이도 기본 모델은 `nlpai-lab/KURE-v1`, 장치는 `cpu`, 배치 크기는 8입니다.
`services/rag/.env`가 필요하면 `.env.example`을 복사한 뒤 값을 조정하세요.

```dotenv
RAG_EMBEDDING_MODEL=nlpai-lab/KURE-v1
RAG_EMBEDDING_DEVICE=cpu
RAG_EMBEDDING_BATCH_SIZE=8
# 선택: 기본 경로 대신 사용할 절대경로
# RAG_FAISS_DIR=/absolute/path/to/data/faiss-kure-v1
```

NVIDIA GPU는 설치된 PyTorch가 CUDA를 지원할 때 `cuda`를 사용합니다.
장치 메모리가 부족하면 배치 크기를 줄이세요. 문서와 질문 모두 단위 길이로 정규화합니다.
모델 인스턴스는 프로세스 안에서 재사용하며, 환경설정 변경 후 API 서버를 재시작하세요.
모델·정규화 방식을 바꿀 때는 같은 차원이어도 기존 벡터를 재사용할 수 없습니다.

기존 `.env`나 셸에서 `RAG_EMBEDDING_MODEL=text-embedding-3-small` 또는
`RAG_FAISS_DIR`를 설정했다면 새 모델과 새 경로로 변경하세요. 기존 인덱스의
`embedding_model` 값만 바꾸지 마세요. 아래 명령으로 원본 데이터를 재적재해야 합니다.
프로젝트 루트에서 실행하며, 기존 `documents/`, `config/topics.json` 구성을 사용합니다.

```bash
python -m pip install -r services/rag/requirements.txt
python services/rag/scripts/ingest_papers.py
python services/rag/scripts/ingest_topics.py
python -m uvicorn app.main:app --app-dir services/rag --port 8001
```

공식 구현 참고: [KURE-v1 모델 카드](https://huggingface.co/nlpai-lab/KURE-v1),
[LangChain Hugging Face 연동](https://docs.langchain.com/oss/python/integrations/embeddings/huggingfacehub).
KURE 연결 테스트는 모델 생성자를 모의 객체로 대체하고 실제 FAISS 저장·질의를 검증합니다.
모델의 실제 검색 품질이나 실행 장치 호환성을 검증하는 테스트는 아닙니다.
