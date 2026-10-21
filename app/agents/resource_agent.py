import json
import os
import re

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

VECTOR_STORE_DIR = "data/vector_store"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

TOP_K = 100
FINAL_RESULTS = 9

EXCLUDED_SECTIONS = {
    "FURTHER READING",
    "ATTRIBUTION",
    "ANSWERS",
    "ANSWER",
    "VIDEO LECTURE",
    "ACTIVITY",
    "BIBLIOGRAPHY",
    "REFERENCES",
    "WORKS CITED",
    "ACKNOWLEDGEMENTS",
    "ACKNOWLEDGMENTS",
    "TABLE OF CONTENTS",
    "CONTENTS",
    "LEARNING OBJECTIVES",
    "LEARNING OUTCOMES",
    "SUMMARY",
    "UNIT SUMMARY",
    "OVERVIEW",
    "INTRODUCTION",
    "INDEX",
    "GENERAL",
    "UNKNOWN",
    "OBJECTIVES",
    "UNTITLED",
    "PRACTICE QUESTIONS",
}

TOPIC_MAP = {
    "normalization": "normalization",
    "sql joins": "sql_joins",
    "python oop": "python",
    "sql basics": "sql_basics",
}

# Order matters. Earlier sections are selected first when available.
TEACHING_ORDER = {
    "normalization": [
        ["FIRST NORMAL FORM", "1NF"],
        ["SECOND NORMAL FORM", "2NF"],
        ["THIRD NORMAL FORM", "3NF"],
        ["BOYCE CODD NORMAL FORM", "BCNF"],
        ["FUNCTIONAL DEPENDENCY", "FUNCTIONAL DEPENDENCIES"],
        ["DECOMPOSITION"],
        ["ANOMALIES"],
        ["KEYS"],
        ["NORMAL FORMS"],
    ],
    "sql_joins": [
        ["INNER JOIN"],
        ["LEFT JOIN"],
        ["RIGHT JOIN"],
        ["FULL OUTER JOIN", "FULL JOIN"],
        ["CROSS JOIN"],
        ["SELF JOIN"],
        ["JOIN CONDITIONS"],
    ],
    "python": [
        ["CLASSES AND OBJECTS", "CLASS AND OBJECT"],
        ["CONSTRUCTOR AND SELF", "CONSTRUCTORS"],
        ["ENCAPSULATION"],
        ["INHERITANCE"],
        ["POLYMORPHISM"],
        ["ABSTRACTION"],
        ["CLASS VS INSTANCE VARIABLES"],
        ["SPECIAL METHODS"],
        ["COMPOSITION"],
    ],
    "sql_basics": [
        ["SELECT"],
        ["WHERE"],
        ["AGGREGATE FUNCTIONS"],
        ["GROUP BY AND HAVING"],
        ["GROUP BY"],
        ["HAVING"],
        ["ORDER BY AND LIMIT"],
        ["ORDER BY"],
    ],
}

SECTION_PRIORITY = {
    "normalization": {
        "FIRST NORMAL FORM": 2.0,
        "SECOND NORMAL FORM": 2.0,
        "THIRD NORMAL FORM": 2.0,
        "BOYCE CODD NORMAL FORM": 2.0,
        "FUNCTIONAL DEPENDENCY": 1.8,
        "FUNCTIONAL DEPENDENCIES": 1.8,
        "DECOMPOSITION": 1.6,
        "ANOMALIES": 1.5,
        "KEYS": 1.5,
        "COMPARISON AT A GLANCE": 1.5,
        "WORKED NORMALIZATION EXAMPLE": 1.7,
        "COMMON MISTAKES": 1.5,
    },
    "sql_joins": {
        "INNER JOIN": 2.0,
        "LEFT JOIN": 1.95,
        "RIGHT JOIN": 1.9,
        "FULL OUTER JOIN": 1.9,
        "FULL JOIN": 1.9,
        "CROSS JOIN": 1.8,
        "SELF JOIN": 1.8,
        "JOIN CONDITIONS": 1.7,
    },
    "python": {
        "CLASSES AND OBJECTS": 2.0,
        "CLASS AND OBJECT": 2.0,
        "CONSTRUCTOR AND SELF": 1.9,
        "CONSTRUCTORS": 1.9,
        "ENCAPSULATION": 1.85,
        "INHERITANCE": 1.85,
        "POLYMORPHISM": 1.85,
        "ABSTRACTION": 1.85,
        "CLASS VS INSTANCE VARIABLES": 1.7,
        "SPECIAL METHODS": 1.6,
        "COMPOSITION": 1.6,
    },
    "sql_basics": {
        "SELECT": 2.0,
        "WHERE": 1.95,
        "AGGREGATE FUNCTIONS": 1.9,
        "GROUP BY AND HAVING": 1.9,
        "GROUP BY": 1.85,
        "HAVING": 1.8,
        "ORDER BY AND LIMIT": 1.85,
        "ORDER BY": 1.8,
    },
}

_embedding_model = None


# ---------------------------------------------------------
# EMBEDDING MODEL
# ---------------------------------------------------------

def get_embedding_model():
    """Load the embedding model once per process."""
    global _embedding_model

    if _embedding_model is None:
        print("[Vector Store] Loading embedding model...")
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    else:
        print("[Vector Store] Using cached embedding model...")

    return _embedding_model


# ---------------------------------------------------------
# TEXT AND TITLE NORMALIZATION
# ---------------------------------------------------------

def normalize_section_title(section_title):
    """Normalize a section title for comparisons."""
    title = str(section_title or "").strip().upper()
    title = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s*", "", title)
    title = re.sub(r"\s+", " ", title)

    return title.strip(" .:-")


def compact_title(section_title):
    """Remove punctuation that does not affect title matching."""
    title = normalize_section_title(section_title)
    title = title.replace("-", " ").replace("_", " ")
    title = re.sub(r"[():]", "", title)
    return re.sub(r"\s+", " ", title).strip()


def normalize_content(content):
    """Normalize text for duplicate detection."""
    text = str(content or "").lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9 ]", "", text)

    return text.strip()


def get_knowledge_base(topic_name):
    """Map topic names to their vector-store directories."""
    normalized = str(topic_name or "").strip().lower()
    return TOPIC_MAP.get(normalized, normalized.replace(" ", "_"))


# ---------------------------------------------------------
# SECTION FILTERING
# ---------------------------------------------------------

def is_excluded_section(section_title):
    """Reject administrative and non-instructional sections."""
    title = compact_title(section_title)

    if not title:
        return True

    excluded = {compact_title(item) for item in EXCLUDED_SECTIONS}

    if title in excluded:
        return True

    if title.startswith("UPON COMPLETION"):
        return True

    if re.search(
        r"\b(references|bibliography|works cited|further reading|"
        r"acknowledgements|acknowledgments|table of contents)\b",
        title,
        flags=re.IGNORECASE,
    ):
        return True

    if re.match(r"^(https?://|www\.|ISBN\b|ISSN\b|DOI\b)", title):
        return True

    return False


def is_sentence_like_heading(title):
    """
    Reject headings that are actually sentence fragments extracted
    from the middle of a PDF paragraph.
    """
    cleaned = compact_title(title)

    suspicious_starts = (
        "THEREFORE",
        "HOWEVER",
        "FOR EXAMPLE",
        "FOR INSTANCE",
        "IN THIS",
        "AS FOLLOWS",
        "WHICH",
        "THAT",
        "BECAUSE",
        "HENCE",
        "THE RELATION",
        "THE TABLE",
        "IT IS",
        "THIS IS",
        "THE RESULT",
        "WE CAN",
        "YOU CAN",
        "NOTE THAT",
    )

    if cleaned.startswith(suspicious_starts):
        return True

    if re.search(r"[.!?]", cleaned):
        return True

    if len(cleaned.split()) > 12:
        return True

    return False


# ---------------------------------------------------------
# CHUNK QUALITY FILTER
# ---------------------------------------------------------

def is_substantive_chunk(candidate, knowledge_base):
    """
    Reject empty, administrative, extremely short, or fragmented
    chunks while preserving useful instructional examples.
    """
    content = str(
        candidate.get("content") or candidate.get("text") or ""
    ).strip()

    title = str(candidate.get("section_title") or "").strip()

    if not content or is_excluded_section(title):
        return False

    if is_sentence_like_heading(title):
        return False

    cleaned = re.sub(r"\s+", " ", content).strip()
    normalized_content = compact_title(cleaned)
    normalized_title = compact_title(title)

    if normalized_title and normalized_content == normalized_title:
        return False

    bad_patterns = [
        r"\bRetrieved\s+(January|February|March|April|May|June|July|"
        r"August|September|October|November|December)\b",
        r"https?://\S+",
        r"\bwww\.\S+",
        r"\bISBN\b",
        r"\bISSN\b",
        r"\bCreative Commons\b",
        r"\bAll rights reserved\b",
        r"\bCopyright\b",
        r"\bWorks Cited\b",
        r"\bBibliography\b",
        r"\bUpon completion of this unit you will be able to\b",
        r"\bLearning objectives?\b",
        r"\bLearning outcomes?\b",
    ]

    if any(
        re.search(pattern, cleaned, flags=re.IGNORECASE)
        for pattern in bad_patterns
    ):
        return False

    words = re.findall(r"\b[A-Za-z0-9_]+\b", cleaned)
    alphabetic_words = re.findall(r"\b[A-Za-z]{2,}\b", cleaned)

    # SQL examples can be compact, so use a separate threshold.
    is_sql_topic = knowledge_base in {"sql_basics", "sql_joins"}

    if is_sql_topic:
        has_sql = re.search(
            r"\b(SELECT|FROM|WHERE|JOIN|GROUP BY|HAVING|ORDER BY|"
            r"INSERT|UPDATE|DELETE|CREATE TABLE|COUNT|SUM|AVG)\b",
            cleaned,
            flags=re.IGNORECASE,
        )

        if has_sql and len(words) >= 8 and len(cleaned) >= 35:
            return True

    if len(words) < 12 or len(cleaned) < 65:
        return False

    if len(alphabetic_words) < 8:
        return False

    if re.match(
        r"^(and|or|but|which|that|these|those|therefore|hence|"
        r"because|where|when|below|above|thus|also)\b",
        cleaned,
        flags=re.IGNORECASE,
    ):
        first_sentence = re.split(
            r"[.!?]\s+", cleaned, maxsplit=1
        )[0]

        if len(first_sentence.split()) < 12:
            return False

    if re.search(
        r"\b(retrieved|available at|doi:|references|bibliography)\b",
        cleaned,
        flags=re.IGNORECASE,
    ):
        return False

    return True


# ---------------------------------------------------------
# VECTOR STORE LOADING
# ---------------------------------------------------------

def load_vector_store(topic_name):
    """Load FAISS index and matching chunk metadata."""
    index_path = os.path.join(
        VECTOR_STORE_DIR, topic_name, "index.faiss"
    )
    metadata_path = os.path.join(
        VECTOR_STORE_DIR, topic_name, "metadata.json"
    )

    print(f"[Resource Agent] Index: {index_path}")
    print(f"[Resource Agent] Metadata: {metadata_path}")

    if not os.path.exists(index_path) or not os.path.exists(metadata_path):
        print("[Vector Store] Index or metadata file not found.")
        return None, None

    try:
        index = faiss.read_index(index_path)

        with open(metadata_path, "r", encoding="utf-8") as file:
            metadata = json.load(file)

    except (OSError, ValueError, RuntimeError) as exc:
        print(f"[Vector Store] Could not load index: {exc}")
        return None, None

    if not isinstance(metadata, list):
        print("[Vector Store] Invalid metadata format.")
        return None, None

    if index.ntotal != len(metadata):
        print(
            "[Vector Store] WARNING: index count "
            f"{index.ntotal} differs from metadata count {len(metadata)}."
        )

    print("[Vector Store] Existing FAISS index loaded.")
    print(f"[Vector Store] Vectors: {index.ntotal}")
    print(f"[Vector Store] Chunks: {len(metadata)}")

    return index, metadata


def create_query_embedding(query, model):
    """Create a normalized query embedding."""
    embedding = model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    embedding = np.asarray(embedding, dtype=np.float32)
    faiss.normalize_L2(embedding)

    return embedding


# ---------------------------------------------------------
# QUERY GENERATION
# ---------------------------------------------------------

def build_rag_query(topic_name, subject_name, learning_status=None):
    """Build a topic-specific retrieval query."""
    topic = str(topic_name or "").strip()
    subject = str(subject_name or "").strip()

    focus_map = {
        "normalization": (
            "database normalization, first normal form 1NF, "
            "second normal form 2NF, third normal form 3NF, "
            "Boyce Codd normal form BCNF, functional dependencies, "
            "decomposition, keys, anomalies, comparison at a glance, "
            "worked normalization examples, common mistakes"
        ),
        "sql joins": (
            "SQL joins, INNER JOIN, LEFT JOIN, RIGHT JOIN, "
            "FULL OUTER JOIN, CROSS JOIN, SELF JOIN, join conditions, "
            "matching rows, SQL queries and examples"
        ),
        "python oop": (
            "Python object oriented programming, classes, objects, "
            "constructors, self, encapsulation, inheritance, "
            "polymorphism, abstraction, code examples"
        ),
        "sql basics": (
            "SQL SELECT, WHERE, aggregate functions, GROUP BY, HAVING, "
            "ORDER BY, LIMIT, filtering, queries and examples"
        ),
    }

    focus = focus_map.get(
        topic.lower(),
        f"{topic}, core concepts, definitions, and examples",
    )

    if learning_status == "weak":
        focus += (
            ", beginner-friendly explanations, step-by-step examples, "
            "common mistakes, practice questions"
        )
    elif learning_status == "moderate":
        focus += ", applied examples, practice, revision"
    else:
        focus += ", revision and reinforcement examples"

    return f"{topic} in {subject}. Focus on {focus}."


# ---------------------------------------------------------
# FAISS SEARCH
# ---------------------------------------------------------

def search_vector_store(index, metadata, query_embedding, top_k=TOP_K):
    """Retrieve chunks and calculate similarity scores."""
    if index is None or not metadata:
        return []

    count = min(max(top_k, FINAL_RESULTS), index.ntotal, len(metadata))

    if count <= 0:
        return []

    scores, indices = index.search(query_embedding, count)
    results = []

    is_l2 = getattr(index, "metric_type", None) == faiss.METRIC_L2

    for raw_score, idx in zip(scores[0], indices[0]):
        idx = int(idx)

        if idx < 0 or idx >= len(metadata):
            continue

        item = dict(metadata[idx])
        raw_score = float(raw_score)

        if is_l2:
            similarity = 1.0 - raw_score / 2.0
        else:
            similarity = raw_score

        item["similarity_score"] = float(
            np.clip(similarity, -1.0, 1.0)
        )

        results.append(item)

    return results


# ---------------------------------------------------------
# RANKING
# ---------------------------------------------------------

def get_section_priority(section_title, knowledge_base):
    """Return a relevance bonus for a known section."""
    title = compact_title(section_title)
    priorities = SECTION_PRIORITY.get(knowledge_base, {})

    for keyword, priority in sorted(
        priorities.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        normalized_keyword = compact_title(keyword)

        if title == normalized_keyword:
            return priority

        # Match only at the start of a heading, not inside prose.
        if title.startswith(normalized_keyword + " "):
            return priority

    return 1.0


def calculate_ranking_score(
    similarity_score,
    section_title,
    knowledge_base="",
):
    """Combine semantic similarity with section relevance."""
    similarity = float(similarity_score)
    priority = get_section_priority(section_title, knowledge_base)

    score = similarity + ((priority - 1.0) * 0.15)

    if is_excluded_section(section_title):
        score -= 1.0

    if is_sentence_like_heading(section_title):
        score -= 1.0

    return score


# ---------------------------------------------------------
# DEDUPLICATION
# ---------------------------------------------------------

def remove_duplicate_sections(candidates):
    """Keep the best candidate per section and remove near-duplicates."""
    best_by_section = {}

    for candidate in candidates:
        key = compact_title(
            candidate.get("section_title", "")
        ) or "GENERAL"

        previous = best_by_section.get(key)

        if (
            previous is None
            or candidate.get("ranking_score", 0.0)
            > previous.get("ranking_score", 0.0)
        ):
            best_by_section[key] = candidate

    ranked = sorted(
        best_by_section.values(),
        key=lambda item: item.get("ranking_score", 0.0),
        reverse=True,
    )

    unique = []
    seen_content = []

    for candidate in ranked:
        text = normalize_content(
            candidate.get("content") or candidate.get("text") or ""
        )

        if not text:
            continue

        tokens = set(text.split())
        duplicate = False

        for previous_tokens in seen_content:
            if not tokens or not previous_tokens:
                continue

            overlap = len(tokens & previous_tokens) / max(
                1, min(len(tokens), len(previous_tokens))
            )

            if overlap >= 0.90:
                duplicate = True
                break

        if duplicate:
            print(
                "[Resource Agent] Removed near-duplicate chunk: "
                f"{candidate.get('section_title', 'Untitled')}"
            )
            continue

        unique.append(candidate)
        seen_content.append(tokens)

    return unique


# ---------------------------------------------------------
# TOPIC-SPECIFIC SECTION MATCHING
# ---------------------------------------------------------

def section_matches_terms(section_title, terms):
    """Match a section title without accepting keyword mentions in prose."""
    title = compact_title(section_title)

    if not title or is_sentence_like_heading(title):
        return False

    for term in terms:
        normalized_term = compact_title(term)

        if not normalized_term:
            continue

        if title == normalized_term:
            return True

        # Permit a short descriptive suffix, e.g. "SELECT Statement".
        if title.startswith(normalized_term + " "):
            suffix = title[len(normalized_term):].strip()

            if len(suffix.split()) <= 4:
                return True

    return False


# ---------------------------------------------------------
# NORMALIZATION CURRICULUM LEVELS
# ---------------------------------------------------------
def _normalization_level(section_title):
    """
    Identify genuine Normalization curriculum headings.
    """
    title = compact_title(section_title)

    if not title or is_sentence_like_heading(title):
        # Allow known headings even if PDF extraction adds punctuation.
        normalized = re.sub(r"[.!?]+$", "", title).strip()

        if normalized != "COMPARISON AT A GLANCE":
            return 99

        title = normalized

    # Remove labels inserted by the PDF index builder.
    title = re.sub(r"^LEVEL\s+\d+\s+", "", title)
    title = re.sub(
        r"^SECTION\s+\d+\s*[:.-]?\s*",
        "",
        title,
    )

    patterns = [
        (0, r"^(FIRST NORMAL FORM|1NF)(?:\b|$)"),
        (1, r"^(SECOND NORMAL FORM|2NF)(?:\b|$)"),
        (2, r"^(THIRD NORMAL FORM|3NF)(?:\b|$)"),
        (3, r"^(BOYCE CODD NORMAL FORM|BCNF)(?:\b|$)"),
        (4, r"^FUNCTIONAL DEPENDENC(?:Y|IES)\b"),
        (5, r"^DECOMPOSITION\b"),
        (6, r"^ANOMAL(?:Y|IES)\b"),
        (7, r"^KEYS?\b"),
        (8, r"^(NORMAL FORMS?|COMPARISON AT A GLANCE)\b"),
        (9, r"^WORKED NORMALIZATION EXAMPLE\b"),
        (10, r"^WHAT IS DATABASE NORMALIZATION\b"),
        (11, r"^COMMON MISTAKES\b"),
    ]

    for level, pattern in patterns:
        if re.match(pattern, title):
            return level

    return 99


# ---------------------------------------------------------
# FINAL RESOURCE SELECTION
# ---------------------------------------------------------

def select_diverse_results(
    candidates,
    knowledge_base,
    final_results=FINAL_RESULTS,
):
    """
    Select distinct sections in curriculum order.

    Normalization uses an explicit priority order so that important
    study sections are selected before general introductory content.
    """
    if final_results <= 0:
        return []

    candidates = sorted(
        candidates,
        key=lambda item: item.get("ranking_score", 0.0),
        reverse=True,
    )

    # -----------------------------------------------------
    # NORMALIZATION CURRICULUM SELECTION
    # -----------------------------------------------------

    if knowledge_base == "normalization":
        print("[Resource Agent] Validating Normalization candidates:")

        best_by_level = {}

        for candidate in candidates:
            title = candidate.get("section_title", "")
            level = _normalization_level(title)

            if level < 99:
                print(f"  -> Level {level}: {title}")

                previous = best_by_level.get(level)

                if (
                    previous is None
                    or candidate.get("ranking_score", 0.0)
                    > previous.get("ranking_score", 0.0)
                ):
                    best_by_level[level] = candidate
            else:
                print(
                    "[Resource Agent] Ignoring non-curriculum heading: "
                    f"{title}"
                )

        selected = []

        # Explicit curriculum order:
        # 1NF, 2NF, 3NF, BCNF, Functional Dependencies,
        # Anomalies, Comparison, Worked Example, Common Mistakes.
        #
        # Decomposition and Keys are not discarded from the source.
        # They are simply lower priority in this nine-resource selection.
        preferred_levels = (0, 1, 2, 3, 4, 6, 8, 9, 11)

        for level in preferred_levels:
            candidate = best_by_level.get(level)

            if candidate is not None:
                selected.append(candidate)

            if len(selected) >= final_results:
                break

        print(
            "[Resource Agent] Normalization curriculum selection: "
            + ", ".join(
                item.get("section_title", "")
                for item in selected
            )
        )

        return selected

    # -----------------------------------------------------
    # OTHER TOPICS
    # -----------------------------------------------------

    selected = []
    used_sections = set()

    for terms in TEACHING_ORDER.get(knowledge_base, []):
        matching = []

        for candidate in candidates:
            section = compact_title(
                candidate.get("section_title", "")
            )

            if not section or section in used_sections:
                continue

            if section_matches_terms(
                candidate.get("section_title", ""),
                terms,
            ):
                matching.append(candidate)

        if matching:
            best = max(
                matching,
                key=lambda item: item.get("ranking_score", 0.0),
            )

            selected.append(best)
            used_sections.add(
                compact_title(best.get("section_title", ""))
            )

        if len(selected) >= final_results:
            return selected[:final_results]

    # Do not fill missing slots with unrelated headings.
    return selected[:final_results]


# ---------------------------------------------------------
# RESOURCE RETRIEVAL
# ---------------------------------------------------------

def retrieve_topic_resources(
    topic_name,
    subject_name,
    learning_status=None,
):
    """Retrieve, filter, rank, and select resources for one topic."""
    print(f"\n[Resource Agent] Topic: {topic_name}")
    print(f"[Resource Agent] Subject: {subject_name}")

    knowledge_base = get_knowledge_base(topic_name)

    print(
        f"[Resource Agent] Using topic knowledge base: {knowledge_base}"
    )

    index, metadata = load_vector_store(knowledge_base)

    if index is None or metadata is None or index.ntotal == 0:
        return []

    model = get_embedding_model()

    query = build_rag_query(
        topic_name,
        subject_name,
        learning_status,
    )

    print(f"[Resource Agent] RAG Query: {query}")

    query_embedding = create_query_embedding(query, model)

    candidates = search_vector_store(
        index,
        metadata,
        query_embedding,
        top_k=min(TOP_K, index.ntotal),
    )

    print(f"[Resource Agent] Retrieved candidates: {len(candidates)}")

    filtered = []

    for candidate in candidates:
        title = candidate.get("section_title", "")

        candidate["content"] = (
            candidate.get("content") or candidate.get("text") or ""
        )

        if is_excluded_section(title):
            print(
                "[Resource Agent] Excluded section: "
                f"{title or 'Untitled'}"
            )
            continue

        if not is_substantive_chunk(candidate, knowledge_base):
            print(
                "[Resource Agent] Rejected weak chunk: "
                f"{title or 'Untitled'}"
            )
            continue

        candidate["ranking_score"] = calculate_ranking_score(
            candidate.get("similarity_score", 0.0),
            title,
            knowledge_base,
        )

        filtered.append(candidate)

    filtered.sort(
        key=lambda item: item.get("ranking_score", 0.0),
        reverse=True,
    )

    filtered = remove_duplicate_sections(filtered)

    selected = select_diverse_results(
        filtered,
        knowledge_base,
        FINAL_RESULTS,
    )

    print(
        f"[Resource Agent] Accepted results for {topic_name}: "
        f"{len(selected)}"
    )

    for resource in selected:
        print(f"  -> {resource.get('section_title', 'General')}")

    return selected


# ---------------------------------------------------------
# LANGGRAPH RESOURCE AGENT
# ---------------------------------------------------------

def resource_agent(state):
    """Retrieve filtered learning resources for all learning gaps."""
    print("\n[Resource Agent] Finding learning resources...")

    all_resources = []

    for gap in state.get("learning_gaps", []):
        topic_name = gap.get("topic_name")

        if not topic_name:
            continue

        subject_name = gap.get("subject_name", "")

        resources = retrieve_topic_resources(
            topic_name=topic_name,
            subject_name=subject_name,
            learning_status=gap.get("status"),
        )

        for resource in resources:
            all_resources.append({
                "topic_id": gap.get("topic_id"),
                "topic_name": topic_name,
                "subject_id": gap.get("subject_id"),
                "subject_name": subject_name,
                "resource_type": "rag_content",
                "title": f"{topic_name} - Study Material",
                "source": resource.get(
                    "source",
                    f"{topic_name}.pdf",
                ),
                "page_number": resource.get("page_number"),
                "section_title": resource.get("section_title"),
                "content": resource.get("content", ""),
                "similarity_score": resource.get(
                    "similarity_score",
                    0.0,
                ),
                "ranking_score": resource.get(
                    "ranking_score",
                    0.0,
                ),
            })

    print(
        f"[Resource Agent] Retrieved {len(all_resources)} "
        "filtered learning resources."
    )

    state["resources"] = all_resources
    return state