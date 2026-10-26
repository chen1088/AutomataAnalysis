#!/usr/bin/env python3
"""Reject oversized staged Git blobs without inspecting working-tree copies."""
import argparse
import subprocess
import sys


def git(*args, data=None):
    return subprocess.run(["git", *args], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-bytes", type=int, default=1024 * 1024,
                        help="maximum size of each added/modified blob (default: 1 MiB)")
    args = parser.parse_args()
    if args.max_bytes < 1:
        parser.error("--max-bytes must be positive")
    changed = set(git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split(b"\0"))
    entries = []
    for record in git("ls-files", "--stage", "-z").split(b"\0"):
        if not record:
            continue
        metadata, path = record.split(b"\t", 1)
        _, oid, stage = metadata.split()
        if stage != b"0":
            raise ValueError("resolve unmerged index entries before committing")
        if path in changed:
            entries.append((path, oid))
    if not entries:
        print("No added or modified files staged.")
        return 0
    sizes = git("cat-file", "--batch-check=%(objectsize)",
                data=b"\n".join(oid for _, oid in entries) + b"\n").splitlines()
    blobs = sorted(((int(size), path.decode("utf-8", errors="replace"))
                    for (path, _), size in zip(entries, sizes)), reverse=True)
    print(f"{len(blobs)} staged files; {sum(size for size, _ in blobs):,} bytes total.")
    for size, path in blobs[:5]:
        print(f"  {size:>10,}  {path}")
    oversized = [(size, path) for size, path in blobs if size > args.max_bytes]
    for size, path in oversized:
        print(f"Too large ({size:,} > {args.max_bytes:,} bytes): {path}", file=sys.stderr)
    return 1 if oversized else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (subprocess.CalledProcessError, ValueError) as error:
        print(error, file=sys.stderr)
        sys.exit(2)
