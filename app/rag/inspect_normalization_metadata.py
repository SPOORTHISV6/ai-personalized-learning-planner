
import json
import re
from pathlib import Path


METADATA_PATH = Path(
    "data/vector_store/normalization/metadata.json"
)

CONCEPT_KEYWORDS = {
    "NORMAL FORMS": [
        "normal forms",
        "normalization",
        "normalisation",
        "1nf",
        "2nf",
        "3nf",
        "bcnf",
    ],
    "DECOMPOSITION": [
        "decomposition",
        "decompose",
        "lossless",
        "dependency preservation",
    ],
    "KEYS": [
        "keys",
        "candidate key",
        "primary key",
        "superkey",
        "super key",
        "foreign key",
        "composite key",
    ],
}


def get_content(item):
    return str(
        item.get("content")
        or item.get("text")
        or ""
    )


def get_title(item, index):
    return str(
        item.get("section_title")
        or item.get("title")
        or item.get("heading")
        or f"Untitled section {index}"
    )


def main():
    if not METADATA_PATH.exists():
        print(f"Metadata file not found: {METADATA_PATH}")
        return

    with METADATA_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        metadata = json.load(file)

    if not isinstance(metadata, list):
        print("ERROR: Metadata must contain a JSON list.")
        return

    print("=" * 75)
    print("NORMALIZATION METADATA INSPECTION")
    print("=" * 75)
    print(f"Metadata file: {METADATA_PATH}")
    print(f"Total chunks: {len(metadata)}")

    for index, item in enumerate(metadata, start=1):
        title = get_title(item, index)
        content = get_content(item)
        searchable_text = f"{title}\n{content}".lower()

        print("\n" + "-" * 75)
        print(f"CHUNK {index}: {title}")
        print(f"Content length: {len(content)} characters")

        if not content.strip():
            print("WARNING: Empty content.")

        for concept, keywords in CONCEPT_KEYWORDS.items():
            matched = [
                keyword
                for keyword in keywords
                if re.search(
                    r"(?<!\w)"
                    + re.escape(keyword.lower())
                    + r"(?!\w)",
                    searchable_text,
                )
            ]

            if matched:
                print(
                    f"[MATCH] {concept}: "
                    + ", ".join(matched)
                )

        preview = re.sub(r"\s+", " ", content).strip()

        if preview:
            print("Preview:")
            print(preview[:450])
        else:
            print("Preview: No content available.")

    print("\n" + "=" * 75)
    print("INSPECTION COMPLETE")
    print("=" * 75)


if __name__ == "__main__":
    main()
