
# NUVEMIXA 2026-11-20f: beveiligings-headers (HSTS 1 dag, CSP alleen in testmodus / Report-Only)
@app.after_request
def _nv_security_headers_20261120f(resp):
    try:
        h = resp.headers
        h.setdefault("Strict-Transport-Security", "max-age=86400")
        h.setdefault("Content-Security-Policy-Report-Only",
                     "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                     "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                     "font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: blob: https:; "
                     "connect-src 'self'; frame-ancestors 'self'; base-uri 'self'; object-src 'none'; form-action 'self'")
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    except Exception:
        pass
    return resp
