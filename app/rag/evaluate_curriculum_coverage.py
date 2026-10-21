
import json
import re
from pathlib import Path

from app.agents.resource_agent import retrieve_topic_resources


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
REPORT_PATH = BASE_DIR / "data" / "curriculum_coverage_report.json"

CURRICULUM = {
    "normalization": {
        "subject": "DBMS",
        "concepts": {
            "FIRST NORMAL FORM": {
                "aliases": ["first normal form", "1nf"],
                "headings": ["first normal form", "1nf"],
            },
            "SECOND NORMAL FORM": {
                "aliases": ["second normal form", "2nf"],
                "headings": ["second normal form", "2nf"],
            },
            "THIRD NORMAL FORM": {
                "aliases": ["third normal form", "3nf"],
                "headings": ["third normal form", "3nf"],
            },
            "BOYCE CODD NORMAL FORM": {
                "aliases": [
                    "boyce codd normal form",
                    "boyce-codd normal form",
                    "bcnf",
                ],
                "headings": [
                    "boyce codd normal form",
                    "boyce-codd normal form",
                    "bcnf",
                ],
            },
            "FUNCTIONAL DEPENDENCIES": {
                "aliases": [
                    "functional dependency",
                    "functional dependencies",
                ],
                "headings": [
                    "functional dependency",
                    "functional dependencies",
                ],
            },
            "NORMAL FORMS OVERVIEW": {
                "aliases": [
                    "normal forms overview",
                    "normal forms",
                    "comparison at a glance",
                ],
                "headings": [
                    "normal forms overview",
                    "comparison at a glance",
                ],
            },
            "DECOMPOSITION": {
                "aliases": [
                    "decomposition",
                    "decompose",
                    "decomposes",
                    "decomposed",
                    "decomposing",
                ],
                "headings": ["decomposition"],
            },
            "ANOMALIES": {
                "aliases": [
                    "anomalies",
                    "insertion anomaly",
                    "update anomaly",
                    "deletion anomaly",
                ],
                "headings": [
                    "anomalies",
                    "insertion anomaly",
                    "update anomaly",
                    "deletion anomaly",
                ],
            },
            "KEYS": {
                "aliases": [
                    "candidate key",
                    "candidate keys",
                    "primary key",
                    "primary keys",
                    "composite key",
                    "composite keys",
                    "foreign key",
                    "foreign keys",
                    "superkey",
                    "superkeys",
                    "super key",
                    "super keys",
                ],
                "headings": [
                    "keys",
                    "candidate keys",
                    "primary keys",
                    "composite keys",
                    "foreign keys",
                ],
            },
        },
    },
    "sql_joins": {
        "subject": "DBMS",
        "concepts": {
            "INNER JOIN": {
                "aliases": ["inner join"],
                "headings": ["inner join"],
            },
            "LEFT JOIN": {
                "aliases": ["left join", "left outer join"],
                "headings": ["left join", "left outer join"],
            },
            "RIGHT JOIN": {
                "aliases": ["right join", "right outer join"],
                "headings": ["right join", "right outer join"],
            },
            "FULL OUTER JOIN": {
                "aliases": ["full outer join", "full join"],
                "headings": ["full outer join", "full join"],
            },
            "CROSS JOIN": {
                "aliases": ["cross join"],
                "headings": ["cross join"],
            },
            "SELF JOIN": {
                "aliases": ["self join"],
                "headings": ["self join"],
            },
            "JOIN CONDITIONS": {
                "aliases": ["join conditions", "join condition"],
                "headings": ["join conditions", "join condition"],
            },
        },
    },
    "python oop": {
        "subject": "Python",
        "concepts": {
            "CLASSES AND OBJECTS": {
                "aliases": [
                    "classes and objects",
                    "class and objects",
                    "class and object",
                ],
                "headings": [
                    "classes and objects",
                    "class and objects",
                    "class and object",
                ],
            },
            "CONSTRUCTOR AND SELF": {
                "aliases": ["constructor and self", "constructors", "__init__"],
                "headings": ["constructor and self", "constructors"],
            },
            "ENCAPSULATION": {
                "aliases": ["encapsulation"],
                "headings": ["encapsulation"],
            },
            "INHERITANCE": {
                "aliases": ["inheritance"],
                "headings": ["inheritance"],
            },
            "POLYMORPHISM": {
                "aliases": ["polymorphism"],
                "headings": ["polymorphism"],
            },
            "ABSTRACTION": {
                "aliases": ["abstraction"],
                "headings": ["abstraction"],
            },
            "CLASS VS INSTANCE VARIABLES": {
                "aliases": [
                    "class vs instance variables",
                    "class variables",
                    "instance variables",
                ],
                "headings": [
                    "class vs instance variables",
                    "class and instance variables",
                ],
            },
            "SPECIAL METHODS": {
                "aliases": [
                    "special methods",
                    "magic methods",
                    "dunder methods",
                ],
                "headings": [
                    "special methods",
                    "magic methods",
                    "dunder methods",
                ],
            },
            "COMPOSITION": {
                "aliases": ["composition"],
                "headings": ["composition"],
            },
        },
    },
    "sql basics": {
        "subject": "DBMS",
        "concepts": {
            "SELECT": {
                "aliases": ["select statement", "select and from", "select"],
                "headings": ["select", "select statement", "select and from"],
            },
            "WHERE": {
                "aliases": ["where clause", "where and operators", "where"],
                "headings": ["where", "where clause", "where and operators"],
            },
            "AGGREGATE FUNCTIONS": {
                "aliases": ["aggregate functions", "aggregate function"],
                "headings": ["aggregate functions", "aggregate function"],
            },
            "GROUP BY": {
                "aliases": ["group by"],
                "headings": ["group by", "group by and having"],
            },
            "HAVING": {
                "aliases": ["having clause", "having"],
                "headings": ["having", "group by and having"],
            },
            "ORDER BY": {
                "aliases": ["order by"],
                "headings": ["order by", "order by and limit"],
            },
            "LIMIT": {
                "aliases": ["limit clause", "limit"],
                "headings": ["limit", "order by and limit"],
            },
        },
    },
}


# ============================================================
# TEXT MATCHING
# ============================================================

def normalize_text(value):
    """Normalize text for case-insensitive phrase matching."""
    text = str(value or "").lower()
    text = text.replace("_", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_phrase(text, phrase):
    """Match a complete phrase, not a substring."""
    normalized_text = normalize_text(text)
    normalized_phrase = normalize_text(phrase)

    if not normalized_text or not normalized_phrase:
        return False

    pattern = (
        r"(?<![a-z0-9])"
        + re.escape(normalized_phrase)
        + r"(?![a-z0-9])"
    )
    return re.search(pattern, normalized_text) is not None


def get_resource_title(resource):
    """Extract a section title from supported metadata fields."""
    for field in ("section_title", "title", "heading", "section"):
        value = resource.get(field)
        if value:
            return str(value).strip()

    return "Untitled section"


def get_resource_content(resource):
    """Extract body text from supported metadata fields."""
    for field in ("content", "text", "page_content", "chunk"):
        value = resource.get(field)
        if value:
            return str(value)

    return ""


def match_heading(title, heading_aliases):
    """Return the first alias matched by a section heading."""
    for alias in heading_aliases:
        if contains_phrase(title, alias):
            return alias

    return None


def match_content(content, aliases):
    """
    Return all matching body-text excerpts.

    Each result contains the matching alias and a short excerpt.
    """
    if not content:
        return []

    content = str(content)
    segments = re.split(r"(?<=[.!?])\s+|\n+", content)
    matches = []
    seen = set()

    for alias in aliases:
        for segment in segments:
            segment = segment.strip()

            if segment and contains_phrase(segment, alias):
                key = (normalize_text(alias), normalize_text(segment))

                if key not in seen:
                    seen.add(key)
                    matches.append({
                        "alias": alias,
                        "excerpt": segment[:500],
                    })

    # Fallback for PDF text with unreliable sentence boundaries.
    if not matches:
        for alias in aliases:
            if contains_phrase(content, alias):
                matches.append({
                    "alias": alias,
                    "excerpt": content.strip()[:500],
                })
                break

    return matches


# ============================================================
# BODY EVIDENCE VALIDATION
# ============================================================

def has_strong_body_evidence(concept_name, evidence_text):
    """
    Apply conservative, concept-specific evidence checks.

    These are transparent keyword and pattern heuristics. They do not
    prove that a topic is comprehensively taught.
    """
    text = normalize_text(evidence_text)

    if concept_name == "DECOMPOSITION":
        has_decomposition_term = any(
            contains_phrase(text, term)
            for term in (
                "decomposition",
                "decompose",
                "decomposes",
                "decomposed",
                "decomposing",
                "normalized decomposition",
            )
        )

        has_explanation_context = any(
            contains_phrase(text, term)
            for term in (
                "relation",
                "table",
                "smaller relations",
                "lossless",
                "dependency preservation",
                "split",
                "student course enrollment",
            )
        )

        return has_decomposition_term and has_explanation_context

    if concept_name == "KEYS":
        definition_patterns = (
            r"\bcandidate key is\b",
            r"\bprimary key is\b",
            r"\bforeign key is\b",
            r"\bsuperkey is\b",
            r"\bminimal set of attributes\b",
            r"\buniquely identifies?\b",
            r"\bfunctionally determines every attribute\b",
            r"\bcandidate key\b.{0,100}\bminimal\b",
            r"\bsuperkey\b.{0,100}\bcandidate key\b",
        )

        return any(
            re.search(pattern, text)
            for pattern in definition_patterns
        )

    return False


# ============================================================
# RESOURCE NORMALIZATION
# ============================================================

def retrieve_resources(topic_name, subject_name):
    """Retrieve resources through the existing resource agent."""
    resources = retrieve_topic_resources(
        topic_name,
        subject_name,
        learning_status="weak",
    )

    if not resources:
        return []

    normalized_resources = []

    for resource in resources:
        if not isinstance(resource, dict):
            continue

        normalized_resources.append({
            "title": get_resource_title(resource),
            "content": get_resource_content(resource),
            "original": resource,
        })

    return normalized_resources


# ============================================================
# EVALUATE ONE TOPIC
# ============================================================

def evaluate_topic(topic_name, config):
    subject_name = config["subject"]
    concepts = config["concepts"]
    resources = retrieve_resources(topic_name, subject_name)

    results = []
    confirmed_count = 0
    provisional_count = 0
    missing_count = 0

    for concept_name, concept_config in concepts.items():
        heading_aliases = concept_config["headings"]
        body_aliases = concept_config["aliases"]

        heading_match = None
        matched_resource = None
        evidence_snippet = None
        matched_alias = None

        # Pass 1: headings provide the strongest evidence.
        for resource in resources:
            alias = match_heading(
                resource["title"],
                heading_aliases,
            )

            if alias:
                heading_match = alias
                matched_alias = alias
                matched_resource = resource
                break

        if heading_match:
            status = "CONFIRMED"
            evidence_type = "heading"
            confirmed_count += 1

        else:
            # Pass 2: collect evidence across all retrieved sections.
            body_evidence = []

            for resource in resources:
                for match in match_content(
                    resource["content"],
                    body_aliases,
                ):
                    body_evidence.append({
                        "alias": match["alias"],
                        "excerpt": match["excerpt"],
                        "section": resource["title"],
                    })

            if body_evidence:
                evidence_text = " ".join(
                    item["excerpt"] for item in body_evidence
                )

                evidence_snippet = " | ".join(
                    f"{item['section']}: {item['excerpt']}"
                    for item in body_evidence[:3]
                )[:1200]

                matched_alias = body_evidence[0]["alias"]

                matched_resource = next(
                    (
                        resource
                        for resource in resources
                        if resource["title"]
                        == body_evidence[0]["section"]
                    ),
                    None,
                )

                if has_strong_body_evidence(
                    concept_name,
                    evidence_text,
                ):
                    status = "BODY_CONFIRMED"
                    evidence_type = "body_text"
                    confirmed_count += 1
                else:
                    status = "NEEDS_REVIEW"
                    evidence_type = "body_text_only"
                    provisional_count += 1

            else:
                status = "MISSING"
                evidence_type = "none"
                matched_alias = None
                evidence_snippet = None
                missing_count += 1

        results.append({
            "concept": concept_name,
            "status": status,
            "evidence_type": evidence_type,
            "matched_alias": matched_alias,
            "matched_section": (
                matched_resource["title"]
                if matched_resource
                else None
            ),
            "evidence_snippet": (
                evidence_snippet if not heading_match else None
            ),
        })

    total = len(concepts)

    confirmed_coverage = (
        confirmed_count / total * 100 if total else 0.0
    )

    potential_coverage = (
        (confirmed_count + provisional_count) / total * 100
        if total
        else 0.0
    )

    return {
        "topic": topic_name,
        "subject": subject_name,
        "resources_retrieved": len(resources),
        "concepts_expected": total,
        "confirmed": confirmed_count,
        "needs_review": provisional_count,
        "missing": missing_count,
        "confirmed_coverage_percent": round(
            confirmed_coverage, 2
        ),
        "potential_coverage_percent": round(
            potential_coverage, 2
        ),
        "concept_results": results,
    }


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 72)
    print("CURRICULUM COVERAGE EVALUATION")
    print("=" * 72)
    print("CONFIRMED = matched by section heading")
    print("BODY_CONFIRMED = passed body-text evidence checks")
    print("NEEDS_REVIEW = body text matched, evidence insufficient")
    print("MISSING = no matching evidence found")
    print()

    topic_results = []
    total_expected = 0
    total_confirmed = 0
    total_review = 0
    total_missing = 0

    for topic_name, config in CURRICULUM.items():
        result = evaluate_topic(topic_name, config)
        topic_results.append(result)

        total_expected += result["concepts_expected"]
        total_confirmed += result["confirmed"]
        total_review += result["needs_review"]
        total_missing += result["missing"]

        print("-" * 72)
        print(f"TOPIC: {topic_name.upper()}")
        print("-" * 72)
        print(f"Resources retrieved: {result['resources_retrieved']}")
        print(
            f"Confirmed coverage: "
            f"{result['confirmed_coverage_percent']:.2f}%"
        )
        print(
            f"Potential coverage: "
            f"{result['potential_coverage_percent']:.2f}%"
        )
        print()

        status_labels = {
            "CONFIRMED": "[CONFIRMED]",
            "BODY_CONFIRMED": "[BODY CONFIRMED]",
            "NEEDS_REVIEW": "[REVIEW]",
            "MISSING": "[MISSING]",
        }

        for item in result["concept_results"]:
            label = status_labels[item["status"]]
            print(f"{label} {item['concept']}")

            if item["matched_section"]:
                print(f"    Section: {item['matched_section']}")

            if item["matched_alias"]:
                print(f"    Evidence: {item['matched_alias']}")

            if item.get("evidence_snippet"):
                print(
                    f"    Evidence excerpt: "
                    f"{item['evidence_snippet']}"
                )

        print()

    overall_confirmed_coverage = (
        total_confirmed / total_expected * 100
        if total_expected
        else 0.0
    )

    overall_potential_coverage = (
        (total_confirmed + total_review) / total_expected * 100
        if total_expected
        else 0.0
    )

    report = {
        "evaluation_type": (
            "Heading and evidence-based body-text coverage"
        ),
        "overall": {
            "concepts_expected": total_expected,
            "confirmed": total_confirmed,
            "needs_review": total_review,
            "missing": total_missing,
            "confirmed_coverage_percent": round(
                overall_confirmed_coverage, 2
            ),
            "potential_coverage_percent": round(
                overall_potential_coverage, 2
            ),
        },
        "topics": topic_results,
    }

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(REPORT_PATH, "w", encoding="utf-8") as file:
        json.dump(
            report,
            file,
            indent=4,
            ensure_ascii=False,
        )

    print("=" * 72)
    print("OVERALL RESULTS")
    print("=" * 72)
    print(f"Expected concepts: {total_expected}")
    print(f"Confirmed: {total_confirmed}")
    print(f"Needs review: {total_review}")
    print(f"Missing: {total_missing}")
    print(
        f"Confirmed coverage: "
        f"{overall_confirmed_coverage:.2f}%"
    )
    print(
        f"Potential coverage: "
        f"{overall_potential_coverage:.2f}%"
    )
    print()
    print(f"Report saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
