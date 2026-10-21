import os

from app.rag.pdf_loader import load_pdf
from app.rag.chunker import create_chunks
from app.rag.retriever import RAGRetriever


PDF_PATH = "data/documents/dbms.pdf"

INDEX_PATH = (
    "data/vector_store/dbms/index.faiss"
)

METADATA_PATH = (
    "data/vector_store/dbms/metadata.json"
)


def main():

    print("\n==============================")
    print("RAG PIPELINE TEST")
    print("==============================")

    retriever = RAGRetriever(
        index_path=INDEX_PATH,
        metadata_path=METADATA_PATH
    )

    # --------------------------------------------------
    # STEP 1: Load existing vector store or build it
    # --------------------------------------------------

    if retriever.exists():

        print("\n[1] Existing vector store found.")

        retriever.load_existing()

    else:

        print("\n[1] No vector store found.")

        if not os.path.exists(PDF_PATH):

            print("\nERROR:")
            print(f"PDF not found: {PDF_PATH}")

            print("\nPlace the PDF inside:")
            print("data/documents/")

            return

        # ----------------------------------------------
        # STEP 2: Load PDF
        # ----------------------------------------------

        print("\n[2] Loading PDF...")

        pages = load_pdf(PDF_PATH)

        print(
            f"Pages extracted: {len(pages)}"
        )

        if not pages:

            print(
                "ERROR: No text extracted from PDF."
            )

            return

        # ----------------------------------------------
        # STEP 3: Create heading-aware chunks
        # ----------------------------------------------

        print("\n[3] Creating heading-aware chunks...")

        chunks = create_chunks(
            pages,
            chunk_size=200,
            overlap=40
        )

        print(
            f"Chunks created: {len(chunks)}"
        )

        if not chunks:

            print(
                "ERROR: No chunks created."
            )

            return

        # ----------------------------------------------
        # STEP 4: Build vector store
        # ----------------------------------------------

        print(
            "\n[4] Building vector store..."
        )

        retriever.build_from_chunks(chunks)

    # --------------------------------------------------
    # STEP 5: Ask user for query
    # --------------------------------------------------

    query = input(
        "\nEnter your learning question: "
    ).strip()

    if not query:

        print(
            "No query entered."
        )

        return

    # --------------------------------------------------
    # STEP 6: Semantic search
    # --------------------------------------------------

    print(
        "\n[5] Searching relevant content..."
    )

    results = retriever.retrieve(
        query=query,
        top_k=5
    )

    # --------------------------------------------------
    # STEP 7: Display results
    # --------------------------------------------------

    print("\n==============================")
    print("RETRIEVED CONTENT")
    print("==============================")

    if not results:

        print(
            "\nNo relevant content found."
        )

        return

    for i, result in enumerate(
        results,
        start=1
    ):

        print(
            f"\n--- Result {i} ---"
        )

        print(
            f"Page: {result['page_number']}"
        )

        print(
            f"Section: "
            f"{result.get('section_title', 'Unknown')}"
        )

        print(
            f"Similarity: "
            f"{result['similarity_score']:.4f}"
        )

        print("\nContent:")

        print(
            result["text"]
        )


if __name__ == "__main__":
    main()