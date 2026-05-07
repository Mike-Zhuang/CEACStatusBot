# CEACStatusBot Web

🎉 **已部署上线:** 本服务已部署上线，可以直接访问 [ceac.mikezhuang.cn](https://ceac.mikezhuang.cn) 使用。

> **非盈利个人项目。** 如果 CEACStatusBot 对你有帮助，欢迎自愿赞赏支持服务器和维护成本。Premium 升级方式：在小红书发布包含网站链接、使用截图和使用感受的帖子后联系管理员；或赞赏时备注账号邮箱，管理员人工核对后升级。联系邮箱：`ceac-admin@mikezhuang.cn`。
>
> <img src="frontend/public/support/buy-me-a-coffee.jpg" alt="支持 CEACStatusBot" width="180" />
>
> 小字说明：本站为非官方服务，不隶属于美国国务院、CEAC、GTS 或中信银行。赞赏是自愿支持，不购买官方服务，不保证签证结果、护照进度、slot 可用性或预约成功。

CEACStatusBot Web 是一个自托管的美国签证 CEAC 状态监控面板。它提供账号注册登录、邮箱验证码、忘记密码、多个签证档案管理、状态历史、邮件通知、管理员后台和生产安全基线，适合本地开发后部署到自己的服务器向公网开放。

本项目是修改版本，遵循 GPLv3 许可证发布。项目保留并改造了 CEAC 状态查询与验证码识别相关思路，感谢原项目 [Andision/CEACStatusBot](https://github.com/Andision/CEACStatusBot)。

## 功能

- FastAPI 后端、SQLite 数据库、APScheduler 入队调度、独立 Worker 消费查询任务。
- React + Vite + TypeScript 前端控制台，支持暗色 / 亮色模式和中英文切换。
- 开放注册，注册和忘记密码均通过邮箱验证码完成。
- 普通账号可创建 1 个 CEAC 档案、每天手动刷新 1 次，并使用有限的每日业务邮件额度；Premium 账号可创建 5 个档案并拥有高额度查询/邮件额度；管理员不受限制。
- 每个启用档案每小时随机分钟入队查询，Issued 后降为每天一次并在一周后自动停止。
- CEAC 状态进入 Approved 或 Issued 后，邮件会邀请用户填写 UID/HAL 开启 GTS 护照预约 slot 监控。
- GTS 护照预约监控绑定到签证档案，默认每 5-10 分钟随机轮询；自动轮询开关和 slot 变化邮件推送开关相互独立。发现 slot 后会放缓到约每小时一次，用户预约成功后可在站内点击“我已预约，停止监控”。
- 立即查询会创建手动任务，前端轮询任务状态并刷新档案和时间线；非管理员账号每天有手动查询次数限制。
- 状态无变化不发邮件；状态或 CEAC 更新时间变化时写入历史并发送通知。
- 支持系统默认 SMTP，也支持用户自定义 SMTP。
- 管理员可查看所有用户资料、用户分组档案、状态历史、查询日志、默认发信配置和每个账号的 Worker 优先级。
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
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,ceac.mikezhuang.cn` | 应用层允许的 Host header |
| `TRUSTED_PROXY_IPS` | `127.0.0.1,::1` | 允许信任 `X-Forwarded-For` 的反向代理 IP |
| `API_MAX_BODY_BYTES` | `131072` | API 请求体最大字节数 |
| `COOKIE_SECURE` | `false` | 本地默认 `false`，HTTPS 生产必须 `true` |
| `SESSION_IDLE_TIMEOUT_MINUTES` | `720` | 会话空闲自动登出时间 |
| `SESSION_ABSOLUTE_TIMEOUT_DAYS` | `14` | 数据库会话最长有效期 |
| `AUTH_LOGIN_IP_DEVICE_LIMIT_PER_MINUTE` | `10` | 每个 IP/设备每分钟登录尝试上限 |
| `AUTH_LOGIN_EMAIL_FAILURE_LIMIT_PER_15_MINUTES` | `5` | 邮箱登录失败冷却阈值 |
| `AUTH_CODE_EMAIL_LIMIT_PER_HOUR` | `3` | 每个邮箱每小时验证码请求上限 |
| `AUTH_CODE_IP_DEVICE_LIMIT_PER_10_MINUTES` | `3` | 每个 IP/设备每 10 分钟验证码请求上限 |
| `STANDARD_API_LIMIT_PER_MINUTE` | `120` | 普通账号每分钟已登录 API 上限 |
| `PREMIUM_API_LIMIT_PER_MINUTE` | `300` | Premium 账号每分钟已登录 API 上限 |
| `ADMIN_API_LIMIT_PER_MINUTE` | `600` | 管理员每分钟已登录 API 上限 |
| `WORKER_POLL_INTERVAL_SECONDS` | `1` | Worker 轮询 SQLite 队列间隔；GTS 零点加频任务需要秒级拾取 |
| `STANDARD_DAILY_MANUAL_QUERY_LIMIT` | `1` | 普通账号每天可发起的 CEAC/GTS 手动查询次数 |
| `PREMIUM_DAILY_MANUAL_QUERY_LIMIT` | `1000` | Premium 账号每天可发起的 CEAC/GTS 手动查询次数 |
| `STANDARD_DAILY_EMAIL_LIMIT` | `5` | 普通账号每天可发送的 CEAC/GTS 业务邮件数量；注册和重置密码验证码不计入 |
| `PREMIUM_DAILY_EMAIL_LIMIT` | `1000` | Premium 账号每天可发送的 CEAC/GTS 业务邮件数量 |
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

立即查询不会由 Web 进程直接执行爬虫，而是创建 `manual` 任务并返回任务 ID。前端轮询任务状态，完成后刷新档案信息和状态时间线。CEAC 立即查询和 GTS 立即查询 slot 共用每日手动查询额度：普通账号默认每天 1 次，Premium 默认每天 1000 次，管理员账号不受限制。CEAC/GTS 业务邮件也有账号级每日额度：普通账号默认每天 5 封，Premium 默认每天 1000 封。Worker 优先级数值越小越优先；Premium 默认 50，普通账号默认 100，管理员可手动覆盖。

系统会比较最近一次历史记录中的状态和 CEAC 更新时间：

- 完全一致：只记录查询日志，不发送通知。
- 状态或 CEAC 更新时间变化：写入该档案的状态历史，并发送邮件。

如果某个档案关闭了“状态更新邮件推送”，系统仍会定时查询并记录时间线，但不会在状态变化时自动发邮件。用户仍可手动点击“测试发信”，按最新已有状态模板发送一封邮件。

护照预约 slot 监控使用 GTS 官网同源 API：先用 UID/HAL 调用 `https://scheduling-api.gtspremium.com/authenticate` 获取 token，再调用 `/availability7days/` 查询 7 天可用时间。UID/HAL、GTS 原始返回和 slot 变化历史都会加密保存。系统会把 GTS 返回归一化为三种状态：`not_eligible` 表示暂不具备预约资格，`no_slot` 表示已可预约但暂无可选时间，`has_slot` 表示发现一个或多个可预约时间。自动轮询由“启用自动监控”控制，slot 变化邮件由“状态更新时发送邮件推送”控制。系统会在 `not_eligible -> no_slot`、`no_slot -> has_slot`、以及 `has_slot` 时间列表变化时发邮件。`no_slot` 和 `has_slot` 邮件会包含完整 UID/HAL、GTS 官网入口、站内入口、操作提示和不要转发邮件的安全提醒；系统不使用猜测的 UID/HAL 深链，因为 GTS 官网没有公开可靠的自动填充 URL。slot 邮件会列出可读日期和具体时间，不展示原始 JSON/JWT 摘要。处于 `no_slot` 后按中国时间零点加频：23:59-00:02 约 15 秒一次，23:59:45-00:00:30 核心窗口约 5 秒一次，并明确覆盖 00:00:00 和 00:00:02。一旦确认进入 `no_slot` 或 `has_slot`，系统会自动停止并锁定对应 CEAC 自动查询，只有管理员可以恢复。发现 slot 后 GTS 后续查询放缓到约每小时一次，并且不再参与零点加频；用户在 GTS 官网预约成功后，应回到站内点击“我已预约，停止监控”。GTS 查询任务同样由 Worker 消费，触发类型显示为 `passport_slot_manual` 或 `passport_slot_automatic`；队列按 `users.worker_priority ASC, query_jobs.id ASC` 领取，数值越小越优先。

## 生产安全基线

- 登录密码使用 Argon2id；旧 PBKDF2-SHA256 哈希仅用于兼容迁移，用户登录成功后自动升级。
- CEAC 档案敏感字段、GTS UID/HAL、SMTP 授权码和原始查询快照使用 AES-256-GCM 可逆加密。
- 主密钥放在仓库外本地密钥文件，不写入代码、README、`backend.env` 或 GitHub。
- 生产 Cookie 必须启用 `HttpOnly + SameSite=Lax + Secure`。
- 所有敏感 API 请求校验 `Origin` / `Referer`，生产只信任 `https://ceac.mikezhuang.cn`。
- 应用层新增匿名设备 Cookie、SQLite 持久化 IP/设备/账号/邮箱限流、登录失败冷却、数据库会话空闲超时、请求体大小限制、Host 白名单和安全事件审计日志。
- “记住密码”会把密码保存在当前浏览器本地，只建议在私人设备上使用。
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
