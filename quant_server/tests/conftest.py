# 全局测试配置
"""pytest 全局配置与钩子。

## 为什么需要下面的 async 钩子（2026-09-15）

项目里存在两套并存的异步测试写法：
  · `asyncio.run(...)` 包同步用例 —— **可以在无插件环境下真正运行**（7 个文件采用）；
  · `@pytest.mark.asyncio` + `async def test_*` —— **需要 pytest-asyncio 插件**（4 个文件采用）。

而 `pytest-asyncio` **不在依赖中**（`pyproject.toml` 未声明），pytest 9 下这类用例
既不会被执行、也不报明确错误 —— 表现为「测试看起来存在，实际从没跑过」。
`test_event_engine.py`、`test_strategy_manager.py` 等文件的用例即因此长期失败/空转。

本钩子用 **标准库 asyncio** 直接驱动协程用例，零新增依赖，且两种写法都能跑：

## 行为

- 同步用例：不受影响（返回 None，走 pytest 默认路径）；
- `async def` 用例：用 `asyncio.run()` 执行，等价于 pytest-asyncio 的默认（function-scope）模式。

## 注意

- **异步 fixture 不受本钩子覆盖**（pytest-asyncio 对 fixture 的支持需要更深的钩子）。
  异步 fixture 请改为**同步 fixture**（若其体内无 await，直接去掉 async 即可 —— 见
  `tests/modules/test_data/test_services.py` 的 `sync_service`）。
- 若日后真的引入 `pytest-asyncio`，本钩子会自动让位（见下方 `_HAS_PYTEST_ASYNCIO` 判断），
  以免两套机制打架。
"""
import asyncio
import inspect

import pytest

try:  # pragma: no cover - 取决于是否安装插件
    import pytest_asyncio  # noqa: F401

    _HAS_PYTEST_ASYNCIO = True
except ImportError:  # pragma: no cover
    _HAS_PYTEST_ASYNCIO = False


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    """让 `async def` 测试函数在本项目（无 pytest-asyncio）下也能运行。

    Returns:
        True 表示本次调用已被处理（阻止 pytest 默认路径）；None 表示交回 pytest。
    """
    if _HAS_PYTEST_ASYNCIO:
        return None

    testfunc = pyfuncitem.obj
    if not inspect.iscoroutinefunction(testfunc):
        return None

    # 只传该用例真正声明的 fixture（与 pytest 默认行为一致）
    argnames = pyfuncitem._fixtureinfo.argnames
    kwargs = {name: pyfuncitem.funcargs[name] for name in argnames}
    asyncio.run(testfunc(**kwargs))
    return True
