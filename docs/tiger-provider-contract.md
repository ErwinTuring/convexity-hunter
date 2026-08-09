# Tiger Provider Local Runtime Boundary v0.1

## Status and scope

This Tier-A contract selects Tiger OpenAPI as the Convexity Hunter MVP primary
market-data provider and freezes only the first provider work unit:

```text
local provider-native configuration discovery
    -> local configuration validation
    -> non-networking Tiger SDK configuration
    -> non-preempting QuoteClient initialization
```

This work unit does not retrieve market data, normalize provider fields, scan
an option chain, select a contract, calculate analytics, or change any
provider-neutral market-data record.

## Credential boundary

Tiger credentials are per-user, local-only runtime state. They are never
repository state, application defaults, model or agent inputs, logs,
exceptions, source references, calculation lineage, research records, reports,
fixtures, or child-agent context.

The product consumes Tiger's official
`tiger_openapi_config.properties`; it does not define another credential
schema. The only application environment variable is:

```text
CONVEXITY_HUNTER_TIGER_CONFIG
```

Its value is a local filesystem path only. It must never contain credential
material.

## Public module boundary

The direct module is:

```text
convexity_hunter.providers.tiger
```

It exports exactly:

```text
resolve_tiger_config_path
initialize_tiger_quote_client
```

Neither name is re-exported from `convexity_hunter` or
`convexity_hunter.providers`. The provider-neutral core never imports this
module or the Tiger SDK.

## Configuration resolution

`resolve_tiger_config_path()` has no public parameters and returns one
canonical absolute `pathlib.Path` without reading or returning configuration
contents.

Resolution precedence is exact:

1. When `CONVEXITY_HUNTER_TIGER_CONFIG` is present, it is authoritative.
2. Otherwise use
   `~/.config/tigeropen/tiger_openapi_config.properties`.
3. Otherwise raise a concise configuration-not-found failure with local setup
   instructions.

An invalid explicit override never falls back to the default. A supplied value
may use `~`, but after expansion it must be absolute. Blank, relative,
URI-like, NUL-containing, missing, non-regular, or unsafe paths fail with
stable sanitized messages that do not echo the supplied value.

The canonical target must be outside the Convexity Hunter repository root.
Canonicalization occurs before containment checking, so a symlink into the
repository is rejected. An external symlink to an external target is allowed;
the canonical target is returned and validated.

On POSIX, the target must be owned by the current user, owner-readable, and
have no owner-execute, group, or world permission bits. `0400` and `0600` are
therefore accepted. Parent-directory mode is not part of this work unit. On a
non-POSIX platform, existence, regular-file, canonical-path, and repository-
containment checks still apply.

The repository root is discovered from the resolved provider module location
and its ancestor `.git` marker, never from caller input or an LLM.

## SDK isolation and initialization

The Tiger SDK is an optional installation extra pinned for the reviewed MVP
boundary:

```text
convexity-hunter[tiger]
    -> tigeropen==3.7.0
```

The provider module imports the SDK lazily. Importing `convexity_hunter`, the
provider package, or the Tiger provider module performs no network call and
does not resolve or read credentials.

Before SDK construction, any process environment key beginning with
`TIGEROPEN_` causes a sanitized failure. This prevents the SDK's alternate
environment credential schema from overriding the product's single path-only
resolution contract.

`initialize_tiger_quote_client()`:

1. resolves and validates the provider configuration;
2. constructs `TigerOpenClientConfig` with the exact path and
   `enable_dynamic_domain=False`;
3. verifies only that Tiger ID, account, and private-key fields are present,
   without returning or logging their values;
4. disables SDK token refresh and SDK-configured file logging; and
5. constructs `QuoteClient` with a non-propagating discard logger and
   `is_grab_permission=False`.

Initialization therefore performs no dynamic-domain request, license request,
permission grab, quote request, token-refresh thread, trading request, or
other intentional network action. A later provider runtime contract must
explicitly own network calls and quote-permission lifecycle.

Tiger SDK import, configuration, and client-construction failures are wrapped
in stable sanitized `RuntimeError` messages. Raw SDK exception text is not
included.

If the SDK's provider-native adjacent `tiger_openapi_token.properties` exists,
it remains local provider state and must satisfy the same external canonical
path, ownership, and permission checks before SDK construction. The product
does not create, copy, render, or return that file.

## Failure precedence

Observable validation precedence is:

```text
unsupported TIGEROPEN_* environment
-> path source and syntax
-> canonical repository containment
-> existence and regular-file validation
-> POSIX ownership and mode
-> adjacent provider-token-file validation
-> SDK availability
-> required field presence
-> sanitized client initialization
```

No failure contains configuration contents, private-key material, Tiger ID,
account ID, token, secret, license value, or caller-supplied path text.

## Tests and repository safety

Committed tests use temporary synthetic files and fake SDK classes only. They
must not read the user's real Tiger configuration or make network calls.

Defense-in-depth ignore rules cover obvious Tiger configuration/token files,
PEM files, key files, and `.secrets/`. Runtime rejection of in-repository
credentials remains authoritative; `.gitignore` is not a security boundary.

## Explicit exclusions

This work unit adds no market-data retrieval, adapter normalization, raw
payload fixture, monthly classification record, option quote, volume, open
interest, historical bar, dividend, rate, IV, Greek, transformation,
screening, reporting, monitoring, scheduling, order, or execution behavior. It
adds no secret database, cloud vault, OAuth flow, multi-user service, generic
secret manager, provider registry, fallback provider, or provider arbitration.
