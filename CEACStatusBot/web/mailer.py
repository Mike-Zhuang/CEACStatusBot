from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP, SMTP_SSL
from typing import Any

from .config import getSettings
from .database import getConnection, utcNowIso
from .secrets import decryptSecret, encryptSecret


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
    lines = [
        f"档案：{case['display_name']}",
        f"申请号：{case['application_num']}",
        f"状态：{result['status']}",
        f"CEAC 更新时间：{result.get('case_last_updated', '')}",
        f"签证类型：{result.get('visa_type', '')}",
        "",
        str(result.get("description", "")),
    ]
    if str(result.get("status", "")).strip().lower() == "issued":
        lines.extend(
            [
                "",
                "提示：该档案已进入 Issued，系统会将自动查询频率降为每周一次。",
                "你可以登录站内档案详情页停止自动查询；如果一周内未停止，系统将自动停止该档案的自动查询并邮件通知你。",
            ],
        )
    if str(result.get("status", "")).strip().lower() in {"approved", "issued"}:
        lines.extend(
            [
                "",
                "护照预约提醒：你现在可以登录 CEACStatusBot，在该档案详情页填写 UID 或 HAL，开启 GTS 护照预约 slot 监控。",
                "系统会以 5-10 分钟随机间隔查询可预约时间，并只在发现新 slot 或 slot 时间变化时邮件通知你。",
                f"登录入口：{getSettings().appBaseUrl}",
            ],
        )
    body = "\n".join(lines)
    sendCaseEmail(case, smtpConfig, subject, body)


def sendPassportSlotNotification(
    case: dict[str, Any],
    smtpConfig: dict[str, Any] | None,
    *,
    identifierMasked: str,
    fetchedAt: str,
    slotLines: list[str],
    rawSummary: str,
) -> None:
    sendPassportSlotStatusEmail(
        case,
        smtpConfig,
        identifierMasked=identifierMasked,
        fetchedAt=fetchedAt,
        slotLines=slotLines,
        rawSummary=rawSummary,
        hasSlots=True,
        isTest=False,
    )


def sendPassportSlotStatusEmail(
    case: dict[str, Any],
    smtpConfig: dict[str, Any] | None,
    *,
    identifierMasked: str,
    fetchedAt: str,
    slotLines: list[str],
    rawSummary: str,
    hasSlots: bool,
    isTest: bool = False,
) -> None:
    subject = f"[GTS] 发现可预约时间：{case['display_name']}"
    if isTest:
        subject = f"[GTS] 护照预约监控测试：{case['display_name']}"
    lines = [
        f"档案：{case['display_name']}",
        f"申请号：{case['application_num']}",
        f"UID/HAL：{identifierMasked}",
        f"查询时间：{fetchedAt}",
        "",
        "当前可预约时间：" if hasSlots else "当前状态：暂无可预约时间",
    ]
    if hasSlots:
        lines.extend(slotLines or ["接口返回了可用 slot，但未能解析为标准日期字段，请查看下方原始摘要。"])
    elif isTest:
        lines.append("这是一封测试邮件，用于确认护照预约监控的发信配置可用。")
    if rawSummary:
        lines.extend(["", "原始返回摘要：", rawSummary])
    lines.extend(["", "预约入口：https://schedule.gtspremium.com/"])
    sendCaseEmail(case, smtpConfig, subject, "\n".join(lines))


def sendIssuedAutoStopNotification(case: dict[str, Any], smtpConfig: dict[str, Any] | None, issuedAt: str) -> None:
    subject = f"[CEAC] {case['application_num']} 已自动停止查询"
    body = "\n".join(
        [
            f"档案：{case['display_name']}",
            f"申请号：{case['application_num']}",
            "状态：Issued",
            f"首次记录 Issued 时间：{issuedAt}",
            "",
            "该档案进入 Issued 已超过一周，且你尚未在站内停止自动查询。",
            "系统已按策略自动关闭该档案的自动查询，避免继续请求 CEAC。",
            "你仍然可以登录网站，在档案详情页手动执行快速查询。",
        ],
    )
    sendCaseEmail(case, smtpConfig, subject, body)


def sendCaseEmail(case: dict[str, Any], smtpConfig: dict[str, Any] | None, subject: str, body: str) -> None:
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
