# AstrBot MySQL 数据库管理插件

[![GitHub](https://img.shields.io/badge/作者-Chris-blue)](https://github.com/Chris95743)
[![License](https://img.shields.io/badge/license-AGPL--3.0-green)](LICENSE)
[![Version](https://img.shields.io/badge/version-v1.0.0-orange)](https://github.com/Chris95743/astrbot_plugin_mysql/releases)

> 让AI通过自然语言安全地操作MySQL数据库，支持增删改查、WebUI管理和完整审计

---

## ✨ 核心特性

- 🤖 **AI函数工具集成** - 6个LLM工具让AI理解自然语言并执行SQL操作
- �️ **多数据库连接支持** - 配置多个数据库连接，每个连接独立的权限设置
- �🔒 **多层安全防护** - SQL注入防护、危险操作拦截、参数化查询强制执行
- 🎯 **细粒度权限控制** - 表级白名单/黑名单、操作类型开关、行数限制
- 📊 **完整审计日志** - 记录所有操作、执行时间、影响行数、错误信息
- 🌐 **WebUI管理界面** - 可视化配置、查询历史、审计日志、数据库浏览器
- ⚡ **高性能连接池** - 异步连接池管理、自动重连、优雅关闭

---

## 📦 安装

### 方法1: 通过AstrBot插件市场（推荐）
1. 打开AstrBot Dashboard
2. 进入"插件市场"
3. 搜索"MySQL"或"astrbot_plugin_mysql"
4. 点击"安装"

### 方法2: 手动安装
```bash
cd data/plugins
git clone https://github.com/Chris95743/astrbot_plugin_mysql.git
# 或下载ZIP后解压到 data/plugins/astrbot_plugin_mysql/
```

### 依赖安装
插件会自动安装以下依赖：
- `aiomysql` - MySQL异步驱动
- `quart` - WebUI框架
- `hypercorn` - ASGI服务器
- `cryptography` - SSL支持（可选）

---

## 🚀 快速开始

### 1. 配置数据库连接

**方式1: 单个数据库（简单配置）**

在AstrBot Dashboard的插件配置页面，`connections` 字段填写：

```json
[{"name":"default","host":"localhost","port":3306,"username":"root","password":"your_password","database":"test","charset":"utf8mb4","enable_insert":true,"enable_update":true,"enable_delete":false,"enable_create_table":false,"table_whitelist":[],"table_blacklist":["mysql","information_schema","performance_schema","sys"],"max_query_rows":1000,"max_update_rows":100,"pool_size":3}]
```

**方式2: 多个数据库（高级配置）**

支持配置多个数据库全局参数

除了连接配置外，还有以下全局参数：

```json
{
  "default_connection": "default",     // 默认使用的连接名称
  "query_timeout": 30.0,               // 查询超时时间（秒）
  "webui_port": 6200,                  // WebUI端口号
  "webui_username": "admin",           // WebUI登录用户名
  "webui_password": "admin123",        // WebUI登录密码
  "enable_audit_log": true,            // 启用审计日志
  "pool_recycle": 3600,                // 连接回收时间（秒）
  "enable_ssl": false                  // 启用SSL连接
}
```

**每个连接的权限配置**：

- `enable_insert` - 允许INSERT操作
- `enable_update` - 允许UPDATE操作
- `enable_delete` - 允许DELETE操作（⚠️ 建议false）
- `enable_create_table` - 允许CREATE TABLE操作（⚠️ 建议false）
- `table_whitelist` - 表白名单（推荐使用）
- `table_blacklist` - 表黑名单（系统表默认已包含）
- `max_query_rows` - 单次查询最大行数
- `max_update_rows` - 单次更新/删除最大行数
- `pool_size` - 该连接的连接池大小 "port": 3306,
    "username": "readonly",
    "password": "ReadOnly",
    "database": "analytics_db",
    "enable_insert": false,
    "enable_update": false,
    "max_query_rows": 10000,
    "pool_size": 5
  }
]
```

### 2. 配置权限（重要！）

**基础权限**：
- ✅ 允许 INSERT - 开启后AI可插入数据
- ✅ 允许 UPDATE - 开启后AI可更新数据
- ⚠️ 允许 DELETE - 默认关闭，谨慎开启
- ⚠️ 允许 CREATE TABLE - 默认关闭

**表访问控制**（二选一）：
```yaml
# 方式1: 白名单模式（推荐）
表白名单: ["users", "orders", "products"]
# 只允许操作这些表

# 方式2: 黑名单模式
表黑名单: ["mysql", "sys", "information_schema"]
# 禁止操作这些表（系统表默认已加入）
```

**安全限制**：
```yaml
单次查询最大行数: 1000      # 防止大表全表查询
单次更新最大行数: 100       # 防止误操作影响过多数据
查询超时时间: 30秒          # 超时自动终止
```

### 3. 启用插件
1. 在AstrBot Dashboard中启用插件
2. AI对话中使用命令: `/mysql 开启后台`
3. 浏览器访问WebUI: `http://localhost:6200`（默认账号密码: admin/admin123）

---

## 💬 使用示例

### 场景1: 数据查询
```
👤 用户: 查询最近10条订单
🤖 AI: [调用 mysql_query]
返回结果:
| id | user_id | amount | created_at |
|----|---------|--------|------------|
| 101| 1001    | 299.00 | 2026-01-20 |
| 102| 1002    | 450.00 | 2026-01-19 |
...
共10行
```

### 场景2: 数据插入
```
👤 用户: 添加一个新用户，名字叫张三，邮箱zhangsan@test.com
🤖 AI: [调用 mysql_insert]
✅ 成功插入1行，新用户ID: 1523
```

### 场景3: 数据更新
```
👤 用户: 把订单123的状态改为已发货
🤖 AI: [调用 mysql_update]
✅ 成功更新1行数据
```

### 场景4: 查看表结构
```
👤 用户: 用户表有哪些字段？
🤖 AI: [调用 mysql_show_schema]
users表结构:
- id: INT(11), 主键, 自增
- username: VARCHAR(50), 非空, 唯一索引
- email: VARCHAR(100)
- created_at: DATETIME
```

---

## 🛠️ LLM工具列表

| 工具名 | 功能 | 安全措施 |
|-------|------|---------|
| `mysql_query` | 查询数据（SELECT） | 自动LIMIT限制、超时控制 |
| `mysql_insert` | 插入数据 | 参数化查询、字段验证 |
| `mysql_update` | 更新数据 | 强制WHERE条件、行数限制 |
| `mysql_delete` | 删除数据 | 默认禁用、二次确认 |
| `mysql_create_table` | 创建表 | 默认禁用、语法验证 |
| `mysql_show_schema` | 查看表结构 | 仅返回白名单表 |

---

## 🖥️ WebUI功能

访问 `http://localhost:6200`（可在配置中修改端口）

### 1. 连接状态监控
- 实时连接状态（✅ 已连接 / ❌ 断开）
- 连接池使用率（3/5 活跃）
- 今日查询统计
- 平均响应时间

### 2. 查询历史
- 查看所有AI执行的SQL语句
- 时间范围/用户/操作类型筛选
- SQL语句详情查看
- 导出为CSV/JSON

### 3. 权限配置
- 可视化表白名单/黑名单管理
- 操作权限开关（INSERT/UPDATE/DELETE/CREATE）
- 限制参数调整（行数、超时时间）
- 实时生效（无需重启）

### 4. 审计日志
- 时间线展示所有操作
- 成功/失败状态
- 执行耗时和影响行数
- 错误信息追踪

### 5. 数据库浏览器
- 表列表和行数统计
- 表结构查看（字段、类型、索引）
- 数据预览（前100行）
- DDL导出

---

## 🔐 安全机制

### 1. SQL注入防护
- ✅ 强制使用参数化查询（`cursor.execute(sql, params)`）
- ✅ 拒绝字符串拼接SQL
- ✅ 输入验证和转义

### 2. 危险操作拦截
自动拦截以下关键词：
- `DROP DATABASE` / `DROP TABLE`
- `TRUNCATE`
- `FLUSH` / `GRANT` / `REVOKE`
- SQL注释符 `--`
- 多语句注入 `;`

### 3. 权限分层控制
```
请求 → 操作类型检查 → 表黑名单检查 → 表白名单检查 
    → SQL危险词检查 → 行数限制 → 执行（带超时）
    → 审计日志记录 → 返回结果
```

### 4. 审计日志
所有操作自动记录到SQLite数据库：
- 时间戳、用户ID、平台来源
- 完整SQL语句和参数
- 影响行数、执行耗时
- 成功/失败状态、错误信息

### 5. WebUI密码安全
- MD5 16位小写哈希存储（取32位MD5的中间16位）
- Session Token验证
- Cookie过期管理

---

## ⚙️ 配置参考

### 最小配置（开发环境）
```json
{
  "db_host": "localhost",
  "db_port": 3306,
  "db_username": "root",
  "db_password": "123456",
  "db_database": "test",
  "enable_insert": true,
  "enable_update": true,
  "enable_delete": false
}
```0: 如何配置多个数据库连接？
**A**: 参见 [CONNECTIONS_CONFIG.md](CONNECTIONS_CONFIG.md) 详细文档。简单来说，`connections` 字段填写JSON数组，每个元素是一个连接配置。AI可以通过连接名称选择目标数据库。

### Q1: 插件启动失败，提示"连接数据库失败"
**A**: 检查以下几点：
1. MySQL服务是否正在运行
2. JSON配置格式是否正确（可用在线JSON验证工具检查）
3. 数据库地址、端口、用户名、密码是否正确
4. 数据库用户是否有相应权限
5 "db_host": "192.168.1.100",
  "db_port": 3306,
  "db_username": "app_user",
  "db_password": "ComplexP@ssw0rd",
  "db_database": "production_db",
  "db_charset": "utf8mb4",
  
  "enable_insert": true,
  "enable_update": true,
  "enable_delete": false,
  "enable_create_table": false,
  
  "table_whitelist": ["users", "orders", "products", "logs"],
  "table_blacklist": ["mysql", "sys", "information_schema", "performance_schema"],
  
  "max_query_rows": 500,
  "max_update_rows": 50,
  "query_timeout": 20.0,
  
  "webui_port": 6200,
  "webui_username": "admin",
  "webui_password": "YourStrongPassword",
  "enable_audit_log": true,
  
  "pool_size": 3,
  "pool_recycle": 1800,
  "enable_ssl": true
}
```

---

## 📋 常见问题

### Q1: 插件启动失败，提示"连接数据库失败"
**A**: 检查以下几点：
1. MySQL服务是否正在运行
2. 数据库地址、端口、用户名、密码是否正确
3. 数据库用户是否有相应权限
4. 防火墙是否阻止了连接

### Q2: AI无法执行DELETE操作
**A**: DELETE操作默认禁用，需在配置中将 `enable_delete` 改为 `true`

### Q3: 查询返回的数据不完整
**A**: 可能触发了行数限制，增大 `max_query_rows` 配置（默认1000行）

### Q4: WebUI无法访问
**A**: 
1. 确认已执行 `/mysql 开启后台` 命令
2. 检查端口是否被占用（默认6200）
3. 尝试访问 `http://127.0.0.1:6200`

### Q5: 如何修改WebUI密码
**A**: 
1. 在配置中修改 `webui_password`
2. 密码会自动使用MD5 16位小写哈希存储
3. 重启插件或重新开启后台生效

### Q6: 审计日志存储在哪里
**A**: `data/audit_logs.db`（SQLite数据库文件），可用任意SQLite客户端查看

### Q7: 支持PostgreSQL/SQLite吗
**A**: 当前版本仅支持MySQL/MariaDB，其他数据库计划在v2.0支持

---

## 🛣️ 开发路线图

### v1.0.0（当前版本）✅
- 基础6个LLM工具
- 连接池管理
- 权限控制系统
- WebUI管理界面
- 审计日志

### v1.1.0（计划中）
- [ ] 事务支持（BEGIN/COMMIT/ROLLBACK）
- [ ] 多数据库连接
- [ ] 慢查询分析和优化建议
- [ ] 查询结果缓存（Redis）
- [ ] 数据可视化图表（Echarts）

### v1.2.0（未来）
- [ ] 敏感字段自动脱敏
- [ ] SQL执行计划分析
- [ ] 索引优化建议
- [ ] 数据导出（Excel/CSV）

### v2.0.0（长期目标）
- [ ] PostgreSQL/SQLite支持
- [ ] RBAC权限系统
- [ ] 监控告警
- [ ] 备份/恢复工具

---

## ⚠️ 重要提示

1. **生产环境使用**：
   - 建议创建专门的只读或受限权限用户
   - 务必启用表白名单，限制可访问的表
   - DELETE和CREATE TABLE操作保持禁用
   - 定期检查审计日志

2. **性能建议**：
   - 为常用查询字段创建索引
   - 避免让AI执行大表全表扫描
   - 合理设置连接池大小（推荐3-5）

3. **安全建议**：
   - 修改默认WebUI密码
   - 仅在可信网络暴露WebUI端口
   - 启用SSL连接（生产环境）
   - 定期导出审计日志备份

---

## 🤝 贡献

欢迎提交Issue和Pull Request！

### 贡献指南
1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

---

## 📄 许可证

本项目采用 [AGPL-3.0](LICENSE) 许可证

---

## 📧 联系方式

- **作者**: Chris
- **GitHub**: [@Chris95743](https://github.com/Chris95743)
- **仓库**: [astrbot_plugin_mysql](https://github.com/Chris95743/astrbot_plugin_mysql)
- **问题反馈**: [GitHub Issues](https://github.com/Chris95743/astrbot_plugin_mysql/issues)

---

## 🙏 致谢

- [AstrBot](https://github.com/Soulter/AstrBot) - 强大的多平台聊天机器人框架
- [aiomysql](https://github.com/aio-libs/aiomysql) - 优秀的MySQL异步驱动
- [Quart](https://github.com/pallets/quart) - 异步Web框架

---

<div align="center">

**⭐ 如果这个插件对你有帮助，请给个Star支持一下！**

Made with ❤️ by Chris

</div>
