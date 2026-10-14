#!/bin/bash
# usage: run_scn.sh NAME   (reads scenarios2/meta.json); env CODEX_CMD, OUT_ROOT
set -e; HERE="$(cd "$(dirname "$0")/.." && pwd)"; N=$1
CODEX=${CODEX_CMD:-$HERE/target/codex-0.162.1-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex}
OUT=${OUT_ROOT:-$HERE/exam/real2}/$N; rm -rf "$OUT"; mkdir -p "$OUT/requests" "$OUT/workdir"
[ -d "$HERE/exam/fixtures2/$N" ] && cp -r "$HERE/exam/fixtures2/$N/." "$OUT/workdir/"
read -r PR STDIN NOSKIP ARGS < <(python3 - "$N" <<'PY'
import json,sys,shlex
m=json.load(open('scenarios2/meta.json'))[sys.argv[1]]
print(shlex.quote(m['prompt']),int(bool(m.get('stdin'))),int(bool(m.get('noskip'))),' '.join(shlex.quote(a) for a in m.get('args',[])))
PY
)
eval "PRV=$PR"
PORT=$((19000 + RANDOM % 900))
python3 "$HERE/exam/mock_model.py" $PORT "scenarios2/$N.json" "$OUT/requests" >"$OUT/mock.log" 2>&1 & MP=$!
sleep 0.7
SK="--skip-git-repo-check"; [ "$NOSKIP" = "1" ] && SK=""
CMDLINE="timeout 120 $CODEX exec $SK -c 'model_provider=\"mock\"' -c 'model_providers.mock={name=\"mock\",base_url=\"http://127.0.0.1:$PORT/v1\",wire_api=\"responses\",env_key=\"MOCK_KEY\"}' $ARGS"
( cd "$OUT/workdir" && export HOME="$HERE/home" CODEX_HOME="$HERE/home/.codex" MOCK_KEY=x
  if [ "$STDIN" = "1" ]; then eval "$CMDLINE" - <<< "$PRV" ; else eval "$CMDLINE" "\"\$PRV\"" </dev/null; fi ) >"$OUT/stdout.txt" 2>"$OUT/stderr.txt"; echo $? > "$OUT/exit_code"
kill $MP 2>/dev/null; wait $MP 2>/dev/null || true
echo "$N: $(ls $OUT/requests | grep -c req_) requests, exit $(cat $OUT/exit_code)"
