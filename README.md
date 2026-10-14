# Codex clone: hidden test kit

Files from the video **"I Used REA to Clone OpenAI's Codex"**: https://youtu.be/pX8Sy8Rd44U

An AI (Claude Code, with the open source reverse engineering tool REA) rebuilt the non-interactive mode of OpenAI's Codex CLI (`codex exec`, Apache-2.0) in Python, starting only from the files Codex installs on a computer. A hidden test, written before the AI started, compared the real program and the copy on the same scripted tasks. This repo has the test, the fake AI server and the AI's own notes.

## What is inside
- `exam/mock_model.py`: the tiny fake AI server (38 lines). It speaks the Responses API, answers with whatever a script file says and writes every request it receives to a log folder.
- `exam/scenarios/` (first test, 14 tasks) and `exam/scenarios2/` (hard test, 25 tasks: 11 model names + the default, JSON events, images, goals, environment, server errors) with `meta.json` per test.
- `exam/compare.py` and `exam/compare2.py`: the scorers. Each task runs checks (13 in the hard test: request count and shape, instructions, tools, environment, user messages, tool results, file effects, final answer, JSON events, exit code, stderr errors, headers) and prints `TOTAL ok/total`.
- `exam/run_real.sh`, `run_scn.sh`, `run_scn.py`, `run_suite*.sh`: run the real Codex (or your own copy through `CODEX_CMD`) against the fake server and save requests and output.
- `notes/`: the AI's honest notes about both copies (`NOTES-first-copy.md`, `NOTES-second-copy.md`) and the two prompts I gave it.
- `results/compare-outputs.txt`: the scores shown in the video. `RESULTS.md`: all the real numbers.

## Results (from the video)
- Easy test: first copy 96/97 = 99.0%.
- Hard test: first copy 245/325 = 75.4%, second copy (REA mandatory) 320/325 = 98.5%. Real Codex against itself: 325/325 = 100%.
- Both tests together: 416/422 = 98.6%. AI cost about $16.80 in total.
- Not tested: the real sandbox (it does not start on my machine), the interactive screen, resume/review commands, a real model.

## Run it yourself
1. Get the Codex package (Apache-2.0): `npm pack @openai/codex@0.162.1-linux-x64`, extract it to `target/codex-0.162.1-linux-x64/` (see `target/README.txt`) and create an empty `home/` folder.
2. Real run of one hard-test task: `cd exam && python3 run_scn.py m_gpt-5.5` (results in `exam/real2/`).
3. Run your own copy the same way: `CODEX_CMD="python3 /path/to/your/clone.py" OUT_ROOT=$PWD/mycopy python3 run_scn.py m_gpt-5.5`.
4. Score it: `python3 compare2.py real2 mycopy`.
Needs Linux, Python 3.11+, Node (for the package). Only analyze software you are allowed to test. This is not legal advice.
