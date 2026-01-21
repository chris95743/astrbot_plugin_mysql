"""
查询执行器
负责SQL执行和结果格式化
"""
import re
from typing import Any

from ..security.sql_validator import SQLValidator


class QueryExecutor:
    """SQL查询执行器"""

    def __init__(self, pool_manager, permission_manager, audit_logger):
        """
        初始化查询执行器
        
        Args:
            pool_manager: ConnectionPoolManager实例
            permission_manager: PermissionManager实例
            audit_logger: AuditLogger实例
        """
        self.pool_manager = pool_manager
        self.permission_manager = permission_manager
        self.audit_logger = audit_logger
        self.validator = SQLValidator()

    async def execute_query(
        self,
        sql: str,
        params: tuple | None = None,
        connection_name: str | None = None,
        user_id: str | None = None,
        platform: str | None = None
    ) -> tuple[bool, Any]:
        """
        执行查询并返回结果
        
        Args:
            sql: SQL语句
            params: 参数
            connection_name: 连接名称
            user_id: 用户ID
            platform: 平台
            
        Returns:
            (success, result/error_message)
        """
        import time
        start_time = time.time()

        # 使用默认连接
        if connection_name is None:
            connection_name = self.pool_manager.config.get("default_connection", "default")

        # 提取操作类型和表名
        operation = self._get_operation_type(sql)
        table_name = self._extract_table_name(sql, operation)

        # 检查SQL安全性
        is_dangerous, reason = self.validator.is_dangerous(sql)
        if is_dangerous:
            await self._log_failure(
                user_id, platform, operation, table_name,
                sql, params, 0, reason
            )
            return False, f"❌ 安全检查失败: {reason}"

        # 检查权限
        allowed, reason = self.permission_manager.validate_operation(
            operation, table_name, connection_name
        )
        if not allowed:
            await self._log_failure(
                user_id, platform, operation, table_name,
                sql, params, 0, f"权限不足: {reason}"
            )
            return False, f"❌ {reason}"

        # UPDATE/DELETE需要WHERE子句
        if operation in ["UPDATE", "DELETE"]:
            is_valid, error = self.validator.validate_update_delete(sql, operation)
            if not is_valid:
                await self._log_failure(
                    user_id, platform, operation, table_name,
                    sql, params, 0, error
                )
                return False, f"❌ {error}"

        # 自动添加LIMIT（SELECT查询）
        if operation == "SELECT":
            max_rows = self.permission_manager.get_max_query_rows(connection_name)
            sql = self._add_limit(sql, max_rows)

        try:
            # 执行查询
            result = await self.pool_manager.execute(sql, params, connection_name)
            execution_time = time.time() - start_time

            # 记录审计日志
            if isinstance(result, dict):
                # INSERT/UPDATE/DELETE
                affected_rows = result.get("affected_rows", 0)
            else:
                # SELECT
                affected_rows = len(result) if result else 0

            await self.audit_logger.log(
                user_id=user_id,
                platform=platform,
                operation=operation,
                table_name=table_name,
                sql_statement=sql,
                parameters=list(params) if params else None,
                affected_rows=affected_rows,
                execution_time=execution_time,
                success=True
            )

            # 格式化结果
            formatted_result = self._format_result(result, operation)
            return True, formatted_result

        except Exception as e:
            execution_time = time.time() - start_time
            await self._log_failure(
                user_id, platform, operation, table_name,
                sql, params, execution_time, str(e)
            )
            return False, f"❌ 执行失败: {e}"

    def _get_operation_type(self, sql: str) -> str:
        """提取SQL操作类型"""
        sql_upper = sql.strip().upper()
        for op in ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "SHOW", "DESCRIBE", "DESC"]:
            if sql_upper.startswith(op):
                if op == "CREATE" and "TABLE" in sql_upper[:20]:
                    return "CREATE_TABLE"
                return op
        return "UNKNOWN"

    def _extract_table_name(self, sql: str, operation: str) -> str | None:
        """从SQL中提取表名"""
        try:
            if operation == "SELECT":
                # SELECT * FROM table_name ...
                match = re.search(r"\bFROM\s+`?(\w+)`?", sql, re.IGNORECASE)
                return match.group(1) if match else None

            elif operation == "INSERT":
                # INSERT INTO table_name ...
                match = re.search(r"\bINTO\s+`?(\w+)`?", sql, re.IGNORECASE)
                return match.group(1) if match else None

            elif operation in ["UPDATE", "DELETE"]:
                # UPDATE table_name ... / DELETE FROM table_name ...
                match = re.search(r"\b(?:UPDATE|FROM)\s+`?(\w+)`?", sql, re.IGNORECASE)
                return match.group(1) if match else None

            elif operation == "CREATE_TABLE":
                # CREATE TABLE table_name ...
                match = re.search(r"\bTABLE\s+`?(\w+)`?", sql, re.IGNORECASE)
                return match.group(1) if match else None

        except Exception:
            pass

        return None

    def _add_limit(self, sql: str, max_rows: int) -> str:
        """为SELECT语句添加LIMIT"""
        # 检查是否已有LIMIT
        if re.search(r"\bLIMIT\s+\d+", sql, re.IGNORECASE):
            return sql

        # 添加LIMIT
        return f"{sql.rstrip(';')} LIMIT {max_rows}"

    def _format_result(self, result: Any, operation: str) -> str:
        """格式化查询结果为Markdown"""
        if operation == "SELECT" or operation in ["SHOW", "DESCRIBE", "DESC"]:
            return self._format_select_result(result)
        else:
            # INSERT/UPDATE/DELETE
            if isinstance(result, dict):
                affected = result.get("affected_rows", 0)
                last_id = result.get("last_insert_id")

                msg = f"✅ 操作成功，影响 {affected} 行"
                if last_id and last_id > 0:
                    msg += f"，新记录ID: {last_id}"
                return msg
            else:
                return "✅ 操作成功"

    def _format_select_result(self, rows: list[dict]) -> str:
        """将SELECT结果格式化为Markdown表格"""
        if not rows:
            return "查询结果为空（0行）"

        # 获取列名
        columns = list(rows[0].keys())

        # 构建表格头部
        header = "| " + " | ".join(columns) + " |"
        separator = "|" + "|".join(["---" for _ in columns]) + "|"

        # 构建表格内容
        lines = [header, separator]
        for row in rows[:100]:  # 最多显示100行
            values = [self._format_value(row.get(col)) for col in columns]
            line = "| " + " | ".join(values) + " |"
            lines.append(line)

        result = "\n".join(lines)
        result += f"\n\n共 {len(rows)} 行"

        if len(rows) > 100:
            result += "（仅显示前100行）"

        return result

    def _format_value(self, value: Any) -> str:
        """格式化单个值"""
        if value is None:
            return "NULL"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, bytes):
            return f"<binary:{len(value)}bytes>"
        else:
            # 截断过长的字符串
            s = str(value)
            if len(s) > 50:
                return s[:47] + "..."
            return s

    async def _log_failure(
        self,
        user_id: str | None,
        platform: str | None,
        operation: str,
        table_name: str | None,
        sql: str,
        params: tuple | None,
        execution_time: float,
        error_message: str
    ):
        """记录失败的操作"""
        await self.audit_logger.log(
            user_id=user_id,
            platform=platform,
            operation=operation,
            table_name=table_name,
            sql_statement=sql,
            parameters=list(params) if params else None,
            affected_rows=0,
            execution_time=execution_time,
            success=False,
            error_message=error_message
        )
