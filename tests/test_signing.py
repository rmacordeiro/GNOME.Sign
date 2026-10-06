import socket

import pymupdf
import pytest

from certificate_manager import CertificateManager
from services.signing_service import parse_stamp_text, sign_pdf
from services.validation_service import analyze_signatures, flatten_page_tree


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("network access attempted")
    monkeypatch.setattr(socket.socket, "connect", blocked)


def make_pdf(path, pages=1):
    doc = pymupdf.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"page {i + 1}")
    doc.save(path)
    return str(path)


@pytest.fixture
def credentials(p12_file):
    return CertificateManager().get_credentials(p12_file, "secret")


def signed_pdf(tmp_path, credentials, pages=3, page_index=1):
    key, cert = credentials
    src = make_pdf(tmp_path / "in.pdf", pages)
    data = sign_pdf(src, key, cert, page_index, (50, 600, 250, 700), "<b>$$SUBJECTCN$$</b>".replace("$$SUBJECTCN$$", "Test Signer"),
                    reason="because", location="here")
    out = tmp_path / "out.pdf"
    out.write_bytes(data)
    return out, cert


def test_sign_and_analyze_roundtrip(tmp_path, credentials):
    out, cert = signed_pdf(tmp_path, credentials)
    (sig,) = analyze_signatures(str(out), trust_roots=[])
    assert sig.intact
    assert not sig.trusted and not sig.valid  # "valid" is the full bottom line, which requires trust
    assert sig.signer_name == "Test Signer"
    assert sig.reason == "because" and sig.location == "here"
    assert sig.page_num == 1
    assert [round(v) for v in sig.rect] == [50, 600, 250, 700]


def test_trusted_when_certificate_is_a_trust_root(tmp_path, credentials):
    from asn1crypto import x509 as asn1_x509
    from cryptography.hazmat.primitives import serialization
    out, cert = signed_pdf(tmp_path, credentials)
    root = asn1_x509.Certificate.load(cert.public_bytes(serialization.Encoding.DER))
    (sig,) = analyze_signatures(str(out), trust_roots=[root])
    assert sig.trusted and sig.valid


def test_original_content_is_preserved_by_incremental_save(tmp_path, credentials):
    out, _ = signed_pdf(tmp_path, credentials)
    original = (tmp_path / "in.pdf").read_bytes()
    assert out.read_bytes().startswith(original)


def test_two_signatures_are_both_found(tmp_path, credentials):
    key, cert = credentials
    first, _ = signed_pdf(tmp_path, credentials)
    data = sign_pdf(str(first), key, cert, 0, (50, 100, 250, 200), "second")
    second = tmp_path / "second.pdf"
    second.write_bytes(data)
    sigs = analyze_signatures(str(second), trust_roots=[])
    assert len(sigs) == 2 and all(s.intact for s in sigs)
    assert all(s.intact for s in sigs) and sorted(s.page_num for s in sigs) == [0, 1]


def test_tampering_is_detected(tmp_path, credentials):
    out, _ = signed_pdf(tmp_path, credentials)
    data = bytearray(out.read_bytes())
    pos = data.index(b"page 1") if b"page 1" in data else 100
    data[pos + 5] ^= 0x01
    tampered = tmp_path / "tampered.pdf"
    tampered.write_bytes(bytes(data))
    sigs = analyze_signatures(str(tampered), trust_roots=[])
    assert sigs and not (sigs[0].intact and sigs[0].valid)


def test_unsigned_pdf_has_no_signatures(tmp_path):
    assert analyze_signatures(make_pdf(tmp_path / "plain.pdf"), trust_roots=[]) == []


def make_nested_pdf(path):
    """4 pages where pages 1-2 live under an intermediate /Pages node."""
    doc = pymupdf.open()
    for i in range(4):
        doc.new_page().insert_text((72, 72), f"page {i + 1}")
    root = doc.xref_get_key(doc.pdf_catalog(), "Pages")[1].split()[0]
    pages = [doc[i].xref for i in range(4)]
    node = doc.get_new_xref()
    doc.update_object(node, f"<< /Type /Pages /Kids [{pages[0]} 0 R {pages[1]} 0 R] /Count 2 /Parent {root} 0 R >>")
    for xref in pages[:2]:
        doc.xref_set_key(xref, "Parent", f"{node} 0 R")
    doc.xref_set_key(int(root), "Kids", f"[{node} 0 R {pages[2]} 0 R {pages[3]} 0 R]")
    doc.save(path)
    return str(path)


def test_signature_page_is_found_in_nested_page_tree(tmp_path, credentials):
    key, cert = credentials
    src = make_nested_pdf(tmp_path / "nested.pdf")
    from pyhanko.pdf_utils.reader import PdfFileReader
    with open(src, "rb") as f:
        assert len(flatten_page_tree(PdfFileReader(f).root["/Pages"])) == 4
    for page_index in (1, 3):
        out = tmp_path / f"signed{page_index}.pdf"
        out.write_bytes(sign_pdf(src, key, cert, page_index, (10, 10, 110, 60), "x"))
        (sig,) = analyze_signatures(str(out), trust_roots=[])
        assert sig.page_num == page_index


def test_parse_stamp_text_placeholders(credentials):
    from datetime import datetime
    _, cert = credentials
    text = parse_stamp_text("$$SUBJECTCN$$|$$ISSUERCN$$|$$CERTSERIAL$$|$$SIGNDATE=dd/MM/yyyy HH:mm$$", cert, now=datetime(2026, 1, 2, 3, 4))
    assert text == f"Test Signer|Test Signer|{cert.serial_number}|02/01/2026 03:04"
