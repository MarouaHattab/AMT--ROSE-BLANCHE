import requests
import json
import sys

API_URL = "http://127.0.0.1:8000/api/v1/search/"

# ═══════════════════════════════════════════════════════════════════
# GROUND TRUTH — extracted from the 35 TDS markdown files
# ═══════════════════════════════════════════════════════════════════

GROUND_TRUTH = {
    # ── Ascorbic Acid ──
    "ascorbic acid": {
        "products": ["Acide Ascorbique (E300)"],
        "dosage_ppm": "20–300",
        "type": "Oxidant / Vitamin C / E300",
    },
    # ── Glucose Oxidase ──
    "glucose oxidase": {
        "products": ["BVZyme GOX 110", "BVZyme GO MAX 63", "BVZyme GO MAX 65"],
        "dosage_ppm": "5–50",
        "type": "Glucose oxidase",
    },
    # ── Alpha-Amylase (Fungal) ──
    "alpha-amylase": {
        "products": ["BVZyme AF110", "BVZyme AF220", "BVZyme AF330", "BVZyme AF SX"],
        "dosage_ppm": "2–25",
        "type": "Fungal α-amylase",
    },
    # ── Maltogenic Amylase ──
    "maltogenic amylase": {
        "products": [
            "BVZyme A FRESH101", "BVZyme A FRESH202", "BVZyme A FRESH303",
            "BVZyme A SOFT205", "BVZyme A SOFT305", "BVZyme A SOFT405",
        ],
        "dosage_ppm": "10–100",
        "type": "Maltogenic amylase",
    },
    # ── Lipase ──
    "lipase": {
        "products": [
            "BVZyme L MAX X", "BVZyme L MAX63", "BVZyme L MAX64",
            "BVZyme L MAX65", "BVZyme L55", "BVZyme L65",
        ],
        "dosage_ppm": "2–60",
        "type": "Lipase / Phospholipase",
    },
    # ── Amyloglucosidase ──
    "amyloglucosidase": {
        "products": ["BVZyme AMG880", "BVZyme AMG1400"],
        "dosage_ppm": "10–100",
        "type": "Amyloglucosidase / Glucoamylase",
    },
    # ── Transglutaminase ──
    "transglutaminase": {
        "products": ["BVZyme TG881", "BVZyme TG883", "BVZyme TG MAX63", "BVZyme TG MAX64"],
        "dosage_ppm": "5–40",
        "type": "Transglutaminase",
    },
    # ── Xylanase (Bacterial) ──
    "bacterial xylanase": {
        "products": ["BVZyme HCB708", "BVZyme HCB709", "BVZyme HCB710"],
        "dosage_ppm": "5–30",
        "type": "Bacterial xylanase",
    },
    # ── Xylanase (Fungal) ──
    "fungal xylanase": {
        "products": [
            "BVZyme HCF400", "BVZyme HCF500", "BVZyme HCF600",
            "BVZyme HCF MAX X", "BVZyme HCF MAX63", "BVZyme HCF MAX64",
        ],
        "dosage_ppm": "0.5–70",
        "type": "Fungal xylanase",
    },
}

# ═══════════════════════════════════════════════════════════════════
# TEST CASES — question + expected ingredients in top results
# ═══════════════════════════════════════════════════════════════════

TEST_CASES = [
    # ─── Multi-ingredient queries ───────────────────────────────
    {
        "id": "T01",
        "name": "Challenge question (FR) — 3 ingredients",
        "question": "Quelles sont les quantites recommandees d acide ascorbique, d alpha-amylase et de xylanase pour l amelioration de la panification?",
        "top_k": 3,
        "expected_ingredients": ["ascorbic acid", "alpha-amylase", "xylanase"],
        "min_coverage": 1.0,         # all 3 must appear
        "min_avg_score": 0.70,
    },
    {
        "id": "T02",
        "name": "Challenge question (EN) — 3 ingredients",
        "question": "What are the recommended quantities of ascorbic acid, alpha-amylase and xylanase for bread improvement?",
        "top_k": 3,
        "expected_ingredients": ["ascorbic acid", "alpha-amylase", "xylanase"],
        "min_coverage": 1.0,
        "min_avg_score": 0.70,
    },
    {
        "id": "T03",
        "name": "Transglutaminase + Glucose oxidase (FR)",
        "question": "Quel est le dosage de transglutaminase et de glucose oxydase pour le pain?",
        "top_k": 3,
        "expected_ingredients": ["transglutaminase", "glucose oxidase"],
        "min_coverage": 1.0,
        "min_avg_score": 0.60,
    },
    {
        "id": "T04",
        "name": "Lipase + AMG (EN)",
        "question": "What is the dosage of lipase and amyloglucosidase for bakery?",
        "top_k": 3,
        "expected_ingredients": ["lipase", "amyloglucosidase"],
        "min_coverage": 1.0,
        "min_avg_score": 0.55,
    },

    # ─── Single-ingredient queries ──────────────────────────────
    {
        "id": "T05",
        "name": "Lipase dosage (EN)",
        "question": "What is the recommended dosage of lipase for bread softness?",
        "top_k": 3,
        "expected_ingredients": ["lipase"],
        "min_coverage": 1.0,
        "min_avg_score": 0.55,
    },
    {
        "id": "T06",
        "name": "Anti-staling / shelf life (EN)",
        "question": "What enzyme prevents bread staling and extends shelf life?",
        "top_k": 3,
        "expected_ingredients": ["maltogenic amylase"],
        "min_coverage": 1.0,
        "min_avg_score": 0.50,
    },
    {
        "id": "T07",
        "name": "Dough tolerance + fermentation (EN)",
        "question": "Which enzyme improves dough tolerance and fermentation?",
        "top_k": 3,
        "expected_ingredients": ["glucose oxidase"],
        "min_coverage": 1.0,
        "min_avg_score": 0.55,
    },
    {
        "id": "T08",
        "name": "Ascorbic acid dosage (FR)",
        "question": "Quel est le dosage recommande d acide ascorbique pour la panification?",
        "top_k": 3,
        "expected_ingredients": ["ascorbic acid"],
        "min_coverage": 1.0,
        "min_avg_score": 0.55,
        "min_unique_docs": 2,  # only 1 source file → max 1 doc_id, but MMR may pull a related doc
    },
    {
        "id": "T09",
        "name": "Golden crust color (EN)",
        "question": "Which enzyme gives golden crust color to bread?",
        "top_k": 3,
        "expected_ingredients": ["amyloglucosidase"],
        "min_coverage": 1.0,
        "min_avg_score": 0.45,
    },
    {
        "id": "T10",
        "name": "Gluten network strength (EN)",
        "question": "What enzyme strengthens gluten networks in dough?",
        "top_k": 3,
        "expected_ingredients": ["glucose oxidase"],
        "min_coverage": 1.0,
        "min_avg_score": 0.50,
    },
    {
        "id": "T11",
        "name": "Xylanase for volume (EN)",
        "question": "Recommended dosage of xylanase for improving loaf volume?",
        "top_k": 3,
        "expected_ingredients": ["xylanase"],
        "min_coverage": 1.0,
        "min_avg_score": 0.55,
    },
    {
        "id": "T12",
        "name": "Transglutaminase for texture (EN)",
        "question": "How much transglutaminase to improve bread texture and elasticity?",
        "top_k": 3,
        "expected_ingredients": ["transglutaminase"],
        "min_coverage": 1.0,
        "min_avg_score": 0.55,
    },
]

# ═══════════════════════════════════════════════════════════════════
# INGREDIENT DETECTION IN RESULT TEXT
# ═══════════════════════════════════════════════════════════════════

INGREDIENT_KEYWORDS = {
    "ascorbic acid":       ["ascorbic", "acide ascorbique", "e300", "vitamin c"],
    "alpha-amylase":       ["alpha-amylase", "α-amylase", "fungal amylase", "af110", "af220", "af330", "af sx"],
    "xylanase":            ["xylanase", "endo-xylanase", "hcb7", "hcf"],
    "lipase":              ["lipase", "phospholipase", "bvzyme l"],
    "glucose oxidase":     ["glucose oxidase", "glucose oxydase", "gox", "go max"],
    "transglutaminase":    ["transglutaminase", "tg881", "tg883", "tg max"],
    "amyloglucosidase":    ["amyloglucosidase", "glucoamylase", "amg880", "amg1400"],
    "maltogenic amylase":  ["maltogenic", "anti-staling", "a fresh", "a soft"],
}


def ingredient_in_text(ingredient: str, text: str) -> bool:
    """Check if a result text mentions a given ingredient."""
    lower = text.lower()
    keywords = INGREDIENT_KEYWORDS.get(ingredient, [ingredient])
    return any(kw in lower for kw in keywords)


# ═══════════════════════════════════════════════════════════════════
# TEST RUNNER
# ═══════════════════════════════════════════════════════════════════

def run_test(test_case: dict) -> dict:
    """Run a single test case and return pass/fail + details."""
    tid = test_case["id"]
    payload = {
        "question": test_case["question"],
        "top_k": test_case["top_k"],
    }

    try:
        resp = requests.post(API_URL, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"id": tid, "pass": False, "error": str(e)}

    results = data.get("results", [])
    metrics = data.get("metrics", {})

    # ── Check 1: Coverage — each expected ingredient in at least 1 result ──
    expected = test_case["expected_ingredients"]
    covered = []
    missing = []
    for ing in expected:
        found = any(ingredient_in_text(ing, r["text"]) for r in results)
        if found:
            covered.append(ing)
        else:
            missing.append(ing)

    coverage = len(covered) / len(expected) if expected else 0.0
    coverage_pass = coverage >= test_case["min_coverage"]

    # ── Check 2: Average score threshold ──
    scores = [r["score"] for r in results]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    score_pass = avg_score >= test_case["min_avg_score"]

    # ── Check 3: Unique documents (allow configurable minimum) ──
    doc_ids = [r["document_id"] for r in results]
    unique_docs = len(set(doc_ids))
    min_unique = test_case.get("min_unique_docs", len(doc_ids))  # default: all unique
    diversity_pass = unique_docs >= min_unique

    overall_pass = coverage_pass and score_pass and diversity_pass

    # ── Recall@3: fraction of expected ingredients found in top-3 results ──
    recall_at_3 = len(covered) / len(expected) if expected else 0.0

    # ── MRR@3: reciprocal rank of the first relevant result ──
    reciprocal_rank = 0.0
    for r in sorted(results, key=lambda x: x["rank"]):
        if any(ingredient_in_text(ing, r["text"]) for ing in expected):
            reciprocal_rank = 1.0 / r["rank"]
            break

    return {
        "id": tid,
        "name": test_case["name"],
        "pass": overall_pass,
        "coverage": f"{len(covered)}/{len(expected)}",
        "coverage_pass": coverage_pass,
        "missing_ingredients": missing,
        "scores": [round(s, 4) for s in scores],
        "avg_score": round(avg_score, 4),
        "score_pass": score_pass,
        "unique_docs": unique_docs,
        "diversity_pass": diversity_pass,
        "recall_at_3": round(recall_at_3, 4),
        "reciprocal_rank": round(reciprocal_rank, 4),
        "results_summary": [
            f"#{r['rank']} score={r['score']:.4f} doc={r['document_id']}"
            for r in results
        ],
    }


def run_all_tests():
    """Run all test cases and print summary."""
    print("=" * 72)
    print("  ROSE BLANCHE RAG — Search Accuracy Test Suite")
    print("=" * 72)

    passed = 0
    failed = 0
    all_results = []

    for tc in TEST_CASES:
        result = run_test(tc)
        all_results.append(result)

        status = "PASS ✓" if result["pass"] else "FAIL ✗"
        print(f"\n{'─' * 72}")
        print(f"  [{result['id']}] {result['name']}  →  {status}")
        print(f"    Coverage:  {result['coverage']}  {'✓' if result['coverage_pass'] else '✗ MISSING: ' + ', '.join(result['missing_ingredients'])}")
        print(f"    Recall@3:  {result['recall_at_3']:.4f}")
        print(f"    RR@3:      {result['reciprocal_rank']:.4f}")
        print(f"    Avg Score: {result['avg_score']:.4f}  {'✓' if result['score_pass'] else '✗'}")
        print(f"    Diversity: {result['unique_docs']} unique docs  {'✓' if result['diversity_pass'] else '✗ DUPLICATE'}")
        print(f"    Scores:    {result['scores']}")

        if result["pass"]:
            passed += 1
        else:
            failed += 1

    # ── Summary ──
    total = passed + failed
    accuracy = passed / total * 100 if total else 0

    all_avg_scores = [r["avg_score"] for r in all_results if r.get("avg_score")]
    global_avg = sum(all_avg_scores) / len(all_avg_scores) if all_avg_scores else 0

    # ── Recall@3 & MRR@3 aggregation ──
    all_recall = [r["recall_at_3"] for r in all_results if "recall_at_3" in r]
    all_rr = [r["reciprocal_rank"] for r in all_results if "reciprocal_rank" in r]
    mean_recall_at_3 = sum(all_recall) / len(all_recall) if all_recall else 0.0
    mrr_at_3 = sum(all_rr) / len(all_rr) if all_rr else 0.0

    print(f"\n{'═' * 72}")
    print(f"  SUMMARY")
    print(f"{'═' * 72}")
    print(f"  Tests:           {total}")
    print(f"  Passed:          {passed}")
    print(f"  Failed:          {failed}")
    print(f"  Accuracy:        {accuracy:.1f}%")
    print(f"  Global Avg Score: {global_avg:.4f}")
    print(f"  Mean Recall@3:   {mean_recall_at_3:.4f}")
    print(f"  MRR@3:           {mrr_at_3:.4f}")
    print(f"{'═' * 72}")

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "accuracy_pct": round(accuracy, 1),
        "global_avg_score": round(global_avg, 4),
        "mean_recall_at_3": round(mean_recall_at_3, 4),
        "mrr_at_3": round(mrr_at_3, 4),
        "details": all_results,
    }


if __name__ == "__main__":
    summary = run_all_tests()
    sys.exit(0 if summary["failed"] == 0 else 1)
