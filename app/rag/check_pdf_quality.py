
from pathlib import Path
import re
import fitz

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCUMENT_DIR = PROJECT_ROOT / "data" / "documents"
OUTPUT_DIR = PROJECT_ROOT / "data" / "extraction_reports"

PDF_FILES = [
    "normalization.pdf",
    "sql_joins.pdf",
    "python_oop.pdf",
    "sql_basics.pdf",
]

SUSPICIOUS_PATTERNS = [
    re.compile(r"\b[A-Za-z]\s+[A-Za-z]\s+[A-Za-z]\b"),
    re.compile(r"[^\x00-\x7F]{2,}"),
    re.compile(r"\bG\s+G\b", re.IGNORECASE),
    re.compile(r"\s{2,}"),
]

def inspect_pdf(pdf_path):
    print(f"\n{'=' * 65}")
    print(f"Inspecting: {pdf_path.name}")
    print("=" * 65)

    report_lines = []
    total_chars = 0
    suspicious_lines = 0

    try:
        with fitz.open(pdf_path) as document:
            print(f"Total pages: {len(document)}")

            for page_number, page in enumerate(document, start=1):
                text = page.get_text("text")
                total_chars += len(text)

                for line_number, raw_line in enumerate(
                    text.splitlines(), start=1
                ):
                    line = raw_line.strip()

                    if not line:
                        continue

                    reasons = []

                    if len(line) > 15 and len(line.split()) <= 2:
                        if re.search(r"[A-Za-z]", line):
                            reasons.append("Possible fragmented text")

                    if re.search(r"[^\x00-\x7F]", line):
                        reasons.append("Non-ASCII characters")

                    if re.search(r"\bG\b", line):
                        reasons.append("Possible stray G marker")

                    if re.search(
                        r"\b(?:SELECT|FROM|WHERE|JOIN)\b",
                        line,
                        re.IGNORECASE,
                    ) and len(line.split()) < 3:
                        reasons.append("Possibly incomplete SQL")

                    if reasons:
                        suspicious_lines += 1
                        report_lines.append(
                            f"Page {page_number}, "
                            f"line {line_number}: {line}\n"
                            f"  Possible issues: {', '.join(reasons)}"
                        )

            print(f"Extracted characters: {total_chars}")
            print(f"Potentially suspicious lines: {suspicious_lines}")

    except Exception as exc:
        print(f"ERROR reading PDF: {exc}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / f"{pdf_path.stem}_report.txt"

    with open(report_path, "w", encoding="utf-8") as file:
        file.write(f"PDF: {pdf_path.name}\n")
        file.write(f"Extracted characters: {total_chars}\n")
        file.write(
            f"Potentially suspicious lines: {suspicious_lines}\n\n"
        )

        file.write("\n".join(report_lines))

    print(f"Report saved: {report_path}")


def main():
    if not DOCUMENT_DIR.exists():
        print(f"Document directory not found: {DOCUMENT_DIR}")
        return

    for filename in PDF_FILES:
        pdf_path = DOCUMENT_DIR / filename

        if not pdf_path.exists():
            print(f"\nMISSING PDF: {pdf_path}")
            continue

        inspect_pdf(pdf_path)

    print("\nPDF quality inspection completed.")


if __name__ == "__main__":
    main()
