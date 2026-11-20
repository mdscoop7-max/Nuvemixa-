"""Voegt Gmail-SMTP toe aan het contactformulier en een bestelmelding (alleen live bestellingen).
Wachtwoord komt ALLEEN uit omgevingsvariabele SMTP_PASSWORD (Gmail app-wachtwoord)."""
import sys, re
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
if "def nv_send_mail(" in s:
    print("al gepatcht"); sys.exit(0)

helper = '''

# --- NUVEMIXA e-mail via Gmail SMTP (wachtwoord alleen via env SMTP_PASSWORD) ---
import smtplib as _nv_smtplib
from email.message import EmailMessage as _NvEmailMessage

NV_MAIL_DEFAULT = "mdscoop7@gmail.com"


def nv_mail_configured():
    return bool(os.getenv("SMTP_PASSWORD"))


def nv_send_mail(subject, text, to=None, reply_to=None):
    """Verstuur een e-mail via SMTP. Geeft True terug als het gelukt is."""
    password = os.getenv("SMTP_PASSWORD", "").replace(" ", "")
    if not password:
        return False
    user = os.getenv("SMTP_USER", NV_MAIL_DEFAULT)
    msg = _NvEmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"NUVEMIXA <{user}>"
    msg["To"] = to or os.getenv("CONTACT_TO_EMAIL", NV_MAIL_DEFAULT)
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text)
    try:
        with _nv_smtplib.SMTP(os.getenv("SMTP_HOST", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", "587")), timeout=15) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except Exception as exc:  # nooit het wachtwoord loggen
        app.logger.error("Mail versturen mislukt: %s", type(exc).__name__)
        return False
'''
anchor = "\n@app.route(\"/contact\", methods=[\"POST\"])"
assert anchor in s
s = s.replace(anchor, helper + "\n" + anchor, 1)

old = '''    is_ajax = request.args.get("ajax") == "1" or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    api_key = os.getenv("RESEND_API_KEY")'''
new = '''    is_ajax = request.args.get("ajax") == "1" or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if nv_mail_configured():
        sent = nv_send_mail(
            f"NUVEMIXA contactformulier: {name}",
            f"Naam: {name}\\nE-mail: {email}\\n\\nBericht:\\n{message}\\n",
            reply_to=email,
        )
        if sent:
            if is_ajax:
                return Response(json.dumps({"ok": True}), mimetype="application/json")
            return redirect(url_for("contact_page") + "?status=sent")
        if is_ajax:
            return Response(json.dumps({"ok": False}), status=502, mimetype="application/json")
        return redirect(url_for("contact_page") + "?status=error")
    api_key = os.getenv("RESEND_API_KEY")'''
assert old in s
s = s.replace(old, new, 1)

old2 = '''            order, error = create_woo_order(cart, customer)
            if order:
                session.pop("trendmix_cart", None)'''
new2 = '''            order, error = create_woo_order(cart, customer)
            if order:
                try:
                    regels = "\\n".join(f"- {i.get('qty', 1)}x {i.get('name', i.get('id'))} ({i.get('price', '')})" for i in cart)
                    nv_send_mail(
                        f"Nieuwe bestelling NUVEMIXA #{order.get('id', '')}",
                        f"Nieuwe bestelling #{order.get('id', '')}\\n\\nKlant: {customer['first_name']} {customer['last_name']}\\nE-mail: {customer['email']}\\nAdres: {customer['address_1']}, {customer['postcode']} {customer['city']}, {customer['country']}\\n\\nProducten:\\n{regels}\\n\\nTotaal: {total:.2f} EUR\\n",
                        reply_to=customer["email"],
                    )
                except Exception:
                    pass
                session.pop("trendmix_cart", None)'''
assert old2 in s
s = s.replace(old2, new2, 1)
open(p, "w", encoding="utf-8").write(s)
print("gepatcht")
