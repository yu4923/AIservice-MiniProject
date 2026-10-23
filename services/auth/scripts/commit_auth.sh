#!/bin/sh
# 다른 담당자의 스테이징을 보존하면서 auth 경로만 커밋한다.
set -eu
if [ "$#" -ne 1 ] || [ -z "$1" ]; then
    echo 'Usage: ./scripts/commit_auth.sh "commit message"' >&2
    exit 2
fi
auth_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
repo_root=$(git -C "$auth_dir" rev-parse --show-toplevel)
auth_path=services/auth
if [ "$auth_dir" != "$repo_root/$auth_path" ]; then
    echo 'Expected services/auth within the repository; refused to stage.' >&2
    exit 1
fi
cd "$repo_root"
git add --all -- "$auth_path"
if git diff --cached --quiet -- "$auth_path"; then
    echo 'No auth changes to commit.'
    exit 0
fi
# --only는 다른 경로에 이미 올라간 변경도 이번 커밋에서 제외한다.
git commit --only -m "$1" -- "$auth_path"
