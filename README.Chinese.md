# CEACStatusBot Web

CEACStatusBot Web 是一个自托管的美国签证 CEAC 状态监控面板。它提供账号注册登录、邮箱验证码、忘记密码、多个签证档案管理、状态历史、邮件通知、管理员后台和生产安全基线，适合本地开发后部署到自己的服务器向公网开放。

本项目是修改版本，遵循 GPLv3 许可证发布。项目保留并改造了 CEAC 状态查询与验证码识别相关思路，感谢原项目 [Andision/CEACStatusBot](https://github.com/Andision/CEACStatusBot)。

## 功能

- FastAPI 后端、SQLite 数据库、APScheduler 入队调度、独立 Worker 消费查询任务。
- React + Vite + TypeScript 前端控制台，支持暗色 / 亮色模式和中英文切换。
- 开放注册，注册和忘记密码均通过邮箱验证码完成。
- 每个用户可创建多个 CEAC 查询档案，并开启或关闭状态更新邮件推送。
- 每个启用档案每小时随机分钟入队查询，Issued 后降为每天一次并在一周后自动停止。
- CEAC 状态进入 Approved 或 Issued 后，邮件会邀请用户填写 UID/HAL 开启 GTS 护照预约 slot 监控。
- GTS 护照预约监控绑定到签证档案，默认每 5-10 分钟随机轮询；自动轮询开关和 slot 变化邮件推送开关相互独立。
- 立即查询会创建手动任务，前端轮询任务状态并刷新档案和时间线；非管理员账号每天有手动查询次数限制。
- 状态无变化不发邮件；状态或 CEAC 更新时间变化时写入历史并发送通知。
- 支持系统默认 SMTP，也支持用户自定义 SMTP。
- 管理员可查看所有用户资料、用户分组档案、状态历史、查询日志和默认发信配置。
- 查询日志记录手动 / 自动抓取来源、绝对时间、耗时、成功失败和错误信息。
- 前端包含自定义 SVG favicon / 品牌图标，以及 ICP 备案号底部链接。

## 账号初始化

默认不会自动创建本地测试账号。公网部署时请通过注册流程创建账号，或由管理员直接在生产数据库中创建首个管理员账号。

如果只在本地开发并确实需要演示账号，可以临时设置 `SEED_DEFAULT_USERS=true`，并同时提供 `DEFAULT_ADMIN_EMAIL` / `DEFAULT_ADMIN_PASSWORD`。不要在公网环境启用该开关。

## 本地开发

```bash
pip install uv
uv sync
cp .env.example .env
uv run uvicorn CEACStatusBot.web.main:app --reload --host 127.0.0.1 --port 8000
```

另开一个终端启动 Worker：

```bash
uv run python -m CEACStatusBot.web.worker
```

启动前端：

```bash
cd frontend
npm install
npm run dev
```

打开 `http://127.0.0.1:5173`。VS Code 调试配置位于 `.vscode/launch.json`，不会自动启动浏览器。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_PATH` | `ceacstatusbot.sqlite3` | SQLite 数据库路径 |
| `SECRET_KEY` | 开发默认值 | 会话签名密钥，公网必须修改 |
| `CREDENTIAL_KEY_FILE` | 空 | AES-256-GCM 主密钥文件路径，生产建议 `/opt/ceacstatusbot-runtime/secrets/credential-master.key` |
| `ENCRYPTION_KEY` | 空 | 旧 Fernet 密文兼容 / 迁移使用，不作为新凭证主密钥 |
| `SYSTEM_FROM_EMAIL` | 空 | 系统默认发信邮箱 |
| `SYSTEM_EMAIL_PASSWORD` | 空 | 系统默认发信邮箱授权码；生产建议由管理员后台保存到加密存储 |
| `SYSTEM_SMTP_HOST` | `smtp.exmail.qq.com` | 系统 SMTP 主机 |
| `SYSTEM_SMTP_PORT` | `465` | 系统 SMTP 端口 |
| `SYSTEM_SMTP_USE_SSL` | `true` | 是否使用 SMTP SSL |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | 允许访问后端的前端地址 |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | 敏感请求允许的 Origin / Referer 来源 |
| `COOKIE_SECURE` | `false` | 本地默认 `false`，HTTPS 生产必须 `true` |
| `WORKER_POLL_INTERVAL_SECONDS` | `1` | Worker 轮询 SQLite 队列间隔；GTS 零点加频任务需要秒级拾取 |
| `DAILY_MANUAL_QUERY_LIMIT` | `20` | 非管理员账号每天可发起的 CEAC/GTS 手动查询次数，管理员不受限制 |
| `SEED_DEFAULT_USERS` | `false` | 本地演示账号种子开关，公网必须保持 `false` |
| `DEFAULT_ADMIN_EMAIL` | 空 | 本地种子管理员邮箱，仅 `SEED_DEFAULT_USERS=true` 时使用 |
| `DEFAULT_ADMIN_PASSWORD` | 空 | 本地种子管理员密码，仅 `SEED_DEFAULT_USERS=true` 时使用 |
| `DEFAULT_USER_EMAIL` | 空 | 本地种子普通用户邮箱，仅 `SEED_DEFAULT_USERS=true` 时使用 |
| `DEFAULT_USER_PASSWORD` | 空 | 本地种子普通用户密码，仅 `SEED_DEFAULT_USERS=true` 时使用 |
| `VITE_ICP_RECORD_NUMBER` | 空 | 前端底部展示的 ICP 备案号，例如 `沪ICP备2026015123号-1` |

腾讯企业邮箱常用配置：

- SMTP：`smtp.exmail.qq.com`
- SMTP SSL 端口：`465`
- IMAP：`imap.exmail.qq.com`
- IMAP SSL 端口：`993`

当前 Web 应用核心流程只需要 SMTP；IMAP 暂不参与状态查询或通知。

## 查询与通知逻辑

每个启用的签证档案都会保存 `nextCheckAt`。调度器每分钟扫描到期档案，并将自动查询任务写入 SQLite 队列。独立 Worker 消费队列、调用 CEAC 查询、记录查询日志、更新状态历史并发送邮件通知。

立即查询不会由 Web 进程直接执行爬虫，而是创建 `manual` 任务并返回任务 ID。前端轮询任务状态，完成后刷新档案信息和状态时间线。非管理员账号的 CEAC 立即查询和 GTS 立即查询 slot 共用每日手动查询额度，默认每天 20 次，可通过 `DAILY_MANUAL_QUERY_LIMIT` 调整；管理员账号不受限制。

系统会比较最近一次历史记录中的状态和 CEAC 更新时间：

- 完全一致：只记录查询日志，不发送通知。
- 状态或 CEAC 更新时间变化：写入该档案的状态历史，并发送邮件。

如果某个档案关闭了“状态更新邮件推送”，系统仍会定时查询并记录时间线，但不会在状态变化时自动发邮件。用户仍可手动点击“测试发信”，按最新已有状态模板发送一封邮件。

护照预约 slot 监控使用 GTS 官网同源 API：先用 UID/HAL 调用 `https://scheduling-api.gtspremium.com/authenticate` 获取 token，再调用 `/availability7days/` 查询 7 天可用时间。UID/HAL、GTS 原始返回和 slot 变化历史都会加密保存。系统会把 GTS 返回归一化为三种状态：`not_eligible` 表示暂不具备预约资格，`no_slot` 表示已可预约但暂无可选时间，`has_slot` 表示发现一个或多个可预约时间。自动轮询由“启用自动监控”控制，slot 变化邮件由“状态更新时发送邮件推送”控制。系统会在 `not_eligible -> no_slot`、`no_slot -> has_slot`、以及 `has_slot` 时间列表变化时发邮件。处于 `no_slot` 后按中国时间零点加频：23:59-00:02 约 15 秒一次，23:59:45-00:00:30 核心窗口约 5 秒一次，并明确覆盖 00:00:00 和 00:00:02。发现 slot 后后续查询先放缓到约 30 秒，再到约 1 分钟，若仍无变化则恢复 5-10 分钟常规频率。GTS 查询任务同样由 Worker 消费，触发类型显示为 `passport_slot_manual` 或 `passport_slot_automatic`。

## 生产安全基线

- 登录密码使用 Argon2id；旧 PBKDF2-SHA256 哈希仅用于兼容迁移，用户登录成功后自动升级。
- CEAC 档案敏感字段、GTS UID/HAL、SMTP 授权码和原始查询快照使用 AES-256-GCM 可逆加密。
- 主密钥放在仓库外本地密钥文件，不写入代码、README、`backend.env` 或 GitHub。
- 生产 Cookie 必须启用 `HttpOnly + SameSite=Lax + Secure`。
- 所有敏感 API 请求校验 `Origin` / `Referer`，生产只信任 `https://ceac.mikezhuang.cn`。
- CEAC 爬虫目标固定为 `https://ceac.state.gov`，GTS slot 查询目标固定为 `https://scheduling-api.gtspremium.com`，用户输入不能影响请求 Host 或 URL。
- 生产入口只走 HTTPS 域名；8010 不作为公网入口。
- Nginx 配置连接超时、请求限流、安全响应头，并只启用 TLS 1.2 / TLS 1.3。

更完整的安全模型见 [SECURITY.md](SECURITY.md)。

## 部署与运维

生产部署说明见 [DEPLOYMENT.md](DEPLOYMENT.md)，日常运维和故障处理见 [OPERATIONS.md](OPERATIONS.md)。

核心约定：

- 代码仓库：`/opt/ceacstatusbot`
- 运行时数据：`/opt/ceacstatusbot-runtime`
- 前端构建产物：`/var/www/ceacstatusbot/frontend/dist`
- 后端服务：`ceacstatusbot-backend.service`
- Worker 服务：`ceacstatusbot-worker.service`
- 生产域名：`https://ceac.mikezhuang.cn`
- 自动部署仓库：`https://github.com/Mike-Zhuang/CEACStatusBot_Web`

部署时不要提交或覆盖 `.env`、`backend.env`、SQLite 数据库、主密钥文件、日志、备份、SMTP 授权码或服务器私钥。

## License

本项目遵循 [GNU General Public License v3.0](LICENSE)。如果你分发修改版本，需要继续遵守 GPLv3 的源码开放、许可证保留和修改声明要求。

## 致谢

感谢 [Andision/CEACStatusBot](https://github.com/Andision/CEACStatusBot)。本项目基于其 CEAC 自动查询方向与部分实现进行 Web 化、服务化和多用户改造。
