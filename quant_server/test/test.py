import hashlib


def hash_password(password: str) -> str:
    """简单的密码哈希函数"""
    return hashlib.sha256(password.encode()).hexdigest()


def test_hash_password():
    """
    测试密码哈希函数的基本功能
    """
    # 测试用例1: 相同密码应该产生相同哈希值
    password = "123456"
    hash1 = hash_password(password)
    hash2 = hash_password(password)

    print(f"密码: {password}")
    print(f"哈希值1: {hash1}")
    print(f"哈希值2: {hash2}")
    print(f"两次哈希是否相同: {hash1 == hash2}")

    # 测试用例2: 不同密码应该产生不同哈希值
    password2 = "test1234"
    hash3 = hash_password(password2)

    print(f"\n密码: {password2}")
    print(f"哈希值3: {hash3}")
    print(f"不同密码哈希是否不同: {hash1 != hash3}")

    # 测试用例3: 验证哈希长度
    print(f"\n哈希值长度: {len(hash1)} 字符")
    print(f"哈希值是否为十六进制格式: {all(c in '0123456789abcdef' for c in hash1)}")

    # 测试用例4: 测试空字符串
    empty_hash = hash_password("")
    print(f"\n空密码哈希值: {empty_hash}")


if __name__ == "__main__":
    print("=== 密码哈希函数测试 ===")
    test_hash_password()
    print("\n=== 测试完成 ===")
