import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Mail,
  History,
  LogOut,
  Moon,
  Plus,
  Shield,
  Sun,
  Trash2,
  UserRound,
} from "lucide-react";
import { ceacLocations } from "./locations";

type ThemeMode = "dark" | "light";
type LanguageMode = "zh" | "en";
type ViewMode = "dashboard" | "profile" | "admin";
type AuthMode = "login" | "register" | "forgot";

interface User {
  id: number;
  email: string;
  role: "admin" | "user";
  is_email_verified: number;
  created_at: string;
}

interface CeacCase {
  id: number;
  userId: number;
  displayName: string;
  location: string;
  applicationNum: string;
  passportNumber: string;
  surname: string;
  receiveEmail: string;
  senderMode: "system" | "custom";
  isEnabled: boolean;
  emailNotificationsEnabled: boolean;
  nextCheckAt: string | null;
  lastCheckedAt: string | null;
  lastTriggerType: "manual" | "automatic" | "unknown" | null;
  lastStatus: string | null;
  lastDescription: string | null;
  createdAt: string;
  updatedAt: string;
}

interface HistoryItem {
  id: number;
  caseId: number;
  status: string;
  description: string;
  ceacLastUpdated: string;
  visaType: string;
  caseCreated: string;
  fetchedAt: string;
}

interface QueryRun {
  id: number;
  case_id: number;
  display_name: string;
  application_num: string;
  user_email: string;
  started_at: string;
  finished_at: string;
  trigger_type: "manual" | "automatic" | "passport_slot_manual" | "passport_slot_automatic" | "unknown";
  success: number;
  status: string | null;
  error_message: string;
  duration_ms: number;
}

interface QueryJob {
  id: number;
  caseId: number;
  triggerType: "manual" | "automatic" | "passport_slot_manual" | "passport_slot_automatic";
  status: "queued" | "running" | "succeeded" | "failed";
  attempts: number;
  errorMessage: string;
  result: {
    success: boolean;
    changed: boolean;
    error: string;
  } | null;
  createdAt: string;
  updatedAt: string;
  startedAt: string | null;
  finishedAt: string | null;
}

interface PassportSlotMonitor {
  id: number;
  caseId: number;
  identifier: string;
  identifierMasked: string;
  isEnabled: boolean;
  emailNotificationsEnabled: boolean;
  nextCheckAt: string | null;
  lastCheckedAt: string | null;
  lastSlotFingerprint: string;
  lastSlotCount: number;
  lastResult: {
    success?: boolean;
    availableSlots?: unknown[];
    availableDates?: unknown[];
    raw?: unknown;
    error?: string;
  } | null;
  lastErrorMessage: string;
  createdAt: string;
  updatedAt: string;
}

interface PassportSlotHistoryItem {
  id: number;
  caseId: number;
  slotFingerprint: string;
  slotCount: number;
  rawPayload: Record<string, unknown>;
  fetchedAt: string;
  notificationSent: boolean;
}

interface AdminUser {
  id: number;
  email: string;
  role: "admin" | "user";
  is_email_verified: number;
  created_at: string;
  updated_at: string;
  case_count: number;
  last_checked_at: string | null;
}

interface SystemEmailConfig {
  fromEmail: string;
  host: string;
  port: number;
  useSsl: boolean;
  source: "database" | "environment";
  isConfigured: boolean;
  hasPassword: boolean;
}

interface SystemEmailForm {
  fromEmail: string;
  host: string;
  port: string;
  useSsl: boolean;
  password: string;
}

interface ProfileForm {
  email: string;
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

interface CaseForm {
  displayName: string;
  location: string;
  applicationNum: string;
  passportNumber: string;
  surname: string;
  receiveEmail: string;
  senderMode: "system" | "custom";
  isEnabled: boolean;
  emailNotificationsEnabled: boolean;
  smtpFromEmail: string;
  smtpHost: string;
  smtpPort: string;
  smtpUseSsl: boolean;
  smtpPassword: string;
}

const emptyCaseForm: CaseForm = {
  displayName: "",
  location: "CHINA, BEIJING",
  applicationNum: "",
  passportNumber: "",
  surname: "",
  receiveEmail: "",
  senderMode: "system",
  isEnabled: true,
  emailNotificationsEnabled: true,
  smtpFromEmail: "",
  smtpHost: "smtp.exmail.qq.com",
  smtpPort: "465",
  smtpUseSsl: true,
  smtpPassword: "",
};

const icpRecordNumber = import.meta.env.VITE_ICP_RECORD_NUMBER as string | undefined;

const translations = {
  en: {
    admin: "Admin",
    adminTitle: "Admin Console",
    adminUsers: "Users",
    appSubtitle: "Visa status monitoring, query history, and email delivery.",
    applicationId: "Application ID or Case Number",
    autoMonitor: "Enable automatic monitoring",
    caseCreated: "Visa profile created.",
    caseList: "Profiles",
    caseName: "Profile name",
    caseNamePlaceholder: "e.g. Beijing F1 interview",
    casesOwned: "Profiles",
    changeContent: "Change",
    confirmDelete: "Delete this profile?",
    createdAt: "Created",
    currentLogin: "Signed in as",
    dashboard: "My Profiles",
    deliveryEmail: "Notification email",
    deliverySection: "Email delivery",
    duration: "Duration",
    email: "Email",
    emailPushOff: "Email updates off",
    emailPushOn: "Email updates on",
    emailPushSetting: "Send email when status changes",
    error: "Failed",
    executor: "User",
    fastQuery: "Quick query",
    fastQueryChanged: "Quick query completed: status changed",
    fastQueryUnchanged: "Quick query completed: status unchanged",
    firstFiveSurname: "First 5 Letters of Surname",
    firstFiveSurnameHint: "Enter only the first 5 letters of your surname. If shorter, enter the full surname.",
    forgotPassword: "Forgot password?",
    lastCheckMode: "Last query mode",
    lastCheckedAt: "Last updated",
    lastQuery: "Last query",
    location: "Select a location",
    locationMetric: "Location",
    keepPasswordPlaceholder: "Leave blank to keep current password",
    login: "Sign in",
    loginAction: "Sign in",
    logoutTitle: "Sign out",
    missingCaseNumber: "No case number",
    noCases: "No profiles yet",
    noHistory: "No status history yet",
    noLogs: "No logs yet",
    noStatus: "Not ready",
    noStatusChange: "No status change",
    issuedSlowQueryNotice: "This profile is Issued. Automatic checks are now weekly and will stop automatically after one week if you do not stop them here.",
    stopAutomaticQuery: "Stop automatic checks",
    automaticQueryStopped: "Automatic checks stopped. You can still run quick queries manually.",
    notVerified: "Not verified",
    newProfile: "New",
    nextCheckAt: "Next automatic query",
    notifyEmail: "Notification email",
    officialIntro: "Welcome! On this website, you can check your U.S. visa application status.",
    passport: "Passport Number",
    passportPlaceholder: "Passport Number or NA",
    password: "Password",
    passwordOrCode: "Password / App password",
    personalInfo: "Account",
    profile: "Profile",
    profileSaved: "Account updated.",
    refresh: "Refresh",
    register: "Register",
    registerAction: "Create account",
    rememberLogin: "Remember email and password",
    rememberPassword: "Remember password",
    resetAction: "Reset password",
    resetCodeSent: "If this email exists, a reset code has been sent.",
    resetPassword: "Reset password",
    resetPasswordSaved: "Password has been reset. Please sign in.",
    resetPasswordMismatch: "The two passwords do not match.",
    requestFailed: "Request failed",
    save: "Save profile",
    send: "Send",
    sendCodeFailed: "Failed to send verification code",
    senderConfig: "Sender configuration",
    signInFailed: "Operation failed",
    smtpEmail: "Sender email",
    smtpHost: "SMTP server",
    smtpPort: "SMTP port",
    status: "Status",
    statusHistory: "Status history",
    statusMonitoring: "Visa Status Check",
    success: "Success",
    systemLogs: "System query logs",
    systemEmail: "Default sender email",
    systemEmailConfigured: "Configured",
    systemEmailNotConfigured: "Not configured",
    systemEmailSaved: "Default sender email saved.",
    systemEmailSource: "Source",
    systemSender: "System sender",
    testEmail: "Test email",
    testEmailSending: "Sending current status email.",
    testEmailSent: "Test email sent with the current status template.",
    themeToDark: "Switch to dark mode",
    themeToLight: "Switch to light mode",
    updatePushDisabled: "Status update emails disabled.",
    updatePushEnabled: "Status update emails enabled.",
    updatedAt: "Updated",
    useCustomSmtp: "Custom SMTP",
    useSsl: "Use SSL",
    triggerAutomatic: "Automatic",
    triggerManual: "Manual",
    triggerUnknown: "Unknown",
    verificationCode: "Verification code",
    verificationCodeSent: "Verification code sent. Please check your mailbox.",
    verified: "Verified",
    visaApplicationType: "Visa Application Type",
    visaTypeNiv: "Nonimmigrant Visa (NIV)",
    waitFirstQuery: "Waiting for first query",
    queryHint: "Please select a location and enter your Application ID or Case Number.",
    queryInProgress: "Querying CEAC. Please wait.",
    pre2022Note: "NOTE: For applicants who completed their forms prior to January 1, 2022, please put NA into the Passport and Surname fields.",
    passportSlotMonitor: "Passport appointment monitor",
    passportSlotIntro: "Enter your UID or HAL after Approved or Issued to watch GTS appointment slots.",
    passportSlotEarlyHint: "You can configure this now, but GTS usually returns valid tokens after Approved or Issued.",
    passportSlotIdentifier: "UID or HAL",
    passportSlotIdentifierPlaceholder: "106417002 or HAL0123456789",
    passportSlotSave: "Save monitor",
    passportSlotSaved: "Passport appointment monitor saved.",
    passportSlotEnabled: "GTS monitor enabled.",
    passportSlotDisabled: "GTS monitor disabled.",
    passportSlotEmailEnabled: "GTS slot email notifications enabled.",
    passportSlotEmailDisabled: "GTS slot email notifications disabled.",
    passportSlotManualQuery: "Check slots now",
    passportSlotTestEmail: "Test GTS email",
    passportSlotTestEmailSending: "Sending GTS monitor test email.",
    passportSlotTestEmailSent: "GTS monitor test email sent.",
    passportSlotQuerying: "Querying GTS slots. Please wait.",
    passportSlotFound: "GTS slot query completed: available slots found.",
    passportSlotNotFound: "GTS slot query completed: no available slot.",
    passportSlotChanged: "GTS slot result changed.",
    passportSlotConfigured: "Configured identifier",
    passportSlotLastCount: "Last slot count",
    passportSlotLastError: "Last GTS error",
    passportSlotHistory: "Slot change history",
    noPassportSlotMonitor: "No UID/HAL monitor yet",
    noPassportSlotHistory: "No slot changes yet",
  },
  zh: {
    admin: "管理员",
    adminTitle: "管理后台",
    adminUsers: "用户资料",
    appSubtitle: "签证状态监控、查询历史与邮件提醒。",
    applicationId: "Application ID 或 Case Number",
    autoMonitor: "启用自动监控",
    caseCreated: "签证档案已创建。",
    caseList: "档案列表",
    caseName: "档案名称",
    caseNamePlaceholder: "例如：北京 F1 面签",
    casesOwned: "档案数量",
    changeContent: "变更内容",
    confirmDelete: "确认删除此档案？",
    createdAt: "创建时间",
    currentLogin: "当前登录",
    dashboard: "我的档案",
    deliveryEmail: "接收提醒邮箱",
    deliverySection: "邮件发送",
    duration: "耗时",
    email: "邮箱",
    emailPushOff: "邮件推送关闭",
    emailPushOn: "邮件推送开启",
    emailPushSetting: "状态更新时发送邮件推送",
    error: "失败",
    executor: "执行人",
    fastQuery: "快速查询",
    fastQueryChanged: "快速查询完成：状态已更新",
    fastQueryUnchanged: "快速查询完成：状态未变化",
    firstFiveSurname: "姓的前 5 个字母",
    firstFiveSurnameHint: "只填写姓氏前 5 个英文字母；不足 5 个按实际姓氏填写。",
    forgotPassword: "忘记密码？",
    lastCheckMode: "上次抓取方式",
    lastCheckedAt: "上次更新时间",
    lastQuery: "最近查询",
    location: "选择面签地点",
    locationMetric: "办理地点",
    keepPasswordPlaceholder: "留空则保留当前授权码",
    login: "登录",
    loginAction: "登录控制台",
    logoutTitle: "退出登录",
    missingCaseNumber: "未提供流水号",
    noCases: "尚未添加档案",
    noHistory: "暂无历史状态记录",
    noLogs: "暂无日志",
    noStatus: "未就绪",
    noStatusChange: "未发生状态变更",
    issuedSlowQueryNotice: "此档案已进入 Issued，自动查询已降频为每周一次；如果你一周内未手动停止，系统将自动停止并邮件通知你。",
    stopAutomaticQuery: "停止自动查询",
    automaticQueryStopped: "已停止自动查询，你仍然可以手动快速查询。",
    notVerified: "未验证",
    newProfile: "新增",
    nextCheckAt: "下次自动查询",
    notifyEmail: "接收邮箱",
    officialIntro: "欢迎！你可以在这里查询美国签证申请状态。",
    passport: "护照号码",
    passportPlaceholder: "护照号码或 NA",
    password: "密码",
    passwordOrCode: "密码 / 授权码",
    personalInfo: "个人信息",
    profile: "案卷",
    profileSaved: "个人信息已更新。",
    refresh: "刷新数据",
    register: "注册",
    registerAction: "创建账号",
    rememberLogin: "记住账号和密码",
    rememberPassword: "记住密码",
    resetAction: "重置密码",
    resetCodeSent: "如果该邮箱存在，重置验证码已发送。",
    resetPassword: "重置密码",
    resetPasswordSaved: "密码已重置，请重新登录。",
    resetPasswordMismatch: "两次输入的新密码不一致。",
    requestFailed: "请求失败",
    save: "保存档案",
    send: "发送",
    sendCodeFailed: "验证码发送失败",
    senderConfig: "发件人配置",
    signInFailed: "操作失败",
    smtpEmail: "发件邮箱",
    smtpHost: "SMTP 服务器",
    smtpPort: "SMTP 端口",
    status: "状态",
    statusHistory: "状态历史",
    statusMonitoring: "Visa Status Check",
    success: "成功",
    systemLogs: "系统监控日志",
    systemEmail: "默认发信邮箱",
    systemEmailConfigured: "已配置",
    systemEmailNotConfigured: "未配置",
    systemEmailSaved: "默认发信邮箱已保存。",
    systemEmailSource: "来源",
    systemSender: "系统发信",
    testEmail: "测试发信",
    testEmailSending: "正在发送现有状态邮件。",
    testEmailSent: "测试邮件已按当前状态模板发送。",
    themeToDark: "切换至暗色模式",
    themeToLight: "切换至亮色模式",
    updatePushDisabled: "已关闭状态更新邮件推送。",
    updatePushEnabled: "已开启状态更新邮件推送。",
    updatedAt: "更新时间",
    useCustomSmtp: "自定义 SMTP",
    useSsl: "启用 SSL",
    triggerAutomatic: "自动抓取",
    triggerManual: "手动抓取",
    triggerUnknown: "未知",
    verificationCode: "验证码",
    verificationCodeSent: "验证码已发送，请查看邮箱。",
    verified: "已验证",
    visaApplicationType: "Visa Application Type",
    visaTypeNiv: "非移民签证（NIV）",
    waitFirstQuery: "等待首次查询",
    queryHint: "请选择面签地点，并输入你的 Application ID 或 Case Number。",
    queryInProgress: "正在查询 CEAC，请稍候。",
    pre2022Note: "注意：如果你在 2022 年 1 月 1 日之前完成表格，请在护照号码和姓氏字段填写 NA。",
    passportSlotMonitor: "护照预约监控",
    passportSlotIntro: "Approved 或 Issued 后填写 UID/HAL，系统会轮询 GTS 可预约时间。",
    passportSlotEarlyHint: "你可以提前配置；但 GTS 通常在 Approved 或 Issued 后才会返回有效 token。",
    passportSlotIdentifier: "UID 或 HAL",
    passportSlotIdentifierPlaceholder: "106417002 或 HAL0123456789",
    passportSlotSave: "保存监控",
    passportSlotSaved: "护照预约监控已保存。",
    passportSlotEnabled: "已开启 GTS 监控。",
    passportSlotDisabled: "已关闭 GTS 监控。",
    passportSlotEmailEnabled: "已开启 GTS slot 邮件推送。",
    passportSlotEmailDisabled: "已关闭 GTS slot 邮件推送。",
    passportSlotManualQuery: "立即查询 slot",
    passportSlotTestEmail: "测试 GTS 邮件",
    passportSlotTestEmailSending: "正在发送 GTS 监控测试邮件。",
    passportSlotTestEmailSent: "GTS 监控测试邮件已发送。",
    passportSlotQuerying: "正在查询 GTS slot，请稍候。",
    passportSlotFound: "GTS slot 查询完成：发现可预约时间。",
    passportSlotNotFound: "GTS slot 查询完成：暂无可预约时间。",
    passportSlotChanged: "GTS slot 结果发生变化。",
    passportSlotConfigured: "已配置编号",
    passportSlotLastCount: "最近 slot 数量",
    passportSlotLastError: "最近 GTS 错误",
    passportSlotHistory: "slot 变化历史",
    noPassportSlotMonitor: "尚未配置 UID/HAL 监控",
    noPassportSlotHistory: "暂无 slot 变化记录",
  },
} as const;

type TranslationKey = keyof typeof translations.en;

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
      throw new Error(payload.detail ?? "Request failed");
  }
  return payload as T;
}

function getInitialTheme(): ThemeMode {
  const stored = localStorage.getItem("themeMode");
  if (stored === "dark" || stored === "light") {
    return stored;
  }
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

function getInitialLanguage(): LanguageMode {
  const stored = localStorage.getItem("languageMode");
  if (stored === "zh" || stored === "en") {
    return stored;
  }
  return navigator.language.toLowerCase().startsWith("zh") ? "zh" : "en";
}

function formatTime(value: string | null, languageMode: LanguageMode): string {
  if (!value) {
    return languageMode === "zh" ? "尚未记录" : "Not recorded";
  }
  return new Date(value).toLocaleString(languageMode === "zh" ? "zh-CN" : "en-US");
}

function formatTriggerType(value: CeacCase["lastTriggerType"] | QueryRun["trigger_type"], t: (key: TranslationKey) => string): string {
  if (value === "passport_slot_manual") {
    return `${t("passportSlotMonitor")} · ${t("triggerManual")}`;
  }
  if (value === "passport_slot_automatic") {
    return `${t("passportSlotMonitor")} · ${t("triggerAutomatic")}`;
  }
  if (value === "manual") {
    return t("triggerManual");
  }
  if (value === "automatic") {
    return t("triggerAutomatic");
  }
  return t("triggerUnknown");
}

function getStatusTone(status: string | null | undefined): "issued" | "approved" | "refused" | "" {
  const normalized = (status ?? "").trim().toLowerCase();
  if (normalized === "issued") {
    return "issued";
  }
  if (normalized === "approved") {
    return "approved";
  }
  if (normalized === "refused") {
    return "refused";
  }
  return "";
}

function getStatusBadgeClass(status: string | null | undefined, extraClass = ""): string {
  const tone = getStatusTone(status);
  return ["status-badge", tone ? `status-${tone}` : "", extraClass].filter(Boolean).join(" ");
}

function isIssuedStatus(status: string | null | undefined): boolean {
  return getStatusTone(status) === "issued";
}

function isPassportSlotReadyStatus(status: string | null | undefined): boolean {
  const tone = getStatusTone(status);
  return tone === "approved" || tone === "issued";
}

function getRememberedCredentials(): { email: string; password: string; remember: boolean } {
  const enabled = localStorage.getItem("rememberLogin") === "true";
  return {
    email: localStorage.getItem("rememberedEmail") ?? "",
    password: enabled ? localStorage.getItem("rememberedPassword") ?? "" : "",
    remember: enabled,
  };
}

export function App() {
  const [themeMode, setThemeMode] = useState<ThemeMode>(getInitialTheme);
  const [languageMode, setLanguageMode] = useState<LanguageMode>(getInitialLanguage);
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [viewMode, setViewMode] = useState<ViewMode>("dashboard");
  const [user, setUser] = useState<User | null>(null);
  const [cases, setCases] = useState<CeacCase[]>([]);
  const [adminCases, setAdminCases] = useState<CeacCase[]>([]);
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [passportSlotMonitor, setPassportSlotMonitor] = useState<PassportSlotMonitor | null>(null);
  const [passportSlotHistory, setPassportSlotHistory] = useState<PassportSlotHistoryItem[]>([]);
  const [passportSlotIdentifier, setPassportSlotIdentifier] = useState("");
  const [queryRuns, setQueryRuns] = useState<QueryRun[]>([]);
  const [systemEmailConfig, setSystemEmailConfig] = useState<SystemEmailConfig | null>(null);
  const [systemEmailForm, setSystemEmailForm] = useState<SystemEmailForm>({
    fromEmail: "",
    host: "smtp.exmail.qq.com",
    port: "465",
    useSsl: true,
    password: "",
  });
  const [selectedCaseId, setSelectedCaseId] = useState<number | null>(null);
  const [caseForm, setCaseForm] = useState<CaseForm>(emptyCaseForm);
  const [profileForm, setProfileForm] = useState<ProfileForm>({
    email: "",
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });
  const rememberedCredentials = useMemo(getRememberedCredentials, []);
  const [authEmail, setAuthEmail] = useState(rememberedCredentials.email);
  const [authPassword, setAuthPassword] = useState(rememberedCredentials.password);
  const [rememberLogin, setRememberLogin] = useState(rememberedCredentials.remember);
  const [registerCode, setRegisterCode] = useState("");
  const [resetCode, setResetCode] = useState("");
  const [resetConfirmPassword, setResetConfirmPassword] = useState("");
  const [message, setMessage] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const t = (key: TranslationKey) => translations[languageMode][key];

  useEffect(() => {
    document.documentElement.dataset.theme = themeMode;
    localStorage.setItem("themeMode", themeMode);
  }, [themeMode]);

  useEffect(() => {
    document.documentElement.lang = languageMode === "zh" ? "zh-CN" : "en";
    localStorage.setItem("languageMode", languageMode);
  }, [languageMode]);

  useEffect(() => {
    requestJson<{ user: User }>("/api/me")
      .then((payload) => {
        setUser(payload.user);
        setProfileForm((current) => ({ ...current, email: payload.user.email }));
        void loadCases();
      })
      .catch(() => undefined);
  }, []);

  const selectedCase = useMemo(
    () => cases.find((item) => item.id === selectedCaseId) ?? cases[0] ?? null,
    [cases, selectedCaseId],
  );

  useEffect(() => {
    if (selectedCase) {
      void loadHistory(selectedCase.id);
      void loadPassportSlotMonitor(selectedCase.id);
    } else {
      setHistory([]);
      setPassportSlotMonitor(null);
      setPassportSlotHistory([]);
      setPassportSlotIdentifier("");
    }
  }, [selectedCase?.id]);

  async function loadCases() {
    const payload = await requestJson<{ cases: CeacCase[] }>("/api/cases");
    setCases(payload.cases);
    if (payload.cases.length > 0) {
      setSelectedCaseId((current) => current ?? payload.cases[0].id);
    }
  }

  async function loadHistory(caseId: number) {
    const payload = await requestJson<{ history: HistoryItem[] }>(`/api/cases/${caseId}/history`);
    setHistory(payload.history);
  }

  async function loadPassportSlotMonitor(caseId: number) {
    const payload = await requestJson<{ monitor: PassportSlotMonitor | null; history: PassportSlotHistoryItem[] }>(
      `/api/cases/${caseId}/passport-slot-monitor`,
    );
    setPassportSlotMonitor(payload.monitor);
    setPassportSlotHistory(payload.history);
    setPassportSlotIdentifier(payload.monitor?.identifier ?? "");
  }

  async function loadAdminData() {
    const [runsPayload, casesPayload, usersPayload, systemEmailPayload] = await Promise.all([
      requestJson<{ runs: QueryRun[] }>("/api/admin/query-runs"),
      requestJson<{ cases: CeacCase[] }>("/api/admin/cases"),
      requestJson<{ users: AdminUser[] }>("/api/admin/users"),
      requestJson<{ config: SystemEmailConfig }>("/api/admin/system-email"),
    ]);
    setQueryRuns(runsPayload.runs);
    setAdminCases(casesPayload.cases);
    setAdminUsers(usersPayload.users);
    setSystemEmailConfig(systemEmailPayload.config);
    setSystemEmailForm({
      fromEmail: systemEmailPayload.config.fromEmail,
      host: systemEmailPayload.config.host,
      port: String(systemEmailPayload.config.port),
      useSsl: systemEmailPayload.config.useSsl,
      password: "",
    });
  }

  async function saveSystemEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsBusy(true);
    setMessage("");
    try {
      const payload = await requestJson<{ config: SystemEmailConfig }>("/api/admin/system-email", {
        method: "PUT",
        body: JSON.stringify({
          fromEmail: systemEmailForm.fromEmail,
          host: systemEmailForm.host,
          port: Number(systemEmailForm.port),
          useSsl: systemEmailForm.useSsl,
          password: systemEmailForm.password || null,
        }),
      });
      setSystemEmailConfig(payload.config);
      setSystemEmailForm((current) => ({ ...current, password: "" }));
      setMessage(t("systemEmailSaved"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("requestFailed"));
    } finally {
      setIsBusy(false);
    }
  }

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsBusy(true);
    setMessage("");
    try {
      if (authMode === "forgot") {
        if (authPassword !== resetConfirmPassword) {
          setMessage(t("resetPasswordMismatch"));
          return;
        }
        await requestJson<{ ok: boolean }>("/api/auth/reset-password", {
          method: "POST",
          body: JSON.stringify({ email: authEmail, code: resetCode, password: authPassword }),
        });
        setAuthMode("login");
        setAuthPassword("");
        setResetCode("");
        setResetConfirmPassword("");
        setMessage(t("resetPasswordSaved"));
        return;
      }
      const path = authMode === "login" ? "/api/auth/login" : "/api/auth/register";
      const body = authMode === "login"
        ? { email: authEmail, password: authPassword }
        : { email: authEmail, password: authPassword, code: registerCode };
      const payload = await requestJson<{ user: User }>(path, {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (authMode === "login" && rememberLogin) {
        localStorage.setItem("rememberLogin", "true");
        localStorage.setItem("rememberedEmail", authEmail);
        localStorage.setItem("rememberedPassword", authPassword);
      } else if (authMode === "login") {
        localStorage.removeItem("rememberLogin");
        localStorage.removeItem("rememberedPassword");
        localStorage.setItem("rememberedEmail", authEmail);
      }
      setUser(payload.user);
      setProfileForm({ email: payload.user.email, currentPassword: "", newPassword: "", confirmPassword: "" });
      await loadCases();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("signInFailed"));
    } finally {
      setIsBusy(false);
    }
  }

  async function sendCode() {
    setIsBusy(true);
    setMessage("");
    try {
      const path = authMode === "forgot" ? "/api/auth/send-password-reset-code" : "/api/auth/send-code";
      await requestJson<{ ok: boolean }>(path, {
        method: "POST",
        body: JSON.stringify({ email: authEmail }),
      });
      setMessage(authMode === "forgot" ? t("resetCodeSent") : t("verificationCodeSent"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("sendCodeFailed"));
    } finally {
      setIsBusy(false);
    }
  }

  async function logout() {
    await requestJson<{ ok: boolean }>("/api/auth/logout", { method: "POST", body: "{}" });
    setUser(null);
    setCases([]);
    setHistory([]);
  }

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsBusy(true);
    setMessage("");
    if (profileForm.newPassword && profileForm.newPassword !== profileForm.confirmPassword) {
      setMessage(languageMode === "zh" ? "两次输入的新密码不一致。" : "New passwords do not match.");
      setIsBusy(false);
      return;
    }
    try {
      const payload = await requestJson<{ user: User }>("/api/me", {
        method: "PATCH",
        body: JSON.stringify({
          email: profileForm.email,
          currentPassword: profileForm.currentPassword,
          newPassword: profileForm.newPassword || null,
        }),
      });
      setUser(payload.user);
      setProfileForm({ email: payload.user.email, currentPassword: "", newPassword: "", confirmPassword: "" });
      localStorage.setItem("rememberedEmail", payload.user.email);
      setMessage(t("profileSaved"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("requestFailed"));
    } finally {
      setIsBusy(false);
    }
  }

  async function saveCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsBusy(true);
    setMessage("");
    try {
      const payload = {
        displayName: caseForm.displayName,
        location: caseForm.location,
        applicationNum: caseForm.applicationNum,
        passportNumber: caseForm.passportNumber,
        surname: caseForm.surname,
        receiveEmail: caseForm.receiveEmail,
        senderMode: caseForm.senderMode,
        isEnabled: caseForm.isEnabled,
        emailNotificationsEnabled: caseForm.emailNotificationsEnabled,
        smtpConfig: caseForm.senderMode === "custom"
          ? {
              fromEmail: caseForm.smtpFromEmail,
              host: caseForm.smtpHost,
              port: Number(caseForm.smtpPort),
              useSsl: caseForm.smtpUseSsl,
              password: caseForm.smtpPassword,
            }
          : null,
      };
      const result = await requestJson<{ case: CeacCase }>("/api/cases", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setCaseForm(emptyCaseForm);
      setSelectedCaseId(result.case.id);
      await loadCases();
      setMessage(t("caseCreated"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("requestFailed"));
    } finally {
      setIsBusy(false);
    }
  }

  async function runTest(caseId: number) {
    setIsBusy(true);
    setMessage(t("queryInProgress"));
    try {
      const payload = await requestJson<{ jobId: number; status: QueryJob["status"] }>(`/api/cases/${caseId}/test-query`, {
        method: "POST",
        body: "{}",
      });
      let job: QueryJob | null = null;
      for (let index = 0; index < 60; index += 1) {
        const jobPayload = await requestJson<{ job: QueryJob }>(`/api/query-jobs/${payload.jobId}`);
        job = jobPayload.job;
        if (job.status === "succeeded" || job.status === "failed") {
          break;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 2000));
      }
      await loadCases();
      await loadHistory(caseId);
      if (!job || (job.status !== "succeeded" && job.status !== "failed")) {
        setMessage(t("queryInProgress"));
        return;
      }
      const result = job.result;
      setMessage(
        result?.success
          ? (result.changed ? t("fastQueryChanged") : t("fastQueryUnchanged"))
          : (job.errorMessage || result?.error || t("requestFailed")),
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("requestFailed"));
    } finally {
      setIsBusy(false);
    }
  }

  async function sendTestEmail(caseId: number) {
    setIsBusy(true);
    setMessage(t("testEmailSending"));
    try {
      await requestJson<{ success: boolean; error: string }>(`/api/cases/${caseId}/test-email`, {
        method: "POST",
        body: "{}",
      });
      setMessage(t("testEmailSent"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("requestFailed"));
    } finally {
      setIsBusy(false);
    }
  }

  async function toggleEmailPush(targetCase: CeacCase) {
    setIsBusy(true);
    setMessage("");
    try {
      await requestJson<{ case: CeacCase }>(`/api/cases/${targetCase.id}`, {
        method: "PATCH",
        body: JSON.stringify({ emailNotificationsEnabled: !targetCase.emailNotificationsEnabled }),
      });
      await loadCases();
      setMessage(!targetCase.emailNotificationsEnabled ? t("updatePushEnabled") : t("updatePushDisabled"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("requestFailed"));
    } finally {
      setIsBusy(false);
    }
  }

  async function stopAutomaticQuery(targetCase: CeacCase) {
    setIsBusy(true);
    setMessage("");
    try {
      await requestJson<{ case: CeacCase }>(`/api/cases/${targetCase.id}`, {
        method: "PATCH",
        body: JSON.stringify({ isEnabled: false }),
      });
      await loadCases();
      setMessage(t("automaticQueryStopped"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("requestFailed"));
    } finally {
      setIsBusy(false);
    }
  }

  async function savePassportSlotMonitor(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCase) {
      return;
    }
    setIsBusy(true);
    setMessage("");
    try {
      const payload = await requestJson<{ monitor: PassportSlotMonitor }>(`/api/cases/${selectedCase.id}/passport-slot-monitor`, {
        method: "PUT",
        body: JSON.stringify({
          identifier: passportSlotIdentifier,
          isEnabled: passportSlotMonitor?.isEnabled ?? true,
          emailNotificationsEnabled: passportSlotMonitor?.emailNotificationsEnabled ?? true,
        }),
      });
      setPassportSlotMonitor(payload.monitor);
      setPassportSlotIdentifier(payload.monitor.identifier);
      await loadPassportSlotMonitor(selectedCase.id);
      setMessage(t("passportSlotSaved"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("requestFailed"));
    } finally {
      setIsBusy(false);
    }
  }

  async function togglePassportSlotMonitor(targetCase: CeacCase, targetMonitor: PassportSlotMonitor) {
    setIsBusy(true);
    setMessage("");
    try {
      const payload = await requestJson<{ monitor: PassportSlotMonitor }>(`/api/cases/${targetCase.id}/passport-slot-monitor`, {
        method: "PATCH",
        body: JSON.stringify({ isEnabled: !targetMonitor.isEnabled }),
      });
      setPassportSlotMonitor(payload.monitor);
      setMessage(!targetMonitor.isEnabled ? t("passportSlotEnabled") : t("passportSlotDisabled"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("requestFailed"));
    } finally {
      setIsBusy(false);
    }
  }

  async function togglePassportSlotEmailNotifications(targetCase: CeacCase, targetMonitor: PassportSlotMonitor) {
    setIsBusy(true);
    setMessage("");
    try {
      const payload = await requestJson<{ monitor: PassportSlotMonitor }>(`/api/cases/${targetCase.id}/passport-slot-monitor`, {
        method: "PATCH",
        body: JSON.stringify({ emailNotificationsEnabled: !targetMonitor.emailNotificationsEnabled }),
      });
      setPassportSlotMonitor(payload.monitor);
      setMessage(!targetMonitor.emailNotificationsEnabled ? t("passportSlotEmailEnabled") : t("passportSlotEmailDisabled"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("requestFailed"));
    } finally {
      setIsBusy(false);
    }
  }

  async function runPassportSlotQuery(caseId: number) {
    setIsBusy(true);
    setMessage(t("passportSlotQuerying"));
    try {
      const payload = await requestJson<{ jobId: number; status: QueryJob["status"] }>(`/api/cases/${caseId}/passport-slot-monitor/test-query`, {
        method: "POST",
        body: "{}",
      });
      let job: QueryJob | null = null;
      for (let index = 0; index < 60; index += 1) {
        const jobPayload = await requestJson<{ job: QueryJob }>(`/api/query-jobs/${payload.jobId}`);
        job = jobPayload.job;
        if (job.status === "succeeded" || job.status === "failed") {
          break;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 2000));
      }
      await loadPassportSlotMonitor(caseId);
      if (!job || (job.status !== "succeeded" && job.status !== "failed")) {
        setMessage(t("passportSlotQuerying"));
        return;
      }
      const result = job.result as (QueryJob["result"] & { slotCount?: number; notified?: boolean }) | null;
      if (!result?.success) {
        setMessage(job.errorMessage || result?.error || t("requestFailed"));
        return;
      }
      if ((result.slotCount ?? 0) > 0) {
        setMessage(result.changed ? t("passportSlotChanged") : t("passportSlotFound"));
      } else {
        setMessage(t("passportSlotNotFound"));
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("requestFailed"));
    } finally {
      setIsBusy(false);
    }
  }

  async function sendPassportSlotTestEmail(caseId: number) {
    setIsBusy(true);
    setMessage(t("passportSlotTestEmailSending"));
    try {
      await requestJson<{ success: boolean; error: string }>(`/api/cases/${caseId}/passport-slot-monitor/test-email`, {
        method: "POST",
        body: "{}",
      });
      setMessage(t("passportSlotTestEmailSent"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("requestFailed"));
    } finally {
      setIsBusy(false);
    }
  }

  async function removeCase(caseId: number) {
    await requestJson<{ ok: boolean }>(`/api/cases/${caseId}`, { method: "DELETE", body: "{}" });
    setSelectedCaseId(null);
    await loadCases();
  }

  if (!user) {
    return (
      <main className="auth-shell">
        <div className="auth-tools">
          <LanguageButton languageMode={languageMode} setLanguageMode={setLanguageMode} />
          <ThemeButton themeMode={themeMode} setThemeMode={setThemeMode} t={t} />
        </div>
        <div className="auth-header">
          <img className="brand-mark" src="/favicon.svg" alt="CEACStatusBot" />
          <h1 className="display-md">CEACStatusBot</h1>
          <p className="body">{t("appSubtitle")}</p>
        </div>
        <section className="auth-panel">
          <form className="stack" onSubmit={submitAuth}>
            <div className="segmented">
              <button type="button" className={authMode === "login" ? "selected" : ""} onClick={() => setAuthMode("login")}>
                {t("login")}
              </button>
              <button type="button" className={authMode === "register" ? "selected" : ""} onClick={() => setAuthMode("register")}>
                {t("register")}
              </button>
            </div>
            <label>
              {t("email")}
              <input value={authEmail} onChange={(event) => setAuthEmail(event.target.value)} type="email" required autoComplete="username" />
            </label>
            <label>
              {authMode === "forgot" ? t("resetPassword") : t("password")}
              <input
                value={authPassword}
                onChange={(event) => setAuthPassword(event.target.value)}
                type="password"
                required
                minLength={8}
                autoComplete={authMode === "login" ? "current-password" : "new-password"}
              />
            </label>
            {authMode === "login" && (
              <div className="auth-options">
                <label className="checkbox">
                  <input type="checkbox" checked={rememberLogin} onChange={(event) => setRememberLogin(event.target.checked)} />
                  <span className="body-sm">{t("rememberPassword")}</span>
                </label>
                <button type="button" className="text-button" onClick={() => { setAuthMode("forgot"); setMessage(""); }}>
                  {t("forgotPassword")}
                </button>
              </div>
            )}
            {(authMode === "register" || authMode === "forgot") && (
              <label>
                {t("verificationCode")}
                <div className="inline-field">
                  <input
                    value={authMode === "forgot" ? resetCode : registerCode}
                    onChange={(event) => authMode === "forgot" ? setResetCode(event.target.value) : setRegisterCode(event.target.value)}
                    required
                  />
                  <button type="button" className="button secondary" onClick={sendCode} disabled={isBusy}>
                    {t("send")}
                  </button>
                </div>
              </label>
            )}
            {authMode === "forgot" && (
              <label>
                {languageMode === "zh" ? "确认新密码" : "Confirm new password"}
                <input
                  value={resetConfirmPassword}
                  onChange={(event) => setResetConfirmPassword(event.target.value)}
                  type="password"
                  required
                  minLength={8}
                  autoComplete="new-password"
                />
              </label>
            )}
            <button className="button primary" disabled={isBusy}>
              {authMode === "login" ? t("loginAction") : authMode === "register" ? t("registerAction") : t("resetAction")}
            </button>
            {authMode === "forgot" && (
              <button type="button" className="text-button centered" onClick={() => { setAuthMode("login"); setMessage(""); }}>
                {t("login")}
              </button>
            )}
            {message && <p className="notice">{message}</p>}
          </form>
        </section>
        <SiteFooter />
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="top-nav">
        <div className="top-nav-main">
          <div className="brand-lockup">
            <img className="brand-mark" src="/favicon.svg" alt="" />
            <span className="brand-name">CEACStatusBot</span>
          </div>
        </div>
        <nav className="nav-actions" aria-label="Primary">
          <button className={`nav-tab ${viewMode === "dashboard" ? "active" : ""}`} onClick={() => setViewMode("dashboard")}>
            <UserRound size={16} /> {t("dashboard")}
          </button>
          <button className={`nav-tab ${viewMode === "profile" ? "active" : ""}`} onClick={() => setViewMode("profile")}>
            <UserRound size={16} /> {t("personalInfo")}
          </button>
          {user.role === "admin" && (
            <button
              className={`nav-tab ${viewMode === "admin" ? "active" : ""}`}
              onClick={() => {
                setViewMode("admin");
                void loadAdminData();
              }}
            >
              <Shield size={16} /> {t("admin")}
            </button>
          )}
        </nav>
        <div className="utility-actions">
          <LanguageButton languageMode={languageMode} setLanguageMode={setLanguageMode} />
          <ThemeButton themeMode={themeMode} setThemeMode={setThemeMode} t={t} />
          <button className="button tertiary icon-only" onClick={logout} title={t("logoutTitle")} aria-label={t("logoutTitle")}>
            <LogOut size={16} />
          </button>
        </div>
      </header>

      <section className="workspace">
        <header className="page-header">
          <div>
            <p className="eyebrow" style={{ color: 'var(--primary-hover)' }}>{t("currentLogin")}: {user.email}</p>
            <h1 className="headline">
              {viewMode === "admin" ? t("adminTitle") : viewMode === "profile" ? t("personalInfo") : t("statusMonitoring")}
            </h1>
          </div>
          {message && <p className="notice">{message}</p>}
        </header>

        {viewMode === "dashboard" ? (
          <div className="dashboard-layout">
            <div className="stack">
              <section className="panel">
                <div className="panel-title">
                  <h2 className="headline">{t("caseList")}</h2>
                  <button className="button secondary" title={t("caseName")} onClick={() => { setSelectedCaseId(null); setCaseForm(emptyCaseForm); }}>
                    <Plus size={16} /> {t("newProfile")}
                  </button>
                </div>
                <div className="case-list">
                  {cases.map((item) => (
                    <div key={item.id} className={`case-row ${selectedCaseId === item.id ? "selected" : ""}`} onClick={() => setSelectedCaseId(item.id)}>
                      <div className="case-info">
                        <div className="case-name">{item.displayName}</div>
                        <div className="case-meta">{item.applicationNum || t("missingCaseNumber")}</div>
                      </div>
                      <span className={getStatusBadgeClass(item.lastStatus)}>{item.lastStatus ?? t("waitFirstQuery")}</span>
                    </div>
                  ))}
                  {cases.length === 0 && <p className="empty-state">{t("noCases")}</p>}
                </div>
              </section>
            </div>

            <div className="stack">
              {selectedCaseId === null ? (
                <section className="panel">
                  <div className="panel-title">
                    <div>
                      <h2 className="headline">{t("statusMonitoring")}</h2>
                      <p className="form-intro">{t("officialIntro")}</p>
                    </div>
                  </div>
                  <CaseFormView caseForm={caseForm} setCaseForm={setCaseForm} saveCase={saveCase} isBusy={isBusy} t={t} languageMode={languageMode} />
                </section>
              ) : selectedCase ? (
                <>
                  <section className="panel">
                    <div className="panel-title">
                      <h2 className="headline">{selectedCase.displayName}</h2>
                      <div className="row-actions">
                        <button className="button secondary" onClick={() => runTest(selectedCase.id)} disabled={isBusy}>
                          <Activity size={16} /> {t("fastQuery")}
                        </button>
                        <button className="button secondary" onClick={() => sendTestEmail(selectedCase.id)} disabled={isBusy || history.length === 0}>
                          <Mail size={16} /> {t("testEmail")}
                        </button>
                        <button className="icon-button danger" onClick={() => { if (confirm(t("confirmDelete"))) void removeCase(selectedCase.id); }}>
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                    
                    <div className="stack" style={{ marginBottom: "24px" }}>
                      {isIssuedStatus(selectedCase.lastStatus) && selectedCase.isEnabled && (
                        <div className="notice action-notice">
                          <span>{t("issuedSlowQueryNotice")}</span>
                          <button className="button secondary" onClick={() => stopAutomaticQuery(selectedCase)} disabled={isBusy}>
                            {t("stopAutomaticQuery")}
                          </button>
                        </div>
                      )}
                      <div className="two-col metric-grid">
                        <Metric label={t("locationMetric")} value={selectedCase.location} />
                        <Metric label={`${t("applicationId")} / ${t("passport")}`} value={`${selectedCase.applicationNum} / ${selectedCase.passportNumber}`} />
                      </div>
                      <div className="two-col metric-grid">
                        <Metric label={t("notifyEmail")} value={selectedCase.receiveEmail} />
                        <Metric label={t("status")}>
                          <span className={getStatusBadgeClass(selectedCase.lastStatus, "metric-status")}>
                            {selectedCase.lastStatus || t("noStatus")}
                          </span>
                        </Metric>
                      </div>
                      <div className="two-col metric-grid">
                        <Metric label={t("lastCheckedAt")} value={formatTime(selectedCase.lastCheckedAt, languageMode)} />
                        <Metric label={t("lastCheckMode")} value={formatTriggerType(selectedCase.lastTriggerType, t)} />
                      </div>
                      <div className="two-col metric-grid">
                        <Metric label={t("nextCheckAt")} value={formatTime(selectedCase.nextCheckAt, languageMode)} />
                        <Metric label={t("emailPushSetting")} value={selectedCase.emailNotificationsEnabled ? t("emailPushOn") : t("emailPushOff")} />
                      </div>
                      <div className="settings-row">
                        <label className="checkbox">
                          <input
                            type="checkbox"
                            checked={selectedCase.emailNotificationsEnabled}
                            onChange={() => toggleEmailPush(selectedCase)}
                            disabled={isBusy}
                          />
                          <span className="body-sm">{t("emailPushSetting")}</span>
                        </label>
                        <span className={`status-badge ${selectedCase.emailNotificationsEnabled ? "success" : ""}`}>
                          {selectedCase.emailNotificationsEnabled ? t("emailPushOn") : t("emailPushOff")}
                        </span>
                      </div>
                    </div>
                  </section>

                  <PassportSlotMonitorPanel
                    selectedCase={selectedCase}
                    monitor={passportSlotMonitor}
                    history={passportSlotHistory}
                    identifier={passportSlotIdentifier}
                    setIdentifier={setPassportSlotIdentifier}
                    saveMonitor={savePassportSlotMonitor}
                    toggleMonitor={togglePassportSlotMonitor}
                    toggleEmailNotifications={togglePassportSlotEmailNotifications}
                    runQuery={runPassportSlotQuery}
                    sendTestEmail={sendPassportSlotTestEmail}
                    isBusy={isBusy}
                    t={t}
                    languageMode={languageMode}
                  />

                  <section className="panel">
                    <div className="panel-title">
                      <h2 className="subhead">{t("statusHistory")}</h2>
                      <History size={18} />
                    </div>
                    <div className="timeline">
                      {history.map((record) => (
                        <div key={record.id} className="timeline-item">
                          <div className="timeline-header">
                            <span className="timeline-time">{formatTime(record.fetchedAt, languageMode)}</span>
                            <span className={getStatusBadgeClass(record.status)}>{record.status}</span>
                          </div>
                          <div className="timeline-desc">{record.description}</div>
                        </div>
                      ))}
                      {history.length === 0 && <p className="empty-state">{t("noHistory")}</p>}
                    </div>
                  </section>
                </>
              ) : null}
            </div>
          </div>
        ) : viewMode === "profile" ? (
          <ProfilePanel
            profileForm={profileForm}
            setProfileForm={setProfileForm}
            saveProfile={saveProfile}
            isBusy={isBusy}
            t={t}
            languageMode={languageMode}
          />
        ) : (
          <AdminPanel
            users={adminUsers}
            queryRuns={queryRuns}
            cases={adminCases}
            reload={loadAdminData}
            t={t}
            languageMode={languageMode}
            systemEmailConfig={systemEmailConfig}
            systemEmailForm={systemEmailForm}
            setSystemEmailForm={setSystemEmailForm}
            saveSystemEmail={saveSystemEmail}
            isBusy={isBusy}
          />
        )}
      </section>
      <SiteFooter />
    </main>
  );
}

function SiteFooter() {
  if (!icpRecordNumber) {
    return null;
  }
  return (
    <footer className="site-footer">
      <a href="https://beian.miit.gov.cn/" target="_blank" rel="noreferrer">
        {icpRecordNumber}
      </a>
    </footer>
  );
}

function ThemeButton(props: { themeMode: ThemeMode; setThemeMode: (mode: ThemeMode) => void; t: (key: TranslationKey) => string }) {
  const nextTitle = props.themeMode === "dark" ? props.t("themeToLight") : props.t("themeToDark");
  return (
    <button
      className="button tertiary theme-toggle"
      onClick={() => props.setThemeMode(props.themeMode === "dark" ? "light" : "dark")}
      title={nextTitle}
      style={{ padding: "8px" }}
    >
      {props.themeMode === "dark" ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}

function LanguageButton(props: { languageMode: LanguageMode; setLanguageMode: (mode: LanguageMode) => void }) {
  return (
    <button
      className="button tertiary language-toggle"
      onClick={() => props.setLanguageMode(props.languageMode === "zh" ? "en" : "zh")}
      title={props.languageMode === "zh" ? "Switch to English" : "切换到中文"}
    >
      {props.languageMode === "zh" ? "EN" : "中"}
    </button>
  );
}

function Metric(props: { label: string; value?: string; children?: React.ReactNode }) {
  return (
    <div className="metric">
      <div className="caption">{props.label}</div>
      <div className="body-sm">{props.children ?? props.value}</div>
    </div>
  );
}

function summarizePassportSlotResult(result: PassportSlotMonitor["lastResult"], languageMode: LanguageMode): string {
  const slots = Array.isArray(result?.availableSlots)
    ? result.availableSlots
    : Array.isArray(result?.availableDates)
      ? result.availableDates
      : [];
  if (!slots.length) {
    return languageMode === "zh" ? "暂无可预约时间" : "No available slot";
  }
  return slots.slice(0, 3).map((slot) => {
    if (slot && typeof slot === "object") {
      const record = slot as Record<string, unknown>;
      const parts = ["date", "time", "datetime", "dateTime", "startTime", "city", "location"]
        .map((key) => record[key] ? `${key}: ${String(record[key])}` : "")
        .filter(Boolean);
      return parts.join("; ") || JSON.stringify(record);
    }
    return String(slot);
  }).join(" | ");
}

function PassportSlotMonitorPanel(props: {
  selectedCase: CeacCase;
  monitor: PassportSlotMonitor | null;
  history: PassportSlotHistoryItem[];
  identifier: string;
  setIdentifier: (value: string) => void;
  saveMonitor: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  toggleMonitor: (targetCase: CeacCase, targetMonitor: PassportSlotMonitor) => Promise<void>;
  toggleEmailNotifications: (targetCase: CeacCase, targetMonitor: PassportSlotMonitor) => Promise<void>;
  runQuery: (caseId: number) => Promise<void>;
  sendTestEmail: (caseId: number) => Promise<void>;
  isBusy: boolean;
  t: (key: TranslationKey) => string;
  languageMode: LanguageMode;
}) {
  const isReadyStatus = isPassportSlotReadyStatus(props.selectedCase.lastStatus);
  return (
    <section className={`panel passport-slot-panel ${isReadyStatus ? "ready" : ""}`}>
      <div className="panel-title">
        <div>
          <h2 className="subhead">{props.t("passportSlotMonitor")}</h2>
          <p className="form-intro">
            {isReadyStatus ? props.t("passportSlotIntro") : props.t("passportSlotEarlyHint")}
          </p>
        </div>
        {props.monitor && (
          <span className={`status-badge ${props.monitor.isEnabled ? "success" : ""}`}>
            {props.monitor.isEnabled ? props.t("autoMonitor") : props.t("passportSlotDisabled")}
          </span>
        )}
      </div>

      <form className="inline-monitor-form" onSubmit={props.saveMonitor}>
        <label>
          {props.t("passportSlotIdentifier")}
          <input
            value={props.identifier}
            onChange={(event) => props.setIdentifier(event.target.value.trim().toUpperCase())}
            placeholder={props.t("passportSlotIdentifierPlaceholder")}
            required
          />
        </label>
        <button className="button primary" disabled={props.isBusy}>
          {props.t("passportSlotSave")}
        </button>
      </form>

      {props.monitor ? (
        <div className="stack">
          <div className="two-col metric-grid">
            <Metric label={props.t("passportSlotConfigured")} value={props.monitor.identifierMasked} />
            <Metric label={props.t("passportSlotLastCount")} value={String(props.monitor.lastSlotCount)} />
          </div>
          <div className="two-col metric-grid">
            <Metric label={props.t("lastCheckedAt")} value={formatTime(props.monitor.lastCheckedAt, props.languageMode)} />
            <Metric label={props.t("nextCheckAt")} value={formatTime(props.monitor.nextCheckAt, props.languageMode)} />
          </div>
          <Metric label={props.t("changeContent")} value={summarizePassportSlotResult(props.monitor.lastResult, props.languageMode)} />
          {props.monitor.lastErrorMessage && (
            <Metric label={props.t("passportSlotLastError")} value={props.monitor.lastErrorMessage} />
          )}
          <div className="settings-row">
            <label className="checkbox">
              <input
                type="checkbox"
                checked={props.monitor.isEnabled}
                onChange={() => props.toggleMonitor(props.selectedCase, props.monitor!)}
                disabled={props.isBusy}
              />
              <span className="body-sm">{props.t("autoMonitor")}</span>
            </label>
            <span className={`status-badge ${props.monitor.isEnabled ? "success" : ""}`}>
              {props.monitor.isEnabled ? props.t("passportSlotEnabled") : props.t("passportSlotDisabled")}
            </span>
          </div>
          <div className="settings-row">
            <label className="checkbox">
              <input
                type="checkbox"
                checked={props.monitor.emailNotificationsEnabled}
                onChange={() => props.toggleEmailNotifications(props.selectedCase, props.monitor!)}
                disabled={props.isBusy}
              />
              <span className="body-sm">{props.t("emailPushSetting")}</span>
            </label>
            <span className={`status-badge ${props.monitor.emailNotificationsEnabled ? "success" : ""}`}>
              {props.monitor.emailNotificationsEnabled ? props.t("emailPushOn") : props.t("emailPushOff")}
            </span>
          </div>
          <div className="row-actions">
            <button
              type="button"
              className="button secondary"
              onClick={() => props.runQuery(props.selectedCase.id)}
              disabled={props.isBusy}
            >
              <Activity size={16} /> {props.t("passportSlotManualQuery")}
            </button>
            <button
              type="button"
              className="button secondary"
              onClick={() => props.sendTestEmail(props.selectedCase.id)}
              disabled={props.isBusy}
            >
              <Mail size={16} /> {props.t("passportSlotTestEmail")}
            </button>
          </div>
          <div className="mini-history">
            <div className="caption">{props.t("passportSlotHistory")}</div>
            {props.history.slice(0, 3).map((item) => (
              <div key={item.id} className="mini-history-row">
                <span>{formatTime(item.fetchedAt, props.languageMode)}</span>
                <span>{item.slotCount} slot</span>
                <span>{item.notificationSent ? props.t("emailPushOn") : props.t("noStatusChange")}</span>
              </div>
            ))}
            {props.history.length === 0 && <p className="empty-state compact">{props.t("noPassportSlotHistory")}</p>}
          </div>
        </div>
      ) : (
        <p className="empty-state compact">{props.t("noPassportSlotMonitor")}</p>
      )}
    </section>
  );
}

function ProfilePanel(props: {
  profileForm: ProfileForm;
  setProfileForm: React.Dispatch<React.SetStateAction<ProfileForm>>;
  saveProfile: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  isBusy: boolean;
  t: (key: TranslationKey) => string;
  languageMode: LanguageMode;
}) {
  const form = props.profileForm;
  return (
    <section className="panel narrow-panel profile-panel">
      <div className="panel-title">
        <h2 className="headline">{props.t("personalInfo")}</h2>
      </div>
      <form className="stack" onSubmit={props.saveProfile}>
        <label>
          {props.t("email")}
          <input
            value={form.email}
            onChange={(event) => props.setProfileForm({ ...form, email: event.target.value.trim() })}
            type="email"
            required
          />
        </label>
        <label>
          {props.languageMode === "zh" ? "当前密码" : "Current password"}
          <input
            value={form.currentPassword}
            onChange={(event) => props.setProfileForm({ ...form, currentPassword: event.target.value })}
            type="password"
            required
            autoComplete="current-password"
          />
        </label>
        <div className="two-col">
          <label>
            {props.languageMode === "zh" ? "新密码" : "New password"}
            <input
              value={form.newPassword}
              onChange={(event) => props.setProfileForm({ ...form, newPassword: event.target.value })}
              type="password"
              minLength={8}
              autoComplete="new-password"
            />
          </label>
          <label>
            {props.languageMode === "zh" ? "确认新密码" : "Confirm new password"}
            <input
              value={form.confirmPassword}
              onChange={(event) => props.setProfileForm({ ...form, confirmPassword: event.target.value })}
              type="password"
              minLength={8}
              autoComplete="new-password"
            />
          </label>
        </div>
        <div>
          <button className="button primary" disabled={props.isBusy}>{props.t("save")}</button>
        </div>
      </form>
    </section>
  );
}

function AdminPanel(props: {
  users: AdminUser[];
  queryRuns: QueryRun[];
  cases: CeacCase[];
  reload: () => Promise<void>;
  t: (key: TranslationKey) => string;
  languageMode: LanguageMode;
  systemEmailConfig: SystemEmailConfig | null;
  systemEmailForm: SystemEmailForm;
  setSystemEmailForm: React.Dispatch<React.SetStateAction<SystemEmailForm>>;
  saveSystemEmail: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  isBusy: boolean;
}) {
  const form = props.systemEmailForm;
  const casesByUserId = useMemo(() => {
    const grouped = new Map<number, CeacCase[]>();
    for (const item of props.cases) {
      grouped.set(item.userId, [...(grouped.get(item.userId) ?? []), item]);
    }
    return grouped;
  }, [props.cases]);
  return (
    <div className="stack">
      <section className="panel">
        <div className="panel-title">
          <div>
            <h2 className="headline">{props.t("systemEmail")}</h2>
            {props.systemEmailConfig && (
              <p className="form-intro">
                {props.t("systemEmailSource")}: {props.systemEmailConfig.source}
                {" · "}
                {props.systemEmailConfig.isConfigured ? props.t("systemEmailConfigured") : props.t("systemEmailNotConfigured")}
              </p>
            )}
          </div>
        </div>
        <form className="stack" onSubmit={props.saveSystemEmail}>
          <div className="two-col">
            <label>
              {props.t("smtpEmail")}
              <input
                value={form.fromEmail}
                onChange={(event) => props.setSystemEmailForm({ ...form, fromEmail: event.target.value.trim() })}
                type="email"
                required
              />
            </label>
            <label>
              {props.t("passwordOrCode")}
              <input
                value={form.password}
                onChange={(event) => props.setSystemEmailForm({ ...form, password: event.target.value })}
                type="password"
                placeholder={props.systemEmailConfig?.hasPassword ? props.t("keepPasswordPlaceholder") : ""}
              />
            </label>
          </div>
          <div className="two-col">
            <label>
              {props.t("smtpHost")}
              <input
                value={form.host}
                onChange={(event) => props.setSystemEmailForm({ ...form, host: event.target.value.trim() })}
                required
              />
            </label>
            <label>
              {props.t("smtpPort")}
              <input
                value={form.port}
                onChange={(event) => props.setSystemEmailForm({ ...form, port: event.target.value })}
                inputMode="numeric"
                required
              />
            </label>
          </div>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.useSsl}
              onChange={(event) => props.setSystemEmailForm({ ...form, useSsl: event.target.checked })}
            />
            <span>{props.t("useSsl")}</span>
          </label>
          <div>
            <button className="button primary" disabled={props.isBusy}>{props.t("save")}</button>
          </div>
        </form>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2 className="headline">{props.t("adminUsers")}</h2>
        </div>
        <div className="admin-user-list">
          {props.users.map((adminUser) => {
            const ownedCases = casesByUserId.get(adminUser.id) ?? [];
            return (
              <div key={adminUser.id} className="admin-user-card">
                <div className="admin-user-header">
                  <div>
                    <div className="case-name">{adminUser.email}</div>
                    <div className="case-meta">
                      {adminUser.role} · {adminUser.is_email_verified ? props.t("verified") : props.t("notVerified")}
                    </div>
                  </div>
                  <span className="status-badge">{adminUser.case_count} {props.t("casesOwned")}</span>
                </div>
                <div className="admin-user-metrics">
                  <Metric label={props.t("lastQuery")} value={formatTime(adminUser.last_checked_at, props.languageMode)} />
                  <Metric label={props.t("createdAt")} value={formatTime(adminUser.created_at, props.languageMode)} />
                  <Metric label={props.t("updatedAt")} value={formatTime(adminUser.updated_at, props.languageMode)} />
                </div>
                <div className="case-list compact">
                  {ownedCases.map((item) => (
                    <div key={item.id} className="admin-case-row">
                      <span>{item.displayName}</span>
                      <span className="mono-text">{item.applicationNum}</span>
                      <span className={getStatusBadgeClass(item.lastStatus)}>{item.lastStatus ?? props.t("waitFirstQuery")}</span>
                    </div>
                  ))}
                  {ownedCases.length === 0 && <p className="empty-state compact">{props.t("noCases")}</p>}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2 className="headline">{props.t("systemLogs")}</h2>
          <button className="button secondary" onClick={props.reload}>{props.t("refresh")}</button>
        </div>
        <div className="log-table-wrap">
          <table className="log-table">
            <thead>
              <tr>
                <th>{props.t("lastCheckedAt")}</th>
                <th>{props.t("executor")}</th>
                <th>{props.t("profile")}</th>
                <th>{props.t("applicationId")}</th>
                <th>{props.t("lastCheckMode")}</th>
                <th>{props.t("status")}</th>
                <th>{props.t("duration")}</th>
                <th>{props.t("changeContent")}</th>
              </tr>
            </thead>
            <tbody>
              {props.queryRuns.map((run) => (
                <tr key={run.id}>
                  <td>{formatTime(run.finished_at, props.languageMode)}</td>
                  <td>{run.user_email}</td>
                  <td>{run.display_name}</td>
                  <td className="mono-text">{run.application_num}</td>
                  <td>{formatTriggerType(run.trigger_type, props.t)}</td>
                  <td>
                    <span className={`status-badge ${run.success ? "success" : "error"}`}>
                      {run.success ? props.t("success") : props.t("error")}
                    </span>
                  </td>
                  <td className="mono-text">{run.duration_ms}ms</td>
                  <td>
                    {run.status ? (
                      <span className={getStatusBadgeClass(run.status)}>{run.status}</span>
                    ) : (
                      run.error_message || props.t("noStatusChange")
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="log-card-list">
            {props.queryRuns.map((run) => (
              <div key={run.id} className="log-card">
                <div className="log-card-header">
                  <span>{formatTime(run.finished_at, props.languageMode)}</span>
                  <span className={`status-badge ${run.success ? "success" : "error"}`}>
                    {run.success ? props.t("success") : props.t("error")}
                  </span>
                </div>
                <div className="log-card-grid">
                  <Metric label={props.t("executor")} value={run.user_email} />
                  <Metric label={props.t("profile")} value={run.display_name} />
                  <Metric label={props.t("applicationId")} value={run.application_num} />
                  <Metric label={props.t("lastCheckMode")} value={formatTriggerType(run.trigger_type, props.t)} />
                  <Metric label={props.t("duration")} value={`${run.duration_ms}ms`} />
                  <Metric label={props.t("changeContent")}>
                    {run.status ? (
                      <span className={getStatusBadgeClass(run.status, "metric-status")}>{run.status}</span>
                    ) : (
                      run.error_message || props.t("noStatusChange")
                    )}
                  </Metric>
                </div>
              </div>
            ))}
          </div>
          {props.queryRuns.length === 0 && <p className="empty-state">{props.t("noLogs")}</p>}
        </div>
      </section>
    </div>
  );
}

function CaseFormView(props: {
  caseForm: CaseForm;
  setCaseForm: React.Dispatch<React.SetStateAction<CaseForm>>;
  saveCase: (e: FormEvent<HTMLFormElement>) => Promise<void>;
  isBusy: boolean;
  t: (key: TranslationKey) => string;
  languageMode: LanguageMode;
}) {
  const form = props.caseForm;
  const setForm = props.setCaseForm;

  return (
    <form className="stack" onSubmit={props.saveCase}>
      <div className="official-form-note">
        <strong>{props.t("visaApplicationType")}</strong>
        <span>{props.t("visaTypeNiv")}</span>
      </div>

      <div className="form-section">
        <p className="section-help">{props.t("queryHint")}</p>
        <label>
          {props.t("caseName")}
          <input value={form.displayName} onChange={(e) => setForm({ ...form, displayName: e.target.value })} required placeholder={props.t("caseNamePlaceholder")} />
        </label>
        <label>
          {props.t("location")}
          <select
            value={form.location}
            onChange={(e) => setForm({ ...form, location: e.target.value })}
            required
            className="select-input"
          >
            {ceacLocations.map((location) => (
              <option key={location} value={location}>{location}</option>
            ))}
          </select>
        </label>
        <label>
          {props.t("applicationId")}
          <input value={form.applicationNum} onChange={(e) => setForm({ ...form, applicationNum: e.target.value.trim().toUpperCase() })} required placeholder="AA0020AKAX or 2012118 345 0001" />
          <span className="field-hint">(e.g., AA0020AKAX or 2012118 345 0001)</span>
        </label>
      </div>

      <div className="form-section">
        <p className="section-help">{props.t("pre2022Note")}</p>
      <div className="two-col">
        <label>
            {props.t("passport")}
            <input value={form.passportNumber} onChange={(e) => setForm({ ...form, passportNumber: e.target.value.trim().toUpperCase() })} required placeholder={props.t("passportPlaceholder")} />
          </label>
          <label>
            {props.t("firstFiveSurname")}
            <input
              value={form.surname}
              onChange={(e) => setForm({ ...form, surname: e.target.value.trim().toUpperCase().slice(0, 5) })}
              required
              maxLength={5}
              placeholder={props.languageMode === "zh" ? "姓的前五个字母，或 NA" : "First 5 letters or NA"}
            />
            <span className="field-hint">{props.t("firstFiveSurnameHint")}</span>
          </label>
        </div>
      </div>

      <div className="form-section">
        <p className="section-help">{props.t("deliverySection")}</p>
        <label>
          {props.t("deliveryEmail")}
          <input value={form.receiveEmail} onChange={(e) => setForm({ ...form, receiveEmail: e.target.value.trim() })} type="email" required />
        </label>

      <label className="checkbox">
        <input type="checkbox" checked={form.isEnabled} onChange={(e) => setForm({ ...form, isEnabled: e.target.checked })} />
        <span className="body-sm">{props.t("autoMonitor")}</span>
      </label>

      <label className="checkbox">
        <input type="checkbox" checked={form.emailNotificationsEnabled} onChange={(e) => setForm({ ...form, emailNotificationsEnabled: e.target.checked })} />
        <span className="body-sm">{props.t("emailPushSetting")}</span>
      </label>

      <label>
        {props.t("senderConfig")}
        <div className="segmented">
          <button type="button" className={form.senderMode === "system" ? "selected" : ""} onClick={() => setForm({ ...form, senderMode: "system" })}>{props.t("systemSender")}</button>
          <button type="button" className={form.senderMode === "custom" ? "selected" : ""} onClick={() => setForm({ ...form, senderMode: "custom" })}>{props.t("useCustomSmtp")}</button>
        </div>
      </label>

      {form.senderMode === "custom" && (
        <div className="smtp-box">
          <label>{props.t("smtpEmail")} <input value={form.smtpFromEmail} onChange={(e) => setForm({ ...form, smtpFromEmail: e.target.value })} type="email" required /></label>
          <div className="two-col">
            <label>{props.t("smtpHost")} <input value={form.smtpHost} onChange={(e) => setForm({ ...form, smtpHost: e.target.value })} required /></label>
            <label>{props.t("smtpPort")} <input value={form.smtpPort} onChange={(e) => setForm({ ...form, smtpPort: e.target.value })} required /></label>
          </div>
          <label>{props.t("passwordOrCode")} <input value={form.smtpPassword} onChange={(e) => setForm({ ...form, smtpPassword: e.target.value })} type="password" required /></label>
          <label className="checkbox"><input type="checkbox" checked={form.smtpUseSsl} onChange={(e) => setForm({ ...form, smtpUseSsl: e.target.checked })} /> <span>{props.t("useSsl")}</span></label>
        </div>
      )}
      </div>

      <div style={{ marginTop: "16px" }}>
        <button className="button primary" disabled={props.isBusy}>{props.t("save")}</button>
      </div>
    </form>
  );
}
