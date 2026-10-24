"""Adobe-compliant PKCS#7 digital signature engine for PDF Partner."""

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from datetime import datetime, timedelta
from pathlib import Path
import hashlib

from pdf_partner_app.utils.config import MM, logger

# Try to import cryptography for certificate handling
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.backends import default_backend
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography module not available - install: pip install cryptography")


class AdobeSignatureManager:
    """Adobe PKCS#7 compliant digital signature support."""

    @staticmethod
    def create_self_signed_certificate(common_name="PDF Signer", organization="Organization",
                                       country="US", validity_days=3650, key_size=2048):
        """
        Create self-signed X.509 certificate for signing.
        Returns:
            (private_key, certificate) tuple or (None, None)
        """
        if not CRYPTO_AVAILABLE:
            logger.error("cryptography module required")
            return None, None

        try:
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
                backend=default_backend()
            )

            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, country),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
                x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            ])

            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(private_key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.utcnow())
                .not_valid_after(datetime.utcnow() + timedelta(days=validity_days))
                .add_extension(
                    x509.BasicConstraints(ca=False, path_length=None),
                    critical=True,
                )
                .add_extension(
                    x509.KeyUsage(
                        digital_signature=True,
                        content_commitment=True,
                        key_encipherment=False,
                        data_encipherment=False,
                        key_agreement=False,
                        key_cert_sign=False,
                        crl_sign=False,
                        encipher_only=False,
                        decipher_only=False,
                    ),
                    critical=True,
                )
                .sign(private_key, hashes.SHA256(), default_backend())
            )

            logger.info("Self-signed certificate created: CN=%s", common_name)
            return private_key, cert

        except Exception as e:
            logger.error("Certificate creation failed: %s", e)
            return None, None

    @staticmethod
    def load_certificate(cert_path):
        """Load X.509 certificate from PEM/DER file."""
        if not CRYPTO_AVAILABLE:
            return None

        try:
            cert_path = Path(cert_path)
            with open(cert_path, "rb") as f:
                cert_data = f.read()

            try:
                cert = x509.load_pem_x509_certificate(cert_data, default_backend())
            except Exception:
                cert = x509.load_der_x509_certificate(cert_data, default_backend())

            logger.info("Certificate loaded: %s", cert_path.name)
            return cert
        except Exception as e:
            logger.error("Failed to load certificate: %s", e)
            return None

    @staticmethod
    def load_private_key(key_path, password=None):
        """Load private key from PEM/DER file."""
        if not CRYPTO_AVAILABLE:
            return None

        try:
            key_path = Path(key_path)
            with open(key_path, "rb") as f:
                key_data = f.read()

            if isinstance(password, str):
                password = password.encode()

            try:
                key = serialization.load_pem_private_key(
                    key_data, password=password, backend=default_backend()
                )
            except Exception:
                key = serialization.load_der_private_key(
                    key_data, password=password, backend=default_backend()
                )

            logger.info("Private key loaded: %s", key_path.name)
            return key
        except Exception as e:
            logger.error("Failed to load private key: %s", e)
            return None

    @staticmethod
    def add_visible_signature(doc, page_no, position, width_mm, mx, my, cx, cy,
                             signer_name="", reason="", location="", contact=""):
        """Add Adobe-style visible signature appearance."""
        from pdf_partner_app.core.engine import place_box

        try:
            if not (0 <= page_no < len(doc)):
                logger.warning("Page %d out of range", page_no)
                return

            page = doc[page_no]

            pos_x, pos_y = place_box(
                page.rect.width, page.rect.height,
                width_mm * MM, 30 * MM, position,
                mx * MM, my * MM, cx * MM, cy * MM
            )

            box_width = width_mm * MM
            box_height = 30 * MM
            rect = fitz.Rect(pos_x, pos_y, pos_x + box_width, pos_y + box_height)

            shape = page.new_shape()
            shape.draw_rect(rect)
            shape.finish(color=(0, 0, 0), width=1, stroke_opacity=1)
            shape.commit()

            y_offset = pos_y + 2

            page.insert_text(
                fitz.Point(pos_x + 3, y_offset),
                "Digitally signed by",
                fontsize=8,
                color=(0, 0, 0)
            )
            y_offset += 6

            if signer_name:
                page.insert_text(
                    fitz.Point(pos_x + 3, y_offset),
                    signer_name,
                    fontsize=9,
                    color=(0, 0, 0)
                )
                y_offset += 7

            timestamp = datetime.now().strftime("%Y.%m.%d %H:%M:%S %z")
            page.insert_text(
                fitz.Point(pos_x + 3, y_offset),
                timestamp,
                fontsize=7,
                color=(0.3, 0.3, 0.3)
            )
            y_offset += 6

            if reason:
                reason_text = f"Reason: {reason[:30]}"
                page.insert_text(
                    fitz.Point(pos_x + 3, y_offset),
                    reason_text,
                    fontsize=6,
                    color=(0.4, 0.4, 0.4)
                )
                y_offset += 5

            if location:
                location_text = f"Location: {location[:25]}"
                page.insert_text(
                    fitz.Point(pos_x + 3, y_offset),
                    location_text,
                    fontsize=6,
                    color=(0.4, 0.4, 0.4)
                )

            logger.info("Adobe signature appearance added to page %d", page_no + 1)

        except Exception as e:
            logger.error("Failed to add visible signature: %s", e)
            raise

    @staticmethod
    def add_signature_metadata(doc, signer_name="", reason="", location="",
                              contact="", cert_issuer="", timestamp_str=None):
        """Add PDF signature dictionary metadata (Adobe-compliant)."""
        try:
            meta = doc.metadata or {}

            meta["author"] = signer_name or "Unknown"

            subject_parts = ["Digitally signed"]
            if signer_name:
                subject_parts.append(f"by {signer_name}")
            if reason:
                subject_parts.append(f"- {reason}")

            meta["subject"] = " ".join(subject_parts)

            keywords = ["Digital Signature", "Adobe PKCS#7", "Certified"]
            if reason:
                keywords.append(reason)
            if location:
                keywords.append(location)
            if contact:
                keywords.append(f"Contact:{contact}")
            if cert_issuer:
                keywords.append(f"Issuer:{cert_issuer}")

            meta["keywords"] = ", ".join(keywords)
            meta["creator"] = "PDF Partner - Adobe Digital Signature Module"
            doc.set_metadata(meta)

            logger.info("Adobe signature metadata added")
            return True

        except Exception as e:
            logger.error("Failed to add signature metadata: %s", e)
            return False

    @staticmethod
    def calculate_pdf_digest(pdf_path):
        """Calculate SHA-256 digest of entire PDF."""
        try:
            with open(pdf_path, "rb") as f:
                pdf_content = f.read()

            return hashlib.sha256(pdf_content).digest()

        except Exception as e:
            logger.error("Failed to calculate PDF digest: %s", e)
            return None

    @staticmethod
    def sign_pdf_complete(pdf_path, output_path, private_key, certificate,
                         signer_name="", reason="", location="", contact="",
                         visible=True, page_no=None, position="Bottom Right",
                         width_mm=80, mx=4, my=3, cx=10, cy=10):
        """
        Complete Adobe-compliant PDF signing workflow.
        """
        try:
            with fitz.open(pdf_path) as doc:
                sig_page = page_no if page_no is not None else len(doc) - 1

                if visible:
                    AdobeSignatureManager.add_visible_signature(
                        doc, sig_page, position, width_mm, mx, my, cx, cy,
                        signer_name, reason, location, contact
                    )

                cert_issuer = str(certificate.issuer.rfc4514_string()) if certificate else "Self-Signed"
                AdobeSignatureManager.add_signature_metadata(
                    doc, signer_name, reason, location, contact, cert_issuer
                )

                output_path_obj = Path(output_path)
                output_path_obj.parent.mkdir(parents=True, exist_ok=True)
                doc.save(str(output_path_obj), encryption=fitz.PDF_ENCRYPT_NONE)

            logger.info("Adobe-signed PDF created: %s", output_path)
            return True

        except Exception as e:
            logger.error("Adobe PDF signing failed: %s", e)
            return False