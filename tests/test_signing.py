import io

import fitz
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import signers
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext

from certificate_manager import CertificateManager


def _sample_pdf():
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "hello")
    return doc.tobytes()


def test_sign_and_validate_roundtrip(p12_file):
    key, cert = CertificateManager().get_credentials(p12_file, "secret")
    from pyhanko.keys import load_cert_from_pemder  # noqa: F401
    from pyhanko_certvalidator.registry import SimpleCertificateStore
    from asn1crypto import x509 as asn1_x509, keys as asn1_keys
    from cryptography.hazmat.primitives import serialization

    signer = signers.SimpleSigner(
        signing_cert=asn1_x509.Certificate.load(cert.public_bytes(serialization.Encoding.DER)),
        signing_key=asn1_keys.PrivateKeyInfo.load(
            key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())),
        cert_registry=SimpleCertificateStore(),
    )
    writer = IncrementalPdfFileWriter(io.BytesIO(_sample_pdf()))
    out = io.BytesIO()
    signers.sign_pdf(writer, signers.PdfSignatureMetadata(field_name="Sig1", reason="test"), signer=signer, output=out)

    reader = PdfFileReader(io.BytesIO(out.getvalue()))
    sigs = reader.embedded_signatures
    assert len(sigs) == 1
    status = validate_pdf_signature(sigs[0], ValidationContext(allow_fetching=False, trust_roots=[signer.signing_cert]))
    assert status.intact and status.valid and status.trusted

    # Flipping a byte inside the signed range must be detected.
    tampered = bytearray(out.getvalue())
    pos = len(_sample_pdf()) // 2
    tampered[pos] ^= 0x01
    t_reader = PdfFileReader(io.BytesIO(bytes(tampered)), strict=False)
    t_status = validate_pdf_signature(t_reader.embedded_signatures[0], ValidationContext(allow_fetching=False))
    assert not t_status.intact
