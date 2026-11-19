
from pathlib import Path
import json
import os
import re

import faiss
import numpy as np

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from sentence_transformers import SentenceTransformer


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCUMENT_DIR = PROJECT_ROOT / "data" / "documents"
VECTOR_DIR = PROJECT_ROOT / "data" / "vector_store"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

MAX_CHARS = 1500
MIN_CHARS = 60

DOCUMENTS = {
    "normalization": "normalization.pdf",
    "sql_joins": "sql_joins.pdf",
    "python": "python_oop.pdf",
    "sql_basics": "sql_basics.pdf",
}


# ============================================================
# HEADING CONFIGURATION
# ============================================================

HEADINGS_BY_TOPIC = {
    "normalization": {
        "what is database normalization",
        "functional dependencies",
        "anomalies in poorly designed tables",
        "insertion anomaly",
        "deletion anomaly",
        "first normal form (1nf)",
        "second normal form (2nf)",
        "third normal form (3nf)",
        "boyce-codd normal form (bcnf)",
        "comparison at a glance",
        "worked normalization example",
        "common mistakes",
        "validation checklist",
        "quick revision",
        "quick revision and practice",
        "quick revision checklist",
        "practice questions",
        "practice question",
    },
    "python": {
        "introduction to oop",
        "classes and objects",
        "constructor and self",
        "encapsulation",
        "inheritance",
        "using super()",
        "polymorphism",
        "abstraction",
        "class vs instance variables",
        "special methods",
        "composition",
        "interview revision",
        "class vs object",
        "inheritance vs composition",
        "overriding vs overloading",
        "encapsulation vs abstraction",
        "quick practice questions",
        "practice questions",
        "practice question",
    },
    "sql_basics": {
        "relational database and tables",
        "select and from",
        "select: retrieve data",
        "where and operators",
        "null and three-valued logic",
        "null and common mistakes",
        "order by",
        "order by and limit",
        "aggregate functions",
        "group by and having",
        "case expressions",
        "insert, update, and delete",
        "update, delete, alter, and drop",
        "constraints and keys",
        "subqueries",
        "quick revision and practice",
        "quick revision",
        "query order concept",
        "practice questions",
        "practice question",
    },
    "sql_joins": {
        "introduction to sql joins",
        "sample tables",
        "inner join",
        "left join",
        "right join",
        "full outer join",
        "cross join",
        "self join",
        "cross join and self join",
        "join conditions",
        "join conditions and null",
        "comparison at a glance",
        "common mistakes",
        "interview practice",
        "practice questions",
        "practice question",
    },
}

GENERIC_HEADINGS = {
    "introduction",
    "overview",
    "conclusion",
    "summary",
    "practice questions",
    "practice question",
    "worked solutions",
    "worked examples",
    "quick revision",
    "quick revision checklist",
    "quick revision and practice",
    "interview revision",
    "interview practice",
    "common mistakes",
    "comparison at a glance",
}


# ============================================================
# CLEANING
# ============================================================

def normalize_line(line):
    return re.sub(r"\s+", " ", line).strip()


def clean_text(text):
    if not text:
        return ""

    text = text.replace("\x00", " ").replace("\u00a0", " ")
    text = text.replace("\uf0b7", "\n").replace("\u2022", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize_title(title):
    title = normalize_line(title)
    title = re.sub(
        r"^(?:section\s*:\s*)",
        "",
        title,
        flags=re.I,
    )
    title = re.sub(
        r"^\d+(?:\.\d+)*[.)]?\s*",
        "",
        title,
    )
    return title.casefold().strip(" :")


def is_page_artifact(line, index_name):
    line = normalize_line(line)
    lower = line.casefold()

    if not line:
        return True

    if re.fullmatch(r"(?:page\s*)?\d+", lower):
        return True

    if re.fullmatch(r"page\s+\d+(?:\s+of\s+\d+)?", lower):
        return True

    if "ai personalized learning & study planner" in lower:
        return True

    if lower.startswith("retrieved ") and "http" in lower:
        return True

    # Reject duplicated numbering such as:
    # 11. 11. Interview Practice
    if re.match(r"^\d{1,2}\.\s+\d{1,2}\.\s+", line):
        return True

    if index_name == "normalization" and lower in {
        "introduction to data normalization",
        "database design",
    }:
        return True

    # Reject table separators and empty table cells.
    if re.fullmatch(r"[-_=|+:\s]+", line):
        return True

    return False


# ============================================================
# PDF EXTRACTION
# ============================================================

def extract_pdf_text(pdf_path, index_name):
    pages = []

    try:
        with fitz.open(pdf_path) as document:
            line_counts = {}

            for page in document:
                for raw_line in page.get_text("text").splitlines():
                    line = normalize_line(raw_line)

                    if 4 <= len(line) <= 90:
                        key = line.casefold()
                        line_counts[key] = line_counts.get(key, 0) + 1

            repeated_lines = {
                line
                for line, count in line_counts.items()
                if count >= max(3, int(len(document) * 0.5))
            }

            for page_number, page in enumerate(document, start=1):
                kept_lines = []

                for raw_line in page.get_text("text").splitlines():
                    line = normalize_line(raw_line)

                    if not line:
                        kept_lines.append("")
                        continue

                    if line.casefold() in repeated_lines:
                        continue

                    if is_page_artifact(line, index_name):
                        continue

                    kept_lines.append(line)

                text = clean_text("\n".join(kept_lines))

                if text:
                    pages.append({
                        "page_number": page_number,
                        "text": text,
                    })

    except Exception as exc:
        print(f"[ERROR] Could not read {pdf_path}: {exc}")
        return []

    return pages


# ============================================================
# CODE DETECTION
# ============================================================

def is_actual_code(line):
    """
    Detect executable code without classifying normal SQL topic
    headings such as GROUP BY and ORDER BY as code.
    """
    line = normalize_line(line)

    patterns = [
        r"^(?:async\s+)?def\s+\w+\s*\(",
        r"^class\s+[A-Za-z_]\w*\s*[:(]",
        r"^(?:return|yield|raise|pass|break|continue)\b",
        r"^(?:if|elif|else|for|while|try|except|finally|with)\b",
        r"^(?:import|from)\s+\w+",
        r"^(?:print|len|range|super)\s*\(",
        r"^self\.\w+\s*=",
        r"^@\w+",
        r"^(?:SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\s+",
        r"^#",
    ]

    return any(
        re.match(pattern, line, re.I)
        for pattern in patterns
    )


# ============================================================
# HEADING DETECTION
# ============================================================

def detect_heading(line, index_name):
    """
    Return a recognized heading or None.

    Important:
    - Numbered headings are checked before code detection.
    - Python example class declarations remain body content.
    - SQL code fragments are not automatically treated as headings.
    - Only headings appropriate for the current PDF are accepted.
    """
    line = normalize_line(line)

    if not line or len(line) > 110:
        return None

    if is_page_artifact(line, index_name):
        return None

    if "|" in line:
        return None

    # Reject malformed duplicate numbering.
    if re.match(r"^\d{1,2}\.\s+\d{1,2}\.\s+", line):
        return None

    candidate = line

    # Strip one numbering prefix, e.g.:
    # 2. Classes and Objects
    # 3.1 First Normal Form (1NF)
    match = re.match(
        r"^\d{1,2}(?:\.\d+)*[.)]?\s+(.+)$",
        line,
    )

    if match:
        candidate = match.group(1).strip().rstrip(":").strip()

    key = normalize_title(candidate)

    # Topic-specific exact heading recognition.
    allowed = HEADINGS_BY_TOPIC.get(index_name, set())

    if key in allowed or key in GENERIC_HEADINGS:
        # Do not treat numbered questions as headings.
        if candidate.endswith("?"):
            return None

        return candidate

    # Avoid splitting sections at Python class declarations,
    # SQL statements, assignments, and other executable code.
    if is_actual_code(candidate):
        return None

    # Do not accept arbitrary short lines as headings.
    # This prevents labels such as FROM Employees, INNER, SELF,
    # and individual table-cell labels becoming separate chunks.
    if match:
        if len(candidate) <= 85 and len(candidate.split()) <= 12:
            question_starts = (
                "what ",
                "why ",
                "how ",
                "when ",
                "where ",
                "which ",
                "who ",
                "explain ",
                "define ",
                "describe ",
                "discuss ",
                "write ",
                "find ",
                "show ",
                "list ",
                "give ",
                "calculate ",
            )

            if not candidate.casefold().startswith(question_starts):
                # Only accept a numbered title if it resembles a
                # section heading, not a table value or SQL statement.
                if re.match(
                    r"^[A-Za-z][A-Za-z0-9 &(),/'-]{1,70}$",
                    candidate,
                ):
                    return candidate

    return None


# ============================================================
# TEXT CHUNKING
# ============================================================

def split_long_text(text, max_chars=MAX_CHARS):
    text = clean_text(text)

    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        if len(sentence) > max_chars:
            words = sentence.split()

            for word in words:
                candidate = f"{current} {word}".strip()

                if len(candidate) <= max_chars:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    current = word

            continue

        candidate = f"{current} {sentence}".strip()

        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = sentence

    if current:
        chunks.append(current)

    return chunks


def create_unique_chunks(chunks):
    unique = []
    seen = set()

    for chunk in chunks:
        content = chunk["content"].strip()

        if len(content) < MIN_CHARS:
            continue

        normalized_content = re.sub(
            r"\W+",
            " ",
            content.casefold(),
        ).strip()

        key = (
            normalize_title(chunk["section_title"]),
            normalized_content,
        )

        if key in seen:
            continue

        seen.add(key)

        chunk["chunk_id"] = len(unique)
        unique.append(chunk)

    return unique


def create_heading_chunks(pages, index_name):
    chunks = []

    current_title = "General"
    current_page = 1
    current_lines = []

    def flush():
        nonlocal current_lines

        if not current_lines:
            return

        body = clean_text("\n".join(current_lines))
        current_lines = []

        if len(body) < MIN_CHARS:
            return

        full_text = f"Section: {current_title}\n{body}"

        for part in split_long_text(full_text):
            if len(part.strip()) < MIN_CHARS:
                continue

            chunks.append({
                "chunk_id": len(chunks),
                "page_number": current_page,
                "section_title": current_title,
                "content": part,
            })

    for page in pages:
        page_number = page["page_number"]

        for raw_line in page["text"].splitlines():
            line = normalize_line(raw_line)

            if not line or is_page_artifact(line, index_name):
                continue

            title = detect_heading(line, index_name)

            if title:
                # Repeated section headings should not create duplicates.
                if normalize_title(title) == normalize_title(current_title):
                    continue

                flush()

                current_title = title
                current_page = page_number
                continue

            # Code examples and SQL fragments stay inside their
            # current concept instead of becoming standalone sections.
            if not current_lines:
                current_page = page_number

            current_lines.append(line)

            if len("\n".join(current_lines)) >= MAX_CHARS:
                flush()
                current_page = page_number

    flush()

    return create_unique_chunks(chunks)


# ============================================================
# NORMALIZATION CHUNKING
# ============================================================

NORMALIZATION_SECTIONS = {
    1: "What is Database Normalization",
    2: "Functional Dependencies",
    3: "Anomalies in Poorly Designed Tables",
    4: "First Normal Form (1NF)",
    5: "Second Normal Form (2NF)",
    6: "Third Normal Form (3NF)",
    7: "Boyce-Codd Normal Form (BCNF)",
    8: "Comparison at a Glance",
    9: "Worked Normalization Example",
    10: "Common Mistakes",
    11: "Quick Revision Checklist",
    12: "Practice Questions",
}


def detect_normalization_heading(line):
    line = normalize_line(line).rstrip(":").strip().rstrip("?").strip()

    match = re.match(r"^(\d{1,2})\.\s+(.+)$", line)

    if not match:
        return None

    number = int(match.group(1))
    title = normalize_title(match.group(2))
    expected = NORMALIZATION_SECTIONS.get(number)

    if expected and title == normalize_title(expected):
        return expected

    return None


def create_normalization_chunks(pages):
    chunks = []
    current_title = None
    current_page = 1
    current_lines = []

    def flush():
        nonlocal current_lines

        if current_title is None or not current_lines:
            current_lines = []
            return

        body = clean_text("\n".join(current_lines))
        current_lines = []

        if len(body) < MIN_CHARS:
            return

        full_text = (
            f"Database Normalization. "
            f"Section: {current_title}\n{body}"
        )

        for part in split_long_text(full_text):
            if len(part.strip()) < MIN_CHARS:
                continue

            chunks.append({
                "chunk_id": len(chunks),
                "page_number": current_page,
                "section_title": current_title,
                "content": part,
            })

    for page in pages:
        page_number = page["page_number"]

        for raw_line in page["text"].splitlines():
            line = normalize_line(raw_line)

            if not line or is_page_artifact(line, "normalization"):
                continue

            title = detect_normalization_heading(line)

            if title:
                flush()
                current_title = title
                current_page = page_number
                continue

            # Ignore cover-page material before the first real section.
            if current_title is None:
                continue

            if re.fullmatch(r"[\d\s|,.;:-]+", line):
                continue

            current_lines.append(line)

    flush()

    return create_unique_chunks(chunks)


# ============================================================
# CHUNK ROUTING
# ============================================================

def create_chunks(pages, index_name):
    if not pages:
        return []

    if index_name == "normalization":
        chunks = create_normalization_chunks(pages)
    else:
        chunks = create_heading_chunks(pages, index_name)

    if index_name == "sql_basics":
        for chunk in chunks:
            if not chunk["content"].casefold().startswith("sql basics."):
                chunk["content"] = "SQL Basics. " + chunk["content"]

    for chunk_id, chunk in enumerate(chunks):
        chunk["chunk_id"] = chunk_id

    return chunks


# ============================================================
# INDEX BUILDING
# ============================================================

def build_index(index_name, pdf_filename, model):
    pdf_path = DOCUMENT_DIR / pdf_filename
    output_dir = VECTOR_DIR / index_name
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print(f"BUILDING INDEX: {index_name}")
    print(f"PDF: {pdf_path}")
    print("=" * 60)

    if not pdf_path.exists():
        print(f"[ERROR] PDF not found: {pdf_path}")
        return False

    pages = extract_pdf_text(pdf_path, index_name)

    print(f"[PDF] Pages with text: {len(pages)}")

    if not pages:
        print("[ERROR] No readable text found.")
        return False

    chunks = create_chunks(pages, index_name)

    print(f"[RAG] Chunks created: {len(chunks)}")

    if not chunks:
        print("[ERROR] No usable chunks created.")
        return False

    for chunk in chunks:
        print(
            f"  Page {chunk['page_number']} | "
            f"{chunk['section_title']} | "
            f"{len(chunk['content'])} chars"
        )

    embeddings = model.encode(
        [chunk["content"] for chunk in chunks],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    embeddings = np.asarray(embeddings, dtype=np.float32)

    if embeddings.ndim != 2 or embeddings.shape[0] != len(chunks):
        print("[ERROR] Invalid embedding matrix.")
        return False

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    index_path = output_dir / "index.faiss"
    metadata_path = output_dir / "metadata.json"

    # Save temporary files first, then replace existing files.
    # This reduces the risk of leaving a half-written index.
    temp_index = output_dir / "index.tmp.faiss"
    temp_metadata = output_dir / "metadata.tmp.json"

    try:
        faiss.write_index(index, str(temp_index))

        with open(temp_metadata, "w", encoding="utf-8") as file:
            json.dump(chunks, file, indent=2, ensure_ascii=False)

        os.replace(temp_index, index_path)
        os.replace(temp_metadata, metadata_path)

    except Exception as exc:
        print(f"[ERROR] Saving index failed: {exc}")

        for path in (temp_index, temp_metadata):
            if path.exists():
                path.unlink()

        return False

    print(f"[SUCCESS] {index_name}: {index.ntotal} vectors")
    print(f"[FAISS] Dimension: {embeddings.shape[1]}")
    print(f"[FAISS] Index saved: {index_path}")
    print(f"[FAISS] Metadata saved: {metadata_path}")

    return True


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("AI PERSONALIZED LEARNING & STUDY PLANNER")
    print("RAG INDEX BUILDER")
    print("=" * 60)

    print(f"Project root: {PROJECT_ROOT}")
    print(f"Documents: {DOCUMENT_DIR}")
    print(f"Vector stores: {VECTOR_DIR}")

    if not DOCUMENT_DIR.exists():
        print(f"[ERROR] Document directory not found: {DOCUMENT_DIR}")
        return

    try:
        model = SentenceTransformer(MODEL_NAME)
    except Exception as exc:
        print(f"[ERROR] Embedding model could not load: {exc}")
        return

    results = {}

    for index_name, pdf_filename in DOCUMENTS.items():
        results[index_name] = build_index(
            index_name,
            pdf_filename,
            model,
        )

    print("\n" + "=" * 60)
    print("INDEX BUILD SUMMARY")
    print("=" * 60)

    for name, success in results.items():
        print(f"{name:<20} {'SUCCESS' if success else 'FAILED'}")

    successful = sum(results.values())
    print(f"Successful indexes: {successful}/{len(results)}")

    if successful != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
