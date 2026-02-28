from .BaseController import BaseController
from stores.embedding.EmbeddingService import EmbeddingService
from stores.vectordb.PGVectorProvider import PGVectorProvider
from models.db_schemes import RetrievedFragment
from typing import List, Tuple, Optional
import numpy as np
import re
import logging

logger = logging.getLogger("uvicorn")

# ── Known ingredients for query decomposition ─────────────────────
# (term to detect, canonical English name) — sorted longest first
KNOWN_INGREDIENTS = [
    ("acide ascorbique", "ascorbic acid"),
    ("ascorbic acid", "ascorbic acid"),
    ("vitamine c", "ascorbic acid"),
    ("vitamin c", "ascorbic acid"),
    ("amylase maltogénique", "maltogenic amylase"),
    ("maltogenic amylase", "maltogenic amylase"),
    ("amylase fongique", "alpha-amylase"),
    ("fungal amylase", "alpha-amylase"),
    ("alpha-amylase", "alpha-amylase"),
    ("α-amylase", "alpha-amylase"),
    ("glucose oxydase", "glucose oxidase"),
    ("glucose oxidase", "glucose oxidase"),
    ("transglutaminase", "transglutaminase"),
    ("amyloglucosidase", "amyloglucosidase"),
    ("glucoamylase", "amyloglucosidase"),
    ("endo-xylanase", "xylanase"),
    ("xylanase", "xylanase"),
    ("phospholipase", "lipase"),
    ("lipase", "lipase"),
]

# ── French → English bakery terminology for query expansion ────────
# Sorted by length (longest first) for correct replacement order
BAKERY_FR_EN = [
    ("améliorant de panification", "bread improver baking additive"),
    ("quantités recommandées", "recommended dosage quantities"),
    ("acide ascorbique", "ascorbic acid vitamin C E300"),
    ("quelles sont les", "what are the"),
    ("glucose oxydase", "glucose oxidase"),
    ("panification", "bread making baking"),
    ("améliorant", "improver additive"),
    ("alpha-amylase", "alpha-amylase fungal amylase"),
    ("α-amylase", "alpha-amylase fungal amylase"),
    ("transglutaminase", "transglutaminase"),
    ("amyloglucosidase", "amyloglucosidase glucoamylase"),
    ("boulangerie", "bakery bread"),
    ("pâtisserie", "pastry"),
    ("xylanase", "xylanase"),
    ("quantité", "quantity dosage"),
    ("recommandé", "recommended"),
    ("dosage", "dosage"),
    ("farine", "flour"),
    ("lipase", "lipase"),
    ("enzyme", "enzyme"),
    ("pâte", "dough"),
]

# ── Ingredient-specific search templates ───────────────────────────
# Focused sub-queries per ingredient type for maximum embedding match
INGREDIENT_SEARCH_TEMPLATES = {
    "ascorbic acid": [
        "Ascorbic Acid E300 recommended dosage ppm bread improver",
        "acide ascorbique dosage panification améliorant",
    ],
    "alpha-amylase": [
        "alpha-amylase fungal amylase recommended dosage bread improver bakery enzyme",
        "BVZyme AF alpha-amylase dosage flour bread",
    ],
    "xylanase": [
        "xylanase endo-xylanase recommended dosage bread improver bakery enzyme",
        "BVZyme HCF HCB xylanase dosage flour bread",
    ],
    "lipase": [
        "lipase phospholipase recommended dosage bread improver bakery enzyme",
        "BVZyme L lipase dosage flour crumb softness",
    ],
    "glucose oxidase": [
        "glucose oxidase GOX recommended dosage bread improver bakery enzyme",
        "BVZyme GOX glucose oxidase dosage flour dough strength",
    ],
    "transglutaminase": [
        "transglutaminase TG recommended dosage bread improver bakery enzyme",
        "BVZyme TG transglutaminase dosage flour gluten network",
    ],
    "amyloglucosidase": [
        "amyloglucosidase glucoamylase AMG recommended dosage bread improver",
        "BVZyme AMG amyloglucosidase dosage flour fermentation",
    ],
    "maltogenic amylase": [
        "maltogenic amylase anti-staling recommended dosage bread improver",
        "BVZyme FRESH SOFT maltogenic amylase dosage shelf life",
    ],
}


class SearchController(BaseController):

    def __init__(self, embedding_service: EmbeddingService,
                 vectordb_client: PGVectorProvider):
        super().__init__()
        self.embedding_service = embedding_service
        self.vectordb_client = vectordb_client

    # ── Query decomposition ────────────────────────────────────────────

    def extract_ingredients(self, question: str) -> List[str]:
        """Extract individual ingredient / enzyme names from a query.

        Returns canonical English names found, ordered by appearance.
        Returns empty list if < 2 ingredients detected (no decomposition needed).
        """
        lower = question.lower()
        found = {}  # canonical → match position

        for term, canonical in KNOWN_INGREDIENTS:
            pos = lower.find(term)
            if pos >= 0 and canonical not in found:
                found[canonical] = pos

        if len(found) < 2:
            return []

        # Sort by position in query (preserve user's order)
        return [name for name, _ in sorted(found.items(), key=lambda x: x[1])]

    def _detect_intent(self, question: str) -> str:
        """Detect what the user is asking about (dosage, function, etc.)."""
        lower = question.lower()
        if any(w in lower for w in ['dosage', 'quantit', 'dose', 'ppm', 'recommand',
                                     'how much', 'amount']):
            return "dosage"
        if any(w in lower for w in ['function', 'fonct', 'role', 'rôle', 'effect',
                                     'what does', 'purpose']):
            return "function"
        return "dosage"  # default for bread improvement context

    # ── Query expansion ────────────────────────────────────────────────

    def is_french_query(self, question: str) -> bool:
        """Detect if a query contains French language."""
        french_words = [
            'quelles', 'quelle', 'quels', 'sont', 'les', 'des', 'recommandées',
            'recommandé', 'améliorant', 'panification', 'farine', 'pâte',
            'boulangerie', 'pâtisserie', 'acide', 'combien', 'comment',
            'pourquoi', 'utilisation',
        ]
        lower = question.lower()
        matches = sum(1 for w in french_words if w in lower)
        return matches >= 2

    def translate_query(self, question: str) -> str:
        """Translate French bakery terms to English for cross-lingual matching."""
        translated = question.lower()
        for fr_term, en_term in BAKERY_FR_EN:
            if fr_term in translated:
                translated = translated.replace(fr_term, en_term)
        translated = re.sub(r'\s+', ' ', translated).strip()
        translated = re.sub(r"[d'l']", '', translated)
        return translated

    # ── Keyword re-ranking ─────────────────────────────────────────────

    def keyword_boost(self, query: str, fragment: str,
                      boost_weight: float = 0.15) -> float:
        """Score boost based on keyword overlap between query and fragment."""
        stopwords = {
            'the', 'is', 'in', 'of', 'and', 'to', 'for', 'are', 'was', 'with',
            'this', 'that', 'les', 'des', 'est', 'une', 'par', 'pour', 'dans',
            'sur', 'qui', 'que', 'son', 'ses', 'aux', 'du', 'de', 'la', 'le',
            'also', 'known', 'used', 'based', 'from', 'bread', 'bakery',
        }

        def tokenize(text):
            tokens = re.findall(r'[a-zA-ZÀ-ÿ\-]{3,}', text.lower())
            return set(t for t in tokens if t not in stopwords)

        query_tokens = tokenize(query)
        fragment_tokens = tokenize(fragment)

        if not query_tokens:
            return 0.0

        overlap = query_tokens & fragment_tokens
        overlap_ratio = len(overlap) / len(query_tokens)
        return overlap_ratio * boost_weight

    # ── MMR Diversity ──────────────────────────────────────────────────

    def mmr_rerank(self, candidates: List[RetrievedFragment],
                   query_embedding: List[float],
                   top_k: int = 3,
                   lambda_param: float = 0.7) -> List[RetrievedFragment]:
        """Maximal Marginal Relevance with document-level diversity.

        Selects items that are relevant to the query but dissimilar to each
        other, preventing multiple near-duplicate fragments from the same
        enzyme type OR same source document from dominating the results.

        lambda_param: 1.0 = pure relevance, 0.0 = pure diversity
        """
        if len(candidates) <= top_k:
            return candidates

        # Re-embed candidate texts to compute inter-candidate similarity
        candidate_texts = [c.text for c in candidates]
        candidate_embeddings = self.embedding_service.embed_text(candidate_texts)

        query_vec = np.array(query_embedding)
        cand_vecs = np.array(candidate_embeddings)

        # Relevance = cosine similarity to query (already normalized)
        relevance = cand_vecs @ query_vec

        selected = []
        selected_indices = []
        selected_doc_ids = set()
        remaining = list(range(len(candidates)))

        for _ in range(top_k):
            if not remaining:
                break

            best_idx = None
            best_mmr = -float('inf')

            for idx in remaining:
                rel = float(relevance[idx])

                # Max similarity to any already-selected item
                if selected_indices:
                    sims = cand_vecs[selected_indices] @ cand_vecs[idx]
                    max_sim = float(np.max(sims))
                else:
                    max_sim = 0.0

                mmr = lambda_param * rel - (1 - lambda_param) * max_sim

                # Penalize candidates from an already-selected document
                if candidates[idx].document_id in selected_doc_ids:
                    mmr -= 0.15

                if mmr > best_mmr:
                    best_mmr = mmr
                    best_idx = idx

            if best_idx is not None:
                selected.append(candidates[best_idx])
                selected_indices.append(best_idx)
                selected_doc_ids.add(candidates[best_idx].document_id)
                remaining.remove(best_idx)

        return selected

    # ── Main search entry point ────────────────────────────────────────

    async def search(self, question: str, top_k: int = 3) -> List[RetrievedFragment]:
        """Enhanced search with query decomposition, expansion, and MMR.

        Strategy:
        1. Try to decompose query into individual ingredients
        2. If multi-ingredient: use per-ingredient slot allocation
           (1 best result per ingredient → perfectly diverse top-K)
        3. If single topic: standard search with MMR diversity
        """
        logger.info(f"Search query: {question[:80]}...")

        # Step 1: Try query decomposition
        ingredients = self.extract_ingredients(question)

        if len(ingredients) >= 2:
            logger.info(f"Detected {len(ingredients)} ingredients: {ingredients}")
            results, detected = await self._multi_ingredient_search(
                question, ingredients, top_k
            )
            return results, detected

        # Step 2: Single-topic search with MMR diversity
        results, detected = await self._single_topic_search(question, top_k)
        return results, detected

    # ── Multi-ingredient search ────────────────────────────────────────

    async def _multi_ingredient_search(
        self, question: str, ingredients: List[str], top_k: int
    ) -> List[RetrievedFragment]:
        """Search each ingredient independently and allocate 1 slot each.

        This guarantees diversity: if the user asks about 3 ingredients,
        they get 1 best result per ingredient instead of 3 results for
        the most common ingredient.
        """
        is_french = self.is_french_query(question)
        intent = self._detect_intent(question)

        per_ingredient_best: List[RetrievedFragment] = []

        for ing in ingredients:
            # Build multiple search queries for this ingredient
            search_queries = []

            # 1. Ingredient-specific templates (hand-crafted for best match)
            templates = INGREDIENT_SEARCH_TEMPLATES.get(ing, [])
            search_queries.extend(templates)

            # 2. Generic sub-query: ingredient + intent + context
            if intent == "dosage":
                search_queries.append(
                    f"{ing} recommended dosage ppm bread improver bakery"
                )
            else:
                search_queries.append(
                    f"{ing} function effect bread improver bakery enzyme"
                )

            logger.info(f"  Searching '{ing}' with {len(search_queries)} queries")

            # Embed all sub-queries and fetch candidates
            seen = {}
            for sq in search_queries:
                vec = self.embedding_service.embed_text(sq)
                results = await self.vectordb_client.search_by_vector(
                    vector=vec, limit=10
                )
                for r in results:
                    if r.text not in seen or r.score > seen[r.text].score:
                        seen[r.text] = r

            # Apply keyword boost specifically for this ingredient
            scored = []
            for text, result in seen.items():
                boost = self.keyword_boost(ing, text, boost_weight=0.20)
                final = min(result.score + boost, 1.0)
                scored.append(
                    RetrievedFragment(
                        text=result.text,
                        score=round(final, 4),
                        document_id=result.document_id,
                    )
                )

            # Pick the single best for this ingredient
            scored.sort(key=lambda x: x.score, reverse=True)
            if scored:
                per_ingredient_best.append(scored[0])
                logger.info(
                    f"  Best for '{ing}': score={scored[0].score:.4f}"
                )

        # Fill remaining slots if top_k > number of ingredients
        remaining_slots = top_k - len(per_ingredient_best)
        if remaining_slots > 0:
            selected_texts = {r.text for r in per_ingredient_best}
            selected_doc_ids = {r.document_id for r in per_ingredient_best}
            general_results, _ = await self._single_topic_search(question, top_k + 10)
            for r in general_results:
                if remaining_slots <= 0:
                    break
                # Skip same text OR same document (avoids dosage chunk
                # of an already-selected product appearing as filler)
                if r.text in selected_texts or r.document_id in selected_doc_ids:
                    continue
                per_ingredient_best.append(r)
                selected_texts.add(r.text)
                selected_doc_ids.add(r.document_id)
                remaining_slots -= 1

        # Sort by score DESC
        per_ingredient_best.sort(key=lambda x: x.score, reverse=True)
        final = per_ingredient_best[:top_k]

        logger.info(
            f"Multi-ingredient results: {[r.score for r in final]}"
        )
        return final, ingredients

    # ── Single-topic search ────────────────────────────────────────────

    async def _single_topic_search(
        self, question: str, top_k: int
    ) -> List[RetrievedFragment]:
        """Standard search with translation, keyword boost, and MMR."""
        queries = [question]

        if self.is_french_query(question):
            english_query = self.translate_query(question)
            if english_query.lower() != question.lower():
                queries.append(english_query)
                logger.info(f"English translation: {english_query[:80]}...")

        # Embed all query variants
        query_embeddings = []
        for q in queries:
            vec = self.embedding_service.embed_text(q)
            query_embeddings.append((q, vec))

        # Fetch candidates from all variant embeddings
        candidate_limit = max(top_k * 5, 15)
        seen = {}

        for q, vec in query_embeddings:
            results = await self.vectordb_client.search_by_vector(
                vector=vec, limit=candidate_limit
            )
            for r in results:
                if r.text not in seen or r.score > seen[r.text].score:
                    seen[r.text] = r

        if not seen:
            logger.info("No results found")
            return []

        # Apply keyword boost
        combined_query = " ".join([q for q, _ in query_embeddings])
        boosted = []

        for text, result in seen.items():
            boost = self.keyword_boost(combined_query, text)
            final_score = min(result.score + boost, 1.0)
            boosted.append(
                RetrievedFragment(
                    text=result.text,
                    score=round(final_score, 4),
                    document_id=result.document_id,
                )
            )

        # Sort by score and take top candidates for MMR selection
        boosted.sort(key=lambda x: x.score, reverse=True)
        mmr_pool = boosted[:max(top_k * 3, 10)]

        # Apply MMR for diversity (prevents duplicate enzyme types)
        primary_vec = query_embeddings[0][1]
        final = self.mmr_rerank(
            mmr_pool, primary_vec, top_k=top_k, lambda_param=0.7
        )

        # Re-sort by boosted score (MMR only selects, doesn't change scores)
        final.sort(key=lambda x: x.score, reverse=True)

        logger.info(
            f"Found {len(final)} results, scores: {[r.score for r in final]}"
        )
        return final, []
