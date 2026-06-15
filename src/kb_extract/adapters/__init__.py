"""Adapter package. H2 static scan runs over every .py file here.

v0.8.0: the four MinerU-inspired v2 adapters (docx_v2, pptx_v2,
xlsx_v2, pdf_v2) are now the defaults for their respective file
extensions. The legacy adapter classes remain importable for explicit
use (e.g. parity tests, downstream code that pinned a specific
adapter), but are no longer auto-registered.
"""

from .base import register
from .docx import DocxAdapter
from .docx_v2 import DocxV2Adapter
from .image import ImageAdapter
from .pdf_docling import PdfDoclingAdapter
from .pdf_v2 import PdfV2Adapter
from .pptx import PptxAdapter
from .pptx_v2 import PptxV2Adapter
from .xlsx import XlsxAdapter
from .xlsx_v2 import XlsxV2Adapter
from .zip import ZipAdapter

# v2 adapters supersede v1 for their extensions.
for _cls in (DocxV2Adapter, PptxV2Adapter, XlsxV2Adapter, PdfV2Adapter, ImageAdapter):
    register(_cls)

# ZipAdapter requires registry handle; orchestrator wires it explicitly when used.
__all__ = [
    "DocxAdapter", "DocxV2Adapter",
    "ImageAdapter",
    "PdfDoclingAdapter", "PdfV2Adapter",
    "PptxAdapter", "PptxV2Adapter",
    "XlsxAdapter", "XlsxV2Adapter",
    "ZipAdapter",
]

