from datetime import UTC, datetime, timedelta
import secrets

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

from .case_service import (
    createCase,
    deleteCase,
    getCase,
    listCases,
    listHistory,
    patchCase,
    runCaseQuery,
    sendCurrentStatusEmail,
)
from .config import getSettings
from .database import getConnection, initializeDatabase, utcNowIso
from .mailer import getSystemSmtpConfigPublic, saveSystemSmtpConfig, sendSystemEmail
from .schemas import (
    CeacCaseInput,
    CeacCasePatch,
    LoginRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    SendCodeRequest,
    SystemSmtpConfigInput,
)
from .security import (
    clearSessionCookie,
    getCurrentUser,
    hashCode,
    hashPassword,
    requireAdmin,
    seedDefaultUsers,
    setSessionCookie,
    verifyPassword,
)


app = FastAPI(title="CEACStatusBot Web", version="1.0.0")
settings = getSettings()
scheduler = BackgroundScheduler(timezone="UTC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.corsOrigins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def currentUserDependency(request: Request) -> dict:
    return getCurrentUser(request)


def adminDependency(request: Request) -> dict:
    return requireAdmin(request)


def runDueCases() -> None:
    nowIso = datetime.now(UTC).replace(microsecond=0).isoformat()
    with getConnection() as connection:
        rows = connection.execute(
            """
            SELECT id FROM ceac_cases
            WHERE is_enabled = 1
              AND next_check_at IS NOT NULL
              AND next_check_at <= ?
            ORDER BY next_check_at ASC
            LIMIT 20
            """,
            (nowIso,),
        ).fetchall()
    for row in rows:
        try:
            runCaseQuery(int(row["id"]))
        except Exception as exc:
            print(f"[scheduler] case {row['id']} failed: {exc}")


@app.on_event("startup")
def onStartup() -> None:
    initializeDatabase()
    seedDefaultUsers()
    if not scheduler.running:
        scheduler.add_job(runDueCases, "interval", minutes=1, id="run-due-cases", replace_existing=True)
        scheduler.start()


@app.on_event("shutdown")
def onShutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/auth/send-code")
def sendCode(payload: SendCodeRequest) -> dict:
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = datetime.now(UTC)
    with getConnection() as connection:
        existing = connection.execute("SELECT id FROM users WHERE email = ?", (payload.email,)).fetchone()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已注册")
        connection.execute(
            """
            INSERT INTO email_verification_codes (email, code_hash, purpose, expires_at, created_at)
            VALUES (?, ?, 'register', ?, ?)
            """,
            (
                payload.email,
                hashCode(code),
                (now + timedelta(minutes=10)).replace(microsecond=0).isoformat(),
                now.replace(microsecond=0).isoformat(),
            ),
        )
    sendSystemEmail(payload.email, "CEACStatusBot 注册验证码", f"你的注册验证码是：{code}\n\n验证码 10 分钟内有效。")
    return {"ok": True}


@app.post("/api/auth/register")
def register(payload: RegisterRequest, response: Response) -> dict:
    nowIso = utcNowIso()
    with getConnection() as connection:
        existing = connection.execute("SELECT id FROM users WHERE email = ?", (payload.email,)).fetchone()
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
            (payload.email,),
        ).fetchone()
        if not codeRow or codeRow["code_hash"] != hashCode(payload.code):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误")
        if datetime.fromisoformat(codeRow["expires_at"]) < datetime.now(UTC):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码已过期")
        cursor = connection.execute(
            """
            INSERT INTO users (email, password_hash, role, is_email_verified, created_at, updated_at)
            VALUES (?, ?, 'user', 1, ?, ?)
            """,
            (payload.email, hashPassword(payload.password), nowIso, nowIso),
        )
        connection.execute("UPDATE email_verification_codes SET used_at = ? WHERE id = ?", (nowIso, codeRow["id"]))
        user = connection.execute(
            "SELECT id, email, role, is_email_verified, created_at FROM users WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    setSessionCookie(response, user)
    return {"user": user}


@app.post("/api/auth/login")
def login(payload: LoginRequest, response: Response) -> dict:
    with getConnection() as connection:
        user = connection.execute("SELECT * FROM users WHERE email = ?", (payload.email,)).fetchone()
    if not user or not verifyPassword(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    publicUser = {
        "id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "is_email_verified": user["is_email_verified"],
        "created_at": user["created_at"],
    }
    setSessionCookie(response, publicUser)
    return {"user": publicUser}


@app.post("/api/auth/logout")
def logout(response: Response) -> dict:
    clearSessionCookie(response)
    return {"ok": True}


@app.get("/api/me")
def me(user: dict = Depends(currentUserDependency)) -> dict:
    return {"user": user}


@app.patch("/api/me")
def updateMe(payload: ProfileUpdateRequest, response: Response, user: dict = Depends(currentUserDependency)) -> dict:
    nowIso = utcNowIso()
    with getConnection() as connection:
        privateUser = connection.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        if not privateUser or not verifyPassword(payload.currentPassword, privateUser["password_hash"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码错误")
        nextEmail = payload.email.strip() if payload.email else privateUser["email"]
        if nextEmail != privateUser["email"]:
            exists = connection.execute("SELECT id FROM users WHERE email = ? AND id != ?", (nextEmail, user["id"])).fetchone()
            if exists:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已被使用")
        nextPasswordHash = hashPassword(payload.newPassword) if payload.newPassword else privateUser["password_hash"]
        connection.execute(
            """
            UPDATE users
            SET email = ?, password_hash = ?, updated_at = ?
            WHERE id = ?
            """,
            (nextEmail, nextPasswordHash, nowIso, user["id"]),
        )
        publicUser = connection.execute(
            "SELECT id, email, role, is_email_verified, created_at FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()
    setSessionCookie(response, publicUser)
    return {"user": publicUser}


@app.get("/api/cases")
def apiListCases(user: dict = Depends(currentUserDependency)) -> dict:
    return {"cases": listCases(int(user["id"]))}


@app.post("/api/cases")
def apiCreateCase(payload: CeacCaseInput, user: dict = Depends(currentUserDependency)) -> dict:
    return {"case": createCase(int(user["id"]), payload)}


@app.patch("/api/cases/{caseId}")
def apiPatchCase(caseId: int, payload: CeacCasePatch, user: dict = Depends(currentUserDependency)) -> dict:
    case = patchCase(caseId, int(user["id"]), payload)
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
    if not getCase(caseId, int(user["id"])):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="签证档案不存在")
    return runCaseQuery(caseId)


@app.post("/api/cases/{caseId}/test-email")
def apiTestEmail(caseId: int, user: dict = Depends(currentUserDependency)) -> dict:
    if not getCase(caseId, int(user["id"])):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="签证档案不存在")
    payload = sendCurrentStatusEmail(caseId, int(user["id"]))
    if not payload["success"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=payload["error"])
    return payload


@app.get("/api/admin/users")
def adminUsers(_: dict = Depends(adminDependency)) -> dict:
    with getConnection() as connection:
        users = connection.execute(
            "SELECT id, email, role, is_email_verified, created_at, updated_at FROM users ORDER BY id ASC",
        ).fetchall()
    return {"users": users}


@app.get("/api/admin/cases")
def adminCases(_: dict = Depends(adminDependency)) -> dict:
    return {"cases": listCases()}


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
    return {"runs": rows}


@app.get("/api/admin/system-email")
def adminSystemEmail(_: dict = Depends(adminDependency)) -> dict:
    return {"config": getSystemSmtpConfigPublic()}


@app.put("/api/admin/system-email")
def adminSaveSystemEmail(payload: SystemSmtpConfigInput, _: dict = Depends(adminDependency)) -> dict:
    try:
        config = saveSystemSmtpConfig(
            fromEmail=payload.fromEmail,
            host=payload.host,
            port=payload.port,
            useSsl=payload.useSsl,
            password=payload.password,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"config": config}
