import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from .config import Config
from .data_store import get_massive_scan_run_history

logger = logging.getLogger(__name__)


def _build_cve_alert_lines(registry_name, scan_result):
    summary = scan_result.get("runSummary") or scan_result or {}
    if summary.get("dryRun"):
        return []

    history = get_massive_scan_run_history(registry_name, limit=2)
    if len(history) < 2:
        return []

    prev_summary = history[1]
    prev_critical = int(prev_summary.get("critical", 0) or 0)
    prev_high = int(prev_summary.get("high", 0) or 0)
    curr_critical = int(summary.get("critical", 0) or 0)
    curr_high = int(summary.get("high", 0) or 0)
    diff_critical = curr_critical - prev_critical
    diff_high = curr_high - prev_high

    lines = []
    if diff_critical > 0:
        lines.append(
            f"Alert: Critical CVE increased from {prev_critical} to {curr_critical} (+{diff_critical})"
        )
    if diff_high > 0:
        lines.append(
            f"Alert: High CVE increased from {prev_high} to {curr_high} (+{diff_high})"
        )
    return lines


def _build_recap_text(registry_name, scan_result):
    summary = scan_result.get("runSummary") or scan_result

    scanned = summary.get("scanned", scan_result.get("scanned", 0))
    skipped = summary.get("skipped", scan_result.get("skipped", 0))
    errors = summary.get("errors", scan_result.get("errors", 0))
    total_images = summary.get("totalImages", 0)
    total_tags = summary.get("totalTags", 0)
    total_scans = summary.get("totalScans", scanned)
    critical = summary.get("critical", 0)
    high = summary.get("high", 0)
    medium = summary.get("medium", 0)
    low = summary.get("low", 0)
    alert_lines = _build_cve_alert_lines(registry_name, scan_result)

    alert_block = ""
    if alert_lines:
        alert_block = "".join(f"{line}\n" for line in alert_lines)

    return (
        "Massive scan recap\n"
        f"Registry: {registry_name}\n"
        f"Totals: images {total_images}, tags {total_tags}, scans {total_scans}\n"
        f"Severities: C {critical} · H {high} · M {medium} · L {low}\n"
        f"Execution: scanned {scanned}, skipped {skipped}, errors {errors}\n"
        f"{alert_block}"
    )


def _build_top_risk_repositories(scan_result):
    repo_risk = {}

    for entry in scan_result.get("results", []):
        if entry.get("status") != "success":
            continue

        repo = entry.get("repo")
        if not repo:
            continue

        row = repo_risk.setdefault(
            repo,
            {
                "repo": repo,
                "scannedTags": 0,
                "vulnerableTags": 0,
                "critical": 0,
                "high": 0,
                "total": 0,
            },
        )

        row["scannedTags"] += 1
        result = entry.get("result") or {}
        summary = result.get("summary") or {}
        critical = int(summary.get("CRITICAL", 0) or 0)
        high = int(summary.get("HIGH", 0) or 0)
        total = int(result.get("total", 0) or 0)

        row["critical"] += critical
        row["high"] += high
        row["total"] += total
        if total > 0:
            row["vulnerableTags"] += 1

    return sorted(
        repo_risk.values(),
        key=lambda r: (r["critical"], r["high"], r["total"]),
        reverse=True,
    )[:10]


def _build_email_html(registry_name, scan_result):
    recap = _build_recap_text(registry_name, scan_result).strip().split("\n")
    top_risk_rows = _build_top_risk_repositories(scan_result)

    table_header = (
        "<tr>"
        "<th align='left'>Repository</th>"
        "<th align='right'>Scanned Tags</th>"
        "<th align='right'>Vulnerable Tags</th>"
        "<th align='right'>Critical</th>"
        "<th align='right'>High</th>"
        "<th align='right'>Total</th>"
        "</tr>"
    )

    table_rows = "".join(
        (
            "<tr>"
            f"<td>{row['repo']}</td>"
            f"<td align='right'>{row['scannedTags']}</td>"
            f"<td align='right'>{row['vulnerableTags']}</td>"
            f"<td align='right'>{row['critical']}</td>"
            f"<td align='right'>{row['high']}</td>"
            f"<td align='right'>{row['total']}</td>"
            "</tr>"
        )
        for row in top_risk_rows
    )

    no_data_row = (
        "<tr><td colspan='6' align='center'>No scan results available.</td></tr>"
        if not table_rows
        else ""
    )

    recap_html = "".join(f"<p style='margin:0 0 6px 0'>{line}</p>" for line in recap)

    return (
        "<html><body style='font-family: Arial, sans-serif; font-size: 14px; color: #1f2937;'>"
        f"{recap_html}"
        "<p style='margin:16px 0 8px 0; font-weight: 600;'>Top 10 Risk Repositories</p>"
        "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse: collapse; width: 100%;'>"
        f"{table_header}{table_rows}{no_data_row}"
        "</table>"
        "</body></html>"
    )


def _build_email_text(registry_name, scan_result):
    top_risk_rows = _build_top_risk_repositories(scan_result)
    lines = [
        _build_recap_text(registry_name, scan_result).rstrip(),
        "",
        "Top 10 Risk Repositories",
        "Repository\tScanned Tags\tVulnerable Tags\tCritical\tHigh\tTotal",
    ]

    for row in top_risk_rows:
        lines.append(
            f"{row['repo']}\t{row['scannedTags']}\t{row['vulnerableTags']}\t{row['critical']}\t{row['high']}\t{row['total']}"
        )

    if not top_risk_rows:
        lines.append("No scan results available.")

    return "\n".join(lines) + "\n"


def send_email_recap(registry_name, scan_result):
    if not Config.NOTIFY_EMAIL_ENABLED:
        return False

    missing = [
        key
        for key in ["NOTIFY_EMAIL_SMTP_HOST", "NOTIFY_EMAIL_TO", "NOTIFY_EMAIL_FROM"]
        if not getattr(Config, key)
    ]
    if missing:
        logger.warning(
            f"Email recap disabled due to missing config: {', '.join(missing)}"
        )
        return False

    body_text = _build_email_text(registry_name, scan_result)
    body_html = _build_email_html(registry_name, scan_result)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Registry UI] Massive scan recap - {registry_name}"
    msg["From"] = Config.NOTIFY_EMAIL_FROM
    msg["To"] = Config.NOTIFY_EMAIL_TO
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(
            Config.NOTIFY_EMAIL_SMTP_HOST, Config.NOTIFY_EMAIL_SMTP_PORT, timeout=20
        ) as server:
            if Config.NOTIFY_EMAIL_USE_TLS:
                server.starttls()
            if Config.NOTIFY_EMAIL_SMTP_USER:
                server.login(
                    Config.NOTIFY_EMAIL_SMTP_USER,
                    Config.NOTIFY_EMAIL_SMTP_PASSWORD or "",
                )
            server.sendmail(
                Config.NOTIFY_EMAIL_FROM, [Config.NOTIFY_EMAIL_TO], msg.as_string()
            )
        logger.info(f"Massive scan email recap sent for {registry_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email recap for {registry_name}: {e}")
        return False


def send_telegram_recap(registry_name, scan_result):
    if not Config.NOTIFY_TELEGRAM_ENABLED:
        return False
    if not Config.NOTIFY_TELEGRAM_BOT_TOKEN or not Config.NOTIFY_TELEGRAM_CHAT_ID:
        logger.warning("Telegram recap disabled due to missing token/chat id")
        return False

    body = _build_recap_text(registry_name, scan_result)
    url = f"https://api.telegram.org/bot{Config.NOTIFY_TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": Config.NOTIFY_TELEGRAM_CHAT_ID,
        "text": body,
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code >= 300:
            logger.error(
                f"Failed to send Telegram recap for {registry_name}: HTTP {response.status_code}"
            )
            return False
        logger.info(f"Massive scan Telegram recap sent for {registry_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram recap for {registry_name}: {e}")
        return False


def send_massive_scan_recap(registry_name, scan_result):
    # If configured to only send on delta > 0, check for positive changes
    if Config.NOTIFY_ONLY_IF_DELTA_GT_0:
        alert_lines = _build_cve_alert_lines(registry_name, scan_result)
        if not alert_lines:
            logger.info(f"Skipping notifications for {registry_name}: no positive delta")
            return {"email": False, "telegram": False}
    email_ok = send_email_recap(registry_name, scan_result)
    telegram_ok = send_telegram_recap(registry_name, scan_result)
    return {"email": email_ok, "telegram": telegram_ok}
