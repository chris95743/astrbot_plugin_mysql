"""
配置管理模块
负责连接配置的持久化存储
"""
import json
from pathlib import Path
from typing import List, Dict, Any


class ConfigManager:
    """配置管理器 - 管理数据库连接配置的持久化"""
    
    def __init__(self, data_dir: str):
        """
        初始化配置管理器
        
        Args:
            data_dir: 数据目录路径
        """
        self.data_dir = Path(data_dir)
        self.config_file = self.data_dir / "connections_override.json"
        
        # 确保目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def load_connections(self) -> List[Dict[str, Any]]:
        """
        从配置文件加载连接配置
        
        Returns:
            连接配置列表，如果文件不存在则返回空列表
        """
        if not self.config_file.exists():
            return []
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                connections = json.load(f)
                # 兼容旧格式（嵌套对象）和新格式（直接数组）
                if isinstance(connections, dict):
                    return connections.get("connections", [])
                elif isinstance(connections, list):
                    return connections
                return []
        except Exception as e:
            print(f"警告: 加载配置文件失败: {e}")
            return []
    
    def save_connections(self, connections: List[Dict[str, Any]]) -> bool:
        """
        保存连接配置到文件（直接保存数组格式）
        
        Args:
            connections: 连接配置列表
            
        Returns:
            是否保存成功
        """
        try:
            # 直接保存数组格式，与ConnectionPoolManager.reload_config_if_changed()一致
            temp_file = self.config_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(connections, f, ensure_ascii=False, indent=2)
            
            # 替换原文件
            temp_file.replace(self.config_file)
            return True
            
        except Exception as e:
            print(f"错误: 保存配置文件失败: {e}")
            return False
    
    def update_connection(self, connection_name: str, updated_data: Dict[str, Any]) -> bool:
        """
        更新指定连接的配置
        
        Args:
            connection_name: 连接名称
            updated_data: 更新的数据
            
        Returns:
            是否更新成功
        """
        connections = self.load_connections()
        
        # 查找并更新
        found = False
        for i, conn in enumerate(connections):
            if conn.get("name") == connection_name:
                connections[i] = updated_data
                found = True
                break
        
        if not found:
            return False
        
        return self.save_connections(connections)
    
    def get_connection(self, connection_name: str) -> Dict[str, Any] | None:
        """
        获取指定连接的配置
        
        Args:
            connection_name: 连接名称
            
        Returns:
            连接配置字典，不存在则返回None
        """
        connections = self.load_connections()
        
        for conn in connections:
            if conn.get("name") == connection_name:
                return conn
        
        return None
    
    def has_overrides(self) -> bool:
        """
        检查是否存在配置覆盖文件
        
        Returns:
            是否存在配置文件
        """
        return self.config_file.exists()
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()


def merge_connections(base_connections: List[Dict], override_connections: List[Dict]) -> List[Dict]:
    """
    合并基础配置和覆盖配置
    
    覆盖配置优先级更高，会替换同名的基础配置
    
    Args:
        base_connections: 基础连接配置列表
        override_connections: 覆盖连接配置列表
        
    Returns:
        合并后的连接配置列表
    """
    if not override_connections:
        return base_connections
    
    # 创建基础配置的副本
    merged = base_connections.copy()
    
    # 用覆盖配置替换同名连接
    for override_conn in override_connections:
        override_name = override_conn.get("name")
        if not override_name:
            continue
        
        # 查找同名连接
        replaced = False
        for i, base_conn in enumerate(merged):
            if base_conn.get("name") == override_name:
                merged[i] = override_conn
                replaced = True
                break
        
        # 如果没找到同名连接，添加到末尾
        if not replaced:
            merged.append(override_conn)
    
    return merged
