"""Phase 1: units, money, evidence, models, profiles."""
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from shelfscout.core.errors import CurrencyError, EvidenceError, ProfileError, UnitError, ValidationError  # noqa: E402
from shelfscout.core.evidence import Status, make_claim, EvidenceSource  # noqa: E402
from shelfscout.core.models import parse_request  # noqa: E402
from shelfscout.core.money import FxRate, Money, minor_units  # noqa: E402
from shelfscout.core.units import Quantity, Range, parse_value  # noqa: E402
from shelfscout.profiles.loader import DIMENSIONS, list_profiles, load_profile, requirements_for, validate_profile  # noqa: E402


class Units(unittest.TestCase):
    def test_conversions(self):
        self.assertEqual(Quantity(1, "in").to("mm").value, Decimal("25.4"))
        self.assertEqual(Quantity("276", "MPa").to("GPa").value, Decimal("0.276"))
        self.assertAlmostEqual(float(Quantity(100, "C").to("F").value), 212.0)
        self.assertAlmostEqual(float(Quantity(1, "ksi").to("MPa").value), 6.894757, places=5)
        self.assertEqual(Quantity(2.7, "g/cm3").to("kg/m3").value, Decimal("2700.0"))

    def test_incompatible_units_refused(self):
        with self.assertRaises(UnitError):
            Quantity(1, "MPa") < Quantity(1, "mm")
        with self.assertRaises(UnitError):
            Quantity(1, "MPa").to("kg")
        with self.assertRaises(UnitError):
            Quantity(1, "HRC").to("HV"), "hardness scales aren't interconvertible"

    def test_comparison_across_units(self):
        self.assertTrue(Quantity(500, "mm") < Quantity(1, "m"))
        self.assertTrue(Quantity(1, "kg").equals(Quantity(1000, "g")))

    def test_bad_values(self):
        for bad in ("nan", "inf", "abc"):
            with self.assertRaises(UnitError):
                Quantity(bad, "mm")
        with self.assertRaises(UnitError):
            Quantity(1, "furlong")

    def test_ranges(self):
        r = parse_value({"min": 420, "max": 520}, "mm")
        self.assertTrue(r.contains(Quantity(45, "cm")))
        self.assertFalse(r.contains(Quantity(60, "cm")))
        self.assertEqual(r.mid().value, Decimal(470))
        with self.assertRaises(UnitError):
            Range.of(5, 1, "mm")
        self.assertEqual(parse_value("aluminium", None), "aluminium")


class MoneyTests(unittest.TestCase):
    def test_minor_units(self):
        self.assertEqual(minor_units("JPY"), 0)
        self.assertEqual(minor_units("KWD"), 3)
        self.assertEqual(minor_units("INR"), 2)
        self.assertEqual(Money("10.125", "USD").rounded().amount, Decimal("10.13"))
        self.assertEqual(Money("10.1255", "KWD").rounded().amount, Decimal("10.126"))
        self.assertEqual(Money("1500.5", "JPY").format(), "¥1,501")
        self.assertEqual(Money("8499", "INR").format(), "₹8,499.00")

    def test_no_cross_currency_math(self):
        with self.assertRaises(CurrencyError):
            Money(1, "USD") + Money(1, "EUR")
        with self.assertRaises(CurrencyError):
            Money(1, "USD") < Money(1, "INR")
        with self.assertRaises(CurrencyError):
            Money(1, "US")

    def test_fx_needs_source_and_date(self):
        with self.assertRaises(CurrencyError):
            FxRate("USD", "INR", "84", "", "2026-11-22")
        with self.assertRaises(CurrencyError):
            FxRate("USD", "INR", "-1", "bank", "2026-11-22")
        fx = FxRate("USD", "INR", "84.1", "user-provided bank rate", "2026-11-22")
        self.assertEqual(Money(100, "USD").convert(fx), Money("8410.00", "INR"))
        with self.assertRaises(CurrencyError):
            Money(100, "EUR").convert(fx)


class Evidence(unittest.TestCase):
    def setUp(self):
        self.sources = {s["id"]: EvidenceSource.from_dict(s) for s in [
            {"id": "m", "name": "Brand page", "type": "manufacturer", "url": "https://brand.example/chair"},
            {"id": "lab", "name": "Test lab", "type": "independent_lab"},
            {"id": "rv", "name": "Reviews", "type": "customer_reviews"},
            {"id": "aff", "name": "Affiliate blog", "type": "expert_review", "independence": "affiliated"}]}

    def test_unknown_has_no_value(self):
        c = make_claim({"claim_type": "material.frame_grade", "status": "UNKNOWN"}, self.sources, "c1")
        self.assertFalse(c.is_known())
        with self.assertRaises(EvidenceError):
            make_claim({"claim_type": "x", "status": "UNKNOWN", "value": 5}, self.sources, "c2")

    def test_known_needs_value_and_source(self):
        with self.assertRaises(EvidenceError):
            make_claim({"claim_type": "x", "status": "MANUFACTURER_REPORTED", "value": 5}, self.sources, "c")
        with self.assertRaises(EvidenceError):
            make_claim({"claim_type": "x", "status": "MANUFACTURER_REPORTED", "source": "m"}, self.sources, "c")
        with self.assertRaises(EvidenceError):
            make_claim({"claim_type": "x", "status": "MANUFACTURER_REPORTED", "value": 1, "source": "nope"}, self.sources, "c")

    def test_manufacturer_cannot_verify_itself(self):
        with self.assertRaises(EvidenceError):
            make_claim({"claim_type": "safety.cert", "status": "VERIFIED", "value": "CE", "source": "m"}, self.sources, "c")
        with self.assertRaises(EvidenceError):
            make_claim({"claim_type": "x", "status": "INDEPENDENTLY_TESTED", "value": 1, "source": "aff"}, self.sources, "c")
        ok = make_claim({"claim_type": "x", "status": "INDEPENDENTLY_TESTED", "value": 1, "source": "lab"}, self.sources, "c")
        self.assertEqual(ok.status, Status.INDEPENDENTLY_TESTED)

    def test_customer_reported_needs_customer_source(self):
        with self.assertRaises(EvidenceError):
            make_claim({"claim_type": "x", "status": "CUSTOMER_REPORTED", "value": 1, "source": "m"}, self.sources, "c")

    def test_ai_summary_is_not_a_source(self):
        with self.assertRaises(EvidenceError):
            EvidenceSource.from_dict({"id": "ai", "type": "agent_summary"})
        with self.assertRaises(EvidenceError):
            EvidenceSource.from_dict({"id": "x", "type": "manufacturer", "url": "javascript:alert(1)"})


class Requests(unittest.TestCase):
    def base(self):
        return {"category": "office_chair", "market": {"country": "IN", "currency": "INR"},
                "sources": [{"id": "m", "type": "manufacturer"}],
                "products": [{"id": "a", "name": "Chair A", "listing": {"price": 9999, "currency": "INR"},
                              "claims": [{"claim_type": "material.frame", "status": "MANUFACTURER_REPORTED",
                                          "value": "aluminium alloy", "source": "m"}]}]}

    def test_parses(self):
        r = parse_request(self.base())
        self.assertEqual(r.products[0].listing.total(), Money(9999, "INR"))
        self.assertEqual(r.products[0].claim("material.frame").value, "aluminium alloy")

    def test_rejects_mixed_currency_and_bad_safety(self):
        d = self.base()
        d["products"][0]["listing"]["currency"] = "USD"
        with self.assertRaises(ValidationError):
            parse_request(d)
        d = self.base()
        d["products"][0]["safety"] = [{"requirement": "x", "outcome": "pass"}]
        with self.assertRaises(ValidationError):
            parse_request(d)

    def test_reviews_need_source(self):
        d = self.base()
        d["products"][0]["reviews"] = {"items": [{"rating": 5}]}
        with self.assertRaises(ValidationError):
            parse_request(d)


class Profiles(unittest.TestCase):
    def test_all_profiles_valid(self):
        names = list_profiles()
        self.assertGreaterEqual(len(names), 15)
        for n in names:
            p = load_profile(n)
            self.assertEqual(set(p["weights"]), set(DIMENSIONS))
            self.assertAlmostEqual(sum(p["weights"].values()), 100)
            self.assertIn("uncalibrated", p["calibration"])

    def test_extends_merges_requirements(self):
        p = load_profile("smartphone")
        self.assertEqual(p["lineage"], ["smartphone", "electronics"])
        ids = [r["id"] for r in requirements_for(p, "IN")]
        self.assertIn("in-bis-crs", ids)
        self.assertIn("all-un383", ids)
        self.assertNotIn("us-fcc", ids)
        self.assertIn("eu-ce-red", [r["id"] for r in requirements_for(p, "DE")])

    def test_invalid_profiles_rejected(self):
        good = load_profile("furniture")
        bad = dict(good, weights=dict(good["weights"], aesthetics=good["weights"]["aesthetics"] + 1))
        with self.assertRaises(ProfileError):
            validate_profile(bad)
        with self.assertRaises(ProfileError):
            validate_profile(dict(good, weights={k: v for k, v in good["weights"].items() if k != "safety"}))
        with self.assertRaises(ProfileError):
            validate_profile(dict(good, gates=[{"id": "g", "dimension": "vibes"}]))
        with self.assertRaises(ProfileError):
            load_profile("spaceships")

    def test_circular_extends(self):
        with tempfile.TemporaryDirectory() as d:
            for a, b in (("a", "b"), ("b", "a")):
                Path(d, f"{a}.json").write_text(json.dumps({"id": a, "extends": b, "version": "1"}))
            with self.assertRaises(ProfileError):
                load_profile("a", Path(d))


if __name__ == "__main__":
    unittest.main()
