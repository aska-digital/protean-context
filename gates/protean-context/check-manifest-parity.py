#!/usr/bin/env python3
"""check-manifest-parity.py - gate 1 of build/verify-all.py.

Proves that the contract line and the descriptor agree everywhere they are
carried, so no carrier can drift alone:

  * README.md line 1 is the authority;
  * protean-ingredient.json `contract` equals it byte for byte;
  * the skill carrier (skills/protean-context/SKILL.md frontmatter
    `description`) equals it;
  * the composer post-install gate carrier
    (gates/protean-context/check-post-install.py `CONTRACT_LINE`) equals it;
  * the descriptor's `installTargets` equals its `payload`;
  * install.sh declares the same payload;
  * every gate script named by the descriptor exists in this tree;
  * every install target exists as a directory.

The contract sentence is the one published in the locked wording record
(architecture decision D2 of the protean-context lock (2026-09-22)).

Usage: python3 gates/protean-context/check-manifest-parity.py [repo-root]
Exit: 0 pass; 1 violation; 2 missing source data.
"""

import json
import os
import re
import sys

GATE = "check-manifest-parity.py"
DESCRIPTOR = "protean-ingredient.json"
README = "README.md"
SKILL = "skills/protean-context/SKILL.md"
POST_INSTALL = "gates/protean-context/check-post-install.py"
INSTALLER = "install.sh"
CONTRACT_LINE_NAME = "CONTRACT_LINE"
DESCRIPTION_RE = re.compile(r'^description:\s*(.+?)\s*$', re.MULTILINE)
CONSTANT_RE = re.compile(r'^%s\s*=\s*"(.*)"\s*$' % CONTRACT_LINE_NAME, re.MULTILINE)
PAYLOAD_RE = re.compile(r'^PAYLOAD=\((.*?)\)', re.MULTILINE | re.DOTALL)


def read_lines(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().splitlines()


def main(argv):
    root = argv[1] if len(argv) > 1 else "."
    root = os.path.abspath(root)
    problems = []

    readme_path = os.path.join(root, README)
    descriptor_path = os.path.join(root, DESCRIPTOR)
    if not os.path.isfile(readme_path):
        sys.stderr.write("MISSING: %s\n" % README)
        return 2
    if not os.path.isfile(descriptor_path):
        sys.stderr.write("MISSING: %s\n" % DESCRIPTOR)
        return 2

    contract = read_lines(readme_path)[0]
    try:
        with open(descriptor_path, "r", encoding="utf-8") as handle:
            descriptor = json.load(handle)
    except ValueError as exc:
        print("FAIL: %s is not valid JSON (%s)" % (DESCRIPTOR, exc))
        return 1

    if descriptor.get("contract") != contract:
        problems.append("%s: `contract` is not byte-identical to README line 1"
                        % DESCRIPTOR)

    carriers = [(README + " line 1", contract),
                (DESCRIPTOR + " contract", descriptor.get("contract"))]
    skill_path = os.path.join(root, SKILL)
    if not os.path.isfile(skill_path):
        problems.append("%s: carrier file is missing" % SKILL)
    else:
        with open(skill_path, "r", encoding="utf-8") as handle:
            match = DESCRIPTION_RE.search(handle.read())
        carriers.append((SKILL + " description", match.group(1) if match else None))
    gate_path = os.path.join(root, POST_INSTALL)
    if not os.path.isfile(gate_path):
        problems.append("%s: carrier file is missing" % POST_INSTALL)
    else:
        with open(gate_path, "r", encoding="utf-8") as handle:
            match = CONSTANT_RE.search(handle.read())
        carriers.append((POST_INSTALL + " " + CONTRACT_LINE_NAME,
                         match.group(1) if match else None))
    for label, value in carriers[1:]:
        if value != contract:
            problems.append("%s: does not carry the contract line byte for byte"
                            % label)

    payload = descriptor.get("payload")
    targets = descriptor.get("installTargets")
    if not isinstance(payload, list) or not isinstance(targets, list):
        problems.append("%s: payload and installTargets must both be lists"
                        % DESCRIPTOR)
    else:
        if targets != payload:
            problems.append("%s: installTargets differs from payload" % DESCRIPTOR)
        if len(set(targets)) != len(targets):
            problems.append("%s: an install target is declared twice" % DESCRIPTOR)
        for rel in targets:
            if not os.path.isdir(os.path.join(root, rel)):
                problems.append("%s: install target is not a directory here: %s"
                                % (DESCRIPTOR, rel))
        if os.path.isfile(os.path.join(root, INSTALLER)):
            with open(os.path.join(root, INSTALLER), "r", encoding="utf-8") as handle:
                match = PAYLOAD_RE.search(handle.read())
            declared = []
            if match:
                declared = [item.strip().strip('"') for item in match.group(1).split()
                            if item.strip()]
            if declared != list(targets):
                problems.append("%s: declared PAYLOAD differs from the descriptor's "
                                "installTargets" % INSTALLER)
        else:
            problems.append("%s: installer is missing" % INSTALLER)

    for gate in descriptor.get("gates") or []:
        command = gate.get("cmd") or ""
        for token in command.split():
            if token.endswith(".py") or token.endswith(".sh"):
                if not os.path.isfile(os.path.join(root, token)):
                    problems.append("%s: declared gate script is missing: %s"
                                    % (DESCRIPTOR, token))
                break

    if problems:
        print("FAIL: %s" % GATE)
        for problem in problems:
            print("  " + problem)
        return 1
    print("check-manifest-parity: PASS")
    print("  contract carriers agree: %d" % len(carriers))
    print("  install targets: %d" % len(targets or []))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
