"""Standard-library file text extraction for the POC.

Supported now: TXT/MD (UTF-8), DOCX (word/document.xml), PPTX (ordered
slide XML inside the zip). PDF, XLSX, Visio and images return explicit
warnings — a production extractor integration is pending; we do not
pretend content was parsed."""

import io
import re
import xml.etree.ElementTree as ET
import zipfile

_NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_NS_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def extract_text(filename: str, data: bytes) -> tuple[str, list[str]]:
    """Return (text, warnings). Empty text with warnings = not extracted."""
    name = (filename or "").lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext in ("txt", "md"):
        return data.decode("utf-8", errors="replace"), []
    if ext == "docx":
        return _docx(data)
    if ext == "pptx":
        return _pptx(data)
    if ext in ("pdf", "xlsx", "vsdx", "vsd", "png", "jpg", "jpeg", "gif",
               "svg"):
        return "", [f"{ext.upper()} text extraction is pending a "
                    "production parser; metadata was registered but the "
                    "file body was not indexed."]
    return "", [f"Unsupported file type '.{ext}'; registered metadata "
                "only."]


def _docx(data: bytes) -> tuple[str, list[str]]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError):
        return "", ["DOCX container could not be read."]
    root = ET.fromstring(xml)
    paras = []
    for p in root.iter(_NS_W + "p"):
        text = "".join(t.text or "" for t in p.iter(_NS_W + "t"))
        if text.strip():
            paras.append(text.strip())
    return "\n".join(paras), []


def _pptx(data: bytes) -> tuple[str, list[str]]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            slide_names = sorted(
                (n for n in z.namelist()
                 if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                key=lambda n: int(re.search(r"(\d+)", n).group(1)))
            texts = []
            for n in slide_names:
                root = ET.fromstring(z.read(n))
                t = " ".join(e.text or "" for e in root.iter(_NS_A + "t"))
                if t.strip():
                    texts.append(t.strip())
    except (zipfile.BadZipFile, ET.ParseError):
        return "", ["PPTX container could not be read."]
    return "\n".join(texts), []
