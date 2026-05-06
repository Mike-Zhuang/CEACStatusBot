import hashlib
import json
import random
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from .database import getConnection, utcNowIso
from .mailer import sendPassportSlotNotification, sendPassportSlotStatusEmail
from .secrets import decryptIfNeeded, encryptSecret


GTS_API_BASE_URL = "https://scheduling-api.gtspremium.com"
GTS_SITE_URL = "https://schedule.gtspremium.com/"
EMPTY_SLOT_FINGERPRINT = "empty"
PASSPORT_SLOT_TRIGGER_PREFIX = "passport_slot_"


def normalizeIdentifier(identifier: str) -> str:
    value = re.sub(r"\s+", "", identifier or "").upper()
    if not value:
        raise ValueError("UID/HAL 不能为空")
    if value.startswith("HAL"):
        if not re.fullmatch(r"HAL\d{10}", value):
            raise ValueError("HAL 必须以 HAL 开头并包含 10 位数字")
        return value
    digits = re.sub(r"\D", "", value)
    if not re.fullmatch(r"\d{8,9}", digits):
        raise ValueError("UID 必须是 8 或 9 位数字")
    return digits


def maskIdentifier(identifier: str) -> str:
    value = normalizeIdentifier(identifier)
    if value.startswith("HAL"):
        return f"HAL******{value[-4:]}"
    return f"{value[:2]}***{value[-3:]}"


def computeNextPassportSlotCheckAt(
    base: datetime | None = None,
    *,
    isRateLimited: bool = False,
    hadError: bool = False,
) -> str:
    base = base or datetime.now(UTC)
    if isRateLimited:
        minutes = random.randint(30, 60)
    elif hadError:
        minutes = random.randint(10, 20)
    else:
        minutes = random.randint(5, 10)
    return (base + timedelta(minutes=minutes)).replace(microsecond=0).isoformat()


def normalizePassportSlotMonitor(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    resultJson = decryptIfNeeded(row.get("last_result_json") or "") or ""
    result = json.loads(resultJson) if resultJson else None
    identifier = decryptIfNeeded(row.get("identifier_encrypted")) or ""
    return {
        "id": row["id"],
        "caseId": row["case_id"],
        "identifier": identifier,
        "identifierMasked": maskIdentifier(identifier) if identifier else "",
        "isEnabled": bool(row["is_enabled"]),
        "emailNotificationsEnabled": bool(row["email_notifications_enabled"]),
        "nextCheckAt": row["next_check_at"],
        "lastCheckedAt": row["last_checked_at"],
        "lastSlotFingerprint": row["last_slot_fingerprint"],
        "lastSlotCount": row["last_slot_count"],
        "lastResult": result,
        "lastErrorMessage": row["last_error_message"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def getPassportSlotMonitor(caseId: int, userId: int | None = None) -> dict[str, Any] | None:
    params: tuple[Any, ...] = (caseId,)
    userFilter = ""
    if userId is not None:
        userFilter = "AND c.user_id = ?"
        params = (caseId, userId)
    with getConnection() as connection:
        row = connection.execute(
            f"""
            SELECT m.*
            FROM passport_slot_monitors m
            JOIN ceac_cases c ON c.id = m.case_id
            WHERE m.case_id = ? {userFilter}
            """,
            params,
        ).fetchone()
    return normalizePassportSlotMonitor(row)


def upsertPassportSlotMonitor(
    caseId: int,
    userId: int,
    identifier: str,
    isEnabled: bool,
    emailNotificationsEnabled: bool,
) -> dict[str, Any] | None:
    normalizedIdentifier = normalizeIdentifier(identifier)
    now = datetime.now(UTC).replace(microsecond=0)
    nowIso = now.isoformat()
    nextCheckAt = computeNextPassportSlotCheckAt(now) if isEnabled else None
    with getConnection() as connection:
        case = connection.execute("SELECT id FROM ceac_cases WHERE id = ? AND user_id = ?", (caseId, userId)).fetchone()
        if not case:
            return None
        current = connection.execute("SELECT id FROM passport_slot_monitors WHERE case_id = ?", (caseId,)).fetchone()
        if current:
            connection.execute(
                """
                UPDATE passport_slot_monitors
                SET identifier_encrypted = ?, is_enabled = ?, email_notifications_enabled = ?,
                    next_check_at = ?, last_error_message = '', updated_at = ?
                WHERE case_id = ?
                """,
                (encryptSecret(normalizedIdentifier), int(isEnabled), int(emailNotificationsEnabled), nextCheckAt, nowIso, caseId),
            )
        else:
            connection.execute(
                """
                INSERT INTO passport_slot_monitors (
                    case_id, identifier_encrypted, is_enabled, email_notifications_enabled, next_check_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (caseId, encryptSecret(normalizedIdentifier), int(isEnabled), int(emailNotificationsEnabled), nextCheckAt, nowIso, nowIso),
            )
    return getPassportSlotMonitor(caseId, userId)


def patchPassportSlotMonitor(
    caseId: int,
    userId: int,
    *,
    isEnabled: bool | None = None,
    emailNotificationsEnabled: bool | None = None,
) -> dict[str, Any] | None:
    now = datetime.now(UTC).replace(microsecond=0)
    nowIso = now.isoformat()
    with getConnection() as connection:
        row = connection.execute(
            """
            SELECT m.id
            FROM passport_slot_monitors m
            JOIN ceac_cases c ON c.id = m.case_id
            WHERE m.case_id = ? AND c.user_id = ?
            """,
            (caseId, userId),
        ).fetchone()
        if not row:
            return None
        assignments: list[str] = []
        values: list[Any] = []
        if isEnabled is not None:
            assignments.extend(["is_enabled = ?", "next_check_at = ?"])
            values.extend([int(isEnabled), computeNextPassportSlotCheckAt(now) if isEnabled else None])
        if emailNotificationsEnabled is not None:
            assignments.append("email_notifications_enabled = ?")
            values.append(int(emailNotificationsEnabled))
        if not assignments:
            return getPassportSlotMonitor(caseId, userId)
        assignments.append("updated_at = ?")
        values.extend([nowIso, caseId])
        connection.execute(
            f"UPDATE passport_slot_monitors SET {', '.join(assignments)} WHERE case_id = ?",
            tuple(values),
        )
    return getPassportSlotMonitor(caseId, userId)


def normalizeSlots(data: dict[str, Any]) -> list[Any]:
    availableDates = data.get("availableDates")
    if isinstance(availableDates, list):
        return availableDates
    for key in ("slots", "availableSlots", "dates"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def stableSlotValue(slot: Any) -> Any:
    if isinstance(slot, dict):
        preferredKeys = [
            "date",
            "time",
            "datetime",
            "dateTime",
            "startTime",
            "endTime",
            "city",
            "location",
            "center",
            "available",
        ]
        compact = {key: slot[key] for key in preferredKeys if key in slot}
        return compact or {key: slot[key] for key in sorted(slot)}
    return slot


def computeSlotFingerprint(slots: list[Any]) -> str:
    if not slots:
        return EMPTY_SLOT_FINGERPRINT
    normalized = [stableSlotValue(slot) for slot in slots]
    normalized.sort(key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False))
    payload = json.dumps(normalized, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def formatSlotLines(slots: list[Any]) -> list[str]:
    lines: list[str] = []
    for index, slot in enumerate(slots[:20], start=1):
        if isinstance(slot, dict):
            parts = []
            for key in ("date", "time", "datetime", "dateTime", "startTime", "endTime", "city", "location", "center"):
                value = slot.get(key)
                if value not in (None, ""):
                    parts.append(f"{key}: {value}")
            lines.append(f"{index}. {'; '.join(parts) if parts else json.dumps(slot, ensure_ascii=False, default=str)}")
        else:
            lines.append(f"{index}. {slot}")
    if len(slots) > 20:
        lines.append(f"... 还有 {len(slots) - 20} 条结果未在邮件中展开。")
    return lines


def summarizePayload(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)[:2000]


def buildGtsHeaders() -> dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": GTS_SITE_URL.rstrip("/"),
        "Referer": GTS_SITE_URL,
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
    }


def isRateLimitedResponse(data: dict[str, Any], statusCode: int) -> bool:
    return statusCode == 429 or data.get("rateLimited") is True or data.get("reason") == "rate_limited"


def errorFromAuthResponse(data: dict[str, Any]) -> str:
    errors = data.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            return str(first.get("message") or first.get("reason") or "GTS UID/HAL 鉴权失败")
    if data.get("token") is None:
        return "GTS 未返回 token，UID/HAL 可能不具备预约资格"
    return "GTS UID/HAL 鉴权失败"


def fetchPassportSlotAvailability(identifier: str) -> dict[str, Any]:
    normalizedIdentifier = normalizeIdentifier(identifier)
    headers = buildGtsHeaders()
    with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=True) as client:
        authResponse = client.post(
            f"{GTS_API_BASE_URL}/authenticate",
            headers=headers,
            json={"uid": normalizedIdentifier},
        )
        try:
            authData = authResponse.json()
        except ValueError as exc:
            raise RuntimeError(f"GTS 鉴权返回非 JSON：HTTP {authResponse.status_code}") from exc
        if isRateLimitedResponse(authData, authResponse.status_code):
            return {"success": False, "rateLimited": True, "error": "GTS 请求被限流", "raw": authData}
        token = authData.get("token") if isinstance(authData, dict) else None
        if not token:
            return {"success": False, "rateLimited": False, "error": errorFromAuthResponse(authData), "raw": authData}
        availabilityResponse = client.get(
            f"{GTS_API_BASE_URL}/availability7days/",
            headers={**headers, "Authorization": str(token)},
        )
        try:
            availabilityData = availabilityResponse.json()
        except ValueError as exc:
            raise RuntimeError(f"GTS slot 返回非 JSON：HTTP {availabilityResponse.status_code}") from exc
        if isRateLimitedResponse(availabilityData, availabilityResponse.status_code):
            return {"success": False, "rateLimited": True, "error": "GTS slot 查询被限流", "raw": availabilityData}
        slots = normalizeSlots(availabilityData)
        return {
            "success": True,
            "rateLimited": False,
            "availableSlots": slots,
            "availableDates": availabilityData.get("availableDates", slots),
            "raw": availabilityData,
        }


def runPassportSlotQuery(caseId: int, triggerType: str = "passport_slot_automatic") -> dict[str, Any]:
    started = datetime.now(UTC)
    startedIso = started.replace(microsecond=0).isoformat()
    success = False
    errorMessage = ""
    result: dict[str, Any] = {"success": False}
    with getConnection() as connection:
        row = connection.execute(
            """
            SELECT m.*, c.user_id, c.display_name, c.application_num, c.receive_email, c.sender_mode
            FROM passport_slot_monitors m
            JOIN ceac_cases c ON c.id = m.case_id
            WHERE m.case_id = ?
            """,
            (caseId,),
        ).fetchone()
        smtpConfig = connection.execute("SELECT * FROM smtp_configs WHERE user_id = ?", (row["user_id"],)).fetchone() if row else None
    if not row:
        raise RuntimeError("护照预约监控不存在")
    identifier = decryptIfNeeded(row["identifier_encrypted"]) or ""
    slots: list[Any] = []
    fingerprint = row["last_slot_fingerprint"] or ""
    notificationSent = False

    try:
        result = fetchPassportSlotAvailability(identifier)
        success = bool(result.get("success"))
        if not success:
            errorMessage = str(result.get("error") or "GTS slot 查询失败")
        else:
            slots = normalizeSlots(result)
            fingerprint = computeSlotFingerprint(slots)
    except Exception as exc:
        errorMessage = str(exc)
        result = {"success": False, "error": errorMessage, "rateLimited": False}

    finished = datetime.now(UTC)
    finishedIso = finished.replace(microsecond=0).isoformat()
    durationMs = int((finished - started).total_seconds() * 1000)
    previousFingerprint = row["last_slot_fingerprint"] or ""
    hasSlot = bool(slots)
    changed = success and fingerprint != previousFingerprint
    shouldNotify = success and hasSlot and fingerprint != previousFingerprint and bool(row["email_notifications_enabled"])

    with getConnection() as connection:
        if shouldNotify:
            try:
                sendPassportSlotNotification(
                    {
                        "display_name": row["display_name"],
                        "application_num": decryptIfNeeded(row["application_num"]) or row["application_num"],
                        "receive_email": decryptIfNeeded(row["receive_email"]) or row["receive_email"],
                        "sender_mode": row["sender_mode"],
                    },
                    smtpConfig,
                    identifierMasked=maskIdentifier(identifier),
                    fetchedAt=finishedIso,
                    slotLines=formatSlotLines(slots),
                    rawSummary=summarizePayload(result.get("raw") if isinstance(result.get("raw"), dict) else result),
                )
                notificationSent = True
            except Exception as exc:
                errorMessage = f"Notification failed: {exc}"
        if success and changed:
            connection.execute(
                """
                INSERT INTO passport_slot_history (
                    monitor_id, case_id, slot_fingerprint, slot_count, raw_payload, fetched_at, notification_sent
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    caseId,
                    fingerprint,
                    len(slots),
                    encryptSecret(json.dumps(result, ensure_ascii=False, default=str)),
                    finishedIso,
                    int(notificationSent),
                ),
            )
        nextCheckAt = (
            computeNextPassportSlotCheckAt(finished, isRateLimited=bool(result.get("rateLimited")), hadError=not success)
            if bool(row["is_enabled"])
            else None
        )
        connection.execute(
            """
            UPDATE passport_slot_monitors
            SET last_checked_at = ?, next_check_at = ?, last_slot_fingerprint = ?,
                last_slot_count = ?, last_result_json = ?, last_error_message = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                finishedIso,
                nextCheckAt,
                fingerprint if success else previousFingerprint,
                len(slots) if success else int(row["last_slot_count"]),
                encryptSecret(json.dumps(result, ensure_ascii=False, default=str)),
                errorMessage,
                finishedIso,
                row["id"],
            ),
        )
        connection.execute(
            """
            INSERT INTO query_runs (case_id, started_at, finished_at, success, status_id, error_message, duration_ms, trigger_type)
            VALUES (?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (caseId, startedIso, finishedIso, int(success), errorMessage, durationMs, triggerType),
        )
    return {
        "success": success,
        "changed": changed,
        "notified": notificationSent,
        "slotCount": len(slots),
        "error": errorMessage,
        "result": result,
    }


def sendCurrentPassportSlotEmail(caseId: int, userId: int | None = None) -> dict[str, Any]:
    params: tuple[Any, ...] = (caseId,)
    userFilter = ""
    if userId is not None:
        userFilter = "AND c.user_id = ?"
        params = (caseId, userId)
    with getConnection() as connection:
        row = connection.execute(
            f"""
            SELECT m.*, c.user_id, c.display_name, c.application_num, c.receive_email, c.sender_mode
            FROM passport_slot_monitors m
            JOIN ceac_cases c ON c.id = m.case_id
            WHERE m.case_id = ? {userFilter}
            """,
            params,
        ).fetchone()
        if not row:
            return {"success": False, "error": "护照预约监控不存在，请先保存 UID/HAL"}
        smtpConfig = connection.execute("SELECT * FROM smtp_configs WHERE user_id = ?", (row["user_id"],)).fetchone()
    identifier = decryptIfNeeded(row["identifier_encrypted"]) or ""
    resultJson = decryptIfNeeded(row.get("last_result_json") or "") or ""
    result = json.loads(resultJson) if resultJson else {}
    slots = normalizeSlots(result) if isinstance(result, dict) else []
    rawSummary = summarizePayload(result) if result else (row["last_error_message"] or "尚未执行过 GTS slot 查询。")
    case = {
        "display_name": row["display_name"],
        "application_num": decryptIfNeeded(row["application_num"]) or row["application_num"],
        "receive_email": decryptIfNeeded(row["receive_email"]) or row["receive_email"],
        "sender_mode": row["sender_mode"],
    }
    try:
        sendPassportSlotStatusEmail(
            case,
            smtpConfig,
            identifierMasked=maskIdentifier(identifier),
            fetchedAt=row["last_checked_at"] or utcNowIso(),
            slotLines=formatSlotLines(slots),
            rawSummary=rawSummary,
            hasSlots=bool(slots),
            isTest=True,
        )
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    return {"success": True, "error": ""}


def enqueuePassportSlotQuery(caseId: int, triggerType: str, userId: int | None = None) -> dict[str, Any] | None:
    now = utcNowIso()
    params: tuple[Any, ...] = (caseId,)
    userFilter = ""
    if userId is not None:
        userFilter = "AND c.user_id = ?"
        params = (caseId, userId)
    with getConnection() as connection:
        monitor = connection.execute(
            f"""
            SELECT m.id
            FROM passport_slot_monitors m
            JOIN ceac_cases c ON c.id = m.case_id
            WHERE m.case_id = ? {userFilter}
            """,
            params,
        ).fetchone()
        if not monitor:
            return None
        existing = connection.execute(
            """
            SELECT * FROM query_jobs
            WHERE case_id = ?
              AND trigger_type LIKE 'passport_slot_%'
              AND status IN ('queued', 'running')
            ORDER BY id DESC
            LIMIT 1
            """,
            (caseId,),
        ).fetchone()
        if existing:
            from .case_service import normalizeQueryJob

            return normalizeQueryJob(existing)
        cursor = connection.execute(
            """
            INSERT INTO query_jobs (case_id, trigger_type, status, created_at, updated_at)
            VALUES (?, ?, 'queued', ?, ?)
            """,
            (caseId, triggerType, now, now),
        )
        row = connection.execute("SELECT * FROM query_jobs WHERE id = ?", (cursor.lastrowid,)).fetchone()
    from .case_service import normalizeQueryJob

    return normalizeQueryJob(row)


def enqueueDuePassportSlotMonitors(limit: int = 20) -> list[dict[str, Any]]:
    nowIso = datetime.now(UTC).replace(microsecond=0).isoformat()
    queued: list[dict[str, Any]] = []
    with getConnection() as connection:
        rows = connection.execute(
            """
            SELECT m.case_id
            FROM passport_slot_monitors m
            WHERE m.is_enabled = 1
              AND m.next_check_at IS NOT NULL
              AND m.next_check_at <= ?
              AND NOT EXISTS (
                  SELECT 1 FROM query_jobs j
                  WHERE j.case_id = m.case_id
                    AND j.trigger_type LIKE 'passport_slot_%'
                    AND j.status IN ('queued', 'running')
              )
            ORDER BY m.next_check_at ASC
            LIMIT ?
            """,
            (nowIso, limit),
        ).fetchall()
    for row in rows:
        job = enqueuePassportSlotQuery(int(row["case_id"]), "passport_slot_automatic")
        if job:
            queued.append(job)
    return queued


def listPassportSlotHistory(caseId: int, userId: int | None = None) -> list[dict[str, Any]]:
    params: tuple[Any, ...] = (caseId,)
    userFilter = ""
    if userId is not None:
        userFilter = "AND c.user_id = ?"
        params = (caseId, userId)
    with getConnection() as connection:
        rows = connection.execute(
            f"""
            SELECT h.*
            FROM passport_slot_history h
            JOIN ceac_cases c ON c.id = h.case_id
            WHERE h.case_id = ? {userFilter}
            ORDER BY h.id DESC
            LIMIT 50
            """,
            params,
        ).fetchall()
    return [
        {
            "id": row["id"],
            "caseId": row["case_id"],
            "slotFingerprint": row["slot_fingerprint"],
            "slotCount": row["slot_count"],
            "rawPayload": json.loads(decryptIfNeeded(row["raw_payload"]) or "{}"),
            "fetchedAt": row["fetched_at"],
            "notificationSent": bool(row["notification_sent"]),
        }
        for row in rows
    ]


def isPassportSlotTrigger(triggerType: str | None) -> bool:
    return str(triggerType or "").startswith(PASSPORT_SLOT_TRIGGER_PREFIX)


def passportWorkerId() -> str:
    return f"passport-slot-{uuid.uuid4()}"
