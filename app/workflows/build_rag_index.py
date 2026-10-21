
import os
import sys
import re
from pathlib import Path

from app.rag.pdf_loader import load_pdf
from app.rag.chunker import create_chunks
from app.rag.retriever import RAGRetriever


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DOCUMENTS_DIR = PROJECT_ROOT / "data" / "documents"
VECTOR_STORE_DIR = PROJECT_ROOT / "data" / "vector_store"


# --------------------------------------------------
# CHUNK FILTERING
# --------------------------------------------------

INSTRUCTIONAL_PHRASES = [
    "write a query",
    "write sql",
    "write a sql",
    "find the",
    "display the",
    "show the",
    "list the",
    "calculate the",
    "identify the",
    "explain how",
    "explain why",
    "what is the",
    "what are the",
    "which of the",
    "using self join",
    "using inner join",
    "using left join",
    "using right join",
    "using full outer join",
    "using cross join",
    "with their managers",
    "employees with their",
    "retrieve the",
    "fetch the",
    "determine the",
    "consider the following",
    "answer the following",
    "solve the following",
]

# These are valid SQL headings even though some contain
# words that could otherwise be interpreted as instructions.
VALID_SQL_HEADINGS = {
    "inner join",
    "left join",
    "right join",
    "full outer join",
    "cross join",
    "self join",
    "join conditions",
    "join types",
    "introduction to sql joins",
    "sql joins",
}


def normalize_heading(text):
    """
    Normalize a heading for comparison.

    Example:
        '4. INNER JOIN' -> 'inner join'
    """

    text = text.strip()

    text = re.sub(
        r"^\d+(?:\.\d+)*\.?\s*",
        "",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip().lower()


def is_instructional_text(text):
    """
    Detect sentences that look like practice questions
    or instructions rather than section headings.
    """

    cleaned = text.strip().lower()

    if not cleaned:
        return True

    # A sentence ending in punctuation is more likely
    # to be an instruction than a section heading.
    if cleaned.endswith(("?", "!", ".")):
        return True

    for phrase in INSTRUCTIONAL_PHRASES:
        if phrase in cleaned:
            return True

    # Reject sentence-like instructions containing
    # common action verbs followed by additional text.
    instructional_patterns = [
        r"\bjoin\s+\w+\s+with\s+\w+",
        r"\bselect\s+.+\s+from\s+",
        r"\bwrite\s+",
        r"\bfind\s+",
        r"\bdisplay\s+",
        r"\bcalculate\s+",
        r"\bidentify\s+",
        r"\bcompare\s+",
        r"\bdemonstrate\s+",
        r"\bexecute\s+",
        r"\bperform\s+",
    ]

    for pattern in instructional_patterns:
        if re.search(pattern, cleaned):
            return True

    return False


def is_valid_numbered_heading(text):
    """
    Determine whether a numbered line is a genuine
    section heading rather than a numbered exercise.

    Examples accepted:
        2. INNER JOIN
        3. LEFT JOIN
        4. RIGHT JOIN
        7. SELF JOIN
        8. JOIN Conditions

    Example rejected:
        4. Join employees with their managers using SELF JOIN.
    """

    text = text.strip()

    match = re.match(
        r"^\d{1,2}\.\s+(.+)$",
        text
    )

    if not match:
        return False

    heading_text = match.group(1).strip()
    normalized = normalize_heading(heading_text)

    if not normalized:
        return False

    # Explicitly preserve known legitimate SQL headings.
    if normalized in VALID_SQL_HEADINGS:
        return True

    # Practice instructions commonly end with punctuation
    # or contain phrases such as "using SELF JOIN".
    if is_instructional_text(heading_text):
        return False

    # Keep headings reasonably short.
    words = heading_text.split()

    if len(words) > 9:
        return False

    # Reject numbered questions.
    if "?" in heading_text:
        return False

    # Reject common exercise/instruction beginnings.
    first_word = words[0].lower().strip(".,:;")

    rejected_starts = {
        "write",
        "find",
        "show",
        "list",
        "calculate",
        "identify",
        "explain",
        "describe",
        "compare",
        "solve",
        "give",
        "select",
        "display",
        "retrieve",
        "fetch",
        "determine",
        "demonstrate",
        "execute",
        "perform",
        "consider",
        "answer",
    }

    if first_word in rejected_starts:
        return False

    return True


def filter_chunks(chunks):
    """
    Remove chunks that consist primarily of practice
    instructions accidentally interpreted as headings.

    The original chunk format is preserved so that
    RAGRetriever can continue using it.
    """

    filtered_chunks = []

    for chunk in chunks:
        if isinstance(chunk, dict):
            content = str(
                chunk.get("content", "")
            ).strip()

            section_title = str(
                chunk.get("section_title", "")
            ).strip()

            # Remove malformed section titles if the
            # chunker supplies section metadata.
            if section_title:
                normalized_title = normalize_heading(
                    section_title
                )

                if is_instructional_text(section_title):
                    print(
                        "[FILTER] Removed instructional "
                        f"section title: {section_title}"
                    )
                    continue

            # Reject a chunk only when its content is
            # essentially a standalone instruction.
            if content and is_instructional_text(content):
                if len(content.split()) <= 20:
                    print(
                        "[FILTER] Removed short "
                        f"instructional chunk: {content}"
                    )
                    continue

        elif isinstance(chunk, str):
            content = chunk.strip()

            if (
                content
                and len(content.split()) <= 20
                and is_instructional_text(content)
            ):
                print(
                    "[FILTER] Removed short "
                    f"instructional chunk: {content}"
                )
                continue

        filtered_chunks.append(chunk)

    return filtered_chunks


# --------------------------------------------------
# BUILD SUBJECT INDEX
# --------------------------------------------------

def build_subject_index(
    subject_name: str,
    pdf_filename: str
):
    print("\n==============================")
    print("BUILDING RAG KNOWLEDGE BASE")
    print("==============================")

    subject_key = (
        subject_name.strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )

    pdf_path = DOCUMENTS_DIR / pdf_filename

    index_directory = VECTOR_STORE_DIR / subject_key

    index_path = index_directory / "index.faiss"
    metadata_path = index_directory / "metadata.json"

    # --------------------------------------------------
    # CHECK PDF
    # --------------------------------------------------

    if not pdf_path.exists():
        print("\nERROR: PDF not found:")
        print(pdf_path)
        return False

    print(f"\nSubject: {subject_name}")
    print(f"PDF: {pdf_path}")

    # --------------------------------------------------
    # LOAD PDF
    # --------------------------------------------------

    print("\n[1] Loading PDF...")

    pages = load_pdf(str(pdf_path))

    print(f"Pages extracted: {len(pages)}")

    if not pages:
        print(
            "ERROR: No text could be extracted "
            "from the PDF."
        )
        return False

    # --------------------------------------------------
    # CREATE CHUNKS
    # --------------------------------------------------

    print("\n[2] Creating semantic chunks...")

    chunks = create_chunks(
        pages,
        chunk_size=200,
        overlap=40
    )

    print(f"Chunks created before filtering: {len(chunks)}")

    if not chunks:
        print("ERROR: No chunks were created.")
        return False

    # --------------------------------------------------
    # FILTER BAD CHUNKS
    # --------------------------------------------------

    print("\n[3] Filtering instructional chunks...")

    filtered_chunks = filter_chunks(chunks)

    print(
        "Chunks remaining after filtering: "
        f"{len(filtered_chunks)}"
    )

    if not filtered_chunks:
        print(
            "ERROR: All chunks were filtered out. "
            "Check your PDF and chunker output."
        )
        return False

    # --------------------------------------------------
    # BUILD VECTOR STORE
    # --------------------------------------------------

    print("\n[4] Building subject knowledge base...")

    index_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    retriever = RAGRetriever(
        index_path=str(index_path),
        metadata_path=str(metadata_path)
    )

    retriever.build_from_chunks(
        filtered_chunks
    )

    # --------------------------------------------------
    # SUCCESS
    # --------------------------------------------------

    print("\n[5] Knowledge base created successfully.")
    print(f"Subject: {subject_name}")
    print(f"Pages: {len(pages)}")
    print(f"Original chunks: {len(chunks)}")
    print(f"Indexed chunks: {len(filtered_chunks)}")
    print(f"Index: {index_path}")
    print(f"Metadata: {metadata_path}")

    return True


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():
    subject_name = "DBMS"
    pdf_filename = "dbms.pdf"

    if len(sys.argv) >= 2:
        subject_name = sys.argv[1]

    if len(sys.argv) >= 3:
        pdf_filename = sys.argv[2]

    success = build_subject_index(
        subject_name,
        pdf_filename
    )

    if success:
        print("\nRAG indexing completed.")
    else:
        print("\nRAG indexing failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
