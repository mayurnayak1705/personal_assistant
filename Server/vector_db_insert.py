import chromadb
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
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