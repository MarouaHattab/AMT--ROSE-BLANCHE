"""
Comprehensive search quality test suite.
Tests dosage, function, disambiguation, and safety queries.
"""
import json
import urllib.request

API = "http://localhost:8000/api/v1/search/"

def search(question: str, top_k: int = 3) -> dict:
    data = json.dumps({"question": question, "top_k": top_k}).encode()
    req = urllib.request.Request(API, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

def run_test(label: str, question: str, expected_keywords: list, top_k: int = 3):
    """Run a single test and print results."""
    res = search(question, top_k)
    results = res.get("results", [])
    print(f"\n{'='*80}")
    print(f"[{label}] Q: {question}")
    print(f"  Expected keywords: {expected_keywords}")
    print(f"  Results ({len(results)}):")
    
    found_keywords = []
    for r in results:
        txt = r["text"][:300]
        score = r["score"]
        # Check which expected keywords appear
        matched = [kw for kw in expected_keywords if kw.lower() in r["text"].lower()]
        found_keywords.extend(matched)
        status = "MATCH" if matched else "---"
        print(f"    Rank {r['rank']} (score={score:.4f}) [{status}]: {txt[:200]}...")
        if matched:
            print(f"      -> Found: {matched}")
    
    missing = [kw for kw in expected_keywords if kw.lower() not in [k.lower() for k in found_keywords]]
    if missing:
        print(f"  MISSING keywords in top-{top_k}: {missing}")
    else:
        print(f"  ALL KEYWORDS FOUND in top-{top_k}")
    
    return len(missing) == 0

# ═══════════════════════════════════════════════════════════════
#  A) DOSAGE-FOCUSED QUESTIONS
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*80)
print("SECTION A: DOSAGE-FOCUSED QUESTIONS")
print("="*80)

tests_a = [
    ("A1", "What is the recommended dosage for BVZyme AF330?", ["AF330", "2-10 ppm"]),
    ("A2", "AF110 dosage in ppm?", ["AF110"]),
    ("A3", "What dosage range is given for BVZyme GOX 110 (glucose oxidase)?", ["GOX 110", "5-40 ppm"]),
    ("A4", "GO MAX 63 dosage?", ["GO MAX 63", "5-50 ppm"]),
    ("A5", "What is the dosage range for BVZyme TG MAX63 (transglutaminase)?", ["TG MAX63", "5-25 ppm"]),
    ("A6", "What dosage is suggested for BVZyme A SOFT305?", ["SOFT 305"]),
    ("A7", "What is the dosage range for A FRESH202?", ["FRESH202", "10-90 ppm"]),
    ("A8", "A FRESH101 dosage range?", ["FRESH101", "15-100 ppm"]),
    ("A9", "What dosage is recommended for AMG880 (amyloglucosidase)?", ["AMG880", "10-100 ppm"]),
    ("A10", "For ascorbic acid (E300), what dosage is recommended for standard direct breadmaking?", ["Ascorbique", "20-60"]),
    ("A11", "For ascorbic acid (E300), what dosage is recommended for frozen (surgelation) dough?", ["Ascorbique", "150-200"]),
    ("A12", "What is the maximum authorized dosage for ascorbic acid (E300)?", ["Ascorbique", "300"]),
]

# ═══════════════════════════════════════════════════════════════
#  B) FUNCTION / APPLICATION QUESTIONS
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*80)
print("SECTION B: FUNCTION / APPLICATION QUESTIONS")
print("="*80)

tests_b = [
    ("B1", "Which product is used to improve bread freshness and extend shelf life?", ["FRESH", "freshness"]),
    ("B2", "Which enzyme strengthens gluten networks?", ["gluten"]),
    ("B3", "Which product is a lipase used in bakery and what does it do?", ["Lipase", "crumb"]),
    ("B4", "What does AF330 do in baking?", ["AF330", "damaged starch"]),
    ("B5", "What is the role of ascorbic acid (E300) in breadmaking?", ["Ascorbique"]),
]

# ═══════════════════════════════════════════════════════════════
#  C) DISAMBIGUATION QUESTIONS
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*80)
print("SECTION C: DISAMBIGUATION QUESTIONS")
print("="*80)

tests_c = [
    ("C1", "Which product is an enzyme preparation based on glucose oxidase produced by Aspergillus niger and Trichoderma reesei?", ["GO MAX 65"]),
    ("C2", "Which product is based on maltogenic amylase and has activity 10,000 NMAU/g?", ["FRESH101"]),
    ("C3", "Which product is fungal amyloglucosidase (Aspergillus niger) and what dosage is used?", ["AMG"]),
]

# ═══════════════════════════════════════════════════════════════
#  D) SAFETY / STORAGE / PACKAGING QUESTIONS
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*80)
print("SECTION D: SAFETY / STORAGE / PACKAGING QUESTIONS")
print("="*80)

tests_d = [
    ("D1", "What storage condition is recommended for these enzyme powders?", ["Storage", "cool"]),
    ("D2", "What allergen is declared in the enzyme product sheets?", ["gluten"]),
    ("D3", "What is the packaging format mentioned?", ["25 kg"]),
]

# Run all tests
all_tests = tests_a + tests_b + tests_c + tests_d
passed = 0
failed = 0
failed_list = []

for label, question, keywords in all_tests:
    try:
        if run_test(label, question, keywords):
            passed += 1
        else:
            failed += 1
            failed_list.append(label)
    except Exception as e:
        print(f"\n[{label}] ERROR: {e}")
        failed += 1
        failed_list.append(label)

print("\n" + "="*80)
print(f"SUMMARY: {passed}/{passed+failed} tests passed")
if failed_list:
    print(f"FAILED: {', '.join(failed_list)}")
print("="*80)
