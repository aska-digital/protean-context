"""init and plan: ensure-exist creation of the two empty scaffolds.

Semantics (locked, decisions D5.1 to D5.3):

* every command takes an explicit --target; there is no hidden default;
* --dry-run prints the same plan and writes nothing; `plan` is `init --dry-run`;
* ensure-exist per file: absent -> create, byte-identical -> unchanged,
  different -> never overwritten. A scaffold-owned file whose content still
  matches its init-receipt hash is replaced after a backup; anything else is
  reported and skipped;
* a second init with the same arguments performs zero writes and exits 0;
* the whole plan is classified before the first write, and a refused downgrade
  (exit 2) or a failed migration (exit 4) aborts the run with nothing written.
  Reported conflicts do not stop the remaining writes, but they make the run
  exit 4: a run that could not place every planned file is never exit 0.

The registry (`eldunarya/eldunarya.json`) is the one document init merges
rather than skips, because appending an entry for a requested name is the
locked ensure-exist behavior (decision D3.4). User edits elsewhere in that
document are preserved.
"""

import json
import os

from pc_common import (EXIT_INSTALL, EXIT_INTEGRITY, EXIT_SCHEMA, EXIT_USAGE,
                       check_name, fail, iter_rel_files, out, read_text,
                       sha256_bytes, sha256_file, write_text)
from pc_migrate import apply_chain, backup_file, document_version
from pc_paths import (ARIF_ADAPTERS_README_REL, ARIF_EMPTY_DIRS, ARIF_DIR,
                      ARIF_MANIFEST_REL, ELDUNARI_HOME, ELDUNARYA_DIR,
                      PLACEHOLDER_NAME, REGISTRY_REL, arif_manifest_template,
                      eldunari_path, modules_path, modules_readme_path,
                      registry_entry_path, registry_entry_router,
                      registry_template, router_path, schema_document,
                      template_text)
from pc_receipt import (RECEIPT_NAME, build_receipt, created_hashes, current_hashes,
                        read_receipt, render_receipt, write_receipt)
from pc_schema import load_json, validate

CLASS_CREATE = "create"
CLASS_UNCHANGED = "unchanged"
CLASS_REPLACE = "replace"
CLASS_CONFLICT = "conflict"

REGISTRY_SCHEMA = "eldunarya-v1"
ARIF_SCHEMA = "arif-store-v1"


def render_json(document):
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def check_document(document, schema_name, label):
    """Validate one document against a shipped schema document; bad is exit 2."""
    problems = validate(document, schema_document(schema_name), label)
    if problems:
        fail(EXIT_SCHEMA, "invalid input: %s" % "; ".join(problems))
    return document


def registry_entries(document, label):
    entries = []
    for index, entry in enumerate(document.get("eldunari") or []):
        if not isinstance(entry, dict):
            fail(EXIT_SCHEMA, "invalid registry: %s eldunari[%d] is not an object"
                 % (label, index))
        entries.append({"name": entry.get("name"), "path": entry.get("path"),
                        "router": entry.get("router")})
    return entries


def versioned_document(target, rel, schema_name, template_document, migrations):
    """Apply the version rules to one JSON document and return its document.

    A target version newer than the scaffold's is refused (exit 2). An older
    version is migrated forward-only (exit 4 when a rule is missing or not
    additive). Equal versions return the target document unchanged.
    """
    path = os.path.join(target, rel)
    template_version = document_version(template_document, "template %s" % rel)
    if not os.path.isfile(path):
        return json.loads(render_json(template_document))
    document = check_document(load_json(path, rel), schema_name, rel)
    current_version = document_version(document, rel)
    if current_version > template_version:
        fail(EXIT_SCHEMA,
             "downgrade refused: %s is at schemaVersion %d, the scaffold is at %d"
             % (rel, current_version, template_version))
    if current_version < template_version:
        document, applied = apply_chain(document, schema_name, current_version,
                                        template_version, path=rel)
        migrations.extend(applied)
    return document


def registry_document(target, names, migrations):
    """The registry document the target should hold, with every name ensured."""
    document = versioned_document(target, REGISTRY_REL, REGISTRY_SCHEMA,
                                  registry_template(), migrations)
    document = check_document(document, REGISTRY_SCHEMA, REGISTRY_REL)
    entries = registry_entries(document, REGISTRY_REL)
    known = [entry["name"] for entry in entries]
    for name in names:
        if name in known:
            continue
        entries.append({"name": name, "path": registry_entry_path(name),
                        "router": registry_entry_router(name)})
        known.append(name)
    merged = dict(document)
    merged["eldunari"] = entries
    return merged


def desired_texts(target, names, migrations):
    """Every scaffold-owned file the target should hold, as {rel: text}."""
    texts = {REGISTRY_REL: render_json(registry_document(target, names, migrations))}
    for name in names:
        router = template_text("router").replace(PLACEHOLDER_NAME, name)
        if PLACEHOLDER_NAME in router:
            fail(EXIT_INTEGRITY,
                 "template placeholder %s survived materialization" % PLACEHOLDER_NAME)
        texts[router_path(name)] = router
        texts[modules_readme_path(name)] = template_text("modules_readme").replace(
            PLACEHOLDER_NAME, name)
    manifest = versioned_document(target, ARIF_MANIFEST_REL, ARIF_SCHEMA,
                                  arif_manifest_template(), migrations)
    manifest = check_document(manifest, ARIF_SCHEMA, ARIF_MANIFEST_REL)
    texts[ARIF_MANIFEST_REL] = render_json(manifest)
    texts[ARIF_ADAPTERS_README_REL] = template_text("arif_adapters_readme")
    return texts


def desired_directories(names):
    directories = [ELDUNARYA_DIR, ELDUNARI_HOME, ARIF_DIR, "arif/adapters"]
    for name in names:
        directories.append(eldunari_path(name))
        directories.append(modules_path(name))
    directories.extend(ARIF_EMPTY_DIRS)
    return sorted(set(directories))


def file_version(target, rel, text=None):
    """Version used for the backup directory name: the JSON schemaVersion, else 1."""
    if text is not None:
        try:
            document = json.loads(text)
        except ValueError:
            return 1
        if isinstance(document, dict):
            version = document.get("schemaVersion")
            if isinstance(version, int) and not isinstance(version, bool) and version > 0:
                return version
        return 1
    path = os.path.join(target, rel)
    if not os.path.isfile(path):
        return 1
    try:
        with open(path, "r", encoding="utf-8") as handle:
            document = json.loads(handle.read())
    except (ValueError, OSError):
        return 1
    if isinstance(document, dict):
        version = document.get("schemaVersion")
        if isinstance(version, int) and not isinstance(version, bool) and version > 0:
            return version
    return 1


def build_plan(target, names):
    """Classify every planned write without touching the filesystem."""
    migrations = []
    receipt_document = read_receipt(target)
    receipt_hashes = created_hashes(receipt_document) if receipt_document else {}
    current = current_hashes(target) if os.path.isdir(target) else {}
    texts = desired_texts(target, names, migrations)
    actions = []
    conflicts = []
    for rel in sorted(texts):
        wanted = sha256_bytes(texts[rel].encode("utf-8"))
        note = ""
        if rel not in current:
            kind = CLASS_CREATE
        elif current[rel] == wanted:
            kind = CLASS_UNCHANGED
        elif rel == REGISTRY_REL:
            kind, note = CLASS_REPLACE, "registry entry ensured"
        elif receipt_hashes.get(rel) == current[rel]:
            kind, note = CLASS_REPLACE, "scaffold-owned file updated"
        else:
            kind, note = CLASS_CONFLICT, "user-modified file kept as is"
        action = {"rel": rel, "kind": kind, "note": note, "text": texts[rel],
                  "sha256": wanted, "backup": None}
        if kind == CLASS_REPLACE:
            action["backup"] = (file_version(target, rel),
                                file_version(target, rel, texts[rel]))
        if kind == CLASS_CONFLICT:
            conflicts.append(rel)
        actions.append(action)
    return {"actions": actions, "conflicts": conflicts, "migrations": migrations,
            "directories": desired_directories(names), "texts": texts,
            "receipt_document": receipt_document, "receipt_hashes": receipt_hashes}


def apply_plan(target, plan):
    """Perform the planned writes; return a summary of what changed."""
    written, backups = [], []
    for rel in plan["directories"]:
        path = os.path.join(target, rel)
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as exc:
            fail(EXIT_INSTALL, "cannot create directory %s (%s)" % (rel, exc))
    for action in plan["actions"]:
        if action["kind"] not in (CLASS_CREATE, CLASS_REPLACE):
            continue
        destination = os.path.join(target, action["rel"])
        if action["kind"] == CLASS_REPLACE and action["backup"]:
            rel_backup = backup_file(target, action["rel"], action["backup"][0],
                                     action["backup"][1])
            if rel_backup:
                backups.append(rel_backup)
        write_text(destination, action["text"])
        written.append(action["rel"])
    created = {}
    for rel in sorted(iter_rel_files(target)):
        if rel == RECEIPT_NAME:
            continue
        if rel in written or rel in plan["receipt_hashes"]:
            created[rel] = sha256_file(os.path.join(target, rel))
    directories = set(plan["directories"])
    for rel in (plan["receipt_document"] or {}).get("directories") or []:
        if isinstance(rel, str) and os.path.isdir(os.path.join(target, rel)):
            directories.add(rel)
    document = build_receipt(created, sorted(directories), plan["migrations"])
    text = render_receipt(document)
    receipt_written = False
    current_receipt = os.path.join(target, RECEIPT_NAME)
    if not os.path.isfile(current_receipt) or read_text(current_receipt) != text:
        write_receipt(target, document)
        receipt_written = True
    return {"written": written, "backups": backups,
            "receipt_written": receipt_written}


def run(target, names, dry_run=False):
    """Run plan/init; return the process exit code."""
    if not names:
        fail(EXIT_USAGE, "init requires at least one --name (repeat the flag to "
                         "ensure several Eldunari)")
    unique = []
    for name in names:
        check_name(name)
        if name not in unique:
            unique.append(name)
    if os.path.exists(target) and not os.path.isdir(target):
        fail(EXIT_USAGE, "invalid --target: %s exists and is not a directory" % target)
    if not dry_run:
        try:
            os.makedirs(target, exist_ok=True)
        except OSError as exc:
            fail(EXIT_INSTALL, "cannot create --target: %s (%s)" % (target, exc))
    plan = build_plan(target, unique)
    out("target: %s" % target)
    out("command: %s" % ("plan (init --dry-run)" if dry_run else "init"))
    out("names: %s" % ", ".join(unique))
    for action in plan["actions"]:
        line = "%s%s: %s" % ("would " if dry_run else "", action["kind"], action["rel"])
        if action["note"]:
            line += "  (%s)" % action["note"]
        out(line)
    unchanged = sum(1 for a in plan["actions"] if a["kind"] == CLASS_UNCHANGED)
    created = sum(1 for a in plan["actions"] if a["kind"] == CLASS_CREATE)
    replaced = sum(1 for a in plan["actions"] if a["kind"] == CLASS_REPLACE)
    if dry_run:
        out("summary: create=%d replace=%d unchanged=%d conflict=%d migrations=%d"
            % (created, replaced, unchanged, len(plan["conflicts"]),
               len(plan["migrations"])))
        out("result: dry-run, no files written")
    else:
        result = apply_plan(target, plan)
        for rel in result["written"]:
            out("wrote: %s" % rel)
        for rel in result["backups"]:
            out("backup: %s" % rel)
        if result["receipt_written"]:
            out("wrote: %s" % RECEIPT_NAME)
        out("summary: create=%d replace=%d unchanged=%d conflict=%d migrations=%d"
            % (created, replaced, unchanged, len(plan["conflicts"]),
               len(plan["migrations"])))
        out("result: %s" % ("ok" if not plan["conflicts"]
                            else "conflicts reported, user-modified files untouched"))
    for rel in plan["conflicts"]:
        out("conflict: %s (user-modified, not overwritten)" % rel)
    if plan["conflicts"]:
        return EXIT_INTEGRITY
    return 0

