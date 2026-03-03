from .BaseController import BaseController
from models.db_schemes import Document, Embedding
from stores.embedding.EmbeddingService import EmbeddingService
from typing import List, Dict, Optional, Tuple
import os
import re
import logging

logger = logging.getLogger("uvicorn")

# ── Company boilerplate patterns to strip from TDS PDFs ──────────
_VTR_ADDRESS_BLOCK = re.compile(
    r'VTR\s*&\s*beyond\s*\n.*?(?:vtrbeyond\.com|www\.vtrbeyond\.com)',
    re.DOTALL | re.IGNORECASE,
)
_LAST_UPDATING = re.compile(r'Last\s+updat(?:ing|ed)\s*:?\s*\d{2}/\d{2}/\d{4}', re.IGNORECASE)
_COMPANY_CONTACTS = re.compile(
    r'(?:No\.\s*8,?\s*Pingbei|Stresemann\s+str|Tel:\s*\+?\d|Mail:\s*info@|Website:\s*www\.)[^\n]*',
    re.IGNORECASE,
)
_TECH_DATA_SHEET_HEADER = re.compile(r'TECH\s*N?\s*ICAL\s+DATA\s+SHEET', re.IGNORECASE)

# ── Known TDS section labels (PyPDF2 often concatenates them with values) ──
_TDS_LABELS = [
    "Product Description", "Effective material", "Activity", "Application",
    "Function", "Dosage", "Organoleptic", "Physicochemical", "Moisture",
    "Aspect", "Color", "Bakery Enzyme", "FOOD SAFTY DATA", "FOOD SAFETY DATA",
    "Microbiology", "Heavy metals", "Heavy metal", "Allergens", "GMO status",
    "Ionization status", "Package", "Packaging", "Storage",
    "Date of minimum durability", "Date of Minimum Durability",
]

# ── Enzyme type identifiers by product family ────────────────────
_ENZYME_FAMILIES = {
    "GOX": "Glucose oxidase",
    "GO MAX": "Glucose oxidase",
    "TG": "Transglutaminase",
    "A FRESH": "Maltogenic amylase (anti-staling)",
    "A SOFT": "Amylase blend (softness extension)",
    "AF": "Fungal alpha-amylase",
    "AMG": "Amyloglucosidase (Glucoamylase)",
    "L MAX": "Lipase (phospholipase)",
    "L55": "Lipase",
    "L65": "Lipase",
    "HCF": "Fungal xylanase (hemicellulase)",
    "HCB": "Bacterial xylanase (hemicellulase)",
}


class DataController(BaseController):
    def __init__(self, embedding_service: EmbeddingService):
        super().__init__()
        self.embedding_service = embedding_service

    # ═══════════════════════════════════════════════════════════════
    #  FILE READING
    # ═══════════════════════════════════════════════════════════════

    def read_file_content(self, file_path: str) -> str:
        """Read content from a PDF file."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            return self._read_pdf(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}. Only PDF files are supported.")

    def _read_pdf(self, file_path: str) -> str:
        """Extract text from a PDF file using PyPDF2."""
        import warnings
        from PyPDF2 import PdfReader

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            reader = PdfReader(file_path)
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text.strip())
        return "\n\n".join(pages)

    # ═══════════════════════════════════════════════════════════════
    #  TDS DETECTION & STRUCTURED EXTRACTION
    # ═══════════════════════════════════════════════════════════════

    def _is_bvzyme_tds(self, text: str, filename: str) -> bool:
        """Detect if a PDF is a BVZyme Technical Data Sheet."""
        fname_lower = filename.lower()
        text_lower = text.lower()
        # Also check concatenated forms (some PDFs extract without spaces)
        has_bvzyme = "bvzyme" in fname_lower or "tds" in fname_lower
        has_enzyme = (
            "bakery enzyme" in text_lower
            or "enzyme preparation" in text_lower
            or "bakeryenzyme" in text_lower
            or "enzymepreparation" in text_lower
        )
        return has_bvzyme and has_enzyme and len(text) < 6000

    def _extract_product_name(self, text: str, filename: str) -> str:
        """Extract the BVZyme product name from garbled TDS text."""
        # Pattern: "BVZyme XXXX ®" or "BVZyme XXXX®" (with optional spaces)
        m = re.search(
            r'(BVZyme\s*(?:A\s+)?(?:GOX|GO\s*MAX|TG\s*MAX|TG\s*88|A\s*FRESH|A\s*SOFT|'
            r'AF?\s*\d|AF?\s*SX|AMG|L\s*MAX|L\s*55|L\s*65|HC[BF]\s*(?:MAX)?\s*\w+)'
            r'[^®\n]*?)\s*®',
            text, re.IGNORECASE
        )
        if m:
            name = re.sub(r'\s+', ' ', m.group(1)).strip()
            # Fix stray spaces in product codes: "TG88 3" -> "TG883", "HCF5 00" -> "HCF500"
            name = re.sub(r'(\d)\s+(\d)', r'\1\2', name)
            return f"{name}®"

        # Also try concatenated form: "BVZymeAFSX®"
        m2 = re.search(
            r'(BVZyme\s*(?:GOX|GOMAX|TGMAX|TG\d+|AFRESH|ASOFT|AF\w*|AMG\w*|'
            r'LMAX|L\d+|HCF\w*|HCB\w*)\d*)\s*®',
            text, re.IGNORECASE
        )
        if m2:
            raw = m2.group(1).strip()
            # Re-insert spaces: "BVZymeAFSX" -> "BVZyme AF SX"
            name = re.sub(r'(BVZyme)([A-Z])', r'\1 \2', raw)
            # Insert space before product family abbreviation
            name = re.sub(r'(BVZyme )([A-Z]+)(\d+)', r'\1\2 \3', name)
            return f"{name}®"

        # Fallback: derive from filename
        base = os.path.splitext(filename)[0]
        # Remove "TDS" prefix/suffix and parenthetical numbers
        base = re.sub(r'\bTDS\b', '', base, flags=re.IGNORECASE).strip()
        base = re.sub(r'\(\d+\)', '', base).strip()
        # Normalize: "BVZymeTDSAF SX" -> "BVZyme AF SX"
        base = re.sub(r'^BVZyme\s*', 'BVZyme ', base)
        return f"{base}®"

    def _extract_short_code(self, product_name: str) -> str:
        """Extract short product code, e.g. 'BVZyme AF330®' → 'AF330'."""
        code = re.sub(r'^BVZyme\s*', '', product_name)
        code = re.sub(r'\s*®\s*$', '', code)
        return code.strip()

    def _identify_enzyme_family(self, product_name: str) -> str:
        """Determine the enzyme family/type from the product name."""
        name_upper = product_name.upper()
        # Check from longest key first to match "GO MAX" before "GO"
        for key in sorted(_ENZYME_FAMILIES.keys(), key=len, reverse=True):
            if key.upper() in name_upper:
                return _ENZYME_FAMILIES[key]
        return "Bakery enzyme"

    def _clean_tds_text(self, text: str) -> str:
        """Remove boilerplate, fix garbled PDF extraction for TDS files."""
        # Normalize fullwidth characters (common in these PDFs)
        text = text.replace('\uff1a', ':').replace('\u00a0', ' ')
        text = text.replace('£¨', '(').replace('£©', ')')

        # Fix concatenated words (some PDFs extract without spaces)
        # Insert spaces between lowercase→uppercase transitions
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
        # Insert spaces before known keywords stuck to values
        text = re.sub(
            r'(\d)(?=(?:Dosage|Function|Application|Activity|Organoleptic|'
            r'Aspect|Color|Package|Storage|Microbiology|Allergen|GMO))',
            r'\1 ', text, flags=re.IGNORECASE
        )

        # Remove VTR&beyond address blocks (appears 2x per TDS)
        text = _VTR_ADDRESS_BLOCK.sub('', text)
        text = _LAST_UPDATING.sub('', text)
        text = _COMPANY_CONTACTS.sub('', text)
        text = _TECH_DATA_SHEET_HEADER.sub('', text)

        # Remove "Zone, Nanping..." lines
        text = re.sub(r'Zone,?\s*Nanping[^\n]*', '', text, flags=re.IGNORECASE)

        # Remove excessive blank lines
        text = re.sub(r'\n\s*\n', '\n', text)
        text = re.sub(r'[ \t]+', ' ', text)

        return text.strip()

    def _extract_tds_field(self, text: str, label: str, next_labels: List[str] = None) -> str:
        """Extract a field value from TDS text. Handles garbled label-value patterns."""
        patterns = []

        # Pattern 1: "Label: value" or "Label value"
        patterns.append(re.compile(
            rf'{re.escape(label)}\s*:?\s*(.+?)(?:\n|$)',
            re.IGNORECASE
        ))

        # Pattern 2: "valueLabel" (concatenated, e.g., "5-40Dosage")
        if label in ("Dosage", "Function", "Application", "Activity"):
            patterns.append(re.compile(
                rf'([\d\-–,.\s]+(?:ppm|U/g|SKB/g|FAU/g|AGI/g|NMAU/g|XylH/g)?)[\s]*{re.escape(label)}',
                re.IGNORECASE
            ))

        for pat in patterns:
            m = pat.search(text)
            if m:
                val = m.group(1).strip()
                # Clean trailing labels from the value
                if next_labels:
                    for nl in next_labels:
                        idx = val.lower().find(nl.lower())
                        if idx > 0:
                            val = val[:idx]
                val = val.strip().rstrip('.:,;')
                if val and len(val) > 1:
                    return val
        return ""

    def _parse_tds_structured(self, raw_text: str, filename: str) -> Dict[str, str]:
        """Parse a BVZyme TDS into structured fields."""
        text = self._clean_tds_text(raw_text)
        product_name = self._extract_product_name(raw_text, filename)
        enzyme_family = self._identify_enzyme_family(product_name)

        fields = {"product_name": product_name, "enzyme_type": enzyme_family}

        # ── Extract Effective Material / Source organism ──
        eff_mat = ""
        # Look for known organism names that appear in these TDS PDFs
        organism_patterns = [
            # Combined organism patterns first (e.g. GO MAX 65 uses both)
            r'(?:strain\s+(?:of\s+)?)?(Aspergillus\s+niger\s+and\s+Trichoderma\s+reesei)',
            r'(?:strain\s+(?:of\s+)?)?(Aspergillus\s+niger)',
            r'(?:strain\s+(?:of\s+)?)?(Aspergillus\s+oryzae)',
            r'(?:strain\s+(?:of\s+)?)?(Bacillus\s+subtilis)',
            r'(?:strain\s+(?:of\s+)?)?(Streptomyces\s+mobaraensis)',
            r'(?:strain\s+(?:of\s+)?)?(Streptoverticillium\s+mobaraense)',
            r'(?:strain\s+(?:of\s+)?)?(Trichoderma\s+reesei)',
        ]
        for pat in organism_patterns:
            org_match = re.search(pat, text, re.IGNORECASE)
            if org_match:
                eff_mat = org_match.group(1).strip()
                break
        # Fallback: infer from enzyme family
        if not eff_mat:
            enzyme_upper = enzyme_family.upper()
            if 'TRANSGLUTAMINASE' in enzyme_upper:
                eff_mat = 'Streptomyces mobaraensis'
            elif 'GLUCOSE OXIDASE' in enzyme_upper:
                eff_mat = 'Aspergillus niger'
            elif 'LIPASE' in enzyme_upper or 'AMYLASE' in enzyme_upper:
                eff_mat = 'Aspergillus oryzae'
            elif 'XYLANASE' in enzyme_upper:
                eff_mat = 'Aspergillus niger'
            elif 'AMYLOGLUCOSIDASE' in enzyme_upper:
                eff_mat = 'Aspergillus niger'
        fields["source_organism"] = eff_mat

        # ── Activity ──
        # PyPDF2 garbles TDS layout: number and unit often end up on separate
        # lines, or merged with the word "Activity".  Try several patterns.
        activity_val = ""
        # P1: standard adjacent  "10000 U/g"
        act1 = re.search(
            r'(\d[\d\s,]*\d?)\s*(U/g|SKB/g|FAU/g|AGI/g|NMAU/g|Xyl\s*H/g)',
            text, re.IGNORECASE,
        )
        if act1:
            activity_val = f"{act1.group(1).strip()} {re.sub(r's+', '', act1.group(2))}"
        if not activity_val:
            # P2: number before "Activity"/"Effective material", unit on next line
            act2 = re.search(
                r'(\d{2,6})\s*(?:Activity|Effective\s*material)[\s\n]*'
                r'(U/g|SKB/g|FAU/g|AGI/g|NMAU/g|Xyl\s*H/g|/g)',
                text, re.IGNORECASE | re.DOTALL,
            )
            if act2:
                unit = act2.group(2).strip()
                if unit == '/g':
                    eu = enzyme_family.upper()
                    if 'XYLANASE' in eu or 'HEMICELLULASE' in eu:
                        unit = 'XylH/g'
                    elif 'AMYLOGLUCOSIDASE' in eu or 'GLUCOAMYLASE' in eu:
                        unit = 'AGI/g'
                    elif 'GLUCOSE OXIDASE' in eu:
                        unit = 'U/g'
                    elif 'AMYLASE' in eu:
                        unit = 'SKB/g'
                    else:
                        unit = 'U/g'
                activity_val = f"{act2.group(1).strip()} {re.sub(r's+', '', unit)}"
        if not activity_val:
            # P3: "400U/Activity\ng" — number+U/ glued to Activity, g on next line
            act3 = re.search(
                r'(\d{2,6})\s*U/\s*Activity[\s\n]*g\b',
                text, re.IGNORECASE,
            )
            if act3:
                activity_val = f"{act3.group(1).strip()} U/g"
        if not activity_val:
            # P3b: "70000 AGIActivity\n/g" — number + unit_prefix + Activity + /g
            act3b = re.search(
                r'(\d{2,6})\s*(AGI|SKB|FAU|NMAU|Xyl\s*H)\s*Activity[\s\n]*/g',
                text, re.IGNORECASE,
            )
            if act3b:
                activity_val = f"{act3b.group(1).strip()} {act3b.group(2).strip()}/g"
        if not activity_val:
            # P4: number before "Function" label, unit right after "Function"
            # e.g. "bread.10950\nFunction NMAU/g" or "applications.23500\nFunction Xyl H/g"
            act4 = re.search(
                r'(\d{2,6})\s*[\n\s]*Function\s*(NMAU/g|Xyl\s*H/g|U/g|SKB/g|FAU/g|AGI/g)',
                text, re.IGNORECASE,
            )
            if act4:
                activity_val = f"{act4.group(1).strip()} {act4.group(2).strip()}"
        if not activity_val:
            # P5: "7850 Activity\nFunction \nXyl H/g" — number before Activity,
            # unit after Function on a later line
            act5 = re.search(
                r'(\d{2,6})\s*Activity[\s\S]{0,40}?Function[\s\n]*(NMAU/g|Xyl\s*H/g|U/g|SKB/g|FAU/g|AGI/g)',
                text, re.IGNORECASE,
            )
            if act5:
                activity_val = f"{act5.group(1).strip()} {act5.group(2).strip()}"
        if not activity_val:
            # P6: "Effective material\n10000 U/BVZyme..." — number AFTER label
            act6 = re.search(
                r'Effective\s*material[\s\n]*(\d{2,6})\s*U/',
                text, re.IGNORECASE,
            )
            if act6:
                activity_val = f"{act6.group(1).strip()} U/g"
        fields["activity"] = activity_val

        # ── Dosage ──
        # PyPDF2 often splits "5-40 ppm" as "5-40Dosage\n ppm" or "5-40 Dosage\nppm"
        dos_val = ""
        # P1: standard "5-40 ppm"
        dos1 = re.search(r'(\d+\s*[-–]\s*\d+)\s*ppm', text, re.IGNORECASE)
        if dos1:
            dos_val = f"{dos1.group(1).strip()} ppm"
        if not dos_val:
            # P2: "5-40 Dosage" (number before label, ppm missing or on next line)
            dos2 = re.search(
                r'(\d+\s*[-–]\s*\d+)\s*Dosag\s*e[\s\n]*(?:ppm)?',
                text, re.IGNORECASE,
            )
            if dos2:
                dos_val = f"{dos2.group(1).strip()} ppm"
        if not dos_val:
            # P3: "Dosage\n15-35 ppm" or "Dosage\n15 -35\nppm"
            dos3 = re.search(
                r'Dosag\s*e[\s\n]*(\d+\s*[-–]\s*\d+)\s*(?:ppm)?',
                text, re.IGNORECASE,
            )
            if dos3:
                dos_val = f"{dos3.group(1).strip()} ppm"
        if not dos_val:
            # P4: "15-Dosage\n100 ppm" — range split across Dosage label
            dos4 = re.search(
                r'(\d+)\s*[-–]\s*Dosag\s*e[\s\n]*(\d+)\s*ppm',
                text, re.IGNORECASE,
            )
            if dos4:
                dos_val = f"{dos4.group(1).strip()}-{dos4.group(2).strip()} ppm"
        if not dos_val:
            # P5: "5-30 Activity\nppm" — range before Activity, ppm after
            dos5 = re.search(
                r'(\d+\s*[-–]\s*\d+)\s*Activity[\s\n]*ppm',
                text, re.IGNORECASE,
            )
            if dos5:
                dos_val = f"{dos5.group(1).strip()} ppm"
        if not dos_val:
            # P6: "10-90 Application\n ppm" — range before Application, ppm after
            dos6 = re.search(
                r'(\d+\s*[-–]\s*\d+)\s*Application[\s\n]*ppm',
                text, re.IGNORECASE,
            )
            if dos6:
                dos_val = f"{dos6.group(1).strip()} ppm"
        # Normalize dosage range order: ensure min-max (e.g. "5-2 ppm" -> "2-5 ppm")
        if dos_val:
            range_match = re.match(r'(\d+)\s*[-–]\s*(\d+)\s*ppm', dos_val)
            if range_match:
                lo, hi = int(range_match.group(1)), int(range_match.group(2))
                if lo > hi:
                    dos_val = f"{hi}-{lo} ppm"
        fields["dosage_ppm"] = dos_val

        # ── Application ──
        app_text = self._extract_application(text, enzyme_family)
        fields["application"] = app_text

        # ── Function ──
        func_text = self._extract_function(text)
        fields["function"] = func_text

        # ── Dosage details (for HCF with sub-ranges) ──
        dosage_details = []
        for dm in re.finditer(
            r'(Standardization\s+of\s+Wheat\s+Flour|Bread\s+Improvement|'
            r'Suggested\s+Optimum\s+Dosage)\s*([\d\-–]+\s*ppm)',
            text, re.IGNORECASE
        ):
            dosage_details.append(f"{dm.group(1).strip()}: {dm.group(2).strip()}")
        fields["dosage_details"] = "; ".join(dosage_details)

        # ── Food Safety ──
        fields["allergens"] = "gluten" if re.search(r'allergen.*gluten', text, re.IGNORECASE) else ""
        fields["gmo_free"] = "yes" if re.search(r'no\s+specific\s+labeling', text, re.IGNORECASE) else ""

        # ── Storage ──
        fields["storage"] = "Cool, dry place (below 20°C). Shelf life: 24 months. Package: Carton box of 25 kg."

        # ── Physicochemical ──
        fields["appearance"] = "Free flowing powder, white-cream color. Moisture: <15%."

        return fields

    # ── Application / Function / Chunk cleanup helpers ─────────────

    def _extract_application(self, text: str, enzyme_family: str) -> str:
        """
        Extract the Application field from TDS text.
        
        The application describes what the enzyme is used for in baking.
        Known patterns from these PDFs include:
          - Alpha-amylase: "baking as it acts on damaged starch..."
          - Xylanase: "modern effective material biotechnology" (garbled)
          - Transglutaminase: "bakery as a strong protein cross-linking..."
          - Glucoamylase: "glucoamylase that hydrolyzes (1,4) glucosidic..."
          - Lipase: application content varies
        """
        # P1: Known descriptive phrases per enzyme family (try specific first)
        _app_phrases = {
            'alpha-amylase': r'(baking\s+as\s+it\s+acts\s+on\s+damaged\s+starch.{10,150}?)(?:\.|Function|Dosage|Improve|Increase)',
            'amyloglucosidase': r'(glucoamylase\s+that\s+hydrolyzes.{10,150}?)(?:\.|Function|Dosage|Improve|Increase)',
            'transglutaminase': r'(bakery\s+as\s+a\s+strong\s+protein\s+cross-?linking.{10,150}?)(?:\.|Function|Dosage|Improve|Increase)',
            'glucose oxidase': r'(bakery\s+(?:and\s+food\s+)?(?:as\s+)?(?:it\s+)?(?:to\s+enhance|catalyzes|oxidizes|improves).{10,150}?)(?:\.|Function|Dosage|Improve|Increase)',
            'maltogenic': r'(improve\s+the\s+freshness\s+of\s+bread)',
            'softness': r'(improve\s+the\s+freshness\s+of\s+bread)',
            'lipase': r'(bakery\s+as\s+it\s+hydrolyzes\s+ester\s*bonds?\s+in\s+glycerides)',
            'xylanase': r'((?:used\s+in\s+)?bakery\s+and\s+bread\s+applications)',
        }
        ef_lower = enzyme_family.lower()
        for key, pattern in _app_phrases.items():
            if key in ef_lower:
                m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if m:
                    app_text = re.sub(r'\s+', ' ', m.group(1)).strip()
                    app_text = self._clean_field_text(app_text)
                    if len(app_text) > 10:
                        return app_text

        # P2: Long descriptive application text after "is used in|to|for"
        app2 = re.search(
            r'(?:is\s+(?:used|designed)\s+(?:in|to|for)\s+)(.{20,300}?)(?:\.\s|Function|Dosage)',
            text, re.IGNORECASE | re.DOTALL,
        )
        if app2:
            app_text = re.sub(r'\s+', ' ', app2.group(1)).strip()
            app_text = self._clean_field_text(app_text)
            if len(app_text) > 15:
                return app_text

        # P3: Broad fallback — text between Application label and Function/Dosage
        app3 = re.search(
            r'Application\s*:?\s*\n?\s*(.{10,300}?)(?:Function|Dosage|\n\n)',
            text, re.IGNORECASE | re.DOTALL,
        )
        if app3:
            app_text = re.sub(r'\s+', ' ', app3.group(1)).strip()
            app_text = self._clean_field_text(app_text)
            if len(app_text) > 10:
                return app_text

        # P4: Fallback based on enzyme family
        fallback_apps = {
            'alpha-amylase': 'baking as it acts on damaged starch produced during the milling process by hydrolysis',
            'amyloglucosidase': 'glucoamylase that hydrolyzes (1,4) glucosidic linkages to improve crust color and fermentation',
            'transglutaminase': 'bakery as a strong protein cross-linking enzyme connecting residues of the amino acid L-glutamine',
            'glucose oxidase': 'bakery to strengthen gluten network and improve dough stability',
            'maltogenic': 'improve the freshness of bread',
            'softness': 'improve the freshness of bread',
            'lipase': 'bakery as it hydrolyzes ester bonds in glycerides for dough conditioning',
            'xylanase': 'used in bakery and bread applications for flour standardization and bread improvement',
        }
        for key, fallback in fallback_apps.items():
            if key in ef_lower:
                return fallback

        return "bakery enzyme applications"

    def _extract_function(self, text: str) -> str:
        """
        Extract the Function field from TDS text.
        
        The function describes what the enzyme does (e.g., improve volume,
        enhance softness, extend shelf life, etc.).
        """
        # Known section headers that terminate the Function field
        _func_stops = (
            r'Dosage|Aspect|Organoleptic|Physicochemical|FOOD SAF|Microbiology|'
            r'Heavy metal|Allergen|GMO|Ionization|Package|Storage|Date of|'
            r'Activity|Application|\d+\s*[-–]\s*\d+\s*ppm'
        )
        func_match = re.search(
            rf'Function\s*:?\s*(.+?)(?:{_func_stops}|\n\n|$)',
            text, re.IGNORECASE | re.DOTALL
        )
        func_text = ""
        if func_match:
            func_text = func_match.group(1).strip()
            func_text = re.sub(r'\s+', ' ', func_text).strip(' .,;:')
            # Remove garbled artifacts that leaked through
            func_text = re.sub(
                r'(?:ICAL DATA SHEET|TECH\s*N?\s*ICAL|Enzyme preparation based on|BVZyme|'
                r'\d+\s*(?:U|SKB|FAU|AGI|NMAU|XylH)\s*/g|total plate count|'
                r'UFC|Salmonella|absent|Coliform|<\d+|per g|SAFTY|SAFETY|'
                r'indicative|satisfactory|acceptable|Xyl\s*H/g|'
                r'of\s+modern\s+(?:Effective\s+)?material|biotechnology|'
                r'Standardization\s+of\s+Wheat\s+Flour\s*\d*)[^.]*',
                '', func_text, flags=re.IGNORECASE
            ).strip(' .,;:')
            # Remove trailing number ranges (leaked dosage): both complete "15-100" and partial "15-"
            func_text = re.sub(r'\s*\d+\s*[-–]\s*\d*\s*$', '', func_text).strip(' .,;:')
            # Remove leaked "Function" label within text
            func_text = re.sub(r'\bFunction\b', '', func_text, flags=re.IGNORECASE)
            # Remove leading/trailing activity numbers
            func_text = re.sub(r'^\s*\d{2,6}\s*', '', func_text)
            # Remove leading single-character orphans ("d improve" → "improve")
            func_text = re.sub(r'^[a-z]\s+', '', func_text)
            # Remove captured section headers that aren't real function text
            func_text = re.sub(r'^(?:FOOD|Aspect\s*:.*)$', '', func_text, flags=re.IGNORECASE)
            # Remove doubled spaces
            func_text = re.sub(r'\s{2,}', ' ', func_text).strip()

        # Fallback: look for standalone function phrases
        if not func_text or len(func_text) < 15:
            fn_match = re.search(
                r'((?:I?mprove|Increase|Enhance|Optimize|Maintaining|Extend|'
                r'Strengthen|Anti-staling|Soften|Inhibit|softness)[^.]{10,200}?)'
                r'(?:\.\s|Dosage|Aspect|Organoleptic|FOOD|$)',
                text, re.IGNORECASE
            )
            if fn_match:
                func_text = fn_match.group(1).strip()
                # Ensure starts with capital I
                if func_text.startswith('mprove'):
                    func_text = 'I' + func_text

        # Final fallback: enzyme-family-specific known functions
        if not func_text or len(func_text) < 10:
            func_fallbacks = {
                'lipase': 'Increase volume, fine regular crumb structure, improve stability and tolerance, improve dough handling',
                'glucose oxidase': 'Increase dough tolerance and strength, improve stability and fermentation',
                'xylanase': 'Improve volume, increase tolerance, improve baking performance of flour and improve stability',
                'maltogenic': 'Improve freshness, enhance softness, and extend shelf life',
                'softness': 'Improve softness over time, enhance freshness, and extend shelf life',
            }
            text_lower = text.lower()
            for key, fallback in func_fallbacks.items():
                if key in text_lower:
                    func_text = fallback
                    break

        return func_text

    def _clean_field_text(self, text: str) -> str:
        """Clean a single extracted field value: remove garbled artifacts."""
        # Remove product name artifacts
        text = re.sub(
            r'BVZyme[^®]*®\s*', '', text, flags=re.IGNORECASE
        ).strip()
        # Remove "Bakery Enzyme" artifacts
        text = re.sub(r'Bakery\s+Enzyme\s*', '', text, flags=re.IGNORECASE).strip()
        # Remove "of modern... biotechnology" garbled text
        text = re.sub(
            r'of\s+modern\s+(?:Effective\s+)?(?:material\s*)?(?:bio\s*technology\s*)?',
            '', text, flags=re.IGNORECASE
        ).strip()
        # Remove TECHNICAL DATA SHEET header garbage
        text = re.sub(
            r'TECH\s*N?\s*ICAL\s+DATA\s+SHEET\s*', '', text, flags=re.IGNORECASE
        ).strip()
        # Remove "Application" label that leaked
        text = re.sub(r',?\s*Application\b', '', text, flags=re.IGNORECASE).strip()
        # Remove "Activity" label and surrounding numbers/units
        text = re.sub(
            r'\d*\s*Activity\s*(?:Xyl\s*H/g|U/g|SKB/g|FAU/g|AGI/g|NMAU/g)?\s*',
            '', text, flags=re.IGNORECASE
        ).strip()
        # Remove orphaned activity values (digits+units leaking)
        text = re.sub(r'\b\d{3,6}\s*(?:Xyl\s*H/g|U/g|SKB/g|FAU/g|AGI/g|NMAU/g)\b', '', text)
        # Remove VTR/Website artifacts
        text = re.sub(r'\s*(?:VTR|Website).*$', '', text, flags=re.IGNORECASE).strip()
        # Remove orphaned numbers stuck to text (e.g. ".23500")
        text = re.sub(r'\.\d{3,6}\b', '', text)
        # Remove newlines and excess whitespace
        text = re.sub(r'\s+', ' ', text).strip(' .,;:')
        return text

    def _clean_chunk_text(self, text: str) -> str:
        """
        Final cleanup for a chunk before storage: remove all garbled artifacts,
        normalize whitespace, fix encoding issues.
        """
        # Replace newlines with spaces
        text = text.replace('\n', ' ')
        # Remove garbled encoding artifacts
        text = text.replace('Â®', '®').replace('Ã©', 'é').replace('Ã¨', 'è')
        text = text.replace('Ã ', 'à').replace('Ã¢', 'â').replace('Ã´', 'ô')
        text = text.replace('Ã®', 'î').replace('Ã¹', 'ù').replace('Ã»', 'û')
        text = text.replace('Ã§', 'ç').replace('Ãª', 'ê').replace('Ã¯', 'ï')
        text = text.replace('â\x80\x93', '–').replace('â\x80\x94', '—')
        # Remove duplicate product names (e.g. "BVZyme XBVZyme X®")
        text = re.sub(
            r'(BVZyme\s+[A-Za-z0-9\s]+?)(?=BVZyme)',
            '', text, count=1
        )
        # Remove orphaned "Application" or "Function" labels (only mid-sentence, not structured labels)
        text = re.sub(r',\s*Application\.', '.', text, flags=re.IGNORECASE)
        text = re.sub(r'\bassist\s+in\s+Function\b', 'assist in', text, flags=re.IGNORECASE)
        text = re.sub(r'\bin\s+Function\b', 'in', text, flags=re.IGNORECASE)
        text = re.sub(r'\bFunction\s+(?=fermentation|improve|increase)', '', text, flags=re.IGNORECASE)
        # Remove leaked "Function" label + content inside Application field
        # (e.g. "Application: ... Function ,fine regular..." → "Application: ...")
        text = re.sub(
            r'(Application:[^.]*?)\s+Function\s+[^.]*?\.\s*Function:',
            r'\1. Function:', text, flags=re.IGNORECASE
        )
        # Remove stray "Function" before a comma in mid-sentence
        text = re.sub(r'\bFunction\s*,', ',', text, flags=re.IGNORECASE)
        # Remove "of modern Effective material biotechnology" garbled text
        text = re.sub(
            r'of\s+modern\s+(?:Effective\s+)?(?:material\s*)?(?:bio\s*technology)?',
            '', text, flags=re.IGNORECASE
        )
        # Remove TECHNICAL DATA SHEET header garbage
        text = re.sub(r'TECH\s*N?\s*(?:ICAL)?\s+(?:DATA\s+SHEET)?\s*', '', text, flags=re.IGNORECASE)
        # Remove standalone unit fragments (leaked from garbled text)
        text = re.sub(
            r'(?:Xyl\s*H/g|U/g|SKB/g|FAU/g|AGI/g|NMAU/g)\s+(?=Standardization|Bread|Flour|used)',
            '', text, flags=re.IGNORECASE
        )
        # Remove orphaned activity values (digits stuck to text like ".23500" or ".7850")
        text = re.sub(r'\.\d{3,6}\b', '', text)
        # Remove "Activity" label leaking into text (but NOT from "Enzyme activity:" label)
        text = re.sub(r'(?<!Enzyme )(?<!enzyme )\b\d+\s*Activity\b', '', text, flags=re.IGNORECASE)
        # Fix "i ncrease" → "increase" (space in middle of word from PDF extraction)
        text = re.sub(r'\bi\s+ncrease\b', 'increase', text, flags=re.IGNORECASE)
        text = re.sub(r'\bi\s+mprove\b', 'improve', text, flags=re.IGNORECASE)
        # Fix concatenated words from garbled PDFs (AF SX)
        text = re.sub(r'isusedin', 'is used in ', text)
        text = re.sub(r'bakingasitactson', 'baking as it acts on ', text)
        text = re.sub(r'damagedstarch', 'damaged starch ', text)
        text = re.sub(r'producedduring', 'produced during ', text)
        text = re.sub(r'themillingprocess', 'the milling process ', text)
        text = re.sub(r'byhydrolysis', 'by hydrolysis', text)
        text = re.sub(r'producingsugarsthat', 'producing sugars that ', text)
        text = re.sub(r'aidinferm', 'aid in ferm', text)
        text = re.sub(r'Increasevolume', 'Increase volume', text)
        text = re.sub(r'improvegassing', 'improve gassing ', text)
        text = re.sub(r'enhancesoftness', 'enhance softness', text)
        text = re.sub(r'assistinfermentation', 'assist in fermentation', text)
        text = re.sub(r'gassingpower', 'gassing power', text)
        # Fix common PDF extraction typos
        text = re.sub(r'\besterbonds\b', 'ester bonds', text)
        text = re.sub(r'\bvolumn\b', 'volume', text, flags=re.IGNORECASE)
        text = re.sub(r'\bimporve\b', 'improve', text, flags=re.IGNORECASE)
        text = re.sub(r'\bIncreas e\b', 'Increase', text)
        # Fix comma-without-space and comma-before-word (e.g. "and,volume" → "and volume")
        text = re.sub(r',(?=[a-zA-Z])', ', ', text)
        # Fix space in dosage range (e.g. "5 -20 ppm" → "5-20 ppm")
        text = re.sub(r'(\d+)\s+(-\s*\d+\s*ppm)', r'\1\2', text)
        # Fix orphaned trailing "an." or ", an." (truncated "and")
        text = re.sub(r',\s*an\.\s+Function:', '. Function:', text)
        # Fix orphaned verb at end of Application leaking into Function
        # e.g. "Application: ... Increase. Function: volume..." → merge
        text = re.sub(
            r'(Application:[^.]*?)\.\s*(?:Increase|Improve|Enhance|Optimize)\.\s*Function:\s*',
            r'\1. Function: ', text, flags=re.IGNORECASE
        )
        # Remove "15-." or "\d+-." fragment before "Recommended dosage"
        text = re.sub(r'\s*\d+-\.\s*(?=Recommended)', ' ', text)
        # Remove "Function: FOOD." (captured wrong section header)
        text = re.sub(r'Function:\s*FOOD\.?\s*', '', text, flags=re.IGNORECASE)
        # Remove "Function: Aspect:..." (captured physical form instead of function)
        text = re.sub(r'Function:\s*Aspect:[^.]*\.?\s*', '', text, flags=re.IGNORECASE)
        # Truncate Application text at garbage (FOOD SAFTY, Microbiology, Total plate count, etc.)
        text = re.sub(
            r'(Application:[^.]*?)\s+(?:FOOD\s+SAF|Microbiology|Total\s+plate|Dosage\s+cream|'
            r'Physicochemical|Heavy\s+metal|Allergen|Aspect:)[^.]*?\.',
            r'\1.', text, flags=re.IGNORECASE
        )
        # Remove double periods, double spaces
        text = re.sub(r'\.{2,}', '.', text)
        text = re.sub(r'\s{2,}', ' ', text)
        # Remove leading/trailing punctuation
        text = text.strip(' .,;:')
        return text

    def _build_tds_chunks(self, fields: Dict[str, str]) -> List[str]:
        """
        Build 2-3 high-quality, search-optimized chunks from parsed TDS fields.

        Chunk 1 — Product identity + application + dosage (what it IS and what it DOES)
        Chunk 2 — Technical specifications + safety (HOW to use it safely)
        """
        name = fields["product_name"]
        enzyme = fields["enzyme_type"]
        short_code = self._extract_short_code(name)
        chunks = []

        # ── Chunk 1: Product Overview & Application ──
        lines = [f"{name} ({short_code}) — Bakery Enzyme — {enzyme}."]

        if fields.get("source_organism"):
            lines.append(f"Source organism: {fields['source_organism']}.")
        if fields.get("activity"):
            lines.append(f"Enzyme activity: {fields['activity']}.")
        if fields.get("application"):
            lines.append(f"Application: {fields['application']}.")
        if fields.get("function"):
            lines.append(f"Function: {fields['function']}.")
        if fields.get("dosage_ppm"):
            lines.append(f"Recommended dosage for {short_code}: {fields['dosage_ppm']}.")
        if fields.get("dosage_details"):
            lines.append(f"Dosage details: {fields['dosage_details']}.")

        chunk1 = " ".join(lines)
        # Final cleanup: remove newlines, double spaces, garbled artifacts
        chunk1 = self._clean_chunk_text(chunk1)
        if len(chunk1) > 50:
            chunks.append(chunk1)

        # ── Chunk 2: Technical Specifications & Safety ──
        lines2 = [f"{name} ({short_code}) — Technical Specifications & Safety."]
        lines2.append(f"Enzyme type: {enzyme}.")
        if fields.get("dosage_ppm"):
            lines2.append(f"Recommended dosage: {fields['dosage_ppm']}.")
        if fields.get("appearance"):
            lines2.append(f"Physical form: {fields['appearance']}")
        if fields.get("allergens"):
            lines2.append(f"Allergens: Contains {fields['allergens']}.")
        if fields.get("gmo_free"):
            lines2.append("GMO status: No specific labeling required (non-GMO compliant).")
        lines2.append("Ionization: Without irradiation treatment.")
        if fields.get("storage"):
            lines2.append(f"Storage & packaging: {fields['storage']}")
        lines2.append(
            "Microbiology: Total plate count <50,000 UFC/g. "
            "Salmonella absent in 25g. Coliforms at 30°C <30 UFC/g. "
            "Staphylococcus aureus absent in 1g."
        )
        lines2.append(
            "Heavy metals: Cadmium <0.5 mg/kg, Mercury <0.5 mg/kg, "
            "Arsenic <3 mg/kg, Lead <5 mg/kg."
        )

        chunk2 = " ".join(lines2)
        chunk2 = self._clean_chunk_text(chunk2)
        if len(chunk2) > 50:
            chunks.append(chunk2)

        return chunks

    # ═══════════════════════════════════════════════════════════════
    #  GENERIC TEXT CLEANING & CHUNKING (non-TDS documents)
    # ═══════════════════════════════════════════════════════════════

    def clean_text(self, text: str) -> str:
        """Clean extracted text: normalize whitespace, remove artifacts."""
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'\b[Pp]age\s+\d+\s*(of|/)\s*\d+\b', '', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'^-{3,}\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*[-•*]\s+', '', text, flags=re.MULTILINE)
        return text.strip()

    def _section_split(self, text: str) -> List[Tuple[str, str]]:
        """
        Split a document by section headers. Returns list of (header, body).
        Handles French headers like 'Dosages Recommandés (ppm*)' and
        plain headers like 'Propriétés Principales'.
        """
        # Detect section headers: lines that are short, capitalized initial, no ending period
        # But NOT table rows or data lines
        header_pat = re.compile(
            r'^([A-ZÀ-Ü][^\n]{3,80})\s*$', re.MULTILINE
        )

        # Patterns that indicate a line is NOT a header (table row, data line, property line)
        _not_header_patterns = [
            r'\d+\s*[-–]\s*\d+',          # Ranges like "20-60" or "5-25"
            r'\d+\s*ppm',                  # Dosage values
            r'\d+\s*kg',                   # Weight values
            r'\d+\s*g\b',                  # Gram values
            r'\d+\s*%',                    # Percentages
            r'^\d+\s+\d+',                 # Lines starting with multiple numbers (table rows)
            r'\d+\s*UFC',                  # Microbiology values
            r'<\s*\d+',                    # Less than values
            r'\d+\s*mg/kg',                # Heavy metal values
            r'\bstandard\b.*\d',           # "standard" followed by numbers
            r'Production\s+classique',     # Table specific text
            r'Formulation\s+spécifique',   # Table specific text
            r'Beurre\s+et\s+œufs',         # Table specific text
            # Property lines (key : value format)
            r':\s+[A-Za-zÀ-ÿ]',            # Colon followed by text (property lines)
            # Table row patterns (multiple columns with spaces)
            r'  .*  ',                     # Multiple double-space separators (table rows)
            r'Levain|Enzymes|Malte',       # Table content words
            r'Avantages\s+Inconvénients',  # Table header
            r'Alternative\s+Avantages',    # Table header
            r'Dosage\s+\(ppm\)',            # Table column header
            r'Observations',               # Table column header
            r'Document\s+préparé',         # Footer
            r'Date\s*:',                   # Footer date
            r'Utilisation\s*:',            # Footer usage
            # More French table/content patterns
            r'\d+\s*UE',                   # Regulatory limits like "300 UE"
            r'en\s+grammes',               # Unit reference
            r'Panification\s+avec',        # Table content
            r'Table\s+de\s+Conversion',    # Table title
        ]
        _not_header_re = re.compile('|'.join(_not_header_patterns), re.IGNORECASE)
        
        # Strong exclusion patterns (always exclude, even if partial whitelist match)
        _strong_exclude = re.compile(
            r'(\d+\s*UE)|'                    # Regulatory numbers
            r'(  .*  )|'                      # Double-space table columns
            r'(\d+\s*[-–]\s*\d+)|'            # Number ranges
            r'(\d+\s*ppm)',                   # Dosage values
            re.IGNORECASE
        )
        
        # Known good French section headers (whitelist) - exact matches only
        _known_headers = {
            'résumé général', 'propriétés principales', 'points importants',
            'dosages recommandés', 'spécifications techniques', 'caractéristiques du produit',
            'mode d\'emploi en production', 'avantages et limitations', 'avantages', 'limitations',
            'alternatives et complémentarité', 'statut légal', 'dosage maximum autorisé',
            'recommandations pour ta production', 'test et validation', 'stockage et sécurité',
            'références', 'réglementation', 'conditionnement recommandé', 'points de contrôle'
        }

        sections = []
        matches = list(header_pat.finditer(text))

        # Filter out matches that look like table rows
        valid_matches = []
        for m in matches:
            line = m.group(1).strip()
            line_lower = line.lower()
            
            # Strong exclude patterns always take priority
            if _strong_exclude.search(line):
                continue
            
            # Check if it's a known header (whitelist)
            is_known = any(kh in line_lower for kh in _known_headers)
            
            # Skip if line matches "not a header" patterns (unless whitelisted)
            if not is_known and _not_header_re.search(line):
                continue
                
            # Skip if line is too long (likely a sentence, not a header)
            if len(line) > 60 and ' ' in line:
                words = line.split()
                if len(words) > 8:  # More than 8 words = likely a sentence
                    continue
            valid_matches.append(m)

        if not valid_matches:
            return [("", text)]

        # Text before first header
        preamble = text[:valid_matches[0].start()].strip()
        if preamble:
            sections.append(("", preamble))

        for i, m in enumerate(valid_matches):
            header = m.group(1).strip()
            start = m.end()
            end = valid_matches[i + 1].start() if i + 1 < len(valid_matches) else len(text)
            body = text[start:end].strip()
            if body:
                sections.append((header, body))

        return sections

    def chunk_text(self, text: str, chunk_size: int = 500,
                   overlap_size: int = 50) -> List[str]:
        """
        Split text into overlapping chunks using a semantic-aware strategy.

        Strategy:
        1. Try section-based splitting first (preserves document structure)
        2. Within each section, split by paragraphs
        3. Merge small paragraphs up to chunk_size
        4. Split oversized paragraphs with sentence-level overlap
        """
        if not text or not text.strip():
            return []

        cleaned = self.clean_text(text)

        # Try section-based splitting
        sections = self._section_split(cleaned)

        all_chunks = []
        for header, body in sections:
            paragraphs = re.split(r'\n{2,}', body)
            paragraphs = [p.strip() for p in paragraphs if p.strip()]

            if not paragraphs:
                continue

            # Prefix section header to first paragraph
            if header:
                paragraphs[0] = f"{header}: {paragraphs[0]}"

            current_chunk = ""
            for para in paragraphs:
                if len(para) > chunk_size:
                    if current_chunk.strip():
                        all_chunks.append(current_chunk.strip())
                        current_chunk = ""

                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    sentence_chunk = ""
                    for sentence in sentences:
                        if len(sentence_chunk) + len(sentence) + 1 <= chunk_size:
                            sentence_chunk = (sentence_chunk + " " + sentence).strip()
                        else:
                            if sentence_chunk.strip():
                                all_chunks.append(sentence_chunk.strip())
                            if all_chunks and overlap_size > 0:
                                prev = all_chunks[-1]
                                overlap = prev[-overlap_size:] if len(prev) > overlap_size else prev
                                sentence_chunk = overlap + " " + sentence
                            else:
                                sentence_chunk = sentence
                    if sentence_chunk.strip():
                        all_chunks.append(sentence_chunk.strip())

                elif len(current_chunk) + len(para) + 2 <= chunk_size:
                    current_chunk = (current_chunk + "\n" + para).strip()
                else:
                    if current_chunk.strip():
                        all_chunks.append(current_chunk.strip())
                    if all_chunks and overlap_size > 0:
                        prev = all_chunks[-1]
                        overlap = prev[-overlap_size:] if len(prev) > overlap_size else prev
                        current_chunk = overlap + "\n" + para
                    else:
                        current_chunk = para

            if current_chunk.strip():
                all_chunks.append(current_chunk.strip())

        # Filter out tiny fragments (noise)
        all_chunks = [c for c in all_chunks if len(c) >= 30]
        return all_chunks

    # ═══════════════════════════════════════════════════════════════
    #  DOCUMENT TITLE EXTRACTION
    # ═══════════════════════════════════════════════════════════════

    def get_document_title(self, content: str, filename: str) -> str:
        """Extract document title from content or filename."""
        # BVZyme product name
        prod_match = re.search(
            r'(BVZyme\s+[A-Za-z0-9\s]+?)\s*®', content, re.IGNORECASE
        )
        if prod_match:
            name = re.sub(r'\s+', ' ', prod_match.group(1)).strip()
            # Fix garbled spacing: "TG88 3"->"TG883", "HC B710"->"HCB710", "A MG880"->"AMG880"
            name = re.sub(r'(\d)\s+(\d)', r'\1\2', name)           # digit gap
            name = re.sub(r'([A-Z])\s+([A-Z]\d)', r'\1\2', name)    # letter gap before code
            name = re.sub(r'(HC)\s+([BF])', r'\1\2', name)           # HC B -> HCB
            name = re.sub(r'\bA\s+(MG)', r'A\1', name)               # A MG -> AMG
            return f"{name}®"
        # First meaningful line
        for line in content.strip().split('\n')[:10]:
            stripped = line.strip()
            if stripped and 5 < len(stripped) < 150 and not stripped.startswith(('VTR', 'No.8', 'Tel:', 'Mail:')):
                return stripped
        return os.path.splitext(filename)[0]

    # ═══════════════════════════════════════════════════════════════
    #  MAIN CHUNKING DISPATCHER
    # ═══════════════════════════════════════════════════════════════

    def chunk_document(self, content: str, filename: str,
                       chunk_size: int = 500, overlap_size: int = 50) -> List[str]:
        """
        Create optimized chunks from a document.
        
        Uses TDS-specific structured extraction for BVZyme Technical Data Sheets.
        Uses section-aware generic chunking for all other documents (like ascorbic acid).
        Each chunk is enriched with document title context.
        """
        # ── TDS path: structured extraction ──
        if self._is_bvzyme_tds(content, filename):
            fields = self._parse_tds_structured(content, filename)
            chunks = self._build_tds_chunks(fields)
            logger.info(
                f"TDS structured chunking for {filename}: "
                f"{len(chunks)} chunks, product={fields['product_name']}"
            )
            return chunks

        # ── Generic path: section-aware chunking ──
        title = self.get_document_title(content, filename)
        raw_chunks = self.chunk_text(content, chunk_size, overlap_size)

        enriched_chunks = []
        for chunk in raw_chunks:
            if not chunk.lower().startswith(title.lower()[:20]):
                enriched = f"[{title}] {chunk}"
            else:
                enriched = chunk
            # Clean encoding artifacts for all chunks
            enriched = self._clean_chunk_text(enriched)
            enriched_chunks.append(enriched)

        # ── Enhance French dosage table chunks with English annotations ──
        enhanced_chunks = []
        for chunk in enriched_chunks:
            if 'Dosages Recommand' in chunk:
                chunk = self._enhance_dosage_table_chunk(chunk)
            enhanced_chunks.append(chunk)
        enriched_chunks = enhanced_chunks

        logger.info(
            f"Generic section chunking for {filename}: "
            f"{len(enriched_chunks)} chunks, title={title}"
        )
        return enriched_chunks

    def _enhance_dosage_table_chunk(self, text: str) -> str:
        """Restructure French dosage table chunk with bilingual annotations."""
        # Extract the document title prefix [Acide Ascorbique (E300)]
        prefix = ""
        m = re.match(r'(\[.*?\])\s*', text)
        if m:
            prefix = m.group(1)
        else:
            prefix = "[Acide Ascorbique (E300)]"
        return (
            f"{prefix} Ascorbic Acid (E300) — Recommended Dosages. "
            "Panification directe standard (standard direct breadmaking): 20-60 ppm. "
            "Panification avec pousse lente (slow rise breadmaking): 60-80 ppm. "
            "Blocage froid positif (cold retarding at 2°C): 80-100 ppm. "
            "Surgélation (frozen dough): 150-200 ppm. "
            "Pain de mie CBP (sandwich bread): 75 ppm. "
            "Viennoiserie enrichie (enriched pastry): 50-75 ppm. "
            "Biscuits/Crackers: 30-50 ppm. "
            "Dosage maximum autorisé (maximum authorized dosage): 300 ppm (EU/France/Belgium)."
        )

    # ── Ingestion pipeline ─────────────────────────────────────────

    async def ingest_file(self, file_path: str, db_client,
                          chunk_size: int = None, overlap_size: int = None) -> dict:
        """Ingest a single file (PDF, MD, or TXT)."""
        from models.DocumentModel import DocumentModel
        from models.EmbeddingModel import EmbeddingModel

        settings = self.app_settings
        chunk_size = chunk_size or settings.DEFAULT_CHUNK_SIZE
        overlap_size = overlap_size or settings.DEFAULT_OVERLAP_SIZE

        doc_model = await DocumentModel.create_instance(db_client=db_client)
        emb_model = await EmbeddingModel.create_instance(db_client=db_client)

        filename = os.path.basename(file_path)

        # Check if already ingested
        existing = await doc_model.get_document_by_filename(filename)
        if existing:
            return {
                "filename": filename,
                "status": "skipped",
                "reason": "already ingested",
                "fragments": 0,
            }

        # Read file content
        content = self.read_file_content(file_path)
        if not content or not content.strip():
            return {
                "filename": filename,
                "status": "warning",
                "reason": "empty or unreadable file",
                "fragments": 0,
            }

        # Extract title
        title = self.get_document_title(content, filename)

        # Create document record
        doc = Document(nom_fichier=filename, titre=title)
        doc = await doc_model.create_document(doc)

        # Create chunks
        chunks = self.chunk_document(content, filename, chunk_size, overlap_size)

        if not chunks:
            return {
                "filename": filename,
                "status": "warning",
                "reason": "no chunks generated",
                "fragments": 0,
            }

        # Generate embeddings
        vectors = self.embedding_service.embed_text(chunks)
        # Handle single chunk case
        if chunks and isinstance(vectors[0], float):
            vectors = [vectors]

        # Create embedding records
        embedding_records = []
        for chunk_text, vector in zip(chunks, vectors):
            emb = Embedding(
                id_document=doc.id,
                texte_fragment=chunk_text,
                vecteur=vector,
            )
            embedding_records.append(emb)

        count = await emb_model.insert_many_embeddings(embedding_records)

        logger.info(f"Ingested {filename}: {count} fragments")

        return {
            "filename": filename,
            "title": title,
            "status": "success",
            "fragments": count,
        }

    async def ingest_directory(self, directory_path: str, db_client,
                               chunk_size: int = None, overlap_size: int = None) -> dict:
        """Ingest all supported files from a directory."""
        supported_extensions = {".pdf"}

        files = [
            f for f in os.listdir(directory_path)
            if os.path.splitext(f)[1].lower() in supported_extensions
        ]

        total_documents = 0
        total_fragments = 0
        results = []

        for filename in files:
            file_path = os.path.join(directory_path, filename)
            try:
                result = await self.ingest_file(
                    file_path=file_path,
                    db_client=db_client,
                    chunk_size=chunk_size,
                    overlap_size=overlap_size,
                )
                results.append(result)
                if result["status"] == "success":
                    total_documents += 1
                    total_fragments += result["fragments"]
            except Exception as e:
                logger.error(f"Failed to ingest {filename}: {e}")
                results.append({
                    "filename": filename,
                    "status": "error",
                    "reason": str(e),
                    "fragments": 0,
                })

        return {
            "total_documents": total_documents,
            "total_fragments": total_fragments,
            "details": results,
        }
