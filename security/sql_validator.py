"""
SQL语法验证器
检测危险操作、SQL注入等安全风险
"""
import re

from ..config import DANGEROUS_SQL_PATTERNS


class SQLValidator:
    """SQL安全验证器"""

    def __init__(self):
        self.dangerous_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in DANGEROUS_SQL_PATTERNS
        ]

    def is_dangerous(self, sql: str) -> tuple[bool, str]:
        """
        检查SQL是否包含危险操作
        
        Args:
            sql: SQL语句
            
        Returns:
            (is_dangerous, reason): (是否危险, 原因描述)
        """
        if not sql:
            return False, ""

        for pattern in self.dangerous_patterns:
            match = pattern.search(sql)
            if match:
                return True, f"包含危险操作: {match.group()}"

        return False, ""

    def is_select_query(self, sql: str) -> bool:
        """判断是否为SELECT查询"""
        return sql.strip().upper().startswith("SELECT")

    def is_insert_query(self, sql: str) -> bool:
        """判断是否为INSERT语句"""
        return sql.strip().upper().startswith("INSERT")

    def is_update_query(self, sql: str) -> bool:
        """判断是否为UPDATE语句"""
        return sql.strip().upper().startswith("UPDATE")

    def is_delete_query(self, sql: str) -> bool:
        """判断是否为DELETE语句"""
        return sql.strip().upper().startswith("DELETE")

    def has_where_clause(self, sql: str) -> bool:
        """检查是否包含WHERE子句"""
        return bool(re.search(r"\bWHERE\b", sql, re.IGNORECASE))

    def validate_update_delete(self, sql: str, operation: str) -> tuple[bool, str]:
        """
        验证UPDATE/DELETE语句安全性
        
        Args:
            sql: SQL语句
            operation: 操作类型（UPDATE/DELETE）
            
        Returns:
            (is_valid, error_message)
        """
        # 检查是否包含WHERE子句
        if not self.has_where_clause(sql):
            return False, f"{operation}操作必须包含WHERE条件，防止全表{operation.lower()}"

        # 检查危险操作
        is_dangerous, reason = self.is_dangerous(sql)
        if is_dangerous:
            return False, reason

        return True, ""


# 测试代码
if __name__ == "__main__":
    validator = SQLValidator()

    test_cases = [
        ("SELECT * FROM users", "查询", True),
        ("DROP TABLE users", "删除表", False),
        ("DELETE FROM users WHERE id = 1", "带WHERE的删除", True),
        ("DELETE FROM users", "全表删除", False),
        ("UPDATE users SET name='test' WHERE id=1", "带WHERE的更新", True),
        ("UPDATE users SET name='test'", "全表更新", False),
        ("SELECT * FROM users; DROP TABLE users;", "SQL注入", False),
        ("SELECT * FROM users -- comment", "注释注入", False),
    ]

    print("SQL验证器测试:")
    print("=" * 80)

    for sql, desc, expected_safe in test_cases:
        is_dangerous, reason = validator.is_dangerous(sql)
        is_safe = not is_dangerous

        status = "✅" if is_safe == expected_safe else "❌"
        print(f"{status} {desc:15s} | 安全: {is_safe:5s} | SQL: {sql[:40]}")
        if reason:
            print(f"   原因: {reason}")

    print("\nWHERE子句检查:")
    print("-" * 80)
    for sql, desc, _ in test_cases:
        if "DELETE" in sql or "UPDATE" in sql:
            has_where = validator.has_where_clause(sql)
            operation = "DELETE" if "DELETE" in sql else "UPDATE"
            is_valid, error = validator.validate_update_delete(sql, operation)
            print(f"{desc:20s} | WHERE: {has_where:5s} | 合法: {is_valid:5s}")
            if error:
                print(f"  错误: {error}")
