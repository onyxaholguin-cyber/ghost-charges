"""Score findings against a hand-made answer key: python3 eval/score.py bank.csv truth.json readings.json [--rules-only]"""
import datetime as dt
import json
import re
import sys

sys.path.insert(0, __import__("os").path.dirname(__file__) + "/..")
from ghostcharges import find  # noqa: E402


def key(s):
    return re.sub(r"[^a-z]", "", s.lower())


def score(csv_path, truth_path, readings_path, rules_only=False):
    truth = json.load(open(truth_path))
    readings = json.load(open(readings_path))
    rows = find.load_csv(csv_path)
    merchant_of = {}
    for d, rd in readings.items():
        merchant_of[d] = find.fallback_key(d) if rules_only else find.check_reading(d, rd)[0]
    fs = find.find_ghosts(rows, merchant_of, dt.date.fromisoformat(truth["as_of"]))
    right, used, notes = 0, set(), []
    for name, t in truth["subscriptions"].items():
        hits = [i for i, f in enumerate(fs) if key(name)[:5] in key(f["merchant"]) or key(f["merchant"])[:5] in key(name)]
        ok = (len(hits) == 1 and fs[hits[0]]["cadence"] == t["cadence"] and fs[hits[0]]["active"] == t["active"]
              and sorted(fs[hits[0]]["flags"]) == sorted(t["flags"]))
        right += ok
        used.update(hits)
        if not ok:
            notes.append(f"MISS {name}: found {[fs[i]['merchant'] + '/' + fs[i]['cadence'] for i in hits]}")
    extra = [f["merchant"] for i, f in enumerate(fs) if i not in used]
    return right, len(truth["subscriptions"]), extra, notes


if __name__ == "__main__":
    r, n, extra, notes = score(*sys.argv[1:4], rules_only="--rules-only" in sys.argv)
    print(f"{r}/{n} subscriptions exactly right (cadence, active, flags); {len(extra)} false alarms {extra}")
    print("\n".join(notes))
    sys.exit(0 if r == n and not extra else 1)
