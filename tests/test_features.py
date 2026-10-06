import pymupdf
import pytest

from certificate_manager import CertificateManager
from services.document_service import display_rect_to_pdf_box
from services.signing_service import sign_pdf, validate_timestamp_url
from services.validation_service import analyze_signatures, build_trust_roots, load_certificates_from_file


@pytest.fixture
def credentials(p12_file):
    return CertificateManager().get_credentials(p12_file, "secret")


def blank_pdf(path, rotation=0, cropbox=None):
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    if cropbox:
        page.set_cropbox(pymupdf.Rect(*cropbox))
    page.set_rotation(rotation)
    doc.save(path)
    return str(path)


def test_invisible_signature_has_empty_rect(tmp_path, credentials):
    key, cert = credentials
    src = blank_pdf(tmp_path / "a.pdf")
    out = tmp_path / "o.pdf"
    out.write_bytes(sign_pdf(src, key, cert, 0, None, "", visible=False))
    (sig,) = analyze_signatures(str(out), trust_roots=[])
    assert sig.intact
    assert not sig.rect or sig.rect == [0.0, 0.0, 0.0, 0.0]


def test_certification_signature_sets_docmdp(tmp_path, credentials):
    key, cert = credentials
    src = blank_pdf(tmp_path / "a.pdf")
    out = tmp_path / "o.pdf"
    out.write_bytes(sign_pdf(src, key, cert, 0, (10, 10, 110, 60), "x", certify=True))
    with pymupdf.open(str(out)) as doc:
        assert "DocMDP" in doc.xref_object(doc.pdf_catalog())  # /Perms << /DocMDP ... >>
    (sig,) = analyze_signatures(str(out), trust_roots=[])
    assert sig.intact and sig.docmdp_ok is not False


def test_technical_details_and_warnings(tmp_path, credentials):
    key, cert = credentials
    out = tmp_path / "o.pdf"
    out.write_bytes(sign_pdf(blank_pdf(tmp_path / "a.pdf"), key, cert, 0, (10, 10, 110, 60), "x"))
    (sig,) = analyze_signatures(str(out), trust_roots=[])
    assert sig.md_algorithm == "sha256"
    assert sig.coverage == "ENTIRE_FILE" and sig.modification_level == "NONE"
    assert {"sig_warn_untrusted", "sig_warn_no_timestamp", "sig_warn_offline"} <= set(sig.warnings)
    assert "sig_warn_modified" not in sig.warnings
    assert sig.revocation_checked is False


def test_incremental_edit_after_signing_is_flagged(tmp_path, credentials):
    key, cert = credentials
    edited = tmp_path / "e.pdf"
    edited.write_bytes(sign_pdf(blank_pdf(tmp_path / "a.pdf"), key, cert, 0, (10, 10, 110, 60), "x"))
    with pymupdf.open(str(edited)) as doc:
        doc[0].insert_text((50, 300), "added later")
        doc.saveIncr()
    (sig,) = analyze_signatures(str(edited), trust_roots=[])
    assert sig.coverage != "ENTIRE_FILE" or sig.modification_level != "NONE"
    assert "sig_warn_modified" in sig.warnings or "sig_warn_partial_coverage" in sig.warnings


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("cropbox", [None, (20, 40, 380, 560)])
def test_display_rect_maps_back_to_the_same_page_position(tmp_path, rotation, cropbox):
    path = blank_pdf(tmp_path / "r.pdf", rotation, cropbox)
    with pymupdf.open(path) as doc:
        page = doc[0]
        shown = pymupdf.Rect(30, 50, 130, 90)
        x0, y0, x1, y1 = display_rect_to_pdf_box(page, shown)
        assert x0 < x1 and y0 < y1
        # PDF space (origin bottom-left) -> MuPDF unrotated -> rotated display space must give back the rectangle.
        back = pymupdf.Rect(x0, y0, x1, y1) * page.transformation_matrix * page.rotation_matrix
        back.normalize()
        assert tuple(round(v, 3) for v in back) == tuple(round(v, 3) for v in shown)


def test_signature_on_rotated_cropped_page_lands_where_selected(tmp_path, credentials):
    key, cert = credentials
    src = blank_pdf(tmp_path / "r.pdf", 90, (20, 40, 380, 560))
    with pymupdf.open(src) as doc:
        box = display_rect_to_pdf_box(doc[0], pymupdf.Rect(30, 50, 130, 90))
    out = tmp_path / "o.pdf"
    out.write_bytes(sign_pdf(src, key, cert, 0, box, "x"))
    (sig,) = analyze_signatures(str(out), trust_roots=[])
    assert sig.intact
    assert [round(v) for v in sig.rect] == [round(v) for v in box]


def test_timestamp_url_validation():
    assert validate_timestamp_url(" https://tsa.example/ts ") == "https://tsa.example/ts"
    for bad in ("", "ftp://x/y", "javascript:alert(1)", "http://", "tsa.example"):
        with pytest.raises(ValueError):
            validate_timestamp_url(bad)


def test_unreachable_timestamp_server_fails_instead_of_signing_silently(tmp_path, credentials):
    key, cert = credentials
    src = blank_pdf(tmp_path / "a.pdf")
    with pytest.raises(Exception):
        sign_pdf(src, key, cert, 0, (10, 10, 110, 60), "x", timestamp_url="http://127.0.0.1:9/tsa")


def test_extra_trust_roots_are_loaded_and_bad_files_skipped(tmp_path, credentials):
    from cryptography.hazmat.primitives import serialization
    _, cert = credentials
    pem_path = tmp_path / "root.pem"
    pem_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    der_path = tmp_path / "root.der"
    der_path.write_bytes(cert.public_bytes(serialization.Encoding.DER))
    bad = tmp_path / "bad.pem"
    bad.write_text("not a certificate")
    assert len(load_certificates_from_file(str(pem_path))) == 1
    assert len(load_certificates_from_file(str(der_path))) == 1
    base = len(build_trust_roots())
    assert len(build_trust_roots([str(pem_path), str(bad), str(tmp_path / "missing")])) == base + 1
