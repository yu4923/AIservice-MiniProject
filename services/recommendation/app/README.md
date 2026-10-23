> 현재 실행 기준: `GraphPolicyAgent`가 실제 정책 API를 Graph의 `ApiLookupResult`로 변환하며 기본 연결됩니다.
> 설정은 `services/recommendation/.env` 또는 프로세스 환경변수를 사용합니다.
> 컨테이너 실행·서비스별 변수 주입은 루트 `CONFIGURATION.md`의 컨테이너 연결 절을 참고하세요.
> 아래 백업 복원 내역의 미연결 Agent·app/.env 설명은 복원 당시 기록입니다.

## 현재 요청 규격과 검색 방식

- `question`을 생략하거나 `null`, 빈 문자열, 공백만 보내면 서버가 기본 추천 질문을 넣습니다.
  직접 입력한 유효한 질문은 앞뒤 공백만 제거합니다. 숫자·한 글자·1,000자 초과 질문은 계속 거절합니다.
  `prompt` 별칭도 유지합니다.
- 기본 질문을 자동 생성한 경우에는 프로필의 지역·나이·상황·한국어 관심 분야·상세 선택으로 검색합니다.
  직접 질문한 경우에는 그 질문으로 검색하고, 기존 관심 분야를 검색어에 섞지 않습니다.
  두 경우 모두 사용자 프로필은 이후 정책 조건 비교에 전달됩니다.
- 현재 프론트는 `{"profile": {...}}`만 보냅니다. 서버가 기본 질문과 `source="pdf"`, `top_k=5`를 채웁니다.
- `source`는 `all` / `pdf` / `web`, 생략 시 `pdf`입니다. PDF 근거가 부족하면 기존 Graph가 공식 정책 API로 보완합니다.
  `top_k`는 엄격한 정수 1~20, 생략 시 5이며 Vector DB에서 검색·검토할 문서 조각 수입니다.
  검색 후 근거 변환에서도 20개 요청을 10개로 다시 자르지 않습니다. 빈 문서·중복은 제외합니다.
  `source="all"`은 두 인덱스의 결과를 합쳐 총 `top_k`개까지 유지합니다.
  별도 정책 API 보완 자료는 기존과 같이 최대 10개로 제한하며 `top_k`가 최종 정책 개수를 뜻하지는 않습니다.
- 소득·취업 상태의 공백은 제거하고 비면 `None`으로 처리합니다.
  현재 Graph는 소득과 취업 상태가 없으면 `needs_profile`을 반환합니다. `statuses`만 보고 추정하지 않습니다.
- 영어 선택 코드 원본은 보존하고 검색할 때만 한국어로 변환합니다.
  `unknown`과 `none` 자체를 검색어로 넣거나 각각 특정 관심 분야·미취업으로 추정하지 않습니다.
- 직접 질문의 정책 API 검색어는 기존 LLM 범위 판단에서 함께 추출합니다. 별도 모델 호출은 추가하지 않습니다.
  주제를 추출하지 못하면 이전 관심 분야로 임의 전환하지 않고 API 보완 검색을 생략합니다.
  `agents` 코드는 수정하지 않았으며, 검색어가 네 개이면 기존 세 개 제한에 맞춰 3개+1개로 전달합니다.
  Graph 보완 경로는 여전히 한 번이고, 여러 묶음의 전체 시간 제한은 50초입니다.
- `question_is_generated`는 서버 내부 표시이며 프론트가 보내는 필드가 아닙니다.

### 팀에서 정한 기본 자료 범위

1. 2026년 중앙행정기관 청년정책 시행계획
2. 17시도 광역지자체 2026년 청년정책 시행계획
   (서울·부산·대구·인천·광주·대전·울산·세종·경기·강원·충북·충남·전북·전남·경북·경남·제주)
3. 2026년 청년정책 시행계획 과제카드(중앙행정기관)
   (일자리·교육직업훈련·주거·금융복지문화·참여기반)

이 범위는 모델의 판단 지침으로 전달합니다. 자료 파일을 추가로 수집하거나 인덱스를 재구축한 것은 아닙니다.
시행계획·과제카드의 사업 소개만으로 현재 모집 중이라고 안내하지 않으며,
세부 자격·기간이 없으면 근거 부족 또는 추가 확인 대상으로 처리하도록 지시합니다.
기존의 공식 정책 API 보완 경로는 유지합니다. 광역 지역을 시군구 정보로 임의 확장하지 않습니다.
이 지침은 모델 판단의 정확성을 보장하는 코드 검증이나 문서 출처 화이트리스트 필터가 아닙니다.

### 변경 후 검증

`services/recommendation`에서 Python 3.11 환경으로 실행합니다.

```bash
python -B -m unittest discover -s app/checks -t . -v
```

새 검증 코드는 작업 범위를 지키고 Git의 `tests/` 제외 규칙을 피하기 위해 `app/checks`에 두었습니다.
실제 LLM·정책 API·RAG 검색은 가짜 객체로 대체합니다. FastAPI 입력 경계는 같은 DTO·Service를 연결한
테스트 경로로 확인하고, 실제 main/auth와 JWT 의존성은 실행하지 않습니다.
따라서 실제 인증·외부 연결·정책 추천 정확도 검증은 별도입니다.
기존 `recommendation/checks`는 작업 범위 밖이라 수정하지 않았습니다. 그 평가셋 중 질문 누락·빈 값·공백·null
네 사례는 새 동작에 따라 허용하는 기대값으로 `app/checks`에서 재검증합니다.

# 추천 Graph 복원 안내

임시 백업 `/tmp/ai-mini-graph-undo.nULvMy`의 구현을 현재 llm 브랜치 구조에 맞게 복원했습니다.
모든 변경은 `services/recommendation/app` 안에만 있습니다.
`app/agents`, RAG 서비스, 원래 실습 폴더, 기존 .env, 루트 문서·의존성 목록은 수정하지 않았습니다.

## pull 후 stash 복구

`git stash`에 보관돼 있던 Graph·추천 API·RAG 검색 클라이언트 코드를 복구했습니다.
원격에서 받은 `YouthPolicyAPI`·`PolicyAPIError` 구현은 유지하고, 같은 파일에 Graph의 연결 규격을 함께 복원했습니다.
`agents/policy_agent.py`는 원격 버전 그대로이며 수정하지 않았습니다.
원격 Agent의 `lookup(keyword, *, region_code=...) -> dict`와 Graph의
`lookup(query, missing_information) -> ApiLookupResult`는 규격이 달라 자동 연결하지 않았습니다.
기본 Graph는 이전과 같이 미연결 대체 객체를 사용합니다. 실제 연결에는 어댑터 구현·합의가 필요합니다.
테스트 파일은 삭제되지 않았으며, 원격 `.gitignore`의 `tests/` 규칙 때문에 Git 목록에서 제외됩니다.
stash는 안전을 위해 삭제하거나 적용 완료 처리하지 않고 남겨 두었습니다.

## 백업에서 가져온 부분과 달라진 부분

| 파일 | 역할 | 복원·변경 내용 |
|---|---|---|
| graph/state.py | Request/Response DTO와 Graph 작업 노트 | 백업 policy_graph.py의 데이터 모델 복원 |
| graph/nodes.py | LLM 호출, 충분성 판단, 조건 비교, 답변 생성 | 백업의 노드·프롬프트·출처 검증 복원 |
| graph/workflow.py | Service와 조건 분기 | 백업의 StateGraph·answer_question 복원 |
| tools/rag_api.py | RAG 검색 서버 호출 | 로컬 FAISS 직접 접근을 HTTP 호출로 변경 |
| tools/youth_policy_api.py | 외부 API·Agent 연결 규격 | 백업의 반환 형식을 복원하되 Agent 자체는 제외 |
| main.py | FastAPI Controller | 백업의 Graph 호출 부분을 별도 추천 API로 분리 |
| tests/test_policy_graph.py | API 비용 없는 검증 | 백업의 분기 테스트 복원 + HTTP 계약 테스트 |
| requirements.txt, ../.env.example | 실행 설정 예시 | 의존성 목록은 app 안에 두고, 설정 예시는 recommendation/.env.example 하나로 통합 |

PDF·웹 수집, 청킹, 임베딩, FAISS 생성 코드는 데이터 파이프라인/RAG 서비스 영역이므로 가져오지 않았습니다.
백업의 policy_api_agent.py에 있던 실제 Agent 구현도 가져오지 않았습니다.
이번 작업에서 agents 폴더 대신 다른 위치에 실제 Agent를 새로 구현하지도 않았습니다.

## 요청 한 번의 처리 순서

1. collect_profile: 나이·거주지·소득·취업 상태·관심 분야가 빠졌는지 확인합니다.
   빠졌으면 needs_profile과 추가 질문을 반환하며, RAG·LLM·외부 정책 API를 호출하지 않습니다.
2. build_search: 질문이 다섯 정책 범위에 속하는지 LLM으로 판단하고 검색어를 만듭니다.
3. retrieve: 별도 RAG 서버의 POST /rag-query에서 정책 본문·메타데이터·거리를 받습니다.
4. assess_information: 질문에 답하고 조건을 비교할 정책 자료가 충분한지 판단합니다.
5. 충분하면 compare_conditions에서 사용자 상황과 정책 조건을 비교합니다.
   부족하면 supplement에서 주입된 Agent의 lookup을 한 번 호출합니다.
6. Agent가 문서를 추가했다면 assess_information으로 돌아가 같은 검토를 다시 합니다.
   여전히 부족하거나 Agent가 미연결이면 답을 만들지 않고 insufficient로 종료합니다.
7. generate: 검토된 정책과 실제 근거 ID로 답변을 생성하고 출처를 검증합니다.

다섯 범위는 중앙정부 청년 지원사업, 지자체 청년 지원정책, 청년정책 신청 자격·지원 내용,
청년 지원사업 모집 공고, 청년정책 종합 안내입니다.
키워드가 문자 그대로 일치하는지만 보는 것이 아니라 의미상 범위를 판단합니다.

'정보가 충분함'은 '지원 자격이 됨'이 아닙니다.
예를 들어 나이가 정책 대상보다 많으면 조건 불일치이지 검색 실패가 아닙니다.
소득 단위가 다르거나 가구원 수가 필요하면 임의로 환산하지 않고 추가 확인을 요청합니다.
FAISS distance는 검색 거리이지 신청 자격 점수나 확률이 아닙니다.

## 실행

저장소 루트에서 아래 순서로 실행합니다. Python 3.11을 사용하세요.

```bash
cd services/recommendation
python3.11 -m venv app/.venv
source app/.venv/bin/activate
python -m pip install -r app/requirements.txt
cp -n .env.example .env
```

현재 폴더의 .env, 즉 services/recommendation/.env에 본인의 OPENAI_API_KEY,
필요시 LLM_MODEL과 RAG_API_URL을 입력합니다. 외부 정책 API를 사용할 때는
같은 파일에 YOUTH_POLICY_API_KEY도 설정합니다.
추천 서버와 정책 API 클라이언트는 이 설정 파일을 함께 사용합니다.
기존 app/.env나 실습 폴더의 .env는 자동으로 복사하거나 읽지 않습니다.
프로세스 환경변수는 .env보다 우선합니다. 실제 키는 Git에 올리지 마세요.
설정 파일이 필요 없다면 터미널·컨테이너에서 같은 환경변수를 주입해도 됩니다.

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
```

추천 API: http://127.0.0.1:8002/docs
상태 확인: http://127.0.0.1:8002/health
RAG 검색 서버는 별도 실행이 필요하며 기본 주소는 http://127.0.0.1:8001 입니다.
다른 컨테이너에서 실행한다면 RAG_API_URL을 그 컨테이너에서 접근 가능한 서버 주소로 지정하세요.
서버 실행·패키지 설치·.env 작성은 이번 복원 작업에서 자동으로 수행하지 않았습니다.

POST /recommend 예시:

```json
{
  "question": "응시료 지원 정책을 알려줘",
  "profile": {
    "age": 25,
    "region": "서울",
    "statuses": ["unemployed"],
    "income": "가구 기준중위소득 100% 이하",
    "employment_status": "미취업",
    "interests": ["education"],
    "details": ["시험 응시료"]
  },
  "source": "pdf",
  "top_k": 5
}
```

이 입력은 질문·사용자 상황이지 정책 근거가 아닙니다. context를 요청에 넣으면 422입니다.
response의 answer는 최종 안내, citations는 실제 사용 근거, policies는 정책별 조건 비교입니다.
status는 answered / needs_profile / out_of_scope / insufficient로 구분합니다.
api_status는 not_used / not_configured / used / no_results / failed / timeout으로 구분합니다.
node_path는 실제 방문한 노드 경로이며 분기 확인에 사용할 수 있습니다.
예전 prompt 요청 필드와 /rag-query 경로는 추천 서버 안에서만 호환 별칭으로 유지합니다.
원래 RAG 서버의 /rag-query는 검색만 하는 별도 API이며 변경하지 않았습니다.

## 다른 담당자와 맞출 계약

RAG 팀: POST /rag-query 요청은 prompt, source(pdf 또는 web), top_k입니다.
응답은 prompt, source, documents(content, metadata, distance), context, index_available입니다.
이 구조는 현재 저장소 services/rag/app/retrieval/policy_search.py의 규격을 따릅니다.
recommendation은 그 Python 모듈을 직접 import하지 않고 HTTP로만 호출합니다.
all이면 두 인덱스를 동시에 조회하고 번갈아 합쳐 총 top_k개를 남깁니다.
서로 다른 인덱스의 거리를 동일 기준이라고 가정하지 않습니다.
여기서 web은 기존에 적재된 웹 문서 검색이지 새 웹 검색 호출이 아닙니다.

Agent 팀: async lookup(query, missing_information) -> ApiLookupResult 규격을 맞춥니다.
result.documents에는 langchain_core.documents.Document 목록을 넣고
metadata에는 공식 URL/source, title, 정책 ID와 확인된 조건 등을 보존해 주세요.
result.status는 used, no_results, not_configured, failed, timeout 중 하나입니다.
정책 API 제공자·URL·인증·응답 규격과 키 이름은 아직 정하지 않았습니다.
백업에도 기관별 API 클라이언트는 미설정이었으며, 키만 넣어도 연결되는 구조는 아닙니다.
준비된 Agent 객체를 create_app(api_agent=agent) 또는 PolicyRagService(..., api_agent=agent)에 주입합니다.
실제 서버에서 주입하려면 담당자와 연결 코드를 합의해야 합니다.
기본 서버는 UnconfiguredPolicyAgent를 사용하므로 부족한 자료를 임의로 보완했다고 말하지 않습니다.
이 객체는 실제 Agent가 아니라 미연결 상태를 명시하는 대체 객체입니다.
건강 확인의 policy_agent_configured도 외부 API 실제 호출 성공을 보장하지 않습니다.

백엔드·프런트 팀: profile 필드·추천 API 경로·status·citations·추가 질문 표시 방법을 맞추세요.
인증·CORS·배포 연결은 이 복원에서 구현하지 않았으므로 공개 서비스 배포 전 별도 합의가 필요합니다.
응답은 후보 안내이며 신청 자격 확정이나 접수 대행이 아닙니다.

## 검증

services/recommendation에서 실행합니다.

```bash
python -B -m unittest discover -s app/tests -t . -v
```

실제 LLM·외부 정책 API·RAG 서버 없이 가짜 모델과 가짜 HTTP 응답으로 검증합니다.
따라서 분기·입출력 규격 검증이지 실제 정책 데이터 품질·모델 판단 정확도·운영 연결 검증은 아닙니다.
