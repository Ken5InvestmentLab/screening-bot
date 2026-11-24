"""OFFLINE PROPOSAL: complete-text comparison of HTTP discovery and secure original.

This is NOT byte identity, not general PDF document identity, and generates no
publication metadata. Image differences require a separately reviewed exact pair.
"""
import hashlib
import json
import sys
import unicodedata
from pathlib import Path
from pypdf import PdfReader, _cmap
from pypdf.generic import DictionaryObject, ArrayObject, IndirectObject

_cmap._predefined_cmap['/UniJIS-UTF16-H'] = 'utf-16-be'
_cmap._predefined_cmap['/UniJIS-UTF16-V'] = 'utf-16-be'
METHOD = 'layout-reencoded-complete-page-text-v1'
FORBIDDEN = {'/OpenAction', '/AA', '/JS', '/JavaScript', '/EmbeddedFiles',
             '/AF', '/AcroForm', '/XFA', '/EF', '/RichMediaContent'}
ACTION_TYPES = {'/JavaScript', '/Launch', '/GoToR', '/GoToE', '/URI',
                '/SubmitForm', '/ImportData', '/Rendition', '/Movie', '/Sound'}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text)
                   if not c.isspace())

def inspect_active(root):
    seen = set()
    def visit(obj):
        if isinstance(obj, IndirectObject):
            key = (id(obj.pdf), obj.idnum, obj.generation)
            if key in seen:
                return
            seen.add(key)
            obj = obj.get_object()
        elif isinstance(obj, (DictionaryObject, ArrayObject)):
            key = id(obj)
            if key in seen:
                return
            seen.add(key)
        if isinstance(obj, DictionaryObject):
            for key in FORBIDDEN:
                if key in obj:
                    raise ValueError('interactive/embedded PDF content: ' + key)
            if str(obj.get('/S', '')) in ACTION_TYPES:
                raise ValueError('PDF action present')
            if '/Annots' in obj and len(obj['/Annots']):
                raise ValueError('PDF annotations require separate review')
            for value in obj.values():
                visit(value)
        elif isinstance(obj, ArrayObject):
            for value in obj:
                visit(value)
    visit(root)

def inspect_pdf(file, min_page_chars=80):
    raw = Path(file).read_bytes()
    if not raw.startswith(b'%PDF-'):
        raise ValueError('not a PDF')
    reader = PdfReader(file, strict=True)
    if reader.is_encrypted:
        raise ValueError('encrypted PDF not supported')
    inspect_active(reader.trailer['/Root'])
    if not reader.pages:
        raise ValueError('empty PDF')
    pages = []
    texts = []
    for number, page in enumerate(reader.pages, 1):
        text = normalized(page.extract_text() or '')
        if len(text) < min_page_chars:
            raise ValueError('insufficient complete page text: page ' + str(number))
        if '\ufffd' in text or '\x00' in text:
            raise ValueError('undecodable page text')
        images = []
        for image in page.images:
            pixels = image.image.convert('RGBA')
            images.append({'width': pixels.width, 'height': pixels.height,
                           'rgbaSha256': digest(pixels.tobytes())})
        images.sort(key=lambda x: (x['width'], x['height'], x['rgbaSha256']))
        texts.append(text)
        pages.append({'page': number, 'normalizedCharacters': len(text),
                      'completeTextSha256': digest(text.encode('utf-8')),
                      'images': images,
                      'mediaBox': [float(x) for x in page.mediabox],
                      'cropBox': [float(x) for x in page.cropbox],
                      'rotation': int(page.get('/Rotate', 0))})
    return {'rawSha256': digest(raw), 'bytes': len(raw), 'pages': pages}, texts

def compare(issuer_file, secure_file):
    issuer, left = inspect_pdf(issuer_file)
    secure, right = inspect_pdf(secure_file)
    equal = len(left) == len(right) and all(a == b for a, b in zip(left, right))
    image_equal = len(left) == len(right) and all(
        a['images'] == b['images'] for a, b in zip(issuer['pages'], secure['pages']))
    return {'method': METHOD, 'completePageTextEqual': equal,
            'pageCountEqual': len(left) == len(right),
            'imageContentEqual': image_equal,
            'requiresReviewedImageLayoutPair': equal and not image_equal,
            'notRawByteIdentity': issuer['rawSha256'] != secure['rawSha256'],
            'fullTextSha256': digest(''.join(left).encode('utf-8')),
            'normalizedCharacters': sum(map(len, left)),
            'publicationInferred': False, 'issuer': issuer, 'secure': secure}

if __name__ == '__main__':
    try:
        result = compare(sys.argv[1], sys.argv[2])
    except Exception as error:
        result = {'method': METHOD, 'completePageTextEqual': False,
                  'publicationInferred': False, 'error': str(error)}
    print(json.dumps(result, ensure_ascii=True, separators=(',', ':')))
