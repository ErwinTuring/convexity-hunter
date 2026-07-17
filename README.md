# Convexity Hunter

Convexity Hunter is an open-source research assistant for finding assets that deserve further investigation as potential positive-convexity opportunities. It combines world events and narratives, market evidence, and bounded-downside/nonlinear-payoff reasoning.

It does not predict market direction or place trades. Narratives generate hypotheses; evidence determines what merits deeper research.

## MVP scope

The first MVP will organize research into five small stages:

1. Observe relevant world events and narratives.
2. Gather market evidence.
3. Connect hypotheses to evidence.
4. Identify candidates with bearable downside and nonlinear payoff potential.
5. Produce an evidence-based investigation report without unsupported scores.

## Current status

The repository contains only the initial project skeleton and documentation. Market scanning, external APIs, LLMs, MCP, Skills, and trading integrations are not implemented.

## Run the bilingual synthetic reports

Both reports use invented demonstration values. Neither is current market analysis or a trade recommendation. Each begins with a plain-language overview while retaining the complete technical detail below it. Scanning, screening policy, real-data integration, and the AI agent are not operational.

Run the Chinese report with:

```bash
PYTHONPATH=src python3 examples/sample_candidate_report.py --locale zh-CN
```

Run the English report with:

```bash
PYTHONPATH=src python3 examples/sample_candidate_report.py --locale en
```

The checked-in outputs are `data/samples/sample-candidate-report.zh-CN.md` and `data/samples/sample-candidate-report.en.md`.

## Development

Python 3.9 or later is required. Source code will live under `src/convexity_hunter`, with tests under `tests`.
