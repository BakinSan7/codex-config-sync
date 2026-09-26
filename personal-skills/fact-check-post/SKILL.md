---
name: fact-check-post
description: Verify public, externally checkable factual claims in news items, Telegram or social-media posts, articles, screenshots, and forwarded messages. Use to split a post into claims, find primary sources, distinguish evidence from inference, and return a concise source-linked verdict with uncertainty. Do not use for opinion-only text, job-fit assessments, ordinary research without claim verification, or OpenAI implementation guidance; pair with openai-docs for OpenAI-specific claims.
---

# Fact Check Post

Verify the post, not its tone. Separate what is evidenced from what is asserted or inferred.

## Method

1. Preserve the original wording and identify its publication date, author or source, place, and timeframe when available.
2. Split the text into independently checkable claims. Exclude opinions, predictions, and value judgments unless they contain a factual premise.
3. Check volatile claims live. Follow the [source hierarchy](references/source-hierarchy.md): seek the original document, dataset, official statement, study, court record, company filing, or direct interview before relying on summaries.
4. Cross-check material claims with independent credible evidence. Use specialist or reputable reporting for context or when a primary source is unavailable, and label that limitation.
5. Check dates, denominators, definitions, jurisdiction or geographic scope, and whether a source supports the exact wording. Do not treat a headline, repost, screenshot, search snippet, or merely related fact as confirmation.

## Verdict rules

Apply [the verdict rules](references/verdict-rules.md) to every material claim, using these user-facing labels:

- **Верно** — reliable evidence directly supports the material claim without a misleading omission.
- **Частично верно** — evidence supports a meaningful part, but context, scale, timing, or wording materially distorts it.
- **Неверно** — reliable evidence directly contradicts the material claim.
- **Недостаточно данных** — available reliable evidence cannot establish the claim.
- **Непроверяемое мнение/прогноз** — the statement is not currently verifiable as a factual claim.

Do not make a stronger verdict than the evidence permits. Use "не найдено подтверждений" rather than "ложь" when evidence is merely absent.

## Output

Start with one overall verdict about the post, then provide a compact table:

| Утверждение | Вердикт | Что подтверждается / не подтверждается | Источники | Уверенность |
|---|---|---|---|---|

- Link sources directly and include the publication or document date.
- Mark a conclusion as an inference whenever it goes beyond a source's direct statement.
- Keep quotations short and necessary; paraphrase the rest.
- Finish with the most important unresolved context, manipulation technique, or caveat, when one exists.

## Boundaries

- Do not infer a person's intent, identity, or guilt from a post.
- Do not present anonymous claims as established facts.
- For medical, legal, financial, or safety-sensitive claims, prioritize authoritative current sources and state that the check is informational rather than professional advice.
- If browsing or source access is unavailable, say so clearly and provide a provisional source-free assessment only when useful.
- Do not edit or publish the original post unless explicitly asked.
