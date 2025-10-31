# Quick Start Guide - 快速开始

5分钟上手测试套件。

## 🚀 快速开始

### 步骤 1: 启动后端服务

```bash
cd backend
uv run python start_server.py
```

### 步骤 2: 运行测试批次

```bash
# 运行所有肉牛场景
python test_suite/run_test_batch.py beef_cow

# 或运行指定场景（例如：场景1、3、5）
python test_suite/run_test_batch.py beef_cow 1 3 5
```

**输出示例：**
```
================================================================================
测试运行 ID: 20251030_143000
结果目录: .../test_suite/test_runs/20251030_143000
================================================================================
请使用以下命令提取结果:
  python test_suite/extract_test_results.py 20251030_143000
```

### 步骤 3: 等待完成

- 在浏览器打开 `http://localhost:3000`
- 登录后查看会话进度
- 等待所有场景完成配方（通常5-30分钟）

### 步骤 4: 提取结果

```bash
# 使用步骤2输出的时间戳
python test_suite/extract_test_results.py 20251030_143000
```

**自动完成：**
- ✅ 从数据库导出会话数据
- ✅ 复制配方文件
- ✅ 生成成本分析
- ✅ 生成提取报告

### 步骤 5: 查看结果

```bash
# 进入结果目录
cd test_suite/test_runs/20251030_143000

# 查看成本分析
cat cost_analysis.json

# 查看所有配方文件
ls results/formulations/

# 查看某个场景的详细数据
ls results/success/场景01_育肥初期（架子牛）/
```

## 📁 结果文件说明

```
test_runs/20251030_143000/
├── manifest.json              # 测试清单（session_id映射）
├── session_mapping.json       # 快速查找映射
├── extraction_report.json     # 提取报告
├── cost_analysis.json         # 成本分析 ⭐
└── results/
    ├── success/               # 成功场景
    │   └── 场景01_育肥初期（架子牛）/
    │       ├── xxx_messages.json   # 完整对话历史
    │       ├── xxx_stats.txt       # Token统计
    │       ├── metadata.json       # 场景元数据
    │       └── *.xlsx              # 配方文件 ⭐
    └── formulations/          # 所有配方文件汇总 ⭐
```

## 💰 成本分析示例

```json
{
  "summary": {
    "total_scenarios": 30,
    "total_tokens": 10423027,
    "total_cost": 12.0060,
    "average_cost_per_scenario": 0.4002
  }
}
```

## 🔧 常用命令

### 查看可用测试运行
```bash
ls -lt test_suite/test_runs/
```

### 重新提取结果
```bash
# 如果配方完成较晚，可重新提取
python test_suite/extract_test_results.py 20251030_143000
```

### 导出单个会话
```bash
# 获取 session_id
cat test_suite/test_runs/20251030_143000/session_mapping.json

# 导出
python test_suite/dump_session.py <session_id> ./output
```

### 分析历史数据
```bash
# 分析 test_cases 目录中的历史数据
python test_suite/calculate_test_costs.py
```

## ⚠️ 常见问题

### 问题：提取时找不到配方文件

**原因：** 代理尚未完成配方

**解决：** 在前端检查会话状态，等待完成后重新提取

### 问题：登录失败

**原因：** 测试账号不存在

**解决：**
1. 在前端注册测试账号
2. 或修改 `run_test_batch.py` 中的凭据

### 问题：成本为 0

**原因：** 消息中缺少 token 统计

**解决：** 确保使用最新版本代码（已包含 token 追踪）

## 📚 详细文档

- 完整文档：`test_suite/README.md`
- 场景配置：`test_suite/scenarios/`
- 工具说明：`test_suite/README.md#工具详解`

## 🎯 下一步

1. **创建自定义场景：** 编辑 `scenarios/beef_scenarios_sample.json`
2. **自动化测试：** 添加到 CI/CD 流程
3. **成本优化：** 分析 `cost_analysis.json`，优化高成本场景
4. **对比测试：** 运行多次测试，对比不同版本性能

## 💡 提示

- 使用时间戳追踪不同的测试运行
- 保留重要的测试结果作为基准
- 定期清理旧的测试运行释放空间
- 使用 `scenario_ids` 参数只测试修改的场景

---

**需要帮助？** 查看 `README.md` 获取完整文档。
