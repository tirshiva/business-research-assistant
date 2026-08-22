"""Document parser — split public reports into page-level text."""

from __future__ import annotations

import re

from app.rag.models import ParsedPage, SourceDocument

_PAGE_MARKER = re.compile(
    r"(?:\[Page\s+(\d+)\]|---\s*page\s+(\d+)\s*---|^\f)",
    re.IGNORECASE | re.MULTILINE,
)


def parse_document(document: SourceDocument) -> list[ParsedPage]:
    """Parse plain text (and simple page markers) into ordered pages.

    Supported markers: ``[Page N]``, ``--- page N ---``, and form-feed.
    PDFs and other binaries are out of scope for this MVP parser.
    """
    text = document.text.replace("\r\n", "\n").strip()
    if not text:
        return []

    matches = list(_PAGE_MARKER.finditer(text))
    if not matches:
        return [ParsedPage(page_number=1, text=text)]

    pages: list[ParsedPage] = []
    first_start = matches[0].start()
    preamble = text[:first_start].strip()
    if preamble:
        pages.append(ParsedPage(page_number=1, text=preamble))

    for index, match in enumerate(matches):
        explicit = match.group(1) or match.group(2)
        if explicit:
            page_number = int(explicit)
        elif pages:
            page_number = pages[-1].page_number + 1
        else:
            page_number = 1
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end].strip()
        if not body:
            continue
        pages.append(ParsedPage(page_number=page_number, text=body))
    return pages or [ParsedPage(page_number=1, text=text)]
