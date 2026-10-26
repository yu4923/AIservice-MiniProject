"""PDF/ZIP batch preprocessing. Default input is services/fastapi/rag/documents/."""
import argparse
import json
import shutil
import sys
import tempfile
import unicodedata
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR.parent))
from rag.utils.ingestion import ingest_paper
from rag.utils.policy_preprocessing import Settings


def iter_inputs(inputs):
    seen = set()
    for item in inputs:
        path = Path(item).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        candidates = sorted(path.rglob("*")) if path.is_dir() else [path]
        root = path if path.is_dir() else path.parent
        for candidate in candidates:
            if not candidate.is_file() or candidate.suffix.lower() not in {".pdf", ".zip"}:
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            source = unicodedata.normalize("NFC", candidate.relative_to(root).as_posix())
            if candidate.suffix.lower() == ".pdf":
                yield candidate, source
            else:
                with zipfile.ZipFile(candidate) as archive:
                    members = [m for m in archive.infolist() if not m.is_dir()
                               and m.filename.lower().endswith(".pdf")
                               and "__MACOSX" not in m.filename.split("/")]
                    if len(members) > 1024 or sum(m.file_size for m in members) > 1_000_000_000:
                        raise ValueError(f"ZIP size/member limit exceeded: {candidate.name}")
                    for member in sorted(members, key=lambda m: m.filename):
                        if member.file_size > 200_000_000:
                            raise ValueError("Individual PDF exceeds 200 MB")
                        # Do not extract archive paths onto the filesystem.
                        with tempfile.TemporaryDirectory(prefix="policy-pdf-") as directory:
                            target = Path(directory) / "input.pdf"
                            with archive.open(member) as src, target.open("wb") as dst:
                                shutil.copyfileobj(src, dst, length=65536)
                            yield target, source + "!/" + unicodedata.normalize("NFC", member.filename)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", nargs="+", default=[str(BASE_DIR / "documents")])
    parser.add_argument("--dry-run", action="store_true", help="Save JSONL without embeddings/API key")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--ocr", choices=["auto", "off", "required"], default="auto")
    parser.add_argument("--first-page", type=int, default=1)
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--max-documents", type=int)
    parser.add_argument("--chunk-chars", type=int, default=2200)
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args(argv)
    if (args.max_pages or args.first_page != 1) and not args.dry_run:
        parser.error("Page-limited runs require --dry-run")
    if args.max_documents is not None and args.max_documents < 1:
        parser.error("--max-documents must be positive")
    settings = Settings(ocr=args.ocr, max_chars=args.chunk_chars,
                        max_pages=args.max_pages, first_page=args.first_page)
    success, failures = 0, []
    try:
        for path, source in iter_inputs(args.input):
            if args.max_documents and success + len(failures) >= args.max_documents:
                break
            try:
                _, result = ingest_paper(path, source_name=source, dry_run=args.dry_run,
                                         output_dir=args.output_dir, settings=settings)
                success += 1
                print(json.dumps({"source": source, **result}, ensure_ascii=False), flush=True)
            except Exception as exc:
                failures.append({"source": source, "error": str(exc)})
                print(json.dumps(failures[-1], ensure_ascii=False), file=sys.stderr, flush=True)
                if args.fail_fast:
                    break
    except Exception as exc:
        failures.append({"error": str(exc)})
    if not success and not failures:
        print("적재할 PDF/ZIP이 없습니다.")
    print(json.dumps({"successful_documents": success, "failed_documents": len(failures),
                      "failures": failures}, ensure_ascii=False), flush=True)
    return 1 if failures or not success else 0


if __name__ == "__main__":
    raise SystemExit(main())
