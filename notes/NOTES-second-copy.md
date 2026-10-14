# Clone of the Codex CLI (`codex exec`), v0.162.1 — notes (second pass, REA-assisted)

## How to run
```
python3 out/clone.py exec [OPTIONS] [PROMPT]        # same command line as `codex exec`
```
Files: `clone.py` (everything, incl. a small JavaScript-subset interpreter for code-mode `exec`), `clone_data.py`
(static data: base instructions, fallback tool list, the embedded model catalog + tool fragments as zlib/base64,
multi-agent texts, CLI help texts, feature-name region). Python 3.11+, standard library only. `clone.py` is executable
(the PATH alias dir created at startup symlinks `apply_patch`, `applypatch`, `codex-linux-sandbox`,
`codex-execve-wrapper` to it, like the original's arg0 dir; `apply_patch` invoked by that name works).

## Honest account of what REA could and could not do on this 294 MB binary
* `open_binary` on `.../bin/codex` worked (returned format/sha256/arch only). Every analysis call on the full binary
  (`list_segments`, `search_strings`, `binary_overview`, `search_procedures`, five attempts) ended with
  `provider_timeout` after 330 000 ms: a Ghidra JVM child process did start (seen in `pstree`) but is killed at the
  timeout and the next call re-imports from scratch, so **Ghidra full analysis never finished; no decompilation,
  xrefs, procedure listing or call graph of the real binary was obtained.** `binary_session` returned only
  capabilities (analysis_run/process lineage `not_observed`). `inspect_binary_layout` is unavailable
  (`REA_PWNTOOLS_PYTHON` not set).
* Workaround that did work: I carved the `.rodata` section (file offset == vaddr `0xe2f4000`, size `0xe44acc`,
  from `readelf -SW`) into a minimal ELF with my own script (`mkelf.py`, one PT_LOAD at the same vaddr) and opened it
  with REA (`open_binary` → ok, Ghidra imported it in seconds). `search_strings` / `read_bytes` on that image are
  genuine REA reads of the binary's own bytes, but Ghidra only reports "defined" strings; Rust packs most literals
  without separators, so several searches came back empty even though the bytes are there (see below).
  For bulk work (finding the catalog JSON boundaries, extracting 13k length-prefixed message literals, regex over
  the 15 MB) I used plain Python on the same `.rodata` bytes — that part is **not** an REA call; where it mattered I
  re-confirmed addresses with REA `read_bytes`.
* Behaviour was then pinned down by differential runs of the real binary against a scripted fake Responses server
  (allowed). Harness: `/tmp/w/{fake,cmp2,suite*}.py` (not shipped).

## Recoveries: REA evidence → change → verification
1. **Model catalog (target 1).** REA `search_strings "gpt-5"` on the carved image returned 15 string objects (e.g.
   `0xe53e978`, `0xe677fe4`); REA `read_bytes 0xe833a82 len 160` returned `{\n  "models": [\n    {\n      "slug":
   "gpt-6-astra", "prefer_websockets": true, ...` i.e. the embedded `models.json` (0xe833a82..0xe8a6e89, 472 KB, 11
   models: gpt-6-astra, gpt-6.1-sol, gpt-6-sol, gpt-6-luna, gpt-5.6-sol/-terra/-luna, gpt-daybreak-blue/-red-latest,
   gpt-5.5, codex-auto-review). I parsed it (Python `json`) and embedded it in `clone_data.MODEL_BLOB`.
   Changed: model lookup = drop one `ns/` prefix (`openai/gpt-5.5` matches, `a/b/gpt-5.5` does not), longest
   catalog-slug prefix wins (`gpt-6-sol-fast` → gpt-6-sol; `GPT-5.5`, `gpt-6`, `gpt-5.6` are unknown → fallback);
   default model is `gpt-6.1-sol` (priority 1; verified: no `-m` → request model gpt-6.1-sol). Per model, driven by the
   catalog: instruction text (`model_messages.instructions_template`; the line `- If you create a checklist or task
   list, …` is deleted — REA found that literal next to `You have access to an update_plan tool` in .rodata at
   `0xe8d1aa8`), reasoning effort default, summary default, `text.verbosity`, `context: all_turns`, `parallel_tool_calls`
   (false for lite models), `x-openai-internal-codex-responses-lite` header, turn-metadata `reasoning_effort` /
   `node_repl_*`, no `tools` key for `use_responses_lite` models (tools go in an `additional_tools` input item, code
   mode `exec`/`wait` + `functions`/`clock`/`collaboration` namespaces), skills usage text (`include_skills_usage_
   instructions`), collaboration-mode developer message, multi-agent role/mode messages (v2), permission/approval
   text overrides (`permissions`, `approvals`; `codex-auto-review` has empty overrides), `view_image` detail,
   `apply_patch` freeform tool, `tool_search`, `service_tier`/`fast` handling.
   Verified: 13 model names × 3 sandbox modes — request bodies, headers, stdout, stderr, exit code identical
   (39/39). The two daybreak models are in that matrix: they are v2 + no experimental tools, `daybreak-red` has
   `verbosity: high`, medium effort and no token budget; both are `visibility: hide` but reachable by name.
2. **Warnings / startup messages (target 6).** REA `search_strings "needs access to create user namespaces"` returned
   one string object at `0xe927fa0` containing: the WSL1 text, `bwrap`, `loopback: Failed RTM_NEWADDR`,
   `loopback: Failed RTM_NEWLINK`, `setting up uid map: Permission denied`, `No permissions to create a new
   namespace`, `Codex's Linux sandbox uses bubblewrap and needs access to create user namespaces.`, `Codex could not
   find bubblewrap on PATH. … Codex will use the bundled bubblewrap in the meantime.`, and the probe argv
   `--unshare-user --unshare-net --ro-bind / / /bin/true`. Implemented as a real probe at startup (read-only /
   workspace-write only; human mode only). REA `search_strings "TERM_PROGRAM_VERSION"` returned the terminal
   detection env list at `0xe988e6c` (Apple_Terminal, Ghostty, iTerm.app, WarpTerminal, vscode, WezTerm, kitty, Konsole,
   VTE, TMUX_PANE, ZELLIJ*, GNOME_TERMINAL_SCREEN, VTE_VERSION, WT_SESSION, …). The 13k length-prefixed message
   literals (Python scan, then spot checks) supplied: `WARNING: proceeding, even though we could not create PATH
   aliases: …`, `Model metadata for \`X\` not found…`, `Failed to read output schema file …`, `Output schema file …
   is not valid JSON`, `Warning: no last agent message; wrote empty content to …`, `unsupported call: ` /
   `unsupported custom tool call: `. Exact conditions/ordering were then verified against the binary:
   * startup WARNING (CODEX_HOME under temp dir) + `Error finding codex home: CODEX_HOME points to … does not
     exist / is not a directory` (exit 1); unset/empty CODEX_HOME → `~/.codex` created;
   * `warning: Model metadata for … not found` (human: stderr; `--json`: `item.completed` of type `error`);
   * deprecation of `features.web_search_request`, service-tier warning, `--enable/--disable` unknown feature
     (`Error: Unknown feature flag: X`), ignored-config warning (printed twice by the original), `--strict-config`
     unknown key, `--oss` error, `--worktree` outside git, `-C file` (AGENTS.md ERROR line), clap errors (exit 2).
3. **Image handling (target 3).** REA `read_bytes 0xe4811b5 len 700` returned the four image-omission messages
   (`image content omitted because remote image URLs are not supported`, `… because detail 'low' is not supported;
   use 'high', 'original', or 'auto'`, `… because it exceeded the supported size limit; use a smaller image`,
   `… because it could not be processed`). REA `search_strings` for the last one returned nothing (packed). Implemented
   `-i/--image` (greedy, comma separated): `<image name=[Image #N] path="…">` + `input_image` (`detail: high`) +
   `</image>` before the prompt text, `Codex could not read the local image at \`P\`: <os error>` for unreadable,
   `image content omitted because it could not be processed` for non-images; `view_image` (`detail` high/original
   only, `view_image.detail only supports …` error, no `detail` key in code-mode models). Verified identical except
   resizing (see missing).
4. **--json event stream (target 2).** REA `search_strings "thread.started"` returned nothing (packed), a Python
   scan of the same bytes showed `ThreadEvent … thread.started turn.started turn.completed turn.failed item.started
   item.updated item.completed error … agent_message reasoning command_execution file_change mcp_tool_call web_search
   todo_list` at `0xe7513f7`. Formats were then taken from the binary: `thread.started`, `turn.started`,
   `item.started/completed` for `command_execution` (status in_progress/completed/failed, `exit_code`),
   `file_change` (kind add/update/delete), `web_search` (duplicate `id` key like the original), `agent_message`,
   `reasoning`, `error` items, `collab_tool_call`, `turn.completed.usage`
   (input/cached_input/cache_write_input/output/reasoning_output tokens, summed over requests), `error` +
   `turn.failed` on failure, `Reconnecting... n/5 (detail)` error events. Human-mode lines (`exec`, ` succeeded in
   Nms:`, `web search: q` ×2, `apply patch / patch: completed / paths`, `collab: SpawnAgent`, `tokens used`) and
   `--color always` ANSI sequences were captured byte-exact. Verified: sc_j1/sc_h1/sc_j2 scripts × {human, json} ×
   {gpt-5.5, m}.
5. **Environment for commands / PATH / user agent / headers (targets 4, 5).** From the real binary: child PATH =
   `<install>/codex-path:[<CODEX_HOME>/tmp/arg0/codex-arg0XXXXXX:]<install>/codex-path:<inherited PATH>`; the arg0
   dir (only when CODEX_HOME is not under the temp dir) holds `.lock` and symlinks `apply_patch`, `applypatch`,
   `codex-execve-wrapper`, `codex-linux-sandbox`; removed at exit. The clone locates `codex-path` next to
   `../input/vendor/*/` or via `which codex`. User-Agent: `codex_exec/0.162.1 (<OS> <ver>; <arch>) <terminal> (codex_exec;
   0.162.1)`; os_info-style version (`Ubuntu 24.04` → `Ubuntu 24.4.0`), terminal token precedence probed with ~45 env
   combinations (TERM_PROGRAM[/ver] → Ghostty → WezTerm → iTerm → Apple_Terminal → kitty → Alacritty → Konsole →
   gnome-terminal → VTE → WindowsTerminal → TERM → unknown; unsafe chars → `_`). Header names are sent lower-case in
   the original's order (no Accept-Encoding; `host`, `content-length` last).
6. **Goals / multi-agent / request_user_input / clock / MCP stubs (target 3).** Tool texts and error strings were
   captured from the binary: `create_goal/update_goal/get_goal` (JSON key order, `completionBudgetReport` only for
   budgeted goals, `goal objective must not be empty`, `goal budgets must be positive when provided`,
   `cannot create a new goal because this thread has an unfinished goal; …`, `update_goal can only mark …`,
   `unknown variant … expected one of …`, tokens accounted on non-complete updates);
   `request_user_input` → error `request_user_input is unavailable in Default mode` (Default mode);
   `request_user_input_async` → `{"accepted":true}` and an `agent_message` of the titles; `clock.sleep`;
   `list_mcp_resources`/`templates`/`read_mcp_resource` stubs for code-mode models. multi_agent v1 (`multi_agent_v1`
   namespace: `spawn_agent` creates a child thread/request with `x-codex-parent-thread-id`, `x-openai-subagent:
   collab_spawn`; `send_input`, `wait_agent`, `close_agent`, `resume_agent`; uuid/not-found/`Provide one of: message or
   items` errors) and v2 (`collaboration` namespace: `spawn_agent` task_name rules, `list_agents`, `send_message`,
   `followup_task`, `interrupt_agent`, `wait_agent` clamping, FINAL_ANSWER mailbox message to the parent).
7. **Code mode `exec`/`wait`.** The 6.x/5.6 models only declare a custom `exec` tool (V8 isolate in the original).
   Implemented a JS-subset interpreter (statements, closures, destructuring, template literals, async/await,
   setTimeout/Promise, JSON/Math/Object/Array helpers) with the original's globals (`text`, `image`, `store`, `load`,
   `notify`, `exit`, `yield_control`, `ALL_TOOLS`, `tools.*`), result envelopes (`Script completed|failed|running with
   cell ID N`, `Wall time x.y seconds`, `Script error:` + V8-style message/stack position), pragma
   `// @exec: {"yield_time_ms":…}`, `wait {cell_id, yield_time_ms, terminate}`, `exec cell N not found`.
   Verified on ~30 scripts (most byte-identical).
8. **Errors from the model API.** 400 → body verbatim, no retry; 401/404/408/413 retried 5× (`Reconnecting... n/5
   (unexpected status …)` in json); 429 → `exceeded retry limit, last status: 429 Too Many Requests` /
   `Quota exceeded…` (no retry); 5xx → retried with `We’re currently experiencing high demand…`; `response.failed`
   codes (`context_length_exceeded`, `insufficient_quota`, `invalid_prompt`, `rate_limit_exceeded`, others);
   `response.incomplete`; unknown `error` events are ignored (stream closed → no `tokens used` line).
9. Other CLI features: `-c/--enable/--disable/--strict-config`, `-i`, `-m`, `--oss`, `--local-provider`, `-p`, `-s`,
   `--approve-for-me` (workspace-write + on-request + auto-review permission text), `--dangerously-bypass-…`/`--yolo`,
   `-C`, `--add-dir` (writable roots, env context, banner), `--output-schema` (`text.format` json_schema), `--color`,
   `--json`, `-o`, `--ephemeral`, `--skip-git-repo-check`, `--help/-h/-V` and `resume|fork|review --help` (texts
   captured from the real binary; `--full-auto` is rejected like the original). Session file
   `sessions/Y/M/D/rollout-*.jsonl` is written (approximate record).

## Verified against the real binary (outputs identical in differential runs)
Request body + headers + stdout/stderr + exit code: all 13 model names × read-only/workspace-write/danger-full-access;
~30 config combinations (effort/summary/verbosity/service_tier/instructions/…); goal/view_image/tool scenarios;
`--json` and human output for command, patch, web search, reasoning, errors; stdin/prompt combinations; `-C`,
`--add-dir`, `--output-schema`, `-o`, images (small), clap errors/help; HTTP/stream error classes; code-mode scripts.

## Still missing / known differences
* Ghidra never finished the full binary: nothing was read from code (no decompilation); all conclusions come from
  `.rodata` bytes (REA on the carved image + Python) and black-box runs. Packed Rust strings are only partly
  visible to REA `search_strings`.
* Image resizing: the original shrinks large images (3000×2000 → 1920×1280, 2048² → 1600², long side ≤ 2048 …,
  re-encoded PNG); the clone passes bytes through (small images are byte-identical). Skills list budget
  (`model_context_window` tiny → descriptions dropped + warning) not implemented.
* Sub-agents are approximated (threads in-process, racy ordering like the original, but statuses/timing differ);
  v2 mailbox/`wait_agent` timeouts, `resume`/`fork`/`review` subcommands, MCP servers, hooks, profiles, ChatGPT auth,
  compaction, token budget reminders are not implemented. Sandbox: the original's working-bwrap layout is unobserved
  (this host cannot create user namespaces); when bwrap fails no exec events are printed (matches).
* Rollout/sqlite/skills-install files in CODEX_HOME are not byte-compatible (rollout is approximate, `skills/.system`
  is not materialised; the skill list falls back to the captured one).
* Unknown config keys are only detected for `features.*` and `--strict-config` uses a hand-made key list;
  feature names are matched by substring against the `.rodata` name region.
* Wall times: exit-time reporting offset (≈0.145 s) is a fit; interleaving of stdout/stderr of one command is racy
  in the original too. Parallel tool calls run sequentially (events order may differ).
