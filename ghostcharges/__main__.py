"""python3 -m ghostcharges statement.csv [--as-of YYYY-MM-DD] [--server URL] [--readings readings.json]"""
import argparse
import datetime as dt
import json
import os

from . import extract, find


def main():
    p = argparse.ArgumentParser(prog="ghostcharges")
    p.add_argument("csv")
    p.add_argument("--as-of", default=dt.date.today().isoformat())
    p.add_argument("--server", default=os.environ.get("GHOST_SERVER", "http://127.0.0.1:8080"))
    p.add_argument("--readings", help="reuse saved model readings (JSON) instead of calling the model")
    p.add_argument("--out", default="ghost-charges-out")
    a = p.parse_args()
    rows = find.load_csv(a.csv)
    readings = json.load(open(a.readings)) if a.readings else {}
    for d in sorted({r["desc"] for r in rows if r["amount"] <= 0}):
        if d not in readings:
            readings[d], secs = extract.read_descriptor(d, a.server)
            print(f"read {secs:>5}s  {d[:40]:<40} -> {readings[d]['merchant']}")
    merchant_of, audit = {}, []
    for d, rd in readings.items():
        merchant_of[d], st = find.check_reading(d, rd)
        audit.append(f"{st:5} {d} -> {merchant_of[d]} (model: {rd.get('merchant')!r}, quote {rd.get('quote')!r})")
    as_of = dt.date.fromisoformat(a.as_of)
    fs = find.find_ghosts(rows, merchant_of, as_of)
    os.makedirs(a.out, exist_ok=True)
    json.dump(readings, open(os.path.join(a.out, "readings.json"), "w"), indent=1, sort_keys=True)
    json.dump(fs, open(os.path.join(a.out, "findings.json"), "w"), indent=1)
    open(os.path.join(a.out, "audit.txt"), "w").write("\n".join(sorted(audit)) + "\n")
    rep = find.report(fs, as_of)
    open(os.path.join(a.out, "ghosts.md"), "w").write(rep)
    print(rep)


if __name__ == "__main__":
    main()
