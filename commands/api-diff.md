---
description: Compare current API contract files with an older copy and report breaking vs non-breaking changes
argument-hint: [base-ref-or-file]
allowed-tools: [Read, Glob, Grep]
---

# API Contract Diff

Compare the current API contract with an older copy the user points to, and report what would break existing clients.

## Arguments

The user invoked this command with: $ARGUMENTS

## Instructions

1. **Resolve the base (old) copy.**
   - A file path (for example `/tmp/openapi.base.yaml`, `old/schema.graphql`): that is the base. Match it to the current file with the same role (same name, or the only spec of the same kind in the project).
   - A directory (an exported copy or a git worktree of the old version): pair each contract file in it with the file at the same relative path in the project.
   - A git ref (`main`, `origin/main`, `v2.3.0`, a SHA) or nothing: this command reads files only and cannot run git. Ask the user to export the old copy and run the command again with its path, for example:
     - `git show origin/main:openapi.yaml > /tmp/openapi.base.yaml` then `/api-diff /tmp/openapi.base.yaml`
     - `git worktree add /tmp/api-base origin/main` then `/api-diff /tmp/api-base`
     Stop after giving these instructions.

2. **Find the current contract files** with Glob (skip `node_modules`, `vendor`, build output):
   - OpenAPI / Swagger: `**/openapi*.{yaml,yml,json}`, `**/swagger*.{yaml,yml,json}`, then confirm the top-level `openapi:` or `swagger:` key.
   - GraphQL SDL: `**/*.{graphql,graphqls,gql}` that define types, not client operations.
   - If the base is a directory, also compare code that shapes the contract, using `skills/api-contract/references/sources.md`: serializers (`app/serializers`, `app/views/**/*.json.jbuilder`, `app/blueprints`, DRF `serializers.py`, `app/Http/Resources`), request validation, and route files (`config/routes.rb`, `urls.py`, `routes/api.php`, Express or NestJS controllers).
   Never open `.env`, credential files, tokens or anything under `~/.claude`.

3. **Read both versions and compare them structurally**, not line by line. For OpenAPI, resolve `$ref`s to `components` (and to other files when the ref points there) before comparing; for split specs, compare each referenced file. Walk every operation in the base: path, method, parameters, request body, responses per status and media type, schemas (properties, `required`, `type`, `nullable`, `enum`, `items`, `allOf`), and `security`. For GraphQL, walk every type, field, argument, input field, enum value, union member and interface.

4. **Classify each change** with `skills/api-contract/references/breaking-changes.md`, applying the direction rule (output may only grow, input may only get looser).

5. **Report** in this format:

```
## API Contract Diff: <base> -> <current>

### BREAKING (N)
- <METHOD path or Type.field> [<file>:<line>]: <change>
  Impact: <which clients break and how>
  Safe path: <pattern from evolution-patterns.md>

### RISKY (N)
- ... (new response enum values, format changes, default changes, status code changes)

### NON-BREAKING (N)
- ... (one line each: added endpoints, optional params, new response fields, deprecations, docs)

### Verdict
<"Safe to ship" or "N breaking changes: needs a new version or a deprecation period">
```

6. **Suggest a CI guard** from `skills/api-contract/references/tools.md`: `oasdiff breaking --fail-on ERR <base> <current>` for OpenAPI, `graphql-inspector diff <base> <current>` for GraphQL, or this plugin's `python3 scripts/openapi_diff.py <base> <current>` when no extra tooling is wanted. Say the user can run these; this command does not run them.

If no contract files are found, say so, list where you looked, and ask for the path.
