import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "openapi_diff.py"
sys.path.insert(0, str(SCRIPT.parent))

import openapi_diff  # noqa: E402

BASE = {
    "openapi": "3.0.3",
    "info": {"title": "Shop", "version": "1"},
    "security": [{"apiKey": []}],
    "paths": {
        "/users/{id}": {
            "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}],
            "get": {
                "parameters": [{"name": "expand", "in": "query", "schema": {"type": "string"}}],
                "responses": {
                    "200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/User"}}}},
                    "404": {"description": "missing"},
                },
            },
            "delete": {"responses": {"204": {"description": "gone"}}},
        },
        "/orders": {
            "post": {
                "requestBody": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/NewOrder"}}}},
                "responses": {"201": {"description": "created"}},
            }
        },
    },
    "components": {
        "securitySchemes": {"apiKey": {"type": "apiKey", "in": "header", "name": "X-Key"}},
        "schemas": {
            "User": {
                "type": "object",
                "required": ["id", "email"],
                "properties": {
                    "id": {"type": "string"},
                    "email": {"type": "string"},
                    "age": {"type": "integer"},
                    "status": {"type": "string", "enum": ["active", "banned"]},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "friends": {"type": "array", "items": {"$ref": "#/components/schemas/User"}},
                },
            },
            "NewOrder": {
                "type": "object",
                "required": ["sku"],
                "properties": {
                    "sku": {"type": "string"},
                    "note": {"type": "string"},
                    "speed": {"type": "string", "enum": ["standard", "express"]},
                },
            },
        },
    },
}


def mutate(fn):
    doc = copy.deepcopy(BASE)
    fn(doc)
    return doc


def findings(new, level=openapi_diff.BREAKING):
    return [msg for lvl, msg in openapi_diff.diff(BASE, new) if lvl == level]


def user(doc):
    return doc["components"]["schemas"]["User"]


def order(doc):
    return doc["components"]["schemas"]["NewOrder"]


def test_identical_documents_have_no_findings():
    assert openapi_diff.diff(BASE, copy.deepcopy(BASE)) == []


@pytest.mark.parametrize("change,expected", [
    (lambda d: d["paths"]["/users/{id}"].pop("delete"), "DELETE /users/{id}: operation removed"),
    (lambda d: d["paths"].pop("/orders"), "POST /orders: operation removed"),
    (lambda d: user(d)["properties"].pop("email"), ".email: response property removed"),
    (lambda d: user(d)["properties"].__setitem__("age", {"type": "string"}), ".age: type changed from integer to string"),
    (lambda d: user(d)["required"].remove("email"), ".email: response property is no longer required"),
    (lambda d: user(d)["properties"]["id"].__setitem__("nullable", True), ".id: response value became nullable"),
    (lambda d: user(d)["properties"]["tags"]["items"].__setitem__("type", "integer"), ".tags[]: type changed"),
    (lambda d: order(d)["required"].append("note"), ".note: request property became required"),
    (lambda d: order(d)["properties"]["speed"]["enum"].remove("express"), "request enum values removed: express"),
    (lambda d: (order(d)["properties"].__setitem__("qty", {"type": "integer"}), order(d)["required"].append("qty")),
     ".qty: new required request property"),
    (lambda d: d["paths"]["/users/{id}"]["get"]["parameters"][0].__setitem__("required", True),
     "query parameter 'expand': parameter became required"),
    (lambda d: d["paths"]["/users/{id}"]["get"]["parameters"].append(
        {"name": "X-Tenant", "in": "header", "required": True, "schema": {"type": "string"}}),
     "header parameter 'x-tenant': new required parameter"),
    (lambda d: d["paths"]["/orders"]["post"]["requestBody"].__setitem__("required", True), "request body: became required"),
    (lambda d: d["paths"]["/users/{id}"]["get"]["responses"].pop("200"), "response 200: success response removed"),
    (lambda d: d["paths"]["/users/{id}"]["get"]["responses"]["200"]["content"].__setitem__(
        "application/xml", d["paths"]["/users/{id}"]["get"]["responses"]["200"]["content"].pop("application/json")),
     "media type application/json removed"),
    (lambda d: d["paths"]["/orders"]["post"].__setitem__("security", [{"apiKey": [], "oauth": ["write"]}]),
     "POST /orders: security tightened"),
    (lambda d: d["paths"]["/orders"]["post"].__setitem__("security", [{"oauth": []}]), "security tightened"),
])
def test_breaking_changes_are_reported(change, expected):
    found = findings(mutate(change))
    assert any(expected in msg for msg in found), found


@pytest.mark.parametrize("change", [
    lambda d: user(d)["properties"].__setitem__("nickname", {"type": "string"}),
    lambda d: order(d)["properties"].__setitem__("gift", {"type": "boolean"}),
    lambda d: order(d)["required"].remove("sku"),
    lambda d: order(d)["properties"]["speed"]["enum"].append("drone"),
    lambda d: d["paths"].__setitem__("/health", {"get": {"responses": {"200": {"description": "ok"}}}}),
    lambda d: d["paths"]["/users/{id}"]["get"]["parameters"].append({"name": "page", "in": "query", "schema": {"type": "integer"}}),
    lambda d: d["paths"]["/users/{id}"]["get"]["responses"].pop("404"),
    lambda d: d["paths"]["/users/{id}"]["get"].__setitem__("security", [{"apiKey": []}, {"oauth": []}]),
    lambda d: d.__setitem__("paths", {k.replace("{id}", "{userId}"): v for k, v in d["paths"].items()}),
    lambda d: order(d)["properties"]["note"].__setitem__("nullable", True),
])
def test_additive_changes_are_not_breaking(change):
    assert findings(mutate(change)) == []


def test_warnings_for_risky_but_not_breaking_changes():
    new = mutate(lambda d: (
        user(d)["properties"]["status"]["enum"].append("pending"),
        order(d)["properties"].pop("note"),
        d["paths"]["/users/{id}"]["get"].__setitem__("deprecated", True),
    ))
    warnings = findings(new, openapi_diff.WARNING)
    assert any("response enum values added: pending" in w for w in warnings)
    assert any(".note: request property removed" in w for w in warnings)
    assert any("GET /users/{id}: operation deprecated" in w for w in warnings)
    assert findings(new) == []


def test_allof_and_openapi_31_null_type():
    base = mutate(lambda d: user(d).update(
        {"allOf": [{"properties": {"plan": {"type": "string"}}, "required": ["plan"]}]}))
    base["openapi"] = "3.1.0"
    new = copy.deepcopy(base)
    user(new)["allOf"][0]["properties"]["plan"]["type"] = ["string", "null"]
    found = [m for lvl, m in openapi_diff.diff(base, new) if lvl == openapi_diff.BREAKING]
    assert any(".plan: response value became nullable" in m for m in found), found


def run(tmp_path, base, new, *args, base_name="base.json", new_name="new.json", raw=False):
    a, b = tmp_path / base_name, tmp_path / new_name
    a.write_text(base if raw else json.dumps(base))
    b.write_text(new if raw else json.dumps(new))
    return subprocess.run([sys.executable, str(SCRIPT), str(a), str(b), *args], capture_output=True, text=True)


def test_cli_exit_codes_and_json_output(tmp_path):
    assert run(tmp_path, BASE, BASE).returncode == 0
    result = run(tmp_path, BASE, mutate(lambda d: d["paths"].pop("/orders")), "--json")
    assert result.returncode == 1
    assert {"level": "BREAKING", "message": "POST /orders: operation removed"} in json.loads(result.stdout)


def test_cli_fail_on_warning(tmp_path):
    new = mutate(lambda d: d["paths"]["/users/{id}"]["get"].__setitem__("deprecated", True))
    assert run(tmp_path, BASE, new).returncode == 0
    assert run(tmp_path, BASE, new, "--fail-on-warning").returncode == 1


def test_cli_reads_yaml(tmp_path):
    pytest.importorskip("yaml")
    base = "openapi: 3.0.0\ninfo: {title: t, version: '1'}\npaths:\n  /a:\n    get:\n      responses: {'200': {description: ok}}\n"
    new = "openapi: 3.0.0\ninfo: {title: t, version: '1'}\npaths: {}\n"
    result = run(tmp_path, base, new, base_name="a.yaml", new_name="b.yaml", raw=True)
    assert result.returncode == 1
    assert "GET /a: operation removed" in result.stdout


def test_json_works_without_yaml(monkeypatch, tmp_path):
    monkeypatch.setattr(openapi_diff, "yaml", None)
    path = tmp_path / "a.json"
    path.write_text(json.dumps(BASE))
    assert openapi_diff.load(str(path))["openapi"] == "3.0.3"
    bad = tmp_path / "a.yaml"
    bad.write_text("openapi: 3.0.0\n")
    with pytest.raises(openapi_diff.LoadError, match="PyYAML"):
        openapi_diff.load(str(bad))


def test_cli_rejects_non_openapi(tmp_path):
    result = run(tmp_path, {"swagger": "2.0"}, BASE)
    assert result.returncode == 2
    assert "not an OpenAPI 3 document" in result.stderr
