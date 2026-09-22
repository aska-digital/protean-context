"""Repository, template, and target layout for the scaffold.

Source directories map 1:1 onto install targets, so this module resolves
everything relative to its own file: the same tree works in a checkout, in a
standalone `install.sh` target, and in a composer staging directory.

Two path bases exist and are kept apart on purpose:

* target-relative paths (`eldunarya/eldunari/...`) address files under the
  directory the user passed with --target;
* registry-relative paths (`eldunari/<name>`) are what the registry stores,
  because the registry describes the Eldunarya root it sits in.
"""

import os

from pc_common import EXIT_DEPENDENCY, fail, read_text
from pc_schema import load_json, load_schema_document

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
TEMPLATE_ROOT = os.path.join(REPO_ROOT, "templates", "protean-context")
SCHEMA_DIR = os.path.join(TEMPLATE_ROOT, "schema")

# Target-relative layout (architecture decisions D3.2, D3.4, D4.2).
ELDUNARYA_DIR = "eldunarya"
ELDUNARI_HOME = "eldunarya/eldunari"
REGISTRY_REL = "eldunarya/eldunarya.json"
ARIF_DIR = "arif"
ARIF_MANIFEST_REL = "arif/arif.json"
ARIF_ADAPTERS_README_REL = "arif/adapters/README.md"
ARIF_EMPTY_DIRS = ("arif/records", "arif/content", "arif/index")

TEMPLATES = {
    "registry": "eldunarya/eldunarya.json",
    "router": "eldunarya/eldunari/ROUTER.template.md",
    "modules_readme": "eldunarya/eldunari/modules/README.template.md",
    "arif_manifest": "arif/arif.json",
    "arif_adapters_readme": "arif/adapters/README.md",
}

SCHEMA_DOCUMENTS = {
    "eldunarya-v1": "eldunarya.schema.json",
    "eldunari-v1": "eldunari.schema.json",
    "arif-store-v1": "arif-store.schema.json",
    "arif-record-v1": "arif-record.schema.json",
}

PLACEHOLDER_NAME = "{ELDUNARI_NAME}"


def template_path(key):
    """Absolute path of one shipped template; missing input is exit 3."""
    if key not in TEMPLATES:
        fail(EXIT_DEPENDENCY, "unknown template key: %s" % key)
    path = os.path.join(TEMPLATE_ROOT, TEMPLATES[key])
    if not os.path.isfile(path):
        fail(EXIT_DEPENDENCY, "missing prerequisite: template %s is not present"
             % TEMPLATES[key])
    return path


def template_text(key):
    return read_text(template_path(key))


def schema_document(schema_name):
    """Load one shipped schema document by its schema name (exit 3 if absent)."""
    if schema_name not in SCHEMA_DOCUMENTS:
        fail(EXIT_DEPENDENCY, "unknown schema name: %s" % schema_name)
    path = os.path.join(SCHEMA_DIR, SCHEMA_DOCUMENTS[schema_name])
    if not os.path.isfile(path):
        fail(EXIT_DEPENDENCY, "missing prerequisite: schema %s is not present"
             % SCHEMA_DOCUMENTS[schema_name])
    return load_schema_document(path)


def registry_template():
    return load_json(template_path("registry"))


def arif_manifest_template():
    return load_json(template_path("arif_manifest"))


def registry_entry_path(name):
    """The registry-relative directory of one Eldunari."""
    return "eldunari/%s" % name


def registry_entry_router(name):
    """The registry-relative router path of one Eldunari."""
    return "%s/ROUTER.md" % registry_entry_path(name)


def eldunari_path(name):
    """The target-relative directory of one Eldunari."""
    return "%s/%s" % (ELDUNARI_HOME, name)


def router_path(name):
    return "%s/ROUTER.md" % eldunari_path(name)


def modules_path(name):
    return "%s/modules" % eldunari_path(name)


def modules_readme_path(name):
    return "%s/README.md" % modules_path(name)
