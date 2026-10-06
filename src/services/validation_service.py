"""Signature discovery and validation. Free of GTK so it can run in a worker thread and be unit tested."""
from functools import lru_cache

from asn1crypto import pem, x509 as asn1_x509
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext

from models import SignatureDetails

SYSTEM_CA_BUNDLES = ("/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt")


@lru_cache(maxsize=1)
def load_system_trust_roots():
    """Loads the system CA bundle (falling back to certifi) as trust roots for signature validation."""
    paths = list(SYSTEM_CA_BUNDLES)
    try:
        import certifi
        paths.append(certifi.where())
    except ImportError:
        pass
    for path in paths:
        try:
            with open(path, 'rb') as f:
                return tuple(asn1_x509.Certificate.load(der) for _, _, der in pem.unarmor(f.read(), multiple=True))
        except (OSError, ValueError):
            continue
    return ()


def flatten_page_tree(node, reference=None):
    """Returns the references of the leaf pages of a (possibly nested) PDF page tree, in document order."""
    kids = node.get('/Kids')
    if kids is None:
        return [reference]
    pages = []
    for i in range(len(kids)):
        pages.extend(flatten_page_tree(kids[i], getattr(kids.raw_get(i), 'reference', None)))
    return pages


def analyze_signatures(file_path, trust_roots=None, cancelled=None):
    """Validates every embedded signature of a PDF and returns a list of SignatureDetails.

    Never fetches revocation/AIA data: those URLs come from the untrusted PDF.
    `cancelled` is an optional callable checked between signatures.
    """
    roots = load_system_trust_roots() if trust_roots is None else trust_roots
    signatures = []
    with open(file_path, 'rb') as f:
        reader = PdfFileReader(f, strict=False)
        validation_context = ValidationContext(trust_roots=roots, allow_fetching=False)
        pages = flatten_page_tree(reader.root['/Pages'])
        for sig in reader.embedded_signatures:
            if cancelled and cancelled():
                break
            status = validate_pdf_signature(sig, validation_context)
            try:
                page_ref = sig.sig_field.raw_get('/P').reference
                page_num = pages.index(page_ref)
                rect = [float(v) for v in sig.sig_field.get('/Rect', [])]
            except (ValueError, KeyError, IndexError, AttributeError):
                page_num, rect = -1, None
            signatures.append(SignatureDetails(sig, status, page_num, rect))
    return signatures
