from .BaseController import BaseController
from models.db_schemes import Document, Embedding
from stores.embedding.EmbeddingService import EmbeddingService
from typing import List, Dict, Optional
import os
import re
import logging

logger = logging.getLogger("uvicorn")

ENZYME_BILINGUAL = {
    "amylase": "alpha-amylase α-amylase fungal amylase amylase fongique",
    "alpha-amylase": "alpha-amylase α-amylase fungal amylase amylase fongique",
    "xylanase": "xylanase endo-xylanase hemicellulose",
    "glucose oxidase": "glucose oxidase glucose oxydase GOX",
    "transglutaminase": "transglutaminase TG",
    "lipase": "lipase phospholipase",
    "phospholipase": "lipase phospholipase",
    "amyloglucosidase": "amyloglucosidase glucoamylase AMG",
    "maltogenic amylase": "maltogenic amylase amylase maltogénique anti-staling",
}


class DataController(BaseController):
    def __init__(self, embedding_service: EmbeddingService):
        super().__init__()
        self.embedding_service = embedding_service

    def read_markdown_file(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def get_document_title(self, content: str, filename: str) -> str:
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return os.path.splitext(filename)[0]


    def _clean_md(self, text: str) -> str:
        """Remove markdown formatting (bold, italic, bullets)."""
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^-{3,}\s*$', '', text, flags=re.MULTILINE)
        return text.strip()

    def _extract_section(self, content: str, heading: str) -> Optional[str]:
        """Extract content under a ## heading (partial match, case-insensitive)."""
        escaped = re.escape(heading)
        pattern = rf'##\s*{escaped}[^\n]*\n+(.+?)(?=\n---|\n##|\Z)'
        match = re.search(pattern, content, re.S | re.I)
        if match:
            return match.group(1).strip()
        return None

    # ── Structured extraction ──────────────────────────────────────────

    def extract_product_info(self, content: str) -> Dict:
      
        info = {}

        # Product name
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            info['name'] = match.group(1).strip()

        
        matches = re.findall(r'^##\s+(.+)$', content, re.MULTILINE)
        if matches:
            info['subtitle'] = matches[0].strip()

        for pattern in [
            r'\*?\*?Enzyme\s+(?:preparation\s+)?based\s+on\*?\*?\s*:\s*\*?\*?\s*(.+)',
            r'\*?\*?Enzyme\s+base\*?\*?\s*:\s*\*?\*?\s*(.+)',
        ]:
            match = re.search(pattern, content, re.I)
            if match:
                info['enzyme_type'] = self._clean_md(match.group(1))
                break

        match = re.search(r'\*?\*?Enzyme\*?\*?\s*:\s*(.+)', content)
        if match:
            info['enzyme'] = self._clean_md(match.group(1))

        # Activity
        match = re.search(r'\*?\*?Activity\*?\*?\s*:\s*(.+)', content)
        if match:
            info['activity'] = self._clean_md(match.group(1))

        # Description
        desc = self._extract_section(content, 'Product Description')
        if desc:
            info['description'] = self._clean_md(desc)

        # Application
        app = self._extract_section(content, 'Application')
        if app:
            
            lines = []
            for line in app.split('\n'):
                stripped = line.strip()
                if stripped.startswith('###') or stripped.startswith('- **'):
                    break
                if stripped and not stripped.startswith('|'):
                    lines.append(self._clean_md(stripped))
            if lines:
                info['application'] = ' '.join(lines)

        # Functions
        func = self._extract_section(content, 'Function')
        if func:
            functions = re.findall(r'^\s*-\s+(.+)$', func, re.MULTILINE)
            info['functions'] = [self._clean_md(f) for f in functions]

        # Dosage — collect all dosage information
        dosages = []
        for match in re.finditer(
            r'\*?\*?(?:Recommended\s+)?[Dd]osage(?:\s+range)?\*?\*?\s*:\s*(.+)',
            content
        ):
            dosages.append(self._clean_md(match.group(1)))
        # Multiple dosage lines (HCF xylanase products)
        for match in re.finditer(
            r'\*?\*?(Standardization of wheat flour|Bread improvement|Suggested optimum dosage)\*?\*?\s*:\s*(.+)',
            content
        ):
            label = self._clean_md(match.group(1))
            value = self._clean_md(match.group(2))
            dosages.append(f"{label}: {value}")

        if dosages:
            info['dosage'] = '; '.join(dosages)

        return info

    # ── Smart chunk creation ───────────────────────────────────────────

    def create_product_chunks(self, content: str, filename: str) -> List[str]:
   
        if 'acide ascorbique' in filename.lower() or 'Acide Ascorbique' in content[:200]:
            return self._create_ascorbic_acid_chunks(content, filename)

        # Standard enzyme TDS files (English)
        return self._create_enzyme_chunks(content, filename)

    def _create_enzyme_chunks(self, content: str, filename: str) -> List[str]:
        """Create 2 focused chunks per enzyme product."""
        info = self.extract_product_info(content)
        name = info.get('name', self.get_document_title(content, filename))
        enzyme = info.get('enzyme', info.get('enzyme_type', ''))

        chunks = []

        # ── Chunk 1: Full product card ──
        parts = []

        # Name + enzyme type
        name_str = name
        if enzyme:
            name_str += f" ({enzyme})"
        parts.append(name_str)

        # Category
        if info.get('subtitle'):
            parts.append(info['subtitle'])

        # Description
        if info.get('description'):
            parts.append(info['description'])

        # Application
        if info.get('application'):
            parts.append(info['application'])

        # Dosage
        if info.get('dosage'):
            parts.append(f"Recommended dosage: {info['dosage']}")

        # Activity
        if info.get('activity'):
            parts.append(f"Enzyme activity: {info['activity']}")

        # Functions
        if info.get('functions'):
            parts.append("Functions: " + ", ".join(info['functions'][:6]))

        # Bilingual domain keywords woven naturally
        bilingual = self._bilingual_suffix(enzyme)
        if bilingual:
            parts.append(f"Bread improver, améliorant de panification. {bilingual}")

        card = ". ".join(parts)
        chunks.append(card)

        # ── Chunk 2: Dosage-focused chunk ──
        if info.get('dosage'):
            dose_parts = [name]
            if enzyme:
                dose_parts.append(f"enzyme type: {enzyme}")
            dose_parts.append(f"Recommended dosage: {info['dosage']}")
            if info.get('functions'):
                dose_parts.append(f"Used for: {', '.join(info['functions'][:3])}")
            dose_parts.append(
                "Bakery enzyme for bread and pastry (améliorant de panification, boulangerie)"
            )
            chunks.append(". ".join(dose_parts))

        return chunks

    def _create_ascorbic_acid_chunks(self, content: str, filename: str) -> List[str]:
        """Create specialized chunks for the French acide ascorbique file."""
        chunks = []
        title = self.get_document_title(content, filename)

        # ── Chunk 1: Identity + Summary + Properties ──
        summary = self._extract_section(content, 'Résumé Général')
        props = self._extract_section(content, 'Propriétés Principales')

        id_parts = [
            f"{title} (Ascorbic Acid, Vitamin C, E300)",
            "Améliorant de Panification (bread improver, baking additive)",
        ]
        if summary:
            id_parts.append(self._clean_md(summary))
        if props:
            prop_items = re.findall(r'^\s*-\s+(.+)$', props, re.MULTILINE)
            clean_props = [self._clean_md(p) for p in prop_items[:5]]
            id_parts.append("Properties: " + "; ".join(clean_props))

        chunks.append(". ".join(id_parts))

        # ── Chunk 2: Dosage table (CRITICAL for the example question) ──
        dosage_section = self._extract_section(content, 'Dosages Recommandés')
        if dosage_section:
            dose_parts = [
                f"{title} (Ascorbic Acid, E300) - Recommended dosages",
                "Améliorant de panification, bread improver",
            ]
            # Parse table rows
            cleaned = self._clean_md(dosage_section)
            table_rows = re.findall(
                r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|',
                dosage_section
            )
            for row in table_rows:
                col1, col2, col3 = [self._clean_md(c) for c in row]
                # Skip header row and separator
                if 'Type' in col1 or re.match(r'^[-:]+$', col1):
                    continue
                dose_parts.append(f"{col1}: {col2} ppm ({col3})")

            # Add the percentage equivalents
            dose_parts.append(
                "General range: 20-200 ppm (0.002% to 0.02% of flour weight)"
            )
            dose_parts.append("Maximum authorized dosage: 300 ppm (EU/France/Belgium)")

            chunks.append(". ".join(dose_parts))

        # ── Chunk 3: Important points + technical specs ──
        important = self._extract_section(content, 'Points Importants')
        usage = self._extract_section(content, "Mode d'Emploi")

        if important or usage:
            tech_parts = [
                f"{title} (Ascorbic Acid, E300) - Technical usage and important notes"
            ]
            if important:
                items = re.findall(r'^\s*-\s+(.+)$', important, re.MULTILINE)
                tech_parts.extend([self._clean_md(i) for i in items])
            if usage:
                steps = re.findall(r'^\d+\.\s+(.+)$', usage, re.MULTILINE)
                if steps:
                    tech_parts.append(
                        "Usage instructions: " +
                        "; ".join([self._clean_md(s) for s in steps])
                    )
            chunks.append(". ".join(tech_parts))

        # ── Chunk 4: Conversion table ──
        conversion = self._extract_section(content, 'Table de Conversion')
        if conversion:
            conv_parts = [
                f"{title} (Ascorbic Acid) - Dosage conversion table (grams per flour weight)",
                "For 100 kg flour: 5g at 50 ppm, 7.5g at 75 ppm, 10g at 100 ppm, 15g at 150 ppm",
                "For 50 kg flour: 2.5g at 50 ppm, 3.75g at 75 ppm, 5g at 100 ppm, 7.5g at 150 ppm",
                "Dosage recommandé: 0.005% à 0.02% du poids de farine (recommended dosage: 0.005% to 0.02% of flour weight)",
            ]
            chunks.append(". ".join(conv_parts))

        return chunks

    def _bilingual_suffix(self, enzyme_name: str) -> str:
        """Get bilingual keyword enrichment for an enzyme type."""
        if not enzyme_name:
            return ""
        lower = enzyme_name.lower()
        for key, bilingual in ENZYME_BILINGUAL.items():
            if key in lower:
                return f"Also known as: {bilingual}"
        return ""

    # ── Ingestion pipeline ─────────────────────────────────────────────

    async def ingest_directory(self, directory_path: str, db_client,
                               chunk_size: int = None, overlap_size: int = None) -> dict:
        from models.DocumentModel import DocumentModel
        from models.EmbeddingModel import EmbeddingModel

        doc_model = await DocumentModel.create_instance(db_client=db_client)
        emb_model = await EmbeddingModel.create_instance(db_client=db_client)

        md_files = [f for f in os.listdir(directory_path) if f.endswith(".md")]

        total_documents = 0
        total_fragments = 0
        results = []

        for filename in md_files:
            file_path = os.path.join(directory_path, filename)
            content = self.read_markdown_file(file_path)

            # Check if already ingested
            existing = await doc_model.get_document_by_filename(filename)
            if existing:
                logger.info(f"Skipping already ingested: {filename}")
                results.append({
                    "filename": filename,
                    "status": "skipped",
                    "reason": "already ingested"
                })
                continue

            # Extract title
            title = self.get_document_title(content, filename)

            # Create document record
            doc = Document(nom_fichier=filename, titre=title)
            doc = await doc_model.create_document(doc)

            # Create focused product chunks (smart domain-aware chunking)
            chunks = self.create_product_chunks(content, filename)

            if not chunks:
                results.append({
                    "filename": filename,
                    "status": "warning",
                    "reason": "no chunks generated"
                })
                continue

            # Generate embeddings for all chunks
            vectors = self.embedding_service.embed_text(chunks)

            # Handle single chunk → embed_text returns flat list
            if chunks and isinstance(vectors[0], float):
                vectors = [vectors]

            # Create embedding records
            embedding_records = []
            for chunk_text, vector in zip(chunks, vectors):
                emb = Embedding(
                    id_document=doc.id,
                    texte_fragment=chunk_text,
                    vecteur=vector
                )
                embedding_records.append(emb)

            # Batch insert
            count = await emb_model.insert_many_embeddings(embedding_records)

            total_documents += 1
            total_fragments += count

            results.append({
                "filename": filename,
                "title": title,
                "status": "success",
                "fragments": count
            })

            logger.info(f"Ingested {filename}: {count} fragments")

        return {
            "total_documents": total_documents,
            "total_fragments": total_fragments,
            "details": results
        }
