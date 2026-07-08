import chromadb
from openai import OpenAI

client = chromadb.PersistentClient(
    path="/Users/mithunnayak/Desktop/WORK/personal_assistant/Databases/Chroma"
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