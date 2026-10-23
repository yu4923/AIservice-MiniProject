# 통합 Docker Compose 실행 안내

저장소 최상위 `compose.yaml`을 사용합니다. 브라우저 → Vue 프론트 → Spring 인증 및 통합 FastAPI → FAISS·외부 LLM 구조입니다. FastAPI 안에 추천과 RAG 검색이 함께 있습니다. 선택 기능인 음성은 포함하지 않았습니다.

## 서비스와 주소

| 서비스 | 역할 | 기본 접속 주소 |
|---|---|---|
| frontend | Vue 빌드 결과를 Nginx로 제공 | http://localhost:5174 |
| auth | 회원가입·로그인·JWT | http://localhost:8080/health |
| fastapi | 내부 FAISS 검색·정책 추천·LLM 답변 | http://localhost:8002/docs |
| db | MariaDB 회원정보 | Compose 내부 `db:3306`만 사용 |
| ingest | `tools` 프로필의 일회성 적재 도구 | 공개 포트 없음 |

공개 포트는 `127.0.0.1`에만 연결됩니다. 다른 PC나 외부 인터넷 접속은 별도 설정이 필요합니다. 기존 개별 Compose 파일도 남아 있으므로 같은 포트를 사용하는 컨테이너와 동시에 실행하지 마세요.

## 1. 로컬 환경변수 준비

명령은 저장소 최상위에서 실행합니다. 기존 `.env`가 있다면 덮어쓰지 마세요.

```bash
cp -n .env.example .env
chmod 600 .env
```

`.env`에 `DB_PASSWORD`, `MARIADB_ROOT_PASSWORD`, `JWT_SECRET`을 채웁니다. `DB_USER`는 전용 계정을 사용합니다. Compose가 같은 `JWT_SECRET`을 auth와 fastapi에 전달합니다.

- `OPENAI_API_KEY`: 실제 LLM 답변 생성에 필요합니다. PDF 임베딩에는 사용하지 않습니다.
- `YOUTH_POLICY_API_KEY`: 외부 정책 API 보완을 사용할 때 설정합니다.
- `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`: 별도 웹 수집 적재에 사용하는 선택 설정입니다.
- `FRONTEND_ORIGIN`, `LOGIN_SUCCESS_URL`: 브라우저 주소와 일치시킵니다. 기본값은 `http://localhost:5174`입니다.
- 실제 키·계정·`.env`·로그·원본 PDF·FAISS·모델 캐시는 GitHub에 올리지 않습니다.

루트 Compose는 각 서비스의 `.env`를 자동으로 합쳐 읽지 않습니다. 셸에 export한 동일 이름의 값은 루트 `.env`보다 우선할 수 있습니다. 실제 비밀값이 출력될 수 있으므로 `docker compose config` 전체 출력을 공유하지 마세요.

## 2. 폴더와 설정 확인

```bash
mkdir -p services/rag/documents data/faiss-kure-v1 data/preprocessed data/hf-cache
docker compose config --quiet
docker compose config --services
```

기존 로컬 PDF 위치를 유지하기 위해 적재 입력은 `services/rag/documents`입니다. 실행 코드는 새 `services/fastapi`에서 빌드합니다. 입력 PDF는 이미지나 저장소에 포함하지 않고 직접 준비합니다.

## 3. 본문 적재 준비

**같은 자료와 모델로 만든 정상 FAISS가 이미 있다면 재적재하지 않습니다.** `data/faiss-kure-v1/pdf/current.json`과 그 포인터가 가리키는 `generations/<generation>/index.faiss`, `index.pkl`이 함께 있어야 합니다. 신뢰할 수 있는 로컬 인덱스만 사용합니다.

새 자료를 준비하는 경우 전처리를 먼저 검사합니다.

```bash
docker compose --profile tools run --rm --no-deps --build ingest python rag/scripts/ingest_papers.py --input /input --dry-run
```

`data/preprocessed/pdf`의 manifest, 청크, 출처, 검토 표시를 데이터 담당자와 확인한 후 실제 적재합니다.

```bash
docker compose --profile tools run --rm --no-deps --build ingest
```

KURE 모델 다운로드·CPU 임베딩에 시간이 걸릴 수 있습니다. 메모리가 부족하면 `RAG_EMBEDDING_BATCH_SIZE`를 줄여 실행할 수 있습니다. 적재 컨테이너를 수동 중지하면 그 실행이 자동 재개된다고 가정하지 마세요.

서버에는 `RAG_BUILD_ON_START=false`를 설정했습니다. 서버 시작 시 자료 수집이나 재적재를 하지 않고 미리 준비한 인덱스를 사용합니다. `RAG_REQUIRED_INDEXES=pdf` 값은 자동 적재가 꺼져 있을 때 인덱스 존재를 보장하지 않습니다. 실제 검색으로 확인해야 합니다.

이번 본문 적재에 사용한 설정은 `nlpai-lab/KURE-v1`, 정규화된 1,024차원 벡터, `policy-preprocess-v3`, 자동 OCR, 정책·항목 경계를 고려한 2,200자 기준 분할입니다. 표는 통째로 보존해 길이 기준을 넘을 수 있습니다. 분리한 총괄표 등 보조 자료는 본문 검색 인덱스에 포함되지 않았으므로 전체 자료가 검색된다고 보장하지 않습니다.

## 4. 통합 서비스 실행

적재가 완료되면 실행합니다.

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail 80 frontend auth fastapi
```

기본 실행은 `ingest`를 실행하지 않습니다. DB가 준비된 후 auth가 시작되고, auth와 fastapi 상태 검사가 통과하면 frontend가 시작됩니다. 상태 검사 성공은 실제 로그인·검색·외부 LLM 응답까지 보증하지 않습니다.

DB를 처음 만들 때 팀의 `schema.sql`을 적용합니다. 기존 DB Volume에는 스키마나 `.env`의 변경된 비밀번호가 자동 반영되지 않습니다. `db_data`는 다른 Compose 프로젝트의 DB Volume과 별개이며 기존 회원정보가 자동 이전되지 않습니다.

이전 분리형 `rag`, `recommendation` 컨테이너가 남아 있으면 FastAPI 실행 전에 해당 컨테이너만 중지해 포트 충돌을 피하세요. 기존 컨테이너 이름·사용 포트는 `docker ps`로 먼저 확인합니다.

## 5. 화면과 검색 점검

1. `http://localhost:5174`에서 회원가입·로그인을 확인합니다.
2. 실제 설문을 입력합니다. 질문·추천 요청은 `question`과 `profile`을 함께 보냅니다.
3. 정책 질문을 입력해 답변의 내용·연도·출처·PDF 쪽수를 확인합니다.
4. 문서에 있는 정책 내용은 안내하되, 현재 모집 여부가 미확인이면 최신 공식 공고 확인 안내가 나오는지 확인합니다.
5. 출처가 실제 답변을 뒷받침하는지 원문과 비교합니다. 확인되지 않은 자격조건을 확정 정보로 취급하지 않습니다.
6. 첫 질문과 이후 질문의 응답 시간을 구분해 기록합니다. 첫 검색은 모델 로딩으로 느릴 수 있습니다.

설문은 같은 브라우저 탭의 `sessionStorage`에 계정별로 저장됩니다. 새로고침 후 인증 확인이 성공하면 복원합니다. 로그아웃·계정 변경 시 삭제되며 브라우저 저장소를 사용할 수 없는 경우 유지되지 않을 수 있습니다. 비밀번호·JWT는 이 설문 저장에 포함하지 않습니다.

## 6. 데이터와 로그 보존

| 저장 공간 | 컨테이너 경로 | 용도 |
|---|---|---|
| `db_data` Volume | DB `/var/lib/mysql` | 회원정보 |
| PC `data/faiss-kure-v1` | `/workspace/data/faiss-kure-v1` | 적재는 쓰기, fastapi는 읽기 전용 |
| PC `data/hf-cache` | `/cache/huggingface` | KURE 모델 재다운로드 방지 |
| PC `data/preprocessed` | 적재 `/workspace/data/preprocessed` | 전처리 결과 |
| PC `services/rag/documents` | 적재 `/input` | 원본 PDF 읽기 전용 |
| `auth_jwt_logs` Volume | auth `/app/jwt_log` | 인증 로그 |
| `recommendation_jwt_logs` Volume | fastapi `/workspace/services/fastapi/jwt_log` | 통합 서버 인증 로그 |

기존 로그를 보존하려고 `recommendation_jwt_logs`라는 Volume 이름은 유지했습니다. FAISS 백업은 적재가 끝난 후 `current.json`과 `generations`를 포함한 폴더 전체를 복사합니다. 컨테이너를 다시 만들어도 연결된 저장 공간은 남지만, PC 폴더나 Volume을 지우면 데이터가 사라집니다.

```bash
docker compose exec auth ls -lh /app/jwt_log
docker compose exec fastapi ls -lh /workspace/services/fastapi/jwt_log
```

## 7. 변경 적용·재시작·종료

프론트의 `VITE_*` 공개 API 주소는 이미지 빌드 시 반영됩니다. 브라우저용 주소는 `localhost`를 사용하고 Compose 서비스 이름을 사용하지 않습니다. 포트·주소를 바꾸면 프론트도 다시 빌드합니다. 비밀키를 프론트 빌드 인수로 전달하지 않습니다.

```bash
# 프론트 코드 또는 공개 API 주소 변경 후
docker compose up -d --build --no-deps frontend
# 통합 FastAPI 코드 변경 후
docker compose up -d --build --no-deps fastapi
# 설정·코드는 그대로 두고 프로세스만 재시작
docker compose restart
```

재시작 후 기존 계정으로 로그인하고 재적재 없이 검색되는지 확인합니다. 종료와 재실행은 다음 명령입니다.

```bash
docker compose down
docker compose up -d
```

`down -v`는 DB·로그 Volume을 삭제하므로 사용하지 마세요. 서비스에는 `restart: unless-stopped`가 적용돼 있지만, 수동 중지나 `unhealthy` 상태만으로 자동 재시작되는 것은 아닙니다. Docker Desktop 자체가 실행돼 있어야 합니다. 일회성 `ingest`에는 자동 재시작을 설정하지 않았습니다.
