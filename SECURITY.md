# 安全说明

本文档记录 CEACStatusBot Web 的生产安全模型、边界和运维要求。不要在本文档或仓库中写入真实管理员账号、SMTP 授权码、数据库、主密钥或服务器私钥。

## 安全模型

- 本站登录密码使用 Argon2id 单向哈希。旧 PBKDF2-SHA256 哈希仅用于兼容迁移，用户登录成功后应自动升级为 Argon2id。
- CEAC 档案敏感字段、GTS UID/HAL、用户自定义 SMTP 授权码、系统 SMTP 授权码和原始查询快照使用 AES-256-GCM 可逆加密。
- 可逆加密主密钥保存在仓库外本地密钥文件中，通过 `CREDENTIAL_KEY_FILE` 指定。
- Web 进程不直接执行 CEAC 爬虫；Web 只创建 SQLite 队列任务，独立 Worker 消费任务。
- CEAC 请求目标固定为 `https://ceac.state.gov`，GTS 护照预约 slot 查询目标固定为 `https://scheduling-api.gtspremium.com`，用户输入不能影响请求 Host、协议或根 URL。
- 敏感 API 请求校验 `Origin` / `Referer`，生产只信任 `https://ceac.mikezhuang.cn`。
- 生产 Cookie 必须启用 `HttpOnly + SameSite=Lax + Secure`。
- 生产入口只走 HTTPS 域名；8010 不作为公网入口。

## 非目标与取舍

本项目不依赖付费云 KMS 或付费 WAF。当前方案使用本地密钥文件、Linux 文件权限、Nginx 限流和应用层校验降低风险。

这个方案的边界很清楚：

- 如果仓库泄露，攻击者拿不到数据库、`backend.env` 或主密钥。
- 如果 SQLite 备份泄露，但主密钥没有泄露，敏感字段仍不可直接读取。
- 如果普通应用配置泄露，但主密钥文件不在其中，敏感字段仍不可直接解密。
- 如果服务器 root 权限被完全攻破，本地密钥文件也可能被读取；这不是 KMS，无法提供云 KMS 级别的硬隔离。

## 主密钥文件

生产建议路径：

```bash
/opt/ceacstatusbot-runtime/secrets/credential-master.key
```

生成示例：

```bash
install -d -m 750 -o root -g www /opt/ceacstatusbot-runtime/secrets
python - <<'PY'
import base64
import os
print(base64.urlsafe_b64encode(os.urandom(32)).decode())
PY
```

写入密钥后设置权限：

```bash
chown root:www /opt/ceacstatusbot-runtime/secrets/credential-master.key
chmod 0440 /opt/ceacstatusbot-runtime/secrets/credential-master.key
```

`backend.env` 只保存路径：

```bash
CREDENTIAL_KEY_FILE=/opt/ceacstatusbot-runtime/secrets/credential-master.key
```

## 密钥轮换

轮换主密钥时必须先备份数据库和旧密钥，再执行迁移：

1. 停止 Worker，避免迁移期间写入新密文。
2. 备份 SQLite、旧主密钥和 `backend.env`。
3. 生成新主密钥文件。
4. 执行凭证重加密迁移脚本。
5. 重启 backend 和 worker。
6. 抽查管理员默认 SMTP、用户自定义 SMTP、CEAC 档案查询是否正常。
7. 确认新备份可恢复后，再归档旧密钥。

不要在没有完整备份的情况下删除旧密钥。

## 会话与 CSRF

生产环境必须配置：

```bash
COOKIE_SECURE=true
CSRF_TRUSTED_ORIGINS=https://ceac.mikezhuang.cn
CORS_ORIGINS=https://ceac.mikezhuang.cn
```

所有修改类接口，包括登录、注册、重置密码、保存档案、保存 SMTP、快速查询、测试发信和管理员保存配置，都应通过 Origin / Referer 校验。

GTS UID/HAL 监控配置和手动 slot 查询也属于敏感接口，必须继续走相同的会话、CSRF 和 HTTPS 约束。GTS 请求只允许发送规范化后的 UID/HAL 到固定 API 主机，不允许用户输入覆盖 URL、Header Host 或协议。

## Nginx 安全基线

生产 Nginx 应启用：

- 强制 HTTPS。
- `ssl_protocols TLSv1.2 TLSv1.3`。
- HSTS。
- `X-Content-Type-Options: nosniff`。
- `X-Frame-Options: DENY`。
- `Referrer-Policy: same-origin`。
- 基础 Content Security Policy。
- `client_header_timeout`、`client_body_timeout`、`send_timeout`。
- 登录、注册、验证码、API 的 `limit_req`。
- 单 IP 连接数 `limit_conn`。

8010 仅作为内部入口或逐步废弃入口，不作为公网访问入口。

## 安全事件处理

怀疑泄露时按以下顺序处理：

1. 立刻停止 backend 和 worker。
2. 备份当前 SQLite、日志和配置，便于审计。
3. 轮换 `SECRET_KEY`，使所有会话失效。
4. 轮换 `credential-master.key` 并重新加密敏感字段。
5. 重置系统 SMTP 和用户自定义 SMTP 授权码。
6. 检查管理员账号、用户列表、查询日志和系统登录日志。
7. 重启服务并验证健康检查、登录、快速查询和发信。

如果服务器 root 权限可能泄露，应视为主密钥也已泄露，必须同时轮换服务器登录密钥、数据库备份密钥和全部第三方授权码。
