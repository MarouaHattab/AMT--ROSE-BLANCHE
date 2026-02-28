# Rose Blanche RAG API

Module de recherche sémantique RAG pour le Défi AMT - Assistance à la formulation en boulangerie et pâtisserie.

## Architecture

```
rose-blanche-api/
├── main.py                    # FastAPI entry point
├── requirements.txt           # Python dependencies
├── .env                       # Configuration (PostgreSQL, model, etc.)
├── helpers/
│   └── config.py              # Pydantic settings
├── models/
│   ├── BaseDataModel.py       # Base model class
│   ├── DocumentModel.py       # CRUD for documents table
│   ├── EmbeddingModel.py      # CRUD for embeddings table
│   ├── db_schemes/
│   │   ├── base.py            # SQLAlchemy declarative base
│   │   └── schemes.py         # Document, Embedding, RetrievedFragment
│   └── enums/
│       └── ResponseEnums.py   # API response signals
├── controllers/
│   ├── BaseController.py      # Base controller
│   ├── DataController.py      # Ingestion: read MD → chunk → embed → store
│   └── SearchController.py    # Semantic search: question → embed → cosine → top-K
├── routes/
│   ├── base.py               # GET /api/v1/ (welcome)
│   ├── data.py               # POST /api/v1/data/ingest, GET /documents
│   ├── search.py             # POST /api/v1/search/ (main endpoint)
│   └── schemes/
│       └── search.py         # Pydantic request models
└── stores/
    ├── embedding/
    │   └── EmbeddingService.py  # sentence-transformers wrapper
    └── vectordb/
        ├── PGVectorProvider.py  # pgvector search provider
        └── VectorDBEnums.py     # Distance method enums
```

## Spécifications Techniques

| Paramètre | Valeur |
|-----------|--------|
| Modèle d'embedding | `all-MiniLM-L6-v2` |
| Bibliothèque | `sentence-transformers` |
| Dimension | 384 |
| Similarité | Cosine Similarity |
| Top-K | 3 |
| Base de données | PostgreSQL + pgvector |
| Table principale | `embeddings` (id, id_document, texte_fragment, vecteur VECTOR(384)) |

## Installation

```bash
# 1. Créer un environnement virtuel
python -m venv .venv
.venv\Scripts\activate  # Windows

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Configurer PostgreSQL
# - Créer la base de données 'rose_blanche'
# - Installer l'extension pgvector
# - Modifier .env si nécessaire

# 4. Lancer le serveur
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Endpoints API

### 1. Welcome
```
GET /api/v1/
```

### 2. Ingestion des documents
```
POST /api/v1/data/ingest
Body: { "chunk_size": 200, "overlap_size": 50 }
```
Lit les fichiers .md du dossier `dataset/`, les découpe en fragments, génère les embeddings et les stocke en base.

### 3. Recherche sémantique (endpoint principal)
```
POST /api/v1/search/
Body: { "question": "votre question", "top_k": 3 }
```

**Exemple:**
```json
{
  "question": "Améliorant de panification : quelles sont les quantités recommandées d'alpha-amylase, xylanase et d'Acide ascorbique ?",
  "top_k": 3
}
```

**Réponse:**
```json
{
  "signal": "search_success",
  "question": "...",
  "top_k": 3,
  "resultats": [
    { "rang": 1, "texte": "Dosage recommandé : ...", "score": 0.91, "id_document": 1 },
    { "rang": 2, "texte": "Alpha-amylase : ...", "score": 0.87, "id_document": 2 },
    { "rang": 3, "texte": "Xylanase : ...", "score": 0.82, "id_document": 3 }
  ]
}
```

### 4. Lister les documents
```
GET /api/v1/data/documents
```

### 5. Statistiques
```
GET /api/v1/data/embeddings/count
GET /api/v1/search/stats
```

## Workflow

1. **Ingestion** : `POST /api/v1/data/ingest` → lit les fiches techniques MD, les découpe, génère les embeddings, stocke dans PostgreSQL
2. **Recherche** : `POST /api/v1/search/` → reçoit la question, génère l'embedding, calcule la similarité cosinus, retourne les 3 fragments les plus pertinents
