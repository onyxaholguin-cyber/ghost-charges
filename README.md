# Ghost Charges 👻

**Find the subscriptions still haunting your bank statement, on your own machine.**
Export a CSV from your bank. An open-weight model (Gemma 4 E2B, 2.8 GB, a CPU is enough) *reads* each messy statement line (`PAYPAL *SPOTIFYUSA 4029357733`, `SQ *IRONWORKS GYM 2841 AUSTIN TX`) and names the merchant. Plain, tested Python checks every name it gives, groups the charges, works out what repeats, and flags the ones worth a look.
Your bank history never leaves your computer.

```
7 recurring charges still active, $1,510.52 a year.

| Merchant      | Every   | Last charge        | Per year | Next       | Why look                       |
| Ironworks Gym | monthly | 2026-10-07 $49.00  | $588.00  | 2026-11-06 |                                |
| Netflix       | monthly | 2026-10-03 $17.99  | $215.88  | 2026-11-02 | price went up $15.49 → $17.99  |
| Canva         | monthly | 2026-10-15 $14.99  | $179.88  | 2026-11-14 | free trial turned paid         |
| Amazon Prime  | annual  | 2025-11-02 $139.00 | $139.00  | 2026-11-02 | renews within 30 days          |
| Apple         | monthly | 2026-10-22 $2.99   | $35.88   | 2026-11-21 | charged twice                  |
| Hulu          | monthly | 2026-04-20 $9.99   | -        | -          | stopped                        |
```
(Full output from the synthetic sample: [`docs/sample-ghosts.md`](docs/sample-ghosts.md), audit trail: [`docs/sample-audit.txt`](docs/sample-audit.txt).)

## Run it

```bash
# 1. a local OpenAI-compatible server (tested: llama.cpp llama-server build b11617)
llama-server -m gemma-4-E2B-it-Q4_0.gguf --port 8080 -c 4096
# 2. your bank's CSV export: needs Date, Description, Amount columns (charges negative)
python3 -m ghostcharges statement.csv
# re-run instantly without the model, reusing what it read:
python3 -m ghostcharges statement.csv --readings ghost-charges-out/readings.json
```
Python 3.9+ standard library only. No pip installs, no accounts, no network calls except to your local model server. Output goes to `ghost-charges-out/` (`ghosts.md`, `findings.json`, `audit.txt`, `readings.json`), which is git-ignored.

## How it works (the model only reads)

1. **Read.** Each unique statement line goes to the local model with a JSON Schema: `merchant`, `quote` (the exact characters it read the name from) and `kind`. About 2 seconds a line on a laptop-class CPU (8 threads).
2. **Check with rules, not another model.** The quote must really be in the line, and at least one word of the merchant name must appear in it. `AMZN Mktp US*2K45L7` → the model said "Amazon", which isn't written there, so a rule-only name ("Amzn Mktp") is used and the line is marked `FIXED` in `audit.txt`.
3. **Group.** Names are merged when one is the other plus a suffix (`Adobe Inc.` → `Adobe`, `Dropbox Plus` → `Dropbox`); keys under 4 letters never swallow others.
4. **Find what repeats, in plain Python.** Weekly (5–9 days), monthly (25–35) or annual (350–380) by the median gap, at least 3 charges (2 for annual), 75% of gaps on cadence, and steady amounts (random grocery runs don't qualify). Then: **price went up**, **charged twice** (same amount within 3 days), **free trial turned paid** ($0–$1 charge up to 45 days before the first full one), **renews within 30 days** (annual), **stopped** (missed its cadence plus a grace period). Yearly cost uses the latest price.

## Measured accuracy (synthetic statements, hand-made answer keys)

| Set | Subscriptions | Gemma 4 E2B + rules | Rules alone (no model) | False alarms |
|---|---:|---:|---:|---:|
| Dev set, 148 rows (`samples/`) | 8 | **8/8** exactly right (cadence, active, every flag) | 7/8 (finds the same charges but can't name `NYTIMES*NYTDIGITAL` as New York Times) | 0 |
| Held-out, 48 rows (`samples/holdout/`), first run | 4 | **1/4** | 0/4 | 0 |
| Same held-out rows after fixing what that run found | 4 | **4/4** | 3/4 (splits `DROPBOX*7GH2K9` and `DBX*DROPBOX PLUS`, so misses the annual renewal) | 0 |

The held-out run was useful: Gemma named the same merchant two ways ("Adobe" / "Adobe Inc.", "Dropbox" / "Dropbox Plus", "Youtube Premium" / "YouTube Premium"), which split each subscription into pieces too small to look recurring. The fix is the merge rule in step 3. Because it was written after seeing those rows, the last row is **not** a clean held-out number. Read it as an honest small-sample result, not a benchmark. Recorded model replies are in `tests/fixtures/` and CI re-scores them on every push. 14 unit tests; 6 of 6 deliberate code breakages (mutations) are caught.

What it won't do: log into your bank, cancel anything, or know about subscriptions billed to another card. Statement descriptors vary by bank; if yours look different, check `audit.txt`.

## Why local

A bank export is a year of where you live, eat, shop and who you pay. Sending it to a hosted model to find a $9.99 subscription is a bad trade. A 2.8 GB open-weight model reads statement lines well enough when plain code checks its work, and it runs with the Wi-Fi off.

## Related

Made by [Sheet & Flow](https://onyxaholguin-cyber.github.io/sheet-and-flow/). If you'd rather plan next year's spending in a spreadsheet, see the [2027 Budget Planner](https://onyxaholguin-cyber.github.io/sheet-and-flow/products/budget-planner-2027/).

MIT licensed. Synthetic sample data only; no real bank data in this repo.
