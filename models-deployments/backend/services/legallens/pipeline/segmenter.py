import logging
import spacy

logger = logging.getLogger(__name__)

class LegalLensSegmenter:
    def __init__(self):
        try:
            self.nlp = spacy.load(
                "en_core_web_sm",
                exclude=["ner", "lemmatizer", "attribute_ruler", "tagger"],
            )
        except OSError:
            logger.warning("en_core_web_sm not found. Please run: python -m spacy download en_core_web_sm")
            self.nlp = spacy.blank("en")
            self.nlp.add_pipe("sentencizer")

    def segment(self, pages_data: list[dict], min_chunk=150, min_leftover=30) -> list[dict]:
        """
        Splits text into clause chunks using spaCy sentence boundaries.
        Input: list of {"page_no": int, "text": str}
        Output: list of {"text": str, "start_char": int, "end_char": int, "page_no": int}
        """
        if not pages_data:
            return []

        # Build one real document + a page-boundary lookup, so offsets are truthful
        # and sentences aren't artificially cut at page breaks.
        sep = "\n"
        full_text_parts = []
        page_offsets = []  # (start_offset, end_offset, page_no)
        offset = 0
        for page in pages_data:
            text = page["text"]
            page_offsets.append((offset, offset + len(text), page["page_no"]))
            full_text_parts.append(text)
            offset += len(text) + len(sep)

        full_text = sep.join(full_text_parts)

        def page_for_offset(pos):
            for start, end, page_no in page_offsets:
                if start <= pos < end or pos == end:
                    return page_no
            return page_offsets[-1][2]

        clauses = []
        current_chunk, current_start = [], None

        doc = self.nlp(full_text)
        for sent in doc.sents:
            sent_text = sent.text.strip()
            if not sent_text:
                continue
            if current_start is None:
                current_start = sent.start_char
            current_chunk.append(sent_text)

            chunk_text = " ".join(current_chunk)
            if len(chunk_text) >= min_chunk:
                clauses.append({
                    "text": chunk_text,
                    "start_char": current_start,
                    "end_char": sent.end_char,
                    "page_no": page_for_offset(current_start),
                })
                current_chunk, current_start = [], None

        if current_chunk:
            chunk_text = " ".join(current_chunk)
            clauses.append({
                "text": chunk_text,
                "start_char": current_start,
                "end_char": len(full_text),
                "page_no": page_for_offset(current_start),
                **({"short": True} if len(chunk_text) < min_leftover else {}),
            })

        logger.info(f"Segmented {len(pages_data)} pages into {len(clauses)} clauses.")
        return clauses
