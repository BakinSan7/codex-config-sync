---
name: context-watchdog
description: Forecast quota use before large Codex tasks when evidence permits, check context cost during long work, and preserve the objective in a fresh-chat handoff when context becomes expensive. Preserve the selected model. Skip routine short questions.
---

# Context Watchdog

Use the bundled script to inspect Codex's local session telemetry. Do not estimate
exact task-versus-harness attribution: Codex exposes totals, cached input and
compaction events, not token provenance.

## Forecast and model choice

Before substantial work, provide a brief forecast of the percentage of the
full weekly allowance expected to be consumed, with a range and its basis.
Use verified comparable tasks on the same model and reasoning effort with
similar context and scope. Read the relevant weekly window through the available
`get_usage_limits` tool; the remaining allowance provides context, not a formula
for estimating the new task. Do not infer subscription percentages from API
dollars, token totals, generic message limits, or another model's prices.

If comparable measurements are unavailable, say that a reliable percentage
cannot yet be estimated and name the main cost drivers. Do not fabricate a
range or silently run a costly calibration task. An account-level before/after
delta includes simultaneous tasks; disclose that limitation. Report material
changes to the forecast during work, but do not invent a daily budget or an
automatic 3/5-percent stop rule. The user requested a forecast, not a fixed cap.

Preserve the user's exact model and reasoning effort throughout the work and
handoff. Never downgrade Astra or reduce its reasoning automatically to save
quota. Do not delegate to cheaper models unless explicitly authorized.

## When to check

- Before starting a large task.
- After a major tool-heavy stage or milestone.
- After Codex reports that the conversation was optimized.
- During a long turn, every 10 model responses or 10 minutes, whichever comes
  first. Do not wait for the next user message or the whole objective to finish.
- When the user explicitly invokes `$context-watchdog`.

Do not check on every message, for routine questions, or during small edits.

## Check and act

Run `scripts/context_watchdog.py --json` with the current Python interpreter.
Resolve the script relative to this skill directory. The script is read-only and
uses `CODEX_SESSION_ID` when available.
If session identity is unavailable, pass `--session` or `--session-id`; never
pick an unrelated task merely because its log was modified most recently.
At checkpoints, also refresh the relevant weekly quota and assess verified
progress, repeated failures, large tool outputs and work beyond accepted scope.
Read only relevant files and bounded excerpts; batch independent operations.

The helper recognizes top-level `compacted` and modern `token_usage_record`
records, ignores embedded replay history and deduplicates response IDs. Repeated
cached tokens are a cost indicator, not proof of wasted or removable context.
Ten successive requests above 272K input with at least 95% cached input and
2.72M cached tokens in total trigger a context-cost review. This is a conservative
review threshold, not a claim about subscription pricing.

- `healthy` or `note`: continue silently.
- `handoff_before_large_task`: finish the current bounded work. Before starting
  another large objective, prepare a compact continuation for a new task.
- `handoff_now`: do not abandon the active objective or replace it with a
  generic restart brief. Continue to the nearest safe, verified checkpoint when
  that is practical; otherwise pause only after preparing an exact continuation
  of the work already in progress.

On expensive context repetition, stop expanding the current work, preserve a
safe checkpoint and prepare the handoff. If a single bounded final verification
finishes the objective, finish it. If the context is essential and a fresh chat
would not help, explain the tradeoff before another expensive stage. After two
failed attempts without new evidence, change approach; after three without
verified progress, checkpoint and explain the blocker. Never use a handoff to
introduce future work, repeat repository-wide instructions, broaden scope, or
ask the user to reconstruct context that is already available.

This is an agent-executed checkpoint policy, not an installed background monitor,
runtime hook or guaranteed spending cap. The script is read-only and does not
stop processes. Never claim enforcement stronger than what was actually tested.

## Seamless continuation

The continuation must preserve the current work rather than describe a new
assignment. Include only:

- the active objective and its accepted scope;
- decisions and assumptions already approved for that objective;
- repository, branch, working-tree, and external-task state that was actually
  observed;
- files changed, checks completed, results, blockers, and the exact next action;
- any user action that is genuinely unavoidable.
- the selected model and reasoning effort, the original forecast, known spend
  and attribution limits; moving chats does not make it a new objective.

Exclude speculative follow-up work, unrelated backlog items, boilerplate setup,
and commands that merely restate repository documentation. Link canonical files
instead of copying their general rules.

Do not use vague completion language such as "implement everything". Repository
rules about tests, commits, pushes, or handoff format remain execution policy;
they do not enlarge the active objective and do not need to be repeated as new
work in the continuation.

When the product can create a separate task and the current user request
explicitly authorizes automatic transfer, prefer a new project task with an
isolated worktree and a compact context packet. The packet must state:

1. **Current objective** - the exact outcome in progress.
2. **Accepted context** - only decisions and rationale needed to continue it.
3. **Observed state** - repository, branch/worktree, changed files, checks, and
   external task state that were actually verified.
4. **Remaining work** - only the unfinished portion of the current objective.
5. **Resume point** - the first concrete action in the destination task.

The user has approved fresh-chat handoffs for expensive context while preserving
the chosen model. When current session instructions permit task creation, pass
the exact verified model and reasoning effort. If either cannot be preserved,
provide the packet instead of silently substituting a default. Preserve observed
uncommitted work with a supported working-tree starting state. First create a
preparation-only successor, verify a ready threadId rather than a pending
clientThreadId, and then transfer exclusive implementation ownership and resume.

Do not fork the full chat history for this mode. Do not leave two tasks actively
implementing the same objective: after the destination is ready, it becomes the
canonical worker and the source task stops implementation. If an automatic
transfer is unavailable or not currently authorized, provide one compact ready
continuation instead; do not pretend that a transfer occurred.

Do not repeat the same warning unless severity increases or context occupancy
grows by at least 10 percentage points.

Never claim the calculated reuse ratio is exact harness overhead.
