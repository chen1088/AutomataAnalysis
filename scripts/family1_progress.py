"""Read-only progress summary for an ordered exhaustive-search journal."""
import argparse
from collections import Counter
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("journal", type=Path)
parser.add_argument("--attained", type=int, required=True)
args = parser.parse_args()
statuses = Counter()
count = excluded = upper_unknown = at_least = 0
best_exact = 0
for line in args.journal.open(encoding="utf-8"):
    if not line.endswith("\n"):
        break  # The writer may still be committing the final line.
    data = json.loads(line)
    count += 1
    statuses[data["status"]] += 1
    upper = data["upper_bound"]
    excluded += upper is not None and upper < args.attained
    upper_unknown += upper is None
    at_least += data["lower_bound"] >= args.attained
    best_exact = max(best_exact, data["merge_length"] or 0)
print(json.dumps({"records_read": count, "statuses": statuses,
                  "excluded_by_verified_upper_below_attained": excluded,
                  "need_more_work_at_attained_threshold": count - excluded,
                  "unknown_upper": upper_unknown, "lower_at_least_attained": at_least,
                  "best_exact_in_journal": best_exact,
                  "note": "Progress only; does not independently check witnesses, lower proofs or coverage."}, indent=2))
