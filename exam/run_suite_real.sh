#!/bin/bash
cd "$(dirname "$0")"; python3 - <<'PY' > /tmp/suite_cmds.txt
import json
m=json.load(open('scenarios/meta.json'))
for n,v in m.items():print(n,'|',v['prompt'],'|',' '.join(v['args']))
PY
while IFS='|' read -r n pr ex; do n=$(echo $n); pr=$(echo "$pr" | sed 's/^ *//;s/ *$//'); ./run_real.sh "$n" "scenarios/$n.json" "$pr" $ex; done < /tmp/suite_cmds.txt
