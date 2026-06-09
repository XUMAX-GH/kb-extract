"""Adapter package. H2 static scan runs over every .py file here."""

from .base import register
from .docx import DocxAdapter
from .image import ImageAdapter
from .pdf_docling import PdfDoclingAdapter
from .pptx import PptxAdapter
from .xlsx import XlsxAdapter
from .zip import ZipAdapter

# Auto-register all real adapters on import.
for _cls in (DocxAdapter, ImageAdapter, PdfDoclingAdapter, PptxAdapter, XlsxAdapter):
    register(_cls)

# ZipAdapter requires registry handle; orchestrator wires it explicitly when used.
__all__ = [
    "DocxAdapter", "ImageAdapter", "PdfDoclingAdapter",
    "PptxAdapter", "XlsxAdapter", "ZipAdapter",
]

