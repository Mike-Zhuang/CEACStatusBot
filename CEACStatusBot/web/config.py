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
        self.cookieSecure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
        self.allowedHosts = [
            host.strip()
            for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,ceac.mikezhuang.cn").split(",")
            if host.strip()
        ]
        self.trustedProxyIps = {
            ip.strip()
            for ip in os.getenv("TRUSTED_PROXY_IPS", "127.0.0.1,::1").split(",")
            if ip.strip()
        }
        self.apiMaxBodyBytes = max(1024, int(os.getenv("API_MAX_BODY_BYTES", "131072")))
        self.sessionIdleTimeoutMinutes = max(5, int(os.getenv("SESSION_IDLE_TIMEOUT_MINUTES", "720")))
        self.sessionAbsoluteTimeoutDays = max(1, int(os.getenv("SESSION_ABSOLUTE_TIMEOUT_DAYS", "14")))
        self.authLoginIpDeviceLimitPerMinute = max(1, int(os.getenv("AUTH_LOGIN_IP_DEVICE_LIMIT_PER_MINUTE", "10")))
        self.authLoginEmailFailureLimitPer15Minutes = max(1, int(os.getenv("AUTH_LOGIN_EMAIL_FAILURE_LIMIT_PER_15_MINUTES", "5")))
        self.authCodeEmailLimitPerHour = max(1, int(os.getenv("AUTH_CODE_EMAIL_LIMIT_PER_HOUR", "3")))
        self.authCodeIpDeviceLimitPer10Minutes = max(1, int(os.getenv("AUTH_CODE_IP_DEVICE_LIMIT_PER_10_MINUTES", "3")))
        self.standardApiLimitPerMinute = max(1, int(os.getenv("STANDARD_API_LIMIT_PER_MINUTE", "120")))
        self.premiumApiLimitPerMinute = max(1, int(os.getenv("PREMIUM_API_LIMIT_PER_MINUTE", "300")))
        self.adminApiLimitPerMinute = max(1, int(os.getenv("ADMIN_API_LIMIT_PER_MINUTE", "600")))
        self.workerPollIntervalSeconds = max(1, int(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "1")))
        self.standardDailyManualQueryLimit = max(1, int(os.getenv("STANDARD_DAILY_MANUAL_QUERY_LIMIT", "1")))
        self.premiumDailyManualQueryLimit = max(1, int(os.getenv("PREMIUM_DAILY_MANUAL_QUERY_LIMIT", "1000")))
        self.standardDailyEmailLimit = max(1, int(os.getenv("STANDARD_DAILY_EMAIL_LIMIT", "5")))
        self.premiumDailyEmailLimit = max(1, int(os.getenv("PREMIUM_DAILY_EMAIL_LIMIT", "1000")))

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
