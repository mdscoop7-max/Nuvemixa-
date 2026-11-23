"""Prepared SMTP adapter. Never sends test messages and never runs automatically."""
import os,re,ssl,smtplib
from email.message import EmailMessage
import nv_store as store

def enabled():
    return (os.getenv('NUVEMIXA_ENV')=='production'
            and os.getenv('NUVEMIXA_ENABLE_EXTERNAL_MAIL')=='true'
            and os.getenv('NUVEMIXA_MAIL_DOMAIN_VERIFIED')=='true'
            and bool(re.fullmatch(r'https://[A-Za-z0-9.-]+(?::[0-9]+)?',os.getenv('SITE_URL','').rstrip('/')))
            and bool(os.getenv('NUVEMIXA_SMTP_HOST'))
            and bool(os.getenv('NUVEMIXA_SMTP_USERNAME'))
            and bool(os.getenv('NUVEMIXA_SMTP_PASSWORD'))
            and bool(os.getenv('NUVEMIXA_MAIL_FROM')))

def dispatch(id):
    """Explicit operator action, only after separate mail acceptance.

    A 'sending' message needs manual reconciliation after an ambiguous SMTP error;
    it is never blindly retried, since SMTP has no exactly-once guarantee.
    """
    if not enabled():raise RuntimeError('external_mail_disabled')
    with store.db(True) as c:
        row=c.execute('SELECT * FROM nv_mail WHERE id=?',(id,)).fetchone()
        if not row or row['status']!='pending':raise ValueError('test_or_nonpending_message_never_sent')
        sender=os.environ['NUVEMIXA_MAIL_FROM'];recipient=row['recipient']
        valid=r'[^@\s\r\n]{1,64}@[^@\s\r\n]{1,185}\.[^@\s\r\n]{2,}'
        if not re.fullmatch(valid,sender) or not re.fullmatch(valid,recipient) or recipient.endswith('.invalid'):raise ValueError('invalid_mail_address')
        message=EmailMessage();message['From']='NUVEMIXA <'+sender+'>';message['To']=recipient;message['Subject']=row['subject'];message['Message-ID']='<'+row['id']+'@'+sender.split('@')[1]+'>';message.set_content(row['body'])
        c.execute("UPDATE nv_mail SET status='sending' WHERE id=? AND status='pending'",(id,))
    try:
        with smtplib.SMTP(os.environ['NUVEMIXA_SMTP_HOST'],int(os.getenv('NUVEMIXA_SMTP_PORT','587')),timeout=15) as smtp:
            smtp.ehlo();smtp.starttls(context=ssl.create_default_context());smtp.ehlo()
            smtp.login(os.environ['NUVEMIXA_SMTP_USERNAME'],os.environ['NUVEMIXA_SMTP_PASSWORD']);smtp.send_message(message)
    except Exception as exc:
        raise RuntimeError('mail_delivery_unconfirmed_manual_review_required') from None
    with store.db(True) as c:c.execute("UPDATE nv_mail SET status='sent' WHERE id=? AND status='sending'",(id,))
    return True
