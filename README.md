# AstrBot MySQL 数据库管理插件

[![GitHub](https://img.shields.io/badge/作者-Chris-blue)](https://github.com/Chris95743)
[![License](https://img.shields.io/badge/license-AGPL--3.0-green)](LICENSE)
[![Version](https://img.shields.io/badge/version-v1.0.0-orange)](https://github.com/Chris95743/astrbot_plugin_mysql/releases)

> 让AI通过自然语言安全地操作MySQL数据库，支持增删改查、WebUI管理和完整审计

---

## ✨ 核心特性

-  **AI函数工具集成** - 6个LLM工具让AI理解自然语言并执行SQL操作
-  **多数据库连接支持** - 配置多个数据库连接，每个连接独立的权限设置
-  **多层安全防护** - SQL注入防护、危险操作拦截、参数化查询强制执行
-  **细粒度权限控制** - 表级白名单/黑名单、操作类型开关、行数限制
-  **完整审计日志** - 记录所有操作、执行时间、影响行数、错误信息
-  **WebUI管理界面** - 可视化配置、查询历史、审计日志、数据库浏览器
-  **高性能连接池** - 异步连接池管理、自动重连、优雅关闭

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

### 1. 安装并启用插件

1. 在AstrBot插件市场搜索"MySQL"并安装
2. 或手动将插件解压到 `data/plugins/astrbot_plugin_mysql/`
3. 在AstrBot Dashboard中启用插件
4. 插件会自动启动WebUI（默认端口6200）

### 2. 插件配置说明

在AstrBot Dashboard的插件配置页面，只需配置以下参数：

```json
{
  "webui_enable": true,              // 是否启用WebUI管理界面
  "webui_port": 6200,                // WebUI访问端口
  "webui_username": "admin",         // WebUI登录用户名
  "webui_password": "admin123",      // WebUI登录密码
  "default_connection": "default",   // AI未指定连接时使用的默认连接名
  "query_timeout": 30.0,             // 查询超时时间（秒）
  "enable_audit_log": true,          // 是否启用审计日志
  "pool_recycle": 3600,              // 连接池回收时间（秒）
  "enable_ssl": false                // 是否启用SSL连接
}
```

> ⚠️ **重要**: 数据库连接不再通过插件配置，请通过WebUI界面管理！

### 3. 通过WebUI管理数据库连接

访问 `http://localhost:6200`，使用配置的用户名密码登录。

**新建连接步骤**：
1. 点击"新建连接"按钮
2. 填写连接信息：
   - **连接名称**: 自定义名称（如：main_db、analytics_db）
   - **主机地址**: 数据库服务器地址（如：localhost、192.168.1.100）
   - **端口**: MySQL端口（默认3306）
   - **数据库名**: 要连接的数据库
   - **用户名/密码**: 数据库认证信息
   - **字符集**: 推荐utf8mb4
   - **连接池大小**: 建议3-5

3. 配置权限（重要）：
   - ✅ **允许INSERT**: 开启后AI可插入数据
   - ✅ **允许UPDATE**: 开启后AI可更新数据
   - ⚠️ **允许DELETE**: 默认关闭，谨慎开启
   - ⚠️ **允许CREATE TABLE**: 默认关闭，谨慎开启

4. 设置限制：
   - **最大查询行数**: 防止大表全表查询（推荐1000）
   - **最大更新行数**: 防止误操作（推荐100）

5. 配置表黑名单（可选）：
   - 编辑连接时会自动加载该数据库的所有表
   - 勾选敏感表（如密码表、系统表）加入黑名单
   - 黑名单中的表AI无法查询

6. 点击"保存配置"

**配置特性**：
- ✅ 配置实时生效，无需重启插件
- ✅ 配置持久化保存在 `data/connections_override.json`
- ✅ 支持启用/禁用连接（禁用的连接不占用资源）
- ✅ 支持删除连接

### 4. 开始使用

配置完成后，直接在AI对话中提问即可：

```
👤 用户: 查询users表的所有数据
🤖 AI: [自动调用mysql_query工具查询数据并返回结果]
```

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

## 🖥️ WebUI功能详解

访问 `http://localhost:6200`（端口可在插件配置中修改）

### 1. 首页概览
- 📊 数据库连接数统计
- 🔗 默认连接名称显示
- 📝 审计日志启用状态
- 🗂️ 连接列表卡片展示
  - 显示连接状态（✅ 已启用 / ⏸️ 已禁用）
  - 显示主机、端口、数据库名、用户名
  - 显示权限配置（INSERT/UPDATE/DELETE/CREATE）
  - 点击卡片进入编辑模式

### 2. 连接管理
**新建连接**：
- 点击"新建连接"按钮
- 填写连接基本信息（名称、主机、端口、数据库、用户名、密码）
- 配置字符集和连接池大小
- 设置权限开关
- 设置查询和更新行数限制
- 保存后立即生效

**编辑连接**：
- 点击连接卡片进入编辑
- 连接名称不可修改（如需更改请新建）
- 修改配置后点击"保存配置"
- 支持以下操作：
  - 💾 **保存配置**: 更新连接参数
  - 🚫 **禁用连接**: 暂时禁用（不删除配置）
  - ✅ **启用连接**: 重新启用已禁用的连接
  - 🗑️ **删除连接**: 永久删除连接配置

**表黑名单设置**：
- 编辑连接时自动加载数据库所有表
- 通过复选框选择需要保护的敏感表
- 支持全选/取消全选
- 黑名单中的表AI无法查询
- 适用场景：密码表、敏感配置表、系统表

### 3. 浏览表
- 选择数据库连接后显示所有表
- 优雅的卡片式布局
- 每个表提供两个操作：
  - 📋 **查看结构**: 显示字段名、类型、键信息、额外属性
  - 👁️ **查看数据**: 预览表中数据（限制50行）

### 4. 查询测试
- SQL在线编辑器
- 选择目标数据库连接
- 执行任意SQL语句（受权限限制）
- 结果以表格形式展示
- 显示查询耗时和影响行数

### 5. 审计日志
- 时间线展示所有数据库操作
- 显示时间戳、用户、平台来源
- SQL语句高亮显示
- 成功/失败状态标识
- 执行耗时统计
- 错误信息详情
- 🗑️ **一键清空日志**: 清理所有历史记录并释放空间

---

## 🔐 安全机制

### 1. SQL注入防护
- ✅ 强制使用参数化查询（`cursor.execute(sql, params)`）
- ✅ 拒绝字符串拼接SQL
- ✅ 输入验证和转义

### 2. 危文件说明

### 插件配置（在AstrBot Dashboard中配置）

```json
{
  "webui_enable": true,              // 启用/禁用WebUI（关闭后完全禁用管理界面）
  "webui_port": 6200,                // WebUI访问端口
  "webui_username": "admin",         // 登录用户名
  "webui_password": "admin123",      // 登录密码（MD5 16位小写存储）
  "default_connection": "default",   // 默认连接名称
  "query_timeout": 30.0,             // 查询超时（秒）
  "enable_audit_log": true,          // 启用审计日志
  "pool_recycle": 3600,              // 连接池回收时间（秒）
  "enable_ssl": false                // 启用SSL连接
}
```

### 连接配置（通过WebUI管理）

连接配置保存在 `data/plugins/astrbot_plugin_mysql/data/connections_override.json`

每个连接的结构：
```json
{
  "name": "main_db",                 // 连接名称（唯一标识）
  "host": "localhost",               // 数据库主机
  "port": 3306,                      // 数据库端口
  "database": "myapp",               // 数据库名
  "username": "root",                // 用户名
  "password": "password",            // 密码
  "charset": "utf8mb4",              // 字符集
  "pool_size": 3,                    // 连接池大小
  "enabled": true,                   // 是否启用此连接
  
  "enable_insert": true,             // 允许INSERT操作
  "enable_update": true,             // 允许UPDATE操作  
  "enable_delete": false,            // 允许DELETE操作（危险）
  "enable_create_table": false,      // 允许CREATE TABLE操作（危险）
  
  "max_query_rows": 1000,            // 单次查询最大行数
  "max_update_rows": 100,            // 单次更新/删除最大行数
  
  "table_blacklist": [               // 表黑名单（AI无法访问）
    "sys_user_password",
    "sys_config",
    "mysql",
    "information_schema"
  ]
}
```

### 生产环境推荐配置

**只读分析库**：
```json
{
  "name": "analytics_readonly",
  "enable_insert": false,
  "enable_update": false,
  "enable_delete": false,
  "enable_create_table": false,
  "max_query_rows": 5000,
  "table_blacklist": ["mysql", "sys", "information_schema", "performance_schema"]
}
```

**应用主库**：
```json
{
  "name": "app_main",
  "enable_insert": true,
  "enable_update": true,
  "enable_delete": false,
  "enable_create_table": false,
  "max_query_rows": 1000,
  "max_update_rows": 50,
  "table_blacklist": ["sys_user_password", "sys_token", "sys_secret"]
}
```

3. 数据库地址、端口、用户名、密码是否正确
4. 数据库用户是否有相应权限
5 "db_host": "192.168.1.100",
  "db_port": 3306,
  "db_username": "app_user",
  "db_password": "ComplexP@ssw0rd",
  "db_database": "production_db",
  "db_charset": "utf8mb4",
  如何配置第一个数据库连接？
**A**: 
1. 启用插件后访问 http://localhost:6200
2. 使用默认账号密码登录（admin/admin123）
3. 点击"新建连接"按钮
4. 填写数据库信息并保存
5. 在插件配置中将 `default_connection` 设置为该连接名称

### Q2: 修改连接配置后需要重启吗？
**A**: 不需要！插件支持配置热更新，修改后下次查询时会自动重载新配置。

### Q3: AI无法执行DELETE操作
**A**: DELETE操作默认禁用。在WebUI中编辑连接，勾选"允许DELETE"权限即可。

### Q4: 如何保护敏感表不被AI查询？
**A**: 
1. 在WebUI中编辑连接
2. 滚动到"表黑名单"区域
3. 勾选需要保护的表（如密码表、配置表）
4. 保存配置

### Q5: 查询返回的数据不完整
**A**: 可能触发了行数限制。在WebUI中编辑连接，增大"最大查询行数"参数。

### Q6: WebUI无法访问
**A**: 
1. 检查插件是否已启用
2. 检查 `webui_enable` 配置是否为 `true`
3. 检查端口是否被占用（默认6200）
4. 尝试访问 `http://127.0.0.1:6200`

### Q7: 如何修改WebUI密码？
**A**: 在插件配置中修改 `webui_password`，然后重启插件。

### Q8: 如何禁用某个连接但不删除配置？
**A**: 在WebUI中编辑连接，点击"禁用连接"按钮。禁用的连接不会创建连接池，不占用资源。
✅ 6个LLM工具（查询、插入、更新、删除、建表、查看结构）
- ✅ 多数据库连接管理
- ✅ 异步连接池管理
- ✅ 细粒度权限控制
- ✅ 表黑名单机制
- ✅ 现代化WebUI管理界面
- ✅ 审计日志（支持一键清理）
- ✅ 配置热更新（无需重启）
- ✅ 连接状态管理（启用/禁用）
- ✅ 表浏览器（查看结构/数据）
- ✅ 在线查询测试

### v1.1.0（计划中）
- [ ] 事务支持（BEGIN/COMMIT/ROLLBACK）
- [ ] 慢查询分析和优化建议
- [ ] 查询结果缓存（Redis）
- [ ] 数据可视化图表
- [ ] SQL语句历史记录
- [ ] 批量导入/导出（CSV/Excel）

### v1.2.0（未来）
- [ ] 敏感字段自动脱敏
- [ ] SQL执行计划分析
- [ ] 索引优化建议
- [ ] 数据库备份/恢复
- [ ] 定时任务调度
- [ ] Webhook通知

### v2.0.0（长期目标）
- [ ] PostgreSQL/SQLite/MongoDB支持
- [ ] RBAC权限系统
- [ ] 监控告警系统
- [ ] 分布式部署支持
- [ ] API接口开放默认6200）
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
### 生产环境使用建议

1. **数据库用户权限**：
   - 创建专门的数据库用户，不要使用root
   - 只读场景使用SELECT权限
   - 应用场景按需授予INSERT/UPDATE权限
   - 绝不授予DROP/TRUNCATE/ALTER权限

2. **连接配置安全**：
   - 修改默认WebUI密码（强密码）
   - 设置表黑名单保护敏感表（密码表、配置表等）
   - DELETE和CREATE TABLE操作保持禁用
   - 合理设置查询和更新行数限制

3. **性能优化**：
   - 为常用查询字段创建索引
   - 避免让AI执行大表全表扫描
   - 连接池大小设置为3-5（按实际并发调整）
   - 查询超时时间设置为30秒以内

4. **安全防护**：
   - WebUI仅在内网访问，不要暴露到公网
   - 启用审计日志，定期检查异常操作
   - 使用表黑名单保护系统表和敏感表
   - 定期备份 `connections_override.json` 和 `audit_logs.db`

5. **监控和维护**：
   - 定期查看审计日志，发现异常操作
   - 使用"一键清理"功能定期清理旧日志释放空间
   - 禁用不使用的连接节省资源
   - 测试环境和生产环境使用不同的连接配置）
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

<div align="center">

**⭐ 如果这个插件对你有帮助，请给个Star支持一下！**

Made with ❤️ by Chris

</div>


