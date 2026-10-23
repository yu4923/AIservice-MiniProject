> 현재 구조는 services/fastapi 단일 실행이며 Python 검사는 tests・rag/tests・JWT 검증을 함께 실행합니다.

# 백엔드 CI 사용 안내

컨테이너 배포 없이 GitHub Actions에서 검증합니다. RAG와 추천의 테스트 job 분리는
배포 컨테이너 분리를 요구하지 않습니다. F/E와 음성은 이번 범위에서 제외합니다.

## 자동 검사: Backend CI

PR 생성·갱신, main push 또는 수동 실행 시 다음을 검사합니다.

- 인증: Java 21 / Gradle test・bootJar, 임시 MariaDB에서 회원가입・로그인・JWT 확인・로그아웃.
- RAG: 실제 FAISS와 가짜 임베딩을 사용하는 기존 전처리・검색・저장 테스트.
- 추천: 정책 API 모의 응답, Graph의 충분/부족/프로필 누락 분기, 내부 RAG 검색 계약.

자동 검사에는 실제 API 키를 넣지 않습니다. 테스트 DB 비밀번호는 일회용 runner의
fixture 값이며 운영 계정이 아닙니다. 모델 가중치・OpenAI・온통청년을 호출하지 않습니다.
pytest는 테스트가 없으면 실패하므로 테스트 파일 누락을 성공으로 처리하지 않습니다.
Java 테스트 XML과 Python JUnit XML은 Actions artifact에 7일 보관합니다.

## 수동 검사: Backend live integration

먼저 워크플로 파일을 main에 반영합니다. GitHub 저장소 Settings → Environments에서
`integration`을 만들고 필요한 Secret을 등록하세요.

- `OPENAI_API_KEY`: llm・graph・all 검사에 사용.
- `YOUTH_POLICY_API_KEY`: policy・graph・all 검사에 사용. 승인된 청년정책 키가 필요합니다.
- 선택 Variable `LLM_MODEL`: 기본 gpt-4o.

Actions → Backend live integration → Run workflow에서 main과 target을 선택합니다.
main 외 브랜치에서는 Secret을 사용하는 job을 실행하지 않습니다.

| target | 실제 실행 |
|---|---|
| kure | KURE 다운로드・임시 FAISS 저장・재로딩・검색. 유료 API 키 불필요 |
| policy | 온통청년 정책 검색・문서 변환・상세 조회 |
| llm | OpenAI 구조화된 정책 범위 판단 |
| graph | 빈 검색 결과를 주입한 뒤 실제 정책 API・LLM으로 보완・재평가・조건 비교・출처 포함 답변 |
| all | 위 검사 모두 |

`policy_keyword`는 정책명 검색어이며 기본 월세입니다. 검색 결과가 없으면 실패합니다.
`graph`는 외부 API 보완 경로를 검사하며 실제 RAG 서버・FAISS와의 전체 통합 검사는 아닙니다.
KURE 검사는 별도 프로세스에서 수행하고 임시 인덱스만 사용합니다. 기존 데이터는 변경하지 않습니다.
OpenAI 검사에는 요금이 발생할 수 있습니다. 원문 응답・키・사용자 프로필은 출력하지 않습니다.
데이터 변화・네트워크・모델 판단에 따라 수동 검사가 실패할 수 있습니다.

## 남은 저장소 설정

- PR 필수 검사에 Auth와 fastapi job을 등록하세요.
- integration Environment의 Secret과 필요 시 승인 규칙을 설정하세요.
- 첫 Actions 실행에서 Ubuntu 의존성 설치와 MariaDB 검사가 통과하는지 확인하세요.
- 실제 배포 연결・정책 정확도 평가・의존성 전체 lock은 별도 후속 작업입니다.
- CI 테스트는 Git에 포함하며 개인 실험용 tests는 다른 경로에서 계속 제외됩니다.
