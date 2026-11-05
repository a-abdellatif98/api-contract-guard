# Per-Source Detection Notes

For each source: where it lives, what to compare, and the patterns that signal a breaking change. Read files only; never open `.env` or credential files while looking for these.

## OpenAPI / Swagger

- Files: `openapi.{yaml,yml,json}`, `swagger.{yaml,json}`, `docs/api/**`, `public/api-docs/**`, `spec/**/swagger.yaml`. Confirm by a top-level `openapi: 3.x` or `swagger: "2.0"` key.
- Split specs: follow `$ref` into other files (`$ref: ./schemas/User.yaml`). A change in a shared schema affects every operation that references it, so list the affected operations.
- Look at: `paths` keys and methods, `parameters` (`required`, `schema`, `in`), `requestBody.required`, `components.schemas.*.required`, `properties`, `type`, `nullable` (3.0) or `type: [..., "null"]` (3.0 does not allow this; 3.1 does), `enum`, `security` (root and per operation), `components.securitySchemes`.
- `allOf` merges properties; `oneOf` / `anyOf` changes need careful reading (removing a branch is breaking on output when clients handle that branch, and on input when clients send it).
- Swagger 2.0 uses `definitions`, `parameters` with `in: body`, and `securityDefinitions`. oasdiff and the bundled script only read OpenAPI 3; convert first or review by hand.
- Generated specs: rswag (Rails, `rake rswag:specs:swaggerize`), drf-spectacular (`./manage.py spectacular --file schema.yml`), Scribe (`php artisan scribe:generate`), L5-Swagger (`php artisan l5-swagger:generate`), `@nestjs/swagger`. Regenerate after code changes and commit the spec so it can be diffed.

## GraphQL

- Files: `schema.graphql`, `*.graphqls`, `*.gql` with `type`, `input`, `enum`, `interface`, `union`, `scalar` or `schema` definitions. Files containing only `query` / `mutation` / `fragment` documents are client operations, not the schema.
- SDL signals: a field or enum value line disappears; `!` added to an argument or input field; `!` removed from an output field; a new argument with `!` and no `= default`; a type in a `union` removed; `implements` removed.
- graphql-ruby (Rails): `field :name, String, null: false` and `argument :id, ID, required: true` in `app/graphql/types/**`. Watch `null:` going from `false` to `true` (output loosening, breaking) and `required:` going to `true` (input tightening, breaking). Defaults differ between versions and configurations, so prefer explicit values. Dump the schema with `GraphQL::RakeTask` (`rake graphql:schema:dump`) or `MySchema.to_definition` and diff the SDL.
- Graphene (Django): `graphene.String(required=True)` means non-null. Dump with `./manage.py graphql_schema --schema app.schema.schema --out schema.graphql`.
- Strawberry (Python): type annotations decide nullability (`str` is non-null, `str | None` or `Optional[str]` is nullable).
- Lighthouse (Laravel): the schema is SDL in `graphql/schema.graphql`; `php artisan lighthouse:print-schema` prints the full schema with imports resolved.
- Node: Apollo Server / graphql-js SDL files, or code first schemas (Nexus `t.nonNull.string`, Pothos `t.exposeString(..., { nullable: true })`, TypeGraphQL `@Field({ nullable: true })`). Code first projects should emit SDL in CI and diff it.

## Rails

- ActiveModel::Serializer (`app/serializers/*_serializer.rb`): `attributes :id, :email`, `attribute :name`, `has_many`, `has_one`, `belongs_to`, `key:` renames, conditional `if:` options that make fields sometimes absent. A removed symbol from `attributes` removes a response field.
- jbuilder (`app/views/**/*.json.jbuilder`): `json.extract! user, :id, :email`, `json.email user.email`, `json.array!`, `json.partial!`, `json.key_format!` (changes every key's case), `json.ignore_nil!` (nil fields disappear instead of being null). Check partials, since one partial change affects many endpoints.
- Blueprinter (`app/blueprints/*_blueprint.rb`): `identifier :id`, `fields :a, :b`, `field :x, name: :y`, `association`, `view :extended`. Changing the default view or removing a field from it changes every response that uses it.
- Rails models `as_json` / `to_json` overrides and `render json: model` leak every column: a database migration that drops or renames a column then changes the API.
- Routes (`config/routes.rb`): `resources :orders, only: [...]` / `except:`, `namespace :api`, `scope`, `member` / `collection` blocks, custom `get "path", to:`. Removing an action from `only:` removes an endpoint. `bin/rails routes` lists the result.
- Input: strong parameters (`params.require(:order).permit(...)`): removing a permitted key silently drops that input. Model validations (`validates :x, presence: true`) and `params.require` add required input.

## Django REST Framework

- Serializers (`serializers.py`): `fields = [...]`, `fields = "__all__"` (adding or dropping a model field changes the API with no serializer edit), `exclude`, `read_only_fields`, `extra_kwargs`, `source="..."` (renames), `SerializerMethodField` (return type is whatever the method returns).
- Required input: serializer fields are required by default unless `required=False`, `read_only=True`, or a `default` is given. On `ModelSerializer`, a model field with `blank=True`, `null=True` or a default becomes optional. So a new model field without a default in `fields` is a new required input.
- `allow_null`, `allow_blank`, `choices` (enum values) and `max_length` changes narrow or widen input.
- Routes: `urls.py` `path()` / `re_path()`, `DefaultRouter().register(...)`, viewset `@action(detail=..., methods=[...])`, and `http_method_names` on views. Removing a mixin (for example `DestroyModelMixin`) removes an endpoint.
- Versioning helpers: `URLPathVersioning`, `NamespaceVersioning`, `AcceptHeaderVersioning` and `request.version` branches in serializers or views.

## Laravel

- API Resources (`app/Http/Resources/*.php`): the array returned by `toArray()`. Watch removed keys, renamed keys, `$this->when(...)`, `$this->whenLoaded(...)`, `$this->mergeWhen(...)` (fields become conditional), `$wrap` / `JsonResource::withoutWrapping()` (changes the top-level `data` envelope for every response), and `ResourceCollection` pagination meta.
- `$hidden`, `$visible`, `$appends` and casts on Eloquent models when controllers return models directly.
- Input: FormRequest `rules()` (`required`, `required_if`, `in:` lists for enums, `max:`), `$request->validate([...])` in controllers.
- Routes (`routes/api.php`): `Route::apiResource(...)`, `->only([...])`, `->except([...])`, `Route::prefix('v1')`, middleware changes (`auth:sanctum`, `auth:api`, `can:`, throttles) which are auth changes. `php artisan route:list --json` (Laravel 5.8.25 and later) gives a diffable list.

## Node (Express, NestJS, Fastify) and Prisma

- Routes: `router.get('/path', ...)`, `app.use('/prefix', router)`, NestJS `@Controller('orders')` with `@Get()`, `@Post()`, Fastify `fastify.route({ method, url, schema })`.
- Input validation: NestJS DTOs with class-validator (removing `@IsOptional()` makes a field required; `@IsEnum()` changes), zod (`.optional()` removed, `.strict()` added, `z.enum([...])` values removed), Joi (`.required()`), Fastify JSON Schema `required` arrays.
- Output: DTO classes with class-transformer `@Expose()` / `@Exclude()`, zod response schemas, Fastify `response` schemas (Fastify serializes with them, so fields missing from the response schema are dropped from the output).
- Prisma: handlers that return Prisma models directly (`return prisma.user.findMany()`) expose every selected column, so a `schema.prisma` field removal or rename changes the API. Prefer explicit `select` or a DTO.

## Webhooks and events

Outgoing webhook payloads and message schemas (AsyncAPI, JSON Schema, Avro, Protobuf) follow the output rule. Protobuf: never reuse or renumber field tags; mark removed fields `reserved`.
