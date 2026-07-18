import chromadb
import os
from dotenv import load_dotenv
from embedding_provider import collection_name, get_embedding

load_dotenv()

client = chromadb.PersistentClient(
    path=os.getenv("CHROMA_PATH", "Databases/Chroma")
)

collection = client.get_or_create_collection(
    name=collection_name()
)


def similarity_search(
    query: str,
    top_k: int = 5,
):

    embedding = get_embedding(query)

    results = collection.query(
        query_embeddings=[embedding],
        n_results=top_k,
    )

    return results
