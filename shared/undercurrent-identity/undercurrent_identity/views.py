"""Routes under /auth: sign-in, invite and recovery links, account page,
and the JSON endpoints the passkey ceremonies call.

Every POST must come from an allowed origin (this domain or a subdomain):
the session cookie is SameSite=Lax, and this Origin check covers the
cross-subdomain case Lax doesn't."""
from __future__ import annotations

import json
from urllib.parse import urlparse

from flask import Blueprint, abort, jsonify, redirect, render_template, request
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .tokens import hash_token


def _safe_next(value: str | None) -> str:
    """Only same-site relative paths, so a link can't bounce people elsewhere."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/"
    return value


def make_blueprint(identity) -> Blueprint:
    bp = Blueprint(
        "undercurrent_identity",
        __name__,
        url_prefix="/auth",
        template_folder="templates",
        static_folder="static",
        static_url_path="/static",
    )
    store = identity.store

    @bp.before_request
    def _check_origin():
        if request.method == "POST":
            origin = request.headers.get("Origin")
            if origin is None and request.headers.get("Referer"):
                ref = urlparse(request.headers["Referer"])
                origin = f"{ref.scheme}://{ref.netloc}"
            if not identity.allowed_origin(origin):
                abort(403)

    def json_error(message, status=400):
        return jsonify({"error": message}), status

    def page(template, **ctx):
        from . import app_label

        return render_template(
            f"undercurrent_identity/{template}", app_name=identity.app_name, app_label=app_label, **ctx
        )

    def signed_in_response(user_id: str, next_path: str):
        token = store.create_session(user_id, request.headers.get("User-Agent"))
        response = jsonify({"ok": True, "next": _safe_next(next_path)})
        identity.set_session_cookie(response, token)
        return response

    def origin_or_400():
        origin = request.headers.get("Origin")
        if not identity.allowed_origin(origin):
            abort(403)
        return origin

    # --- pages ------------------------------------------------------------
    @bp.get("/sign-in")
    def sign_in_page():
        return page("sign_in.html", next=_safe_next(request.args.get("next")), user=identity.current_user())

    @bp.get("/invite/<token>")
    @bp.get("/recover/<token>")
    def link_page(token):
        link = store.link_usable(token)
        kind = "invite" if request.path.startswith("/auth/invite/") else "recovery"
        if link is None or link.kind != kind:
            return page("link_invalid.html"), 410
        existing = store.get_user_by_email(link.email)
        return page("link.html", token=token, link=link, existing=existing)

    @bp.get("/account")
    def account_page():
        user = identity.current_user()
        if user is None:
            return redirect(identity.sign_in_url("/auth/account"))
        return page("account.html", user=user, passkeys=store.passkeys_for(user.id))

    @bp.post("/sign-out")
    def sign_out():
        token = request.cookies.get("uc_session")
        if token:
            store.end_session(token)
        if request.form.get("everywhere") and identity.current_user():
            store.end_all_sessions(identity.current_user().id)
        response = redirect(_safe_next(request.form.get("next")))
        identity.clear_session_cookie(response)
        return response

    # --- sign in (authentication ceremony) --------------------------------
    @bp.post("/api/sign-in/begin")
    def sign_in_begin():
        options = generate_authentication_options(
            rp_id=identity.rp_id, user_verification=UserVerificationRequirement.PREFERRED
        )
        cid = store.save_challenge("authenticate", options.challenge)
        return jsonify({"challenge_id": cid, "options": json.loads(options_to_json(options))})

    @bp.post("/api/sign-in/finish")
    def sign_in_finish():
        origin = origin_or_400()
        body = request.get_json(silent=True) or {}
        row = store.pop_challenge(str(body.get("challenge_id", "")), "authenticate")
        credential = body.get("credential")
        if row is None or not isinstance(credential, dict):
            return json_error("That sign-in attempt expired. Try again.")
        passkey = store.get_passkey(str(credential.get("id", "")))
        if passkey is None:
            return json_error("This passkey isn't registered with Undercurrent.", 401)
        try:
            verified = verify_authentication_response(
                credential=credential,
                expected_challenge=row.challenge,
                expected_rp_id=identity.rp_id,
                expected_origin=origin,
                credential_public_key=passkey.public_key,
                credential_current_sign_count=passkey.sign_count,
            )
        except InvalidAuthenticationResponse:
            return json_error("That passkey couldn't be verified.", 401)
        user = store.get_user(passkey.user_id)
        if user is None or user.disabled:
            return json_error("This account is disabled.", 403)
        store.touch_passkey(passkey.credential_id, verified.new_sign_count)
        return signed_in_response(user.id, body.get("next"))

    # --- registration (invite link, recovery link, or add a passkey) --------
    @bp.post("/api/register/begin")
    def register_begin():
        body = request.get_json(silent=True) or {}
        token = body.get("token")
        display_name = (body.get("display_name") or "").strip()[:120] or None
        link_hash = None
        if token:
            link = store.link_usable(str(token))
            if link is None:
                return json_error("This link has already been used or has expired.", 410)
            link_hash = hash_token(str(token))
            existing = store.get_user_by_email(link.email)
            user_id = existing.id if existing else None
            email = link.email
            name = (existing.display_name if existing else display_name) or email.split("@")[0]
        else:
            user = identity.current_user()
            if user is None:
                return json_error("Sign in first.", 401)
            user_id, email, name = user.id, user.email, user.display_name
        # WebAuthn needs a stable user handle; new users get theirs now and
        # keep it (it's stored with the challenge and becomes users.id).
        from .tokens import new_id

        handle = user_id or new_id()
        exclude = [
            PublicKeyCredentialDescriptor(id=_b64d(p.credential_id))
            for p in (store.passkeys_for(user_id) if user_id else [])
        ]
        options = generate_registration_options(
            rp_id=identity.rp_id,
            rp_name=identity.rp_name,
            user_id=handle.encode(),
            user_name=email,
            user_display_name=name,
            exclude_credentials=exclude,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.REQUIRED,
                user_verification=UserVerificationRequirement.PREFERRED,
            ),
        )
        cid = store.save_challenge(
            "register", options.challenge, user_id=handle, link_hash=link_hash, display_name=display_name
        )
        return jsonify({"challenge_id": cid, "options": json.loads(options_to_json(options))})

    @bp.post("/api/register/finish")
    def register_finish():
        origin = origin_or_400()
        body = request.get_json(silent=True) or {}
        row = store.pop_challenge(str(body.get("challenge_id", "")), "register")
        credential = body.get("credential")
        if row is None or not isinstance(credential, dict):
            return json_error("That attempt expired. Try again.")
        if row.link_hash is None:
            user = identity.current_user()
            if user is None or user.id != row.user_id:
                return json_error("Sign in first.", 401)
        try:
            verified = verify_registration_response(
                credential=credential,
                expected_challenge=row.challenge,
                expected_rp_id=identity.rp_id,
                expected_origin=origin,
            )
        except InvalidRegistrationResponse:
            return json_error("That passkey couldn't be verified.", 400)
        transports = credential.get("response", {}).get("transports") or []
        try:
            user_id = store.complete_registration(
                link_token_hash=row.link_hash,
                user_id=row.user_id,
                display_name=row.display_name,
                credential_id=bytes_to_base64url(verified.credential_id),
                public_key=verified.credential_public_key,
                sign_count=verified.sign_count,
                transports=",".join(str(t) for t in transports)[:200] or None,
                passkey_name=(body.get("passkey_name") or _device_name()).strip(),
                backed_up=bool(verified.credential_backed_up),
            )
        except ValueError as exc:
            return json_error(str(exc), 410)
        except Exception:  # e.g. the same passkey registered twice
            return json_error("That passkey is already registered.", 409)
        if row.link_hash is None:
            return jsonify({"ok": True, "next": "/auth/account"})
        return signed_in_response(user_id, body.get("next") or "/")

    @bp.post("/api/passkeys/delete")
    def delete_passkey():
        user = identity.current_user()
        if user is None:
            return json_error("Sign in first.", 401)
        cred = str((request.get_json(silent=True) or {}).get("credential_id", ""))
        if not store.delete_passkey(user.id, cred):
            return json_error("You can't remove your only passkey.", 400)
        return jsonify({"ok": True})

    return bp


def _b64d(value: str) -> bytes:
    from webauthn.helpers import base64url_to_bytes

    return base64url_to_bytes(value)


def _device_name() -> str:
    ua = request.headers.get("User-Agent", "")
    for needle, name in (("iPad", "iPad"), ("iPhone", "iPhone"), ("Android", "Android"), ("Macintosh", "Mac"),
                         ("Windows", "Windows PC"), ("Linux", "Linux")):
        if needle in ua:
            return f"Passkey on {name}"
    return "Passkey"
