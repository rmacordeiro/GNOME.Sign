"""PDF signing logic without any GTK dependency, so it can be tested headlessly."""
import re
from datetime import datetime
from io import BytesIO

from cryptography import x509
from pyhanko.keys.internal import (
    translate_pyca_cryptography_cert_to_asn1,
    translate_pyca_cryptography_key_to_asn1,
)
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import fields, signers
from pyhanko.sign.signers.pdf_signer import PdfSigner, PdfSignatureMetadata
from pyhanko_certvalidator.registry import SimpleCertificateStore

from stamp_creator import HtmlStamp, pango_to_html

_DATE_TOKENS = (("dd", "%d"), ("MM", "%m"), ("yyyy", "%Y"), ("yy", "%y"), ("HH", "%H"), ("mm", "%M"), ("ss", "%S"))


def _common_name(name):
    try:
        return name.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)[0].value
    except (IndexError, AttributeError):
        return str(name)


def parse_stamp_text(template_text, certificate, now=None):
    """Replaces the $$...$$ placeholders of a stamp template with data from the certificate."""
    text = (template_text.replace("$$SUBJECTCN$$", _common_name(certificate.subject))
            .replace("$$ISSUERCN$$", _common_name(certificate.issuer))
            .replace("$$CERTSERIAL$$", str(certificate.serial_number)))
    if date_match := re.search(r'\$\$SIGNDATE=(.*?)\$\$', text):
        pattern = date_match.group(1)
        for token, directive in _DATE_TOKENS:
            pattern = pattern.replace(token, directive)
        text = text.replace(date_match.group(0), (now or datetime.now()).strftime(pattern))
    return text


def sign_pdf(file_path, private_key, certificate, page_index, box, stamp_text,
             reason=None, location=None, field_name=None):
    """Signs a PDF with an incremental update and returns the signed bytes.

    `box` is (x0, y0, x1, y1) in PDF user space (origin at the bottom-left of the page).
    `stamp_text` is the already-parsed Pango markup shown inside the visible signature.
    """
    signing_key = translate_pyca_cryptography_key_to_asn1(private_key)
    signer_cert = translate_pyca_cryptography_cert_to_asn1(certificate)
    signer = signers.SimpleSigner(signing_cert=signer_cert, signing_key=signing_key,
                                  cert_registry=SimpleCertificateStore.from_certs([signer_cert]))

    x0, y0, x1, y1 = box
    stamp = HtmlStamp(html_content=pango_to_html(stamp_text), width=x1 - x0, height=y1 - y0)
    meta = PdfSignatureMetadata(
        field_name=field_name or f'Signature-{int(datetime.now().timestamp() * 1000)}',
        reason=reason or None,
        location=location or None,
    )
    field_spec = fields.SigFieldSpec(sig_field_name=meta.field_name, on_page=page_index, box=box)
    pdf_signer = PdfSigner(meta, signer, stamp_style=stamp.get_style(), new_field_spec=field_spec)

    output = BytesIO()
    with open(file_path, "rb") as source:
        pdf_signer.sign_pdf(IncrementalPdfFileWriter(source, strict=False), output=output)
    return output.getvalue()
