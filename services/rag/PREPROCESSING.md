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
| `reviews.jsonl` | 조건 적용범위 충돌, 이미지 글자 미검증, OCR·표 추출 실패 등 |

좌표는 PDF 포인트 단위 `[x0, top, x1, bottom]`이며 위쪽이 원점입니다.
`page`는 실제 PDF 쪽(1-based), `printed_page`는 인쇄된 페이지 표기입니다.
표의 빈 셀을 임의로 채우지 않고 행·열·단위·각주를 보존합니다.

### 자동 해석의 범위

- 중앙 과제번호 `Ⅲ-1-1-(1)` 및 지역 과제번호 `1-1-서울-3`를 기준으로 정책을 묶습니다.
- 지원대상 연령·소득비율·취업/학력/주거/거주 관련 언급을 근거와 함께 후보로 저장합니다.
- `만`이 명시되지 않으면 만 나이로 가정하지 않습니다. 적용범위·예외·부정조건은 원문으로 남깁니다.
- 예: 요약표 `연령무관`과 상세 `19~39세(청년특공 기준)`는 `age_scope_conflict`로 검토합니다.
- 발행지역은 신청자 거주요건이 아닙니다. 법정지역 코드 매핑·최종 자격 판정은 별도 구현 대상입니다.
- 기업/개인 신청 주체, 수혜자, 모집 여부는 `unverified`로 남깁니다. 단어 출현만으로 확정하지 않습니다.
- 금액은 원 단위로 환산하되 `benefit_status=unverified`로 저장합니다. 사업예산을 수혜액으로 확정하지 않습니다.
- 과거 실적·추진경과·예산·일정·성과지표는 구간 유형으로 분리합니다. 혼합 표에는 여러 연도가 함께 남습니다.
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

검색 API 테스트 10개, 전처리·저장소 테스트 20개, KURE 연결 테스트 6개로 총 36개입니다.
API 테스트는 인덱스를 모의 객체로 대체하고 실제 FastAPI HTTP 요청/응답, 메타데이터 보존,
입력 검증, 오류 처리, 적재 후 다음 요청에서 최신 인덱스를 읽는 동작을 확인합니다.
실제 모델 가중치 다운로드·KURE 추론 및 OpenAI/DB 서버 연결은 실행하지 않았습니다.

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
