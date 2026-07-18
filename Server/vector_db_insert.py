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


def add_vector(
    memory_id: str,
    summary: str,
    metadata: dict,
):

    embedding = get_embedding(summary)

    collection.add(
        ids=[memory_id],
        documents=[summary],
        embeddings=[embedding],
        metadatas=[metadata],
    )
