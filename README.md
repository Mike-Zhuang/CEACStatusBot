# CEACStatusBot Web

CEACStatusBot Web 是一个自托管的美国签证 CEAC 状态监控面板。它提供账号注册登录、多个签证档案管理、定时随机查询、状态历史记录、邮件通知和管理员后台，适合先在本地开发，再部署到自己的服务器向公网开放。

本项目是修改版本，遵循 GPLv3 许可证发布。项目保留并改造了 CEAC 状态查询与验证码识别相关思路，感谢原项目 [Andision/CEACStatusBot](https://github.com/Andision/CEACStatusBot)。

## 功能

- FastAPI 后端、SQLite 数据库、APScheduler 常驻调度。
- React + Vite + TypeScript 前端控制台。
- 暗色 / 亮色模式切换，主题偏好保存在浏览器本地。
- 开放注册，注册时发送邮箱验证码。
- 每个用户可创建多个 CEAC 查询档案。
- 每个档案每小时随机分钟查询一次，降低固定时间触发特征。
- 状态无变化不发邮件；状态或 CEAC 更新时间变化时记录历史并发送通知。
- 用户可为每个档案开启或关闭状态更新邮件推送。
- 用户可手动快速查询当前 CEAC 状态。
- 用户可手动发送一封测试邮件，邮件内容使用现有状态通知模板。
- 默认使用系统 SMTP 发信，也允许用户配置自己的 SMTP。
- 管理员账号可查看所有用户档案、状态历史与查询日志。

## 默认账号

首次启动后端时会自动创建两个账号：

| 角色 | 邮箱 | 密码 |
| --- | --- | --- |
| 管理员 | `admin@ceac.local` | `Admin@123456` |
| 普通用户 | `user@ceac.local` | `User@123456` |

公网部署后请尽快修改默认密码，并设置强 `SECRET_KEY` 和 `ENCRYPTION_KEY`。

## 本地开发

### 1. 安装后端依赖

```bash
pip install uv
uv sync
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，并填写发信邮箱配置：

```bash
cp .env.example .env
```

腾讯企业邮箱默认服务器：

- SMTP：`smtp.exmail.qq.com`
- SMTP SSL 端口：`465`
- IMAP：`imap.exmail.qq.com`
- IMAP SSL 端口：`993`

当前 Web 应用核心流程只需要 SMTP；IMAP 暂不参与状态查询或通知。

### 3. 启动后端

```bash
uv run uvicorn CEACStatusBot.web.main:app --reload --host 127.0.0.1 --port 8000
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 `http://127.0.0.1:5173`。

VS Code 调试配置位于 `.vscode/launch.json`，提供后端、前端和 Full Stack 三个配置，不会自动启动浏览器。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_PATH` | `ceacstatusbot.sqlite3` | SQLite 数据库路径 |
| `SECRET_KEY` | 开发默认值 | 会话签名密钥，公网必须修改 |
| `ENCRYPTION_KEY` | 由 `SECRET_KEY` 派生 | 用户 SMTP 授权码加密密钥，建议用 Fernet key |
| `SYSTEM_FROM_EMAIL` | 空 | 系统默认发信邮箱 |
| `SYSTEM_EMAIL_PASSWORD` | 空 | 系统默认发信邮箱授权码 |
| `SYSTEM_SMTP_HOST` | `smtp.exmail.qq.com` | 系统 SMTP 主机 |
| `SYSTEM_SMTP_PORT` | `465` | 系统 SMTP 端口 |
| `SYSTEM_SMTP_USE_SSL` | `true` | 是否使用 SMTP SSL |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | 允许访问后端的前端地址 |
| `COOKIE_SECURE` | `false` | HTTPS 部署时设为 `true` |

生成 `ENCRYPTION_KEY`：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 查询与通知逻辑

每个启用的签证档案都会保存 `nextCheckAt`。调度器每分钟扫描到期档案，并调用 CEAC 查询流程。查询完成后，系统会把下一次查询时间设为下一小时内的随机分钟。

系统会比较最近一次历史记录中的状态和 CEAC 更新时间：

- 完全一致：只记录查询日志，不发送通知。
- 状态或 CEAC 更新时间变化：写入该档案的状态历史，并发送邮件。

如果某个档案关闭了“状态更新邮件推送”，系统仍会定时查询并记录时间线，但不会在状态变化时自动发邮件。用户仍可手动点击“测试发信”，按最新已有状态模板发送一封邮件。

## 部署建议

- 使用 HTTPS，并设置 `COOKIE_SECURE=true`。
- 使用反向代理把前端静态文件和后端 API 暴露到同一域名。
- 定期备份 SQLite 数据库。
- 公网开放注册时关注查询量，必要时增加邀请码或管理员审核。
- 不要提交 `.env`、数据库文件、用户 SMTP 授权码或服务器私钥。

## License

本项目遵循 [GNU General Public License v3.0](LICENSE)。如果你分发修改版本，需要继续遵守 GPLv3 的源码开放、许可证保留和修改声明要求。

## 致谢

感谢 [Andision/CEACStatusBot](https://github.com/Andision/CEACStatusBot)。本项目基于其 CEAC 自动查询方向与部分实现进行 Web 化、服务化和多用户改造。
