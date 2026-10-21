import os

from app.rag.vector_store import VectorStore


class RAGRetriever:

    def __init__(
        self,
        index_path=None,
        metadata_path=None
    ):

        self.index_path = index_path
        self.metadata_path = metadata_path

        self.vector_store = VectorStore()

    # --------------------------------
    # Configure index
    # --------------------------------

    def configure(
        self,
        index_path,
        metadata_path
    ):

        self.index_path = index_path
        self.metadata_path = metadata_path

    # --------------------------------
    # Build
    # --------------------------------

    def build_from_chunks(
        self,
        chunks
    ):

        self.vector_store.build(
            chunks
        )

        self.vector_store.save(
            self.index_path,
            self.metadata_path
        )

    # --------------------------------
    # Load
    # --------------------------------

    def load_existing(self):

        if not self.exists():

            raise FileNotFoundError(
                "RAG vector store does not exist:\n"
                f"Index: {self.index_path}\n"
                f"Metadata: {self.metadata_path}"
            )

        self.vector_store.load(
            self.index_path,
            self.metadata_path
        )

    # --------------------------------
    # Retrieve
    # --------------------------------

    def retrieve(
        self,
        query,
        top_k=3
    ):

        return self.vector_store.search(
            query=query,
            top_k=top_k
        )

    # --------------------------------
    # Exists
    # --------------------------------

    def exists(self):

        if not self.index_path:
            return False

        if not self.metadata_path:
            return False

        return (
            os.path.exists(
                self.index_path
            )
            and
            os.path.exists(
                self.metadata_path
            )
        )