import logging
import pdfplumber
import pytesseract
from PIL import Image
import io
import urllib.request
from urllib.parse import urlparse
import socket
import cloudinary
import cloudinary.utils
from pathlib import Path
from core.config import settings

logger = logging.getLogger(__name__)

def is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        
        hostname = parsed.hostname
        if not hostname:
            return False
        
        # Check against local / private IPs
        ip = socket.gethostbyname(hostname)
        ip_parts = list(map(int, ip.split('.')))
        
        # Loopback
        if ip.startswith("127."):
            return False
        # Private IP ranges (RFC 1918)
        if ip_parts[0] == 10:
            return False
        if ip_parts[0] == 172 and 16 <= ip_parts[1] <= 31:
            return False
        if ip_parts[0] == 192 and ip_parts[1] == 168:
            return False
        # Link-local (e.g. AWS/Azure metadata service 169.254.169.254)
        if ip_parts[0] == 169 and ip_parts[1] == 254:
            return False
        
        return True
    except Exception:
        return False

class LegalLensExtractor:
    def __init__(self):
        if settings.CLOUDINARY_CLOUD_NAME:
            cloudinary.config(
                cloud_name=settings.CLOUDINARY_CLOUD_NAME,
                api_key=settings.CLOUDINARY_API_KEY,
                api_secret=settings.CLOUDINARY_API_SECRET,
                secure=True
            )
            self.configured = True
        else:
            self.configured = False
        
    def download_from_cloud(self, file_key: str, local_path: Path):
        """Downloads a contract from Cloudinary (or a direct URL) to a local path."""
        if file_key.startswith("http"):
            logger.info(f"Downloading from URL: {file_key}")
            if not is_safe_url(file_key):
                raise ValueError("SSRF Alert: Forbidden URL host")
            urllib.request.urlretrieve(file_key, str(local_path))
            return

        if not self.configured:
            logger.warning("Cloudinary not configured. Attempting to use local file if it exists.")
            return
            
        logger.info(f"Downloading {file_key} from Cloudinary...")
        
        # Generate the Cloudinary URL. PDFs might be uploaded as 'image' or 'raw'
        url, _ = cloudinary.utils.cloudinary_url(file_key) 
        
        try:
            urllib.request.urlretrieve(url, str(local_path))
        except Exception as e:
            # Fallback to raw resource type in case it fails as image
            logger.info(f"Failed to download as image, trying raw: {e}")
            url, _ = cloudinary.utils.cloudinary_url(file_key, resource_type="raw")
            urllib.request.urlretrieve(url, str(local_path))

    def extract_text(self, file_path: str) -> list[dict]:
        """
        Extracts text from PDF using pdfplumber.
        Falls back to OCR if text is < 100 chars.
        Returns a list of dicts: {"page_no": int, "text": str, "source": str, "ocr_confidence": float, "error": str}
        """
        pages_data = []

        try:
            pdf = pdfplumber.open(file_path)
        except Exception as e:
            logger.error(f"Could not open {file_path}: {e}")
            raise RuntimeError(f"Extraction failed to open file: {e}") from e

        with pdf:
            for i, page in enumerate(pdf.pages):
                page_no = i + 1
                entry = {"page_no": page_no, "text": "", "source": "native", "ocr_confidence": None}

                try:
                    text = page.extract_text() or ""
                    stripped = text.strip()

                    if len(stripped) < 100:
                        logger.info(f"Page {page_no}: sparse text, falling back to OCR.")
                        try:
                            pil_img = page.to_image(resolution=300).original
                            data = pytesseract.image_to_data(
                                pil_img, lang="eng", output_type=pytesseract.Output.DICT
                            )
                            ocr_text = " ".join(w for w in data["text"] if w.strip())
                            confs = [int(c) for c in data["conf"] if c not in ("-1", "")]
                            entry["ocr_confidence"] = sum(confs) / len(confs) if confs else 0
                            entry["source"] = "ocr"
                            stripped = ocr_text.strip()
                        except Exception as ocr_err:
                            logger.warning(f"OCR failed on Page {page_no} (using sparse native text as fallback): {ocr_err}")
                            entry["ocr_confidence"] = 0
                            entry["source"] = "native_fallback"

                    entry["text"] = stripped

                except Exception as e:
                    logger.error(f"Page {page_no} failed: {e}")
                    entry["error"] = str(e)

                pages_data.append(entry)  # always append — no silent gaps
                page.close()

        if not any(p["text"] for p in pages_data):
            raise ValueError(f"EXTRACTION_FAILED: 0/{len(pages_data)} pages yielded text")

        return pages_data
