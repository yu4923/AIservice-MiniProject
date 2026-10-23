#!/usr/bin/env python3
"""Disposable MariaDB + executable Spring jar smoke check. Never uses an existing DB/.env.
Only fixed public test fixtures are used. Removes only its own container and process.
Prerequisites: Docker, Java 17+, ./gradlew bootJar. No third-party Python dependencies.
"""
import base64
import hashlib
import hmac
import http.client
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "mariadb:11.4.13"
FIXTURE_DB_PASSWORD = "auth-db-test-fixture-only"
FIXTURE_JWT_SECRET = "auth-jwt-test-fixture-only-never-deploy"
NAME = f"auth-spring-validation-{os.getpid()}"
checks = []
server = None
created = False


def docker(*args, data=None):
    return subprocess.run(["docker", *args], input=data, text=True, capture_output=True, check=True).stdout.strip()


def check(label, condition):
    checks.append({"check": label, "status": "PASS" if condition else "FAIL"})
    if not condition:
        raise AssertionError(label)


def request(port, method, path, body=None, cookie=None, origin=None, headers=None):
    values = dict(headers or {})
    if body is not None:
        values["Content-Type"] = "application/json"
        body = json.dumps(body)
    if cookie:
        values["Cookie"] = cookie
    if origin:
        values["Origin"] = origin
    connection = http.client.HTTPConnection("localhost", port, timeout=10)
    try:
        connection.request(method, path, body, values)
        result = connection.getresponse()
        payload = result.read().decode("utf-8")
        return result.status, result.getheaders(), json.loads(payload) if payload else None
    finally:
        connection.close()


def token(expiry):
    def b64(obj):
        return base64.urlsafe_b64encode(json.dumps(obj, separators=(",", ":")).encode()).rstrip(b"=").decode()
    data = b64({"alg": "HS256", "typ": "JWT"}) + "." + b64({"iss": "simple-auth-server", "sub": "1", "id": "fixture-user", "exp": expiry})
    return data + "." + base64.urlsafe_b64encode(hmac.new(FIXTURE_JWT_SECRET.encode(), data.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()


try:
    # Docker allocates a free loopback host port atomically; no existing published port is reused.
    docker("run", "--detach", "--rm", "--name", NAME, "--publish", "127.0.0.1::3306",
           "--env", "MARIADB_DATABASE=sql_db", "--env", "MARIADB_USER=auth_fixture",
           "--env", "MARIADB_PASSWORD=" + FIXTURE_DB_PASSWORD,
           "--env", "MARIADB_ROOT_PASSWORD=auth-root-test-fixture-only", IMAGE)
    created = True
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        result = subprocess.run(["docker", "exec", NAME, "healthcheck.sh", "--connect", "--innodb_initialized"], capture_output=True)
        if result.returncode == 0:
            break
        time.sleep(1)
    check("isolated MariaDB readiness", result.returncode == 0)
    db_port = int(docker("port", NAME, "3306/tcp").rsplit(":", 1)[1])
    schema = (ROOT / "src/main/resources/db/schema.sql").read_text()
    def sql(statement):
        return docker("exec", "-i", "--env", "MYSQL_PWD=" + FIXTURE_DB_PASSWORD,
                      NAME, "mariadb", "--user=auth_fixture", "--database=sql_db", "--batch", "--skip-column-names", data=statement)
    old_schema = """CREATE TABLE users (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(100) NOT NULL,
        password VARCHAR(255) NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_users_username (username)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"""
    sql(old_schema)
    sql("INSERT INTO users (username,password) VALUES ('migration-fixture','fixture-preserved-hash');")
    migration = (ROOT / "docs/sql/migrate-users-no-id-pw.sql").read_text()
    sql(migration)
    check("migration preserves existing account no id and password hash", sql("SELECT CONCAT(no, ':', id, ':', pw) FROM users WHERE id='migration-fixture';") == "1:migration-fixture:fixture-preserved-hash")
    check("migration leaves exactly no id pw", sql("SELECT GROUP_CONCAT(column_name ORDER BY ordinal_position) FROM information_schema.columns WHERE table_schema='sql_db' AND table_name='users';") == "no,id,pw")
    sql("DROP TABLE users;")
    sql(schema)
    sql(schema)
    check("MariaDB schema initialization twice", sql("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='sql_db' AND table_name='users';") == "1")
    jar = next((ROOT / "build/libs").glob("auth-service-*.jar"))
    with tempfile.TemporaryFile(mode="w+t") as log:
        environment = os.environ.copy()
        environment.update(DB_URL=f"jdbc:mariadb://127.0.0.1:{db_port}/sql_db", DB_USER="auth_fixture",
                           DB_PASSWORD=FIXTURE_DB_PASSWORD, JWT_SECRET=FIXTURE_JWT_SECRET,
                           SERVER_PORT="0", SERVER_ADDRESS="127.0.0.1", SPRING_PROFILES_ACTIVE="validation",
                           COOKIE_SECURE="false", FRONTEND_ORIGIN="http://localhost:5174")
        server = subprocess.Popen(["java", "-jar", str(jar)], cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
        port = None
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            log.seek(0)
            match = re.search(r"Tomcat started on port (\d+)", log.read())
            if match:
                port = int(match.group(1))
                break
            if server.poll() is not None:
                break
            time.sleep(0.5)
        check("executable Spring jar starts against MariaDB", port is not None)
        status, _, body = request(port, "GET", "/api/auth/check")
        check("unauthenticated protected path 401", status == 401 and body["reason"] == "UNAUTHORIZED")
        fixture = {"id": "fixture-user", "password": "fixture-password"}
        status, _, body = request(port, "POST", "/api/auth/signup", fixture, origin="http://localhost:5174")
        check("signup MariaDB insert 201", status == 201 and body["id"] == fixture["id"])
        check("new schema contains exactly no id pw", sql("SELECT GROUP_CONCAT(column_name ORDER BY ordinal_position) FROM information_schema.columns WHERE table_schema='sql_db' AND table_name='users';") == "no,id,pw")
        check("stored password BCrypt cost 12", sql("SELECT pw FROM users WHERE id='fixture-user';").startswith("$2a$12$"))
        sql(schema)
        check("repeated schema preserves fixture row", sql("SELECT COUNT(*) FROM users WHERE id='fixture-user';") == "1")
        status, _, _ = request(port, "POST", "/api/signup", fixture)
        check("duplicate signup 409", status == 409)
        status, _, _ = request(port, "POST", "/api/login", {**fixture, "password": "wrong-fixture"})
        check("wrong password 401", status == 401)
        status, _, _ = request(port, "POST", "/api/login", {"id": "' OR 1=1 --", "password": "fixture-password"})
        check("SQL injection login rejected", status == 401)
        status, headers, body = request(port, "POST", "/api/login", fixture, origin="http://localhost:5174")
        cookies = [value for key, value in headers if key.lower() == "set-cookie"]
        parts = {value.split("=",1)[0]: value.split(";",1)[0] for value in cookies}
        check("login 200 without exposed JWT body", status == 200 and body["ok"] and "access_token" not in body)
        check("one HttpOnly JWT cookie", len(cookies) == 1 and "HttpOnly" in cookies[0] and "SameSite=Lax" in cookies[0] and "Path=/" in cookies[0])
        check("actual login credentialed CORS", ("Access-Control-Allow-Origin", "http://localhost:5174") in headers and ("Access-Control-Allow-Credentials", "true") in headers)
        for kind, expected in [("ACCESS_TOKEN", "jwt")]:
            status, _, body = request(port, "GET", "/api/auth/check", cookie=parts[kind])
            check(kind + " authenticates alone", status == 200 and body["via"] == expected)
        for label, invalid in [("tampered", parts["ACCESS_TOKEN"].split("=",1)[1] + "x"), ("expired", token(int(time.time())-60))]:
            status, _, _ = request(port, "GET", "/api/auth/check", cookie="ACCESS_TOKEN=" + invalid)
            check(label + " JWT rejected 401 without session", status == 401)
        status, _, _ = request(port, "OPTIONS", "/api/login", origin="http://localhost:5174", headers={"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        check("credentialed preflight 204", status == 204)
        status, _, body = request(port, "POST", "/api/logout", origin="https://untrusted.example")
        check("foreign Origin mutation rejected 403", status == 403 and body["error"]["code"] == "ORIGIN_NOT_ALLOWED")
        status, headers, body = request(port, "POST", "/api/logout", cookie="SESSION_ID=old-session")
        removed = [v for k,v in headers if k.lower() == "set-cookie"]
        check("logout JSON and all cookies cleared", status == 200 and body["ok"] and len(removed) == 3 and all("Max-Age=0" in c for c in removed))
        status, _, _ = request(port, "GET", "/api/auth/check", cookie="SESSION_ID=old-session")
        check("legacy session cannot authenticate", status == 401)
        status, _, _ = request(port, "GET", "/login")
        check("legacy HTML route removed 404", status == 404)
except Exception as error:
    checks.append({"check": "verification runner", "status": "FAIL", "type": type(error).__name__})
finally:
    if server is not None:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
    if created:
        try:
            docker("stop", "--time", "10", NAME)
            checks.append({"check": "disposable container and anonymous volume removed", "status": "PASS"})
        except subprocess.SubprocessError:
            checks.append({"check": "disposable container cleanup", "status": "FAIL"})
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    raise SystemExit(1 if any(item["status"] == "FAIL" for item in checks) else 0)
