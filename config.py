"""
配置常量和默认值
"""

# 默认单个连接配置模板
DEFAULT_CONNECTION_TEMPLATE = {
    "name": "default",
    "host": "localhost",
    "port": 3306,
    "username": "root",
    "password": "",
    "database": "test",
    "charset": "utf8mb4",

    "enable_insert": True,
    "enable_update": True,
    "enable_delete": False,
    "enable_create_table": False,

    "table_whitelist": [],
    "table_blacklist": ["mysql", "information_schema", "performance_schema", "sys"],

    "max_query_rows": 1000,
    "max_update_rows": 100,
    "pool_size": 3,
}

# 默认配置
DEFAULT_CONFIG = {
    "connections": [DEFAULT_CONNECTION_TEMPLATE.copy()],
    "default_connection": "default",
    "query_timeout": 30.0,

    "webui_port": 6200,
    "webui_username": "admin",
    "webui_password": "admin123",
    "enable_audit_log": True,

    "pool_recycle": 3600,
    "enable_ssl": False
}

# SQL危险关键词（正则表达式）
DANGEROUS_SQL_PATTERNS = [
    r"\bDROP\s+DATABASE\b",
    r"\bDROP\s+TABLE\b",
    r"\bTRUNCATE\b",
    r"\bFLUSH\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bALTER\s+USER\b",
    r"\bCREATE\s+USER\b",
    r"--",  # SQL注释
    r"/\*",  # 多行注释开始
    r"\*/--",  # 注释结束
]

# 系统保留表（强制黑名单）
SYSTEM_TABLES = [
    "mysql",
    "information_schema",
    "performance_schema",
    "sys"
]

# WebUI相关
WEBUI_SESSION_EXPIRY = 7 * 24 * 3600  # 7天（秒）
WEBUI_SECRET_KEY_LENGTH = 32  # 32字节

# 审计日志
AUDIT_LOG_DB_NAME = "audit_logs.db"
AUDIT_LOG_TABLE_NAME = "audit_logs"

# 密码哈希
PASSWORD_HASH_METHOD = "MD5_16_LOWERCASE"  # MD5 16位小写
