"""
WebUI服务器
基于Quart的异步Web应用
"""
import json
import os
import sys
from functools import wraps
from pathlib import Path

import aiomysql
import hypercorn.asyncio
from hypercorn.config import Config
from quart import Quart, jsonify, redirect, render_template, request, session, url_for

# 处理相对导入
try:
    from .security.password_hasher import verify_password
    from .backend.connection_pool import ConnectionPoolManager
    from .security.audit_logger import AuditLogger
    from .config_manager import ConfigManager
    try:
        from astrbot.api import logger
    except ImportError:
        # 如果无法导入logger，使用print
        class MockLogger:
            @staticmethod
            def info(msg): print(f"INFO: {msg}")
            @staticmethod
            def error(msg): print(f"ERROR: {msg}")
        logger = MockLogger()
    RUNNING_AS_MODULE = True
except ImportError:
    # 独立运行模式
    sys.path.insert(0, str(Path(__file__).parent))
    from security.password_hasher import verify_password
    from backend.connection_pool import ConnectionPoolManager
    from security.audit_logger import AuditLogger
    from config_manager import ConfigManager
    
    class MockLogger:
        @staticmethod
        def info(msg): print(f"INFO: {msg}")
        @staticmethod
        def error(msg): print(f"ERROR: {msg}")
    logger = MockLogger()
    RUNNING_AS_MODULE = False

# 获取插件目录
PLUGIN_DIR = Path(__file__).parent

# 创建Quart应用，指定模板和静态文件路径
app = Quart(
    __name__,
    template_folder=str(PLUGIN_DIR / "templates"),
    static_folder=str(PLUGIN_DIR / "static")
)
app.secret_key = os.urandom(32)

# 全局配置和组件
_config = {}
_data_dir = ""
_pool_manager = None
_permission_manager = None
_query_executor = None
_audit_logger = None


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    async def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "未登录"}), 401
            return redirect(url_for("login_page"))
        return await f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


# ==================== 页面路由 ====================

@app.route("/")
@login_required
async def index():
    """主页"""
    return await render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
async def login_page():
    """登录页"""
    if session.get("logged_in"):
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        form_data = await request.form
        username = form_data.get("username")
        password = form_data.get("password")

        # 验证用户名和密码
        config_username = _config.get("webui_username", "admin")
        config_password = _config.get("webui_password", "admin123")

        # 验证用户名
        if username != config_username:
            error = "用户名或密码错误"
        else:
            # 验证密码（支持MD5和明文）
            password_valid = False
            if len(config_password) == 16 and config_password.islower() and all(c in "0123456789abcdef" for c in config_password):
                # 配置中是MD5哈希值
                password_valid = verify_password(password, config_password)
            else:
                # 配置中是明文密码
                password_valid = (password == config_password)

            if password_valid:
                session["logged_in"] = True
                session["username"] = username
                return redirect(url_for("index"))
            else:
                error = "用户名或密码错误"

    return await render_template("login.html", error=error)


@app.route("/logout")
async def logout():
    """登出"""
    session.clear()
    return redirect(url_for("login_page"))


# ==================== API路由 ====================

@app.route("/api/status")
@login_required
async def api_status():
    """获取系统状态"""
    connections = _config.get("connections", [])
    
    # 解析连接配置
    if isinstance(connections, str):
        # 尝试delimiter格式解析
        if "|||" in connections:
            from .backend.connection_pool import ConnectionPoolManager
            temp_manager = ConnectionPoolManager(_config)
            connections = temp_manager.connections_config
        else:
            # JSON格式
            try:
                connections = json.loads(connections)
            except:
                connections = []
    
    if not isinstance(connections, list):
        connections = []
    
    return jsonify({
        "connections": len(connections),
        "default_connection": _config.get("default_connection", "default"),
        "audit_enabled": _config.get("enable_audit_log", True)
    })


@app.route("/api/connections")
@login_required
async def api_connections():
    """获取所有连接配置（直接读取配置文件）"""
    # 直接从配置文件读取，不使用全局变量
    config_manager = ConfigManager(_data_dir)
    connections = config_manager.load_connections()
    
    # 如果配置文件为空，使用全局配置作为后备
    if not connections:
        connections = _config.get("connections", [])
        if isinstance(connections, str):
            if "|||" in connections:
                from .backend.connection_pool import ConnectionPoolManager
                temp_manager = ConnectionPoolManager(_config)
                connections = temp_manager.connections_config
            else:
                try:
                    connections = json.loads(connections)
                except:
                    connections = []
    
    if not isinstance(connections, list):
        connections = []

    # 隐藏密码并格式化权限
    safe_connections = []
    for conn in connections:
        safe_conn = {
            "name": conn.get("name", "未命名"),
            "host": conn.get("host", "localhost"),
            "port": conn.get("port", 3306),
            "database": conn.get("database", ""),
            "username": conn.get("username", ""),
            "charset": conn.get("charset", "utf8mb4"),
            "password": "******",
            "enabled": conn.get("enabled", True),
            "permissions": {
                "allow_insert": conn.get("enable_insert", False),
                "allow_update": conn.get("enable_update", False),
                "allow_delete": conn.get("enable_delete", False),
                "allow_create": conn.get("enable_create_table", False)
            }
        }
        safe_connections.append(safe_conn)

    return jsonify({
        "success": True,
        "connections": safe_connections
    })


@app.route("/api/connections/<connection_name>")
@login_required
async def api_connection_detail(connection_name):
    """获取指定连接的详细信息（包含密码）"""
    # 直接从配置文件读取
    config_manager = ConfigManager(_data_dir)
    connections = config_manager.load_connections()
    
    # 如果配置文件为空，使用全局配置
    if not connections:
        connections = _config.get("connections", [])
        if isinstance(connections, str):
            if "|||" in connections:
                from .backend.connection_pool import ConnectionPoolManager
                temp_manager = ConnectionPoolManager(_config)
                connections = temp_manager.connections_config
            else:
                try:
                    connections = json.loads(connections)
                except:
                    connections = []
    
    if not isinstance(connections, list):
        connections = []
    
    # 查找指定连接
    target_conn = None
    for conn in connections:
        if conn.get("name") == connection_name:
            target_conn = conn
            break
    
    if not target_conn:
        return jsonify({
            "success": False,
            "error": f"连接 '{connection_name}' 不存在"
        }), 404
    
    # 返回完整信息（用于编辑）
    return jsonify({
        "success": True,
        "connection": {
            "name": target_conn.get("name", ""),
            "host": target_conn.get("host", "localhost"),
            "port": target_conn.get("port", 3306),
            "database": target_conn.get("database", ""),
            "username": target_conn.get("username", ""),
            "password": target_conn.get("password", ""),
            "charset": target_conn.get("charset", "utf8mb4"),
            "enabled": target_conn.get("enabled", True),
            "enable_insert": target_conn.get("enable_insert", False),
            "enable_update": target_conn.get("enable_update", False),
            "enable_delete": target_conn.get("enable_delete", False),
            "enable_create_table": target_conn.get("enable_create_table", False),
            "table_whitelist": target_conn.get("table_whitelist", []),
            "table_blacklist": target_conn.get("table_blacklist", []),
            "max_query_rows": target_conn.get("max_query_rows", 1000),
            "max_update_rows": target_conn.get("max_update_rows", 100),
            "pool_size": target_conn.get("pool_size", 3)
        }
    })


@app.route("/api/connections/<connection_name>", methods=["DELETE"])
@login_required
async def api_delete_connection(connection_name):
    """删除连接配置"""
    try:
        config_manager = ConfigManager(_data_dir)
        connections = config_manager.load_connections()
        
        # 查找要删除的连接
        found = False
        for i, conn in enumerate(connections):
            if conn.get("name") == connection_name:
                connections.pop(i)
                found = True
                break
        
        if not found:
            return jsonify({"success": False, "error": f"未找到连接: {connection_name}"}), 404
        
        # 保存配置
        config_manager.save_connections(connections)
        logger.info(f"✅ 已删除连接: {connection_name}")
        
        return jsonify({
            "success": True,
            "message": f"✅ 连接已删除！\n\n🚀 新配置将在下次加载配置文件时生效，请手动重载本插件。"
        })
    except Exception as e:
        logger.error(f"删除连接失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/connections/<connection_name>/disable", methods=["POST"])
@login_required
async def api_disable_connection(connection_name):
    """禁用连接配置"""
    try:
        config_manager = ConfigManager(_data_dir)
        connections = config_manager.load_connections()
        
        # 查找要禁用的连接
        found = False
        for conn in connections:
            if conn.get("name") == connection_name:
                conn["enabled"] = False
                found = True
                break
        
        if not found:
            return jsonify({"success": False, "error": f"未找到连接: {connection_name}"}), 404
        
        # 保存配置
        config_manager.save_connections(connections)
        logger.info(f"✅ 已禁用连接: {connection_name}")
        
        return jsonify({
            "success": True,
            "message": f"✅ 连接已禁用！\n\n🚀 新配置将在下次加载配置文件时生效，请手动重载本插件。"
        })
    except Exception as e:
        logger.error(f"禁用连接失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/connections/<connection_name>/enable", methods=["POST"])
@login_required
async def api_enable_connection(connection_name):
    """启用连接配置"""
    try:
        config_manager = ConfigManager(_data_dir)
        connections = config_manager.load_connections()
        
        # 查找要启用的连接
        found = False
        for conn in connections:
            if conn.get("name") == connection_name:
                conn["enabled"] = True
                found = True
                break
        
        if not found:
            return jsonify({"success": False, "error": f"未找到连接: {connection_name}"}), 404
        
        # 保存配置
        config_manager.save_connections(connections)
        logger.info(f"✅ 已启用连接: {connection_name}")
        
        return jsonify({
            "success": True,
            "message": f"✅ 连接已启用！\n\n🚀 新配置将在下次加载配置文件时生效，请手动重载本插件。"
        })
    except Exception as e:
        logger.error(f"启用连接失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/connections/<connection_name>", methods=["PUT"])
@login_required
async def api_update_connection(connection_name):
    """更新指定连接的配置"""
    try:
        data = await request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "无效的请求数据"
            }), 400
        
        # 直接从配置文件读取
        config_manager = ConfigManager(_data_dir)
        connections = config_manager.load_connections()
        
        # 如果配置文件为空，使用全局配置作为初始状态
        if not connections:
            connections = _config.get("connections", [])
            if isinstance(connections, str):
                if "|||" in connections:
                    from .backend.connection_pool import ConnectionPoolManager
                    temp_manager = ConnectionPoolManager(_config)
                    connections = temp_manager.connections_config
                else:
                    try:
                        connections = json.loads(connections)
                    except:
                        connections = []
        
        if not isinstance(connections, list):
            connections = []
        
        # 查找并更新指定连接，或创建新连接
        updated = False
        for i, conn in enumerate(connections):
            if conn.get("name") == connection_name:
                # 获取新密码，如果为空则保持原密码
                new_password = data.get("password", "").strip()
                if not new_password:
                    # 密码为空，保持原密码
                    new_password = conn.get("password", "")
                
                # 更新连接信息（name不允许修改，使用URL中的connection_name）
                connections[i] = {
                    "name": connection_name,  # 强制使用URL中的名称，不允许修改
                    "host": data.get("host", "localhost"),
                    "port": int(data.get("port", 3306)),
                    "database": data.get("database", ""),
                    "username": data.get("username", ""),
                    "password": new_password,
                    "charset": data.get("charset", "utf8mb4"),
                    "enable_insert": bool(data.get("enable_insert", False)),
                    "enable_update": bool(data.get("enable_update", False)),
                    "enable_delete": bool(data.get("enable_delete", False)),
                    "enable_create_table": bool(data.get("enable_create_table", False)),
                    "table_whitelist": data.get("table_whitelist", []),
                    "table_blacklist": data.get("table_blacklist", []),
                    "max_query_rows": int(data.get("max_query_rows", 1000)),
                    "max_update_rows": int(data.get("max_update_rows", 100)),
                    "pool_size": int(data.get("pool_size", 3))
                }
                updated = True
                logger.info(f"更新连接: {connection_name}")
                break
        
        # 如果连接不存在，创建新连接
        if not updated:
            # 新建连接时密码必须提供
            new_password = data.get("password", "").strip()
            if not new_password:
                return jsonify({
                    "success": False,
                    "error": "新建连接时密码不能为空"
                }), 400
            
            # 创建新连接配置（name使用URL中的connection_name）
            new_connection = {
                "name": connection_name,
                "host": data.get("host", "localhost"),
                "port": int(data.get("port", 3306)),
                "database": data.get("database", ""),
                "username": data.get("username", ""),
                "password": new_password,
                "charset": data.get("charset", "utf8mb4"),
                "enable_insert": bool(data.get("enable_insert", True)),
                "enable_update": bool(data.get("enable_update", False)),
                "enable_delete": bool(data.get("enable_delete", False)),
                "enable_create_table": bool(data.get("enable_create_table", False)),
                "table_whitelist": data.get("table_whitelist", []),
                "table_blacklist": data.get("table_blacklist", []),
                "max_query_rows": int(data.get("max_query_rows", 1000)),
                "max_update_rows": int(data.get("max_update_rows", 100)),
                "pool_size": int(data.get("pool_size", 3))
            }
            connections.append(new_connection)
            logger.info(f"创建新连接: {connection_name}")
        
        # 直接保存整个连接数组（简化逻辑）
        try:
            config_manager = ConfigManager(_data_dir)
            config_manager.save_connections(connections)
            logger.info(f"✅ 连接配置已保存: {connection_name}")
            
        except Exception as save_error:
            logger.error(f"保存配置文件失败: {save_error}")
            return jsonify({
                "success": False,
                "error": f"配置已更新但保存失败: {str(save_error)}"
            }), 500
        
        # 构建返回消息（配置会在下次查询时自动生效）
        action = "连接配置已更新" if updated else "新连接已创建"
        message = f"✅ {action}！\n\n🚀 新配置将在下次加载配置文件时生效，请手动重载本插件。"
        
        return jsonify({
            "success": True,
            "message": message
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/tables/<connection_name>")
@login_required
async def api_tables(connection_name):
    """获取指定连接的所有表"""
    global _pool_manager
    try:
        print(f"[DEBUG] 尝试获取连接 '{connection_name}' 的表列表")
        print(f"[DEBUG] _pool_manager 状态: {_pool_manager is not None}")
        
        if not _pool_manager:
            error_msg = "数据库连接管理器未初始化"
            print(f"[ERROR] {error_msg}")
            return jsonify({
                "success": False,
                "error": error_msg
            }), 500

        # 检查连接池中是否有该连接
        if hasattr(_pool_manager, 'pools'):
            print(f"[DEBUG] 连接池中的连接: {list(_pool_manager.pools.keys())}")
        
        tables = await _pool_manager.get_tables(connection_name)
        print(f"[DEBUG] 成功获取 {len(tables)} 个表")
        
        return jsonify({
            "success": True,
            "tables": tables,
            "connection": connection_name
        })
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[ERROR] 获取表列表失败: {str(e)}")
        print(f"[ERROR] 详细错误:\n{error_detail}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/table_schema/<connection_name>/<table_name>")
@login_required
async def api_table_schema(connection_name, table_name):
    """获取表结构"""
    global _pool_manager
    try:
        print(f"[DEBUG] 尝试获取表结构: {connection_name}.{table_name}")
        
        if not _pool_manager:
            error_msg = "数据库连接管理器未初始化"
            print(f"[ERROR] {error_msg}")
            return jsonify({
                "success": False,
                "error": error_msg
            }), 500

        schema = await _pool_manager.get_table_schema(connection_name, table_name)
        print(f"[DEBUG] 成功获取表结构，字段数: {len(schema)}")
        
        return jsonify({
            "success": True,
            "schema": schema,
            "table": table_name,
            "connection": connection_name
        })
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[ERROR] 获取表结构失败: {str(e)}")
        print(f"[ERROR] 详细错误:\n{error_detail}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/table_data/<connection_name>/<table_name>")
@login_required
async def api_table_data(connection_name, table_name):
    """获取表数据"""
    global _pool_manager
    try:
        # 获取查询参数
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
        
        print(f"[DEBUG] 尝试获取表数据: {connection_name}.{table_name} (limit={limit}, offset={offset})")
        
        if not _pool_manager:
            error_msg = "数据库连接管理器未初始化"
            print(f"[ERROR] {error_msg}")
            return jsonify({
                "success": False,
                "error": error_msg
            }), 500

        # 获取表结构（用于显示列名）
        schema = await _pool_manager.get_table_schema(connection_name, table_name)
        columns = [field["Field"] for field in schema]
        
        # 执行查询获取数据
        sql = f"SELECT * FROM `{table_name}` LIMIT {limit} OFFSET {offset}"
        pool = _pool_manager._get_pool(connection_name)
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql)
                rows = await cursor.fetchall()
        
        # 处理特殊类型（DictCursor已经返回字典）
        data = []
        for row in rows:
            row_dict = {}
            for col in columns:
                value = row.get(col)
                # 处理特殊类型
                if value is None:
                    row_dict[col] = None
                elif isinstance(value, (bytes, bytearray)):
                    row_dict[col] = value.decode('utf-8', errors='replace')
                else:
                    row_dict[col] = str(value)
            data.append(row_dict)
        
        print(f"[DEBUG] 成功获取 {len(data)} 行数据")
        
        return jsonify({
            "success": True,
            "data": data,
            "columns": columns,
            "table": table_name,
            "connection": connection_name,
            "count": len(data)
        })
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[ERROR] 获取表数据失败: {str(e)}")
        print(f"[ERROR] 详细错误:\n{error_detail}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/connections/<connection_name>/tables")
@login_required
async def api_get_connection_tables(connection_name):
    """获取指定连接的所有表"""
    try:
        if not _pool_manager:
            return jsonify({
                "success": False,
                "error": "数据库连接未初始化"
            }), 500
        
        # 执行SHOW TABLES查询
        result = await _pool_manager.execute(
            "SHOW TABLES",
            connection_name=connection_name
        )
        
        # 提取表名（结果是列表套字典）
        tables = [list(row.values())[0] for row in result]
        
        return jsonify({
            "success": True,
            "tables": tables
        })
    except Exception as e:
        logger.error(f"获取表列表失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/audit_logs")
@login_required
async def api_audit_logs():
    """获取审计日志"""
    audit_db = Path(_data_dir) / "audit_logs.db"
    logger = AuditLogger(str(audit_db))

    # 获取查询参数
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))
    operation = request.args.get("operation")
    user_id = request.args.get("user_id")

    logs = logger.get_logs(
        limit=limit,
        offset=offset,
        operation=operation,
        user_id=user_id
    )

    return jsonify({
        "success": True,
        "logs": logs,
        "total": len(logs)
    })


@app.route("/api/statistics")
@login_required
async def api_statistics():
    """获取统计信息"""
    audit_db = Path(_data_dir) / "audit_logs.db"
    logger = AuditLogger(str(audit_db))

    stats = logger.get_statistics()

    return jsonify({
        "success": True,
        "statistics": stats
    })


@app.route("/api/audit_logs/clear", methods=["POST"])
@login_required
async def api_clear_audit_logs():
    """清理审计日志"""
    try:
        data = await request.get_json() if request.is_json else {}
        older_than_days = data.get("older_than_days") if data else None
        
        audit_db = Path(_data_dir) / "audit_logs.db"
        audit_logger = AuditLogger(str(audit_db))
        
        # 在后台线程执行同步操作，避免阻塞
        import asyncio
        deleted_count = await asyncio.to_thread(audit_logger.clear_logs, older_than_days)
        
        message = f"已清理 {deleted_count} 条审计日志"
        if older_than_days:
            message += f"（{older_than_days}天前）"
        
        logger.info(f"✅ {message}")
        
        return jsonify({
            "success": True,
            "message": message,
            "deleted_count": deleted_count
        })
    except Exception as e:
        logger.error(f"清理审计日志失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/execute_query", methods=["POST"])
@login_required
async def api_execute_query():
    """执行查询测试"""
    global _query_executor
    try:
        if not _query_executor:
            return jsonify({
                "success": False,
                "error": "查询执行器未初始化"
            }), 500

        data = await request.get_json()
        sql = data.get("sql", "").strip()
        connection_name = data.get("connection")

        if not sql:
            return jsonify({
                "success": False,
                "error": "SQL语句不能为空"
            }), 400

        # 执行查询
        success, result = await _query_executor.execute_query(
            sql=sql,
            connection_name=connection_name,
            user_id="webui_admin",
            platform="webui"
        )

        return jsonify({
            "success": success,
            "result": result
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/config", methods=["GET", "PUT"])
@login_required
async def api_config():
    """获取或更新配置"""
    if request.method == "GET":
        # 返回配置（隐藏敏感信息）
        safe_config = _config.copy()
        safe_config["webui_password"] = "******"

        connections = safe_config.get("connections", [])
        if isinstance(connections, str):
            connections = json.loads(connections)

        for conn in connections:
            if "password" in conn:
                conn["password"] = "******"

        safe_config["connections"] = connections

        return jsonify({
            "success": True,
            "config": safe_config
        })

    else:  # PUT
        # TODO: 实现配置更新
        return jsonify({
            "success": False,
            "message": "配置更新功能待实现"
        })


# ==================== 启动函数 ====================

async def start_server(config: dict, data_dir: str, pool_manager=None, permission_manager=None, query_executor=None, audit_logger=None):
    """
    启动WebUI服务器
    
    Args:
        config: 插件配置
        data_dir: 数据目录路径
        pool_manager: 连接池管理器
        permission_manager: 权限管理器
        query_executor: 查询执行器
        audit_logger: 审计日志记录器
    """
    global _config, _data_dir, _pool_manager, _permission_manager, _query_executor, _audit_logger
    _config = config
    _data_dir = data_dir
    _pool_manager = pool_manager
    _permission_manager = permission_manager
    _query_executor = query_executor
    _audit_logger = audit_logger

    port = config.get("webui_port", 6200)

    # 配置Hypercorn
    hypercorn_config = Config()
    hypercorn_config.bind = [f"0.0.0.0:{port}"]
    hypercorn_config.use_reloader = False

    print(f"🌐 WebUI服务器启动在端口 {port}")
    print(f"📂 访问地址: http://localhost:{port}")

    # 启动服务器
    await hypercorn.asyncio.serve(app, hypercorn_config)


if __name__ == "__main__":
    import asyncio

    # 测试配置
    test_config = {
        "webui_port": 6200,
        "webui_username": "admin",
        "webui_password": "admin123",
        "connections": "[]",
        "default_connection": "default",
        "enable_audit_log": True
    }

    asyncio.run(start_server(test_config, "./data"))

