# GNOME-Sign

GNOME-Sign is a simple and easy-to-use application for signing PDF documents with a digital certificate. It is built using Python and GTK4/Adw, and it is designed to integrate well with the GNOME desktop environment.

## Features

*   **PDF Viewing**: Open and view PDF documents.
*   **Digital Signatures**: Sign PDF documents with a PFX/P12 certificate.
*   **Signature Validation**: Verify the digital signatures in a PDF document.
*   **Customizable Stamps**: Create and customize visual signature stamps using Pango markup.
*   **Text Search**: Search for text within the document, with results highlighted and displayed in the sidebar.
*   **Printing**: Print PDF documents using the system's native print dialog.
*   **Recent Files**: Quickly access your recently opened files.

## Build and Packaging

GNOME-Sign now uses a packaging-neutral Meson install layout so the same source tree can be built for Flatpak, Snap, and Debian packages while keeping PDF signing support as a required feature.

### Local install layout

1. Install Meson and Ninja.
2. Configure the project:
   ```bash
   meson setup builddir --prefix=/usr
   ```
3. Install into a staging directory or the local system:
   ```bash
   DESTDIR="$PWD/out" meson install -C builddir
   ```

The installed launcher is `gnomesign`, and the application data is installed under `share/io.github.ppgllrd.GNOME-Sign`.

### Flatpak

1. Install `flatpak` and `flatpak-builder`.
2. Build the bundle:
   ```bash
   flatpak-builder build-dir io.github.ppgllrd.GNOME-Sign.json --user --install --force-clean
   ```
3. Run it:
   ```bash
   flatpak run io.github.ppgllrd.GNOME-Sign
   ```

### Snap

The Snap packaging metadata lives in `snap/snapcraft.yaml` and builds the same Meson install tree.

Typical build command:
```bash
snapcraft pack
```

### Debian package

The Debian packaging metadata lives in `debian/`.

Typical build command:
```bash
dpkg-buildpackage -us -uc -b
```

## Running from source for development

If you prefer to run the application directly from the source tree, install the dependencies manually.

### Python dependencies

```bash
pip install -r requirements.txt
```

### System dependencies

*   **On Debian/Ubuntu-based systems**:
    ```bash
    sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-secret-1
    ```
*   **On Fedora**:
    ```bash
    sudo dnf install python3-gobject gtk4 libadwaita libsecret
    ```

### Run from source

```bash
python3 src/main.py
```

## License

This project is licensed under the terms of the GNU Affero General Public License v3.0 or later. See the [LICENSE](LICENSE) file for more details.
