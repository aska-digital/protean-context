#!/usr/bin/env python3
# SYNTHETIC TEST DATA - fixture adapter for the ingest tests; it is test input,
# not a shipped adapter, and it reads only the --source tree it is given.
"""Synthetic Arif ingestion adapter fixture.

One record per text file under `source`, named `demo-record-<n>`, with the
checksum and byte count of that file. The scaffold never ships an adapter; this
one exists so the ingest path can be exercised offline and deterministically.
"""

import hashlib
import os

ADAPTER_NAME = "synthetic-adapter"
ADAPTER_VERSION = "0.0.1"
INGESTED_AT = "1970-01-01T00:00:00Z"
PATTERNS = (".txt",)


def collect(source):
    """Yield one arif-record-v1 shaped record per text file under source."""
    root = source if os.path.isdir(source) else os.path.dirname(source)
    names = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(dirs)
        for name in sorted(files):
            if name.endswith(PATTERNS):
                names.append(os.path.relpath(os.path.join(base, name), root))
    index = 0
    for name in sorted(names):
        with open(os.path.join(root, name), "rb") as handle:
            data = handle.read()
        index += 1
        digest = hashlib.sha256(data).hexdigest()
        yield {
            "schema": "arif-record-v1",
            "schemaVersion": 1,
            "id": "demo-record-%d" % index,
            "source": {
                "title": "SYNTHETIC TEST DATA %s" % os.path.basename(name),
                "locator": name,
                "kind": "document",
                "retrieved": None,
            },
            "content": {
                "ref": "content/%s" % digest,
                "mediaType": "text/plain",
                "checksum": digest,
                "bytes": len(data),
            },
            "metadata": {
                "topics": ["synthetic"],
                "tags": ["SYNTHETIC TEST DATA"],
                "language": "en",
                "license": None,
            },
            "provenance": {
                "adapter": ADAPTER_NAME,
                "ingestedAt": INGESTED_AT,
                "method": "collect",
            },
            "embedding": None,
        }
