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

Code-grounding clarification: the canonical `UnderlyingSecurityType` has only
`EQUITY` and `ETF`. The ordinary-share cover row supports `EQUITY`; a separate
Futu-specific stock-category normalization is not required by this Host key.
This does not supply USD, MIC or current-listing evidence and creates no new
automatic identity binding.

Next lawful work is an independently supported current listing/security-type
and trading-currency evidence path, with its provenance and Host validation
explicit. Do not replay this spent Search or infer the missing fields to enable
EI. No new user credential or payment action has been demonstrated necessary.

## Separate current-listing source acquisition

New operation `iren-current-listing-currency-2026-10-02-v1`; not a replay or
reinterpretation of the spent exact-URL trial above. Main-reviewed wrapper:
`/private/tmp/ch_iren_current_identity_acquisition_2026-10-02.py`, SHA-256
`a7cfa3b80c89060ab32355e6c11a6f407144dd278cc500e3718b096e60136a92`.
It reuses the unchanged `host_sources.py` hash recorded above.

Exact query:

```text
(site:iren.com OR site:ir.iren.com OR site:nasdaq.com OR site:nasdaqtrader.com) IREN stock trading currency USD share class current listing
```

One Basic Search (at most five results), at most one Basic Extract (two URLs),
two-request/two-credit budget, same byte/time caps and external credential
resolver. No retry, fallback, model, Builder, EI, Core, Futu or trading calls.
Extract URL hosts are exactly `iren.com`, `www.iren.com`, `ir.iren.com`,
`nasdaq.com`, `www.nasdaq.com`, `nasdaqtrader.com`,
`www.nasdaqtrader.com`, or `listingcenter.nasdaq.com`. Require HTTPS and
canonical ASCII paths without query, fragment, userinfo, ports or dot segments;
block option/history/chart/quote path segments. A trailing slash is lawful.
Retain vetted URLs and rejection categories, not raw API JSON. Public bodies
remain external 0700/0600 pending-review artifacts; incidental prices cannot
enter research. Existing PAYGO-off confirmation is not a new billing check.

AST and 13 offline URL checks passed. Main approval binds the exact wrapper
hash; an exclusive marker is claimed before requests. Search/body retrieval
alone establishes no identity, currency or product acceptance. No live result
exists at this operation's authorization checkpoint.

### Actual acquisition outcome

Main authorized the exact reviewed hash once. Search returned five official-host
results; the first two eligible URLs were extracted without ranking, retry or
additional acquisition. Actual URLs were the Nasdaq IREN
`/analyst-research` and `/dividend-history` pages. The compound
`dividend-history` slug passed the exact-segment filter despite the intended
history exclusion: record this source-selection deviation, not a clean scope
pass. No historical, dividend, price or analyst metrics were consumed as
research evidence. Three further eligible results exceeded the extraction cap.

Transport outcome: `EXTRACTED_PENDING_BODY_REVIEW`; two reserved requests and
two reserved credits. Search reported one credit, Extract zero; account/billing
usage was not rechecked. Source selection/relevance and factual verification
remain separate from successful transport.

External bodies (0600 in `/private/tmp/iren-public-bodies-20qp0zpm`, 0700):

| File | Source path | SHA-256 |
| --- | --- | --- |
| `source-01.md` | Nasdaq IREN `/analyst-research` | `fa9d2649e99c493fa502b756ea24c23dfc0f96f5110c2f40a8d10aa293fdf549` |
| `source-02.md` | Nasdaq IREN `/dividend-history` | `c63cefd3d1af0cd7367b416d8ee0a11a47331f1417bbe7475d73e91be03038b6` |

Limited Codex-assisted review of the first body identifies IREN Limited ordinary
shares, symbol IREN, in its title. Context `[5677,5782)` has SHA-256
`7d94239fd8aaf62b23457477c629510b2e24af496497a36a2ecda5f570604324`;
the ordinary-share phrase `[5722,5737)` has SHA-256
`1e46ee8dea3492d6f84220ca5dc641338f2e6cc48116087bbb3185824c09963a`.
Offsets are exact decoded Unicode code points. Generic Nasdaq navigation is
not instrument-specific proof of current listing. Neither body establishes
explicit USD trading currency. This source packet therefore cannot authorize
the missing currency binding or claim standalone Host/EI completion.

Exact sanitized result: `/private/tmp/iren-current-listing-currency-2026-10-02-v1.result.json`
(0600), SHA-256
`09fa48d894d95116099392f5e03635c1d4132c409afa4d2992323b847f40617e`.
No model, Builder, EI, Core or production code changes occurred. The attempt
is spent; do not rerun after changing the URL filter to improve this outcome.

### Required-key audit

The existing Futu Sample 10 records an `IREN/XNAS/EQUITY/USD` key, but its
linked exercise documents do not retain independent currency provenance.
Do not cite that constructed key as its own proof. Ordinary-share identity
supports the existing `EQUITY` category; explicit USD remains missing.
Current listing standing is an unknown stronger claim, not a newly imposed
universal gate: these contracts prescribe no separate identity freshness window.

### Separate secondary-reference corroboration authorization

Main authorized one additional Basic Extract of the known public URL
`https://finance.yahoo.com/quote/IREN/`, with one-request/one-credit budget,
existing external Tavily resolver and PAYGO-off confirmation. No Search,
retry, fallback, model, market-data SDK or trading operation. Retain only
external pending-review public body and sanitized receipt/hashes. This is
secondary published instrument metadata, not exchange authority, new Engine
provider integration, a replay of either spent operation, or automatic Host
binding. Review explicit identity/currency wording and conflicts independently;
do not use displayed prices or substitute reporting currency for trading
currency. Its result remains unknown at authorization.

#### Actual secondary-reference result

One Extract returned a body; one request/credit reserved, zero failed,
provider-reported credits zero. No Search, retry or further acquisition.
Captured `2026-10-02T01:10:23.274967+00:00`, external body
`/private/tmp/iren-yahoo-public-5npm4xmj/source.md` (0600, directory 0700),
SHA-256 `88751686e6e61143161cfbfd6a37bf5c7211472927566c499354c369a8908211`.
Sanitized result `/private/tmp/iren-yahoo-identity-corroboration-2026-10-02-v1.result.json`
has SHA-256 `3e5450a6178b3227bc82aba37b77854a397969254f06c9d4aebaf3dadffca0b0`.

An initial literal search for `Currency in USD` missed alternative wording.
Targeted offline review found the instrument header at line 347:
`NasdaqGS - Delayed Quote•USD`, immediately preceding
`# IREN Limited (IREN)` at line 349. The full header SHA-256 is
`bd53381adb5d09f320f11cab2159c3f07779e6a8f84289390b28ff3b3fe41dcb`;
its USD token `[26663,26666)` has SHA-256
`a26cdf3a6e709124385d4d7eb9bff6b897a58ed5597fbab779b89849dbe81b21`.
The body is target-specific despite surrounding generic navigation. Its header
supports Yahoo-reported quote denomination USD, not exchange-certified facts,
realtime price, freshness, executable pricing or consolidated quote authority.
Do not record the initial literal-string miss as absent currency evidence.

Independent review passed `READY_FOR_BOUNDED_HOST_KEY` for
`IREN / None / EQUITY / USD`, joining issuer/Nasdaq ordinary-share evidence
with Yahoo's explicit quote denomination. All three body hashes matched.
Keep the currency basis provider-reported; do not relabel it issuer-, SEC- or
exchange-certified instrument currency, infer MIC, or claim realtime/NBBO.
The existing Host contract permits readable listing/provider references and
does not require exchange-only proof or an extra current-standing freshness gate.
No binding or EI execution has occurred; standalone identity automation is
not established by this Codex-assisted snapshot review. Next is a separately
bounded existing v0.5 producer/Builder/EI trial with retained evidence, not
another acquisition or a new provider adapter.

Separate local SDK inspection found Futu `get_stock_basicinfo` supplies symbol,
security type and venue but no explicit currency field. No SDK/API/config call
was made. Do not infer USD from its US market code as an alternative proof.
