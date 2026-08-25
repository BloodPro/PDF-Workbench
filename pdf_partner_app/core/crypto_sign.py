"""Cryptographic PDF Digital Signing Engine for PDF Partner (Solution 1 & Solution 2)."""

import os
import sys
import logging
from pathlib import Path

from pdf_partner_app.utils.config import logger

try:
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.hazmat.primitives import hashes
    CRYPTOGRAPHY_AVAILABLE = True
except Exception:
    CRYPTOGRAPHY_AVAILABLE = False

try:
    import pyhanko
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields, signers, pkcs11
    PYHANKO_AVAILABLE = True
except Exception:
    PYHANKO_AVAILABLE = False


COMMON_PKCS11_DRIVERS = [
    # ePass2003 / HYP2003
    r"C:\Windows\System32\eps2003csp11.dll",
    r"C:\Windows\System32\eps2003csp11_v2.dll",
    # Watchdata / ProxKey
    r"C:\Windows\System32\Watchdata\Watchdata PKCS11 v1.0\WDPKCS.dll",
    r"C:\Windows\System32\wdpkcs.dll",
    # SafeNet / Oberthur / Akis
    r"C:\Windows\System32\eTPKCS11.dll",
    r"C:\Windows\System32\akisp11.dll",
]


def detect_usb_token_drivers():
    """Returns a list of detected PKCS#11 DLL driver paths on Windows machines."""
    found = []
    if sys.platform == "win32":
        for drv in COMMON_PKCS11_DRIVERS:
            if Path(drv).exists():
                found.append(drv)
    return found


def sign_pdf_with_pfx(
    pdf_in,
    pdf_out,
    pfx_path,
    passphrase,
    reason="Digital Legal Signature",
    location="Court / Tribunal",
    page=0,
    rect=None,
):
    """Solution 1: Cryptographic Digital Signing via PFX / P12 Soft Certificate."""
    if not PYHANKO_AVAILABLE:
        raise RuntimeError("pyHanko library is required for cryptographic PDF digital signing.")

    pfx_p = Path(pfx_path)
    if not pfx_p.exists():
        raise FileNotFoundError(f"Certificate file not found: {pfx_path}")

    signer = signers.load_crypto_backend().load_cert_from_pfx(
        str(pfx_p), passphrase.encode("utf-8") if passphrase else None
    )

    with open(pdf_in, "rb") as inf:
        w = IncrementalPdfFileWriter(inf)
        sig_field_name = "DigitalSignature1"

        if rect:
            fields.append_signature_field(
                w,
                sig_field_spec=fields.SigFieldSpec(
                    sig_field_name=sig_field_name,
                    on_page=page,
                    box=rect,
                ),
            )
        else:
            fields.append_signature_field(
                w,
                sig_field_spec=fields.SigFieldSpec(
                    sig_field_name=sig_field_name,
                ),
            )

        meta = signers.PdfSignatureMetadata(
            field_name=sig_field_name,
            reason=reason,
            location=location,
        )
        pdf_signer = signers.PdfSigner(meta, signer=signer)

        with open(pdf_out, "wb") as outf:
            pdf_signer.sign_pdf(w, output=outf)

    logger.info("Successfully digitally signed PDF with PFX: %s", pdf_out)
    return pdf_out


def sign_pdf_with_pkcs11(
    pdf_in,
    pdf_out,
    dll_path,
    slot_pin,
    key_label=None,
    reason="Digital Hardware Signature",
    location="Court / Tribunal",
    page=0,
    rect=None,
):
    """Solution 2: Cryptographic Digital Signing via Hardware USB Token (PKCS#11 Driver)."""
    if not PYHANKO_AVAILABLE:
        raise RuntimeError("pyHanko library is required for USB token digital signing.")

    dll_p = Path(dll_path)
    if not dll_p.exists():
        raise FileNotFoundError(f"PKCS#11 Driver DLL not found: {dll_path}")

    cms_signer = pkcs11.PKCS11SigningContext(
        pkcs11_lib=str(dll_p),
        pin=slot_pin,
        key_label=key_label,
    )

    with open(pdf_in, "rb") as inf:
        w = IncrementalPdfFileWriter(inf)
        sig_field_name = "DigitalTokenSignature1"

        if rect:
            fields.append_signature_field(
                w,
                sig_field_spec=fields.SigFieldSpec(
                    sig_field_name=sig_field_name,
                    on_page=page,
                    box=rect,
                ),
            )
        else:
            fields.append_signature_field(
                w,
                sig_field_spec=fields.SigFieldSpec(
                    sig_field_name=sig_field_name,
                ),
            )

        meta = signers.PdfSignatureMetadata(
            field_name=sig_field_name,
            reason=reason,
            location=location,
        )
        pdf_signer = signers.PdfSigner(meta, signer=cms_signer)

        with open(pdf_out, "wb") as outf:
            pdf_signer.sign_pdf(w, output=outf)

    logger.info("Successfully digitally signed PDF with Hardware USB Token: %s", pdf_out)
    return pdf_out
