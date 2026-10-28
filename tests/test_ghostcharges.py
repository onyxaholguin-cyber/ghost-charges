import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ghostcharges import find  # noqa: E402

D = dt.date


def rows(spec):
    return [{"date": d, "desc": desc, "amount": -a} for d, desc, a in spec]


def monthly(desc, amt, n, start=D(2026, 1, 5)):
    return [(D(start.year + (start.month - 1 + i) // 12, (start.month - 1 + i) % 12 + 1, start.day), desc, amt) for i in range(n)]


class Grounding(unittest.TestCase):
    def test_accepts_grounded_name_and_strips_delimiters(self):
        self.assertEqual(find.check_reading("NETFLIX.COM 866 CA", {"merchant": "Netflix", "quote": "<<<NETFLIX.COM 866 CA>>>"}), ("Netflix", "ok"))

    def test_rejects_invented_brand(self):
        m, st = find.check_reading("AMZN Mktp US*2K4", {"merchant": "Amazon", "quote": "AMZN Mktp"})
        self.assertEqual(st, "FIXED")
        self.assertEqual(m, "Amzn Mktp")

    def test_rejects_quote_not_in_line(self):
        self.assertEqual(find.check_reading("HULU 877 CA", {"merchant": "Hulu", "quote": "HULU PLUS"})[1], "FIXED")

    def test_fallback_drops_processor_and_numbers(self):
        self.assertEqual(find.fallback_key("SQ *IRONWORKS GYM 1201 CO"), "Ironworks Gym")
        self.assertEqual(find.fallback_key("PAYPAL *SPOTIFYUSA 4029"), "Spotifyusa")


class Merge(unittest.TestCase):
    def test_suffix_and_prefix_merge(self):
        g = find.merge_names({"Adobe", "Adobe Inc.", "Dropbox Plus", "Dropbox", "Disney Plus"})
        self.assertEqual(g["Adobe Inc."], "Adobe")
        self.assertEqual(g["Dropbox Plus"], "Dropbox")
        self.assertEqual(g["Disney Plus"], "Disney Plus")

    def test_short_keys_do_not_swallow(self):
        g = find.merge_names({"Ups", "Upstart Loans"})
        self.assertNotEqual(g["Upstart Loans"], "Ups")


class Ghosts(unittest.TestCase):
    def run_one(self, spec, as_of=D(2026, 10, 28)):
        r = rows(spec)
        return find.find_ghosts(r, {x["desc"]: x["desc"] for x in r}, as_of)

    def test_monthly_price_up_and_yearly_cost(self):
        spec = monthly("Netflix", 15.49, 6) + monthly("Netflix", 17.99, 4, D(2026, 7, 5))
        f = self.run_one(spec)[0]
        self.assertEqual((f["cadence"], f["active"], f["flags"], f["per_year"]), ("monthly", True, ["price_up"], 215.88))
        self.assertEqual(f["next_expected"], "2026-11-04")

    def test_stopped_subscription(self):
        f = self.run_one(monthly("Hulu", 9.99, 4))[0]
        self.assertFalse(f["active"])
        self.assertEqual(f["per_year"], 0.0)

    def test_double_charge_not_counted_as_cadence(self):
        spec = monthly("Apple", 2.99, 6, D(2026, 5, 22)) + [(D(2026, 10, 23), "Apple", 2.99)]
        f = self.run_one(spec)[0]
        self.assertEqual(f["flags"], ["double_charge"])
        self.assertEqual(f["extra_paid"], 2.99)

    def test_trial_converted(self):
        spec = [(D(2026, 7, 15), "Canva", 0.0)] + monthly("Canva", 14.99, 3, D(2026, 8, 15))
        self.assertEqual(self.run_one(spec)[0]["flags"], ["trial_converted"])

    def test_annual_renews_soon_and_weekly(self):
        spec = [(D(2024, 11, 2), "Prime", 139.0), (D(2025, 11, 2), "Prime", 139.0)]
        spec += [(D(2026, 8, 3) + dt.timedelta(weeks=i), "NYT", 4.0) for i in range(12)]
        fs = {f["merchant"]: f for f in self.run_one(spec)}
        self.assertEqual(fs["Prime"]["flags"], ["renews_soon"])
        self.assertEqual((fs["NYT"]["cadence"], fs["NYT"]["per_year"]), ("weekly", 208.0))

    def test_random_shopping_is_not_a_subscription(self):
        spec = [(D(2026, 1, 3) + dt.timedelta(days=30 * i), "Grocer", a) for i, a in enumerate([12.5, 88.1, 41.0, 150.2, 9.9])]
        self.assertEqual(self.run_one(spec), [])

    def test_two_monthly_charges_are_not_enough(self):
        self.assertEqual(self.run_one(monthly("Gym", 49.0, 2)), [])

    def test_income_ignored(self):
        r = [{"date": D(2026, i, 1), "desc": "PAYROLL", "amount": 2450.0} for i in range(1, 10)]
        self.assertEqual(find.find_ghosts(r, {"PAYROLL": "Payroll"}, D(2026, 10, 28)), [])


if __name__ == "__main__":
    unittest.main()
