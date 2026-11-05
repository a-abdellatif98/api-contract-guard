# Recommended Tools

Commands below were checked against the projects' documentation (November 2026). Flags change between releases; confirm with `--help` before wiring them into CI.

## oasdiff (OpenAPI 3)

Docs: https://github.com/oasdiff/oasdiff

Install: `brew install oasdiff`, `go install github.com/oasdiff/oasdiff@latest`, or Docker `docker run --rm -t tufin/oasdiff ...`.

```
oasdiff breaking base.yaml revision.yaml               # breaking changes only
oasdiff breaking --fail-on ERR base.yaml revision.yaml # exit 1 on ERR level changes
oasdiff breaking --format markdown base.yaml revision.yaml
oasdiff changelog base.yaml revision.yaml              # breaking and non-breaking changes
oasdiff diff base.yaml revision.yaml                   # full structural diff
oasdiff changelog HEAD~1:openapi.yaml HEAD:openapi.yaml
```

- Inputs can be local files, http(s) URLs, or git revisions in `REV:path` form.
- `--fail-on` takes `ERR`, `WARN` or `INFO`; each also fails on the more severe levels.
- `--format` values for `breaking` include `text` (default), `json`, `yaml`, `markdown`, `html`, `junit`, `githubactions`, `singleline`.
- Only OpenAPI 3.x. Swagger 2.0 specs need converting first.
- A GitHub Action exists (`oasdiff/oasdiff-action`); check its README for current inputs.

## graphql-inspector (GraphQL)

Docs: https://the-guild.dev/graphql/inspector/docs

Install: `npm i --global @graphql-inspector/cli graphql` (`graphql` is a peer dependency).

```
graphql-inspector diff old-schema.graphql schema.graphql
graphql-inspector diff 'git:origin/main:./schema.graphql' 'schema.graphql'
graphql-inspector diff https://api.example.com/graphql schema.graphql
graphql-inspector diff old.graphql schema.graphql --rule suppressRemovalOfDeprecatedField
```

- Exits non-zero when at least one breaking change is found, so it works as a CI gate.
- The `git:` pointer needs the git loader installed alongside the CLI.
- Useful rules: `dangerousBreaking` (treat dangerous changes as breaking), `suppressRemovalOfDeprecatedField` (removing a deprecated field is reported as dangerous), `ignoreDescriptionChanges`, `safeUnreachable`, `considerUsage` (needs `--onUsage`).
- Changes are reported as breaking, dangerous or safe, which maps onto BREAKING, RISKY and SAFE in this plugin's report.
- For code first servers, print the SDL first (see `sources.md`) and diff that.

## Bundled script: scripts/openapi_diff.py

A small, deterministic checker for OpenAPI 3 JSON or YAML. It needs only the Python standard library; YAML input also needs PyYAML (`pip install pyyaml`). It is not registered as a hook.

```
python3 scripts/openapi_diff.py base.yaml openapi.yaml
python3 scripts/openapi_diff.py base.json openapi.json --json
python3 scripts/openapi_diff.py base.yaml openapi.yaml --fail-on-warning
```

Exit codes: 0 no breaking changes, 1 breaking changes (or warnings with `--fail-on-warning`), 2 unreadable or non OpenAPI 3 input.

It reports removed operations, success responses and media types; removed or no longer required response properties; responses that became nullable; type changes; new or newly required parameters, request properties and request bodies; request enum values removed; and tightened security. It warns on response enum additions, format changes, removed request properties and parameters, and newly deprecated operations. It resolves local `#/` refs and merges `allOf`, but does not follow refs into other files or analyse `oneOf` / `anyOf`. Use oasdiff for full coverage.

## Other options

- OpenAPITools `openapi-diff` (Java, Docker image `openapitools/openapi-diff`) also classifies OpenAPI changes; check its README for current flags.
- Spectral (`@stoplight/spectral-cli`) lints a single spec (for example requiring `deprecated` operations to carry a sunset note); it does not diff two versions.
- Apollo GraphOS (`rover subgraph check` / `rover graph check`) and GraphQL Hive check schema changes against real client usage.
