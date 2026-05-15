from email.header import Header
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from pathlib import Path
from smtplib import SMTP, SMTP_SSL
from typing import Any
from datetime import UTC, datetime, timedelta

from .config import getSettings
from .database import getConnection, utcNowIso
from .secrets import decryptSecret, encryptSecret


class DailyEmailLimitExceeded(RuntimeError):
    pass


SUPPORT_IMAGE_CONTENT_ID = "ceacstatusbot-support-qr"


def getSupportImagePath() -> Path:
    return Path(__file__).resolve().parents[2] / "frontend" / "public" / "support" / "buy-me-a-coffee.jpg"


def buildSupportFooterPlain() -> str:
    return "\n".join(
        [
            "",
            "支持这个非盈利项目：如果 CEACStatusBot 对你有帮助，欢迎自愿扫码赞赏，支持服务器和维护成本。",
            "赞赏码图片见本邮件 HTML 版本；如果邮件客户端未显示图片，也可以登录网站查看赞赏码。",
            f"网站入口：{getSettings().appBaseUrl}",
            "小字说明：赞赏完全自愿，不购买官方服务，不保证签证结果、护照进度、slot 可用性或预约成功。",
        ],
    )


def buildEmailHtml(body: str, *, includeSupport: bool = False) -> str:
    bodyHtml = "<br>".join(escape(line) for line in body.splitlines())
    supportHtml = ""
    if includeSupport:
        supportHtml = f"""
          <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0 16px;" />
          <div style="font-size:14px;line-height:1.6;color:#111827;">
            <strong>支持这个非盈利项目</strong>
            <p style="margin:8px 0 12px;">如果 CEACStatusBot 对你有帮助，欢迎自愿扫码赞赏，支持服务器和维护成本。</p>
            <img src="cid:{SUPPORT_IMAGE_CONTENT_ID}" alt="支持 CEACStatusBot" style="display:block;width:180px;max-width:100%;height:auto;border-radius:8px;margin:8px 0 12px;" />
            <p style="margin:0;color:#6b7280;font-size:12px;">赞赏完全自愿，不购买官方服务，不保证签证结果、护照进度、slot 可用性或预约成功。</p>
          </div>
        """
    return f"""<!doctype html>
<html>
  <body style="margin:0;padding:24px;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#111827;">
    <div style="max-width:640px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;padding:24px;">
      <div style="font-size:15px;line-height:1.7;">{bodyHtml}</div>
      {supportHtml}
    </div>
  </body>
</html>"""


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
    htmlBody: str | None = None,
    inlineImages: dict[str, Path] | None = None,
) -> None:
    msg = MIMEMultipart("related")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = fromEmail
    msg["To"] = toEmail
    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(body, "plain", "utf-8"))
    if htmlBody:
        alternative.attach(MIMEText(htmlBody, "html", "utf-8"))
    msg.attach(alternative)

    for contentId, imagePath in (inlineImages or {}).items():
        if not imagePath.exists():
            continue
        image = MIMEImage(imagePath.read_bytes())
        image.add_header("Content-ID", f"<{contentId}>")
        image.add_header("Content-Disposition", "inline", filename=imagePath.name)
        msg.attach(image)

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


def sendSystemEmail(toEmail: str, subject: str, body: str, htmlBody: str | None = None, inlineImages: dict[str, Path] | None = None) -> None:
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
        htmlBody=htmlBody,
        inlineImages=inlineImages,
    )


def enforceDailyEmailLimit(userId: int | None, connection: Any | None = None) -> None:
    if userId is None:
        return
    settings = getSettings()
    now = datetime.now(UTC)
    todayStart = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrowStart = todayStart + timedelta(days=1)
    if connection is not None:
        user = connection.execute(
            "SELECT role, account_tier FROM users WHERE id = ?",
            (userId,),
        ).fetchone()
        if not user or user["role"] == "admin":
            return
        emailLimit = settings.premiumDailyEmailLimit if user["account_tier"] == "premium" else settings.standardDailyEmailLimit
        row = connection.execute(
            """
            SELECT COUNT(*) AS email_count
            FROM email_delivery_logs
            WHERE user_id = ?
              AND created_at >= ?
              AND created_at < ?
            """,
            (userId, todayStart.isoformat(), tomorrowStart.isoformat()),
        ).fetchone()
    else:
        with getConnection() as localConnection:
            user = localConnection.execute(
                "SELECT role, account_tier FROM users WHERE id = ?",
                (userId,),
            ).fetchone()
            if not user or user["role"] == "admin":
                return
            emailLimit = settings.premiumDailyEmailLimit if user["account_tier"] == "premium" else settings.standardDailyEmailLimit
            row = localConnection.execute(
                """
                SELECT COUNT(*) AS email_count
                FROM email_delivery_logs
                WHERE user_id = ?
                  AND created_at >= ?
                  AND created_at < ?
                """,
                (userId, todayStart.isoformat(), tomorrowStart.isoformat()),
            ).fetchone()
    emailCount = int(row["email_count"] if row else 0)
    if emailCount >= emailLimit:
        raise DailyEmailLimitExceeded(f"今日邮件发送数量已达上限（{emailLimit} 封），请明天再试。")


def recordEmailDelivery(
    *,
    userId: int | None,
    caseId: int | None,
    emailType: str,
    recipient: str,
    subject: str,
    connection: Any | None = None,
) -> None:
    if userId is None:
        return
    if connection is not None:
        connection.execute(
            """
            INSERT INTO email_delivery_logs (user_id, case_id, email_type, recipient, subject, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (userId, caseId, emailType, recipient, subject, utcNowIso()),
        )
        return
    with getConnection() as localConnection:
        localConnection.execute(
            """
            INSERT INTO email_delivery_logs (user_id, case_id, email_type, recipient, subject, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (userId, caseId, emailType, recipient, subject, utcNowIso()),
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


def sendCaseNotification(case: dict[str, Any], smtpConfig: dict[str, Any] | None, result: dict[str, Any], connection: Any | None = None) -> None:
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
                "提示：该档案已进入 Issued，系统会将自动查询频率降为每天一次。",
                "你可以登录站内档案详情页停止自动查询；如果一周内未停止，系统将自动停止该档案的自动查询并邮件通知你。",
            ],
        )
    if str(result.get("status", "")).strip().lower() in {"approved", "issued"}:
        lines.extend(
            [
                "",
                "护照预约提醒：你现在可以登录 CEACStatusBot，在该档案详情页填写 UID 或 HAL，开启 GTS 护照预约 slot 监控。",
                "系统会监控“暂不具备预约资格 / 暂无 slot / 发现 slot”三种状态，并在进入可预约阶段、发现 slot 或 slot 时间变化时邮件通知你。",
                f"登录入口：{getSettings().appBaseUrl}",
            ],
        )
    status = str(result.get("status", "")).strip().lower()
    includeSupport = status in {"approved", "issued"}
    body = "\n".join(lines)
    sendCaseEmail(
        case,
        smtpConfig,
        subject,
        body,
        emailType="ceac_status",
        connection=connection,
        includeSupport=includeSupport,
    )


def sendPassportSlotNotification(
    case: dict[str, Any],
    smtpConfig: dict[str, Any] | None,
    *,
    identifierFull: str,
    identifierMasked: str,
    fetchedAt: str,
    slotStatus: str,
    statusMessage: str,
    slotLines: list[str],
    rawSummary: str,
    connection: Any | None = None,
) -> None:
    sendPassportSlotStatusEmail(
        case,
        smtpConfig,
        identifierFull=identifierFull,
        identifierMasked=identifierMasked,
        fetchedAt=fetchedAt,
        slotStatus=slotStatus,
        statusMessage=statusMessage,
        slotLines=slotLines,
        rawSummary=rawSummary,
        hasSlots=slotStatus == "has_slot",
        isTest=False,
        connection=connection,
    )


def sendPassportSlotStatusEmail(
    case: dict[str, Any],
    smtpConfig: dict[str, Any] | None,
    *,
    identifierFull: str,
    identifierMasked: str,
    fetchedAt: str,
    slotStatus: str,
    statusMessage: str,
    slotLines: list[str],
    rawSummary: str,
    hasSlots: bool,
    isTest: bool = False,
    connection: Any | None = None,
) -> None:
    subject = f"[GTS] 发现可预约时间：{case['display_name']}"
    if slotStatus == "no_slot":
        subject = f"[GTS] 护照已可预约但暂无 slot：{case['display_name']}"
    elif slotStatus == "not_eligible":
        subject = f"[GTS] 暂不具备护照预约资格：{case['display_name']}"
    if isTest:
        subject = f"[GTS] 护照预约监控测试：{case['display_name']}"
    statusLabel = statusMessage or ("发现可预约时间" if hasSlots else "暂无可预约时间")
    appEntry = getSettings().appBaseUrl
    lines = [
        f"档案：{case['display_name']}",
        f"申请号：{case['application_num']}",
        f"UID/HAL：{identifierFull or identifierMasked}",
        f"查询时间：{fetchedAt}",
        "",
        f"当前状态：{statusLabel}",
    ]
    if hasSlots:
        lines.append("")
        lines.append("当前可预约时间：")
        lines.extend(slotLines or ["接口返回了可用 slot，但未能解析为标准日期 / 时间字段。"])
        lines.extend(
            [
                "",
                "系统已将该档案的 slot 自动查询放缓到约每小时一次，并且不会再参与零点加频。",
                "如果你已经在 GTS 官网预约成功，请回到站内档案详情页点击“我已预约，停止监控”。",
            ],
        )
    elif slotStatus == "not_eligible":
        lines.append("这通常表示护照还在签证处/使馆，尚未送达中信银行。系统会继续按常规频率监控。")
    elif slotStatus == "no_slot":
        lines.append("这通常表示护照已进入可预约阶段，但当前没有可选时间；系统会继续监控，并在零点附近加密查询。")
    elif isTest:
        lines.append("这是一封测试邮件，用于确认护照预约监控的发信配置可用。")
    lines.extend(
        [
            "",
            "预约入口：https://schedule.gtspremium.com/",
            f"站内入口：{appEntry}",
            "操作提示：打开官网，输入上方 UID/HAL，勾选条款后查询。",
            "安全提醒：本邮件包含完整 UID/HAL，请勿转发或公开截图。",
        ],
    )
    body = "\n".join(lines)
    sendCaseEmail(
        case,
        smtpConfig,
        subject,
        body,
        emailType="passport_slot",
        connection=connection,
        includeSupport=True,
    )


def sendIssuedAutoStopNotification(case: dict[str, Any], smtpConfig: dict[str, Any] | None, issuedAt: str, connection: Any | None = None) -> None:
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
            "你仍然可以登录网站，在档案详情页手动执行立即查询。",
        ],
    )
    sendCaseEmail(
        case,
        smtpConfig,
        subject,
        body,
        emailType="issued_auto_stop",
        connection=connection,
        includeSupport=True,
    )


def sendCeacConsecutiveFailureNotification(
    case: dict[str, Any],
    smtpConfig: dict[str, Any] | None,
    *,
    errorCount: int,
    errorMessage: str,
    stopped: bool,
    connection: Any | None = None,
) -> None:
    subject = f"[CEAC] {case['application_num']} 连续查询失败 {errorCount} 次"
    if stopped:
        subject = f"[CEAC] {case['application_num']} 已因连续失败停止自动查询"
    lines = [
        f"档案：{case['display_name']}",
        f"申请号：{case['application_num']}",
        f"连续失败次数：{errorCount}",
        f"最近失败原因：{errorMessage or 'CEAC 查询失败'}",
        "",
    ]
    if stopped:
        lines.extend(
            [
                "该档案已经连续 10 次查询失败，系统已自动停止 CEAC 自动查询，避免继续无效请求。",
                "你仍然可以登录网站核对信息，并手动执行“立即查询”。如果确认信息无误但仍失败，请联系管理员。",
            ],
        )
    else:
        lines.extend(
            [
                "该档案已经连续 5 次查询失败。",
                "请登录网站核对办理地点、Application ID 或 Case Number、护照号、姓氏前 5 个字母是否填写正确。",
                "如果信息没有修改，后续仍然连续失败到 10 次，系统会自动停止该档案的 CEAC 自动查询。",
            ],
        )
    lines.extend(["", f"登录入口：{getSettings().appBaseUrl}"])
    sendCaseEmail(
        case,
        smtpConfig,
        subject,
        "\n".join(lines),
        emailType="ceac_consecutive_failure",
        connection=connection,
        includeSupport=False,
    )


def sendCaseEmail(
    case: dict[str, Any],
    smtpConfig: dict[str, Any] | None,
    subject: str,
    body: str,
    *,
    emailType: str = "case",
    connection: Any | None = None,
    includeSupport: bool = False,
) -> None:
    userId = int(case["user_id"]) if case.get("user_id") is not None else None
    caseId = int(case["id"]) if case.get("id") is not None else None
    enforceDailyEmailLimit(userId, connection)
    inlineImages = {SUPPORT_IMAGE_CONTENT_ID: getSupportImagePath()} if includeSupport else None
    plainBody = body + (buildSupportFooterPlain() if includeSupport else "")
    htmlBody = buildEmailHtml(body, includeSupport=includeSupport)
    if case["sender_mode"] == "custom" and smtpConfig:
        sendEmail(
            fromEmail=smtpConfig["from_email"],
            toEmail=case["receive_email"],
            password=decryptSecret(smtpConfig["password_encrypted"]),
            host=smtpConfig["host"],
            port=int(smtpConfig["port"]),
            useSsl=bool(smtpConfig["use_ssl"]),
            subject=subject,
            body=plainBody,
            htmlBody=htmlBody,
            inlineImages=inlineImages,
        )
        recordEmailDelivery(userId=userId, caseId=caseId, emailType=emailType, recipient=case["receive_email"], subject=subject, connection=connection)
        return
    sendSystemEmail(case["receive_email"], subject, plainBody, htmlBody=htmlBody, inlineImages=inlineImages)
    recordEmailDelivery(userId=userId, caseId=caseId, emailType=emailType, recipient=case["receive_email"], subject=subject, connection=connection)
