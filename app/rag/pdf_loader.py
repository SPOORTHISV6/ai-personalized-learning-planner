import fitz


def load_pdf(pdf_path: str):
    """
    Extract text from every page of a PDF.

    Returns:
        List of dictionaries containing page number and page text.
    """

    document = fitz.open(pdf_path)

    pages = []

    try:
        for page_number, page in enumerate(document):
            text = page.get_text("text")

            if text.strip():
                pages.append({
                    "page_number": page_number + 1,
                    "text": text.strip()
                })

    finally:
        document.close()

    return pages