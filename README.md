# api-contract-guard

A Claude plugin that catches breaking API changes before they ship.

## What It Catches

- Removed or renamed response fields, and response fields that became optional or nullable
- Type changes on fields and parameters
- New required request parameters, headers, body properties, GraphQL arguments and input fields
- Removed endpoints, HTTP methods and success responses
- Removed request enum values (and risky new response enum values)
- Auth changes: new security requirements, new scopes, dropped schemes
- GraphQL field, type, argument and enum value removal, and nullability changes in the breaking direction

Sources: OpenAPI 3 and Swagger files, GraphQL schemas (SDL, graphql-ruby, Graphene, Strawberry, Lighthouse, Nexus, Pothos, TypeGraphQL), Rails serializers (ActiveModel::Serializer, jbuilder, Blueprinter), Django REST Framework serializers, Laravel API Resources, Node DTOs and validators, and route files.

## Installation

```
/plugin install api-contract-guard@claude-plugins-official
```

## Usage

### Skill: api-contract

Activates when you edit contract files or talk about breaking changes, deprecation or versioning. It classifies changes as BREAKING, RISKY or SAFE and suggests a safe path (add then deprecate then remove, expand and contract, a new version, `Deprecation` and `Sunset` headers). References:

- `breaking-changes.md`: REST and GraphQL rules, including the direction rule
- `evolution-patterns.md`: safe evolution patterns
- `sources.md`: what to look for in each framework
- `tools.md`: oasdiff, graphql-inspector and the bundled script

### Command: /api-diff

```
/api-diff /tmp/openapi.base.yaml
/api-diff /tmp/api-base
```

Compares the current contract files with an older copy (a file, or a directory such as a git worktree) and reports breaking, risky and non-breaking changes. The command only reads files. To compare with a git ref, export the old copy first:

```
git show origin/main:openapi.yaml > /tmp/openapi.base.yaml
git worktree add /tmp/api-base origin/main
```

### Hook: blocks clearly breaking schema edits

A PreToolUse prompt hook checks Edit, Write and MultiEdit calls. For OpenAPI and GraphQL schema files it blocks clearly breaking edits (removing an endpoint, field, argument or enum value; making something optional required; adding a required input) and tells Claude the safe pattern. Everything else, and every non-contract file, goes through. A Write that replaces a whole file is allowed because the hook cannot see what it removed; use `/api-diff` for those.

To go ahead with a breaking change you have approved, ask Claude to add `# api-contract: breaking-approved` to the YAML or GraphQL file, or `"x-api-contract-note": "api-contract: breaking-approved"` to a JSON spec. The hook is a single model call per edit, so it adds a short delay.

### Optional: deterministic OpenAPI checker

`scripts/openapi_diff.py` diffs two OpenAPI 3 files (JSON with the standard library alone, YAML with PyYAML) and lists breaking changes. The plugin does not register it; run it yourself or in CI:

```
python3 scripts/openapi_diff.py base.yaml openapi.yaml
python3 scripts/openapi_diff.py base.json openapi.json --json --fail-on-warning
```

Exit codes: 0 clean, 1 breaking changes found, 2 bad input. For full coverage in CI, prefer `oasdiff breaking --fail-on ERR base.yaml openapi.yaml` and `graphql-inspector diff old.graphql schema.graphql`.

## Safety

The plugin ships no command hooks and gives no shell access to its command. It never reads `.env`, credentials or `~/.claude`, and never calls live APIs on its own.

## Development

```
pip install pytest pyflakes pyyaml
python3 -m pytest -q tests
python3 -m pyflakes scripts tests
```

## License

MIT
