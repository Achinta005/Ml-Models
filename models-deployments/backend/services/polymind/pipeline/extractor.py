# extractor.py
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_OCR_CHAR_THRESHOLD = 20
_OCR_DPI = 300


@dataclass
class Page:
    page_number: int
    text: str
    source: str
    ocr_applied: bool = field(default=False)


def extract(file_path: str) -> list[Page]:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = path.suffix.lower()

    extractors = {
        ".pdf":  _extract_pdf,
        ".txt":  _extract_txt,
        ".docx": _extract_docx,
    }

    if ext not in extractors:
        raise ValueError(
            f"Unsupported file type '{ext}'. Supported types: {', '.join(extractors)}"
        )

    logger.info(f"Extracting text from {path.name} (type={ext})")

    try:
        pages = extractors[ext](path)
        ocr_count = sum(1 for p in pages if p.ocr_applied)
        logger.info(
            f"Extracted {len(pages)} page(s) from {path.name}"
            + (f" ({ocr_count} via OCR)" if ocr_count else "")
        )
        return pages
    except (FileNotFoundError, ValueError):
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from '{file_path}': {e}") from e


def _extract_pdf(path: Path) -> list[Page]:
    try:
        import fitz
    except ImportError as e:
        raise ImportError(
            "PyMuPDF is required for PDF extraction. "
            "Install it with: pip install pymupdf"
        ) from e

    pages: list[Page] = []

    with fitz.open(str(path)) as doc:
        for i in range(doc.page_count):
            fitz_page = doc[i]
            text = fitz_page.get_text("text").strip()  # type: ignore[attr-defined]

            if len(text) >= _OCR_CHAR_THRESHOLD:
                pages.append(Page(page_number=i + 1, text=text, source=str(path)))
            else:
                logger.debug(
                    f"{path.name} p{i + 1}: only {len(text)} chars via PyMuPDF — "
                    "falling back to OCR"
                )
                ocr_text = _ocr_fitz_page(fitz_page)
                pages.append(
                    Page(page_number=i + 1, text=ocr_text, source=str(path), ocr_applied=True)
                )

    return pages


def _ocr_fitz_page(fitz_page) -> str:
    try:
        import pytesseract
        from PIL import Image
        import io
    except ImportError as e:
        raise ImportError(
            "pytesseract and Pillow are required for OCR fallback. "
            "Install them with: pip install pytesseract Pillow"
        ) from e

    # fitz_page is always a raw fitz.Page from doc[i]
    matrix = fitz_page.get_pixmap(dpi=_OCR_DPI)  # type: ignore[attr-defined]
    img = Image.open(io.BytesIO(matrix.tobytes("png")))
    text = pytesseract.image_to_string(img, lang="eng")
    return text.strip()


def _extract_txt(path: Path) -> list[Page]:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            text = path.read_text(encoding=encoding)
            return [Page(page_number=1, text=text.strip(), source=str(path))]
        except UnicodeDecodeError:
            continue

    raise RuntimeError(f"Could not decode '{path}' with supported encodings.")


def _extract_docx(path: Path) -> list[Page]:
    try:
        from docx import Document
        from docx.oxml.ns import qn
    except ImportError as e:
        raise ImportError(
            "python-docx is required for DOCX extraction. "
            "Install it with: pip install python-docx"
        ) from e

    doc = Document(str(path))

    current_lines: list[str] = []
    pages: list[Page] = []
    page_num = 1

    for para in doc.paragraphs:
        # Correct page break detection via XML inspection
        has_page_break = any(
            br.get(qn("w:type")) == "page"
            for run in para.runs
            for br in run._element.findall(qn("w:br"))
        )

        if has_page_break and current_lines:
            pages.append(Page(
                page_number=page_num,
                text="\n".join(current_lines).strip(),
                source=str(path),
            ))
            page_num += 1
            current_lines = []

        if para.text.strip():
            current_lines.append(para.text)

    if current_lines:
        pages.append(Page(
            page_number=page_num,
            text="\n".join(current_lines).strip(),
            source=str(path),
        ))

    if not pages:
        pages.append(Page(page_number=1, text="", source=str(path)))

    return pages