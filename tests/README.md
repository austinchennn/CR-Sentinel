# 覆盖率补充测试

这个目录不重复各服务 `services/<name>/tests/` 里已有的用例，只补写让每个服务
达到 100% 语句覆盖率所缺的分支：`connect()`/`main()` 这类需要真实驱动
（`psycopg2`/`boto3`/`mcp`）的入口、`if __name__ == "__main__"` 守卫、
懒加载 `import boto3`/`import mcp` 分支、`from_env()` 的环境变量读取、
以及各种错误/边界分支。三个子目录一一对应 `services/` 下的三个服务。

## 怎么跑

每个子目录都是独立的 pytest root（有自己的 `pytest.ini` 和 `conftest.py`，
`conftest.py` 会把对应的 `services/<name>` 目录插进 `sys.path`）。跟每个服务
自己的 `services/<name>/tests` 一样，**独立运行**：

```bash
cd tests/crdb-schema      && python3 -m pytest -q
cd tests/demo-target-app  && python3 -m pytest -q
cd tests/patrol-agent     && python3 -m pytest -q
```

## 为什么不建议 `pytest services tests` 一把梭

`services/*/tests/` 和 `tests/*/` 里都有各自的 `conftest.py`，其中一部分测试
文件用的是 `from conftest import xxx` 这种写法（而不是 pytest fixture）。当
同一个 pytest 进程里同时收集多个同名 `conftest.py` 所在的目录时，Python 的
`sys.modules` 只会缓存其中一个 `conftest` 模块，`from conftest import xxx`
可能拿到别的目录的 `conftest.py`，导致原本能跑的用例报
`ImportError`/`AttributeError`，且结果依赖收集顺序，不稳定。这是三个服务原有
测试套件本身的写法决定的（不是这次新加的问题），所以这次新增的测试没有去改
原有测试文件的导入方式，而是保持"每个目录独立运行"这个已经在用的约定
（每个服务的 `pytest.ini` 也是把 `testpaths` 限定在自己目录下）。

## 验证 100% 覆盖率的方法

覆盖率数字是"原有测试 + 这个目录"两次独立进程各自跑、共享同一份
`.coverage` 文件累加出来的，不是一次性跑出来的:

```bash
COVERAGE_FILE=/tmp/.cov.demo python3 -m pytest -q --cov=demo_target_app --cov-append --cov-report=          # 在 services/demo-target-app/ 下跑
COVERAGE_FILE=/tmp/.cov.demo python3 -m pytest -q --cov=demo_target_app --cov-append --cov-report=term-missing  # 在 tests/demo-target-app/ 下跑
```

三个服务（`crdb_schema`/`demo_target_app`/`patrol_agent`）用这种方式验证过，
均为 **100% 语句覆盖率**（合计 610 行、0 未覆盖）。
