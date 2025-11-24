# Test Suite - 测试套件

自动化测试框架，用于批量测试动物营养配方场景。

## 目录结构

```
test_suite/
├── README.md                      # 本文件
├── run_test_batch.py              # 测试运行器（主入口）
├── dump_session.py                # 会话数据导出工具
├── extract_test_results.py        # 结果提取工具
├── calculate_test_costs.py        # 成本分析工具
├── test_beef_scenarios.py         # 遗留脚本（已被 run_test_batch.py 替代）
├── scenarios/                     # 测试场景定义
│   ├── beef_scenarios.json        # 肉牛场景配置
│   ├── dog_scenarios.json         # 犬类场景配置（30个场景）
│   └── cat_scenarios.json         # 猫科场景配置（30个场景）
└── test_runs/                     # 测试运行结果（自动生成）
    └── YYYYMMDD_HHMMSS/           # 时间戳目录
        ├── manifest.json          # 测试清单
        ├── session_mapping.json   # 会话映射
        ├── extraction_report.json # 提取报告
        ├── cost_analysis.json     # 成本分析
        └── results/               # 提取的结果
            ├── success/           # 成功场景
            │   └── 场景XX_名称/
            │       ├── session_id_messages.json  # 会话消息
            │       ├── session_id_stats.txt      # Token统计
            │       ├── metadata.json             # 场景元数据
            │       └── *.xlsx                    # 导出的配方文件
            ├── failed/            # 失败场景
            └── formulations/      # 所有配方文件汇总
```

## 工作流程

### 1. 运行测试批次

使用 `run_test_batch.py` 批量提交测试场景：

```bash
# 运行所有肉牛场景
python test_suite/run_test_batch.py beef_cow

# 运行指定场景（例如：场景1、3、5）
python test_suite/run_test_batch.py beef_cow 1 3 5

# 运行其他动物类型
python test_suite/run_test_batch.py dairy_cow
python test_suite/run_test_batch.py cat
python test_suite/run_test_batch.py dog
```

> 目前仓库内置三套示例场景：`beef_scenarios.json`（肉牛）、`dog_scenarios.json`（30 个犬类场景）以及 `cat_scenarios.json`（30 个猫科场景）。运行 `python test_suite/run_test_batch.py dog` 或 `python test_suite/run_test_batch.py cat` 会自动加载对应的场景文件。

> 为了覆盖 30 个犬类测试场景，系统默认犬类饲料库（`default_dog`）已经扩展了耐力脂肪强化、低脂肠胃罐头、低铜肝脏配方、泌尿与肾脏专用日粮、排除/昆虫蛋白底料、关节与免疫补充剂等原料，可直接被测试代理调用，无需额外配置。猫科测试集同样共享增强后的系统猫粮饲料库（`default_cat`），其中加入了泌尿、肾脏、低脂、昆虫蛋白、康复与适口性增强等配料，覆盖全部 30 个猫科场景。

**输出：**
- 创建时间戳目录（例如：`test_runs/20251030_143000`）
- 生成 `manifest.json`：记录所有提交的场景和 session_id
- 生成 `session_mapping.json`：场景名称到 session_id 的映射
- 打印测试运行 ID，用于后续提取结果

### 2. 等待代理完成配方

测试提交后，代理会在后台自主完成配方制定。可以：
- 在前端查看实时进度
- 等待所有会话完成（通常需要几分钟到几十分钟）

### 3. 提取测试结果

使用 `extract_test_results.py` 提取完整结果：

```bash
# 使用测试运行 ID（时间戳）
python test_suite/extract_test_results.py 20251030_143000

# 查看可用的测试运行
python test_suite/extract_test_results.py
```

**自动执行：**
1. 从数据库导出会话数据（messages.json）
2. 从 `files/` 目录复制配方文件（Excel）
3. 整理到 `results/` 目录，按场景分类
4. 生成提取报告（`extraction_report.json`）
5. 计算成本分析（`cost_analysis.json`）

### 4. 查看成本分析

成本分析会自动生成在 `test_runs/<timestamp>/cost_analysis.json`：

```json
{
  "pricing": {
    "input_price_per_1m": 1.0,
    "output_price_per_1m": 5.0,
    "model": "claude-haiku-4.5"
  },
  "summary": {
    "total_scenarios": 30,
    "total_input_tokens": 10027278,
    "total_output_tokens": 395749,
    "total_tokens": 10423027,
    "total_cost": 12.006,
    "average_cost_per_scenario": 0.4002,
    "average_tokens_per_scenario": 347434
  },
  "scenarios": [...]
}
```

## 工具详解

### run_test_batch.py

**功能：**
- 批量创建测试会话
- 并发提交所有场景
- 记录 session_id 和场景元数据
- 生成测试清单

**参数：**
```bash
python test_suite/run_test_batch.py [animal_type] [scenario_ids...]

# animal_type: beef_cow (默认), dairy_cow, cat, dog
# scenario_ids: 可选，只运行指定场景编号
```

**输出文件：**
- `manifest.json`：完整测试清单
- `session_mapping.json`：快速查找映射

---

### dump_session.py

**功能：**
- 从数据库导出会话数据
- 可单独使用或被 extract_test_results.py 调用

**用法：**
```bash
# 导出单个会话到当前目录
python test_suite/dump_session.py <session_id>

# 导出到指定目录
python test_suite/dump_session.py <session_id> ./output_dir
```

**输出文件：**
- `<session_id>_messages.json`：完整消息历史
- `<session_id>_stats.txt`：Token使用统计

---

### extract_test_results.py

**功能：**
- 提取完整测试结果
- 整理配方文件
- 生成报告和成本分析

**用法：**
```bash
python test_suite/extract_test_results.py <timestamp>
```

**输出：**
- `results/success/`：成功场景的完整数据
- `results/formulations/`：所有配方文件汇总
- `extraction_report.json`：提取详情
- `cost_analysis.json`：成本统计

---

### calculate_test_costs.py

**功能：**
- 分析现有测试用例的成本
- 用于历史数据分析

**用法：**
```bash
python test_suite/calculate_test_costs.py
```

**输出：**
- 终端打印成本汇总
- `test_cost_analysis.json`：详细成本数据

## 场景配置

### 创建新场景文件

在 `scenarios/` 目录创建 JSON 文件：

```json
[
  {
    "id": 1,
    "name": "场景名称",
    "prompt": "完整的场景描述和配方要求..."
  },
  {
    "id": 2,
    "name": "另一个场景",
    "prompt": "..."
  }
]
```

### 使用自定义场景

修改 `run_test_batch.py` 中的 `TEST_SCENARIOS_FILE` 变量，或在代码中指定：

```python
await main(
    scenarios_file=Path("scenarios/custom_scenarios.json"),
    animal_type="beef_cow"
)
```

## 配置说明

### 测试账号

在 `run_test_batch.py` 中配置：

```python
TEST_EMAIL = "test@wuitu.com"
TEST_PASSWORD = "testacc"
API_BASE_URL = "http://localhost:8000"
```

### 定价配置

在 `calculate_test_costs.py` 中配置模型定价：

```python
HAIKU_4_5_INPUT_PRICE = 1.00   # $1.00 per 1M input tokens
HAIKU_4_5_OUTPUT_PRICE = 5.00  # $5.00 per 1M output tokens
```

## 示例工作流

### 完整测试流程

```bash
# 1. 运行测试（所有场景）
python test_suite/run_test_batch.py beef_cow

# 输出示例：
# ================================================================================
# 测试运行 ID: 20251030_143000
# 结果目录: /path/to/test_runs/20251030_143000
# ================================================================================
# 请使用以下命令提取结果:
#   python test_suite/extract_test_results.py 20251030_143000

# 2. 等待代理完成（可在前端监控进度）

# 3. 提取结果
python test_suite/extract_test_results.py 20251030_143000

# 4. 查看成本分析
cat test_suite/test_runs/20251030_143000/cost_analysis.json
```

### 测试特定场景

```bash
# 只测试场景 1、3、5
python test_suite/run_test_batch.py beef_cow 1 3 5

# 提取结果
python test_suite/extract_test_results.py 20251030_150000
```

### 单独导出某个会话

```bash
# 如果已知 session_id
python test_suite/dump_session.py 5c65b644-e527-4c2d-ad53-30d623f9728a ./output

# 查看 session_mapping.json 获取 session_id
cat test_suite/test_runs/20251030_143000/session_mapping.json
```

## 故障排查

### 问题：提取时找不到配方文件

**可能原因：**
- 代理尚未完成配方制定
- 配方生成失败

**解决方案：**
1. 在前端查看会话状态
2. 检查会话是否有错误消息
3. 等待足够时间后重新提取

### 问题：会话创建失败

**可能原因：**
- 后端服务未启动
- 测试账号不存在或密码错误
- 数据库连接失败

**解决方案：**
1. 确认后端服务运行：`http://localhost:8000`
2. 检查测试账号凭据
3. 查看后端日志

### 问题：成本分析结果为 0

**可能原因：**
- 消息中缺少 `usage_metadata` 字段
- 提取未完成

**解决方案：**
1. 确认提取成功（有 `*_messages.json` 文件）
2. 检查 messages.json 中是否有 token 统计
3. 重新运行提取脚本

## 最佳实践

### 1. 命名规范

- 测试运行使用时间戳：`YYYYMMDD_HHMMSS`
- 场景目录：`场景XX_描述性名称`
- 配方文件：`场景XX_原始文件名.xlsx`

### 2. 版本控制

- 将 `scenarios/` 目录纳入版本控制
- **不要**提交 `test_runs/` 目录（太大）
- 提交重要的分析报告（`cost_analysis.json`）

### 3. 成本优化

- 只运行必要的场景
- 使用 scenario_ids 参数限制测试范围
- 定期审查成本分析，优化高成本场景

### 4. 数据管理

- 定期清理旧的测试运行
- 保留重要基准测试的结果
- 备份关键的配方文件

## 依赖要求

```python
# 已包含在 backend 依赖中
httpx          # HTTP 客户端
asyncio        # 异步支持
langchain      # 消息处理
psycopg        # PostgreSQL 连接
```

## 进阶用法

### 自定义成本计算

修改 `calculate_test_costs.py` 添加不同模型的定价：

```python
PRICING = {
    "haiku-4.5": {"input": 1.00, "output": 5.00},
    "sonnet-4": {"input": 3.00, "output": 15.00},
    "opus-4": {"input": 15.00, "output": 75.00},
}
```

### 并行测试多个动物类型

```bash
# 使用 GNU parallel 或编写脚本
python test_suite/run_test_batch.py beef_cow &
python test_suite/run_test_batch.py dairy_cow &
python test_suite/run_test_batch.py cat &
python test_suite/run_test_batch.py dog &
wait
```

### 自动化提取

使用 cron 或脚本定时提取结果：

```bash
#!/bin/bash
# auto_extract.sh

TIMESTAMP=$1
WAIT_TIME=3600  # 等待 1 小时

echo "等待 ${WAIT_TIME} 秒后提取结果..."
sleep $WAIT_TIME

python test_suite/extract_test_results.py $TIMESTAMP
```

## 更新日志

### 2025-10-30
- ✨ 创建 test_suite 模块
- ✨ 添加时间戳测试运行支持
- ✨ 添加自动结果提取
- ✨ 添加成本分析集成
- ♻️  重构测试脚本结构

## 许可证

本测试套件是 Ration Agent 项目的一部分。

## 支持

如有问题或建议，请联系项目维护者。
