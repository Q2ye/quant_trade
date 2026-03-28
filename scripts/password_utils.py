#!/usr/bin/env python3
"""
密码加解密工具脚本
提供密码加密（生成哈希）和验证（比对哈希）功能
"""

import bcrypt

# 硬编码的测试数据
TEST_PASSWORD = "111111.a"
TEST_BASE64 = "MTExMTExLmE="
#!/usr/bin/env python3
"""
密码工具 - base64 加解密（仅作演示，非安全用途）
提供 base64 编码（加密）和解码（解密）方法
"""

import base64

def encrypt_password(password: str) -> str:
    """
    base64 编码密码（模拟加密），输入为空时返回空字符串。
    Args:
        password: 明文密码
    Returns:
        base64 编码字符串，若输入为空则返回空字符串。
    """
    if not password:
        return ""
    encoded_bytes = base64.b64encode(password.encode('utf-8'))
    return encoded_bytes.decode('utf-8')

def decrypt_password(encoded: str) -> str:
    """
    base64 解码密码（模拟解密），输入为空时返回空字符串。
    Args:
        encoded: base64 编码字符串
    Returns:
        原始明文密码，若输入为空则返回空字符串。
    """
    if not encoded:
        return ""
    decoded_bytes = base64.b64decode(encoded.encode('utf-8'))
    return decoded_bytes.decode('utf-8')

def main():
    """主函数：演示加密、验证和哈希解析"""
    print("密码工具 - 加解密演示")
    print("=" * 60)
    # 1. 加密测试密码
    print("\n【加密】")
    new_hash = encrypt_password(TEST_PASSWORD)
    if new_hash:
        print(f"密文: {new_hash}")
    else:
        print("加密失败")

    print("\n【解密】")
    new_hash = decrypt_password(TEST_BASE64)
    if new_hash:
        print(f"明文: {new_hash}")
    else:
        print("解密失败")


if __name__ == "__main__":
    main()