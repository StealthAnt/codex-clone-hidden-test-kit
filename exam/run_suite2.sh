#!/bin/bash
cd "$(dirname "$0")"; for n in $(python3 -c "import json;print(' '.join(json.load(open('scenarios2/meta.json'))))"); do ./run_scn.sh $n; done
