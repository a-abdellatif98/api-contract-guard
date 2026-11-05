---
name: api-contract
description: This skill should be used when the user edits or reviews an API contract or anything that shapes one (OpenAPI or Swagger files, GraphQL schemas or resolvers, serializers such as ActiveModel::Serializer, jbuilder, Blueprinter, Django REST Framework serializers, Laravel API Resources, request validation, route files), or mentions "breaking change", "API compatibility", "backwards compatible", "remove field", "rename field", "deprecate endpoint", "API versioning", "sunset", "oasdiff" or "graphql-inspector". Classifies changes as breaking or safe and gives a safe evolution path.
version: 1.0.0
---

# API Contract Guard

Catch changes that break existing API clients before they ship, and offer a safe way to make the same change.

## When This Skill Applies

- A contract file changes: OpenAPI or Swagger (`openapi.yaml`, `swagger.json`, `docs/api/*.yaml`), GraphQL SDL (`*.graphql`, `*.graphqls`, `*.gql`).
- Code that defines the wire format changes: serializers, API resources, GraphQL type classes, request validation (FormRequest, DTOs, DRF fields), route files.
- The user plans to remove, rename or retype a field, endpoint, argument or enum value, or to change auth.

## Workflow

1. **Find the contract sources.** Glob for spec files and the per-framework files listed in `references/sources.md`. Prefer a checked-in spec over inferring from code; if the spec is generated from code, review the code too.
2. **Get the old version.** Use what the user points to (an older file copy, a worktree, a pasted diff). Without shell access, do not try to read git objects; ask the user for an exported copy such as `git show origin/main:openapi.yaml > /tmp/openapi.base.yaml`.
3. **Classify every change** with `references/breaking-changes.md`. Remember the direction rule: what the server returns (responses, GraphQL output types) may only grow; what the server accepts (parameters, request bodies, arguments, input types) may only get looser.
4. **For each breaking change, propose a safe path** from `references/evolution-patterns.md` (add then deprecate then remove, expand and contract, a new version, Deprecation and Sunset headers).
5. **Recommend a CI check** from `references/tools.md` (oasdiff for OpenAPI, graphql-inspector for GraphQL) so the check does not depend on review alone. `scripts/openapi_diff.py` in this plugin is a small dependency free fallback for OpenAPI 3.

## Report Format

```
## API Contract Report

BREAKING
- [file:line] <change>: <which clients break and how>
  Safe path: <steps>

RISKY (not strictly breaking)
- [file:line] <change>: <why it may still hurt, e.g. new response enum value>

SAFE
- <additive changes, one line each>
```

If nothing is breaking, say so in one line and list the safe changes briefly.

## Escape Hatch for the Hook

The plugin's PreToolUse prompt hook blocks clearly breaking edits to OpenAPI and GraphQL schema files. When the user has explicitly approved a breaking change (for example in a new major version, or after the sunset date), add `# api-contract: breaking-approved` to the YAML or GraphQL file. JSON has no comments, so add `"x-api-contract-note": "api-contract: breaking-approved"` (OpenAPI allows `x-` extension keys on most objects, including the root). Never add the marker on your own initiative.

## Safety

Read files only. Never open `.env`, credential files, tokens, or `~/.claude`. Do not call live APIs to compare schemas unless the user asks and supplies the endpoint.

## References

- `references/breaking-changes.md`: what counts as breaking vs safe, for REST and GraphQL
- `references/evolution-patterns.md`: deprecate then remove, versioning, expand and contract, sunset headers
- `references/sources.md`: per-source detection notes (OpenAPI, GraphQL, Rails, Django REST Framework, Laravel, Node)
- `references/tools.md`: oasdiff, graphql-inspector and the bundled script, with verified commands
