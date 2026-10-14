#!/bin/bash
# usage: run_real.sh NAME SCRIPT.json "PROMPT" [extra codex args...]   -> exam/real/NAME/{requests,stdout.txt,workdir}
set -e; HERE="$(cd "$(dirname "$0")/.." && pwd)"; N=$1; SC=$2; PR=$3; shift 3
CODEX=${CODEX_CMD:-$HERE/target/codex-0.162.1-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex}
OUT=${OUT_ROOT:-$HERE/exam/real}/$N; rm -rf "$OUT"; mkdir -p "$OUT/requests" "$OUT/workdir"
[ -d "$HERE/exam/fixtures/$N" ] && cp -r "$HERE/exam/fixtures/$N/." "$OUT/workdir/"
PORT=$((19000 + RANDOM % 900))
python3 "$HERE/exam/mock_model.py" $PORT "$SC" "$OUT/requests" >"$OUT/mock.log" 2>&1 & MP=$!
sleep 0.7
( cd "$OUT/workdir" && HOME="$HERE/home" CODEX_HOME="$HERE/home/.codex" MOCK_KEY=x timeout 120 $CODEX exec --skip-git-repo-check \
  -c 'model_provider="mock"' -c "model_providers.mock={name=\"mock\",base_url=\"http://127.0.0.1:$PORT/v1\",wire_api=\"responses\",env_key=\"MOCK_KEY\"}" -c 'model="mock-1"' "$@" "$PR" </dev/null ) >"$OUT/stdout.txt" 2>&1 || true
kill $MP 2>/dev/null; wait $MP 2>/dev/null || true
echo "$N: $(ls $OUT/requests | wc -l) requests"
