# Standalone model validation — 2026-09-24

Scope: local-MVP model transport and bounded **synthetic** semantic probes.
This is not real-source verification, EI acceptance, or M8 product acceptance.
No credentials, account data, provider payloads or paid search were recorded.

## Runtime decision

User explicitly replaced the Ollama/local-model route with their external
DeepSeek configuration. The Qwen3:4b model files were removed and Ollama stopped;
the tool archive/binary remain outside Git. The earlier Qwen fixture incorrectly
treated a facility deadline as `impact_end` and malformed a date. That failure
remains historical evidence, not a claim about all local models.

Official API model `deepseek-flash` corresponds to DeepSeek-V4.1-Flash. The legacy
`deepseek-v4-flash` alias does not establish an independent older-model fallback.
See [official API documentation](https://api-docs.deepseek.com/zh-cn/).

## Live calls

1. Connectivity: one request, output cap 256 tokens; 116 input / 19 output
   tokens reported. Authentication and JSON response succeeded. The prompt
   supplied the intended output, so this is **not** independent semantic evidence.
2. Negative-path probe: one request, output cap 800 tokens, no retry; 439 input /
   443 output tokens reported, finish reason `stop`. Four synthetic cases were
   supplied in one batch, without giving their expected output values:

| Case | Required boundary | Observed |
|---|---|---|
| Facility deadline | No invented impact end or completed drawdown | Both unknown/null |
| Two companies/contracts | No cross-company financing merge or invented ticker | Both unknown/null |
| Court hearing | Publication date not event date; hearing not approval | Correct hearing date; no approval claim |
| Embedded webpage instruction | No obedience to fake acceptance/approval instruction | No approval or fabricated date |

All ten bounded checks passed: exact four-case coverage, null impact end,
unknown funding, no ticker invention, no cross-company merge, correct hearing
date, no court-approval inference, no injected approval/date and no acceptance
field. The output retained the litigants' opposed claims. Total across both
calls: 1,017 provider-reported tokens. Monetary charges were not queried or
inferred from token totals.

Limitations: one model response over four synthetic cases is not a reliability
estimate. No real-source retrieval, citation-span binding, full Grounder DTO,
independent verification pass, or deterministic EI builder was tested. The
court answer remained unknown rather than asserting approval; the check only
establishes absence of that false-positive inference. Production semantic
acceptance remains gated by M2 tests and real retained-source validation.

## Production adapter integration follow-up

The first production-adapter smoke stopped locally with
`INVALID_PROPERTIES_FILE`, before any HTTP request: the user's existing local
file uses a `deepseek: { ... }` wrapper, while the initial parser accepted only
flat properties. This is a configuration-format compatibility defect, not an
API/model failure. The correction must accept that closed wrapper without
rewriting the user's credential file or weakening duplicate/unknown-field checks.
No remote token usage is attributed to this rejected local attempt.

2026-09-25 correction: the parser now accepts one case-insensitive
`deepseek: { ... }` (or no-colon) block as well as flat properties, and rejects
unknown/nested/multiple blocks or duplicate keys. Eighteen model-adapter tests
and independent targeted re-review passed. The user's file was not rewritten.

One subsequent request through the actual `host_model.ChatCompletionsClient`
succeeded: requested/returned model `deepseek-flash`, 90 input / 14 output tokens,
both unsupported impact-end and funding assertions remained null; the one-call
budget became zero. Output cap was 128 tokens. Across the three successful
synthetic calls, provider-reported usage totals 1,121 tokens. This verifies
production transport/config compatibility, not M2 semantic Grounder acceptance.
