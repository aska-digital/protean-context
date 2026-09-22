#!/usr/bin/env python3
"""Step 9: no live-state reads, write confinement, and no network activity.

The CLI runs in process under a `sys.addaudithook` sandbox with HOME,
HERMES_HOME, and XDG_CACHE_HOME pointed at a canary tree. The test asserts:

  * no `open` event touches a path inside the canary tree (so no live state is
    read even when the environment points at one);
  * every write-mode `open` event stays inside `--target`;
  * no socket event occurs at all, which is what makes `--offline` truthful;
  * the sandbox really saw activity (a positive control), so the checks above
    cannot pass by doing nothing.
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pc_support

EVENTS = []
CANARY_FILES = (
    ("profiles/canary/SOUL.md", "canary profile identity: synthetic\n"),
    ("profiles/canary/config.yaml", "canary: true\n"),
    ("profiles/canary/memories/MEMORY.md", "canary memory: synthetic\n"),
    ("profiles/canary/skills/example/SKILL.md", "canary skill: synthetic\n"),
)
WRITE_MODES = ("w", "a", "x", "+")


def audit(event, args):
    if event == "open":
        EVENTS.append(("open", str(args[0]), str(args[1])))
    elif event.startswith("socket.") or event in ("socket.connect", "socket.getaddrinfo"):
        EVENTS.append(("socket", event, ""))


def build_canary(root):
    home = os.path.join(root, "canary-home")
    for rel, text in CANARY_FILES:
        path = os.path.join(home, ".hermes", rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
    return home


def is_write(mode):
    return any(marker in mode for marker in WRITE_MODES)


class TestNoLiveState(unittest.TestCase):
    def test_sandbox_reads_no_live_state_and_writes_only_under_target(self):
        scripts = pc_support.SCRIPTS
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        import bootstrap

        with tempfile.TemporaryDirectory(prefix="no-live-state-") as work:
            home = build_canary(work)
            target = os.path.join(work, "created")
            os.environ["HOME"] = home
            os.environ["HERMES_HOME"] = os.path.join(home, ".hermes")
            os.environ["XDG_CACHE_HOME"] = os.path.join(home, ".cache")

            canary_paths = []
            for base, _dirs, files in os.walk(home):
                for name in files:
                    canary_paths.append(os.path.join(base, name))
            self.assertTrue(canary_paths, "the canary tree must exist to be probed")

            del EVENTS[:]
            sys.addaudithook(audit)
            codes = [
                bootstrap.main(["plan", "--target", target, "--name", "demo",
                                "--offline"]),
                bootstrap.main(["init", "--target", target, "--name", "demo",
                                "--offline"]),
                bootstrap.main(["init", "--target", target, "--name", "demo",
                                "--offline"]),
                bootstrap.main(["verify", "--target", target, "--offline"]),
                bootstrap.main(["ingest", "--target", target, "--adapter",
                                pc_support.ADAPTER, "--source", pc_support.SOURCE,
                                "--offline"]),
                bootstrap.main(["verify", "--target", target, "--offline"]),
                bootstrap.main(["remove", "--target", target, "--offline"]),
            ]
            self.assertEqual(codes, [0, 0, 0, 0, 0, 0, 0], "every command must exit 0")

            canary_hits = []
            outside_writes = []
            sockets = []
            writes_inside = 0
            for event, path, mode in EVENTS:
                if event == "socket":
                    sockets.append(path)
                    continue
                if any(path.startswith(root) for root in canary_paths):
                    canary_hits.append((path, mode))
                elif any(path == root or path.startswith(root + os.sep)
                         for root in canary_paths):
                    canary_hits.append((path, mode))
                if is_write(mode):
                    if path.startswith(target + os.sep):
                        writes_inside += 1
                    else:
                        outside_writes.append((path, mode))

            self.assertEqual([], canary_hits,
                             "the sandbox read inside the canary tree")
            self.assertEqual([], outside_writes,
                             "a write happened outside --target")
            self.assertEqual([], sockets, "a socket event happened")
            self.assertTrue(writes_inside > 0,
                            "positive control: the sandbox must observe writes "
                            "inside --target")

            for rel in (".protean-context-receipt.json", "arif/arif.json"):
                self.assertFalse(os.path.exists(os.path.join(target, rel)),
                                 "remove must have deleted %s" % rel)
            for rel, _text in CANARY_FILES:
                self.assertTrue(os.path.isfile(
                    os.path.join(home, ".hermes", rel)),
                    "the canary file must survive: %s" % rel)


if __name__ == "__main__":
    unittest.main()
