# Breaking vs Safe Changes

## The direction rule

- **Output** (responses, GraphQL object fields, webhooks you send): clients read it. Removing, renaming, retyping or making something possibly absent or null breaks them. Adding is safe.
- **Input** (path, query, header and cookie parameters, request bodies, GraphQL arguments and input types): clients write it. Adding a requirement or narrowing accepted values breaks them. Loosening is safe.

A rename is always a removal plus an addition, so it is breaking on output and on required input.

## REST / OpenAPI

| Change | Verdict | Notes |
|---|---|---|
| Remove an endpoint (path) or an HTTP method on it | BREAKING | Includes changing the literal path segments. Renaming a path template variable (`{id}` to `{userId}`) is not breaking on the wire. |
| Remove or rename a response property | BREAKING | Also when the property moves under another object. |
| Response property goes from required to optional | BREAKING | Clients that assume it is present will fail. |
| Response property becomes nullable | BREAKING | `nullable: true` in 3.0, `type: [x, "null"]` in 3.1. |
| Change a property or parameter type (`integer` to `string`, object to array) | BREAKING | Widening `integer` to `number` on input only is safe. |
| Change `format` (`date-time` to `date`, `int32` to `int64`) | RISKY | Often breaks strict parsers and generated clients. |
| Add a required parameter, header or request property | BREAKING | |
| Optional parameter or request property becomes required | BREAKING | |
| Request body becomes required | BREAKING | |
| Remove an enum value from a request parameter or body | BREAKING | Clients sending that value get 4xx. |
| Add an enum value to a response | RISKY | Clients with exhaustive switches or generated enums may crash. Document that clients must tolerate unknown values. |
| Remove an enum value from a response | Usually safe | Clients just stop seeing it. |
| Add an enum restriction to a previously free request value | BREAKING | |
| Tighten validation (`maxLength`, `minimum`, `pattern`) on input | BREAKING | For values clients already send. |
| Remove a success status code or response media type | BREAKING | Removing `application/json` while adding `application/xml` breaks JSON clients. |
| Change the success status code (200 to 201, 200 to 204) | RISKY | Many clients check exact codes. |
| Auth: add a security requirement, add scopes, drop a scheme, move an API key from header to query | BREAKING | Adding an alternative scheme (another entry in the `security` array) is safe. |
| Change default values, pagination defaults or sort order | RISKY | Behavioural, invisible to schema diff tools. |
| Change error body shape | BREAKING for clients that parse errors | |
| Add an endpoint, an optional parameter, an optional request property or a response property | SAFE | A response property is unsafe only for clients that reject unknown properties; say so if `additionalProperties: false` is used for responses. |
| Mark something `deprecated: true` | SAFE | Signals future removal. |
| Descriptions, examples, summaries, tags | SAFE | |

## GraphQL

| Change | Verdict | Notes |
|---|---|---|
| Remove a type, field, argument, enum value, union member or interface implementation | BREAKING | Queries selecting them fail validation. Removing a field already marked `@deprecated` is still breaking for clients that never migrated; graphql-inspector can downgrade it to dangerous with `--rule suppressRemovalOfDeprecatedField`. |
| Change a field's type (`String` to `Int`, `User` to `[User]`) | BREAKING | |
| Output field becomes nullable (`String!` to `String`) | BREAKING | Clients relying on non-null break. |
| Output field becomes non-null (`String` to `String!`) | SAFE for clients | Server side, a null from the resolver now errors and the null propagates to the nearest nullable parent, so check resolvers can never return null. |
| Add a required argument or required input field (non-null with no default) | BREAKING | |
| Argument or input field goes from nullable to non-null | BREAKING | This is the "nullability tightening" that breaks clients. |
| Argument or input field goes from non-null to nullable | SAFE | |
| Add an enum value | RISKY | Breaks clients that switch exhaustively on output enums. |
| Add a type, a field, an optional argument (nullable or with a default) | SAFE | |
| Change a default argument value | RISKY | Behaviour changes for clients that omit it. |
| Add or change `@deprecated` | SAFE | |

## Serializers and routes

Code that builds responses changes the contract even when no spec file changes:

- Removing an attribute from a serializer, resource or view template removes a response field.
- Changing the source of an attribute (`source:`, a method body) can change its type or nullability.
- Adding a required validation rule (FormRequest `required`, DRF field without `required=False`, removing `@IsOptional()`) adds a required input.
- Removing or renaming a route, or narrowing `only:` / `except:` in Rails `resources`, removes endpoints.
- Changing serializer inclusion rules (Laravel `when()`, `whenLoaded()`, DRF `fields`) can turn always present fields into sometimes present ones.

See `sources.md` for what to look for per framework.
