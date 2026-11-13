"""Test helpers: a software passkey (real ES256 signatures, so the server's
WebAuthn verification runs for real) and a shortcut to sign a test client in.
Not used by the app at runtime."""
from __future__ import annotations

import hashlib
import json
import os
import struct

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

from .store import now, users
from .tokens import new_id


class SoftPasskey:
    """One discoverable credential, like a phone's passkey."""

    def __init__(self, rp_id: str = "localhost", origin: str = "http://localhost"):
        self.rp_id = rp_id
        self.origin = origin
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(32)
        self.sign_count = 0
        self.user_handle: bytes | None = None

    def _cose_public_key(self) -> bytes:
        nums = self.key.public_key().public_numbers()
        return cbor2.dumps({1: 2, 3: -7, -1: 1, -2: nums.x.to_bytes(32, "big"), -3: nums.y.to_bytes(32, "big")})

    def _client_data(self, kind: str, challenge_b64: str, origin: str | None) -> bytes:
        return json.dumps(
            {"type": kind, "challenge": challenge_b64, "origin": origin or self.origin, "crossOrigin": False}
        ).encode()

    def create(self, options: dict, origin: str | None = None) -> dict:
        """navigator.credentials.create() for the JSON options the server sent."""
        self.user_handle = base64url_to_bytes(options["user"]["id"])
        rp_hash = hashlib.sha256(options["rp"]["id"].encode()).digest()
        flags = 0x01 | 0x04 | 0x40  # user present, verified, attested data
        auth_data = (
            rp_hash
            + bytes([flags])
            + struct.pack(">I", self.sign_count)
            + b"\x00" * 16  # aaguid
            + struct.pack(">H", len(self.credential_id))
            + self.credential_id
            + self._cose_public_key()
        )
        client_data = self._client_data("webauthn.create", options["challenge"], origin)
        att = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        cid = bytes_to_base64url(self.credential_id)
        return {
            "id": cid,
            "rawId": cid,
            "type": "public-key",
            "clientExtensionResults": {},
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "attestationObject": bytes_to_base64url(att),
                "transports": ["internal"],
            },
        }

    def get(self, options: dict, origin: str | None = None) -> dict:
        """navigator.credentials.get() for the JSON options the server sent."""
        self.sign_count += 1
        rp_hash = hashlib.sha256(options["rpId"].encode()).digest()
        auth_data = rp_hash + bytes([0x01 | 0x04]) + struct.pack(">I", self.sign_count)
        client_data = self._client_data("webauthn.get", options["challenge"], origin)
        signature = self.key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        cid = bytes_to_base64url(self.credential_id)
        return {
            "id": cid,
            "rawId": cid,
            "type": "public-key",
            "clientExtensionResults": {},
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "authenticatorData": bytes_to_base64url(auth_data),
                "signature": bytes_to_base64url(signature),
                "userHandle": bytes_to_base64url(self.user_handle or b""),
            },
        }


def create_user(identity, email: str, apps=(), display_name: str | None = None) -> str:
    """Insert a user directly (no passkey). Returns the user id."""
    uid = new_id()
    with identity.store.engine.begin() as c:
        c.execute(users.insert().values(id=uid, email=email.lower(), display_name=display_name or email.split("@")[0], created_at=now()))
    for app in apps:
        identity.store.grant(uid, app)
    return uid


def sign_in(client, identity, email: str = "owner@example.com", apps=None) -> str:
    """Sign a Flask test client in as `email` (created if needed, granted this
    app by default). Returns the user id."""
    apps = (identity.app_name,) if apps is None else apps
    user = identity.store.get_user_by_email(email)
    uid = user.id if user else create_user(identity, email, apps)
    token = identity.store.create_session(uid)
    client.set_cookie("uc_session", token)
    return uid
