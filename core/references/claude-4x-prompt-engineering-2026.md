# Agent prompting and context reference

Reviewed 2026-09-11. This file retains its original path so existing links work.
Provider-specific model IDs, reasoning options and cache limits must be checked
against the configured provider's documentation; this reference does not select
or configure a model.

## Instructions and observable outcomes

Give each task a concrete objective, relevant context, bounded tools, an output
format and acceptance checks. Ask for evidence of the outcome: a read-back,
an artifact, or a transport receipt. A model's reputation or a successful command
exit cannot replace that check.

Keep stable instructions separate from retrieved content. Preserve the desk's
existing authority rules; this reference does not amend them.

## Context and memory

Load information when needed using paths, source IDs and concise summaries.
Reuse content that is still current; re-read it after edits, contradictions,
expiry or a change in task. Keep source and last-verified date beside mutable
facts. Preserve active constraints when compacting. Tune context size using task
accuracy and cost rather than a universal byte limit.

This follows Anthropic's guidance on [context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).

## Tools

Expose a focused operation with clearly typed inputs, bounded behavior, explicit
errors and evidence. Distinguish an empty search from unavailable or denied
access. Validate inputs in code as well as in the provider schema.

For OpenAI function definitions, enable strict mode and follow its schema
requirements. Schema validity establishes argument shape; it does not establish
permission or prove that an operation succeeded. See [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)
and the local [adapter contracts](../contracts/README.md).

## Model and delegation choices

Follow [model evaluation](model-evaluation.md). Begin comparison with the
simplest workflow that handles the task. Add coordination only when measured
quality gains justify its extra latency, cost and failure modes. There is no
mandatory number of agents or parallel calls.

When delegation is already authorized under the existing rules, give each worker
an independent bounded deliverable, source references, a budget and acceptance
criteria. Record both requested and actual models. Do not assume a model
automatically verifies every factual claim.

This follows Anthropic's [building effective agents](https://www.anthropic.com/engineering/building-effective-agents).

## Verify changes

Run the offline regression suite, then use representative runtime trials before
changing a deployed model or prompt. Compare outcomes, tool traces, latency and
cost. Human review is still needed for usefulness and factual support.

See [OpenAI agent evaluations](https://developers.openai.com/api/docs/guides/agent-evals)
and the local [evaluation procedure](../../evals/README.md).
