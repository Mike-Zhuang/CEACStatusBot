from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP, SMTP_SSL
from typing import Any

from cryptography.fernet import InvalidToken

from .config import getSettings


def encryptSecret(value: str) -> str:
    return getSettings().getFernet().encrypt(value.encode()).decode()


def decryptSecret(value: str) -> str:
    try:
        return getSettings().getFernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("SMTP password cannot be decrypted; check ENCRYPTION_KEY") from exc


def sendEmail(
    *,
    fromEmail: str,
    toEmail: str,
    password: str,
    host: str,
    port: int,
    useSsl: bool,
    subject: str,
    body: str,
) -> None:
    msg = MIMEMultipart()
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = fromEmail
    msg["To"] = toEmail
    msg.attach(MIMEText(body, "plain", "utf-8"))

    client: SMTP | SMTP_SSL
    if useSsl:
        client = SMTP_SSL(host, port, timeout=30)
    else:
        client = SMTP(host, port, timeout=30)
        client.starttls()
    try:
        client.login(fromEmail, password)
        client.sendmail(fromEmail, [toEmail], msg.as_string())
    finally:
        client.quit()


def sendSystemEmail(toEmail: str, subject: str, body: str) -> None:
    settings = getSettings()
    if not settings.systemFromEmail or not settings.systemEmailPassword:
        print(f"[mail] System email is not configured. Subject: {subject}, To: {toEmail}")
        return
    sendEmail(
        fromEmail=settings.systemFromEmail,
        toEmail=toEmail,
        password=settings.systemEmailPassword,
        host=settings.systemSmtpHost,
        port=settings.systemSmtpPort,
        useSsl=settings.systemSmtpUseSsl,
        subject=subject,
        body=body,
    )


def sendCaseNotification(case: dict[str, Any], smtpConfig: dict[str, Any] | None, result: dict[str, Any]) -> None:
    subject = f"[CEAC] {case['application_num']} 状态更新：{result['status']}"
    body = "\n".join(
        [
            f"档案：{case['display_name']}",
            f"申请号：{case['application_num']}",
            f"状态：{result['status']}",
            f"CEAC 更新时间：{result.get('case_last_updated', '')}",
            f"签证类型：{result.get('visa_type', '')}",
            "",
            str(result.get("description", "")),
        ],
    )
    if case["sender_mode"] == "custom" and smtpConfig:
        sendEmail(
            fromEmail=smtpConfig["from_email"],
            toEmail=case["receive_email"],
            password=decryptSecret(smtpConfig["password_encrypted"]),
            host=smtpConfig["host"],
            port=int(smtpConfig["port"]),
            useSsl=bool(smtpConfig["use_ssl"]),
            subject=subject,
            body=body,
        )
        return
    sendSystemEmail(case["receive_email"], subject, body)

