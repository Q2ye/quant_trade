# test_registry_satellite.py
"""
卫星策略注册回归测试 — 恐慌抄底 / 微盘

背景（2026-08 阶段 4b/4c）：两个卫星策略文件位于
  modules/strategy/strategies/panic/
  modules/strategy/strategies/microcap/
但 StrategyRegistry.auto_discover() 的 subpackage_type_map 曾缺这两个子包，
导致策略从未注册、seed_builtin_templates() 无法同步到 strategy_templates 表。

本测试验证：
  1. auto_discover() 能发现 PanicBottomStrategy / MicrocapStrategy（type=custom）
  2. seed_builtin_templates() 的源码 + DEFAULT_PARAMS 提取逻辑对两者可行
     （复刻 template_service.seed_builtin_templates 的提取段，不连 DB）
"""

import inspect

import pytest


@pytest.fixture(scope="module")
def registry():
    """单例注册表：清空 → auto_discover → yield → 清空（避免污染其他测试）。"""
    # 延迟导入：避免顶层 import 触发 modules.strategy → modules.data 依赖链
    from modules.strategy.engines.strategy_registry import StrategyRegistry

    reg = StrategyRegistry()
    reg.clear()
    reg.auto_discover()
    yield reg
    reg.clear()


def _find_entry(registry, class_name: str):
    """按类名在注册表条目中查找。"""
    for entry in registry.list_all():
        if entry.get("class_name") == class_name:
            return entry
    return None


def test_panic_bottom_discovered(registry):
    """恐慌抄底策略应被 auto_discover 扫描注册（type=custom，panic 子包）。"""
    entry = _find_entry(registry, "PanicBottomStrategy")
    assert entry is not None, "PanicBottomStrategy 未注册到 StrategyRegistry"
    assert entry["strategy_type"] == "custom"
    assert entry["module"] == "modules.strategy.strategies.panic.panic_bottom_strategy"


def test_microcap_discovered(registry):
    """微盘策略应被 auto_discover 扫描注册（type=custom，microcap 子包）。"""
    entry = _find_entry(registry, "MicrocapStrategy")
    assert entry is not None, "MicrocapStrategy 未注册到 StrategyRegistry"
    assert entry["strategy_type"] == "custom"
    assert entry["module"] == "modules.strategy.strategies.microcap.microcap_strategy"


@pytest.mark.parametrize(
    "module_path,class_name",
    [
        ("modules.strategy.strategies.panic.panic_bottom_strategy", "PanicBottomStrategy"),
        ("modules.strategy.strategies.microcap.microcap_strategy", "MicrocapStrategy"),
    ],
)
def test_seed_source_and_params_extractable(module_path, class_name):
    """复刻 seed_builtin_templates 提取段，验证两个卫星策略可被 seed 入库。

    template_service.seed_builtin_templates() 提取策略源码（inspect.getsource 整模块）
    与默认参数（DEFAULT_PARAMS fallback），本测试用同一逻辑验证可行，避免连 DB。
    """
    import importlib

    from modules.strategy.strategies.base.base_strategy import BaseStrategy

    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)

    assert issubclass(cls, BaseStrategy), f"{class_name} 必须继承 BaseStrategy"

    # 源码提取（整模块源码，含 import，避免 exec 时 NameError）
    source = None
    for cls_obj in mod.__dict__.values():
        if inspect.isclass(cls_obj) and cls_obj.__name__ == class_name:
            try:
                source = inspect.getsource(inspect.getmodule(cls_obj))
            except (OSError, TypeError):
                source = inspect.getsource(cls_obj)
            break
    assert source, f"{class_name} 无法提取源码"
    assert len(source) > 1000, f"{class_name} 源码过短（{len(source)} 字节），疑似提取失败"

    # 默认参数提取（DEFAULT_PARAMS fallback）
    params = dict(getattr(cls, "DEFAULT_PARAMS", {}))
    assert len(params) > 0, f"{class_name} 无 DEFAULT_PARAMS，seed 将无默认参数"
