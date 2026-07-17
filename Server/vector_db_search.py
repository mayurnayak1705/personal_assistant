import chromadb
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = chromadb.PersistentClient(
    path=os.getenv("CHROMA_PATH", "Databases/Chroma")
)

collection = client.get_or_create_collection(
    name="assistant_memory"
)

openai_client = OpenAI()


def get_embedding(text: str):

    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )

    return response.data[0].embedding


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
