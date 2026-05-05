from pydantic import BaseModel, Field


class SendCodeRequest(BaseModel):
    email: str = Field(min_length=3)


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)
    code: str = Field(min_length=4, max_length=12)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str


class SmtpConfigInput(BaseModel):
    fromEmail: str = Field(min_length=3)
    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    useSsl: bool = True
    password: str = Field(min_length=1)


class CeacCaseInput(BaseModel):
    displayName: str = Field(min_length=1, max_length=80)
    location: str = Field(min_length=1)
    applicationNum: str = Field(min_length=1)
    passportNumber: str = Field(min_length=1)
    surname: str = Field(min_length=1, max_length=5)
    receiveEmail: str = Field(min_length=3)
    senderMode: str = Field(pattern="^(system|custom)$")
    isEnabled: bool = True
    emailNotificationsEnabled: bool = True
    smtpConfig: SmtpConfigInput | None = None


class CeacCasePatch(BaseModel):
    displayName: str | None = Field(default=None, min_length=1, max_length=80)
    location: str | None = None
    applicationNum: str | None = None
    passportNumber: str | None = None
    surname: str | None = Field(default=None, min_length=1, max_length=5)
    receiveEmail: str | None = Field(default=None, min_length=3)
    senderMode: str | None = Field(default=None, pattern="^(system|custom)$")
    isEnabled: bool | None = None
    emailNotificationsEnabled: bool | None = None
    smtpConfig: SmtpConfigInput | None = None
