from path_utils import generate_output_path


def test_generate_output_path_uses_signed_suffix(tmp_path):
    input_file = tmp_path / "document.pdf"
    input_file.write_bytes(b"content")

    assert generate_output_path(str(input_file)).endswith("document-signed.pdf")


def test_generate_output_path_increments_when_target_exists(tmp_path):
    input_file = tmp_path / "document.pdf"
    input_file.write_bytes(b"content")
    (tmp_path / "document-signed.pdf").write_bytes(b"content")
    (tmp_path / "document-signed-1.pdf").write_bytes(b"content")

    assert generate_output_path(str(input_file)).endswith("document-signed-2.pdf")
