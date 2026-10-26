"""고정 평가셋으로 DTO 검증과 422 이전의 추천 처리 차단을 확인한다."""

import ast
import copy
import json
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR))
from app.input_validation import RAGRequest


class ProcessingProbe:
    """외부 API 대신 검증을 통과한 요청만 전달되는지 기록한다."""

    def __init__(self):
        """개인정보 없이 실행 횟수만 초기화한다."""
        self.calls = 0

    def receive(self, request: RAGRequest):
        """수신 경계만 검사하므로 JWT·검색·LLM은 호출하지 않는다."""
        self.calls += 1
        return request.model_dump()


def payload_for(fixture, case):
    """평가 사례끼리 배열 변경이 섞이지 않게 원본을 복사한다."""
    payload = copy.deepcopy(fixture)
    for path, value in case.get("set", {}).items():
        parts = path.split(".")
        target = payload
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value
    for path in case.get("remove", []):
        parts = path.split(".")
        target = payload
        for part in parts[:-1]:
            target = target[part]
        del target[parts[-1]]
    return payload


def run():
    """동일 DTO를 쓰는 메모리 내 FastAPI에서 허용·거절과 처리 호출 수를 검사한다."""
    for name in ("app/input_validation.py", "app/graph/state.py", "app/main.py"):
        ast.parse((SERVICE_DIR / name).read_text())
    data = json.loads(Path(__file__).with_name("request_validation_cases.json").read_text())
    probe = ProcessingProbe()
    application = FastAPI()

    @application.post("/search")
    def receive(request: RAGRequest):
        """실제 API와 같은 입력 DTO를 FastAPI 수신 경계에 연결한다."""
        return probe.receive(request)

    with TestClient(application) as client:
        for case in data["cases"]:
            before = probe.calls
            response = client.post("/search", json=payload_for(data["fixture"], case))
            assert response.status_code == case["expected_status"], case["id"] + ": status mismatch"
            if response.status_code == 422:
                assert probe.calls == before, case["id"] + ": invalid request reached processing"
                location = ["body", *case["error_field"].split(".")]
                assert any(error["loc"][:len(location)] == location for error in response.json()["detail"]), case["id"] + ": field mismatch"
            else:
                assert probe.calls == before + 1, case["id"] + ": valid request not forwarded"
            print(case["id"], "PASS", case["name"])
    # DTO 이동 후에도 기존 Graph의 import가 같은 클래스를 참조하는지 확인한다.
    from app.graph.state import RAGRequest as GraphRequest
    assert GraphRequest is RAGRequest
    parsed = RAGRequest.model_validate(data["fixture"])
    assert parsed.profile.statuses == data["fixture"]["profile"]["statuses"]
    assert parsed.profile.details == data["fixture"]["profile"]["details"]
    assert "서울" not in repr(parsed.profile) and "서울" not in str(parsed.profile)
    print(f"PASS: {len(data['cases'])} cases; syntax; Graph import compatibility; parameter preservation")
    print("NOT RUN: actual JWT dependency, live API integration, Graph business logic, DB, RAG and LLM")


if __name__ == "__main__":
    run()
