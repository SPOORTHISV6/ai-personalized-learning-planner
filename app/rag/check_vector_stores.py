
import json
from pathlib import Path

import faiss


ROOT = Path("data/vector_store")


def check_store(index_path, metadata_path):
    print(f"\nIndex:    {index_path}")
    print(f"Metadata: {metadata_path}")

    if not index_path.exists() or not metadata_path.exists():
        print("STATUS: MISSING FILE")
        return

    try:
        index = faiss.read_index(str(index_path))

        with metadata_path.open("r", encoding="utf-8") as file:
            metadata = json.load(file)

        if not isinstance(metadata, list):
            print("STATUS: INVALID METADATA FORMAT")
            return

        vector_count = index.ntotal
        metadata_count = len(metadata)

        print(f"Vectors:  {vector_count}")
        print(f"Metadata: {metadata_count}")
        print(f"Dimension: {index.d}")

        if vector_count == metadata_count:
            print("STATUS: MATCH")
        else:
            print("STATUS: MISMATCH")

        if metadata:
            print("First metadata keys:", list(metadata[0].keys()))

    except Exception as exc:
        print(f"STATUS: ERROR: {exc}")


def main():
    print("=" * 65)
    print("VECTOR STORE DIAGNOSTICS")
    print("=" * 65)

    for folder in sorted(ROOT.iterdir()):
        if not folder.is_dir():
            continue

        index_path = folder / "index.faiss"
        metadata_path = folder / "metadata.json"

        if index_path.exists() or metadata_path.exists():
            check_store(index_path, metadata_path)

        # Check backups without modifying them.
        backup_index = folder / "index.previous.faiss"
        backup_metadata = folder / "metadata.previous.json"

        if backup_index.exists() or backup_metadata.exists():
            check_store(backup_index, backup_metadata)

    # Legacy index pairs.
    check_store(
        ROOT / "dbms.index",
        ROOT / "dbms_metadata.json",
    )


if __name__ == "__main__":
    main()
