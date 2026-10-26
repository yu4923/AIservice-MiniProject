"""#JWT_code: 실제 인증 모듈의 파일·콘솔 로그를 비공개 설정 없이 검증한다."""
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt

KEY = "logging-public-fixture-only-never-deploy"


class JwtLoggingTests(unittest.TestCase):
    """#JWT_code: 인증 판정·추적 ID와 로그의 민감정보 제외를 확인한다."""

    def setUp(self):
        """#JWT_code: 실제 .env와 운영 로그를 건드리지 않도록 임시 복사본을 사용한다."""
        self.temporary = tempfile.TemporaryDirectory(prefix="jwt-log-check-")
        target = Path(self.temporary.name) / "recommendation/app/auth.py"
        target.parent.mkdir(parents=True)
        shutil.copy2(Path(__file__).resolve().parents[1] / "app/auth.py", target)
        self.name = "jwt_log_fixture_" + uuid4().hex
        spec = importlib.util.spec_from_file_location(self.name, target)
        self.module = importlib.util.module_from_spec(spec)
        sys.modules[self.name] = self.module
        self.console = io.StringIO()
        with patch.dict(os.environ, {"JWT_SECRET": KEY, "FRONTEND_ORIGIN": "http://localhost:5174"}), \
                patch("dotenv.load_dotenv"), patch("sys.stderr", self.console):
            spec.loader.exec_module(self.module)
        app = FastAPI()

        @app.post("/search")
        async def protected(user=Depends(self.module.get_current_user)):
            """#JWT_code: 업무 처리 없이 실제 JWT 의존성만 실행한다."""
            return {"ok": True}

        self.client = TestClient(app)

    def tearDown(self):
        """#JWT_code: 각 검사 뒤 핸들러를 닫아 중복 출력과 임시 파일 잠금을 막는다."""
        self.client.close()
        logger = self.module._audit_logger()
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)
        sys.modules.pop(self.name, None)
        self.temporary.cleanup()

    def token(self, **changes):
        """#JWT_code: 실제 계정 대신 공개 fixture로 유효·만료 JWT를 만든다."""
        return jwt.encode({"iss": "simple-auth-server", "sub": "7", "id": "private-user",
                           "exp": int(time.time()) + 60, **changes}, KEY, algorithm="HS256")

    def records(self):
        """#JWT_code: 두 출력 대상의 JSON 레코드를 동일한 형식으로 비교한다."""
        files = [json.loads(line) for path in self.module.JWT_LOG_DIR.glob("jwt-*.log")
                 for line in path.read_text().splitlines()]
        console = [json.loads(line) for line in self.console.getvalue().splitlines()]
        return files, console

    def test_success_and_failure_have_matching_file_and_console_records(self):
        """#JWT_code: 성공·누락·만료 판정이 파일과 터미널 양쪽에 남아야 한다."""
        for token, expected in ((self.token(), 200), (None, 401),
                                (self.token(exp=int(time.time()) - 60), 401)):
            request_id = str(uuid4())
            headers = {"X-Request-Id": request_id}
            if token is not None:
                headers["Cookie"] = "ACCESS_TOKEN=" + token
            response = self.client.post("/search", headers=headers)
            self.assertEqual(response.status_code, expected)
            self.assertEqual(response.headers["X-Request-Id"], request_id)
        files, console = self.records()
        self.assertEqual(files, console)
        self.assertEqual([r["reason"] for r in files], ["logger_ready", "valid", "missing_cookie", "expired"])

    def test_credentials_body_and_query_are_absent(self):
        """#JWT_code: 토큰·서명키·사용자 입력을 로그 검색으로 복원할 수 없어야 한다."""
        token = self.token()
        self.client.post("/search?password=private-query", headers={"Cookie": "ACCESS_TOKEN=" + token},
                         json={"question": "private-question", "password": "private-password"})
        files, console = self.records()
        text = json.dumps(files + console)
        for private in (token, KEY, "private-user", "private-query", "private-question", "private-password"):
            self.assertNotIn(private, text)

    def test_logger_reuse_does_not_duplicate_handlers(self):
        """#JWT_code: 반복 요청마다 핸들러가 늘어 로그가 중복되는 것을 막는다."""
        for _ in range(3):
            self.module._audit_logger()
            self.client.post("/search")
        files, console = self.records()
        self.assertEqual(files, console)
        self.assertEqual(len(files), 4)
        self.assertEqual(len(self.module._audit_logger().handlers), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
