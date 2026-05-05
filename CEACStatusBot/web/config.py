import os
import base64
import hashlib
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv


load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.databasePath = Path(os.getenv("DATABASE_PATH", "ceacstatusbot.sqlite3"))
        self.secretKey = os.getenv("SECRET_KEY", "change-this-secret-before-public-deploy")
        self.credentialKeyFile = os.getenv("CREDENTIAL_KEY_FILE", "")
        self.encryptionKey = os.getenv("ENCRYPTION_KEY", "")
        self.systemSmtpHost = os.getenv("SYSTEM_SMTP_HOST", "smtp.exmail.qq.com")
        self.systemSmtpPort = int(os.getenv("SYSTEM_SMTP_PORT", "465"))
        self.systemSmtpUseSsl = os.getenv("SYSTEM_SMTP_USE_SSL", "true").lower() == "true"
        self.systemFromEmail = os.getenv("SYSTEM_FROM_EMAIL", "")
        self.systemEmailPassword = os.getenv("SYSTEM_EMAIL_PASSWORD", "")
        self.appBaseUrl = os.getenv("APP_BASE_URL", "http://localhost:5173")
        self.seedDefaultUsers = os.getenv("SEED_DEFAULT_USERS", "false").lower() == "true"
        self.defaultAdminEmail = os.getenv("DEFAULT_ADMIN_EMAIL", "")
        self.defaultAdminPassword = os.getenv("DEFAULT_ADMIN_PASSWORD", "")
        self.defaultUserEmail = os.getenv("DEFAULT_USER_EMAIL", "")
        self.defaultUserPassword = os.getenv("DEFAULT_USER_PASSWORD", "")
        self.corsOrigins = [
            origin.strip()
            for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
            if origin.strip()
        ]
        self.csrfTrustedOrigins = [
            origin.strip().rstrip("/")
            for origin in os.getenv(
                "CSRF_TRUSTED_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173",
            ).split(",")
            if origin.strip()
        ]
        self.workerPollIntervalSeconds = max(1, int(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "3")))

    def getFernet(self) -> Fernet:
        key = self.encryptionKey
        if not key:
            # 本地开发默认从 SECRET_KEY 派生稳定密钥；公网部署建议显式设置 ENCRYPTION_KEY。
            keyBytes = hashlib.sha256(self.secretKey.encode()).digest()
            key = base64.urlsafe_b64encode(keyBytes).decode()
        return Fernet(key.encode())


@lru_cache(maxsize=1)
def getSettings() -> Settings:
    return Settings()
