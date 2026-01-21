"""
密码哈希工具
使用MD5 16位小写（取32位MD5的中间16位）
"""
import hashlib


def hash_password(password: str) -> str:
    """
    将密码哈希为MD5 16位小写
    
    Args:
        password: 明文密码
        
    Returns:
        str: 16位小写MD5哈希值（32位MD5的中间16位）
    """
    if not password:
        return ""

    md5_full = hashlib.md5(password.encode("utf-8")).hexdigest()
    return md5_full[8:24]  # 取中间16位


def verify_password(password: str, password_hash: str) -> bool:
    """
    验证密码是否匹配
    
    Args:
        password: 用户输入的明文密码
        password_hash: 存储的哈希值
        
    Returns:
        bool: 是否匹配
    """
    return hash_password(password) == password_hash


# 示例和测试
if __name__ == "__main__":
    # 测试密码哈希
    test_passwords = [
        "admin123",
        "password",
        "MyS3cur3P@ssw0rd"
    ]

    print("密码哈希测试:")
    print("-" * 50)
    for pwd in test_passwords:
        hashed = hash_password(pwd)
        print(f"明文: {pwd:20s} -> MD5(16): {hashed}")

        # 验证
        is_valid = verify_password(pwd, hashed)
        print(f"  验证结果: {'✅ 通过' if is_valid else '❌ 失败'}")

    print("\n" + "=" * 50)
    print("示例: admin123 的MD5 16位哈希为:", hash_password("admin123"))
