import os


def generate_output_path(input_path):
    """
    Generate a unique output filename based on the input path.
    Appends '-signed.pdf', and adds a version number if a file with that name exists.

    NOTE: In Flatpak, os.path.exists() is limited by sandbox permissions.
    This provides a best-effort suggestion; the portal itself will prevent overwrites.
    """
    base_path, ext = os.path.splitext(input_path)
    output_path = f"{base_path}-signed{ext}"
    version = 1
    while os.path.exists(output_path):
        output_path = f"{base_path}-signed-{version}{ext}"
        version += 1
    return output_path
