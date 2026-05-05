import json
import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from CEACStatusBot.request import query_status

from .database import getConnection, utcNowIso
from .mailer import sendCaseNotification
from .schemas import CeacCaseInput, CeacCasePatch
from .secrets import decryptIfNeeded, encryptSecret, isEncryptedSecret


SENSITIVE_CASE_COLUMNS = {"application_num", "passport_number", "surname", "receive_email"}


def computeNextCheckAt(base: datetime | None = None) -> str:
    base = base or datetime.now(UTC)
    nextHour = (base + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    return (nextHour + timedelta(minutes=random.randint(0, 59))).isoformat()


def decryptCaseRow(row: dict[str, Any]) -> dict[str, Any]:
    decrypted = dict(row)
    for column in SENSITIVE_CASE_COLUMNS:
        decrypted[column] = decryptIfNeeded(decrypted.get(column)) or ""
    return decrypted


def normalizeCaseRow(row: dict[str, Any]) -> dict[str, Any]:
    row = decryptCaseRow(row)
    return {
        "id": row["id"],
        "userId": row["user_id"],
        "displayName": row["display_name"],
        "location": row["location"],
        "applicationNum": row["application_num"],
        "passportNumber": row["passport_number"],
        "surname": row["surname"],
        "receiveEmail": row["receive_email"],
        "senderMode": row["sender_mode"],
        "isEnabled": bool(row["is_enabled"]),
        "emailNotificationsEnabled": bool(row["email_notifications_enabled"]),
        "nextCheckAt": row["next_check_at"],
        "lastCheckedAt": row["last_checked_at"],
        "lastTriggerType": row.get("last_trigger_type"),
        "lastStatus": row.get("last_status"),
        "lastDescription": row.get("last_description"),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def listCases(userId: int | None = None) -> list[dict[str, Any]]:
    params: tuple[Any, ...] = ()
    where = ""
    if userId is not None:
        where = "WHERE c.user_id = ?"
        params = (userId,)
    with getConnection() as connection:
        rows = connection.execute(
            f"""
            SELECT c.*, s.status AS last_status, s.description AS last_description
            FROM ceac_cases c
            LEFT JOIN status_catalog s ON s.id = c.last_status_id
            {where}
            ORDER BY c.updated_at DESC
            """,
            params,
        ).fetchall()
    return [normalizeCaseRow(row) for row in rows]


def getCase(caseId: int, userId: int | None = None) -> dict[str, Any] | None:
    params: tuple[Any, ...] = (caseId,)
    extraWhere = ""
    if userId is not None:
        extraWhere = "AND c.user_id = ?"
        params = (caseId, userId)
    with getConnection() as connection:
        row = connection.execute(
            f"""
            SELECT c.*, s.status AS last_status, s.description AS last_description
            FROM ceac_cases c
            LEFT JOIN status_catalog s ON s.id = c.last_status_id
            WHERE c.id = ? {extraWhere}
            """,
            params,
        ).fetchone()
    return normalizeCaseRow(row) if row else None


def upsertSmtpConfig(connection: Any, userId: int, smtpConfig: Any) -> None:
    if not smtpConfig:
        return
    now = utcNowIso()
    connection.execute(
        """
        INSERT INTO smtp_configs (user_id, from_email, host, port, use_ssl, password_encrypted, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            from_email = excluded.from_email,
            host = excluded.host,
            port = excluded.port,
            use_ssl = excluded.use_ssl,
            password_encrypted = excluded.password_encrypted,
            updated_at = excluded.updated_at
        """,
        (
            userId,
            smtpConfig.fromEmail,
            smtpConfig.host,
            smtpConfig.port,
            int(smtpConfig.useSsl),
            encryptSecret(smtpConfig.password),
            now,
            now,
        ),
    )


def createCase(userId: int, payload: CeacCaseInput) -> dict[str, Any]:
    now = utcNowIso()
    with getConnection() as connection:
        upsertSmtpConfig(connection, userId, payload.smtpConfig)
        cursor = connection.execute(
            """
            INSERT INTO ceac_cases (
                user_id, display_name, location, application_num, passport_number, surname,
                receive_email, sender_mode, is_enabled, email_notifications_enabled,
                next_check_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                userId,
                payload.displayName,
                payload.location,
                encryptSecret(payload.applicationNum),
                encryptSecret(payload.passportNumber),
                encryptSecret(payload.surname),
                encryptSecret(payload.receiveEmail),
                payload.senderMode,
                int(payload.isEnabled),
                int(payload.emailNotificationsEnabled),
                computeNextCheckAt() if payload.isEnabled else None,
                now,
                now,
            ),
        )
        caseId = cursor.lastrowid
    case = getCase(int(caseId), userId)
    if case is None:
        raise RuntimeError("创建档案失败")
    return case


def patchCase(caseId: int, userId: int, payload: CeacCasePatch) -> dict[str, Any] | None:
    current = getCase(caseId, userId)
    if not current:
        return None
    data = payload.model_dump(exclude_unset=True)
    columnMap = {
        "displayName": "display_name",
        "location": "location",
        "applicationNum": "application_num",
        "passportNumber": "passport_number",
        "surname": "surname",
        "receiveEmail": "receive_email",
        "senderMode": "sender_mode",
        "isEnabled": "is_enabled",
        "emailNotificationsEnabled": "email_notifications_enabled",
    }
    encryptedKeys = {"applicationNum", "passportNumber", "surname", "receiveEmail"}
    now = utcNowIso()
    with getConnection() as connection:
        if payload.smtpConfig:
            upsertSmtpConfig(connection, userId, payload.smtpConfig)
        assignments: list[str] = []
        values: list[Any] = []
        for key, column in columnMap.items():
            if key not in data:
                continue
            value = data[key]
            if key in encryptedKeys and value is not None:
                value = encryptSecret(str(value))
            if key == "isEnabled":
                value = int(value)
                assignments.append("next_check_at = ?")
                values.append(computeNextCheckAt() if value else None)
            if key == "emailNotificationsEnabled":
                value = int(value)
            assignments.append(f"{column} = ?")
            values.append(value)
        assignments.append("updated_at = ?")
        values.append(now)
        values.extend([caseId, userId])
        connection.execute(
            f"UPDATE ceac_cases SET {', '.join(assignments)} WHERE id = ? AND user_id = ?",
            tuple(values),
        )
    return getCase(caseId, userId)


def deleteCase(caseId: int, userId: int) -> bool:
    with getConnection() as connection:
        cursor = connection.execute("DELETE FROM ceac_cases WHERE id = ? AND user_id = ?", (caseId, userId))
        return cursor.rowcount > 0


def getOrCreateStatus(connection: Any, status: str, description: str) -> int:
    now = utcNowIso()
    existing = connection.execute(
        "SELECT id FROM status_catalog WHERE status = ? AND description = ?",
        (status, description),
    ).fetchone()
    if existing:
        return int(existing["id"])
    cursor = connection.execute(
        "INSERT INTO status_catalog (status, description, created_at) VALUES (?, ?, ?)",
        (status, description, now),
    )
    return int(cursor.lastrowid)


def runCaseQuery(caseId: int, triggerType: str = "automatic") -> dict[str, Any]:
    started = datetime.now(UTC)
    startedIso = started.replace(microsecond=0).isoformat()
    errorMessage = ""
    statusId: int | None = None
    success = False
    result: dict[str, Any] = {"success": False}
    with getConnection() as connection:
        case = connection.execute("SELECT * FROM ceac_cases WHERE id = ?", (caseId,)).fetchone()
        smtpConfig = connection.execute("SELECT * FROM smtp_configs WHERE user_id = ?", (case["user_id"],)).fetchone() if case else None
    if not case:
        raise RuntimeError("签证档案不存在")
    case = decryptCaseRow(case)

    try:
        result = query_status(case["location"], case["application_num"], case["passport_number"], case["surname"])
        if not result.get("success"):
            raise RuntimeError("CEAC 查询失败")
        success = True
    except Exception as exc:
        errorMessage = str(exc)

    finished = datetime.now(UTC)
    durationMs = int((finished - started).total_seconds() * 1000)
    finishedIso = finished.replace(microsecond=0).isoformat()

    with getConnection() as connection:
        hasChanged = False
        if success:
            statusId = getOrCreateStatus(connection, str(result["status"]), str(result.get("description", "")))
            lastHistory = connection.execute(
                """
                SELECT h.ceac_last_updated, s.status
                FROM case_status_history h
                JOIN status_catalog s ON s.id = h.status_id
                WHERE h.case_id = ?
                ORDER BY h.id DESC
                LIMIT 1
                """,
                (caseId,),
            ).fetchone()
            ceacLastUpdated = str(result.get("case_last_updated", ""))
            hasChanged = (
                lastHistory is None
                or lastHistory["status"] != result["status"]
                or lastHistory["ceac_last_updated"] != ceacLastUpdated
            )
            if hasChanged:
                connection.execute(
                    """
                    INSERT INTO case_status_history (
                        case_id, status_id, ceac_last_updated, visa_type, case_created, fetched_at, raw_payload
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        caseId,
                        statusId,
                        ceacLastUpdated,
                        str(result.get("visa_type", "")),
                        str(result.get("case_created", "")),
                        finishedIso,
                        encryptSecret(json.dumps(result, ensure_ascii=False)),
                    ),
                )
                if bool(case["email_notifications_enabled"]):
                    try:
                        sendCaseNotification(case, smtpConfig, result)
                    except Exception as exc:
                        errorMessage = f"Notification failed: {exc}"
            connection.execute(
                """
                UPDATE ceac_cases
                SET last_checked_at = ?, next_check_at = ?, last_status_id = ?, last_trigger_type = ?, updated_at = ?
                WHERE id = ?
                """,
                (finishedIso, computeNextCheckAt(finished), statusId, triggerType, finishedIso, caseId),
            )
        else:
            connection.execute(
                "UPDATE ceac_cases SET last_checked_at = ?, next_check_at = ?, last_trigger_type = ?, updated_at = ? WHERE id = ?",
                (finishedIso, computeNextCheckAt(finished), triggerType, finishedIso, caseId),
            )
        connection.execute(
            """
            INSERT INTO query_runs (case_id, started_at, finished_at, success, status_id, error_message, duration_ms, trigger_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (caseId, startedIso, finishedIso, int(success), statusId, errorMessage, durationMs, triggerType),
        )
    return {"success": success, "changed": success and hasChanged, "error": errorMessage, "result": result}


def sendCurrentStatusEmail(caseId: int, userId: int | None = None) -> dict[str, Any]:
    params: tuple[Any, ...] = (caseId,)
    userFilter = ""
    if userId is not None:
        userFilter = "AND user_id = ?"
        params = (caseId, userId)
    with getConnection() as connection:
        case = connection.execute(f"SELECT * FROM ceac_cases WHERE id = ? {userFilter}", params).fetchone()
        if not case:
            return {"success": False, "error": "签证档案不存在"}
        case = decryptCaseRow(case)
        smtpConfig = connection.execute("SELECT * FROM smtp_configs WHERE user_id = ?", (case["user_id"],)).fetchone()
        latest = connection.execute(
            """
            SELECT h.*, s.status, s.description
            FROM case_status_history h
            JOIN status_catalog s ON s.id = h.status_id
            WHERE h.case_id = ?
            ORDER BY h.id DESC
            LIMIT 1
            """,
            (caseId,),
        ).fetchone()
    if not latest:
        return {"success": False, "error": "暂无现有状态，请先快速查询一次"}
    result = {
        "success": True,
        "visa_type": latest["visa_type"],
        "status": latest["status"],
        "case_created": latest["case_created"],
        "case_last_updated": latest["ceac_last_updated"],
        "description": latest["description"],
        "application_num": case["application_num"],
        "application_num_origin": case["application_num"],
    }
    try:
        sendCaseNotification(case, smtpConfig, result)
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    return {"success": True, "error": ""}


def listHistory(caseId: int, userId: int | None = None) -> list[dict[str, Any]]:
    params: tuple[Any, ...] = (caseId,)
    userFilter = ""
    if userId is not None:
        userFilter = "AND c.user_id = ?"
        params = (caseId, userId)
    with getConnection() as connection:
        rows = connection.execute(
            f"""
            SELECT h.*, s.status, s.description
            FROM case_status_history h
            JOIN ceac_cases c ON c.id = h.case_id
            JOIN status_catalog s ON s.id = h.status_id
            WHERE h.case_id = ? {userFilter}
            ORDER BY h.id DESC
            """,
            params,
        ).fetchall()
    return [
        {
            "id": row["id"],
            "caseId": row["case_id"],
            "status": row["status"],
            "description": row["description"],
            "ceacLastUpdated": row["ceac_last_updated"],
            "visaType": row["visa_type"],
            "caseCreated": row["case_created"],
            "fetchedAt": row["fetched_at"],
            "rawPayload": json.loads(decryptIfNeeded(row["raw_payload"]) or "{}"),
        }
        for row in rows
    ]


def migrateEncryptedFields() -> None:
    with getConnection() as connection:
        for row in connection.execute("SELECT * FROM ceac_cases").fetchall():
            assignments: list[str] = []
            values: list[Any] = []
            for column in SENSITIVE_CASE_COLUMNS:
                value = row[column]
                if value and not isEncryptedSecret(value):
                    assignments.append(f"{column} = ?")
                    values.append(encryptSecret(str(value)))
            if assignments:
                values.append(row["id"])
                connection.execute(f"UPDATE ceac_cases SET {', '.join(assignments)} WHERE id = ?", tuple(values))

        for tableName in ("smtp_configs", "system_smtp_config"):
            for row in connection.execute(f"SELECT id, password_encrypted FROM {tableName}").fetchall():
                value = row["password_encrypted"]
                if value and not value.startswith("v2:"):
                    connection.execute(
                        f"UPDATE {tableName} SET password_encrypted = ? WHERE id = ?",
                        (encryptSecret(decryptIfNeeded(value) or value), row["id"]),
                    )

        for row in connection.execute("SELECT id, raw_payload FROM case_status_history").fetchall():
            value = row["raw_payload"]
            if value and not isEncryptedSecret(value):
                connection.execute(
                    "UPDATE case_status_history SET raw_payload = ? WHERE id = ?",
                    (encryptSecret(str(value)), row["id"]),
                )


def normalizeQueryJob(row: dict[str, Any]) -> dict[str, Any]:
    resultJson = decryptIfNeeded(row.get("result_json") or "") or ""
    result = json.loads(resultJson) if resultJson else None
    return {
        "id": row["id"],
        "caseId": row["case_id"],
        "triggerType": row["trigger_type"],
        "status": row["status"],
        "attempts": row["attempts"],
        "errorMessage": row["error_message"],
        "result": result,
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "startedAt": row["started_at"],
        "finishedAt": row["finished_at"],
    }


def enqueueCaseQuery(caseId: int, triggerType: str, userId: int | None = None) -> dict[str, Any] | None:
    now = utcNowIso()
    params: tuple[Any, ...] = (caseId,)
    userFilter = ""
    if userId is not None:
        userFilter = "AND user_id = ?"
        params = (caseId, userId)
    with getConnection() as connection:
        case = connection.execute(f"SELECT id FROM ceac_cases WHERE id = ? {userFilter}", params).fetchone()
        if not case:
            return None
        existing = connection.execute(
            """
            SELECT * FROM query_jobs
            WHERE case_id = ? AND status IN ('queued', 'running')
            ORDER BY id DESC
            LIMIT 1
            """,
            (caseId,),
        ).fetchone()
        if existing:
            return normalizeQueryJob(existing)
        cursor = connection.execute(
            """
            INSERT INTO query_jobs (case_id, trigger_type, status, created_at, updated_at)
            VALUES (?, ?, 'queued', ?, ?)
            """,
            (caseId, triggerType, now, now),
        )
        row = connection.execute("SELECT * FROM query_jobs WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return normalizeQueryJob(row)


def enqueueDueCases(limit: int = 20) -> list[dict[str, Any]]:
    nowIso = datetime.now(UTC).replace(microsecond=0).isoformat()
    queued: list[dict[str, Any]] = []
    with getConnection() as connection:
        rows = connection.execute(
            """
            SELECT c.id
            FROM ceac_cases c
            WHERE c.is_enabled = 1
              AND c.next_check_at IS NOT NULL
              AND c.next_check_at <= ?
              AND NOT EXISTS (
                  SELECT 1 FROM query_jobs j
                  WHERE j.case_id = c.id AND j.status IN ('queued', 'running')
              )
            ORDER BY c.next_check_at ASC
            LIMIT ?
            """,
            (nowIso, limit),
        ).fetchall()
    for row in rows:
        job = enqueueCaseQuery(int(row["id"]), "automatic")
        if job:
            queued.append(job)
    return queued


def getQueryJob(jobId: int, userId: int | None = None) -> dict[str, Any] | None:
    params: tuple[Any, ...] = (jobId,)
    userFilter = ""
    if userId is not None:
        userFilter = "AND c.user_id = ?"
        params = (jobId, userId)
    with getConnection() as connection:
        row = connection.execute(
            f"""
            SELECT j.*
            FROM query_jobs j
            JOIN ceac_cases c ON c.id = j.case_id
            WHERE j.id = ? {userFilter}
            """,
            params,
        ).fetchone()
    return normalizeQueryJob(row) if row else None


def claimNextQueryJob(workerId: str | None = None) -> dict[str, Any] | None:
    workerId = workerId or f"worker-{uuid.uuid4()}"
    nowIso = utcNowIso()
    with getConnection() as connection:
        row = connection.execute(
            """
            SELECT * FROM query_jobs
            WHERE status = 'queued'
            ORDER BY id ASC
            LIMIT 1
            """,
        ).fetchone()
        if not row:
            return None
        connection.execute(
            """
            UPDATE query_jobs
            SET status = 'running', attempts = attempts + 1, locked_at = ?, locked_by = ?,
                started_at = ?, updated_at = ?
            WHERE id = ? AND status = 'queued'
            """,
            (nowIso, workerId, nowIso, nowIso, row["id"]),
        )
        claimed = connection.execute("SELECT * FROM query_jobs WHERE id = ?", (row["id"],)).fetchone()
    return normalizeQueryJob(claimed)


def runQueryJob(job: dict[str, Any]) -> dict[str, Any]:
    nowIso = utcNowIso()
    try:
        result = runCaseQuery(int(job["caseId"]), triggerType=str(job["triggerType"]))
        status = "succeeded" if result.get("success") else "failed"
        errorMessage = str(result.get("error") or "")
    except Exception as exc:
        result = {"success": False, "changed": False, "error": str(exc)}
        status = "failed"
        errorMessage = str(exc)
    with getConnection() as connection:
        connection.execute(
            """
            UPDATE query_jobs
            SET status = ?, error_message = ?, result_json = ?, finished_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                errorMessage,
                encryptSecret(json.dumps(result, ensure_ascii=False)),
                nowIso,
                nowIso,
                job["id"],
            ),
        )
        row = connection.execute("SELECT * FROM query_jobs WHERE id = ?", (job["id"],)).fetchone()
    return normalizeQueryJob(row)
