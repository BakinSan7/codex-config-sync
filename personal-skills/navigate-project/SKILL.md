---
name: navigate-project
description: Restore orientation in a large or long-running project and select one next verifiable outcome. Use when the user says they are stuck, overwhelmed, unsure what to do next or today, returning after a break, juggling too many tasks, questioning focus, or asking to clean up and prioritize project work.
---

# Navigate Project

Turn scattered project context into one clear next outcome. Reduce cognitive load without discarding ideas or creating a duplicate planning system.

## Respect project authority

Read applicable project instructions before acting. Use the project's existing canonical sources instead of inventing another tracker. Prefer, in order when available:

1. The current user request and conversation.
2. Applicable `AGENTS.md` files and project rules.
3. Actual repository, application, or workspace state.
4. The current milestone, issue, task board, or equivalent tracker.
5. Current decisions, status documents, and knowledge base.
6. Older plans and backlog only after checking whether they remain valid.

Distinguish confirmed facts, approved decisions, hypotheses, deferred work, blockers, and obsolete items. Never treat a note or idea as approved scope merely because it exists.

## Restore direction

1. Establish the current phase and nearest meaningful destination.
2. Identify what is already complete, active, blocked, deferred, or obsolete.
3. Define the nearest playable, usable, testable, publishable, or decision-ready outcome.
4. Trace the critical path: the smallest chain of work that must happen before that outcome can exist.
5. Remove candidates blocked by missing authority, external conditions, or superseded decisions.
6. Rank the remaining candidates by whether they:
   - unblock the critical path;
   - produce a verifiable result;
   - reduce an important uncertainty;
   - fit the user's current time, energy, tools, and resources;
   - minimize rework and unnecessary scope.
7. Recommend exactly one main outcome. Do not present several equal choices unless a material product tradeoff genuinely requires the owner to choose.
8. Reduce the first action to a closed loop that normally takes 30–90 minutes. State an observable definition of done.
9. Name the tempting work that should remain parked for now.

Allow at most two supporting actions, and only when they directly enable the main outcome without splitting attention.

## Adapt to the request

- For "what next?", give a quick orientation and one next result.
- For "what should I do today?", give one main task and up to two necessary supporting actions.
- After a break, reconstruct the actual state and flag stale plans before recommending work.
- When the user is overloaded, audit active work, set work in progress to one main outcome, and park the rest explicitly.
- For a focus check, compare current work with the nearest meaningful outcome and identify activity that does not support it.
- If the user asks only for navigation or planning, remain read-only. Do not edit files, create issues, or start implementation.
- If the user explicitly asks to begin or complete the selected work, continue under the project's implementation, verification, documentation, and handoff rules.

After authorized execution, update the canonical task or status source when project rules require it so the next session starts from the current truth.

## Output

Reply in the user's language and follow any project-specific format. Keep the answer compact:

**Where we are:** one or two factual sentences.

**Next outcome:** one result and why it is the current priority.

**First action:** a concrete closed loop with a definition of done.

**Not now:** two to four parked distractions or blocked items.

Add **Owner decision needed** only when a real product, financial, legal, external, or irreversible choice blocks progress.

## Guardrails

- Do not generate a long roadmap unless requested.
- Do not invent deadlines or use guilt as motivation. Scope estimates are still useful.
- Do not count research, infrastructure, or documentation as progress unless it enables the next meaningful outcome or removes critical uncertainty.
- Do not reopen deferred work unless its blocking condition changed.
- Do not create duplicate task lists in chat or a knowledge base.
- Do not ask the user to decide technical details that can be resolved safely from evidence and project rules.
- Do not silently make product or architectural decisions.
- If the current task is blocked, record the reason and choose the next unblocked item on the critical path.
- Preserve existing user work and respect project-specific delegation rules. Executors may implement a decided solution, but they must not inherit unresolved product or architectural choices.
