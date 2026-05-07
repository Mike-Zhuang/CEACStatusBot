# 部署说明

本文档记录 CEACStatusBot Web 的生产部署约定。不要把生产账号、密码、SMTP 授权码、主密钥或数据库写入仓库。

## 目录约定

| 路径 | 用途 |
| --- | --- |
| `/opt/ceacstatusbot` | 代码仓库 |
| `/opt/ceacstatusbot-runtime` | 运行时数据目录 |
| `/opt/ceacstatusbot-runtime/backend.env` | 后端环境变量 |
| `/opt/ceacstatusbot-runtime/ceacstatusbot.sqlite3` | SQLite 数据库 |
| `/opt/ceacstatusbot-runtime/secrets` | 仓库外密钥目录 |
| `/opt/ceacstatusbot-runtime/secrets/credential-master.key` | AES-256-GCM 主密钥 |
| `/var/www/ceacstatusbot/frontend/dist` | 前端构建产物 |
| `/www/wwwlogs` | Nginx、backend、worker 日志 |

运行时目录和密钥目录不受 Git 管理，自动部署脚本不得删除或覆盖。

## 仓库与自动同步

生产仓库：

```text
https://github.com/Mike-Zhuang/CEACStatusBot_Web
```

自动同步脚本：

```bash
/usr/local/bin/ceacstatusbot-sync-deploy.sh
```

计划任务通过宝塔计划任务和系统 crontab 每 10 分钟执行一次。脚本使用 git proxy 源拉取 `main`，只更新 `/opt/ceacstatusbot` 和 `/var/www/ceacstatusbot/frontend/dist`，不触碰 `/opt/ceacstatusbot-runtime`。

## 环境变量

生产 `backend.env` 至少包含：

```bash
DATABASE_PATH=/opt/ceacstatusbot-runtime/ceacstatusbot.sqlite3
SECRET_KEY=<随机强密钥>
CREDENTIAL_KEY_FILE=/opt/ceacstatusbot-runtime/secrets/credential-master.key
ENCRYPTION_KEY=<仅旧 Fernet 密文兼容需要>

SYSTEM_FROM_EMAIL=
SYSTEM_EMAIL_PASSWORD=
SYSTEM_SMTP_HOST=smtp.exmail.qq.com
SYSTEM_SMTP_PORT=465
SYSTEM_SMTP_USE_SSL=true

CORS_ORIGINS=https://ceac.mikezhuang.cn
CSRF_TRUSTED_ORIGINS=https://ceac.mikezhuang.cn
COOKIE_SECURE=true
WORKER_POLL_INTERVAL_SECONDS=1
DAILY_MANUAL_QUERY_LIMIT=20
SEED_DEFAULT_USERS=false
```

`SECRET_KEY`、`ENCRYPTION_KEY`、`SYSTEM_EMAIL_PASSWORD` 不要写入 README、提交记录或聊天记录。生产建议通过管理员后台保存系统 SMTP 授权码，使其进入加密存储。

## systemd 服务

后端服务：

```ini
[Unit]
Description=CEACStatusBot FastAPI Backend
After=network.target

[Service]
Type=simple
User=www
Group=www
WorkingDirectory=/opt/ceacstatusbot
EnvironmentFile=/opt/ceacstatusbot-runtime/backend.env
Environment=UV_PYTHON_INSTALL_DIR=/opt/ceacstatusbot-python
ExecStart=/opt/ceacstatusbot/.venv/bin/python -m uvicorn CEACStatusBot.web.main:app --host 127.0.0.1 --port 8011 --proxy-headers --forwarded-allow-ips=127.0.0.1,::1
Restart=always
RestartSec=3
StandardOutput=append:/www/wwwlogs/ceacstatusbot-backend.log
StandardError=append:/www/wwwlogs/ceacstatusbot-backend.error.log

[Install]
WantedBy=multi-user.target
```

Worker 服务：

```ini
[Unit]
Description=CEACStatusBot Query Worker
After=network.target ceacstatusbot-backend.service

[Service]
Type=simple
User=www
Group=www
WorkingDirectory=/opt/ceacstatusbot
EnvironmentFile=/opt/ceacstatusbot-runtime/backend.env
Environment=UV_PYTHON_INSTALL_DIR=/opt/ceacstatusbot-python
ExecStart=/opt/ceacstatusbot/.venv/bin/python -m CEACStatusBot.web.worker
Restart=always
RestartSec=3
StandardOutput=append:/www/wwwlogs/ceacstatusbot-worker.log
StandardError=append:/www/wwwlogs/ceacstatusbot-worker.error.log

[Install]
WantedBy=multi-user.target
```

常用命令：

```bash
systemctl daemon-reload
systemctl enable --now ceacstatusbot-backend.service
systemctl enable --now ceacstatusbot-worker.service
```

## Nginx 策略

生产域名：

```text
https://ceac.mikezhuang.cn
```

推荐结构：

- 域名站点直接服务 `/var/www/ceacstatusbot/frontend/dist`。
- `/api/` 反代到 `http://127.0.0.1:8011`。
- 8010 仅作为内部入口或逐步废弃入口，不作为公网入口。
- TLS 仅启用 `TLSv1.2 TLSv1.3`。
- 增加连接超时、请求限流和安全响应头。

站点级关键配置示例：

```nginx
client_max_body_size 2m;
client_header_timeout 10s;
client_body_timeout 10s;
send_timeout 15s;
keepalive_timeout 20s;

add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "same-origin" always;
add_header Content-Security-Policy "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'" always;

location ^~ /api/ {
    limit_req zone=ceac_api burst=30 nodelay;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 180s;
    proxy_connect_timeout 10s;
    proxy_send_timeout 60s;
    proxy_pass http://127.0.0.1:8011;
}
```

`limit_req_zone` 需要写在 Nginx `http` 块中，不能直接写进单个 `server` 块。

## 健康检查

```bash
curl https://ceac.mikezhuang.cn/api/health
systemctl status ceacstatusbot-backend.service --no-pager
systemctl status ceacstatusbot-worker.service --no-pager
nginx -t
```

## 部署验证

部署后确认：

- Git 提交为预期的 `main` 最新提交。
- `/opt/ceacstatusbot-runtime` 未被覆盖。
- SQLite、`backend.env`、主密钥文件权限正确。
- 后端、Worker、Nginx 均正常。
- 管理员后台可加载用户资料、查询日志和系统发信配置。
- 立即查询会进入队列并由 Worker 完成；非管理员账号达到 `DAILY_MANUAL_QUERY_LIMIT` 后会收到 429 提示。
- Approved/Issued 档案详情页可保存 UID/HAL 并创建 GTS 护照预约监控；Worker 日志中可看到 `passport_slot_manual` 或 `passport_slot_automatic` 任务。
