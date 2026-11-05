# Safe Evolution Patterns

## 1. Add, deprecate, then remove

The default for removing or renaming a field, parameter or endpoint.

1. Add the replacement (new field, new endpoint) next to the old one. Return both.
2. Mark the old one deprecated:
   - OpenAPI: `deprecated: true` on the operation, parameter or schema property.
   - GraphQL: `@deprecated(reason: "Use fullName")` on the field or enum value. Newer spec drafts and many servers (graphql-js, graphql-ruby, Strawberry and others) also allow it on arguments and input fields; check your server version.
3. Tell clients: changelog, docs, and response headers (pattern 4).
4. Measure usage: access logs per endpoint, GraphQL field usage (Hive, Apollo GraphOS or your own resolver metrics), API key analytics.
5. Remove only after usage is zero or the announced sunset date has passed. Removal is still a breaking change for anyone left, so mark the removal commit as approved (`api-contract: breaking-approved`).

## 2. Expand and contract (parallel change)

For type changes and shape changes, the API version of the database pattern.

1. Expand: add `price_cents` (integer) next to `price` (string). Write and return both.
2. Migrate clients to the new field.
3. Contract: stop returning `price` once no client reads it.

For inputs, accept both shapes for a while: accept the old parameter name as an alias, or accept a string and an integer, then remove the old form after the sunset date.

## 3. Versioning

Use a new version when many breaking changes land together, or when a change cannot be made additive.

- URI version: `/v1/orders`, `/v2/orders`. Simple to route and cache. Rails `namespace :v2`, Django `path("v2/", include(...))` or DRF `URLPathVersioning`, Laravel `Route::prefix('v2')`, Express `app.use('/v2', router)`.
- Header or media type version: `Accept: application/vnd.example.v2+json`, DRF `AcceptHeaderVersioning`, or a custom header. Cleaner URLs, harder to test in a browser.
- Date based versions (one version per release date, pinned per API key) suit public APIs with many clients.
- GraphQL usually avoids versions and evolves continuously with `@deprecated`; when a version is unavoidable, serve a second schema at a second endpoint.

Keep the old version running for an announced period and give each version its own OpenAPI file so diff tools can guard it.

## 4. Deprecation and Sunset headers

- `Sunset` (RFC 8594): the HTTP date after which the resource is expected to stop responding, for example `Sunset: Sat, 31 Oct 2027 23:59:59 GMT`. Pair it with `Link: <https://example.com/docs/migrate-v2>; rel="sunset"`.
- `Deprecation` (RFC 9745): says the resource is or will be deprecated. Its value is a Structured Field date, for example `Deprecation: @1767225599` (Unix seconds). Pair it with `Link: <...>; rel="deprecation"`.

Send them from the deprecated endpoints only, in middleware or a controller concern, and document them in the OpenAPI `headers` of the affected responses.

## 5. Tolerant readers, strict writers

Ask clients to ignore unknown response fields and handle unknown enum values (a fallback branch). Generated clients should not be configured to reject additional properties in responses. This turns "add a field" and "add an enum value" into truly safe changes.

## 6. Making something required, safely

1. Add the field as optional with a server side default.
2. Announce, then start logging requests that omit it.
3. Make it required in a new version, or after the sunset date when the logs show no omissions.

## 7. Auth changes

Add the new scheme as an alternative first (`security: [{apiKey: []}, {oauth2: [read]}]`), migrate clients, then remove the old alternative after the sunset date. Adding scopes to an existing requirement is breaking for tokens issued without them.

## 8. Guard it in CI

Diff the contract on every pull request against the main branch and fail on breaking changes unless the PR is labelled or approved. See `tools.md`.
