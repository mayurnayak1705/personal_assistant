from Server.vector_db_search import similarity_search
from Server.postgre_search import fetch_records


def search_memory(
    query: str,
    top_k: int = 5,
):

    vector_results = similarity_search(
        query=query,
        top_k=top_k,
    )

    postgres_results = fetch_records(
        vector_results
    )

    return postgres_results