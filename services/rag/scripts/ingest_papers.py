"""Ingest every PDF under the fixed documents directory."""
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
from app.utils.ingestion import ingest_paper


def main():
    directory = BASE_DIR / "documents"
    paths = sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")
    if not paths:
        print("documents/에 적재할 PDF가 없습니다.")
    for path in paths:
        _, result = ingest_paper(path, source_name=path.relative_to(directory).as_posix())
        print(path.name, json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
