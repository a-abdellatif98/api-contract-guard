#!/usr/bin/env python3
"""Diff two OpenAPI 3 documents (JSON or YAML) and list breaking changes. Exit 1 if any are found."""

import argparse
import json
import re
import sys

try:
    import yaml
except ImportError:
    yaml = None

BREAKING = "BREAKING"
WARNING = "WARNING"
METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
REQUEST = "request"
RESPONSE = "response"


class LoadError(Exception):
    pass


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        raise LoadError(f"cannot read {path}: {e}")
    try:
        doc = json.loads(text)
    except ValueError:
        if yaml is None:
            raise LoadError(f"{path} is not JSON and PyYAML is not installed (pip install pyyaml)")
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError as e:
            raise LoadError(f"cannot parse {path}: {e}")
    if not isinstance(doc, dict) or not str(doc.get("openapi", "")).startswith("3"):
        raise LoadError(f"{path} is not an OpenAPI 3 document")
    return doc


def resolve(doc, node, seen=()):
    while isinstance(node, dict) and isinstance(node.get("$ref"), str):
        ref = node["$ref"]
        if not ref.startswith("#/") or ref in seen:
            return {}
        seen = seen + (ref,)
        target = doc
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            target = target.get(part, {}) if isinstance(target, dict) else {}
        node = target
    return node if isinstance(node, dict) else {}


def flatten(doc, schema, seen=()):
    """Resolve $ref and merge allOf members into one schema dict."""
    ref = schema.get("$ref") if isinstance(schema, dict) else None
    if ref in seen:
        return {}
    if ref:
        seen = seen + (ref,)
    schema = resolve(doc, schema)
    if "allOf" not in schema:
        return schema
    merged = {k: v for k, v in schema.items() if k != "allOf"}
    merged["properties"] = dict(merged.get("properties", {}))
    merged["required"] = list(merged.get("required", []))
    for part in schema["allOf"]:
        part = flatten(doc, part, seen)
        merged["properties"].update(part.get("properties", {}))
        merged["required"] += part.get("required", [])
        for key in ("type", "enum", "items", "nullable", "format"):
            if key in part and key not in merged:
                merged[key] = part[key]
    return merged


def types_of(schema):
    t = schema.get("type")
    if t is None:
        return set()
    return {t} if isinstance(t, str) else set(t)


def is_nullable(schema):
    return schema.get("nullable") is True or "null" in types_of(schema)


def compare_schema(old_doc, new_doc, old, new, where, direction, out, seen=()):
    key = (id(old), id(new))
    if key in seen:
        return
    seen = seen + (key,)
    old = flatten(old_doc, old)
    new = flatten(new_doc, new)

    old_types = types_of(old) - {"null"}
    new_types = types_of(new) - {"null"}
    if old_types and new_types and old_types != new_types:
        widened = old_types == {"integer"} and new_types == {"number"}
        narrowed = old_types == {"number"} and new_types == {"integer"}
        if not ((widened and direction == REQUEST) or (narrowed and direction == RESPONSE)):
            out.append((BREAKING, f"{where}: type changed from {'/'.join(sorted(old_types))} to {'/'.join(sorted(new_types))}"))
            return
    if old.get("format") and new.get("format") and old["format"] != new["format"]:
        out.append((WARNING, f"{where}: format changed from {old['format']} to {new['format']}"))

    if direction == RESPONSE and is_nullable(new) and not is_nullable(old):
        out.append((BREAKING, f"{where}: response value became nullable"))
    if direction == REQUEST and is_nullable(old) and not is_nullable(new):
        out.append((BREAKING, f"{where}: request value no longer accepts null"))

    compare_enum(old.get("enum"), new.get("enum"), where, direction, out)

    old_props = old.get("properties", {}) or {}
    new_props = new.get("properties", {}) or {}
    old_req = set(old.get("required", []) or [])
    new_req = set(new.get("required", []) or [])
    for name in sorted(old_props):
        path = f"{where}.{name}"
        if name not in new_props:
            if direction == RESPONSE:
                out.append((BREAKING, f"{path}: response property removed"))
            else:
                out.append((WARNING, f"{path}: request property removed (clients still sending it may be rejected)"))
            continue
        if direction == RESPONSE and name in old_req and name not in new_req:
            out.append((BREAKING, f"{path}: response property is no longer required (may be absent)"))
        if direction == REQUEST and name not in old_req and name in new_req:
            out.append((BREAKING, f"{path}: request property became required"))
        compare_schema(old_doc, new_doc, old_props[name], new_props[name], path, direction, out, seen)
    for name in sorted(set(new_props) - set(old_props)):
        if direction == REQUEST and name in new_req:
            out.append((BREAKING, f"{where}.{name}: new required request property"))

    if isinstance(old.get("items"), dict) and isinstance(new.get("items"), dict):
        compare_schema(old_doc, new_doc, old["items"], new["items"], f"{where}[]", direction, out, seen)


def compare_enum(old_enum, new_enum, where, direction, out):
    if old_enum is None and new_enum is None:
        return
    if old_enum is None:
        if direction == REQUEST:
            out.append((BREAKING, f"{where}: request value is now restricted to an enum"))
        return
    if new_enum is None:
        if direction == RESPONSE:
            out.append((WARNING, f"{where}: response enum restriction removed (clients may get unknown values)"))
        return
    removed = [v for v in old_enum if v not in new_enum]
    added = [v for v in new_enum if v not in old_enum]
    if removed and direction == REQUEST:
        out.append((BREAKING, f"{where}: request enum values removed: {', '.join(map(str, removed))}"))
    if removed and direction == RESPONSE:
        out.append((WARNING, f"{where}: response enum values removed: {', '.join(map(str, removed))}"))
    if added and direction == RESPONSE:
        out.append((WARNING, f"{where}: response enum values added: {', '.join(map(str, added))} (clients with exhaustive matching may fail)"))


def normalize_path(path):
    return re.sub(r"\{[^}]*\}", "{}", path)


def operations(doc):
    ops = {}
    for path, item in (doc.get("paths") or {}).items():
        item = resolve(doc, item)
        shared = item.get("parameters", [])
        for method in METHODS:
            if isinstance(item.get(method), dict):
                ops[(normalize_path(path), method)] = (path, item[method], shared)
    return ops


def parameters(doc, shared, op):
    params = {}
    for p in list(shared) + list(op.get("parameters", [])):
        p = resolve(doc, p)
        if "name" in p and "in" in p:
            params[(p["in"], p["name"].lower() if p["in"] == "header" else p["name"])] = p
    return params


def security_alternatives(doc, op):
    reqs = op.get("security", doc.get("security", []))
    alts = []
    for req in reqs or []:
        alt = set()
        for scheme, scopes in (req or {}).items():
            alt.add(scheme)
            alt.update(f"{scheme}:{s}" for s in scopes or [])
        alts.append(frozenset(alt))
    return alts or [frozenset()]


def compare_security(old_doc, new_doc, old_op, new_op, label, out):
    old_alts = security_alternatives(old_doc, old_op)
    new_alts = security_alternatives(new_doc, new_op)
    for alt in old_alts:
        if not any(n <= alt for n in new_alts):
            shown = ", ".join(sorted(alt)) or "no auth"
            out.append((BREAKING, f"{label}: security tightened, clients using [{shown}] are no longer accepted"))


def compare_media(old_doc, new_doc, old_content, new_content, where, direction, out):
    old_content = old_content or {}
    new_content = new_content or {}
    for media in sorted(old_content):
        if media not in new_content:
            out.append((BREAKING, f"{where}: media type {media} removed"))
            continue
        old_schema = (old_content[media] or {}).get("schema")
        new_schema = (new_content[media] or {}).get("schema")
        if isinstance(old_schema, dict) and isinstance(new_schema, dict):
            compare_schema(old_doc, new_doc, old_schema, new_schema, f"{where} {media}", direction, out)


def compare_operation(old_doc, new_doc, old_entry, new_entry, label, out):
    _, old_op, old_shared = old_entry
    _, new_op, new_shared = new_entry

    old_params = parameters(old_doc, old_shared, old_op)
    new_params = parameters(new_doc, new_shared, new_op)
    for key, p in sorted(new_params.items()):
        where = f"{label} {key[0]} parameter '{key[1]}'"
        old_p = old_params.get(key)
        if old_p is None:
            if p.get("required"):
                out.append((BREAKING, f"{where}: new required parameter"))
            continue
        if p.get("required") and not old_p.get("required"):
            out.append((BREAKING, f"{where}: parameter became required"))
        if isinstance(old_p.get("schema"), dict) and isinstance(p.get("schema"), dict):
            compare_schema(old_doc, new_doc, old_p["schema"], p["schema"], where, REQUEST, out)
    for key in sorted(set(old_params) - set(new_params)):
        if key[0] != "path":
            out.append((WARNING, f"{label} {key[0]} parameter '{key[1]}': parameter removed"))

    old_body = resolve(old_doc, old_op.get("requestBody", {}))
    new_body = resolve(new_doc, new_op.get("requestBody", {}))
    if new_body.get("required") and not old_body.get("required"):
        out.append((BREAKING, f"{label} request body: became required"))
    compare_media(old_doc, new_doc, old_body.get("content"), new_body.get("content"), f"{label} request body", REQUEST, out)

    old_responses = old_op.get("responses", {}) or {}
    new_responses = new_op.get("responses", {}) or {}
    for code in sorted(old_responses, key=str):
        where = f"{label} response {code}"
        if code not in new_responses:
            if str(code).startswith("2"):
                out.append((BREAKING, f"{where}: success response removed"))
            continue
        old_resp = resolve(old_doc, old_responses[code])
        new_resp = resolve(new_doc, new_responses[code])
        compare_media(old_doc, new_doc, old_resp.get("content"), new_resp.get("content"), where, RESPONSE, out)

    compare_security(old_doc, new_doc, old_op, new_op, label, out)


def diff(old_doc, new_doc):
    out = []
    old_ops = operations(old_doc)
    new_ops = operations(new_doc)
    for key in sorted(old_ops):
        label = f"{key[1].upper()} {old_ops[key][0]}"
        if key not in new_ops:
            out.append((BREAKING, f"{label}: operation removed"))
            continue
        compare_operation(old_doc, new_doc, old_ops[key], new_ops[key], label, out)
        if new_ops[key][1].get("deprecated") and not old_ops[key][1].get("deprecated"):
            out.append((WARNING, f"{label}: operation deprecated"))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", help="older OpenAPI 3 file (JSON or YAML)")
    parser.add_argument("revision", help="newer OpenAPI 3 file (JSON or YAML)")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    parser.add_argument("--fail-on-warning", action="store_true", help="exit 1 on warnings too")
    args = parser.parse_args(argv)
    try:
        findings = diff(load(args.base), load(args.revision))
    except LoadError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps([{"level": level, "message": msg} for level, msg in findings], indent=2))
    elif not findings:
        print("No breaking changes found.")
    else:
        for level, msg in findings:
            print(f"{level}: {msg}")
    levels = {BREAKING, WARNING} if args.fail_on_warning else {BREAKING}
    return 1 if any(level in levels for level, _ in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
