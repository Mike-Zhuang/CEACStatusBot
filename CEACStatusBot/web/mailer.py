from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP, SMTP_SSL
from typing import Any

from cryptography.fernet import InvalidToken

from .config import getSettings
from .database import getConnection, utcNowIso


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
    config = getSystemSmtpConfig()
    if not config["fromEmail"] or not config["password"]:
        print(f"[mail] System email is not configured. Subject: {subject}, To: {toEmail}")
        return
    sendEmail(
        fromEmail=config["fromEmail"],
        toEmail=toEmail,
        password=config["password"],
        host=config["host"],
        port=config["port"],
        useSsl=config["useSsl"],
        subject=subject,
        body=body,
    )


def getSystemSmtpConfig() -> dict[str, Any]:
    settings = getSettings()
    with getConnection() as connection:
        row = connection.execute("SELECT * FROM system_smtp_config WHERE id = 1").fetchone()
    if row:
        return {
            "fromEmail": row["from_email"],
            "host": row["host"],
            "port": int(row["port"]),
            "useSsl": bool(row["use_ssl"]),
            "password": decryptSecret(row["password_encrypted"]),
            "source": "database",
            "isConfigured": True,
        }
    return {
        "fromEmail": settings.systemFromEmail,
        "host": settings.systemSmtpHost,
        "port": settings.systemSmtpPort,
        "useSsl": settings.systemSmtpUseSsl,
        "password": settings.systemEmailPassword,
        "source": "environment",
        "isConfigured": bool(settings.systemFromEmail and settings.systemEmailPassword),
    }


def getSystemSmtpConfigPublic() -> dict[str, Any]:
    config = getSystemSmtpConfig()
    return {
        "fromEmail": config["fromEmail"],
        "host": config["host"],
        "port": config["port"],
        "useSsl": config["useSsl"],
        "source": config["source"],
        "isConfigured": config["isConfigured"],
        "hasPassword": bool(config["password"]),
    }


def saveSystemSmtpConfig(*, fromEmail: str, host: str, port: int, useSsl: bool, password: str | None) -> dict[str, Any]:
    now = utcNowIso()
    with getConnection() as connection:
        current = connection.execute("SELECT password_encrypted FROM system_smtp_config WHERE id = 1").fetchone()
        if password:
            passwordEncrypted = encryptSecret(password)
        elif current:
            passwordEncrypted = current["password_encrypted"]
        else:
            settings = getSettings()
            if not settings.systemEmailPassword:
                raise RuntimeError("System SMTP password is required")
            passwordEncrypted = encryptSecret(settings.systemEmailPassword)
        connection.execute(
            """
            INSERT INTO system_smtp_config (id, from_email, host, port, use_ssl, password_encrypted, created_at, updated_at)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                from_email = excluded.from_email,
                host = excluded.host,
                port = excluded.port,
                use_ssl = excluded.use_ssl,
                password_encrypted = excluded.password_encrypted,
                updated_at = excluded.updated_at
            """,
            (fromEmail, host, port, int(useSsl), passwordEncrypted, now, now),
        )
    return getSystemSmtpConfigPublic()


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
