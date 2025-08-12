import sys
import os
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtCore import QFile, QIODevice
import tempfile

# 常见缺失字符映射表
MISSING_CHAR_MAP = {
    "\N{CJK UNIFIED IDEOGRAPH-51C0}": "?",  # 丼
}


def safe_text(text):
    """
    替换文本中可能缺失的字符

    :param text: 原始文本
    :return: 安全处理后的文本
    """
    for char, replacement in MISSING_CHAR_MAP.items():
        text = text.replace(char, replacement)
    return text


def get_font_path(font_file):
    """
    获取字体文件路径

    :param font_file: 字体文件名
    :return: 字体文件完整路径
    """
    try:
        # 优先检查文件系统中的字体目录
        font_dir = os.path.join(os.path.dirname(__file__), "..", "fonts")
        font_path = os.path.join(font_dir, font_file)

        if os.path.exists(font_path):
            return font_path

        # 检查资源文件（如果打包）
        resource_path = f":/fonts/{font_file}"
        if QFile.exists(resource_path):
            # 提取到临时文件
            temp_dir = tempfile.gettempdir()
            temp_font_path = os.path.join(temp_dir, font_file)

            if not os.path.exists(temp_font_path):
                # 从资源复制到临时文件
                resource_file = QFile(resource_path)
                if resource_file.open(QIODevice.ReadOnly):
                    data = resource_file.readAll()
                    resource_file.close()

                    with open(temp_font_path, 'wb') as f:
                        f.write(data)

            return temp_font_path

        return None
    except Exception as e:
        print(f"获取字体路径失败: {str(e)}")
        return None


def load_embedded_fonts():
    """加载嵌入式字体到字体数据库"""
    try:
        font_files = [
            "SourceHanSansSC-Regular.ttf",
            "SourceHanSansSC-Bold.ttf",
            "SourceHanSerifSC-Regular.ttf"
        ]

        loaded_fonts = []

        for font_file in font_files:
            font_path = get_font_path(font_file)

            if font_path and os.path.exists(font_path):
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id != -1:
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    loaded_fonts.extend(families)
                    print(f"成功加载字体: {font_file} -> {', '.join(families)}")
                else:
                    print(f"警告: 无法加载字体 {font_file} ({font_path})")

        return loaded_fonts
    except Exception as e:
        print(f"加载嵌入式字体失败: {str(e)}")
        return []


def get_common_font(is_monospace=False, size=10):
    """
    获取通用字体设置

    :param is_monospace: 是否用于等宽显示（如日志）
    :param size: 字体大小
    :return: QFont 对象
    """
    # 创建字体对象
    font = QFont()

    # 设置首选字体
    if is_monospace:
        # 等宽字体组合（包含中文字体）
        if sys.platform == "win32":
            font_families = ["Consolas", "Courier New", "Source Han Sans SC"]
        elif sys.platform == "darwin":
            font_families = ["Menlo", "Monaco", "Source Han Sans SC"]
        else:
            font_families = ["DejaVu Sans Mono", "Source Han Sans SC"]
    else:
        # 界面通用字体
        font_families = ["Source Han Sans SC", "Microsoft YaHei UI", "PingFang SC", "WenQuanYi Micro Hei"]

    # 设置字体回退链
    font.setFamilies(font_families)
    font.setPointSize(size)

    # 设置字体渲染策略
    font.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality)

    return font


# 测试函数
if __name__ == "__main__":
    # 测试安全文本处理
    test_text = "这是一个测试文本，包含丼(51C0)、值(503C)、曲(66F2)、线(7EBF)、日(65E5)、期(671F)等字符"
    safe_text_result = safe_text(test_text)
    print(f"原始文本: {test_text}")
    print(f"安全文本: {safe_text_result}")

    # 测试字体加载
    print("\n加载嵌入式字体:")
    loaded = load_embedded_fonts()
    print(f"已加载字体: {', '.join(loaded)}")

    # 测试获取字体
    print("\n获取通用字体:")
    font = get_common_font()
    print(f"字体家族: {font.families()}, 大小: {font.pointSize()}pt")

    print("\n获取等宽字体:")
    mono_font = get_common_font(is_monospace=True)
    print(f"等宽字体家族: {mono_font.families()}, 大小: {mono_font.pointSize()}pt")