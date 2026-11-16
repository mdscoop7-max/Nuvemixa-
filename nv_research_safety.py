"""Check exact product barcodes against recent public EU Safety Gate reports."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
import re
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

import requests


ROOT = "https://ec.europa.eu/safety-gate-alerts"
REPORTS = ROOT + "/api/download/weeklyReport/list/xml/en"
LIMIT = 4


def gtin(value):
    code = str(value or "").strip()
    if len(code) not in (8, 12, 13, 14) or not re.fullmatch(r"[0-9]+", code):
        return None
    total = sum(int(n) * (3 if index % 2 == 0 else 1) for index, n in enumerate(reversed(code[:-1])))
    return code.zfill(14) if total > 0 and (total + int(code[-1])) % 10 == 0 else None


def xml_document(raw):
    if re.search(br"<!\s*(?:DOCTYPE|ENTITY)", raw, re.I):
        raise ValueError("Unexpected XML declaration")
    return ET.fromstring(raw)


def read_report(read, fetch, report, codes):
    url = urlsplit(report.findtext("URL", ""))
    match = re.fullmatch(r"/safety-gate-alerts/api/download/weeklyReport/detail/xml/([0-9]+)", url.path)
    if (url.scheme, url.netloc) != ("https", "ec.europa.eu") or not match:
        raise ValueError("Unexpected Safety Gate report URL")
    report_id = match[1]
    params = {"language": "en", "search": f"WEB_REPORT|:|{report_id},"}
    body = xml_document(read(fetch, "https://ec.europa.eu" + url.path, params, max_bytes=2_000_000))
    if body.tag != "Safety-Gate":
        raise ValueError("Unexpected Safety Gate report")
    matches = {}
    for notice in body.findall("notifications"):
        observed_codes = {gtin(value) for value in re.findall(r"\b[0-9]{8,14}\b", notice.findtext("barcode", ""))}
        matching = codes & observed_codes
        if not matching:
            continue
        source = notice.findtext("reference", "")
        if not re.fullmatch(re.escape(ROOT) + r"/screen/webReport/alertDetail/[0-9]+", source):
            continue
        try:
            published = datetime.strptime(notice.findtext("publicationDate", ""), "%d-%m-%Y").date()
        except ValueError:
            continue
        if published > date.today():
            continue
        alert = {
            "url": source, "date": published.isoformat(), "number": notice.findtext("caseNumber", "")[:30],
            "risk": notice.findtext("riskType", "")[:120], "batch_limited": bool(
                notice.findtext("batchNumber", "").strip() or notice.findtext("productionDates", "").strip()
            ),
        }
        for code in matching:
            matches[code] = alert
    return matches


def recent_alerts(fetch, read, codes):
    index = xml_document(read(fetch, REPORTS, {}, max_bytes=1_500_000))
    if index.tag != "Safety-Gate":
        raise ValueError("Unexpected Safety Gate index")
    weeks = index.findall("weeklyReport")[:LIMIT]
    results = {}
    checked = 0
    with ThreadPoolExecutor(max_workers=LIMIT) as pool:
        for future in [pool.submit(read_report, read, fetch, report, codes) for report in weeks]:
            try:
                for code, alert in future.result().items():
                    results.setdefault(code, alert)
                checked += 1
            except (requests.RequestException, ET.ParseError, ValueError, OSError):
                continue
    return results, checked
