import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from .builder import build_email_context

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def render_email(context: dict) -> tuple[str, str]:
    html = _jinja_env.get_template("digest.html").render(**context)
    text = _jinja_env.get_template("digest.txt").render(**context)
    return html, text


def send_email_raw(config, subject: str, html: str, text: str,
                   recipients: list[str]) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{config.from_name} <{config.from_email}>"
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30) as server:
        server.ehlo()
        if config.smtp_port in (587, 465):
            server.starttls()
        if config.smtp_user and config.smtp_password:
            server.login(config.smtp_user, config.smtp_password)
        server.sendmail(config.from_email, recipients, msg.as_string())


def send_digest_if_configured(tenant_id: int, articles,
                               frequency: str, db: Session) -> bool:
    context = build_email_context(tenant_id, articles, frequency, db)
    if not context:
        return False

    config = context["config"]
    if config.frequency != frequency and frequency != "immediate":
        return False

    html, text = render_email(context)
    try:
        send_email_raw(
            config=config,
            subject=context["subject"],
            html=html,
            text=text,
            recipients=context["recipients"],
        )
        logger.info("Email sent to %s for tenant %d", context["recipients"], tenant_id)
        return True
    except Exception as exc:
        logger.error("Email send failed for tenant %d: %s", tenant_id, exc)
        raise
