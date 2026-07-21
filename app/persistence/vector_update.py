import chromadb
import os
from dotenv import load_dotenv
from app.core.embeddings import collection_name, get_embedding

load_dotenv()

client = chromadb.PersistentClient(
    path=os.getenv("CHROMA_PATH", "Databases/Chroma")
)

collection = client.get_or_create_collection(
    name=collection_name()
)


def update_vector(
    memory_id: str,
    summary: str,
    metadata: dict,
):
    """
    Update an existing vector by replacing its embedding,
    document, and metadata.
    """

    embedding = get_embedding(summary)

    # Chroma supports upsert, which will update if the ID exists
    # and insert if it doesn't.
    collection.upsert(
        ids=[memory_id],
        embeddings=[embedding],
        documents=[summary],
        metadatas=[metadata],
    )

    return memory_id
