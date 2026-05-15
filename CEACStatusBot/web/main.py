from datetime import UTC, datetime, timedelta
import secrets
from urllib.parse import urlparse

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from .case_service import (
    createCase,
    deleteCase,
    enqueueCaseQuery,
    enqueueDueCases,
    getCase,
    getQueryJob,
    listCases,
    listHistory,
    migrateEncryptedFields,
    patchCase,
    restoreCaseAutomaticQuery,
    sendCurrentStatusEmail,
    updateUserAccountTier,
    updateUserWorkerPriority,
)
from .config import getSettings
from .database import getConnection, initializeDatabase, utcNowIso
from .mailer import getSystemSmtpConfigPublic, saveSystemSmtpConfig, sendSystemEmail
from .passport_slot_service import (
    enqueueDuePassportSlotMonitors,
    enqueuePassportSlotQuery,
    getPassportSlotMonitor,
    listPassportSlotHistory,
    patchPassportSlotMonitor,
    sendCurrentPassportSlotEmail,
    upsertPassportSlotMonitor,
)
from .schemas import (
    AccountTierPatch,
    CeacCaseInput,
    CeacCasePatch,
    LoginRequest,
    PasswordResetCodeRequest,
    PasswordResetRequest,
    PassportSlotMonitorInput,
    PassportSlotMonitorPatch,
    ProfileUpdateRequest,
    RegisterRequest,
    SendCodeRequest,
    SystemSmtpConfigInput,
    WorkerPriorityPatch,
)
from .security import (
    clearSessionCookie,
    getCurrentUser,
    hashCode,
    hashPassword,
    needsPasswordRehash,
    requireAdmin,
    seedDefaultUsers,
    setSessionCookie,
    verifyPassword,
)
from .security_guard import (
    attachDeviceCookie,
    clearLoginFailures,
    enforceAuthCodeLimits,
    enforceLoginAttemptLimit,
    enforceRateLimit,
    getOrCreateDeviceId,
    listSecurityEvents,
    logSecurityEvent,
    recordLoginFailure,
    requestActorHashes,
)
from .secrets import decryptIfNeeded, getCredentialMasterKey


app = FastAPI(title="CEACStatusBot Web", version="1.0.0")
settings = getSettings()
scheduler = BackgroundScheduler(timezone="UTC")

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowedHosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.corsOrigins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validationExceptionHandler(request: Request, exc: RequestValidationError):
    logSecurityEvent(
        eventType="validation_rejected",
        request=request,
        severity="warning",
        detail={"errorCount": len(exc.errors())},
    )
    return JSONResponse({"detail": "请求参数格式不正确"}, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


@app.middleware("http")
async def securityResponseHeaders(request: Request, callNext):
    response = await callNext(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    )
    if settings.cookieSecure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.middleware("http")
async def requestGuard(request: Request, callNext):
    if request.url.path.startswith("/api/"):
        getOrCreateDeviceId(request)
        contentLength = request.headers.get("content-length")
        if contentLength and contentLength.isdigit() and int(contentLength) > settings.apiMaxBodyBytes:
            logSecurityEvent(eventType="request_body_too_large", request=request, severity="warning")
            return JSONResponse({"detail": "请求体过大"}, status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
    response = await callNext(request)
    if request.url.path.startswith("/api/"):
        attachDeviceCookie(request, response)
    return response


def requestOrigin(request: Request) -> str:
    origin = request.headers.get("origin")
    if origin:
        return origin.rstrip("/")
    referer = request.headers.get("referer")
    if not referer:
        return ""
    parsed = urlparse(referer)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


@app.middleware("http")
async def csrfOriginGuard(request: Request, callNext):
    unsafeMethods = {"POST", "PATCH", "PUT", "DELETE"}
    if request.method in unsafeMethods and request.url.path.startswith("/api/"):
        origin = requestOrigin(request)
        if origin not in settings.csrfTrustedOrigins:
            logSecurityEvent(
                eventType="csrf_rejected",
                request=request,
                severity="warning",
                detail={"origin": origin or "missing"},
            )
            return JSONResponse({"detail": "Forbidden origin"}, status_code=status.HTTP_403_FORBIDDEN)
    return await callNext(request)


def currentUserDependency(request: Request) -> dict:
    return getCurrentUser(request)


def adminDependency(request: Request) -> dict:
    return requireAdmin(request)


def listCasesForQueryRuns(rows: list[dict]) -> list[dict]:
    runs: list[dict] = []
    for row in rows:
        item = dict(row)
        item["application_num"] = decryptIfNeeded(item.get("application_num")) or ""
        runs.append(item)
    return runs


def enforceDailyManualQueryLimit(user: dict) -> None:
    if user.get("role") == "admin":
        return
    queryLimit = settings.premiumDailyManualQueryLimit if user.get("account_tier") == "premium" else settings.standardDailyManualQueryLimit
    now = datetime.now(UTC)
    todayStart = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrowStart = todayStart + timedelta(days=1)
    with getConnection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS query_count
            FROM query_jobs j
            JOIN ceac_cases c ON c.id = j.case_id
            WHERE c.user_id = ?
              AND j.trigger_type IN ('manual', 'passport_slot_manual')
              AND j.created_at >= ?
              AND j.created_at < ?
            """,
            (
                int(user["id"]),
                todayStart.isoformat(),
                tomorrowStart.isoformat(),
            ),
        ).fetchone()
    queryCount = int(row["query_count"] if row else 0)
    if queryCount >= queryLimit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"今日立即查询次数已达上限（{queryLimit} 次），请明天再试。",
        )


def runDueCases() -> None:
    try:
        queued = enqueueDueCases()
        if queued:
            print(f"[scheduler] queued {len(queued)} CEAC query job(s)")
    except Exception as exc:
        print(f"[scheduler] enqueue failed: {exc}")


def runDuePassportSlotMonitors() -> None:
    try:
        queued = enqueueDuePassportSlotMonitors()
        if queued:
            print(f"[scheduler] queued {len(queued)} GTS slot query job(s)")
    except Exception as exc:
        print(f"[scheduler] enqueue GTS failed: {exc}")


@app.on_event("startup")
def onStartup() -> None:
    getCredentialMasterKey()
    initializeDatabase()
    migrateEncryptedFields()
    if settings.seedDefaultUsers:
        seedDefaultUsers()
    if not scheduler.running:
        scheduler.add_job(runDueCases, "interval", minutes=1, id="run-due-cases", replace_existing=True)
        scheduler.add_job(runDuePassportSlotMonitors, "interval", seconds=1, id="run-due-passport-slot-monitors", replace_existing=True)
        scheduler.start()


@app.on_event("shutdown")
def onShutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/auth/send-code")
def sendCode(payload: SendCodeRequest, request: Request) -> dict:
    email = str(payload.email).lower()
    enforceAuthCodeLimits(request, email, "register")
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = datetime.now(UTC)
    with getConnection() as connection:
        existing = connection.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已注册")
        connection.execute(
            """
            INSERT INTO email_verification_codes (email, code_hash, purpose, expires_at, created_at)
            VALUES (?, ?, 'register', ?, ?)
            """,
            (
                email,
                hashCode(code),
                (now + timedelta(minutes=10)).replace(microsecond=0).isoformat(),
                now.replace(microsecond=0).isoformat(),
            ),
        )
    sendSystemEmail(email, "CEACStatusBot 注册验证码", f"你的注册验证码是：{code}\n\n验证码 10 分钟内有效。")
    logSecurityEvent(eventType="register_code_sent", request=request, email=email)
    return {"ok": True}


@app.post("/api/auth/send-password-reset-code")
def sendPasswordResetCode(payload: PasswordResetCodeRequest, request: Request) -> dict:
    email = str(payload.email).lower()
    enforceAuthCodeLimits(request, email, "password_reset")
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = datetime.now(UTC)
    with getConnection() as connection:
        existing = connection.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if not existing:
            return {"ok": True}
        connection.execute(
            """
            INSERT INTO email_verification_codes (email, code_hash, purpose, expires_at, created_at)
            VALUES (?, ?, 'password_reset', ?, ?)
            """,
            (
                email,
                hashCode(code),
                (now + timedelta(minutes=10)).replace(microsecond=0).isoformat(),
                now.replace(microsecond=0).isoformat(),
            ),
        )
    sendSystemEmail(email, "CEACStatusBot 重置密码验证码", f"你的重置密码验证码是：{code}\n\n验证码 10 分钟内有效。")
    logSecurityEvent(eventType="password_reset_code_sent", request=request, email=email)
    return {"ok": True}


@app.post("/api/auth/reset-password")
def resetPassword(payload: PasswordResetRequest, request: Request) -> dict:
    email = str(payload.email).lower()
    hashes = requestActorHashes(request, email)
    enforceRateLimit(
        request=request,
        scope="password_reset_submit_ip_device",
        subject=f"{hashes['ip_hash']}:{hashes['device_hash']}",
        limit=10,
        windowSeconds=900,
        eventType="password_reset_rate_limited",
    )
    nowIso = utcNowIso()
    with getConnection() as connection:
        user = connection.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误或已过期")
        codeRow = connection.execute(
            """
            SELECT id, code_hash, expires_at
            FROM email_verification_codes
            WHERE email = ? AND purpose = 'password_reset' AND used_at IS NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (email,),
        ).fetchone()
        if not codeRow or codeRow["code_hash"] != hashCode(payload.code):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误或已过期")
        if datetime.fromisoformat(codeRow["expires_at"]) < datetime.now(UTC):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误或已过期")
        connection.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (hashPassword(payload.password), nowIso, user["id"]),
        )
        connection.execute("UPDATE email_verification_codes SET used_at = ? WHERE id = ?", (nowIso, codeRow["id"]))
        connection.execute(
            "UPDATE user_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
            (nowIso, user["id"]),
        )
    logSecurityEvent(eventType="password_reset_completed", request=request, userId=int(user["id"]), email=email)
    return {"ok": True}


@app.post("/api/auth/register")
def register(payload: RegisterRequest, request: Request, response: Response) -> dict:
    email = str(payload.email).lower()
    hashes = requestActorHashes(request, email)
    enforceRateLimit(
        request=request,
        scope="register_submit_ip_device",
        subject=f"{hashes['ip_hash']}:{hashes['device_hash']}",
        limit=10,
        windowSeconds=900,
        eventType="register_rate_limited",
    )
    nowIso = utcNowIso()
    with getConnection() as connection:
        existing = connection.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已注册")
        codeRow = connection.execute(
            """
            SELECT id, code_hash, expires_at
            FROM email_verification_codes
            WHERE email = ? AND purpose = 'register' AND used_at IS NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (email,),
        ).fetchone()
        if not codeRow or codeRow["code_hash"] != hashCode(payload.code):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误")
        if datetime.fromisoformat(codeRow["expires_at"]) < datetime.now(UTC):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码已过期")
        cursor = connection.execute(
            """
            INSERT INTO users (email, password_hash, role, account_tier, is_email_verified, created_at, updated_at)
            VALUES (?, ?, 'user', 'standard', 1, ?, ?)
            """,
            (email, hashPassword(payload.password), nowIso, nowIso),
        )
        connection.execute("UPDATE email_verification_codes SET used_at = ? WHERE id = ?", (nowIso, codeRow["id"]))
        user = connection.execute(
            "SELECT id, email, role, account_tier, is_email_verified, created_at FROM users WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    setSessionCookie(response, user, request)
    logSecurityEvent(eventType="register_completed", request=request, userId=int(user["id"]), email=email)
    return {"user": user}


@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request, response: Response) -> dict:
    email = str(payload.email).lower()
    enforceLoginAttemptLimit(request, email)
    with getConnection() as connection:
        user = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not user or not verifyPassword(payload.password, user["password_hash"]):
        recordLoginFailure(request, email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    clearLoginFailures(email)
    if needsPasswordRehash(user["password_hash"]):
        with getConnection() as connection:
            connection.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (hashPassword(payload.password), utcNowIso(), user["id"]),
            )
    publicUser = {
        "id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "account_tier": user["account_tier"],
        "is_email_verified": user["is_email_verified"],
        "created_at": user["created_at"],
    }
    setSessionCookie(response, publicUser, request)
    logSecurityEvent(eventType="login_success", request=request, userId=int(user["id"]), email=email)
    return {"user": publicUser}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict:
    userId = None
    try:
        userId = int(getCurrentUser(request)["id"])
    except HTTPException:
        userId = None
    clearSessionCookie(response, request)
    logSecurityEvent(eventType="logout", request=request, userId=userId)
    return {"ok": True}


@app.get("/api/me")
def me(user: dict = Depends(currentUserDependency)) -> dict:
    return {"user": user}


@app.patch("/api/me")
def updateMe(payload: ProfileUpdateRequest, request: Request, response: Response, user: dict = Depends(currentUserDependency)) -> dict:
    nowIso = utcNowIso()
    with getConnection() as connection:
        privateUser = connection.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        if not privateUser or not verifyPassword(payload.currentPassword, privateUser["password_hash"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码错误")
        nextEmail = str(payload.email).lower() if payload.email else privateUser["email"]
        if nextEmail != privateUser["email"]:
            exists = connection.execute("SELECT id FROM users WHERE email = ? AND id != ?", (nextEmail, user["id"])).fetchone()
            if exists:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已被使用")
        nextPasswordHash = (
            hashPassword(payload.newPassword)
            if payload.newPassword
            else hashPassword(payload.currentPassword) if needsPasswordRehash(privateUser["password_hash"]) else privateUser["password_hash"]
        )
        connection.execute(
            """
            UPDATE users
            SET email = ?, password_hash = ?, updated_at = ?
            WHERE id = ?
            """,
            (nextEmail, nextPasswordHash, nowIso, user["id"]),
        )
        publicUser = connection.execute(
            "SELECT id, email, role, account_tier, is_email_verified, created_at FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()
    clearSessionCookie(response, request)
    setSessionCookie(response, publicUser, request)
    logSecurityEvent(
        eventType="profile_updated",
        request=request,
        userId=int(user["id"]),
        email=nextEmail,
        detail={"emailChanged": nextEmail != privateUser["email"], "passwordChanged": bool(payload.newPassword)},
    )
    return {"user": publicUser}


@app.get("/api/cases")
def apiListCases(user: dict = Depends(currentUserDependency)) -> dict:
    return {"cases": listCases(int(user["id"]))}


@app.post("/api/cases")
def apiCreateCase(payload: CeacCaseInput, user: dict = Depends(currentUserDependency)) -> dict:
    try:
        case = createCase(int(user["id"]), payload)
        initialQueryJob = None
        if payload.isEnabled:
            job = enqueueCaseQuery(int(case["id"]), "automatic", int(user["id"]))
            if job:
                initialQueryJob = {"jobId": job["id"], "status": job["status"]}
        return {"case": case, "initialQueryJob": initialQueryJob}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.patch("/api/cases/{caseId}")
def apiPatchCase(caseId: int, payload: CeacCasePatch, user: dict = Depends(currentUserDependency)) -> dict:
    try:
        case = patchCase(caseId, int(user["id"]), payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="签证档案不存在")
    return {"case": case}


@app.delete("/api/cases/{caseId}")
def apiDeleteCase(caseId: int, user: dict = Depends(currentUserDependency)) -> dict:
    if not deleteCase(caseId, int(user["id"])):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="签证档案不存在")
    return {"ok": True}


@app.get("/api/cases/{caseId}/history")
def apiHistory(caseId: int, user: dict = Depends(currentUserDependency)) -> dict:
    if not getCase(caseId, int(user["id"])):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="签证档案不存在")
    return {"history": listHistory(caseId, int(user["id"]))}


@app.post("/api/cases/{caseId}/test-query")
def apiTestQuery(caseId: int, user: dict = Depends(currentUserDependency)) -> dict:
    enforceDailyManualQueryLimit(user)
    job = enqueueCaseQuery(caseId, "manual", int(user["id"]))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="签证档案不存在")
    return {"jobId": job["id"], "status": job["status"]}


@app.get("/api/query-jobs/{jobId}")
def apiQueryJob(jobId: int, user: dict = Depends(currentUserDependency)) -> dict:
    job = getQueryJob(jobId, int(user["id"]))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="查询任务不存在")
    return {"job": job}


@app.post("/api/cases/{caseId}/test-email")
def apiTestEmail(caseId: int, user: dict = Depends(currentUserDependency)) -> dict:
    if not getCase(caseId, int(user["id"])):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="签证档案不存在")
    payload = sendCurrentStatusEmail(caseId, int(user["id"]))
    if not payload["success"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=payload["error"])
    return payload


@app.get("/api/cases/{caseId}/passport-slot-monitor")
def apiPassportSlotMonitor(caseId: int, user: dict = Depends(currentUserDependency)) -> dict:
    if not getCase(caseId, int(user["id"])):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="签证档案不存在")
    return {
        "monitor": getPassportSlotMonitor(caseId, int(user["id"])),
        "history": listPassportSlotHistory(caseId, int(user["id"])),
    }


@app.put("/api/cases/{caseId}/passport-slot-monitor")
def apiSavePassportSlotMonitor(caseId: int, payload: PassportSlotMonitorInput, user: dict = Depends(currentUserDependency)) -> dict:
    try:
        monitor = upsertPassportSlotMonitor(
            caseId,
            int(user["id"]),
            payload.identifier,
            payload.isEnabled,
            payload.emailNotificationsEnabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not monitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="签证档案不存在")
    return {"monitor": monitor}


@app.patch("/api/cases/{caseId}/passport-slot-monitor")
def apiPatchPassportSlotMonitor(caseId: int, payload: PassportSlotMonitorPatch, user: dict = Depends(currentUserDependency)) -> dict:
    monitor = patchPassportSlotMonitor(
        caseId,
        int(user["id"]),
        isEnabled=payload.isEnabled,
        emailNotificationsEnabled=payload.emailNotificationsEnabled,
    )
    if not monitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="护照预约监控不存在")
    return {"monitor": monitor}


@app.post("/api/cases/{caseId}/passport-slot-monitor/test-query")
def apiTestPassportSlotMonitor(caseId: int, user: dict = Depends(currentUserDependency)) -> dict:
    enforceDailyManualQueryLimit(user)
    job = enqueuePassportSlotQuery(caseId, "passport_slot_manual", int(user["id"]))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="护照预约监控不存在")
    return {"jobId": job["id"], "status": job["status"]}


@app.post("/api/cases/{caseId}/passport-slot-monitor/test-email")
def apiTestPassportSlotMonitorEmail(caseId: int, user: dict = Depends(currentUserDependency)) -> dict:
    payload = sendCurrentPassportSlotEmail(caseId, int(user["id"]))
    if not payload["success"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=payload["error"])
    return payload


@app.get("/api/admin/users")
def adminUsers(_: dict = Depends(adminDependency)) -> dict:
    with getConnection() as connection:
        users = connection.execute(
            """
            SELECT
                u.id,
                u.email,
                u.role,
                u.account_tier,
                u.worker_priority,
                u.is_email_verified,
                u.created_at,
                u.updated_at,
                COUNT(c.id) AS case_count,
                MAX(c.last_checked_at) AS last_checked_at
            FROM users u
            LEFT JOIN ceac_cases c ON c.user_id = u.id
            GROUP BY u.id
            ORDER BY u.id ASC
            """,
        ).fetchall()
    return {"users": users}


@app.patch("/api/admin/users/{userId}/worker-priority")
def adminPatchUserWorkerPriority(userId: int, payload: WorkerPriorityPatch, request: Request, admin: dict = Depends(adminDependency)) -> dict:
    user = updateUserWorkerPriority(userId, payload.workerPriority)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    logSecurityEvent(
        eventType="admin_worker_priority_updated",
        request=request,
        userId=int(admin["id"]),
        detail={"targetUserId": userId, "workerPriority": payload.workerPriority},
    )
    return {"user": user}


@app.patch("/api/admin/users/{userId}/account-tier")
def adminPatchUserAccountTier(userId: int, payload: AccountTierPatch, request: Request, admin: dict = Depends(adminDependency)) -> dict:
    user = updateUserAccountTier(userId, payload.accountTier)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    logSecurityEvent(
        eventType="admin_account_tier_updated",
        request=request,
        userId=int(admin["id"]),
        detail={"targetUserId": userId, "accountTier": payload.accountTier},
    )
    return {"user": user}


@app.get("/api/admin/cases")
def adminCases(_: dict = Depends(adminDependency)) -> dict:
    return {"cases": listCases()}


@app.post("/api/admin/cases/{caseId}/restore-ceac-auto-query")
def adminRestoreCaseAutomaticQuery(caseId: int, _: dict = Depends(adminDependency)) -> dict:
    case = restoreCaseAutomaticQuery(caseId)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="签证档案不存在")
    return {"case": case}


@app.get("/api/admin/cases/{caseId}/history")
def adminCaseHistory(caseId: int, _: dict = Depends(adminDependency)) -> dict:
    return {"history": listHistory(caseId)}


@app.get("/api/admin/query-runs")
def adminQueryRuns(_: dict = Depends(adminDependency)) -> dict:
    with getConnection() as connection:
        rows = connection.execute(
            """
            SELECT r.*, c.display_name, c.application_num, u.email AS user_email, s.status
            FROM query_runs r
            JOIN ceac_cases c ON c.id = r.case_id
            JOIN users u ON u.id = c.user_id
            LEFT JOIN status_catalog s ON s.id = r.status_id
            ORDER BY r.id DESC
            LIMIT 200
            """,
        ).fetchall()
    return {"runs": listCasesForQueryRuns(rows)}


@app.get("/api/admin/security-events")
def adminSecurityEvents(limit: int = 200, _: dict = Depends(adminDependency)) -> dict:
    return {"events": listSecurityEvents(limit)}


@app.get("/api/admin/system-email")
def adminSystemEmail(_: dict = Depends(adminDependency)) -> dict:
    return {"config": getSystemSmtpConfigPublic()}


@app.put("/api/admin/system-email")
def adminSaveSystemEmail(payload: SystemSmtpConfigInput, _: dict = Depends(adminDependency)) -> dict:
    try:
        config = saveSystemSmtpConfig(
            fromEmail=str(payload.fromEmail),
            host=payload.host,
            port=payload.port,
            useSsl=payload.useSsl,
            password=payload.password,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"config": config}
