# IREN bounded identity source packet — 2026-10-02

## Frozen read-only operation

Run ID: `iren-identity-packet-2026-10-02-v0.1`.
Production baseline: `8e1369eaf2d420900fbb728062ea61bc1b1af8dd`.
Runner: `/private/tmp/ch_iren_identity_packet_2026-10-02.py`.

Runner SHA-256: 601db62f10d1ad82eeaeb783e76a0865442d0168c19b1a2e2d404f5d833fe3f3

host_sources.py SHA-256: 4c32732ff300d689085d8069dd6dd4eb33abf5449eb61d9a9cc5d83139c24e56

Exact Search query:

```text
site:www.nasdaq.com/market-activity/stocks/iren IREN ordinary shares common stock share class trading currency
```

Use existing Tavily Basic Search once, at most two results. If an allowed
result exists, perform Basic Extract once. Only the exact HTTPS URL
`https://www.nasdaq.com/market-activity/stocks/iren` is eligible: no query,
fragment, userinfo, port, option-chain or historical paths. Deduplicate before
Extract; the configured maximum is two URLs, but this grammar permits one.
No fallback, requery, refresh or retry, including transport failure.

The existing validated client enforces request/credit budgets of 2/2,
20-second request timeout, 45-second total budget, 16,384 request bytes,
262,144 response bytes and 530,000 cumulative bytes. PAYGO-off is the user's
existing confirmation, not a new account/billing verification. Resolve only
the authorized external credential file through `TavilyCredentialRef`;
never print its contents or retain them in repository artifacts.

Live invocation requires committed preregistration, matching runner/SDK hashes
and explicit Main authorization. Claim the exclusive external attempt marker
before the first API request. Default mode performs seven offline URL checks
without credentials, network or marker. Worker AST/default checks passed;
Main inspected the wrapper, SDK receipt fields and source-only scope.

## Evidence boundary

Purpose: obtain possible independent IREN listing/class/security-type and
explicit USD trading-currency evidence. MIC is optional and may remain `None`.
No model, Builder, EI, Core, quote, trading or pricing operation is authorized.
Search snippets are leads, not verified facts. Exact public Extract bodies may
be retained only outside Git in a new 0700 directory with 0600 files, hashes,
capture time and `PENDING_BODY_REVIEW`. Do not use incidental prices/quotes.
An allowed URL returned by Tavily is not independent proof of final origin or
source truth. No raw API JSON is retained or printed.

Successful Search/Extract does not establish identity, currency, receipt
authority, Event Intelligence acceptance or standalone Grounder completion.
Loan amounts, `$` notation and a `US.` symbol prefix cannot prove trading
currency. Record unknown evidence as unknown; no automatic context binding.

## Result

Not executed at preregistration. Main may authorize exactly one invocation
after this document is committed and pushed. Record its sanitized outcome
here afterward; do not repeat the operation to improve the result.
