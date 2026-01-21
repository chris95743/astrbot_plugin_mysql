"""
权限管理器
基于连接配置的权限检查
"""
from ..config import SYSTEM_TABLES


class PermissionManager:
    """权限检查管理器"""

    def __init__(self, pool_manager):
        """
        初始化权限管理器
        
        Args:
            pool_manager: ConnectionPoolManager实例
        """
        self.pool_manager = pool_manager

    def check_table_permission(
        self,
        table: str,
        connection_name: str
    ) -> tuple[bool, str]:
        """
        检查表访问权限
        
        Args:
            table: 表名
            connection_name: 连接名称
            
        Returns:
            (allowed, reason)
        """
        config = self.pool_manager.get_connection_config(connection_name)
        if not config:
            return False, f"连接 '{connection_name}' 不存在"

        # 检查系统表（强制黑名单）
        if table.lower() in [t.lower() for t in SYSTEM_TABLES]:
            return False, f"禁止操作系统表 '{table}'"

        # 检查黑名单
        blacklist = config.get("table_blacklist", [])
        if table.lower() in [t.lower() for t in blacklist]:
            return False, f"表 '{table}' 在黑名单中"

        # 检查白名单（如果配置了白名单）
        whitelist = config.get("table_whitelist", [])
        if whitelist:
            if table.lower() not in [t.lower() for t in whitelist]:
                return False, f"表 '{table}' 不在白名单中"

        return True, ""

    def check_operation_permission(
        self,
        operation: str,
        connection_name: str
    ) -> tuple[bool, str]:
        """
        检查操作类型权限
        
        Args:
            operation: 操作类型（INSERT/UPDATE/DELETE/CREATE_TABLE）
            connection_name: 连接名称
            
        Returns:
            (allowed, reason)
        """
        config = self.pool_manager.get_connection_config(connection_name)
        if not config:
            return False, f"连接 '{connection_name}' 不存在"

        operation = operation.upper()

        permission_map = {
            "INSERT": "enable_insert",
            "UPDATE": "enable_update",
            "DELETE": "enable_delete",
            "CREATE_TABLE": "enable_create_table",
            "CREATE": "enable_create_table"
        }

        config_key = permission_map.get(operation)
        if not config_key:
            # SELECT等操作默认允许
            return True, ""

        if not config.get(config_key, False):
            return False, f"{operation} 操作已被禁用"

        return True, ""

    def get_max_query_rows(self, connection_name: str) -> int:
        """获取最大查询行数限制"""
        config = self.pool_manager.get_connection_config(connection_name)
        if not config:
            return 1000  # 默认值
        return config.get("max_query_rows", 1000)

    def get_max_update_rows(self, connection_name: str) -> int:
        """获取最大更新/删除行数限制"""
        config = self.pool_manager.get_connection_config(connection_name)
        if not config:
            return 100  # 默认值
        return config.get("max_update_rows", 100)

    def validate_operation(
        self,
        operation: str,
        table: str | None,
        connection_name: str
    ) -> tuple[bool, str]:
        """
        综合验证操作权限
        
        Args:
            operation: 操作类型
            table: 表名（可选）
            connection_name: 连接名称
            
        Returns:
            (allowed, reason)
        """
        # 检查操作权限
        allowed, reason = self.check_operation_permission(operation, connection_name)
        if not allowed:
            return False, reason

        # 检查表权限
        if table:
            allowed, reason = self.check_table_permission(table, connection_name)
            if not allowed:
                return False, reason

        return True, ""
