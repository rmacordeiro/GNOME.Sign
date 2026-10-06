# gnomesign.py

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Secret", "1")
from gi.repository import Gtk, Adw, Gio, Secret, GLib, GObject
import pymupdf, sys, os

from i18n import I18NManager
from runtime import is_sandboxed_runtime
from certificate_manager import CertificateManager, KEYRING_SCHEMA
from config_manager import ConfigManager
from paths import generate_output_path
from ui.stamp_editor_dialog import StampEditorDialog
from ui.dialogs import create_password_dialog, create_about_dialog, show_error_dialog
from services.document_service import display_rect_to_pdf_box, search_document
from services.tasks import run_in_thread
from services.signing_service import common_name, parse_stamp_text, sign_pdf
from services.validation_service import analyze_signatures, build_trust_roots

class GnomeSign(Adw.Application):
    """The main application class, managing state and high-level logic."""
    __gsignals__ = {
        'language-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'certificates-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'document-changed': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        'page-changed': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT, GObject.TYPE_INT, GObject.TYPE_INT, GObject.TYPE_BOOLEAN)),
        'signature-state-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'signatures-found': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        'toast-request': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING, GObject.TYPE_PYOBJECT)),
        'highlight-rect-changed': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        'search-highlights-updated': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        'search-result-selected': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
    }

    def __init__(self):
        """Initializes the application."""
        super().__init__(application_id="io.github.ppgllrd.GNOME-Sign", flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.config = ConfigManager()
        self.i18n = I18NManager()
        self.cert_manager = CertificateManager()
        self.doc, self.current_page, self.active_cert_path = None, 0, None
        self.page, self.display_pixbuf, self.current_file_path = None, None, None
        self.signature_rect, self.is_dragging_rect = None, False
        self.drag_offset_x, self.drag_offset_y = 0, 0
        self.start_x, self.start_y, self.end_x, self.end_y = -1, -1, -1, -1
        self.highlight_rect = None
        self.window, self.preferences_window = None, None
        self.signatures = []
        self._analysis_token = None
        self._search_token = None
        self._signing = False
        self.search_results = []
        self.search_highlights_on_page = []
        self.current_search_result_index = -1
    
    def _(self, key):
        """A shorthand for the translation function."""
        return self.i18n._(key)
    
    def do_startup(self):
        """Called when the application is starting up."""
        Adw.Application.do_startup(self)
        self.config.load()
        self.i18n.set_language(self.config.get_language())
        self.cert_manager.set_cert_paths(self.config.get_cert_paths())
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda action, param: self.quit())
        self.add_action(quit_action)
        self._build_actions()

        self.set_accels_for_action("app.open", ["<Primary>o"])
        self.set_accels_for_action("app.sign", ["<Primary>s"])
        self.set_accels_for_action("app.print", ["<Primary>p"])
        self.set_accels_for_action("app.preferences", ["<Primary>comma"])
        self.set_accels_for_action("app.quit", ["<Primary>q"])
        self.set_accels_for_action("app.toggle_search", ["<Primary>f"])

        self.active_cert_path = self.config.get_active_cert_path()
        from ui.app_window import AppWindow
        self.window = AppWindow(application=self)
        self.window.sidebar.connect("signature-selected", self.on_signature_selected)
        self.window.connect("close-request", self._on_window_close_request)
        self.connect("shutdown", self._on_shutdown)

    def _on_window_close_request(self, window):
        """Handles the main window close request."""
        self.quit()
        return True

    def _on_shutdown(self, app):
        """Saves the configuration when the application is shutting down."""
        self.config.save()
    
    def do_activate(self):
        """Called when the application is activated (e.g., launched from the desktop)."""
        self.window.present()
    
    def do_open(self, files, n_files, hint):
        """Handles opening files passed as arguments to the application."""
        if n_files > 0 and files[0].get_path():
            self.open_file_path(files[0].get_path())
        self.do_activate()
    
    def _build_actions(self):
        """Creates and adds application-wide actions."""
        actions_with_params = [("open_recent", self.on_open_recent_clicked, "s"), ("change_lang", self.on_lang_change_state, 's', self.i18n.get_language())]
        for name, callback, p_type, *state in actions_with_params:
            action = Gio.SimpleAction.new_stateful(name, GLib.VariantType(p_type), GLib.Variant(p_type, state[0])) if state else Gio.SimpleAction.new(name, GLib.VariantType(p_type))
            if state: action.connect("change-state", callback)
            else: action.connect("activate", callback)
            self.add_action(action)

        toggle_search_action = Gio.SimpleAction.new_stateful("toggle_search", None, GLib.Variant('b', False))
        toggle_search_action.connect("activate", self.on_toggle_search_activate)
        toggle_search_action.connect("change-state", self.on_toggle_search_state_change)
        toggle_search_action.set_enabled(False)
        self.add_action(toggle_search_action)

        action_open = Gio.SimpleAction.new("open", None)
        action_open.connect("activate", self.on_open_pdf_clicked)
        self.add_action(action_open)

        action_sign = Gio.SimpleAction.new("sign", None)
        action_sign.connect("activate", self.on_sign_document_clicked)
        action_sign.set_enabled(False) 
        self.add_action(action_sign)

        action_print = Gio.SimpleAction.new("print", None)
        action_print.connect("activate", self.on_print_clicked)
        action_print.set_enabled(False)
        self.add_action(action_print)

        action_show_sigs = Gio.SimpleAction.new("show_signatures", None)
        action_show_sigs.connect("activate", self.on_show_signatures_clicked)
        action_show_sigs.set_enabled(False) 
        self.add_action(action_show_sigs)
        
        action_prefs = Gio.SimpleAction.new("preferences", None)
        action_prefs.connect("activate", self.on_preferences_clicked)
        self.add_action(action_prefs)

        action_manage_certs = Gio.SimpleAction.new("manage_certs", None)
        action_manage_certs.connect("activate", self.on_preferences_clicked)
        self.add_action(action_manage_certs)

        action_edit_stamps = Gio.SimpleAction.new("edit_stamps", None)
        action_edit_stamps.connect("activate", self.on_edit_stamps_clicked)
        self.add_action(action_edit_stamps)
        
        action_about = Gio.SimpleAction.new("about", None)
        action_about.connect("activate", self.on_about_clicked)
        self.add_action(action_about)  

    def open_file_path(self, file_path, show_toast=True):
        """Opens a PDF document, analyzes it for signatures, and updates the application state."""
        try:
            if not os.path.exists(file_path): raise FileNotFoundError(f"File not found: {file_path}")
            if self.doc: self.doc.close()
            
            self._cancel_background_work()
            self.clear_search()
            self.signatures = []

            self.current_file_path = file_path; self.doc = pymupdf.open(file_path); self.current_page = 0
            self.config.add_recent_file(file_path); self.config.set_last_folder(os.path.dirname(file_path))

            self.emit("document-changed", self.doc)
            self.reset_signature_state(); self.display_page(0)
            self._update_actions_state()
            self._start_signature_analysis(file_path, show_toast)

        except Exception as e:
            show_error_dialog(self.window, self._("error"), self._("open_pdf_error").format(e))
            self.doc = None; self.signatures = []
            self.emit("document-changed", None)

    def _cancel_background_work(self):
        for token in (self._analysis_token, self._search_token):
            if token:
                token.cancel()
        self._analysis_token = self._search_token = None

    def _start_signature_analysis(self, file_path, show_toast):
        """Validates signatures in a worker thread so large or heavily signed PDFs don't block the UI."""
        def on_done(signatures, error):
            if file_path != self.current_file_path:
                return
            if error:
                print(f"Could not analyze for signatures: {error}")
                signatures = []
            self.signatures = signatures
            if signatures:
                self.emit("signatures-found", signatures)
            elif self.active_cert_path and show_toast:
                self.emit("toast-request", self._("toast_select_area"), None, None)
            self._update_actions_state()

        trust_paths = list(self.config.get_trusted_cert_paths())
        allow_online = self.config.get_flag("online_validation")

        def work(token):
            return analyze_signatures(file_path, trust_roots=build_trust_roots(trust_paths),
                                      cancelled=token.is_cancelled, allow_online=allow_online)

        self._analysis_token = run_in_thread(work, on_done)

    def on_show_signatures_clicked(self, action, param):
        """Focuses the sidebar on the list of existing signatures."""
        if self.window:
            if not self.window.flap.get_reveal_flap(): self.window.flap.set_reveal_flap(True)
            self.window.hide_signature_info()
            self.window.sidebar.focus_on_signatures()
            
    def on_signature_selected(self, sidebar, sig_details):
        """Shows details for a selected signature."""
        if self.window:
            self.window.hide_signature_info()
        if self.window:
            if not self.window.flap.get_reveal_flap():
                self.window.flap.set_reveal_flap(True)
            self.window.sidebar.select_signature(sig_details)    
        if sig_details.page_num != -1:
            self.display_page(sig_details.page_num, keep_sidebar_view=True)
            if sig_details.rect:
                self.highlight_rect = sig_details.rect
                self.emit("highlight-rect-changed", self.highlight_rect)
                if self.window:
                    self.window.scroll_to_rect(sig_details.rect)
        
        dialog = Adw.MessageDialog.new(self.window,
                                       heading=self._("sig_details_title"),
                                       body="") 

        validity_parts = [f"<b>{self._('sig_validity_title')}</b>"]
        if sig_details.intact and sig_details.valid:
            validity_parts.append(f"<span color='green'>{self._('sig_integrity_ok')}</span>")
            if sig_details.trusted:
                 validity_parts.append(f"<span color='green'>{self._('sig_trust_ok')}</span>")
            elif sig_details.revoked:
                 validity_parts.append(f"<span color='red'>{self._('sig_revoked')}</span>")
            else:
                 validity_parts.append(f"<span color='orange'>{self._('sig_trust_untrusted')}</span>")
        else:
            validity_parts.append(f"<span color='red'>{self._('sig_integrity_error')}</span>")
        
        validity_text = "\n".join(validity_parts)
        
        signer_esc = GLib.markup_escape_text(sig_details.signer_name)
        issuer_esc = GLib.markup_escape_text(sig_details.issuer_cn)
        serial_esc = GLib.markup_escape_text(sig_details.serial)
        
        details_parts = [
            validity_text,
            f"\n<b>{self._('signer')}:</b> {signer_esc}",
            f"<b>{self._('sign_date')}:</b> {sig_details.sign_time.strftime('%Y-%m-%d %H:%M:%S %Z') if sig_details.sign_time else 'N/A'}"
        ]
        
        if sig_details.reason:
            details_parts.append(f"<b>{self._('signature_reason_label')}:</b> {GLib.markup_escape_text(sig_details.reason)}")

        if sig_details.location:
            details_parts.append(f"<b>{self._('signature_location_label')}:</b> {GLib.markup_escape_text(sig_details.location)}")
            
        if sig_details.contact_info:
            details_parts.append(f"<b>{self._('signature_contact_label')}:</b> {GLib.markup_escape_text(sig_details.contact_info)}")

        details_parts.extend([
            f"\n<b>{self._('issuer')}:</b> {issuer_esc}",
            f"<b>{self._('serial')}:</b> {serial_esc}"
        ])
        
        esc = GLib.markup_escape_text
        tech = [f"\n<b>{self._('sig_technical_title')}</b>"]
        if sig_details.md_algorithm or sig_details.sig_mechanism:
            tech.append(f"<b>{self._('sig_algorithm')}:</b> {esc(sig_details.md_algorithm)} / {esc(sig_details.sig_mechanism)}")
        if sig_details.coverage:
            tech.append(f"<b>{self._('sig_coverage')}:</b> {esc(sig_details.coverage)} ({esc(sig_details.modification_level or '-')})")
        if sig_details.timestamp_time:
            trusted_ts = self._("sig_timestamp_trusted") if sig_details.timestamp_trusted else self._("sig_timestamp_untrusted")
            tech.append(f"<b>{self._('sig_timestamp')}:</b> {esc(sig_details.timestamp_time.strftime('%Y-%m-%d %H:%M:%S %Z'))} ({trusted_ts})")
        else:
            tech.append(f"<b>{self._('sig_timestamp')}:</b> {self._('review_none')}")
        revocation = self._("sig_revocation_checked") if sig_details.revocation_checked else self._("sig_revocation_offline")
        tech.append(f"<b>{self._('sig_revocation')}:</b> {revocation}")
        if sig_details.chain:
            tech.append(f"<b>{self._('sig_chain')}:</b> {esc(' → '.join(sig_details.chain))}")
        for key in sig_details.warnings:
            tech.append(f"<span color='orange'>⚠ {esc(self._(key))}</span>")
        details_parts.extend(tech)

        details_text = "\n".join(details_parts)
        
        body_label = Gtk.Label(
            use_markup=True,
            label=details_text,
            wrap=True,
            xalign=0, 
            selectable=True,
            justify=Gtk.Justification.CENTER
        )
        
        dialog.set_extra_child(body_label)
        
        dialog.add_response("ok", self._("accept"))
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        
        dialog.present()

    def on_open_pdf_clicked(self, action, param):
        """Handles the 'Open' action, showing a file chooser."""
        def on_response(dialog, response):
            if response == Gtk.ResponseType.ACCEPT:
                if file := dialog.get_file(): self.open_file_path(file.get_path())
        file_chooser = Gtk.FileChooserNative.new(self._("open_pdf_dialog_title"), self.window, Gtk.FileChooserAction.OPEN, self._("open"), self._("cancel"))
        filter_pdf = Gtk.FileFilter(); filter_pdf.set_name(self._("pdf_files")); filter_pdf.add_mime_type("application/pdf")
        file_chooser.add_filter(filter_pdf)
        if os.path.isdir(last_folder := self.config.get_last_folder()):
            file_chooser.set_current_folder(Gio.File.new_for_path(last_folder))
        file_chooser.connect("response", on_response); file_chooser.show()

    def on_open_recent_clicked(self, action, param):
        """Handles opening a file from the 'Open Recent' menu."""
        file_path = param.get_string()
        if os.path.exists(file_path): self.open_file_path(file_path)
        else:
            self.emit("toast-request", f"File not found: {file_path}", None, None)
            self.config.remove_recent_file(file_path); self.emit("language-changed")

    def on_preferences_clicked(self, action, param):
        """Shows the preferences window."""
        if self.preferences_window and self.preferences_window.is_visible():
            self.preferences_window.present()
            return
        from ui.preferences_window import PreferencesWindow
        page_name = 'certificates' if action.get_name() == 'manage_certs' else None
        self.preferences_window = PreferencesWindow(application=self, initial_page_name=page_name)
        self.preferences_window.connect("destroy", lambda w: self.config.save())
        self.preferences_window.present()

    def on_edit_stamps_clicked(self, action, param):
        """Shows the stamp editor dialog."""
        dialog = StampEditorDialog(parent_window=self.window, app=self)
        dialog.connect("destroy", lambda w: self.config.save())
        dialog.present()
    
    def on_lang_change_state(self, action, value):
        """Handles changing the application language."""
        new_lang = value.get_string()
        if action.get_state().get_string() != new_lang:
            action.set_state(value); self.i18n.set_language(new_lang)
            self.config.set_language(new_lang); self.emit('language-changed')

    def on_toggle_search_activate(self, action, param):
        """Handles activation of search action (e.g., via Ctrl+F)."""
        current_state = action.get_state().get_boolean()
        action.change_state(GLib.Variant('b', not current_state))
    
    def on_toggle_search_state_change(self, action, value):
        """Callback that updates the state of the 'toggle_search' action."""
        action.set_state(value)
    
    def can_sign(self):
        """True when a document, a certificate and (for visible signatures) an area are available."""
        has_area = self.signature_rect is not None or self.config.get_flag("invisible_signatures")
        return bool(self.doc and self.active_cert_path and has_area and not self._signing)

    def on_sign_document_clicked(self, action=None, param=None):
        """Handles the main 'Sign Document' action."""
        if self._signing:
            return
        if not self.active_cert_path:
            self.emit("toast-request", self._("no_cert_selected_error"), None, None); return
        if not (self.doc and self.current_file_path and self.can_sign()):
            self.emit("toast-request", self._("need_pdf_and_area"), None, None); return
        password = Secret.password_lookup_sync(KEYRING_SCHEMA, {"path": self.active_cert_path}, None)
        if not password:
            show_error_dialog(self.window, self._("error"), self._("credential_load_error"))
            return
        
        private_key_pyca, certificate_pyca = self.cert_manager.get_credentials(self.active_cert_path, password)
        if not (private_key_pyca and certificate_pyca):
            show_error_dialog(self.window, self._("error"), self._("credential_load_error"))
            return

        if self.config.get_flag("review_before_signing"):
            self._show_review_dialog(private_key_pyca, certificate_pyca)
        else:
            self._perform_signing(private_key_pyca, certificate_pyca)

    def _show_review_dialog(self, private_key_pyca, certificate_pyca):
        """Summarizes what is about to be signed and asks for confirmation."""
        cfg = self.config
        invisible = cfg.get_flag("invisible_signatures")
        lines = [
            (self._("review_certificate"), common_name(certificate_pyca.subject)),
            (self._("review_output"), os.path.basename(self._generate_output_path(self.current_file_path))),
            (self._("review_position"), self._("review_invisible") if invisible else self._("review_page_n").format(self.current_page + 1)),
            (self._("signature_reason_label"), cfg.get_signature_reason() or "-"),
            (self._("signature_location_label"), cfg.get_signature_location() or "-"),
            (self._("review_timestamp"), cfg.get_timestamp_url() or self._("review_none")),
        ]
        if cfg.get_flag("certify_signatures"):
            lines.append((self._("review_certification"), self._("review_certification_value")))
        body = "\n".join(f"{label}: {value}" for label, value in lines)

        dialog = Adw.MessageDialog.new(self.window, heading=self._("review_title"), body=body)
        dialog.add_response("cancel", self._("cancel"))
        dialog.add_response("sign", self._("sign_document"))
        dialog.set_response_appearance("sign", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("sign")
        dialog.set_close_response("cancel")

        def on_response(dlg, response):
            if response == "sign":
                self._perform_signing(private_key_pyca, certificate_pyca)

        dialog.connect("response", on_response)
        dialog.present()

    def on_print_clicked(self, action, param):
        """Handles the 'Print' action."""
        if not self.doc: return

        print_op = Gtk.PrintOperation()
        print_op.set_job_name(os.path.basename(self.current_file_path) if self.current_file_path else "Document")
        print_op.set_n_pages(len(self.doc))
        print_op.connect("draw_page", self._on_print_draw_page)

        res = print_op.run(Gtk.PrintOperationAction.PRINT_DIALOG, self.window)

        if res == Gtk.PrintOperationResult.ERROR:
            show_error_dialog(self.window, self._("print_error_title"), self._("print_error_message").format(print_op.get_status_string()))
        elif res == Gtk.PrintOperationResult.APPLY:
            self.emit("toast-request", self._("print_success_toast"), None, None)

    def _on_print_draw_page(self, operation, context, page_nr):
        """Draws a single page for the print operation."""
        try:
            page = self.doc.load_page(page_nr)
            cr = context.get_cairo_context()

            # Get page dimensions from PDF and print context dimensions
            pdf_width, pdf_height = page.rect.width, page.rect.height
            page_setup = context.get_page_setup()
            printable_width = page_setup.get_printable_width(Gtk.Unit.POINTS)
            printable_height = page_setup.get_printable_height(Gtk.Unit.POINTS)

            # Scale to fit printable area while maintaining aspect ratio
            scale_w = printable_width / pdf_width
            scale_h = printable_height / pdf_height
            scale = min(scale_w, scale_h)

            # Center the page
            cr.save()
            cr.translate(
                (printable_width - pdf_width * scale) / 2,
                (printable_height - pdf_height * scale) / 2
            )
            cr.scale(scale, scale)

            # Render the page using Fitz's drawing device
            dl = page.get_displaylist()
            dl.run(pymupdf.TOOLS.new_device("cairo", cr), pymupdf.Matrix(1, 1))

            cr.restore()

        except Exception as e:
            # It's hard to report errors from here, but we can log them.
            print(f"Error drawing page {page_nr} for printing: {e}")

    def _generate_output_path(self, input_path):
        return generate_output_path(input_path)

    def _perform_signing(self, private_key_pyca, certificate_pyca):
        """Signs in a worker thread (timestamp servers can be slow), then saves for native or sandboxed packages."""
        try:
            kwargs = self._collect_signing_arguments(certificate_pyca)
        except Exception as e:
            show_error_dialog(self.window, self._("sig_error_title"), self._("sig_error_message").format(e))
            return

        source_path = self.current_file_path
        self._signing = True
        self._update_actions_state()
        self.emit("signature-state-changed")
        if kwargs.get("timestamp_url"):
            self.emit("toast-request", self._("signing_with_timestamp"), None, None)

        def on_done(signed_bytes, error):
            self._signing = False
            self._update_actions_state()
            self.emit("signature-state-changed")
            if error:
                import traceback
                traceback.print_exception(error)
                show_error_dialog(self.window, self._("sig_error_title"), self._("sig_error_message").format(error))
            elif source_path == self.current_file_path:
                self._store_signed_bytes(signed_bytes)

        run_in_thread(lambda token: sign_pdf(source_path, private_key_pyca, certificate_pyca, **kwargs), on_done)

    def _store_signed_bytes(self, signed_bytes):
        if is_sandboxed_runtime():
            self._save_via_portal(signed_bytes)
            return
        try:
            output_path = self._generate_output_path(self.current_file_path)
            with open(output_path, "xb") as out_f:
                out_f.write(signed_bytes)
            self.emit("toast-request", self._("sign_success_message").format(os.path.basename(output_path)), self._("open"), lambda: self.open_file_path(output_path, show_toast=False))
        except Exception as e:
            import traceback
            traceback.print_exc()
            show_error_dialog(self.window, self._("sig_error_title"), self._("sig_error_message").format(e))

    def _collect_signing_arguments(self, certificate_pyca):
        """Reads the UI/config state (main thread only) into plain arguments for the signing service."""
        cfg = self.config
        visible = not cfg.get_flag("invisible_signatures")
        box = None
        if visible:
            x, y, w, h = self.signature_rect
            view_width = self.window.drawing_area.get_width()
            scale = self.page.rect.width / view_width if view_width > 0 else 1
            box = display_rect_to_pdf_box(self.page, pymupdf.Rect(x * scale, y * scale, (x + w) * scale, (y + h) * scale))
        return dict(
            page_index=self.current_page, box=box,
            stamp_text=self.get_parsed_stamp_text(certificate_pyca) if visible else "",
            reason=cfg.get_signature_reason(), location=cfg.get_signature_location(),
            timestamp_url=cfg.get_timestamp_url() or None,
            certify=cfg.get_flag("certify_signatures"), visible=visible,
        )

    def _save_via_portal(self, content_to_save_bytes):
        """Handles saving the signed file using the Gtk.FileChooserNative portal."""
        suggested_path = self._generate_output_path(self.current_file_path)
        suggested_name = os.path.basename(suggested_path)

        dialog = Gtk.FileChooserNative.new(
            self._("save_pdf_dialog_title"),
            self.window,
            Gtk.FileChooserAction.SAVE
        )
        dialog.set_modal(True)
        dialog.set_current_name(suggested_name)

        original_gfile = Gio.File.new_for_path(self.current_file_path)
        parent_folder = original_gfile.get_parent()
        if parent_folder:
            dialog.set_current_folder(parent_folder)

        dialog.connect("response", self._on_save_dialog_response, content_to_save_bytes)
        dialog.show()

    def _on_save_dialog_response(self, dialog, response_id, content_bytes):
        """Callback for when the user interacts with the save dialog."""
        if response_id == Gtk.ResponseType.ACCEPT:
            output_gfile = dialog.get_file()
            if output_gfile:
                try:
                    output_gfile.replace_contents(
                        content_bytes, None, False, 
                        Gio.FileCreateFlags.REPLACE_DESTINATION, None
                    )
                    output_path = output_gfile.get_path()
                    self.emit("toast-request", self._("sign_success_message").format(os.path.basename(output_path)), self._("open"), lambda: self.open_file_path(output_path, show_toast=False))
                except GLib.Error as e:
                    show_error_dialog(self.window, self._("sig_error_title"), self._("sig_error_message").format(e))
        dialog.destroy()

    def on_about_clicked(self, action, param):
        """Shows the 'About' dialog."""
        create_about_dialog(self.window, self._)

    def search_text(self, text):
        """Searches the document in a worker thread; a newer query cancels the running one."""
        if not self.doc or not text:
            return
        self.clear_search()
        path = self.current_file_path

        def on_done(results, error):
            if error or path != self.current_file_path:
                return
            self.search_results = results
            self.window.sidebar.populate_search_results(self.search_results)
            if self.search_results:
                self.select_search_result(0)
            self.display_page(self.current_page, keep_sidebar_view=True)

        self._search_token = run_in_thread(lambda token: search_document(path, text, cancelled=token.is_cancelled), on_done)

    def clear_search(self):
        """Clears the current search."""
        if self._search_token:
            self._search_token.cancel()
            self._search_token = None
        self.search_results = []
        self.search_highlights_on_page = []
        self.current_search_result_index = -1
        self.emit("search-highlights-updated", [])
        if self.window:
            self.window.sidebar.populate_search_results([])
            self.window.drawing_area.queue_draw()
            self.window.update_search_nav_buttons()

    def select_search_result(self, index):
        """Selects a search result by its index."""
        if not (0 <= index < len(self.search_results)):
            return
        self.current_search_result_index = index
        result = self.search_results[index]
        self.display_page(result.page_num, keep_sidebar_view=True)
        if self.page:
            page_height = self.page.rect.height
            search_rect = result.rect  
            converted_rect = (
                search_rect.x0,
                page_height - search_rect.y1,
                search_rect.x1,
                page_height - search_rect.y0
            )
            self.highlight_rect = converted_rect
        else:
            self.highlight_rect = None
        self.emit("search-result-selected", result)
        if self.window:
            self.window.update_search_nav_buttons()

    def next_search_result(self, button=None):
        """Navigates to the next search result, wrapping around to the start."""
        num_results = len(self.search_results)
        if num_results == 0:
            return
        next_index = (self.current_search_result_index + 1) % num_results
        self.select_search_result(next_index)

    def previous_search_result(self, button=None):
        """Navigates to the previous search result."""
        if self.current_search_result_index > 0:
            self.select_search_result(self.current_search_result_index - 1)

    def _update_actions_state(self):
        """Centralized method to update the enabled state of actions."""
        doc_loaded = self.doc is not None

        toggle_search_action = self.lookup_action("toggle_search")
        if toggle_search_action:
            toggle_search_action.set_enabled(doc_loaded)
            if not doc_loaded and toggle_search_action.get_state().get_boolean():
                toggle_search_action.set_state(GLib.Variant('b', False))

        can_sign = self.can_sign()
        sign_action = self.lookup_action("sign")
        if sign_action:
            sign_action.set_enabled(can_sign)

        print_action = self.lookup_action("print")
        if print_action:
            print_action.set_enabled(doc_loaded)

        doc_has_signatures = doc_loaded and len(self.signatures) > 0
        show_sigs_action = self.lookup_action("show_signatures")
        if show_sigs_action:
            show_sigs_action.set_enabled(doc_has_signatures)    
    
    def reset_signature_state(self):
        """Resets all properties related to the current signature drawing/selection."""
        self.signature_rect = None
        self.start_x, self.start_y, self.end_x, self.end_y = -1, -1, -1, -1
        self.is_dragging_rect = False
        self.highlight_rect = None
        self.emit("signature-state-changed")
        self._update_actions_state()

    def display_page(self, page_num, keep_sidebar_view=False):
        """Loads and displays a specific page of the current document."""
        if self.highlight_rect:
            self.highlight_rect = None
            self.emit("highlight-rect-changed", None)

        self.search_highlights_on_page = []
        if self.search_results:
            for result in self.search_results:
                if result.page_num == page_num:
                    self.search_highlights_on_page.append(result.rect)
        self.emit("search-highlights-updated", self.search_highlights_on_page)

        if not self.doc or not (0 <= page_num < len(self.doc)):
            self.page = None; self.doc = None; self.current_file_path = None; self.display_pixbuf = None; self.signatures = []
            self.emit("document-changed", None)
        else:
            self.current_page = page_num
            self.page = self.doc.load_page(page_num)
            self.display_pixbuf = None
            self.emit("page-changed", self.page, self.current_page, len(self.doc), keep_sidebar_view)
    
    def on_prev_page_clicked(self, button):
        """Navigates to the previous page."""
        if self.doc and self.current_page > 0:
            self.reset_signature_state(); self.display_page(self.current_page - 1)
    
    def on_next_page_clicked(self, button):
        """Navigates to the next page."""
        if self.doc and self.current_page < len(self.doc) - 1:
            self.reset_signature_state(); self.display_page(self.current_page + 1)
            
    def on_jump_to_page_clicked(self, button):
        """Shows a dialog to jump to a specific page."""
        if not self.doc: return
        dialog = Gtk.Dialog(title=self._("jump_to_page_title"), transient_for=self.window, modal=True)
        dialog.add_buttons(self._("cancel"), Gtk.ResponseType.CANCEL, self._("accept"), Gtk.ResponseType.OK)
        content_area = dialog.get_content_area(); content_area.set_spacing(10); content_area.set_margin_top(10); content_area.set_margin_bottom(10); content_area.set_margin_start(10); content_area.set_margin_end(10)
        content_area.append(Gtk.Label(label=self._("jump_to_page_prompt").format(len(self.doc))))
        adj = Gtk.Adjustment(value=self.current_page + 1, lower=1, upper=len(self.doc), step_increment=1)
        spin = Gtk.SpinButton(adjustment=adj, numeric=True); content_area.append(spin)
        dialog.set_default_widget(spin); spin.connect("activate", lambda w: dialog.response(Gtk.ResponseType.OK))
        def on_response(d, res):
            if res == Gtk.ResponseType.OK:
                self.reset_signature_state(); self.display_page(spin.get_value_as_int() - 1)
            d.destroy()
        dialog.connect("response", on_response); dialog.present()

    def on_drag_begin(self, gesture, start_x, start_y):
        """Handles the beginning of a drag gesture on the document view."""
        self.highlight_rect = None; self.emit("highlight-rect-changed", None)
        if self.signature_rect:
            x, y, w, h = self.signature_rect
            if x <= start_x <= x + w and y <= start_y <= y + h:
                self.is_dragging_rect, self.drag_offset_x, self.drag_offset_y = True, start_x - x, start_y - y; return
        self.is_dragging_rect, self.start_x, self.start_y = False, start_x, start_y
        self.end_x, self.end_y = start_x, start_y; self.signature_rect = None
        self.emit("signature-state-changed")

    def on_drag_update(self, gesture, offset_x, offset_y):
        """Handles the update of a drag gesture."""
        success, start_point_x, start_point_y = gesture.get_start_point()
        if not success: return
        current_x, current_y = start_point_x + offset_x, start_point_y + offset_y
        if self.is_dragging_rect:
            _, _, w, h = self.signature_rect
            self.signature_rect = (current_x - self.drag_offset_x, current_y - self.drag_offset_y, w, h)
        else: self.end_x, self.end_y = current_x, current_y
        self.emit("signature-state-changed")

    def on_drag_end(self, gesture, offset_x, offset_y):
        """Handles the end of a drag gesture, finalizing the signature rectangle."""
        if not self.is_dragging_rect:
            x1, y1 = min(self.start_x, self.end_x), min(self.start_y, self.end_y)
            width, height = abs(self.start_x - self.end_x), abs(self.start_y - self.end_y)
            self.signature_rect = (x1, y1, width, height) if width > 5 and height > 5 else None
        self.is_dragging_rect = False
        self.emit("signature-state-changed")
        self._update_actions_state()

    def get_parsed_stamp_text(self, certificate, override_template=None):
        """Parses a signature template, replacing placeholders with actual certificate data."""
        if override_template is not None:
            template_text = override_template
        else:
            template_obj = self.config.get_active_template()
            if not template_obj: return "Error: No active signature template found."
            template_text = template_obj.get("template", template_obj.get("template_es", ""))
        return parse_stamp_text(template_text, certificate)

    def set_active_certificate(self, path):
        """Sets the active certificate, saves the config, and notifies the UI."""
        self.active_cert_path = path
        self.config.set_active_cert_path(path)
        self.emit("certificates-changed")
        self._update_actions_state()

    def add_certificate(self, pkcs12_path, password):
        """Adds a new certificate, saves it, and notifies the UI."""
        common_name = self.cert_manager.test_certificate(pkcs12_path, password)
        if common_name:
            Secret.password_store_sync(KEYRING_SCHEMA, {"path": pkcs12_path}, Secret.COLLECTION_DEFAULT, f"Certificate password for {common_name}", password, None)
            self.config.add_cert_path(pkcs12_path)
            self.config.set_last_folder(os.path.dirname(pkcs12_path))
            self.cert_manager.add_cert_path(pkcs12_path)
            self.set_active_certificate(pkcs12_path)
            self.config.save()
            return True
        else:
            show_error_dialog(self.window, self._("error"), self._("bad_password_or_file"))
            return False

    def remove_certificate(self, path):
        """Removes a certificate and notifies the UI."""
        self.cert_manager.remove_credentials_from_keyring(path)
        self.config.remove_cert_path(path)
        self.cert_manager.remove_cert_path(path)

        if self.active_cert_path == path:
            certs = self.cert_manager.get_all_certificate_details()
            new_path = certs[0]['path'] if certs else None
            self.set_active_certificate(new_path)
        else:
            self.emit("certificates-changed")
        
        self.config.save()

    def remove_template(self, template_id):
        """Removes a signature template, falls back to a valid active template and notifies the UI."""
        if self.config.delete_template(template_id):
            self.config.save()
            self.emit("signature-state-changed")

    def request_add_new_certificate(self):
        """Manages the full flow of adding a new certificate."""
        def on_file_chooser_response(dialog, response):
            if response == Gtk.ResponseType.ACCEPT:
                if file := dialog.get_file():
                    pkcs12_path = file.get_path()
                    
                    def on_password_response(password):
                        if password is not None:
                            self.add_certificate(pkcs12_path, password)
                    
                    create_password_dialog(self.preferences_window, self._("password"), os.path.basename(pkcs12_path), self._, on_password_response)

        file_chooser = Gtk.FileChooserNative.new(self._("open_cert_dialog_title"), self.preferences_window, Gtk.FileChooserAction.OPEN, self._("open"), self._("cancel"))
        filter_p12 = Gtk.FileFilter()
        filter_p12.set_name(self._("p12_files"))
        filter_p12.add_pattern("*.p12"); filter_p12.add_pattern("*.pfx")
        file_chooser.add_filter(filter_p12)
        file_chooser.connect("response", on_file_chooser_response)
        file_chooser.show()

if __name__ == "__main__":
    app = GnomeSign()
    sys.exit(app.run(sys.argv))