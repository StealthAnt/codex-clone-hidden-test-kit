# Clone of the Codex CLI (`codex exec`), v0.162.1 — notes

## How to run
```
python3 out/clone.py exec [--skip-git-repo-check] [--sandbox read-only|workspace-write|danger-full-access] \
    [-c key=value]... PROMPT
```
Files: `clone.py` (everything) and `clone_data.py` (static texts: base instructions, tool schemas, fallback skill
list — all taken from requests the original sent, not from its binary). Python 3.11+ stdlib only (uses `tomllib`).
Final answer goes to stdout, progress/banner/errors to stderr (like the original). Exit 1 on fatal errors.

## What I did (honest account)
I did **not** use Ghidra / the REA static tools. The binary is a 294 MB stripped Rust program and the quickest, most
reliable evidence was black-box observation, which the task allows: I wrote a fake Responses-API server
(`/tmp/w/fake.py`, SSE, scripted tool calls) and ran the real binary against it with a scratch HOME/CODEX_HOME,
logging every request body/header, then scripted many tool-call scenarios and compared the original's
`function_call_output` strings with the clone's using the same scripts (differential testing,
`/tmp/w/cmp.py`, `/tmp/w/cmpreq.py`). Steps:
1. Captured the first request: no `instructions` field; base prompt is a developer message; 2nd developer message
   = skills list + permissions text; user message = AGENTS.md block + `<environment_context>`; then the prompt.
   Captured the tool list (exec_command, write_stdin, request_user_input, view_image, multi_agent_v1 namespace,
   get/create/update_goal, web_search) and top-level fields/headers.
2. Probed tools: output envelope (`Chunk ID / Wall time / Process exited with code / Original token count / Output`),
   truncation rule, yield/poll timing, sessions, tty, error strings (unknown tool, bad JSON, missing field, wrong type,
   unknown session, escalation reject, `rm -f` rejection, bad workdir), apply_patch interception, view_image, goals.
3. Probed configuration: AGENTS.md discovery/merging, `~/.codex/AGENTS.md`, override files, fallback names,
   `project_doc_max_bytes`, `developer_instructions`, `instructions`, `model_instructions_file`,
   `include_*` flags, reasoning/verbosity, sandbox modes (permission text + environment_context per mode), stdin
   appending, git-repo check, retry/error behaviour.

## Verified against the real binary (outputs identical in differential runs)
- Complete first request body (input messages, tools, fields) for read-only / workspace-write / danger-full-access,
  nested git repo AGENTS.md(+override), non-git (cwd only), global AGENTS.md, fallback filenames, byte limit, stdin.
- exec_command / write_stdin results incl. truncation (head+tail split, `…N chars truncated…` vs
  `…N tokens truncated…`, `Warning: truncated output` header, token estimate = ceil(bytes/4)), exit codes, tty,
  session ids, poll timing (empty poll waits 5 s min), non-tty stdin closed, error strings.
- apply_patch via heredoc (Add/Update/Delete/Move, CRLF preservation, context seeking, all error messages seen,
  A/M/D summary order, `cd dir && apply_patch <<EOF`), read-only/outside-workspace rejection.
- Retry behaviour (5 stream retries; 5xx also 4 inner retries), error printing, exit code 1.

## Not recovered / not implemented / uncertain
- Known models: the original has a model catalog (e.g. `gpt-6.1-sol`) that changes tools, instructions, reasoning
  params; only the "unknown model → fallback metadata" configuration (what `model="m"` gives) is implemented.
- Sandbox: shell commands are wrapped in `bwrap` (ro-bind /, writable roots, `--unshare-net`) when it exists, which
  reproduces the original's output on this machine (`bwrap: loopback: Failed RTM_NEWADDR`, exit 1) but I could not
  observe a *working* sandbox, so the exact mount layout and the error text for denied writes are guesses.
- Env given to commands: added vars match (NO_COLOR, PAGER, GIT_*, CODEX_*, LC_ALL...). The original also prepends
  its own `codex-path` dir to PATH; not reproduced. Original does not truly use login shells (`-c`); I match that.
- stdout/stderr interleaving of commands is racy in the original; clone prefers stdout on ties.
- Wall time: original reports ~elapsed−0.145 s for exited commands (fit from a few samples); approximate.
- view_image re-encodes images in the original (resize); clone passes bytes through. Goal tools: create_goal shape
  verified; update_goal success output/`create_goal` on existing goal are guesses. multi_agent_v1 tools (spawn_agent
  etc.) return `unsupported call`; the original actually spawns sub-agents. `local_shell_call` → `aborted`,
  custom tool calls → `unsupported custom tool call: X` (verified).
- rm-force rejection uses a small shell tokenizer instead of the original's bash parser; common forms verified
  (`rm -rf`, `/bin/rm -f`, `sudo`, `env`, `bash -c '...'`, `$(...)`, subshell, `if`), exotic forms may differ.
- Not implemented: `--json` event output, resume/review subcommands, rollout/session files, MCP, hooks, profiles,
  output-schema, images, auth.json/ChatGPT login, `wire_api="chat"`, conversation compaction, token-usage banner details.
- Headers (user-agent etc.) are close but not byte-identical (the original embeds OS/terminal info).
