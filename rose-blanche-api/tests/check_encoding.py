"""Quick diagnostic to check raw text encoding in database."""
import psycopg2

conn = psycopg2.connect('postgresql://admin:admin@pgvector_db:5432/rag_db')
cur = conn.cursor()

# Check HCB710 chunks
cur.execute("SELECT id, LEFT(chunk_text, 300) FROM embeddings WHERE chunk_text LIKE '%HCB710%' LIMIT 3")
print("=== HCB710 chunks ===")
for r in cur.fetchall():
    print(f"ID={r[0]}")
    print(repr(r[1]))
    print()

# Check A SOFT205 chunks
cur.execute("SELECT id, LEFT(chunk_text, 300) FROM embeddings WHERE chunk_text LIKE '%SOFT205%' LIMIT 3")
print("=== A SOFT205 chunks ===")
for r in cur.fetchall():
    print(f"ID={r[0]}")
    print(repr(r[1]))
    print()

# Check French text
cur.execute("SELECT id, LEFT(chunk_text, 300) FROM embeddings WHERE chunk_text LIKE '%Ascorbique%' LIMIT 3")
print("=== French chunks ===")
for r in cur.fetchall():
    print(f"ID={r[0]}")
    print(repr(r[1]))
    print()

conn.close()
