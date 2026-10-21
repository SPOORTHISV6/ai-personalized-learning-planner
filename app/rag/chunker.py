import re


VALID_HEADINGS = {
    "inner join",
    "left join",
    "right join",
    "full outer join",
    "cross join",
    "self join",
    "join conditions",
    "join types",
    "sql joins",
    "introduction to sql joins",
}

INSTRUCTION_WORDS = {
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
    "create",
    "print",
    "derive",
    "compute",
    "evaluate",
}


def normalize_heading(line: str) -> str:
    """Remove numbering and normalize a heading."""

    line = line.strip()

    line = re.sub(
        r"^\d+(?:\.\d+)*\.?\s+",
        "",
        line
    )

    line = re.sub(r"\s+", " ", line)

    return line.strip().lower()


def is_instructional_line(line: str) -> bool:
    """Identify practice instructions and question-like lines."""

    text = line.strip()

    if not text:
        return True

    normalized = normalize_heading(text)

    # Preserve known legitimate SQL headings.
    if normalized in VALID_HEADINGS:
        return False

    # Questions and complete sentences are not headings.
    if text.endswith(("?", "!", ".")):
        return True

    instructional_phrases = [
        "write a query",
        "write sql",
        "write a sql",
        "find the",
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
        "answer the following",
        "solve the following",
    ]

    lower_text = text.lower()

    if any(
        phrase in lower_text
        for phrase in instructional_phrases
    ):
        return True

    words = normalized.split()

    if not words:
        return True

    first_word = re.sub(
        r"^[^a-z]+|[^a-z]+$",
        "",
        words[0]
    )

    if first_word in INSTRUCTION_WORDS:
        return True

    instruction_patterns = [
        r"\bjoin\s+\w+\s+with\s+\w+",
        r"\bselect\s+.+\s+from\b",
        r"\bwrite\s+.+",
        r"\bfind\s+.+",
        r"\bcalculate\s+.+",
        r"\bidentify\s+.+",
        r"\bdisplay\s+.+",
        r"\bretrieve\s+.+",
    ]

    for pattern in instruction_patterns:
        if re.search(pattern, normalized):
            return True

    if len(text) > 100:
        return True

    if len(words) > 12:
        return True

    return False


def is_heading(line: str) -> bool:
    """
    Detect numbered section headings while rejecting
    numbered questions and practice instructions.
    """

    line = line.strip()

    if not line:
        return False

    # Supports:
    # 1. Introduction to DBMS
    # 7. Normalization
    # 10.5.1 First Normal Form (1NF)
    if not re.match(
        r"^\d+(?:\.\d+)*\.?\s+\S",
        line
    ):
        return False

    if is_instructional_line(line):
        return False

    return True


def split_large_section(
    section_text: str,
    chunk_size: int,
    overlap: int,
    section_title: str,
    page_number: int,
    chunks: list
):
    """Split a section into overlapping word-based chunks."""

    words = section_text.split()

    if not words:
        return

    start = 0

    while start < len(words):

        end = start + chunk_size
        content_words = words[start:end]

        if not content_words:
            break

        content = " ".join(content_words)

        chunk_text = (
            f"Section: {section_title}\n"
            f"{content}"
        )

        chunks.append({
            "chunk_id": len(chunks),
            "page_number": page_number,
            "section_title": section_title,
            "text": chunk_text
        })

        if end >= len(words):
            break

        start = end - overlap


def create_chunks(
    pages,
    chunk_size=200,
    overlap=40
):
    """
    Create heading-aware chunks from extracted PDF pages.

    Each chunk contains:
        chunk_id
        page_number
        section_title
        text
    """

    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than 0."
        )

    if overlap < 0:
        raise ValueError(
            "overlap cannot be negative."
        )

    if overlap >= chunk_size:
        raise ValueError(
            "overlap must be smaller than chunk_size."
        )

    chunks = []

    current_section_title = "General"
    current_section_content = []
    current_section_page = 1

    def flush_section():
        nonlocal current_section_content
        nonlocal current_section_title
        nonlocal current_section_page

        if not current_section_content:
            return

        section_text = " ".join(
            current_section_content
        ).strip()

        if section_text:
            split_large_section(
                section_text=section_text,
                chunk_size=chunk_size,
                overlap=overlap,
                section_title=current_section_title,
                page_number=current_section_page,
                chunks=chunks
            )

        current_section_content = []

    for page in pages:

        page_number = page["page_number"]
        text = page["text"]

        for raw_line in text.splitlines():

            line = raw_line.strip()

            if not line:
                continue

            if is_heading(line):

                # Save the previous section.
                flush_section()

                # Begin the new section.
                current_section_title = line
                current_section_page = page_number

            else:

                # Preserve questions and exercises as
                # ordinary content under the current section.
                if not current_section_content:
                    current_section_page = page_number

                current_section_content.append(line)

    # Save the final section.
    flush_section()

    return chunks