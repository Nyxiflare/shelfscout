"""Phases 2-6: scoring invariants, safety gates, reviews, materials, ergonomics, identity, TCO, store, reports."""
import copy
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from shelfscout.core.money import Money  # noqa: E402
from shelfscout.identity.matching import compare  # noqa: E402
from shelfscout.intelligence import materials  # noqa: E402
from shelfscout.intelligence.price import tco  # noqa: E402
from shelfscout.reports import html as html_report, markdown  # noqa: E402
from shelfscout.scoring.engine import evaluate  # noqa: E402
from shelfscout.store import sqlite as store  # noqa: E402

EX = ROOT / "examples"


def example(name):
    return json.loads((EX / name / "request.json").read_text(encoding="utf-8"))


def by_id(result):
    return {e["product_id"]: e for e in result["evaluations"]}


def minimal(**extra_product):
    p = {"id": "x", "name": "Chair X", "listing": {"price": 9000},
         "claims": [{"id": "w", "claim_type": "warranty.years", "status": "MANUFACTURER_REPORTED", "value": 2, "source": "m"}]}
    p.update(extra_product)
    return {"category": "office_chair", "as_of": "2026-11-22", "market": {"country": "IN", "currency": "INR"},
            "sources": [{"id": "m", "type": "manufacturer"}, {"id": "lab", "type": "independent_lab"},
                        {"id": "rv", "type": "customer_reviews"}, {"id": "gov", "type": "government_record"}],
            "products": [p]}


class Examples(unittest.TestCase):
    """The three worked examples behave as designed (regression)."""

    def test_office_chair(self):
        r = evaluate(example("office-chair"))
        e = by_id(r)
        self.assertEqual(r["rankings"]["recommended"], "ergoone")
        self.assertEqual(e["luxemesh"]["eligibility"], "EXCLUDED", "an active recall excludes whatever the score")
        self.assertGreater(e["luxemesh"]["overall_score"], e["ergoone"]["overall_score"] - 5)
        self.assertIn("luxemesh", r["rankings"]["avoid"])
        self.assertNotIn("budgetseat", r["rankings"]["within_budget"])
        self.assertIn("budgetseat", r["rankings"]["over_or_under_budget"])

    def test_smartphone(self):
        r = evaluate(example("smartphone"))
        e = by_id(r)
        self.assertEqual(e["zetax"]["eligibility"], "SAFETY_HOLD")
        self.assertEqual(r["rankings"]["recommended"], "nova8")
        fcc_orbit = next(c for c in e["orbitpro"]["dimensions"]["safety"]["criteria"] if "FCC" in c["name"])
        fcc_nova = next(c for c in e["nova8"]["dimensions"]["safety"]["criteria"] if "FCC" in c["name"])
        self.assertEqual(fcc_nova["score"], 100.0)
        self.assertEqual(fcc_orbit["score"], 60.0, "a manufacturer's own claim is declared, not verified")
        battery = next(c for c in e["nova8"]["dimensions"]["features_performance"]["criteria"] if "battery" in c["name"])
        self.assertAlmostEqual(battery["score"], 80.0)
        musts = next(c for c in e["nova8"]["dimensions"]["features_performance"]["criteria"] if "must-have" in c["name"])
        self.assertAlmostEqual(musts["score"], 200 / 3, places=1)

    def test_running_shoes(self):
        r = evaluate(example("running-shoes"))
        e = by_id(r)
        self.assertEqual(r["rankings"]["recommended"], "stride5")
        width = next(c for c in e["glidepro"]["dimensions"]["ergonomics"]["criteria"] if "width" in c["name"])
        self.assertEqual(width["score"], 20.0, "standard-only shoe for a wide foot")
        for x in e.values():
            self.assertNotEqual(x["eligibility"], "ELIGIBLE", "no safety evidence means not fully eligible")


class Invariants(unittest.TestCase):
    def test_scores_in_range_everywhere(self):
        for name in ("office-chair", "smartphone", "running-shoes"):
            for e in evaluate(example(name))["evaluations"]:
                if e["overall_score"] is not None:
                    self.assertTrue(0 <= e["overall_score"] <= 100)
                for d in e["dimensions"].values():
                    self.assertTrue(0 <= d["score"] <= 100 and 0 <= d["confidence"] <= 100)
                    for c in d["criteria"]:
                        self.assertTrue(0 <= c["score"] <= 100)

    def test_missing_dimension_has_no_score(self):
        e = evaluate(minimal())["evaluations"][0]
        self.assertNotIn("ergonomics", e["dimensions"])
        self.assertIn("ergonomics", e["missing_dimensions"])
        self.assertEqual(e["eligibility"], "INSUFFICIENT_EVIDENCE")

    def test_missing_safety_never_eligible(self):
        d = example("office-chair")
        p = next(x for x in d["products"] if x["id"] == "ergoone")
        p["claims"] = [c for c in p["claims"] if not c["claim_type"].startswith("test.safety")]
        e = by_id(evaluate(d))["ergoone"]
        self.assertNotIn("safety", e["dimensions"])
        self.assertNotEqual(e["eligibility"], "ELIGIBLE")

    def test_failed_mandatory_requirement_excludes(self):
        d = example("smartphone")
        nova = next(x for x in d["products"] if x["id"] == "nova8")
        nova["claims"].append({"id": "fail", "claim_type": "certification.fcc", "status": "VERIFIED",
                               "value": "authorization revoked", "source": "fcc"})
        nova["safety"] = [{"requirement": "us-fcc", "outcome": "fail", "claim": "fail"}]
        r = evaluate(d)
        self.assertEqual(by_id(r)["nova8"]["eligibility"], "EXCLUDED")
        self.assertNotEqual(r["rankings"]["recommended"], "nova8")

    def test_priorities_cannot_override_safety_hold(self):
        d = example("smartphone")
        d["user"]["priorities"] = {"price_value": 100}
        r = evaluate(d)
        self.assertEqual(by_id(r)["zetax"]["eligibility"], "SAFETY_HOLD")
        self.assertNotEqual(r["rankings"]["personal"][0], "zetax")
        self.assertNotEqual(r["rankings"]["recommended"], "zetax")

    def test_over_budget_never_recommended(self):
        d = example("smartphone")
        d["user"]["budget"] = {"max": 400}
        r = evaluate(d)
        self.assertNotIn(r["rankings"]["recommended"], ("nova8", "orbitpro"))
        for best in r["rankings"]["best_by_dimension"].values():
            self.assertNotIn(best, ("nova8", "orbitpro"), "over-budget products can't be 'best' within the budget")

    def test_reproducible(self):
        a, b = evaluate(example("office-chair")), evaluate(example("office-chair"))
        self.assertEqual(json.dumps(a, sort_keys=True, default=str), json.dumps(b, sort_keys=True, default=str))
        self.assertEqual(len(a["input_hash"]), 64)
        self.assertEqual(a["profile_lineage"], ["office_chair", "furniture"])

    def test_agent_judgement_rules(self):
        d = minimal(criteria=[
            {"dimension": "safety", "criterion": "looks safe", "score": 100, "claims": ["w"]},
            {"dimension": "aesthetics", "criterion": "untied", "score": 90, "claims": []},
            {"dimension": "aesthetics", "criterion": "finish", "score": 80, "claims": ["w"], "basis": "photos"}])
        e = evaluate(d)["evaluations"][0]
        self.assertNotIn("safety", e["dimensions"], "safety can't be scored by judgement")
        crit = e["dimensions"]["aesthetics"]["criteria"]
        self.assertEqual([c["name"] for c in crit], ["finish"])
        self.assertEqual(crit[0]["method"], "agent_judgement")
        self.assertTrue(any("ignored" in n for n in e["notes"]))

    def test_other_variant_evidence_is_less_confident(self):
        a = evaluate(minimal())["evaluations"][0]
        d = minimal()
        d["products"][0]["claims"][0]["variant_match"] = "other_variant"
        b = evaluate(d)["evaluations"][0]
        self.assertLess(b["dimensions"]["durability"]["confidence"], a["dimensions"]["durability"]["confidence"])

    def test_unit_mismatch_is_noted_not_crashing(self):
        d = minimal()
        d["products"][0]["claims"].append({"id": "f", "claim_type": "construction.seat_foam_density",
                                           "status": "MANUFACTURER_REPORTED", "value": 45, "unit": "mm", "source": "m"})
        e = evaluate(d)["evaluations"][0]
        self.assertTrue(any("convert" in n.lower() for n in e["notes"]))

    def test_price_value_needs_two_priced_products(self):
        e = evaluate(minimal())["evaluations"][0]
        self.assertNotIn("price_value", e["dimensions"])


class Reviews(unittest.TestCase):
    def test_duplicates_counted_once_and_denominator(self):
        items = [{"rating": 5, "text": "Great chair, very comfortable for work"}] * 6
        items += [{"rating": 2, "text": f"cushion flattened after months, owner {i}",
                   "aspects": [{"aspect": "cushion", "category": "durability", "sentiment": "negative", "severity": 3}]}
                  for i in range(4)]
        d = minimal(reviews={"source": "rv", "items": items})
        rv = evaluate(d)["evaluations"][0]["reviews"]
        self.assertEqual(rv["analysed"], 5)
        self.assertEqual(rv["duplicates_removed"], 5)
        self.assertEqual(rv["aspects"]["cushion"]["negative_share_of_reviews"], 80.0)
        self.assertIn("exact text", " ".join(rv["authenticity"]["signals"]))

    def test_too_few_reviews_not_scored(self):
        d = minimal(reviews={"source": "rv", "items": [{"rating": 5, "text": "nice"}]})
        e = evaluate(d)["evaluations"][0]
        self.assertNotIn("customer_experience", e["dimensions"])

    def _with_complaint(self, severity):
        items = [{"rating": 4, "text": f"fine chair {i}"} for i in range(6)]
        items.append({"rating": 1, "text": "Chair tipped backwards and I fell", "aspects": [
            {"aspect": "tipping", "category": "safety", "sentiment": "negative", "severity": severity, "quote": "tipped backwards"}]})
        return evaluate(minimal(reviews={"source": "rv", "items": items}))["evaluations"][0]

    def test_dangerous_incident_puts_product_on_safety_hold(self):
        e = self._with_complaint(5)
        self.assertEqual(e["eligibility"], "SAFETY_HOLD")
        self.assertTrue(any("dangerous" in r for r in e["eligibility_reasons"]))

    def test_serious_complaint_makes_provisional_at_least(self):
        e = self._with_complaint(4)
        self.assertTrue(any("safety complaints" in r for r in e["eligibility_reasons"]))
        self.assertNotEqual(e["eligibility"], "ELIGIBLE")

    def test_reported_wear_counts_against_durability(self):
        items = [{"rating": 4, "text": f"good {i}"} for i in range(8)]
        items += [{"rating": 2, "text": f"armrest cracked {i}", "aspects": [
            {"aspect": "armrest", "category": "defect", "sentiment": "negative", "severity": 3}]} for i in range(2)]
        e = evaluate(minimal(reviews={"source": "rv", "items": items}))["evaluations"][0]
        wear = next(c for c in e["dimensions"]["durability"]["criteria"] if c["name"] == "reported wear and early failures")
        self.assertAlmostEqual(wear["score"], 60.0)

    def test_other_variant_reviews_less_confident(self):
        items = [{"rating": 4, "text": f"good chair {i}"} for i in range(12)]
        a = evaluate(minimal(reviews={"source": "rv", "items": items}))["evaluations"][0]
        b = evaluate(minimal(reviews={"source": "rv", "variant_match": "other_variant", "items": items}))["evaluations"][0]
        self.assertLess(b["dimensions"]["customer_experience"]["confidence"], a["dimensions"]["customer_experience"]["confidence"])


class Materials(unittest.TestCase):
    def test_grade_never_assumed(self):
        self.assertTrue(materials.find("aluminium alloy")["grade_unknown"])
        self.assertIsNone(materials.find("6061"), "a bare alloy number doesn't imply a temper")
        self.assertEqual(materials.find("6061-T6")["id"], "al-6061-t6")

    def test_unknown_grade_lowers_confidence_and_widens_range(self):
        app = "office_chair_frame"
        known, generic = materials.suitability(materials.find("6061-T6"), app), materials.suitability(materials.find("aluminium"), app)
        self.assertLess(known["spread"][1] - known["spread"][0], generic["spread"][1] - generic["spread"][0])
        self.assertLessEqual(generic["spread"][0], generic["score"])
        self.assertGreaterEqual(generic["spread"][1], generic["score"])

    def test_incomplete_without_required_property(self):
        self.assertFalse(materials.suitability(materials.find("abs"), "office_chair_frame")["complete"])

    def test_measured_property_overrides_catalogue(self):
        from shelfscout.core.units import Quantity
        r = materials.suitability(materials.find("aluminium"), "office_chair_frame", {"yield_strength": Quantity(260, "MPa"),
                                                                                    "fatigue_strength": Quantity(140, "MPa")})
        self.assertTrue(any("(measured)" in u for u in r["used"]))


class Ergonomics(unittest.TestCase):
    def test_seat_height_fit_uses_body(self):
        d = example("office-chair")
        d["user"]["body"]["popliteal_height_cm"] = 36   # short sitter: chair too high
        e = by_id(evaluate(d))["ergoone"]
        fit = next(c for c in e["dimensions"]["ergonomics"]["criteria"] if c["name"] == "seat height fits you")
        self.assertLess(fit["score"], 100)


class TransparencyFixes(unittest.TestCase):
    def test_partial_seat_depth_fit_is_not_full_marks(self):
        d = example("office-chair")
        ergo = next(x for x in d["products"] if x["id"] == "ergoone")
        for c in ergo["claims"]:
            if c["claim_type"] == "ergonomics.seat_depth":
                c["value"] = {"min": 430, "max": 490}
        e = by_id(evaluate(d))["ergoone"]
        fit = next(c for c in e["dimensions"]["ergonomics"]["criteria"] if c["name"] == "seat depth fits you")
        self.assertLess(fit["score"], 90)
        self.assertIn("shallowest", fit["basis"])

    def test_priorities_drive_the_recommendation(self):
        r = evaluate(example("smartphone"))
        self.assertEqual(r["rankings"]["recommended_by"], "the category weights")
        d = example("office-chair")
        r = evaluate(d)
        self.assertEqual(r["rankings"]["recommended_by"], "your priorities")
        self.assertIn("on your priorities", markdown.render(r))

    def test_unknowns_limitations_and_unscored_claims_reach_the_report(self):
        d = example("office-chair")
        ergo = next(x for x in d["products"] if x["id"] == "ergoone")
        ergo["claims"].append({"id": "x9", "claim_type": "durability.design_life_years", "status": "MANUFACTURER_REPORTED",
                               "value": 10, "source": "ergo-site"})
        r = evaluate(d)
        md = markdown.render(r)
        self.assertIn("Looked for but not established:** material.frame_grade", md)
        self.assertIn("alloy grade not disclosed", md)
        self.assertIn("durability.design_life_years", md)
        self.assertIn("material.frame_grade", html_report.render(r))

    def test_no_requirements_on_record_is_said(self):
        e = by_id(evaluate(example("office-chair")))["ergoone"]
        self.assertTrue(any("No mandatory safety requirements are on record" in n for n in e["notes"]))


class Identity(unittest.TestCase):
    def test_matching(self):
        a = {"name": "Nova 8 128GB", "brand": "Nova", "model_number": "N8", "variant": {"storage": "128GB"}}
        self.assertEqual(compare({**a, "gtin": "0123456789012"}, {**a, "gtin": "0123456789012"})["verdict"], "same_variant")
        self.assertEqual(compare(a, {**a, "variant": {"storage": "256GB"}})["verdict"], "same_product_other_variant")
        self.assertEqual(compare(a, {**a, "model_number": "N9"})["verdict"], "different")
        self.assertEqual(compare({"name": "Nova 8 phone black 128GB"}, {"name": "Nova 8 phone black 256GB"})["verdict"],
                         "possible_match")


class Tco(unittest.TestCase):
    def test_missing_parts_listed(self):
        r = tco(Money(25000, "INR"), 5, maintenance_per_year=500, energy_kwh_per_year=120, energy_price_per_kwh=8)
        self.assertEqual(r["total"], Money("32300.00", "INR"))
        self.assertEqual(r["missing"], ["consumables", "repairs"])


class StoreAndReports(unittest.TestCase):
    def test_store_roundtrip_and_immutability(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "s.db"
            req = example("office-chair")
            res = evaluate(req)
            eid = store.save(db, req, res)
            self.assertEqual(store.load(db, eid)["result"]["input_hash"], res["input_hash"])
            self.assertEqual(len(store.history(db, "ErgoOne")), 1)
            con = sqlite3.connect(str(db))
            with self.assertRaises(sqlite3.DatabaseError):
                con.execute("UPDATE evaluations SET category = 'x'")
            con.close()

    def test_reports(self):
        d = example("office-chair")
        d["products"][0]["name"] = "<script>alert(1)</script> | chair"
        res = evaluate(d)
        md = markdown.render(res)
        self.assertIn("## Verdict", md)
        self.assertIn("uncalibrated", md)
        self.assertIn("\\|", md)
        page = html_report.render(res)
        self.assertNotIn("<script>", page)
        self.assertNotIn("http://", page)

    def test_cli_from_another_folder(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "r.html"
            res = subprocess.run([sys.executable, str(ROOT / "scripts" / "shelf.py"), "evaluate",
                                  str(EX / "smartphone" / "request.json"), "--html", str(out), "--save"],
                                 cwd=d, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(out.is_file())
            self.assertTrue((Path(d) / "shelfscout-data" / "shelfscout.db").is_file())
            bad = subprocess.run([sys.executable, str(ROOT / "scripts" / "shelf.py"), "evaluate", str(EX / "smartphone")],
                                 cwd=d, capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(bad.returncode, 0)


if __name__ == "__main__":
    unittest.main()
