import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Bell,
  CheckCircle2,
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

type ThemeMode = "dark" | "light";
type ViewMode = "dashboard" | "admin";
type AuthMode = "login" | "register";

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
  success: number;
  status: string | null;
  error_message: string;
  duration_ms: number;
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
    throw new Error(payload.detail ?? "请求失败");
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

function formatTime(value: string | null): string {
  if (!value) {
    return "尚未记录";
  }
  return new Date(value).toLocaleString();
}

function getRememberedCredentials(): { email: string; password: string; remember: boolean } {
  const enabled = localStorage.getItem("rememberLogin") === "true";
  if (!enabled) {
    return { email: "", password: "", remember: false };
  }
  return {
    email: localStorage.getItem("rememberedEmail") ?? "",
    password: localStorage.getItem("rememberedPassword") ?? "",
    remember: true,
  };
}

export function App() {
  const [themeMode, setThemeMode] = useState<ThemeMode>(getInitialTheme);
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [viewMode, setViewMode] = useState<ViewMode>("dashboard");
  const [user, setUser] = useState<User | null>(null);
  const [cases, setCases] = useState<CeacCase[]>([]);
  const [adminCases, setAdminCases] = useState<CeacCase[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [queryRuns, setQueryRuns] = useState<QueryRun[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<number | null>(null);
  const [caseForm, setCaseForm] = useState<CaseForm>(emptyCaseForm);
  const rememberedCredentials = useMemo(getRememberedCredentials, []);
  const [authEmail, setAuthEmail] = useState(rememberedCredentials.email);
  const [authPassword, setAuthPassword] = useState(rememberedCredentials.password);
  const [rememberLogin, setRememberLogin] = useState(rememberedCredentials.remember);
  const [registerCode, setRegisterCode] = useState("");
  const [message, setMessage] = useState("");
  const [isBusy, setIsBusy] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = themeMode;
    localStorage.setItem("themeMode", themeMode);
  }, [themeMode]);

  useEffect(() => {
    requestJson<{ user: User }>("/api/me")
      .then((payload) => {
        setUser(payload.user);
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
    } else {
      setHistory([]);
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

  async function loadAdminData() {
    const [runsPayload, casesPayload] = await Promise.all([
      requestJson<{ runs: QueryRun[] }>("/api/admin/query-runs"),
      requestJson<{ cases: CeacCase[] }>("/api/admin/cases"),
    ]);
    setQueryRuns(runsPayload.runs);
    setAdminCases(casesPayload.cases);
  }

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsBusy(true);
    setMessage("");
    try {
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
        localStorage.removeItem("rememberedEmail");
        localStorage.removeItem("rememberedPassword");
      }
      setUser(payload.user);
      await loadCases();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "操作失败");
    } finally {
      setIsBusy(false);
    }
  }

  async function sendCode() {
    setIsBusy(true);
    setMessage("");
    try {
      await requestJson<{ ok: boolean }>("/api/auth/send-code", {
        method: "POST",
        body: JSON.stringify({ email: authEmail }),
      });
      setMessage("验证码已发送，请查看邮箱。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "验证码发送失败");
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
      setMessage("签证档案已创建。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
    } finally {
      setIsBusy(false);
    }
  }

  async function runTest(caseId: number) {
    setIsBusy(true);
    setMessage("正在查询 CEAC，请稍候。");
    try {
      const payload = await requestJson<{ success: boolean; changed: boolean; error: string }>(`/api/cases/${caseId}/test-query`, {
        method: "POST",
        body: "{}",
      });
      await loadCases();
      await loadHistory(caseId);
      setMessage(payload.success ? `快速查询完成：${payload.changed ? "状态已更新" : "状态未变化"}` : payload.error);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "查询失败");
    } finally {
      setIsBusy(false);
    }
  }

  async function sendTestEmail(caseId: number) {
    setIsBusy(true);
    setMessage("正在发送现有状态邮件。");
    try {
      await requestJson<{ success: boolean; error: string }>(`/api/cases/${caseId}/test-email`, {
        method: "POST",
        body: "{}",
      });
      setMessage("测试邮件已按当前状态模板发送。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "测试邮件发送失败");
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
      setMessage(!targetCase.emailNotificationsEnabled ? "已开启状态更新邮件推送。" : "已关闭状态更新邮件推送。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "邮件推送设置保存失败");
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
        <ThemeButton themeMode={themeMode} setThemeMode={setThemeMode} />
        <div className="auth-header">
          <div className="brand-mark">C</div>
          <h1 className="display-lg">CEACStatusBot</h1>
          <p className="subhead" style={{ marginTop: '16px' }}>签证状态监控与邮件提醒控制台</p>
        </div>
        <section className="auth-panel">
          <form className="stack" onSubmit={submitAuth}>
            <div className="segmented">
              <button type="button" className={authMode === "login" ? "selected" : ""} onClick={() => setAuthMode("login")}>
                登录
              </button>
              <button type="button" className={authMode === "register" ? "selected" : ""} onClick={() => setAuthMode("register")}>
                注册
              </button>
            </div>
            <label>
              邮箱
              <input value={authEmail} onChange={(event) => setAuthEmail(event.target.value)} type="email" required autoComplete="username" />
            </label>
            <label>
              密码
              <input value={authPassword} onChange={(event) => setAuthPassword(event.target.value)} type="password" required minLength={8} autoComplete={authMode === "login" ? "current-password" : "new-password"} />
            </label>
            {authMode === "login" && (
              <label className="checkbox">
                <input type="checkbox" checked={rememberLogin} onChange={(event) => setRememberLogin(event.target.checked)} />
                <span className="body-sm">记住账号和密码</span>
              </label>
            )}
            {authMode === "register" && (
              <label>
                验证码
                <div className="inline-field">
                  <input value={registerCode} onChange={(event) => setRegisterCode(event.target.value)} required />
                  <button type="button" className="button secondary" onClick={sendCode} disabled={isBusy}>
                    发送
                  </button>
                </div>
              </label>
            )}
            <button className="button primary" disabled={isBusy}>{authMode === "login" ? "登录控制台" : "创建账号"}</button>
            {message && <p className="notice">{message}</p>}
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="top-nav">
        <div className="brand-lockup">
          <span className="brand-mark">C</span>
          CEACStatusBot
        </div>
        <div className="nav-actions">
          <button className={`nav-tab ${viewMode === "dashboard" ? "active" : ""}`} onClick={() => setViewMode("dashboard")}>
            <UserRound size={16} /> 我的档案
          </button>
          {user.role === "admin" && (
            <button
              className={`nav-tab ${viewMode === "admin" ? "active" : ""}`}
              onClick={() => {
                setViewMode("admin");
                void loadAdminData();
              }}
            >
              <Shield size={16} /> 管理员
            </button>
          )}
          <ThemeButton themeMode={themeMode} setThemeMode={setThemeMode} />
          <button className="button tertiary" onClick={logout} title="退出登录">
            <LogOut size={16} />
          </button>
        </div>
      </header>

      <section className="workspace">
        <header className="page-header">
          <div>
            <p className="eyebrow" style={{ color: 'var(--primary-hover)' }}>当前登录: {user.email}</p>
            <h1 className="display-md">{viewMode === "admin" ? "管理后台" : "签证状态监控"}</h1>
          </div>
          {message && <p className="notice">{message}</p>}
        </header>

        {viewMode === "dashboard" ? (
          <div className="dashboard-layout">
            <div className="stack">
              <section className="panel">
                <div className="panel-title">
                  <h2 className="headline">档案列表</h2>
                  <button className="button secondary" title="新建档案" onClick={() => { setSelectedCaseId(null); setCaseForm(emptyCaseForm); }}>
                    <Plus size={16} /> 新增
                  </button>
                </div>
                <div className="case-list">
                  {cases.map((item) => (
                    <div key={item.id} className={`case-row ${selectedCaseId === item.id ? "selected" : ""}`} onClick={() => setSelectedCaseId(item.id)}>
                      <div className="case-info">
                        <div className="case-name">{item.displayName}</div>
                        <div className="case-meta">{item.applicationNum || "未提供流水号"}</div>
                      </div>
                      <span className={`status-badge ${item.lastStatus === "Issued" ? "success" : item.lastStatus === "Refused" ? "error" : ""}`}>{item.lastStatus ?? "等待首次查询"}</span>
                    </div>
                  ))}
                  {cases.length === 0 && <p className="empty-state">尚未添加档案</p>}
                </div>
              </section>
            </div>

            <div className="stack">
              {selectedCaseId === null ? (
                <section className="panel">
                  <div className="panel-title">
                    <h2 className="headline">建立监控档案</h2>
                  </div>
                  <CaseFormView caseForm={caseForm} setCaseForm={setCaseForm} saveCase={saveCase} isBusy={isBusy} />
                </section>
              ) : selectedCase ? (
                <>
                  <section className="panel">
                    <div className="panel-title">
                      <h2 className="headline">{selectedCase.displayName}</h2>
                      <div className="row-actions">
                        <button className="button secondary" onClick={() => runTest(selectedCase.id)} disabled={isBusy}>
                          <Activity size={16} /> 快速查询
                        </button>
                        <button className="button secondary" onClick={() => sendTestEmail(selectedCase.id)} disabled={isBusy || history.length === 0}>
                          <Mail size={16} /> 测试发信
                        </button>
                        <button className="icon-button danger" onClick={() => { if (confirm("确认删除此档案？")) void removeCase(selectedCase.id); }}>
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                    
                    <div className="stack" style={{ marginBottom: "24px" }}>
                      <div className="two-col">
                        <Metric label="办理地点" value={selectedCase.location} />
                        <Metric label="面签号 / 护照号" value={`${selectedCase.applicationNum} / ${selectedCase.passportNumber}`} />
                      </div>
                      <div className="two-col">
                        <Metric label="接收邮箱" value={selectedCase.receiveEmail} />
                        <Metric label="最后状态" value={selectedCase.lastStatus || "未就绪"} />
                      </div>
                      <div className="settings-row">
                        <label className="checkbox">
                          <input
                            type="checkbox"
                            checked={selectedCase.emailNotificationsEnabled}
                            onChange={() => toggleEmailPush(selectedCase)}
                            disabled={isBusy}
                          />
                          <span className="body-sm">状态更新时发送邮件推送</span>
                        </label>
                        <span className={`status-badge ${selectedCase.emailNotificationsEnabled ? "success" : ""}`}>
                          {selectedCase.emailNotificationsEnabled ? "邮件推送开启" : "邮件推送关闭"}
                        </span>
                      </div>
                    </div>
                  </section>

                  <section className="panel">
                    <div className="panel-title">
                      <h2 className="subhead">状态历史</h2>
                      <History size={18} />
                    </div>
                    <div className="timeline">
                      {history.map((record) => (
                        <div key={record.id} className="timeline-item">
                          <div className="timeline-header">
                            <span className="timeline-time">{formatTime(record.fetchedAt)}</span>
                            <span className={`status-badge ${record.status === "Issued" ? "success" : record.status === "Refused" ? "error" : ""}`}>{record.status}</span>
                          </div>
                          <div className="timeline-desc">{record.description}</div>
                        </div>
                      ))}
                      {history.length === 0 && <p className="empty-state">暂无历史状态记录</p>}
                    </div>
                  </section>
                </>
              ) : null}
            </div>
          </div>
        ) : (
          <AdminPanel queryRuns={queryRuns} cases={adminCases} reload={loadAdminData} />
        )}
      </section>
    </main>
  );
}

function ThemeButton(props: { themeMode: ThemeMode; setThemeMode: (mode: ThemeMode) => void }) {
  return (
    <button
      className="button tertiary theme-toggle"
      onClick={() => props.setThemeMode(props.themeMode === "dark" ? "light" : "dark")}
      title={`切换至${props.themeMode === "dark" ? "亮色" : "暗色"}模式`}
      style={{ padding: "8px" }}
    >
      {props.themeMode === "dark" ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}

function Metric(props: { label: string; value: string }) {
  return (
    <div style={{ display: 'grid', gap: '4px' }}>
      <div className="caption" style={{ color: 'var(--ink-subtle)' }}>{props.label}</div>
      <div className="body-sm">{props.value}</div>
    </div>
  );
}

function AdminPanel(props: { queryRuns: QueryRun[]; cases: CeacCase[]; reload: () => Promise<void> }) {
  return (
    <div className="stack">
      <section className="panel">
        <div className="panel-title">
          <h2 className="headline">系统监控日志</h2>
          <button className="button secondary" onClick={props.reload}>刷新数据</button>
        </div>
        <div className="case-list">
          {props.queryRuns.map((run) => (
            <div key={run.id} className="changelog-row">
              <div>
                <div className="changelog-label">执行人</div>
                <div className="changelog-value">{run.user_email}</div>
              </div>
              <div>
                <div className="changelog-label">案卷</div>
                <div className="changelog-value">{run.display_name}</div>
              </div>
              <div>
                <div className="changelog-label">状态</div>
                <div className="changelog-value"><span className={`status-badge ${run.success ? "success" : "error"}`}>{run.success ? "成功" : "失败"}</span></div>
              </div>
              <div>
                <div className="changelog-label">耗时</div>
                <div className="changelog-value mono-text">{run.duration_ms}ms</div>
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <div className="changelog-label">变更内容</div>
                <div className="changelog-value">{run.status || run.error_message || "未发生状态变更"}</div>
              </div>
            </div>
          ))}
          {props.queryRuns.length === 0 && <p className="empty-state">暂无日志</p>}
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
}) {
  const form = props.caseForm;
  const setForm = props.setCaseForm;

  return (
    <form className="stack" onSubmit={props.saveCase}>
      <label>
        显示名称
        <input value={form.displayName} onChange={(e) => setForm({ ...form, displayName: e.target.value })} required />
      </label>
      <label>
        面签地点 (Location)
        <select
          value={form.location}
          onChange={(e) => setForm({ ...form, location: e.target.value })}
          required
          style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", background: "var(--surface-1)", color: "var(--ink)", border: "1px solid var(--hairline)" }}
        >
          <option value="CHINA, BEIJING">CHINA, BEIJING</option>
          <option value="CHINA, GUANGZHOU">CHINA, GUANGZHOU</option>
          <option value="CHINA, SHANGHAI">CHINA, SHANGHAI</option>
          <option value="CHINA, SHENYANG">CHINA, SHENYANG</option>
          <option value="CHINA, CHENGDU">CHINA, CHENGDU</option>
        </select>
      </label>
      <div className="two-col">
        <label>
          面签号码 (Application ID)
          <input value={form.applicationNum} onChange={(e) => setForm({ ...form, applicationNum: e.target.value })} required />
        </label>
        <label>
          护照号码 (Passport)
          <input value={form.passportNumber} onChange={(e) => setForm({ ...form, passportNumber: e.target.value })} required />
        </label>
      </div>
      <div className="two-col">
        <label>
          姓氏 (Surname)
          <input value={form.surname} onChange={(e) => setForm({ ...form, surname: e.target.value })} required />
        </label>
        <label>
          接收提醒邮箱
          <input value={form.receiveEmail} onChange={(e) => setForm({ ...form, receiveEmail: e.target.value })} type="email" required />
        </label>
      </div>

      <label className="checkbox">
        <input type="checkbox" checked={form.isEnabled} onChange={(e) => setForm({ ...form, isEnabled: e.target.checked })} />
        <span className="body-sm">启用自动监控</span>
      </label>

      <label className="checkbox">
        <input type="checkbox" checked={form.emailNotificationsEnabled} onChange={(e) => setForm({ ...form, emailNotificationsEnabled: e.target.checked })} />
        <span className="body-sm">状态更新时发送邮件推送</span>
      </label>

      <label>
        发件人配置
        <div className="segmented">
          <button type="button" className={form.senderMode === "system" ? "selected" : ""} onClick={() => setForm({ ...form, senderMode: "system" })}>系统发信</button>
          <button type="button" className={form.senderMode === "custom" ? "selected" : ""} onClick={() => setForm({ ...form, senderMode: "custom" })}>自定义 SMTP</button>
        </div>
      </label>

      {form.senderMode === "custom" && (
        <div className="smtp-box">
          <label>发件邮箱 <input value={form.smtpFromEmail} onChange={(e) => setForm({ ...form, smtpFromEmail: e.target.value })} type="email" required /></label>
          <div className="two-col">
            <label>SMTP 服务器 <input value={form.smtpHost} onChange={(e) => setForm({ ...form, smtpHost: e.target.value })} required /></label>
            <label>SMTP 端口 <input value={form.smtpPort} onChange={(e) => setForm({ ...form, smtpPort: e.target.value })} required /></label>
          </div>
          <label>密码 / 授权码 <input value={form.smtpPassword} onChange={(e) => setForm({ ...form, smtpPassword: e.target.value })} type="password" required /></label>
          <label className="checkbox"><input type="checkbox" checked={form.smtpUseSsl} onChange={(e) => setForm({ ...form, smtpUseSsl: e.target.checked })} /> <span>启用 SSL</span></label>
        </div>
      )}

      <div style={{ marginTop: "16px" }}>
        <button className="button primary" disabled={props.isBusy}>保存档案</button>
      </div>
    </form>
  );
}
