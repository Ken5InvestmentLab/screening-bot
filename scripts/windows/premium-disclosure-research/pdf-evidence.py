import json, sys
from pathlib import Path
import pypdf
from pypdf import PdfReader, _cmap
from pypdf._font import Font
from pypdf.generic import IndirectObject


def text_width_with_resolved_references(font, text=""):
    # A CID font can store glyph widths as indirect PDF objects. Resolve them
    # to their real values before pypdf uses the widths to separate words.
    widths = font.character_widths
    total = 0.0
    for character in text:
        width = widths.get(character, widths["default"])
        if isinstance(width, IndirectObject):
            width = width.get_object()
        total += width
    return total


Font.text_width = text_width_with_resolved_references
_cmap._predefined_cmap['/UniJIS-UTF16-H']='utf-16-be'
_cmap._predefined_cmap['/UniJIS-UTF16-V']='utf-16-be'
reader=PdfReader(Path(sys.argv[1]))
text='\n'.join(f'--- page {i+1} ---\n{page.extract_text() or ""}' for i,page in enumerate(reader.pages))
meta=reader.metadata or {}
print(json.dumps({'pages':len(reader.pages),'text':text,'pypdfVersion':pypdf.__version__,'auxiliaryPdfMetadata':{'creationDateRaw':meta.get('/CreationDate'),'modificationDateRaw':meta.get('/ModDate'),'role':'supplementary only; never publication time'}},ensure_ascii=False))
