/* Undercurrent identity: passkey ceremonies for the /auth pages.
 * The server sends WebAuthn options as JSON (base64url for binary fields);
 * this converts them for navigator.credentials and posts the result back. */
(function () {
  "use strict";

  function b64urlToBuf(s) {
    s = s.replace(/-/g, "+").replace(/_/g, "/");
    while (s.length % 4) s += "=";
    var bin = atob(s), out = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out.buffer;
  }
  function bufToB64url(buf) {
    var bytes = new Uint8Array(buf), bin = "";
    for (var i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) {
        if (!r.ok) throw new Error(data.error || "Something went wrong (" + r.status + ").");
        return data;
      });
    });
  }

  function status(el, text, kind) {
    var s = el.parentNode.querySelector(".uc-auth__status");
    if (s) { s.textContent = text || ""; s.dataset.kind = kind || ""; }
  }

  function friendly(err) {
    if (err && err.name === "NotAllowedError") return "Cancelled, or the passkey wasn't available. Try again.";
    if (err && err.name === "InvalidStateError") return "This device already has a passkey for your account.";
    return (err && err.message) || "Something went wrong.";
  }

  function credentialJSON(cred) {
    var r = cred.response, out = {
      id: cred.id,
      rawId: bufToB64url(cred.rawId),
      type: cred.type,
      clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {},
      authenticatorAttachment: cred.authenticatorAttachment || undefined,
      response: { clientDataJSON: bufToB64url(r.clientDataJSON) },
    };
    if (r.attestationObject) {
      out.response.attestationObject = bufToB64url(r.attestationObject);
      if (r.getTransports) out.response.transports = r.getTransports();
    } else {
      out.response.authenticatorData = bufToB64url(r.authenticatorData);
      out.response.signature = bufToB64url(r.signature);
      if (r.userHandle) out.response.userHandle = bufToB64url(r.userHandle);
    }
    return out;
  }

  function signIn(btn) {
    btn.disabled = true; status(btn, "Waiting for your passkey…");
    post("/auth/api/sign-in/begin").then(function (begin) {
      var o = begin.options;
      o.challenge = b64urlToBuf(o.challenge);
      (o.allowCredentials || []).forEach(function (c) { c.id = b64urlToBuf(c.id); });
      return navigator.credentials.get({ publicKey: o }).then(function (cred) {
        return post("/auth/api/sign-in/finish", {
          challenge_id: begin.challenge_id, credential: credentialJSON(cred), next: btn.dataset.next,
        });
      });
    }).then(function (done) { window.location.assign(done.next || "/"); })
      .catch(function (err) { status(btn, friendly(err), "error"); btn.disabled = false; });
  }

  function register(btn) {
    var nameInput = document.getElementById("uc-display-name");
    btn.disabled = true; status(btn, "Follow the prompts on your device…");
    post("/auth/api/register/begin", {
      token: btn.dataset.token || null,
      display_name: nameInput ? nameInput.value : null,
    }).then(function (begin) {
      var o = begin.options;
      o.challenge = b64urlToBuf(o.challenge);
      o.user.id = b64urlToBuf(o.user.id);
      (o.excludeCredentials || []).forEach(function (c) { c.id = b64urlToBuf(c.id); });
      return navigator.credentials.create({ publicKey: o }).then(function (cred) {
        return post("/auth/api/register/finish", {
          challenge_id: begin.challenge_id, credential: credentialJSON(cred), next: btn.dataset.next,
        });
      });
    }).then(function (done) { window.location.assign(done.next || "/"); })
      .catch(function (err) { status(btn, friendly(err), "error"); btn.disabled = false; });
  }

  document.addEventListener("click", function (e) {
    var el = e.target.closest("[data-uc-sign-in], [data-uc-register], [data-uc-delete-passkey]");
    if (!el) return;
    if (!window.PublicKeyCredential) { status(el, "This browser doesn't support passkeys.", "error"); return; }
    if (el.hasAttribute("data-uc-sign-in")) signIn(el);
    else if (el.hasAttribute("data-uc-register")) register(el);
    else if (window.confirm("Remove this passkey? You won't be able to sign in with it again.")) {
      post("/auth/api/passkeys/delete", { credential_id: el.dataset.ucDeletePasskey })
        .then(function () { window.location.reload(); })
        .catch(function (err) { window.alert(friendly(err)); });
    }
  });
})();
