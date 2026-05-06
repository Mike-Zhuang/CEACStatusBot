# 运维手册

本文档记录 CEACStatusBot Web 的日常运维、备份恢复和故障排查命令。命令中的真实密钥、密码和授权码必须由运维人员在服务器上管理，不要写入仓库。

## 日常状态检查

查看服务状态：

```bash
systemctl status ceacstatusbot-backend.service --no-pager
systemctl status ceacstatusbot-worker.service --no-pager
systemctl status nginx --no-pager
```

健康检查：

```bash
curl https://ceac.mikezhuang.cn/api/health
curl http://127.0.0.1:8011/api/health
```

查看监听端口：

```bash
ss -ltnp | grep -E ':80|:443|:8011'
```

8010 不应作为公网入口；如果保留，只用于内部入口或过渡调试。

## 日志

后端日志：

```bash
tail -f /www/wwwlogs/ceacstatusbot-backend.log
tail -f /www/wwwlogs/ceacstatusbot-backend.error.log
```

Worker 日志：

```bash
tail -f /www/wwwlogs/ceacstatusbot-worker.log
tail -f /www/wwwlogs/ceacstatusbot-worker.error.log
```

Nginx 日志：

```bash
tail -f /www/wwwlogs/ceac.mikezhuang.cn.log
tail -f /www/wwwlogs/ceac.mikezhuang.cn.error.log
```

宝塔计划任务日志：

```bash
tail -f /www/server/cron/3c0e83e8c3edd66d06abb0f2d514b212.log
```

## 手动部署

执行自动同步脚本：

```bash
/www/server/cron/3c0e83e8c3edd66d06abb0f2d514b212
```

或直接执行部署脚本：

```bash
/usr/local/bin/ceacstatusbot-sync-deploy.sh
```

部署后检查：

```bash
cd /opt/ceacstatusbot
git log -1 --oneline
curl https://ceac.mikezhuang.cn/api/health
systemctl status ceacstatusbot-backend.service --no-pager
systemctl status ceacstatusbot-worker.service --no-pager
```

## SQLite 队列检查

查看任务积压：

```bash
sqlite3 /opt/ceacstatusbot-runtime/ceacstatusbot.sqlite3 \
  "select status, count(*) from query_jobs group by status;"
```

查看最近任务：

```bash
sqlite3 /opt/ceacstatusbot-runtime/ceacstatusbot.sqlite3 \
  ".headers on" ".mode column" \
  "select id, case_id, trigger_type, status, attempts, created_at, finished_at, error_message from query_jobs order by id desc limit 20;"
```

如果 `queued` 或 `running` 长时间积压，先检查 Worker 服务和日志。

非管理员账号的 CEAC 立即查询和 GTS 立即查询 slot 共用每日手动查询额度，默认由 `DAILY_MANUAL_QUERY_LIMIT=20` 控制；管理员账号不受限制。查看当天手动查询量：

```bash
sqlite3 /opt/ceacstatusbot-runtime/ceacstatusbot.sqlite3 \
  ".headers on" ".mode column" \
  "select u.email, count(*) as manual_queries from query_jobs j join ceac_cases c on c.id = j.case_id join users u on u.id = c.user_id where j.trigger_type in ('manual', 'passport_slot_manual') and j.created_at >= datetime('now', 'start of day') group by u.id order by manual_queries desc;"
```

GTS 护照预约监控任务会使用 `passport_slot_manual` 或 `passport_slot_automatic` 触发类型：

```bash
sqlite3 /opt/ceacstatusbot-runtime/ceacstatusbot.sqlite3 \
  ".headers on" ".mode column" \
  "select c.display_name, m.is_enabled, m.last_slot_count, m.next_check_at, m.last_error_message from passport_slot_monitors m join ceac_cases c on c.id = m.case_id order by m.updated_at desc limit 20;"
```

## 备份

建议至少备份三类文件：

- SQLite 数据库：`/opt/ceacstatusbot-runtime/ceacstatusbot.sqlite3`
- 后端环境变量：`/opt/ceacstatusbot-runtime/backend.env`
- 主密钥文件：`/opt/ceacstatusbot-runtime/secrets/credential-master.key`

示例：

```bash
BACKUP_DIR=/opt/ceacstatusbot-runtime/backups/$(date +%Y%m%d%H%M%S)
install -d -m 750 -o root -g www "$BACKUP_DIR"
cp -a /opt/ceacstatusbot-runtime/ceacstatusbot.sqlite3 "$BACKUP_DIR/"
cp -a /opt/ceacstatusbot-runtime/backend.env "$BACKUP_DIR/"
cp -a /opt/ceacstatusbot-runtime/secrets/credential-master.key "$BACKUP_DIR/"
chmod -R go-rwx "$BACKUP_DIR"
```

不要只备份数据库而不备份主密钥。没有主密钥时，加密字段无法恢复。

## 恢复

恢复顺序：

1. 停止服务：

```bash
systemctl stop ceacstatusbot-worker.service
systemctl stop ceacstatusbot-backend.service
```

2. 恢复数据库、`backend.env` 和主密钥文件。
3. 恢复权限：

```bash
chown -R www:www /opt/ceacstatusbot-runtime
chmod 750 /opt/ceacstatusbot-runtime
chmod 640 /opt/ceacstatusbot-runtime/backend.env
chmod 640 /opt/ceacstatusbot-runtime/ceacstatusbot.sqlite3
chown root:www /opt/ceacstatusbot-runtime/secrets/credential-master.key
chmod 0440 /opt/ceacstatusbot-runtime/secrets/credential-master.key
```

4. 启动服务：

```bash
systemctl start ceacstatusbot-backend.service
systemctl start ceacstatusbot-worker.service
```

5. 执行健康检查和一次测试查询。

## 故障排查

### 验证码邮件发不出去

检查：

```bash
tail -n 100 /www/wwwlogs/ceacstatusbot-backend.error.log
tail -n 100 /www/wwwlogs/ceacstatusbot-backend.log
```

确认管理员后台的默认发信邮箱、SMTP 主机、端口、SSL 和授权码正确。腾讯企业邮箱通常使用：

- `smtp.exmail.qq.com`
- SSL 端口 `465`

### Worker 不消费任务

检查：

```bash
systemctl status ceacstatusbot-worker.service --no-pager
tail -n 100 /www/wwwlogs/ceacstatusbot-worker.error.log
sqlite3 /opt/ceacstatusbot-runtime/ceacstatusbot.sqlite3 \
  "select status, count(*) from query_jobs group by status;"
```

常见原因：

- Worker 服务未启动。
- SQLite 文件权限错误。
- 主密钥文件缺失或权限错误。
- CEAC 查询长时间超时。

### 密钥文件缺失导致无法解密

检查：

```bash
grep CREDENTIAL_KEY_FILE /opt/ceacstatusbot-runtime/backend.env
stat /opt/ceacstatusbot-runtime/secrets/credential-master.key
```

如果密钥文件丢失，只能从备份恢复。不要生成新密钥直接覆盖旧密钥，否则旧密文无法解密。

### Nginx 限流误伤

查看 Nginx 错误日志：

```bash
tail -n 100 /www/wwwlogs/ceac.mikezhuang.cn.error.log
```

如果确认是正常用户被误伤，可以适当提高 `burst` 或降低登录页自动重试频率。不要直接移除登录、注册和验证码接口的限流。

### CEAC 查询失败或超时

检查 Worker 日志和查询日志：

```bash
tail -n 100 /www/wwwlogs/ceacstatusbot-worker.log
sqlite3 /opt/ceacstatusbot-runtime/ceacstatusbot.sqlite3 \
  ".headers on" ".mode column" \
  "select id, success, error_message, duration_ms, finished_at from query_runs order by id desc limit 20;"
```

常见原因：

- CEAC 官网网络波动。
- 验证码识别失败。
- 用户填写的地点、申请号、护照号或姓氏前 5 位不正确。
- 代理或出口 IP 被第三方站点限制。

### GTS 护照预约监控无结果

检查对应任务和监控状态：

```bash
sqlite3 /opt/ceacstatusbot-runtime/ceacstatusbot.sqlite3 \
  ".headers on" ".mode column" \
  "select id, case_id, trigger_type, success, error_message, duration_ms, finished_at from query_runs where trigger_type like 'passport_slot_%' order by id desc limit 20;"
sqlite3 /opt/ceacstatusbot-runtime/ceacstatusbot.sqlite3 \
  ".headers on" ".mode column" \
  "select case_id, is_enabled, last_slot_count, last_checked_at, next_check_at, last_error_message from passport_slot_monitors order by updated_at desc limit 20;"
```

常见原因：

- UID/HAL 尚未被 GTS 后端识别，接口返回 `token:null` 或 `invalid_uid`。
- 当前没有可预约 slot，系统只记录查询日志，不发送邮件。
- GTS 接口限流，系统会自动把下一次查询退避到 30-60 分钟后。
- Worker 无法访问 `https://scheduling-api.gtspremium.com`。

### 自动部署没有更新

检查：

```bash
tail -n 80 /www/server/cron/3c0e83e8c3edd66d06abb0f2d514b212.log
cd /opt/ceacstatusbot && git remote -v && git log -1 --oneline
```

仓库应指向：

```text
https://github.com/Mike-Zhuang/CEACStatusBot_Web
```
