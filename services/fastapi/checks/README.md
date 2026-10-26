# 검색 입력 검증

검사 위치는 `app/input_validation.py`다. `main.py`는 여기의 `RAGRequest`로 요청을 받고, `graph/state.py`는 기존 import 호환을 위해 요청 DTO를 재노출한다. Graph·Agent의 추천 판단 로직은 변경하지 않았다.

- 필수 profile: age(엄격한 정수 0~120), region(17개 약칭), statuses(1~5개), interests(1~4개).
- statuses: student/employed/unemployed/self_employed/freelance/none. 중복 불가, none은 단독.
- interests: employment/housing/education/startup/unknown. 중복 불가, unknown은 단독.
- details: 생략 시 [], null 거절. 최대 13개, 중복 불가, 선택한 interests의 상세 항목만 허용. unknown이면 []만 허용. `직무 교육`과 `직무교육`은 다른 값이다.
- question: 앞뒤 공백 제거 후 2~1000자. prompt 별칭 유지.
- source: 기존 web/pdf/all 및 기본 all 유지. top_k: 엄격한 정수 1~20, 기본 5 유지.
- 기존 Graph가 참조하는 income/employment_status/household_size는 선택 입력으로 유지하며 statuses에서 추정하지 않는다.
- 형식 오류는 FastAPI 기본 422와 detail 배열로 반환한다. 공통 error.message/request_id 변환은 이번 범위가 아니다.

실행:

```sh
python3 services/fastapi/checks/check_input_validation.py
```

고정 평가셋은 같은 폴더의 request_validation_cases.json이다. 메모리 내 FastAPI와 실제 DTO로 입력 검사를 확인하며, 잘못된 요청에서 처리 함수가 호출되지 않는지도 검사한다. 실제 서버·JWT 의존성·프론트·검색·LLM·DB를 호출하지 않는다. 기존 환경에 fastapi/httpx/pydantic이 필요하며 패키지 설치는 자동 실행하지 않는다.

검색 API는 `POST /search`입니다. 소득·고용 형태는 선택 입력이며 미입력 값을 추정하지 않습니다. 필수 설문은 DTO에서 검사하고, 소득 등 미확인 자격 정보는 정책별 확인 필요 항목으로 반환합니다.

되돌릴 때는 이번 입력 검증 변경만 되돌린다. 작업 전부터 존재한 statuses/details 수신 필드 변경은 보존한다. 커밋·푸시·서버 재시작·DB 변경은 별도 요청 없이는 수행하지 않는다.
