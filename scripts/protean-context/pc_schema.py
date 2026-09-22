"""Minimal required-key and type validator for the scaffold's four schemas.

Stdlib only, fail closed. Supported keywords: type (string or list), required,
properties, additionalProperties, items, enum, const, minimum, maximum. That
subset is enough for the four fixed schema documents; full JSON-Schema tooling
would need a non-stdlib validator.

Every problem is returned as a string; an empty list means the document is
valid. Callers decide the exit code (a document that does not validate is
exit 2).
"""

import json
import os

from pc_common import EXIT_SCHEMA, BootstrapError, fail

TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def load_json(path, label=None):
    """Parse one JSON file; a missing or unparseable file is exit 2."""
    name = label or path
    if not os.path.isfile(path):
        fail(EXIT_SCHEMA, "invalid input: %s is missing" % name)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except ValueError as exc:
        fail(EXIT_SCHEMA, "invalid input: %s is not valid JSON (%s)" % (name, exc))
    except OSError as exc:
        fail(EXIT_SCHEMA, "invalid input: %s is unreadable (%s)" % (name, exc))


def _type_problems(value, expected):
    if isinstance(expected, list):
        names = ", ".join(str(item) for item in expected)
        if not any(_matches(value, item) for item in expected):
            return ["expected one of [%s], found %s" % (names, _found(value))]
        return []
    if not _matches(value, expected):
        return ["expected %s, found %s" % (expected, _found(value))]
    return []


def _matches(value, expected):
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected not in TYPE_MAP:
        return True
    if expected == "null":
        return value is None
    return isinstance(value, TYPE_MAP[expected])


def _found(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def validate(value, schema, path=""):
    """Validate value against schema; return a list of problem strings."""
    where = path or "<root>"
    problems = []
    if not isinstance(schema, dict):
        return ["%s: schema fragment is not an object" % where]

    if "const" in schema and value != schema["const"]:
        problems.append("%s: expected the constant %r" % (where, schema["const"]))
        return problems

    expected = schema.get("type")
    if expected is not None:
        type_problems = _type_problems(value, expected)
        if type_problems:
            return ["%s: %s" % (where, item) for item in type_problems]

    if isinstance(value, str) and "pattern" in schema:
        import re
        if re.search(schema["pattern"], value) is None:
            problems.append("%s: does not match pattern %s" % (where, schema["pattern"]))

    if isinstance(value, bool):
        return problems

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            problems.append("%s: %r is below the minimum %r"
                            % (where, value, schema["minimum"]))
        if "maximum" in schema and value > schema["maximum"]:
            problems.append("%s: %r is above the maximum %r"
                            % (where, value, schema["maximum"]))
        return problems

    if isinstance(value, list):
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value):
                problems.extend(validate(item, items, "%s[%d]" % (where, index)))
        return problems

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                problems.append("%s: required field %r is missing" % (where, key))
        properties = schema.get("properties", {})
        for key in sorted(value):
            if key in properties:
                problems.extend(validate(value[key], properties[key],
                                         "%s.%s" % (where, key)))
            elif schema.get("additionalProperties") is False:
                problems.append("%s: field %r is not part of the schema" % (where, key))
        if "enum" in schema and value not in schema["enum"]:
            problems.append("%s: value is not one of the declared enum values" % where)
    return problems


def load_schema_document(path):
    """Load a shipped schema document and check its two identity fields."""
    document = load_json(path)
    if not isinstance(document, dict):
        fail(EXIT_SCHEMA, "invalid schema document: %s is not an object" % path)
    name = document.get("schema")
    version = document.get("schemaVersion")
    if not isinstance(name, str) or not name:
        fail(EXIT_SCHEMA, "invalid schema document: %s has no string 'schema'" % path)
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        fail(EXIT_SCHEMA, "invalid schema document: %s has no positive 'schemaVersion'"
             % path)
    problems = validate(document, {"type": "object",
                                   "required": ["schema", "schemaVersion"]},
                        os.path.basename(path))
    if problems:
        raise BootstrapError(EXIT_SCHEMA, "; ".join(problems))
    return document
