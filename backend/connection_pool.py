"""
数据库连接池管理器
支持多个数据库连接池的管理
"""
import asyncio
from typing import Any

import aiomysql
from aiomysql import Pool

# 处理astrbot.api导入
try:
    from astrbot.api import logger
except ImportError:
    # 独立运行模式，使用print代替
    class MockLogger:
        @staticmethod
        def info(msg): print(f"INFO: {msg}")
        @staticmethod
        def warning(msg): print(f"WARNING: {msg}")
        @staticmethod
        def error(msg, **kwargs): print(f"ERROR: {msg}")
        @staticmethod
        def debug(msg): print(f"DEBUG: {msg}")
    logger = MockLogger()


class ConnectionPoolManager:
    """管理多个数据库连接池，支持动态配置重载"""

    def __init__(self, config: dict, config_file_path: str = None):
        """
        初始化连接池管理器
        
        Args:
            config: 插件配置字典
            config_file_path: 配置文件路径，用于动态重载
        """
        self.config = config
        self.pools: dict[str, Pool] = {}  # name -> Pool
        self.connections_config: list[dict] = []
        self.config_file_path = config_file_path
        self._config_mtime = 0  # 配置文件最后修改时间
        self._parse_connections()
        self._update_config_mtime()

    def _parse_connections(self):
        """解析连接配置，支持多种格式"""
        connections = self.config.get("connections", [])

        # 处理字符串格式
        if isinstance(connections, str):
            # 尝试使用 ||| 分隔符解析（新格式）
            if "|||" in connections:
                connections = self._parse_delimiter_format(connections)
            else:
                # 尝试JSON解析（旧格式）
                import json
                try:
                    connections = json.loads(connections)
                except json.JSONDecodeError as e:
                    logger.error(f"解析连接配置失败: {e}")
                    connections = []

        # 确保是列表
        if not isinstance(connections, list):
            connections = [connections]

        self.connections_config = connections
        logger.info(f"加载了 {len(self.connections_config)} 个数据库连接配置")
    
    def _update_config_mtime(self):
        """更新配置文件的修改时间"""
        if self.config_file_path:
            try:
                from pathlib import Path
                config_path = Path(self.config_file_path)
                if config_path.exists():
                    self._config_mtime = config_path.stat().st_mtime
            except Exception as e:
                logger.debug(f"无法获取配置文件修改时间: {e}")
    
    def _check_config_changed(self) -> bool:
        """检查配置文件是否已修改"""
        if not self.config_file_path:
            return False
        
        try:
            from pathlib import Path
            config_path = Path(self.config_file_path)
            if not config_path.exists():
                return False
            
            current_mtime = config_path.stat().st_mtime
            return current_mtime > self._config_mtime
        except Exception as e:
            logger.debug(f"检查配置文件变更失败: {e}")
            return False
    
    async def reload_config_if_changed(self) -> bool:
        """如果配置文件已变更，重新加载配置并重建连接池
        
        Returns:
            bool: 是否进行了重载
        """
        if not self._check_config_changed():
            return False
        
        logger.info("🔄 检测到配置文件变更，重新加载...")
        
        try:
            # 读取新配置
            import json
            from pathlib import Path
            
            config_path = Path(self.config_file_path)
            with open(config_path, 'r', encoding='utf-8') as f:
                new_connections = json.load(f)
            
            if not isinstance(new_connections, list):
                new_connections = []
            
            # 关闭所有旧连接池
            await self.close_all()
            
            # 更新配置
            self.connections_config = new_connections
            self._update_config_mtime()
            
            # 重新初始化所有连接池
            await self.initialize_all()
            
            logger.info(f"✅ 配置已重载，共 {len(new_connections)} 个连接")
            return True
            
        except Exception as e:
            logger.error(f"❌ 配置重载失败: {e}")
            return False

    def _parse_delimiter_format(self, config_str: str) -> list[dict]:
        """
        解析使用分隔符的配置格式
        
        格式示例:
        name=default
        host=localhost
        port=3306
        username=root
        password=123456
        database=test
        |||
        name=analytics
        host=192.168.1.100
        port=3306
        ...
        
        Returns:
            List[dict]: 连接配置列表
        """
        connections = []

        # 按 ||| 分割不同的连接
        blocks = config_str.strip().split("|||")

        for block in blocks:
            if not block.strip():
                continue

            conn = {}
            lines = block.strip().split("\n")

            for line in lines:
                line = line.strip()
                if not line or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # 类型转换
                if key == "port":
                    conn[key] = int(value) if value else 3306
                elif key == "pool_size":
                    conn[key] = int(value) if value else 3
                elif key == "max_query_rows":
                    conn[key] = int(value) if value else 1000
                elif key == "max_update_rows":
                    conn[key] = int(value) if value else 100
                elif key in ["enable_insert", "enable_update", "enable_delete", "enable_create_table"]:
                    conn[key] = value.lower() in ["true", "1", "yes", "on"] if value else False
                elif key in ["table_whitelist", "table_blacklist"]:
                    # 处理数组，使用逗号分隔
                    if value:
                        conn[key] = [t.strip() for t in value.split(",") if t.strip()]
                    else:
                        conn[key] = []
                else:
                    # 字符串类型，保留空值
                    conn[key] = value

            # 设置默认值
            conn.setdefault("name", "unnamed")
            conn.setdefault("port", 3306)
            conn.setdefault("charset", "utf8mb4")
            conn.setdefault("enable_insert", True)
            conn.setdefault("enable_update", True)
            conn.setdefault("enable_delete", False)
            conn.setdefault("enable_create_table", False)
            conn.setdefault("table_whitelist", [])
            conn.setdefault("table_blacklist", ["mysql", "information_schema", "performance_schema", "sys"])
            conn.setdefault("max_query_rows", 1000)
            conn.setdefault("max_update_rows", 100)
            conn.setdefault("pool_size", 3)

            connections.append(conn)

        return connections

    async def initialize_all(self):
        """初始化所有连接池"""
        for conn_config in self.connections_config:
            name = conn_config.get("name", "unnamed")
            
            # 跳过禁用的连接
            if conn_config.get("enabled") == False:
                logger.info(f"⏭️  连接 '{name}' 已被禁用，跳过初始化")
                continue
            
            try:
                # 调试：打印配置信息（隐藏密码）
                debug_config = {k: ("***" if k == "password" else v) for k, v in conn_config.items()}
                logger.debug(f"初始化连接 '{name}': {debug_config}")

                await self.initialize_pool(name, conn_config)
                logger.info(f"✅ 连接池 '{name}' 初始化成功")
            except Exception as e:
                logger.error(f"❌ 连接池 '{name}' 初始化失败: {e}")

    async def initialize_pool(self, name: str, conn_config: dict):
        """
        初始化单个连接池
        
        Args:
            name: 连接名称
            conn_config: 连接配置
        """
        # 修复：空密码应传递None而不是空字符串
        password = conn_config.get("password", "")
        pool = await aiomysql.create_pool(
            host=conn_config.get("host", "localhost"),
            port=conn_config.get("port", 3306),
            user=conn_config.get("username", "root"),
            password=password if password else None,
            db=conn_config.get("database", "test"),
            charset=conn_config.get("charset", "utf8mb4"),
            minsize=1,
            maxsize=conn_config.get("pool_size", 3),
            pool_recycle=self.config.get("pool_recycle", 3600),
            autocommit=True
        )

        self.pools[name] = pool

    async def execute(
        self,
        sql: str,
        params: tuple = None,
        connection_name: str | None = None
    ) -> Any:
        """
        执行SQL语句（支持动态配置重载）
        
        Args:
            sql: SQL语句
            params: 参数元组
            connection_name: 连接名称（None则使用默认连接）
            
        Returns:
            查询结果（SELECT）或受影响行数（INSERT/UPDATE/DELETE）
        """
        # 检查配置是否已变更，如有变更则自动重载
        await self.reload_config_if_changed()
        
        if connection_name is None:
            connection_name = self.config.get("default_connection", "default")

        # 检查连接是否被禁用
        conn_config = None
        for config in self.connections_config:
            if config.get("name") == connection_name:
                conn_config = config
                break
        
        if conn_config and conn_config.get("enabled") == False:
            raise ValueError(f"连接 '{connection_name}' 已被禁用")

        pool = self.pools.get(connection_name)
        if not pool:
            raise ValueError(f"连接 '{connection_name}' 不存在")

        timeout = self.config.get("query_timeout", 30.0)

        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                try:
                    await asyncio.wait_for(
                        cursor.execute(sql, params),
                        timeout=timeout
                    )

                    # 判断是否为查询语句
                    if sql.strip().upper().startswith("SELECT") or \
                       sql.strip().upper().startswith("SHOW") or \
                       sql.strip().upper().startswith("DESCRIBE") or \
                       sql.strip().upper().startswith("DESC"):
                        result = await cursor.fetchall()
                        return result
                    else:
                        # INSERT/UPDATE/DELETE
                        return {
                            "affected_rows": cursor.rowcount,
                            "last_insert_id": cursor.lastrowid
                        }

                except asyncio.TimeoutError:
                    raise TimeoutError(f"查询超时（{timeout}秒）")

    def get_connection_config(self, connection_name: str) -> dict | None:
        """获取指定连接的配置"""
        for conn_config in self.connections_config:
            if conn_config.get("name") == connection_name:
                return conn_config
        return None

    def get_all_connection_names(self) -> list[str]:
        """获取所有连接名称"""
        return [conn.get("name", "unnamed") for conn in self.connections_config]

    async def test_connection(self, connection_name: str) -> tuple[bool, str]:
        """
        测试连接是否可用
        
        Returns:
            (success, message)
        """
        try:
            await self.execute("SELECT 1", connection_name=connection_name)
            return True, "连接正常"
        except Exception as e:
            return False, str(e)

    async def close_all(self):
        """关闭所有连接池"""
        for name, pool in self.pools.items():
            try:
                pool.close()
                await pool.wait_closed()
                logger.info(f"连接池 '{name}' 已关闭")
            except Exception as e:
                logger.error(f"关闭连接池 '{name}' 失败: {e}")

        self.pools.clear()

    def _get_pool(self, connection_name: str | None = None):
        """获取连接池，如果不存在则抛出异常"""
        if connection_name is None:
            connection_name = self.config.get("default_connection", "default")

        pool = self.pools.get(connection_name)
        if not pool:
            raise ValueError(f"连接 '{connection_name}' 不存在")
        return pool

    def get_status(self) -> dict:
        """获取所有连接池状态"""
        status = {}
        for name, pool in self.pools.items():
            status[name] = {
                "size": pool.size,
                "free": pool.freesize,
                "active": pool.size - pool.freesize,
                "maxsize": pool.maxsize,
                "minsize": pool.minsize
            }
        return status

    async def get_tables(self, connection_name: str | None = None) -> list[str]:
        """
        获取数据库所有表名
        
        Args:
            connection_name: 连接名称，None则使用默认连接
            
        Returns:
            表名列表
        """
        pool = self._get_pool(connection_name)

        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SHOW TABLES")
                results = await cursor.fetchall()

                # 提取表名（SHOW TABLES返回的字段名是 Tables_in_xxx）
                if not results:
                    return []

                # 获取第一个字段名（通常是 Tables_in_数据库名）
                field_name = list(results[0].keys())[0]
                return [row[field_name] for row in results]

    async def get_table_schema(self, connection_name: str | None, table_name: str) -> list[dict]:
        """
        获取表结构
        
        Args:
            connection_name: 连接名称
            table_name: 表名
            
        Returns:
            表结构字典列表
        """
        pool = self._get_pool(connection_name)

        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 使用DESCRIBE获取表结构
                await cursor.execute(f"DESCRIBE `{table_name}`")
                results = await cursor.fetchall()
                return results
