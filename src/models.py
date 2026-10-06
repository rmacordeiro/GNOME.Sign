"""Plain data types shared by the services and the GTK layer (no GTK imports)."""

class SearchResult:
    """A data class to hold information about a single text search result."""
    def __init__(self, page_num, rect, context):
        self.page_num = page_num
        self.rect = rect
        self.context = context

class SignatureDetails:
    """A data class to hold processed information about a digital signature."""
    def __init__(self, pyhanko_sig, validation_status, page_num, rect):
        """Initializes the signature details from pyHanko objects."""
        self.pyhanko_sig = pyhanko_sig
        self.status = validation_status
        self.intact = validation_status.intact
        self.valid = validation_status.valid
        self.trusted = validation_status.trusted
        self.revoked = validation_status.revoked
        self.valid = validation_status.bottom_line
        self.signer_name = "Unknown"
        self.sign_time = None
        self.issuer_cn = "Unknown"
        self.serial = "Unknown"
        self.page_num = page_num
        self.rect = rect
        
        sig_obj = pyhanko_sig.sig_object
        self.reason = str(sig_obj.get('/Reason', ''))
        self.location = str(sig_obj.get('/Location', ''))
        self.contact_info = str(sig_obj.get('/ContactInfo', ''))
       
        cert = getattr(validation_status, 'signer_cert', None)
        if not cert:
            cert = pyhanko_sig.signer_cert
        def get_cn_from_name(name_obj):
            if not name_obj: return "N/A"
            try:
                native_dict = name_obj.native
                return native_dict.get('common_name', str(name_obj))
            except Exception: return str(name_obj)
        if cert:
            try:
                self.signer_name = get_cn_from_name(cert.subject)
                self.issuer_cn = get_cn_from_name(cert.issuer)
                self.serial = str(cert.serial_number)
            except Exception as e:
                print(f"Error parsing certificate details: {e}")
                self.signer_name = str(cert.subject) if cert.subject else "Parsing Error"
                self.issuer_cn = str(cert.issuer) if cert.issuer else "Parsing Error"
        self.sign_time = None
        try:
            signed_attrs = self.pyhanko_sig.signer_info['signed_attrs']
            for attr in signed_attrs:
                if attr['type'].native == 'signing_time':
                    self.sign_time = attr['values'][0].native
                    break
        except (KeyError, AttributeError, IndexError, TypeError):
            pass
        if not self.sign_time and validation_status.timestamp_validity:
            self.sign_time = validation_status.timestamp_validity.timestamp
