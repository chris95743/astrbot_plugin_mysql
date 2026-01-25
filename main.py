"""
AstrBot MySQL数据库管理插件
支持多数据库连接、AI函数工具、WebUI管理
"""
import asyncio
from multiprocessing import Process
from pathlib import Path

from astrbot.api import llm_tool, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.message.message_event_result import MessageChain

from .backend.connection_pool import ConnectionPoolManager
from .backend.permission_manager import PermissionManager
from .backend.query_executor import QueryExecutor
from .config import DEFAULT_CONFIG
from .security.audit_logger import AuditLogger
from .config_manager import ConfigManager, merge_connections


def _webui_process_target(config: dict, data_dir: str):
    """WebUI进程目标函数（必须是模块级函数以支持pickle）"""
    from .backend.connection_pool import ConnectionPoolManager
    from .backend.permission_manager import PermissionManager
    from .backend.query_executor import QueryExecutor
    from .security.audit_logger import AuditLogger
    from .webui import start_server
    from .config_manager import ConfigManager, merge_connections
    import asyncio
    import json
    from pathlib import Path

    async def init_and_run():
        # 确保data_dir目录存在
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        
        # 加载配置覆盖（与主进程保持一致）
        try:
            config_manager = ConfigManager(data_dir)
            if config_manager.has_overrides():
                override_connections = config_manager.load_connections()
                if override_connections:
                    # 如果存在override配置，完全使用override，不合并base配置
                    config["connections"] = override_connections
                    print(f"✅ WebUI进程已加载配置覆盖：{len(override_connections)} 个连接（完全覆盖模式）")
                else:
                    print("⚠️  配置覆盖文件为空，使用默认配置")
        except Exception as e:
            print(f"⚠️  加载配置覆盖失败: {e}")
        
        # 在WebUI进程中重新创建组件
        config_file_path = str(Path(data_dir) / "connections_override.json")
        pool_manager = ConnectionPoolManager(config, config_file_path)
        # 初始化连接池
        connection_success = False
        try:
            await pool_manager.initialize_all()
            # 检查是否有成功的连接
            if hasattr(pool_manager, 'pools') and pool_manager.pools:
                print(f"✅ WebUI进程连接池初始化成功，已连接: {list(pool_manager.pools.keys())}")
                connection_success = True
            else:
                print(f"⚠️  连接池为空，没有可用的数据库连接")
                pool_manager = None
        except Exception as e:
            print(f"❌ 数据库连接初始化失败: {e}")
            print(f"   WebUI将以只读模式启动")
            pool_manager = None

        permission_manager = PermissionManager(config)

        # 修复：构建正确的审计日志数据库路径
        audit_db_path = str(Path(data_dir) / "audit_logs.db")
        audit_logger = AuditLogger(audit_db_path) if config.get("enable_audit_log", False) else None
        if audit_logger:
            try:
                await audit_logger.initialize()
            except Exception as e:
                print(f"警告: 审计日志初始化失败: {e}")
                audit_logger = None

        query_executor = QueryExecutor(pool_manager, permission_manager, audit_logger) if pool_manager else None

        # 启动服务器，传递所有组件
        await start_server(config, data_dir, pool_manager, permission_manager, query_executor, audit_logger)

    asyncio.run(init_and_run())


class Main(Star):
    """MySQL数据库管理插件主类"""

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.context = context
        self.config = {**DEFAULT_CONFIG, **(config or {})}

        # 核心组件
        self.pool_manager: ConnectionPoolManager | None = None
        self.permission_manager: PermissionManager | None = None
        self.query_executor: QueryExecutor | None = None
        self.audit_logger: AuditLogger | None = None

        # WebUI进程
        self.webui_process = None

        # 插件数据目录
        self.data_dir = Path(__file__).parent / "data"
        self.data_dir.mkdir(exist_ok=True)

    async def initialize(self):
        """插件初始化"""
        try:
            logger.info("🔌 MySQL插件初始化中...")

            # 加载配置覆盖文件
            config_manager = ConfigManager(str(self.data_dir))
            if config_manager.has_overrides():
                override_connections = config_manager.load_connections()
                if override_connections:
                    # 如果存在override配置，完全使用override，不合并base配置
                    # 这样用户在WebUI中删除的连接不会在重启后恢复
                    self.config["connections"] = override_connections
                    logger.info(f"✅ 已加载配置覆盖：{len(override_connections)} 个连接（完全覆盖模式）")
                else:
                    logger.info("⚠️  配置覆盖文件为空，使用默认配置")
            else:
                logger.info("使用metadata.yaml中的默认配置")

            # 初始化审计日志
            audit_db_path = str(self.data_dir / "audit_logs.db")
            self.audit_logger = AuditLogger(audit_db_path)

            # 初始化连接池管理器（传递配置文件路径以支持动态重载）
            config_file_path = str(self.data_dir / "connections_override.json")
            self.pool_manager = ConnectionPoolManager(self.config, config_file_path)
            await self.pool_manager.initialize_all()

            # 初始化权限管理器
            self.permission_manager = PermissionManager(self.pool_manager)

            # 初始化查询执行器
            self.query_executor = QueryExecutor(
                self.pool_manager,
                self.permission_manager,
                self.audit_logger
            )

            # 激活LLM工具
            tool_names = [
                "mysql_query",
                "mysql_insert",
                "mysql_update",
                "mysql_delete",
                "mysql_create_table",
                "mysql_show_schema"
            ]
            for tool_name in tool_names:
                self.context.activate_llm_tool(tool_name)

            logger.info(f"✅ MySQL插件初始化成功，已激活 {len(tool_names)} 个LLM工具")
            logger.info(f"📊 已加载 {len(self.pool_manager.get_all_connection_names())} 个数据库连接")

            # 自动启动WebUI
            await self._auto_start_webui()

        except Exception as e:
            logger.error(f"❌ MySQL插件初始化失败: {e}", exc_info=True)
            raise

    async def _auto_start_webui(self):
        """自动启动WebUI（内部方法）"""
        # 检查是否启用WebUI
        if not self.config.get("webui_enable", True):
            logger.info("ℹ️  WebUI已禁用（配置项 webui_enable=false）")
            return
        
        try:
            port = self.config.get("webui_port", 6200)

            # 在独立进程中启动WebUI（使用模块级函数）
            self.webui_process = Process(
                target=_webui_process_target,
                args=(self.config, str(self.data_dir))
            )
            self.webui_process.daemon = True  # 设置为守护进程
            self.webui_process.start()

            logger.info(f"🌐 WebUI已自动启动在端口 {port}")
            logger.info(f"📍 访问地址: http://localhost:{port}")
            logger.info(f"👤 登录账号: {self.config.get('webui_username', 'admin')}")

        except Exception as e:
            logger.warning(f"WebUI自动启动失败（不影响插件功能）: {e}")

    async def terminate(self):
        """插件终止"""
        logger.info("🔌 MySQL插件正在关闭...")

        # 关闭WebUI
        if self.webui_process:
            try:
                if self.webui_process.is_alive():
                    self.webui_process.terminate()
                    self.webui_process.join(timeout=3)
                    logger.info("WebUI服务已停止")
            except Exception as e:
                logger.warning(f"关闭WebUI时出错: {e}")

        # 关闭所有连接池
        if self.pool_manager:
            await self.pool_manager.close_all()

        logger.info("✅ MySQL插件已关闭")

    # ==================== LLM工具 ====================

    @llm_tool("mysql_query")
    async def mysql_query(
        self,
        event: AstrMessageEvent,
        sql: str,
        connection: str = None
    ) -> str:
        """执行SELECT查询并返回结果
        
        Args:
            sql(string): SELECT查询语句（会自动添加LIMIT限制）
            connection(string): 数据库连接名称（可选，不填则使用默认连接）
            
        Returns:
            str: Markdown格式的表格结果
        """
        user_id = event.get_sender_id()
        platform = event.get_platform_name()

        success, result = await self.query_executor.execute_query(
            sql=sql,
            connection_name=connection,
            user_id=user_id,
            platform=platform
        )

        return result

    @llm_tool("mysql_insert")
    async def mysql_insert(
        self,
        event: AstrMessageEvent,
        table: str,
        data: dict,
        connection: str = None
    ) -> str:
        """向表中插入数据
        
        Args:
            table(string): 表名
            data(object): 要插入的数据，键为字段名，值为字段值
            connection(string): 数据库连接名称（可选）
            
        Returns:
            str: 插入结果描述
        """
        # 构造INSERT语句
        columns = ", ".join([f"`{k}`" for k in data.keys()])
        placeholders = ", ".join(["%s"] * len(data))
        sql = f"INSERT INTO `{table}` ({columns}) VALUES ({placeholders})"
        params = tuple(data.values())

        user_id = event.get_sender_id()
        platform = event.get_platform_name()

        success, result = await self.query_executor.execute_query(
            sql=sql,
            params=params,
            connection_name=connection,
            user_id=user_id,
            platform=platform
        )

        return result

    @llm_tool("mysql_update")
    async def mysql_update(
        self,
        event: AstrMessageEvent,
        table: str,
        data: dict,
        where: str,
        connection: str = None
    ) -> str:
        """更新表中的数据
        
        Args:
            table(string): 表名
            data(object): 要更新的字段和新值
            where(string): WHERE条件（如 "id=100" 或 "status='active'"）
            connection(string): 数据库连接名称（可选）
            
        Returns:
            str: 更新结果描述
        """
        # 构造UPDATE语句
        set_clause = ", ".join([f"`{k}` = %s" for k in data.keys()])
        sql = f"UPDATE `{table}` SET {set_clause} WHERE {where}"
        params = tuple(data.values())

        user_id = event.get_sender_id()
        platform = event.get_platform_name()

        success, result = await self.query_executor.execute_query(
            sql=sql,
            params=params,
            connection_name=connection,
            user_id=user_id,
            platform=platform
        )

        return result

    @llm_tool("mysql_delete")
    async def mysql_delete(
        self,
        event: AstrMessageEvent,
        table: str,
        where: str,
        connection: str = None
    ) -> str:
        """删除表中的数据
        
        Args:
            table(string): 表名
            where(string): WHERE条件（必需，防止全表删除）
            connection(string): 数据库连接名称（可选）
            
        Returns:
            str: 删除结果描述
        """
        sql = f"DELETE FROM `{table}` WHERE {where}"

        user_id = event.get_sender_id()
        platform = event.get_platform_name()

        success, result = await self.query_executor.execute_query(
            sql=sql,
            connection_name=connection,
            user_id=user_id,
            platform=platform
        )

        return result

    @llm_tool("mysql_create_table")
    async def mysql_create_table(
        self,
        event: AstrMessageEvent,
        table: str,
        schema: str,
        connection: str = None
    ) -> str:
        """创建新的数据表
        
        Args:
            table(string): 表名
            schema(string): 表结构定义（如 "id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(100)"）
            connection(string): 数据库连接名称（可选）
            
        Returns:
            str: 创建结果描述
        """
        sql = f"CREATE TABLE `{table}` ({schema})"

        user_id = event.get_sender_id()
        platform = event.get_platform_name()

        success, result = await self.query_executor.execute_query(
            sql=sql,
            connection_name=connection,
            user_id=user_id,
            platform=platform
        )

        return result

    @llm_tool("mysql_show_schema")
    async def mysql_show_schema(
        self,
        event: AstrMessageEvent,
        table: str = None,
        connection: str = None
    ) -> str:
        """查看数据库表结构
        
        Args:
            table(string): 表名（可选，不填则列出所有表）
            connection(string): 数据库连接名称（可选）
            
        Returns:
            str: 表结构信息
        """
        user_id = event.get_sender_id()
        platform = event.get_platform_name()

        if table:
            # 查看指定表的结构
            sql = f"DESCRIBE `{table}`"
        else:
            # 列出所有表
            sql = "SHOW TABLES"

        success, result = await self.query_executor.execute_query(
            sql=sql,
            connection_name=connection,
            user_id=user_id,
            platform=platform
        )

        return result

    # ==================== 命令 ====================
    
    @filter.command_group("mysql")
    @filter.permission_type(filter.PermissionType.ADMIN)
    def mysql_group(self):
        """MySQL管理命令组"""
        pass

    @mysql_group.command("连接列表")
    async def list_connections(self, event: AstrMessageEvent):
        """查看所有配置的数据库连接"""
        names = self.pool_manager.get_all_connection_names()
        default = self.config.get("default_connection", "default")

        msg = f"📊 已配置 {len(names)} 个数据库连接:\n\n"
        for name in names:
            is_default = " (默认)" if name == default else ""
            msg += f"• {name}{is_default}\n"

        await event.send(MessageChain().message(msg))

    @mysql_group.command("状态")
    async def show_status(self, event: AstrMessageEvent):
        """查看连接池状态"""
        status = self.pool_manager.get_status()

        msg = "📊 连接池状态:\n\n"
        for name, info in status.items():
            msg += f"**{name}**\n"
            msg += f"  活跃: {info['active']}/{info['maxsize']}\n"
            msg += f"  空闲: {info['free']}\n\n"

        await event.send(MessageChain().message(msg))

    @mysql_group.command("测试连接")
    async def test_connection(self, event: AstrMessageEvent, name: str = None):
        """测试数据库连接
        
        参数:
            name: 连接名称（可选，默认测试所有连接）
        """
        if name:
            names = [name]
        else:
            names = self.pool_manager.get_all_connection_names()

        msg = "🔍 连接测试结果:\n\n"
        for conn_name in names:
            success, message = await self.pool_manager.test_connection(conn_name)
            icon = "✅" if success else "❌"
            msg += f"{icon} {conn_name}: {message}\n"

        await event.send(MessageChain().message(msg))

    @mysql_group.command("开启后台")
    async def start_webui(self, event: AstrMessageEvent):
        """启动WebUI管理界面"""
        if self.webui_process and self.webui_process.is_alive():
            port = self.config.get("webui_port", 6200)
            await event.send(
                f"✅ WebUI已在运行中\n"
                f"🌐 访问地址: http://localhost:{port}\n"
                f"👤 登录账号: {self.config.get('webui_username', 'admin')}\n"
                f"🔑 登录密码: {self.config.get('webui_password', 'admin123')}"
            )
            return

        try:
            await self._auto_start_webui()

            port = self.config.get("webui_port", 6200)
            await event.send(
                f"✅ WebUI已启动\n"
                f"🌐 访问地址: http://localhost:{port}\n"
                f"👤 登录账号: {self.config.get('webui_username', 'admin')}\n"
                f"🔑 登录密码: {self.config.get('webui_password', 'admin123')}"
            )

        except Exception as e:
            logger.error(f"启动WebUI失败: {e}", exc_info=True)
            await event.send(f"❌ 启动失败: {e}")

    @mysql_group.command("关闭后台")
    async def stop_webui(self, event: AstrMessageEvent):
        """停止WebUI管理界面"""
        if not self.webui_process or not self.webui_process.is_alive():
            await event.send("❌ WebUI未运行")
            return

        self.webui_process.terminate()
        self.webui_process.join(timeout=5)
        self.webui_process = None

        await event.send("✅ WebUI已停止")

    @mysql_group.command("帮助")
    async def show_help(self, event: AstrMessageEvent):
        """显示插件帮助信息"""
        help_text = """
📚 **MySQL插件使用指南**

**AI函数工具（自动调用）:**
• mysql_query - 查询数据
• mysql_insert - 插入数据
• mysql_update - 更新数据
• mysql_delete - 删除数据（默认禁用）
• mysql_create_table - 创建表（默认禁用）
• mysql_show_schema - 查看表结构

**管理命令:**
• /mysql 连接列表 - 查看所有数据库连接
• /mysql 状态 - 查看连接池状态
• /mysql 测试连接 [名称] - 测试连接可用性
• /mysql 开启后台 - 启动WebUI管理界面
• /mysql 关闭后台 - 停止WebUI
• /mysql 帮助 - 显示此帮助

**使用示例:**
👤 查询最近10条订单
🤖 [自动调用 mysql_query]

👤 添加用户张三，邮箱zhangsan@test.com
🤖 [自动调用 mysql_insert]

详细文档: https://github.com/Chris95743/astrbot_plugin_mysql
        """
        await event.send(help_text.strip())

