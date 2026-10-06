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


def load_certificates_from_file(path):
    """Reads one or more X.509 certificates (PEM bundle or single DER file); raises ValueError if none are found."""
    with open(path, 'rb') as f:
        data = f.read()
    if pem.detect(data):
        certs = [asn1_x509.Certificate.load(der) for _, _, der in pem.unarmor(data, multiple=True)]
    else:
        certs = [asn1_x509.Certificate.load(data)]
    if not certs:
        raise ValueError(f"No certificate found in {path}")
    return certs


def build_trust_roots(extra_paths=()):
    """System trust roots plus user-configured certificates; unreadable extra files are skipped."""
    roots = list(load_system_trust_roots())
    for path in extra_paths:
        try:
            roots.extend(load_certificates_from_file(path))
        except (OSError, ValueError):
            continue
    return roots


def analyze_signatures(file_path, trust_roots=None, cancelled=None, allow_online=False):
    """Validates every embedded signature of a PDF and returns a list of SignatureDetails.

    By default nothing is fetched from the network, because revocation/AIA URLs come from the untrusted PDF.
    Pass allow_online=True only after the user opted in to online revocation checks.
    `cancelled` is an optional callable checked between signatures.
    """
    roots = load_system_trust_roots() if trust_roots is None else trust_roots
    signatures = []
    with open(file_path, 'rb') as f:
        reader = PdfFileReader(f, strict=False)
        validation_context = ValidationContext(trust_roots=roots, allow_fetching=allow_online)
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
            signatures.append(SignatureDetails(sig, status, page_num, rect, online_checks=allow_online))
    return signatures
