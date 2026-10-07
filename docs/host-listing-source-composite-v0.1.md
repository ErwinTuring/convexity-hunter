# Host Listing Source Composite v0.1

Status: FROZEN / BUILD READY / INDEPENDENT CONTRACT REVIEW PASS.
Production implementation absent.

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

An adapter consuming supplied evidence is not an automatic source-acquisition
pipeline. If the existing source batch lacks these bodies, leave identity
unresolved. No real EI acceptance or explanation of the zero-hypothesis result
is claimed. No spent protocol is reopened or new acquisition authorized here.
