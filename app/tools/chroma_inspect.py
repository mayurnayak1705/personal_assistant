"""Inspect the configured Chroma collection during local development."""

import chromadb

client = chromadb.PersistentClient(
    path="Databases/Chroma"
)

print(client.list_collections())

collection = client.get_collection("assistant_memory")

result = collection.get(
    include=["documents", "metadatas", "embeddings"]
)

print(result)
