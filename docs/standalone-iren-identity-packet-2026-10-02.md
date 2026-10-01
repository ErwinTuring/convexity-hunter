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

After preregistration commit/push
`71c7b90d130c93c03fb578ab6fc8050ff9ea6e2e`, Main authorized the sole invocation.
It returned `NO_ALLOWED_SEARCH_RESULT`: Basic Search returned two results,
neither matched the exact allowed URL. Extract was not called; no body
snapshot exists. The attempt marker is spent. No retry or fallback occurred.

Search reserved one request/credit and reported one credit; request/response
bytes were 387/2,926. No account usage-counter or billing query was performed.
This is source-selection noncoverage under the frozen URL grammar, not proof
that IREN identity information is absent or Tavily cannot retrieve it. Rejected
URLs were not retained, so their exact mismatch categories are unknown.

Exact sanitized result is externally retained at
`/private/tmp/ch_iren_identity_packet_2026-10-02_result_y34by8tt.json` (0600),
SHA-256 `98c304b32d26082fd1855bcf6795624c6c684415efd7b69dd596a3305e25397d`.
No identity/currency binding, model, Builder, EI or Core execution followed.
Required independently verified USD trading-currency evidence remains missing.

## Retained SEC body — separate offline review

Luna/max inspected the existing SEC Form 8-K body without acquisition or model
calls. Its SHA-256 remains
`00ecc509846b657702081827db78a220b8ff51a9bacd19537339575e17ee6e29`.
The source is the [retained IREN filing](https://www.sec.gov/Archives/edgar/data/1878848/000114036126023427/ef20075181_8k.htm).

| Body location | Supported statement | Exact excerpt SHA-256 |
| --- | --- | --- |
| Lines 23–25; `[257,325)` | Registrant IREN LIMITED | `f155b279ee5b19f2ff90f43f1f51e08a77cbe7528c4880fb24eea8788e07105c` |
| Line 70; `[1615,1708)` | Columns identify class, symbol and registered exchange | `9bab9df651ceb7c533886ba9e057fa622840591d2a527a21ec428d378f4b0b0f` |
| Line 71; `[1709,1785)` | Ordinary shares, no par value; IREN; The Nasdaq Stock Market LLC | `5d16f325e7cb5028cdb8d34eef5da6dcc1e8d3caee6c8d10010fffa3dbe260ab` |

Offsets are zero-based half-open Unicode code-point ranges in the exact decoded
body; line hashes exclude line endings. This supports the filing's stated
symbol/share class/registered exchange only. It does not prove USD trading
currency, MIC, current listing status or a provider-specific security-type
normalization. Whole-body metadata stays `PENDING_BODY_REVIEW`; this limited
Codex-assisted inspection does not mark every statement verified or establish
an independently running Host identity verifier. No context binding was made.

Next lawful work is an independently supported current listing/security-type
and trading-currency evidence path, with its provenance and Host validation
explicit. Do not replay this spent Search or infer the missing fields to enable
EI. No new user credential or payment action has been demonstrated necessary.
