import os


def generate_output_path(input_path):
    """Returns a non-existing '<name>-signed[-N].<ext>' path next to input_path.

    In Flatpak, os.path.exists() is limited by sandbox permissions, so this is a
    best-effort suggestion; the file is also opened exclusively when written.
    """
    base_path, ext = os.path.splitext(input_path)
    output_path = f"{base_path}-signed{ext}"
    version = 1
    while os.path.exists(output_path):
        output_path = f"{base_path}-signed-{version}{ext}"
        version += 1
    return output_path
