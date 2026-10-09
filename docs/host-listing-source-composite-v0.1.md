# Host Listing Source Composite v0.1

Status: FROZEN / IMPLEMENTED / INDEPENDENT REVIEW PASS.
The historical helper was opt-in. The current Event Host invokes it only over
its own admitted source IDs; that wiring does not expand the v0.1 grammar or
make arbitrary search/model bodies eligible.

## Approved successor preflight — 2026-10-10

### SEC-primary association correction and source-only BUILD boundary

The user approved replacing the dual SEC/Nasdaq CIK target with
`host-listing-issuer-sec-reference-v0.1`. The older bridge below is historical,
superseded target evidence, not a runtime rule. SEC's official
[association documentation](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
describes CIK/name/ticker/exchange associations and explicitly does not guarantee
accuracy or scope. Its association is primary issuer-reference evidence only:
it does not independently prove security class, denomination, current standing,
or a complete UnderlyingKey. Nasdaq need not repeat CIK. Exact cover identity,
security class/venue and independent provider denomination remain required;
no alias, punctuation stripping, ticker-only cross-source inference or EI
acceptance change is authorized.

Formal read-only preflight plus one bounded live packet established the exact
SEC endpoint `https://www.sec.gov/files/company_tickers_exchange.json`, media
type `application/json`, UTF-8, identity encoding, and root field order/schema
`fields = ["cik", "name", "ticker", "exchange"]`, followed by `data` rows.
The 523,544-byte response contained 10,435 rows and exactly one PLUG row:
`[1093691, "PLUG POWER INC", "PLUG", "Nasdaq"]`. This is one retrieved snapshot,
not a promise of future schema, coverage or standing.

Freeze the narrow source-only parser `sec-issuer-reference-v1` / `1`:

- Only the exact HTTPS endpoint; retain existing DNS/TLS, timeout, redirect,
  byte-budget, secret handling and Host origin protections. JSON media type is
  permitted only for this reference parser/path, never for EDGAR HTML parsers.
- Selection is an explicit nonempty unique tuple of existing canonical uppercase
  ticker grammar, never supplied from model-created identity authority. One GET
  yields one source ID and only requested rows enter parsed/model context.
- Strict root schema/order and four-element row shape; duplicate JSON keys,
  nonfinite values, ambiguous/missing/duplicate selected tickers or malformed
  rows fail closed. CIK is an exact non-Boolean positive int below 10^10;
  issuer/ticker/exchange are safe explicit strings. Preserve integer CIK in the
  source record. A later composite may compare that integer with an explicitly
  evidenced filing identifier under its own frozen rule; padding is not source
  evidence and URL alone is not issuer association proof.
- Preserve original selected row tokens, full raw response hash/size, parser
  metadata, selected-row raw byte spans/hashes and parsed spans/hash. Revalidate
  constructor-bypassed records, exact parsed grammar, role/path/media metadata,
  ticker selection and selected-row anchor linkage before consumption.
- Existing filing/HTML admission and composite v0.1 remain unchanged; no
  automatic reference supplements, v3/v4 listing unlock, new composite proof,
  budget increase, source fallback or EI/Core identity is part of this increment.
  A private explicit source-client operation is the only new execution surface.

Source-only BUILD is READY. Full composite BUILD remains blocked: this packet's
Nasdaq response had no supported instrument heading; Yahoo's visible label was
`NasdaqCM - Nasdaq Real Time Price  USD`, not a current supported v1 label.
These observations do not justify a permissive parser or source-global absence
claim. No further user authority decision is needed for the SEC source increment.

The user authorized a minimal Common Stock / Nasdaq Capital Market successor,
only with explicit real fields, multiple-source agreement, no fuzzy identity
inference and no SEC-single-source key. **Composite BUILD is BLOCKED; no v0.2
runtime or frozen source-parser/composite contract exists.** The separately
approved identity-rule target is frozen below. Do not remove the known v3/v4
listing exclusion.

A trusted v4 SEC admission can technically supply exact registrant/marker/cover
parsed spans and raw-anchor provenance to a separate reviewed composite. A
proposed closed class grammar is `Common Stock`, optionally followed by
`, par value $<ASCII decimal> per share`; that dollar sign is not currency
authority. The official SEC format reference uses `The Nasdaq Capital Market`.
Nasdaq Common Stock and Yahoo Capital Market/currency admission would need
separately versioned, actually evidenced formats; current v1 parsers do not
support those proposed successors. No unverified Yahoo label is frozen here.

The [public Nasdaq page](https://www.nasdaq.com/market-activity/stocks/plug) shows
`Plug Power, Inc. Common Stock (PLUG)`, whereas the prior
[official SEC format reference](https://www.sec.gov/Archives/edgar/data/1093691/000110465926082854/tm2620282d1_8k.htm)
shows `Plug Power Inc.`. Current
ASCII-case/space comparison does not equate those names. This is a format
reference, not a complete trusted three-source identity packet. Do not strip
punctuation or silently invent aliases. A stable-identifier correlation rule
would be a distinct authority decision requiring explicit provenance; a SEC
CIK in its URL plus matching ticker strings alone is insufficient.

The two-request production-access result and remaining decision are retained
in [the current checkpoint](current-checkpoint.md#common-stock-listing-successor-preflight--2026-10-10).
No production code, EI rule, denomination, MIC or listing-status claim changed.

## Approved stable-identifier boundary — 2026-10-10

The user has now authorized a minimal, versioned stable-identifier association
rule. Its target rule identifier is `host-listing-issuer-cik-bridge-v0.1`.
Read-only Tier-A preflight supports the following fixed three-role
successor boundary. **This is a frozen identity-rule target, not an implemented
v0.2 composite or a frozen source-parser grammar. BUILD remains blocked until
actual supported source fields and transport are demonstrated.** V0.1 runtime
and historical results retain their existing meaning.

- Keep exactly one eligible SEC, Nasdaq and Yahoo role. No general identity
  graph, extra provider, lookup table, model-supplied ID or new EI contract.
- For the SEC/Nasdaq issuer bridge, require the same explicitly labeled
  issuer CIK in both trusted retained records. The supported identifier is
  a nonzero, exact ten-ASCII-digit `SEC_CIK` string; compare literally, not via
  numeric coercion, inferred zero-padding or Unicode normalization. A filing
  locator may validate an explicit SEC header CIK under the existing exact
  locator rules, but the locator alone does not supply the association.
- SEC evidence must associate the explicit registrant and CIK with the actual
  filing and its independently qualified cover row. Nasdaq evidence must
  explicitly associate its instrument issuer with that same CIK. An isolated
  number, generic SEC link, ticker path, page title, search snippet or hidden
  script value is insufficient. A raw link is not an association simply
  because its URL contains a CIK; do not manufacture visible evidence from it.
- Nasdaq and Yahoo must still agree on issuer under existing ASCII case/space
  comparison. Punctuation remains significant. Yahoo need not expose a CIK;
  no ticker-only edge or transitive arbitrary-source association is permitted.
- CIK establishes only issuer correlation. Independently require exact ticker,
  eligible Common Stock class, explicit supported SEC exchange and Yahoo
  denomination. Multiple classes/rows, duplicate eligible roles, conflicting
  issuers within a single source's association, unequal CIKs or missing association proof fail
  closed. An explicit successor contradiction cannot be hidden by falling back
  to its name-only branch. Do not reinterpret old v0.1 records.
  SEC/Nasdaq spelling differences are intentionally bridgeable by the complete
  CIK proof; they are not a name conflict by themselves. Nasdaq/Yahoo spelling
  disagreement still fails the required existing name comparison.
- Every consumed association/field must retain the Host-authorized source ID,
  locator, full parsed hash, exact unchanged parsed span/hash and validated
  raw-to-parsed anchors under an explicitly supported parser ID/version.
  A future `host-listing-source-composite-v0.2` proof must name this exact
  issuer-bridge rule and its consumed evidence; that composite's remaining
  source grammar is not frozen here. Version source admission separately. Reuse existing
  fill-only binding, verified hypothesis/entity receipt and context-identity
  guards. No source/model acquisition is performed by the composite itself.
- The output remains the existing `UnderlyingKey` with MIC unknown and explicit
  provider-reported currency basis. This proves no current standing, price,
  option deliverable, freshness, session, NBBO or executability.

Required future adversarial checks: positive explicit bridge with different
SEC/Nasdaq punctuation; rejected missing/wrong/duplicate CIK; issuer-vs-security
confusion; detached/footer/hidden/link-only IDs; ticker/class/venue/currency
conflicts; stale or mismatched anchors/metadata; Yahoo name disagreement;
fill-only identity and unchanged v0.1 results. Synthetic checks alone cannot
prove that the real sources expose the required association.

The user-approved [SEC cover-text parser successor](local-event-delivery-v0.1.md#sec-cover-text-parsing-successor--2026-10-09)
may admit additional cover rows as source text. That does not expand this
composite's closed ordinary-share/Nasdaq grammar or establish listing identity.
In particular, Common Stock / Nasdaq Capital Market remains unsupported here.

The [bounded IREN packet](standalone-iren-identity-packet-2026-10-02.md)
already passed `READY_FOR_BOUNDED_HOST_KEY` review. This successor automates
only its source-field correlation, not source acquisition or research claims.
The old external body files are now absent; documentation/hash records alone
cannot populate runtime evidence. Tests must be synthetic, not manufactured
copies of an unavailable provider response.

## Inputs and supported grammar

Reuse the existing context-preparer hook, validated snapshot/receipt and exact
retained `HostSourceBody` records. This is an opt-in trusted Host preparer:
its closure captures an explicit immutable tuple of authorized source IDs,
designated by the existing trusted Host integration, never HTTP/model input.
Only those already Host-authorized records may establish listing fields.
URL/hash matching alone is not origin or source-truth verification; ordinary
unreviewed Tavily results cannot silently acquire authority. No authorized set
means no new listing bindings. The default driver is unchanged.
Add no public arguments, source/model calls,
provider, lookup table, packet IDs, caller assumption or EI schema.

For each actual verified hypothesis require exactly one verified entity
binding at `/hypotheses/{i}/underlying_symbol`, and the exact symbol it binds.
Do not create or rename hypotheses. Only the following three-source agreement
may fill a missing key:

1. An HTTPS SEC EDGAR filing body with an explicit Markdown cover table whose
   columns identify security title/class, trading symbol and registered
   exchange. The exact selected row must identify ordinary shares, that symbol
   and The Nasdaq Stock Market LLC. The explicit ordinary-share class supports
   the existing `EQUITY` enum, not a Futu-specific category.
2. An HTTPS target-specific `www.nasdaq.com/market-activity/stocks/<symbol>`
   page or subpage with an explicit instrument title containing the issuer,
   ordinary-share class and parenthesized matching ticker. Generic navigation
   or a symbol occurring only in the URL does not qualify.
3. An HTTPS `finance.yahoo.com/quote/<symbol>/` body whose explicit instrument
   header pairs the same issuer/ticker with `NasdaqGS - Delayed Quote` and the
   literal denomination `USD`. Generic navigation, dollar signs, financing
   amounts, reporting currency or another instrument's header do not qualify.

Extract fields from exact source text, not model entity text or stored packet
hashes. Use only an explicitly defined header/Markdown grammar, not arbitrary
semantic matching. Issuer agreement may ignore ASCII case and normalize
whitespace only; no inferred company alias, parent/subsidiary relation or fuzzy
match. Missing or contradictory issuer, class, ticker, venue or denomination,
multiple eligible rows/headers, or conflicting eligible sources stays unknown.

### Closed text grammar

Split only LF/CRLF lines; offsets refer to the unchanged decoded body. Whitespace
normalization is ASCII space/tab collapsing for field comparisons only, never
for finding or retaining excerpts. Tickers must match literally and be ASCII
uppercase letters/digits with optional internal dots/hyphens; no alias mapping.
Issuer names are nonempty printable ASCII text, compared after ASCII casefold
and whitespace collapsing; retain their original spelling in provenance.

- SEC issuer is the single preceding nonblank plain-text line before the
  literal `(Exact name of registrant as specified in its charter)` line.
  Unsupported markup remains unresolved. Require one pipe-delimited Markdown
  table with the exact three labels `Title of each class`, `Trading Symbol(s)`,
  `Name of each exchange on which registered` (case/ASCII whitespace comparison
  only), then a three-column dash/optional-colon separator. Require one data
  row in that table, with `Ordinary shares, no par value`, the exact ticker,
  and `The Nasdaq Stock Market LLC`. Additional data rows or competing tables
  stay unresolved; no title inferred from an unrelated narrative paragraph.
- Nasdaq title is one Markdown heading (one through six `#`, followed by one
  space) of the complete form `<issuer> Ordinary Shares (<ticker>)`. No suffix,
  links or emphasis markup is accepted. Require exactly one such instrument
  heading in the authorized body. Path begins the exact matching stock path;
  any suffix is one safe, nonempty ASCII segment only.
- Yahoo is one complete line `NasdaqGS - Delayed Quote•USD`, optionally followed
  by blank lines, then the complete heading `# <issuer> (<ticker>)`. The bullet
  is literal U+2022. Require exactly one such paired header in the authorized
  body; other denominations, venues, ticker headers, inserted nonblank content
  or multiple paired headers remain unresolved. Require the quote path exactly
  `/quote/<ticker>/`, preserving explicit provider-reported denomination.

These narrow formats are target supported grammar, not a claim that the missing
historical extracts used precisely this formatting. No permissive fallback or
real-format compatibility may be claimed without actual source evidence.

## Source and binding controls

Require exact HTTPS hosts/target paths: no credentials, non-default port,
query, fragment, encoded path ambiguity, traversal or spoof domains. SEC uses
the exact archive path grammar already implemented for source facts; table
identity evidence does not require narrative-date submission headers. Do not
reuse the known historical IREN hashes or offsets as new evidence.

Recompute full body hashes and exact excerpt offsets/hashes from retained
sources. The reference is canonical JSON recording rule version, source IDs,
locators, full hashes, exact consumed excerpts/offsets/hashes and the explicit
currency basis `yahoo_provider_reported_quote_denomination`.
Offsets are zero-based half-open Unicode code-point ranges in the exact retained
body; excerpt hashes use exact UTF-8 bytes. Every proof field must point to the
actual consumed line(s), not normalized strings, assumed locations or doc hashes.
Return `UnderlyingKey(symbol, None, EQUITY, "USD")` only after complete
agreement. MIC stays unknown. This does not establish exchange-certified
currency, current listing standing, live pricing, session, freshness, NBBO or
executability. Add no standing/freshness gate absent from the existing contract.

Compose with the existing description/date preparation. Preserve all existing
binding pairs, key/reference objects, supplied fields, raw input, registered
source records and caller-policy identity. Add only missing pairs keyed by the
actual verified hypothesis ID and symbol. No source registry mutation or reuse
of a model assertion as independent listing proof.

## Validation and remaining operational boundary

Synthetic tests: positive dynamic symbols/IDs; rejected hypothesis/entity
binding; missing or mismatched issuer/class/symbol/denomination; conflicting or
duplicate sources/rows/headers; URL spoof/path ambiguity; body hash mismatch;
fill-only identity and no extra calls. Include actual runtime integration and
constructor-bypass controls. Public factory signature/exports remain unchanged.
Independent contract and implementation review precede release.

Release validation (2026-10-07): 32 Event tests, 81 related tests and 1,819
full-suite tests passed (303.357s); compileall and diff checks passed. Independent
review found a case-sensitive competing quote-header check; the ASCII-casefold
fix and adversarial lower-case conflicting-currency tests passed targeted
re-review. Public exports remain 2 and the factory signature is unchanged.
These are synthetic implementation results, not live-format or EI acceptance
evidence. Builder timing was not recorded; no 70% work-share claim is made.

An adapter consuming supplied evidence is not an automatic source-acquisition
pipeline. If the existing source batch lacks these bodies, leave identity
unresolved. No real EI acceptance or explanation of the zero-hypothesis result
is claimed. No spent protocol is reopened or new acquisition authorized here.
