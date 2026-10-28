"""Plain, tested code: check the model's readings, group charges by merchant, find recurring ones and flag the ghosts."""
import csv
import datetime as dt
import re
import statistics

PROCESSORS = re.compile(r"^(PAYPAL \*|SQ \*|TST\* ?|SP \*|PP\*)", re.I)
CADENCES = [("weekly", 5, 9, 7, 3), ("monthly", 25, 35, 30, 7), ("annual", 350, 380, 365, 30)]  # name, lo, hi, step, grace


def fallback_key(desc):
    """Rule-only merchant key: drop processor prefix, then keep the leading alphabetic words."""
    s = PROCESSORS.sub("", desc.strip())
    words = []
    for w in re.split(r"[\s*#/.]+", s):
        if not w or any(c.isdigit() for c in w):
            break
        words.append(w)
    return " ".join(words[:2]).title() or desc.strip()[:12].title()


def check_reading(desc, reading):
    """Accept the model's merchant only if it is grounded in the line: its quote (delimiters stripped) is really in
    the line, and at least one merchant word (3+ letters) appears in the line. Otherwise use the rule-only key.
    Returns (merchant, status) where status is 'ok' or 'FIXED' (rule fallback used)."""
    q = (reading.get("quote") or "").replace("<<<", "").replace(">>>", "").strip()
    m = (reading.get("merchant") or "").strip()
    compact = re.sub(r"[^a-z]", "", desc.lower())
    if m and q and q.lower() in desc.lower():
        words = [w for w in re.findall(r"[a-z]+", m.lower()) if len(w) >= 3]
        if words and any(w in compact for w in words):
            return m, "ok"
    return fallback_key(desc), "FIXED"


def load_csv(path):
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            k = {c.lower(): c for c in r}
            amt = float(r[k["amount"]].replace("$", "").replace(",", ""))
            rows.append({"date": dt.date.fromisoformat(r[k["date"]][:10]), "desc": r[k["description"]].strip(), "amount": amt})
    return rows


def _same(a, b):
    return abs(a - b) <= max(0.02 * max(a, b), 0.01)


SUFFIXES = re.compile(r"\b(inc|llc|ltd|corp|co|com)\b\.?", re.I)


def canon(name):
    """'Adobe Inc.' -> 'adobe', 'YouTube Premium' -> 'youtubepremium'."""
    return re.sub(r"[^a-z]", "", SUFFIXES.sub("", name.lower())) or re.sub(r"[^a-z]", "", name.lower())


def merge_names(names):
    """Map each merchant name to one group label. Names whose canonical key starts with another's (4+ letters)
    join that group: 'Dropbox Plus' joins 'Dropbox', 'Adobe Inc.' joins 'Adobe'. Label = shortest name."""
    keys = sorted({canon(n) for n in names}, key=len)
    root = {}
    for k in keys:
        root[k] = next((r for r in keys if len(r) >= 4 and len(r) < len(k) and k.startswith(r) and root.get(r) == r), k)
    label = {}
    for n in sorted(names, key=len):
        label.setdefault(root[canon(n)], n)
    return {n: label[root[canon(n)]] for n in names}


def find_ghosts(rows, merchant_of, as_of):
    """rows: outgoing charges are negative amounts. merchant_of: desc -> merchant name. Returns a list of findings."""
    group_of = merge_names(set(merchant_of.values()))
    groups = {}
    for r in rows:
        if r["amount"] > 0:
            continue
        groups.setdefault(group_of[merchant_of[r["desc"]]], []).append((r["date"], -r["amount"], r["desc"]))
    out = []
    for merchant, ch in groups.items():
        ch.sort()
        trial = [c for c in ch if c[1] <= 1.0]
        paid = [c for c in ch if c[1] > 1.0]
        if len(paid) < 2:
            continue
        # double charges: same amount within 3 days -> keep the first for cadence
        doubles, clean = [], [paid[0]]
        for c in paid[1:]:
            if (c[0] - clean[-1][0]).days <= 3 and _same(c[1], clean[-1][1]):
                doubles.append(c)
            else:
                clean.append(c)
        gaps = [(b[0] - a[0]).days for a, b in zip(clean, clean[1:])]
        if not gaps:
            continue
        med = statistics.median(gaps)
        cad = next((c for c in CADENCES if c[1] <= med <= c[2]), None)
        if not cad:
            continue
        name, lo, hi, step, grace = cad
        if name != "annual" and len(clean) < 3:
            continue
        if sum(lo <= g <= hi for g in gaps) < 0.75 * len(gaps):
            continue
        first, last = clean[0][1], clean[-1][1]
        if sum(_same(c[1], first) or _same(c[1], last) for c in clean) < 0.8 * len(clean):
            continue  # amounts all over the place: shopping, not a subscription
        nxt = clean[-1][0] + dt.timedelta(days=step)
        active = (as_of - clean[-1][0]).days <= step + grace
        flags = []
        if last > first * 1.01:
            flags.append("price_up")
        if doubles:
            flags.append("double_charge")
        if trial and trial[-1][0] < clean[0][0] and (clean[0][0] - trial[-1][0]).days <= 45:
            flags.append("trial_converted")
        if name == "annual" and active and 0 <= (nxt - as_of).days <= 30:
            flags.append("renews_soon")
        per_year = last * {"weekly": 52, "monthly": 12, "annual": 1}[name]
        out.append({"merchant": merchant, "cadence": name, "active": active, "last_date": clean[-1][0].isoformat(),
                    "last_amount": round(last, 2), "first_amount": round(first, 2), "next_expected": nxt.isoformat() if active else "",
                    "per_year": round(per_year, 2) if active else 0.0, "count": len(clean), "flags": flags,
                    "extra_paid": round(sum(c[1] for c in doubles), 2)})
    out.sort(key=lambda f: (-f["active"], -f["per_year"]))
    return out


def report(findings, as_of):
    act = [f for f in findings if f["active"]]
    total = sum(f["per_year"] for f in act)
    lines = [f"# Ghost charges as of {as_of}", "",
             f"**{len(act)} recurring charges still active, ${total:,.2f} a year.**", "",
             "| Merchant | Every | Last charge | Per year | Next | Why look |", "|---|---|---|---:|---|---|"]
    why = {"price_up": "price went up", "double_charge": "charged twice", "trial_converted": "free trial turned paid",
           "renews_soon": "renews within 30 days"}
    for f in findings:
        w = ", ".join(why[x] for x in f["flags"]) or ("stopped" if not f["active"] else "")
        if f["flags"] and "price_up" in f["flags"]:
            w = w.replace("price went up", f"price went up ${f['first_amount']:.2f} → ${f['last_amount']:.2f}")
        lines.append(f"| {f['merchant']} | {f['cadence']} | {f['last_date']} ${f['last_amount']:.2f} | "
                     f"{'$%.2f' % f['per_year'] if f['active'] else '-'} | {f['next_expected'] or '-'} | {w} |")
    return "\n".join(lines) + "\n"
