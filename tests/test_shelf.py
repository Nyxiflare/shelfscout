"""Offline tests for shelf.py. Run from the skill folder:  python -m unittest discover -s tests"""
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "shelf.py"
sys.path.insert(0, str(SCRIPT.parent))
import shelf  # noqa: E402


def run(*args) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        shelf.main(list(args))
    return buf.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, data) -> str:
        p = self.d / name
        p.write_text(json.dumps(data), encoding="utf-8")
        return str(p)

    def fails(self, *args) -> str:
        with self.assertRaises(SystemExit) as e:
            run(*args)
        return str(e.exception)


class Landed(Base):
    def test_tax_on_price_and_shipping(self):
        r = shelf.landed_cost("49.99", "5", "8.25")
        self.assertEqual(r["total"].quantize(Decimal("0.01")), Decimal("59.53"))

    def test_duty_before_tax(self):
        r = shelf.landed_cost("100", "0", "10", "5")
        self.assertEqual(r["duty"], Decimal("5"))
        self.assertEqual(r["tax"], Decimal("10.5"))
        self.assertEqual(r["total"], Decimal("115.5"))

    def test_bad_input(self):
        for bad in ("-1", "nan", "inf", "abc"):
            self.fails("landed", "--price", bad)


class Unit(Base):
    def test_per_100(self):
        self.assertIn("$1.30 per 100 g", run("unit", "--price", "6.50", "--qty", "500", "--unit-name", "g", "--per", "100"))

    def test_zero_qty(self):
        self.fails("unit", "--price", "5", "--qty", "0")


class Deal(Base):
    def test_fake_was_price(self):
        hist = [{"date": f"2026-0{m}-01", "price": 85} for m in range(5, 10)]
        r = shelf.deal_check("79", "129", hist)
        self.assertTrue(any("never appears" in f for f in r["flags"]))
        self.assertTrue(r["verdict"].startswith("good"), r["verdict"])

    def test_above_usual_price(self):
        hist = [{"date": "2026-08-01", "price": 60}, {"date": "2026-09-15", "price": 62}, {"date": "2026-10-20", "price": 61}]
        self.assertTrue(shelf.deal_check("70", "99", hist)["verdict"].startswith("poor"))

    def test_no_history(self):
        out = run("deal", "--price", "79", "--was", "129")
        self.assertIn("can't be checked", out)
        self.assertIn("Discount claim: unverifiable", out)

    def test_price_and_claim_judged_separately(self):
        hist = [{"date": "2026-06-01", "price": 89.99}, {"date": "2026-08-01", "price": 79.99}, {"date": "2026-11-01", "price": 89.99}]
        r = shelf.deal_check("79.99", "129.99", hist)
        self.assertTrue(r["verdict"].startswith("good"))
        self.assertTrue(r["claim"].startswith("not supported"))
        self.assertTrue(shelf.deal_check("79.99", "89.99", hist)["claim"].startswith("supported"))

    def test_short_history_flagged(self):
        hist = [{"date": "2026-11-01", "price": 90}, {"date": "2026-11-10", "price": 80}]
        self.assertTrue(any("30 days" in f for f in shelf.deal_check("80", None, hist)["flags"]))


class Reviews(Base):
    def test_burst_duplicates_and_uniform_ratings(self):
        text = "This product is absolutely amazing and works perfectly every single time I use it"
        reviews = [{"rating": 5, "date": f"2026-10-0{1 + i % 5}", "verified": i % 2 == 0, "text": text} for i in range(12)]
        reviews += [{"rating": 4, "date": "2026-01-15", "text": "Decent but the lid feels flimsy after a month of use"}]
        r = shelf.review_signals(reviews)
        self.assertEqual(r["level"], "high")
        joined = " ".join(r["signals"])
        for phrase in ("5-star", "burst", "exact text", "not marked as verified"):
            self.assertIn(phrase, joined)

    def test_near_duplicates_detected(self):
        base = "The sound quality is fantastic and the noise cancelling blocks the train completely"
        reviews = [{"rating": 5, "text": base + w} for w in (" every day", " on my commute", " at work", " for hours")]
        reviews += [{"rating": 3, "text": f"Unrelated review number {i} about comfort and fit on long flights"} for i in range(8)]
        joined = " ".join(shelf.review_signals(reviews)["signals"])
        self.assertIn("share much of their wording", joined)
        self.assertNotIn("exact text", joined)

    def test_short_identical_reviews_count_as_duplicates(self):
        reviews = [{"rating": 5, "text": "Great product!"} for _ in range(5)] + [{"rating": 4, "text": "fine"}]
        self.assertIn("5 reviews repeat", " ".join(shelf.review_signals(reviews)["signals"]))

    def test_healthy_sample(self):
        texts = ["Works well, though the cable is short for my desk setup",
                 "Arrived quickly and setup took about ten minutes total",
                 "Broke after three weeks, the hinge snapped on the left side",
                 "Good value for the price, sound is fine for podcasts",
                 "Customer service replaced mine when the button stuck",
                 "The blue colour is darker than in the photos online",
                 "Battery lasts roughly two days with moderate daily use",
                 "Instructions were confusing but a video helped me out",
                 "Heavier than my old one, feels sturdy on the counter",
                 "Fan noise is noticeable at night in a quiet bedroom",
                 "Returned it because the size was wrong for my shelf"]
        reviews = [{"rating": [4, 5, 2, 4, 3][i % 5], "date": f"2026-{1 + i:02d}-10", "verified": True,
                    "text": texts[i]} for i in range(11)]
        r = shelf.review_signals(reviews)
        self.assertEqual(r["level"], "low", r["signals"])

    def test_small_sample_warning(self):
        out = run("reviews", self.write("r.json", [{"rating": 5, "text": "fine"}]))
        self.assertIn("Fewer than 20", out)

    def test_bad_rating(self):
        self.assertIn("1-5", self.fails("reviews", self.write("r.json", [{"rating": 7}])))


class Compare(Base):
    def listings(self):
        return {"currency": "USD", "budget": 100, "listings": [
            {"name": "Cheap kettle", "price": 25, "shipping": 15, "fit": 6, "rating": 4.1, "review_count": 900,
             "seller_rating_pct": 91, "returns_days": 0},
            {"name": "Brand kettle", "price": 69, "shipping": 0, "fit": 9, "rating": 4.6, "review_count": 4000,
             "seller_rating_pct": 99, "returns_days": 30, "sold_by_brand_or_marketplace": True},
            {"name": "Fancy kettle", "price": 140, "fit": 10, "rating": 4.8, "review_count": 300},
            {"name": "Suspicious kettle", "price": 30, "fit": 8, "rating": 4.9, "review_count": 2000,
             "review_warning": "high", "seller_rating_pct": 84}]}

    def test_ranking_and_budget(self):
        rows = shelf.score_listings(self.listings()["listings"], shelf.DEFAULT_WEIGHTS, Decimal(100))
        self.assertEqual(rows[0]["name"], "Brand kettle")
        self.assertEqual(rows[-1]["name"], "Fancy kettle", "over-budget items rank last")
        names = [r["name"] for r in rows]
        self.assertLess(names.index("Cheap kettle"), names.index("Fancy kettle"))
        sus = next(r for r in rows if r["name"] == "Suspicious kettle")
        self.assertLess(sus["reviews"], 5, "high review warning is penalised")

    def test_trust_brand_vs_reseller(self):
        ls = [{"name": "Walmart", "price": 100, "sold_by_brand_or_marketplace": True, "returns_days": 30},
              {"name": "Reseller", "price": 100, "seller_rating_pct": 99.4, "returns_days": 30, "condition": "open box"},
              {"name": "Brand store", "price": 100, "seller_rating_pct": 98, "returns_days": 30, "sold_by_brand_or_marketplace": True}]
        t = {r["name"]: r["trust"] for r in shelf.score_listings(ls, shelf.DEFAULT_WEIGHTS)}
        self.assertGreater(t["Brand store"], t["Reseller"])
        self.assertGreater(t["Walmart"], t["Reseller"])

    def test_same_product_borrows_reviews(self):
        ls = [{"name": "Q30 new", "price": 80, "rating": 4.5, "review_count": 18000},
              {"name": "Q30 open box", "price": 60, "same_product_as": "Q30 new"}]
        rows = {r["name"]: r for r in shelf.score_listings(ls, shelf.DEFAULT_WEIGHTS)}
        self.assertEqual(rows["Q30 open box"]["reviews"], rows["Q30 new"]["reviews"])
        out = run("compare", self.write("s.json", {"listings": ls}))
        self.assertIn("reviews taken from 'Q30 new'", out)

    def test_top_level_tax_applies(self):
        data = {"tax_pct": 10, "listings": [{"name": "A", "price": 100}, {"name": "B", "price": 100, "tax_pct": 0}]}
        rows = {r["name"]: r for r in shelf.score_listings(data["listings"], shelf.DEFAULT_WEIGHTS, None, {"tax_pct": 10})}
        self.assertEqual(rows["A"]["total"], Decimal(110))
        self.assertEqual(rows["B"]["total"], Decimal(100), "a listing's own value wins")

    def test_over_budget_note(self):
        self.assertIn("ranked last, whatever their score", run("compare", self.write("l.json", self.listings())))

    def test_shipping_counts(self):
        rows = shelf.score_listings(self.listings()["listings"][:2], shelf.DEFAULT_WEIGHTS)
        cheap = next(r for r in rows if r["name"] == "Cheap kettle")
        self.assertEqual(cheap["total"], Decimal(40))

    def test_weights_change_order(self):
        rows = shelf.score_listings(self.listings()["listings"][:2], shelf.parse_weights("value=100"))
        self.assertEqual(rows[0]["name"], "Cheap kettle")

    def test_html_output_is_self_contained(self):
        out_html = self.d / "c.html"
        run("compare", self.write("l.json", self.listings()), "--html", str(out_html))
        doc = out_html.read_text(encoding="utf-8")
        self.assertIn("Brand kettle", doc)
        self.assertNotIn("<script", doc)
        self.assertNotIn("http://", doc)

    def test_escapes_names(self):
        data = self.listings()
        data["listings"][0]["name"] = "<img src=x onerror=alert(1)>"
        data["listings"][0]["url"] = "javascript:alert(1)"
        out_html = self.d / "c.html"
        run("compare", self.write("l.json", data), "--html", str(out_html))
        doc = out_html.read_text(encoding="utf-8")
        self.assertNotIn("<img src=x", doc)
        self.assertNotIn("javascript:", doc)

    def test_bad_weights_and_fit(self):
        self.fails("compare", self.write("l.json", self.listings()), "--weights", "price=10")
        bad = self.listings()
        bad["listings"][0]["fit"] = 14
        self.assertIn("0-10", self.fails("compare", self.write("b.json", bad)))


class Margin(Base):
    def test_amazon_example(self):
        r = shelf.margin_calc("29.99", "6.50", "1.20", "amazon-us", None, None, "5.40", "10", "5")
        self.assertEqual(r["referral"].quantize(Decimal("0.01")), Decimal("4.50"))
        self.assertEqual(r["profit"].quantize(Decimal("0.01")), Decimal("8.71"))
        self.assertGreater(r["breakeven_ads_pct"], r["margin_pct"])

    def test_override_preset(self):
        r = shelf.margin_calc("20", "5", marketplace="amazon-us", referral_pct="8")
        self.assertEqual(r["referral"], Decimal("1.6"))

    def test_loss_making_verdict(self):
        self.assertIn("Not viable", run("margin", "--sell", "9.99", "--cost", "6", "--marketplace", "ebay-us", "--fulfil", "4"))

    def test_fees_list(self):
        out = run("fees")
        for k in shelf.FEE_PRESETS:
            self.assertIn(k, out)
        self.assertIn("not checked live", out)


class Cli(Base):
    def test_runs_from_another_folder(self):
        res = subprocess.run([sys.executable, str(SCRIPT), "landed", "--price", "10"], cwd=self.d,
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("$10.00", res.stdout)


if __name__ == "__main__":
    unittest.main()
