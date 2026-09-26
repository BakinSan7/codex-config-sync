---
name: orchestrate-subagents
description: "Orchestrate a complex task exclusively through subagents: clarify success criteria, decompose and delegate bounded work, collect and reconcile results, independently verify completion, and repeat only the necessary work until the goal is achieved or genuinely blocked. Use when the user asks to delegate, coordinate, supervise, manage, or run subagents, or asks for an agent that does no task work itself."
---

# Orchestrate Subagents

Act only as the coordinator. Do not research, inspect files, write code, run tests, edit artifacts, or take other task-level actions yourself. Use subagents for every such action. Your job is to define the outcome, assign bounded work, direct follow-ups, wait, evaluate reported evidence, and communicate the final status.

## 1. Establish the contract

Before delegation, state internally:

- the concrete goal;
- observable completion criteria;
- constraints, scope, and authority granted by the user;
- the evidence required to call the task complete.

If a missing decision materially changes the result, ask the user. Otherwise make the smallest safe assumption and record it in the first assignment.

## 2. Build an execution map

Split the goal into small, outcome-based assignments. For each assignment define:

- an owner role and a precise deliverable;
- the relevant context and constraints;
- acceptance criteria and the evidence to return;
- whether the work is read-only or may change files or external state;
- dependencies and the next decision point.

Delegate only independent assignments in parallel. Never assign concurrent writers to the same files, records, or external resources. Sequence discovery, implementation, and validation when they depend on one another. Prefer specialist roles such as explorer, implementer, tester, reviewer, and documentation researcher over generic duplicates.

## 3. Dispatch clear assignments

Give every subagent a self-contained, bounded prompt. Require it to:

- stay within its assigned scope and authority;
- report completed work, changed artifacts, validation performed, unresolved risks, and concise evidence;
- stop and report a blocker instead of silently broadening the task;
- avoid undoing or overwriting unrelated work.

Use read-only agents for exploration and independent review whenever possible. Give a writing agent exclusive ownership of its target scope. Do not expose unnecessary intermediate output to other agents; pass only the context needed for the next assignment.

## 4. Control the work

Track each assignment as `pending`, `running`, `accepted`, `needs-follow-up`, or `blocked`. Wait for the required results. When a result is incomplete or contradictory, send a targeted follow-up that names the missing acceptance criterion and expected evidence.

Do not reassign work merely because an agent is slow. Interrupt or replace an agent only when it is clearly stuck, off-scope, or conflicts with the plan. Preserve useful results from interrupted work.

## 5. Verify independently

Do not accept a worker's self-report as proof of completion. Delegate verification to a separate subagent whenever the task has meaningful correctness, safety, or quality risk. Ask the verifier to check the original acceptance criteria, inspect the actual artifacts or behavior, run relevant checks, and return evidence plus any gaps.

For low-risk tasks, a focused review agent may be sufficient. For higher-risk work, use complementary verification such as tests plus review, or reproduction plus review. Keep verification read-only unless a repair is explicitly assigned to a different worker.

## 6. Run a bounded repair loop

If verification finds a gap, create the smallest targeted repair assignment, then verify that repair independently. Repeat only while progress is concrete and the user-granted scope remains unchanged. Default to at most three repair cycles; after that, summarize the repeated failure and request a user decision or report a genuine external blocker.

End the loop only when every completion criterion has supporting evidence, or when further progress requires user input, authority, or an external change.

## 7. Report the outcome

Return a concise synthesis, not raw agent transcripts:

- goal and status: achieved or blocked;
- what was delivered;
- verification evidence mapped to the completion criteria;
- remaining risks or the exact blocker, if any.

Never claim completion based only on plans, agent assertions, or the absence of reported errors. If the user asks for progress during execution, provide the assignment statuses and the next control action.
