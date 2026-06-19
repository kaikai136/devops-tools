import base64
import hashlib
import io
import time

import pyotp
import qrcode


def normalize_totp_algorithm(value: str) -> str:
    normalized = value.replace("-", "").upper()
    if normalized not in {"SHA1", "SHA256", "SHA512"}:
        raise ValueError("TOTP 算法仅支持 SHA-1、SHA-256、SHA-512")
    return normalized


def normalize_totp_secret(secret: str) -> str:
    value = secret.replace(" ", "").replace("-", "").upper()
    if not value:
        raise ValueError("请输入 Base32 密钥")
    pyotp.TOTP(value).now()
    return value


def build_totp_uri(entry) -> str:
    return pyotp.totp.TOTP(
        entry.secret,
        digits=entry.digits,
        interval=entry.period,
        digest=totp_digest(entry.algorithm),
    ).provisioning_uri(name=entry.account_name or "Authenticator", issuer_name=entry.issuer or None)


def generate_totp(entry) -> dict:
    totp = pyotp.TOTP(entry.secret, digits=entry.digits, interval=entry.period, digest=totp_digest(entry.algorithm))
    now = int(time.time())
    remaining = entry.period - (now % entry.period)
    return {
        "code": totp.now(),
        "remaining_seconds": remaining,
        "period": entry.period,
    }


def totp_digest(algorithm: str):
    return {
        "SHA1": hashlib.sha1,
        "SHA256": hashlib.sha256,
        "SHA512": hashlib.sha512,
    }[normalize_totp_algorithm(algorithm)]


def generate_qr_data_url(text: str) -> str:
    image = qrcode.make(text)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
