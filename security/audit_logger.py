"""
审计日志记录器
使用SQLite记录所有数据库操作
"""
import asyncio
import json
import sqlite3
from datetime import datetime
from pathlib import Path


class AuditLogger:
    """审计日志记录器"""

    def __init__(self, db_path: str = "data/audit_logs.db"):
        """
        初始化审计日志记录器
        
        Args:
            db_path: SQLite数据库文件路径
        """
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        """确保数据库和表结构存在"""
        # 创建目录
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 创建审计日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id TEXT,
                platform TEXT,
                operation TEXT NOT NULL,
                table_name TEXT,
                sql_statement TEXT NOT NULL,
                parameters TEXT,
                affected_rows INTEGER,
                execution_time REAL,
                success INTEGER NOT NULL,
                error_message TEXT,
                ip_address TEXT
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON audit_logs(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_id 
            ON audit_logs(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_operation 
            ON audit_logs(operation)
        """)

        conn.commit()
        conn.close()

    async def log(
        self,
        user_id: str | None = None,
        platform: str | None = None,
        operation: str = "",
        table_name: str | None = None,
        sql_statement: str = "",
        parameters: list | None = None,
        affected_rows: int | None = None,
        execution_time: float | None = None,
        success: bool = True,
        error_message: str | None = None,
        ip_address: str | None = None
    ):
        """
        记录审计日志（异步）
        
        Args:
            user_id: 用户ID
            platform: 平台来源（QQ/Telegram等）
            operation: 操作类型（SELECT/INSERT/UPDATE/DELETE等）
            table_name: 涉及的表名
            sql_statement: 执行的SQL语句
            parameters: 参数列表
            affected_rows: 受影响行数
            execution_time: 执行耗时（秒）
            success: 是否成功
            error_message: 错误信息（如有）
            ip_address: 来源IP地址
        """
        # 在后台线程执行，避免阻塞
        await asyncio.to_thread(
            self._log_sync,
            user_id, platform, operation, table_name,
            sql_statement, parameters, affected_rows,
            execution_time, success, error_message, ip_address
        )

    def _log_sync(
        self, user_id, platform, operation, table_name,
        sql_statement, parameters, affected_rows,
        execution_time, success, error_message, ip_address
    ):
        """同步写入日志"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO audit_logs (
                timestamp, user_id, platform, operation,
                table_name, sql_statement, parameters,
                affected_rows, execution_time, success,
                error_message, ip_address
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            user_id,
            platform,
            operation,
            table_name,
            sql_statement,
            json.dumps(parameters) if parameters else None,
            affected_rows,
            execution_time,
            1 if success else 0,
            error_message,
            ip_address
        ))

        conn.commit()
        conn.close()

    def get_logs(
        self,
        limit: int = 100,
        offset: int = 0,
        user_id: str | None = None,
        operation: str | None = None,
        success: bool | None = None,
        start_time: str | None = None,
        end_time: str | None = None
    ) -> list:
        """
        查询审计日志
        
        Args:
            limit: 返回数量限制
            offset: 偏移量（分页）
            user_id: 筛选用户ID
            operation: 筛选操作类型
            success: 筛选成功/失败
            start_time: 开始时间（ISO格式）
            end_time: 结束时间（ISO格式）
            
        Returns:
            list: 日志记录列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 构建查询条件
        conditions = []
        params = []

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)

        if operation:
            conditions.append("operation = ?")
            params.append(operation)

        if success is not None:
            conditions.append("success = ?")
            params.append(1 if success else 0)

        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)

        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT * FROM audit_logs
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        conn.close()

        return [dict(row) for row in rows]

    def get_statistics(self) -> dict:
        """获取审计日志统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 总操作数
        cursor.execute("SELECT COUNT(*) FROM audit_logs")
        total_operations = cursor.fetchone()[0]

        # 成功率
        cursor.execute("SELECT COUNT(*) FROM audit_logs WHERE success = 1")
        successful_operations = cursor.fetchone()[0]

        # 按操作类型统计
        cursor.execute("""
            SELECT operation, COUNT(*) as count
            FROM audit_logs
            GROUP BY operation
            ORDER BY count DESC
        """)
        operations_by_type = dict(cursor.fetchall())

        # 平均执行时间
        cursor.execute("SELECT AVG(execution_time) FROM audit_logs WHERE execution_time IS NOT NULL")
        avg_execution_time = cursor.fetchone()[0] or 0

        conn.close()

        return {
            "total_operations": total_operations,
            "successful_operations": successful_operations,
            "success_rate": successful_operations / total_operations if total_operations > 0 else 0,
            "operations_by_type": operations_by_type,
            "avg_execution_time": avg_execution_time
        }

    def clear_logs(self, older_than_days: int | None = None) -> int:
        """
        清理审计日志
        
        Args:
            older_than_days: 删除N天前的日志。如果为None，则清空所有日志
            
        Returns:
            int: 删除的日志条数
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if older_than_days is None:
            # 清空所有日志
            cursor.execute("SELECT COUNT(*) FROM audit_logs")
            count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM audit_logs")
        else:
            # 删除N天前的日志
            from datetime import timedelta
            cutoff_time = (datetime.now() - timedelta(days=older_than_days)).isoformat()
            cursor.execute("SELECT COUNT(*) FROM audit_logs WHERE timestamp < ?", (cutoff_time,))
            count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM audit_logs WHERE timestamp < ?", (cutoff_time,))
        
        conn.commit()
        conn.close()
        
        # VACUUM 必须在事务外执行
        conn = sqlite3.connect(self.db_path)
        conn.execute("VACUUM")
        conn.close()
        
        return count


# 测试代码
if __name__ == "__main__":
    import asyncio

    async def test():
        logger = AuditLogger("test_audit.db")

        # 记录一条成功的查询
        await logger.log(
            user_id="QQ_123456789",
            platform="QQ",
            operation="SELECT",
            table_name="users",
            sql_statement="SELECT * FROM users WHERE id = %s",
            parameters=[1],
            affected_rows=1,
            execution_time=0.025,
            success=True
        )

        # 记录一条失败的操作
        await logger.log(
            user_id="Telegram_987654",
            platform="Telegram",
            operation="DELETE",
            table_name="orders",
            sql_statement="DELETE FROM orders WHERE id = %s",
            parameters=[100],
            success=False,
            error_message="DELETE操作已被禁用"
        )

        # 查询日志
        logs = logger.get_logs(limit=10)
        print("最近10条日志:")
        for log in logs:
            print(f"  {log['timestamp']} | {log['operation']:8s} | "
                  f"{'✅' if log['success'] else '❌'} | {log['sql_statement'][:50]}")

        # 统计信息
        stats = logger.get_statistics()
        print("\n统计信息:")
        print(f"  总操作数: {stats['total_operations']}")
        print(f"  成功率: {stats['success_rate']*100:.1f}%")
        print(f"  平均耗时: {stats['avg_execution_time']*1000:.2f}ms")
        print(f"  操作分布: {stats['operations_by_type']}")

    asyncio.run(test())
