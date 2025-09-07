from sentence_transformers import SentenceTransformer
from embeddings.ingestion.chunking import chunk_text
import weaviate
from ingestion.load_files import load_all_data
from rag.rag_chain import client




embed_model = SentenceTransformer("all-MiniLM-L6-v2")
def ingest_doc(path):
    docs = load_all_data(path)
    if not docs:
        print(f"No documents found in {path}")
        return
    collection = client.collections.use("DocumentChunk")
    with collection.batch.fixed_size(batch_size=64) as batch:
        for doc in docs:
            chunks = chunk_text(doc['text'])
            
            for i, chunk in enumerate(chunks):
                vector = embed_model.encode(chunk).tolist()
                batch.add_object(
                    properties={
                        "text": chunk,
                        "source_id": doc["id"],
                        "title": doc["title"],
                        "chunk_index": i,
                        "images": doc['images'], 
                    },
                    vector=vector
                )

    print(f'Ingested {len(docs)} documents into Weaviate')
    client.close()
