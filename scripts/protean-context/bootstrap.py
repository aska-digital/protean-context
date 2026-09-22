#!/usr/bin/env python3
"""bootstrap.py - the protean-context scaffold CLI.

Commands: `plan`, `init`, `verify`, `ingest`, `remove`. Stdlib only, no
network, no daemon. Every command requires an explicit --target; there is no
hidden default, because this CLI writes user-owned files.

Exit codes follow the kit 0 to 6 convention:

  0 ok
  1 usage, bad --name, reserved name
  2 schema, manifest, or registry invalid; downgrade refused
  3 adapter missing or unimportable; missing prerequisite
  4 hash mismatch, conflict on a scaffold file, migration would edit user content
  5 write failure (permissions, full disk)
  6 verify found a failing or skipping check

Errors go to stderr, the summary goes to stdout, and no partial success ever
exits 0.

--offline is accepted on every command and is truthful by construction: no
shipped code imports a network module (gate 7 proves it) and no code path
opens a socket (test 9 proves it). require_network() below is the hook that
would refuse any future network path; nothing in v0.1.0 calls it.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import pc_common
import pc_ingest
import pc_init
import pc_remove
import pc_verify

TARGET_HELP = ("the directory that receives the scaffolds (required; no hidden "
               "default)")
NAME_HELP = ("name of an Eldunari to ensure; repeat the flag to ensure several "
             "(required on plan and init)")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="bootstrap.py",
        description="Initialize, verify, ingest into, or remove a user-owned "
                    "Eldunarya and Arif scaffold (stdlib only, offline).",
        epilog="exit codes: 0 ok, 1 usage, 2 invalid input, 3 missing dependency, "
               "4 integrity, 5 write failure, 6 verification failure.")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    plan = subparsers.add_parser(
        "plan", help="print the writes init would perform and write nothing",
        description="plan is init --dry-run as a named command: it classifies "
                    "every planned write and writes nothing.")
    init = subparsers.add_parser(
        "init", help="ensure the Eldunarya and Arif scaffolds exist under --target",
        description="Ensure-exist per file: absent files are created, identical "
                    "files are reported unchanged, different files are never "
                    "overwritten. A second init with the same arguments writes "
                    "nothing and exits 0.")
    verify = subparsers.add_parser(
        "verify", help="check an initialized target against the scaffold contract",
        description="Run the target checks (receipt, registry pointers, Arif "
                    "store, record references). Exits 6 when any check fails.")
    ingest = subparsers.add_parser(
        "ingest", help="run one adapter passed by path and write its records",
        description="Import exactly the adapter file passed with --adapter, "
                    "validate every record it yields (all or nothing), and write "
                    "records and blobs under --target/arif/ only.")
    remove = subparsers.add_parser(
        "remove", help="delete exactly the paths the init receipt lists",
        description="Deletes receipt-listed paths whose hash still matches; a "
                    "user-modified path is skipped and reported, unlisted files "
                    "are never touched, and directories are removed only when "
                    "empty.")

    for sub in (plan, init, verify, ingest, remove):
        sub.add_argument("--target", required=True, help=TARGET_HELP)
        sub.add_argument("--dry-run", action="store_true",
                         help="print the plan and write nothing")
        sub.add_argument("--offline", action="store_true",
                         help="refuse any code path that would need network "
                              "(none exists in this release)")
    for sub in (plan, init):
        sub.add_argument("--name", action="append", default=[], help=NAME_HELP)
    ingest.add_argument("--adapter", required=True,
                        help="path to the adapter module you implement")
    ingest.add_argument("--source", required=True,
                        help="path the adapter's collect(source) receives; the "
                             "only tree this command reads")
    return parser


def offline_note(offline):
    if offline:
        pc_common.out("network: none (offline requested; no network path exists)")


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return pc_common.EXIT_USAGE
    target = os.path.abspath(os.path.expanduser(args.target))
    offline_note(args.offline)
    try:
        if args.command == "plan":
            return pc_init.run(target, args.name, dry_run=True)
        if args.command == "init":
            return pc_init.run(target, args.name, dry_run=args.dry_run)
        if args.command == "verify":
            return pc_verify.run(target)
        if args.command == "ingest":
            return pc_ingest.run(target, args.adapter, args.source,
                                 dry_run=args.dry_run)
        if args.command == "remove":
            return pc_remove.run(target, dry_run=args.dry_run)
    except pc_common.BootstrapError as exc:
        pc_common.err(exc.message)
        return exc.code
    except OSError as exc:
        pc_common.err("write failure: %s" % exc)
        return pc_common.EXIT_INSTALL
    parser.print_help()
    return pc_common.EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
