# 测试指南

本项目使用 pytest 作为测试框架。以下是运行测试的指南。

## 安装依赖

在运行测试之前，请确保已安装所有开发依赖项：

```bash
pip install -r requirements.txt
```

## 运行测试

### 运行所有测试

```bash
pytest
```

### 运行特定测试文件

```bash
pytest tests/integration/test_api_tasks.py
```

### 运行特定测试函数

```bash
pytest tests/unit/test_utils.py::test_safe_get_nested_and_default
```

### 生成覆盖率报告

```bash
coverage run -m pytest
coverage report
coverage html  # 生成 HTML 报告
```

## 测试文件结构

```
tests/
├── __init__.py
├── conftest.py              # 共享 fixtures（API/CLI/样例数据）
├── fixtures/                # 贴近真实的样例数据（搜索/用户/评价/任务配置）
│   ├── config.sample.json
│   ├── ratings.json
│   ├── search_results.json
│   ├── state.sample.json
│   ├── user_head.json
│   └── user_items.json
├── integration/             # 关键链路集成测试（API/CLI/解析器）
│   ├── test_api_tasks.py
│   ├── test_cli_spider.py
│   └── test_pipeline_parse.py
└── unit/                    # 核心纯函数单元测试
    ├── test_domain_task.py
    └── test_utils.py
```

## 编写新测试

1. 新增测试放在 `tests/integration/` 或 `tests/unit/`
2. 文件名以 `test_` 开头，函数名以 `test_` 开头
3. 测试采用同步执行（不依赖 pytest-asyncio）
4. 外部依赖（Playwright/AI/通知/网络）统一 mock
5. 使用 `tests/fixtures/` 的样例数据，避免依赖真实网络

## 注意事项

1. 目标是离线可跑且稳定复现
2. 集成测试优先覆盖真实运行链路（API、CLI、解析器）
3. 如需新增真实场景样例，统一补充到 `tests/fixtures/`
