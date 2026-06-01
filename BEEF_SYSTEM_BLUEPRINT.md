# 肉牛配方系统实施蓝图 (Beef Cattle Formulation System Blueprint)

## 1. 现状分析

### 1.1 奶牛系统 (Dairy Cow) — 完整参考
奶牛配方系统已完全建成，包含以下核心组件：

| 组件 | 路径 | 职责 |
|------|------|------|
| 营养模型服务 | `backend/services/nasem_service.py` | 封装 NASEM 2021 Dairy Model，计算 MP/ME 供需、DMI 预测、产奶量预测 |
| 专用工具 | `backend/tools/nasem_tools.py` | `predict_dairy_requirements`、`evaluate_diet_with_nasem` |
| 优化器 | `backend/formulation/optimizer.py` | SLSQP 优化，集成 NASEM 缓存，支持 `mp_balance` / `me_balance` 约束 |
| 配方工具 | `backend/tools/formulation_tools.py` | `set_animal_params` / `formulate_ration` / `add_feed` / `check_feeds` |
| 系统饲料库 | `backend/migrations/data/system_feedbases.json` | `default_dairy_cow` 含完整 NASEM 字段 |
| Prompt | `backend/prompts/nutritionist_dairy_cow.md` | NASEM 2021 标准与配方流程 |

**奶牛工具注册点**：`backend/tools/tools.py` 的 `get_tools()` 中，`animal_type == "dairy_cow"` 时动态加载 `nasem_tools`。

### 1.2 肉牛系统 (Beef Cow) — 当前缺失
虽然骨架存在，但**营养模型层完全空白**：

- **无营养模型服务**：没有等价于 `nasem_service.py` 的 NRC 2016 Beef 服务。
- **无专用评估工具**：没有 `predict_beef_requirements` / `evaluate_diet_beef` 工具。
- **优化器无肉牛逻辑**：`optimizer.py` 只有 NASEM  Dairy 的 DMI/MP/ME 计算，对 beef 无 DMI 预测、无能量/蛋白平衡约束。
- **`set_animal_params` 只支持奶牛参数**：仅有 `milk_prod` / `dim` / `parity` 等，缺少肉牛参数如 `target_adg` / `stage` / `frame_score`。
- **系统饲料库存在但孤立**：`default_beef_cow` 在 `system_feedbases.json` 中已定义（含 `NEm_Mcal`、`NEg_Mcal`、`CP`、`DCP` 等字段），但没有任何代码消费这些字段。

---

## 2. 需要建设的组件清单

### 2.1 营养模型服务 (由用户先实现)
**新建文件**：`backend/services/nrc_beef_service.py`

**核心职责**（基于 NRC 2016 肉牛标准）：
1. **能量需求计算**
   - `NEm_req (Mcal/day) = 0.077 × BW^0.75`
   - `NEg_req (Mcal/day)` 基于目标日增重 (ADG)、空腹体重 (EBW) 和增重成分。
2. **DMI 预测**
   - 支持多阶段 DMI 预测公式（育肥期、妊娠期、维持期等）。
   - 或提供基于日粮 NEm 浓度的 DMI 预测。
3. **蛋白需求计算**
   - MP 需求、CP 需求、RDP 需求。
4. **日粮评估**
   - 输入：feedbase + diet_composition（kg DM/天）+ animal_input。
   - 输出：日粮 NEm/NEg/CP/矿物质供给、与需求的对比、预测 ADG、饲料效率等。
5. **约束建议生成**
   - 根据动物参数自动生成 `formulate_ration` 可直接使用的 nutritional_constraints 列表。

**建议对外暴露的接口**：
```python
class NRCBeefService:
    def build_animal_input(self, body_weight_kg, target_adg_kg, stage, ...)
    def calculate_requirements(self, animal_input) -> dict
    def evaluate_diet(self, feedbase, diet_composition, animal_input) -> dict
    def predict_dmi(self, animal_input, diet_ne_mcal_kg) -> float
```

### 2.2 肉牛专用工具 (待模型完成后实现)
**新建文件**：`backend/tools/beef_tools.py`

| 工具 | 输入 | 输出 |
|------|------|------|
| `predict_beef_requirements` | `body_weight_kg`, `target_adg_kg`, `stage`, ... | JSON：NEm/NEg/CP/DMI 需求 + `formulation_constraints` 建议 |
| `evaluate_diet_beef` | 从 state 读取当前配方 + 动物参数 | JSON：日粮分析、预测 ADG、能量蛋白平衡、矿物质评估 |

### 2.3 优化器扩展 (待模型完成后实现)
**修改文件**：`backend/formulation/optimizer.py`

需要在 `FormulationOptimizer` 中增加：
1. **肉牛参数设置**：`set_animal_params_beef(...)`
2. **肉牛 DMI 预测**：`predict_dmi_beef(feed_percentages, selected_feeds)` — 基于日粮 NEm 浓度调用 NRCBeefService。
3. **牛肉平衡约束**（类似奶牛的 `mp_balance` / `me_balance`）：
   - `nem_balance`：NEm 供给 vs 维持需求
   - `neg_balance`：NEg 供给 vs 增重需求
   - `cp_balance`：CP 供给 vs 蛋白需求
4. **结果字典适配**：`_build_result_dict` 中，beef 模式下不再输出 `predicted_milk_kg`，而是输出 `predicted_adg_kg`、`feed_efficiency` 等。
5. **方向性提示适配**：`_build_orientation_hints` 中增加肉牛特有的 acidosis / NDF / eNDF 提示。

### 2.4 配方工具扩展 (待模型完成后实现)
**修改文件**：`backend/tools/formulation_tools.py`

- **`set_animal_params`**：当 `animal_type == "beef_cow"` 时，支持 `target_adg_kg`、`stage`（`backgrounding`/`growing`/`finishing`/`maintenance`/`gestation`/`lactation`）、`frame_score`、`implant_status` 等参数。
- **`formulate_ration`**：
  - beef 模式下，使用 `NRCBeefService` 进行 DMI 预测。
  - 支持 beef 特有的 balance 约束（`nem_balance`、`neg_balance`、`cp_balance`）。
  - 优化目标暂时保持 `minimize_cost` / `feasibility`，去掉 dairy 的 `maximize_profit`（基于产奶量）。

### 2.5 工具注册 (待模型完成后实现)
**修改文件**：`backend/tools/tools.py`

在 `get_tools()` 中，为 `beef_cow` 增加分支，加载 `beef_tools.py` 中的工具（类似 dairy 加载 `nasem_tools`）。

### 2.6 Prompt / 饲料库 (基本可用，可能需要微调)
- `backend/prompts/nutritionist_beef_cow.md` **已存在**，包含 NRC 2016 基础知识和安全审查流程，无需大改。
- `default_beef_cow` 饲料库 **已存在**，包含 `NEm_Mcal`、`NEg_Mcal`、`ME_Mcal`、`CP`、`DCP`、`NDF`、`ADF`、`Ca`、`P` 等字段，足以支持 NRC 计算。

---

## 3. 关键集成点与数据流

### 3.1 Agent 创建流程
```
create_agent(animal_type="beef_cow")
  └─> get_tools("beef_cow")
        └─> create_formulation_tools("beef_cow")   [已有]
        └─> 加载 beef_tools [待实现]
        └─> 通用工具: calculate, ask_user [已有]
```

### 3.2 配方请求数据流
```
用户输入 -> Agent
  -> set_animal_params(beef参数) [扩展]
  -> predict_beef_requirements [新建]
       └─> NRCBeefService.calculate_requirements
  -> formulate_ration [扩展]
       └─> optimizer.optimize [扩展]
            └─> NRCBeefService.predict_dmi [新建]
            └─> NRCBeefService.evaluate_diet [新建] (用于 balance 约束)
  -> evaluate_diet_beef [新建]
  -> export_formulation [已有]
```

### 3.3 State  Schema
`FormulationState`（`backend/core/agent.py`）中 `animal_params` 是通用 `dict`，无需改 schema，beef 参数直接存入即可。

---

## 4. `default_beef_cow` 饲料库字段现状

现有饲料已包含以下 NRC 相关字段（% DM basis，能量为 Mcal/kg DM）：
- `CP`, `DCP` (Digestible CP)
- `EE`
- `NDF`, `ADF`
- `Ash`
- `Ca`, `P`, `Na`, `K`, `Mg`, `S`
- `ME_Mcal`, `ME_MJ`
- `NEm_Mcal`, `NEm_MJ`
- `NEg_Mcal`, `NEg_MJ`

**注意**：如果 NRC 模型需要额外字段（如 `RUP`、`RDP`、`eNDF`、`TDN`），可在模型实现后通过 `_apply_feed_overrides` 机制或在 `system_feedbases.json` 中补充。

---

## 5. 测试场景

`backend/test_suite/test_beef_scenarios.py` 已定义 10 个场景，覆盖：
1. 育肥初期（架子牛，ADG 1.5）
2. 妊娠晚期母牛（保胎）
3. 后备母牛（培育期，ADG 0.7-0.8）
4. 育肥冲刺期（终结期，高能量）
5. 泌乳高峰期母牛
6. 应激期犊牛（开口料）
7. 育肥中期（生长期，ADG 1.6）
8. 空怀母牛（维持期，低成本）
9. 过瘦母牛（恢复期）
10. 种公牛（非配种季）

模型实现后，这些场景可作为端到端验证用例。

---

## 6. 实施顺序建议

1. **Step 1 (用户)**：实现 `backend/services/nrc_beef_service.py`，确保接口与上述设计一致。
2. **Step 2 (Agent)**：
   - 创建 `backend/tools/beef_tools.py`
   - 扩展 `optimizer.py` 的 beef 支持
   - 扩展 `formulation_tools.py` 的 beef 支持
   - 修改 `tools.py` 注册 beef 工具
3. **Step 3 (验证)**：运行 `test_beef_scenarios.py` 验证各场景是否能成功配方并导出 Excel。

---

## 7. 需要特别注意的约束类型

优化器当前已原生支持的约束类型对 beef 同样适用：
- `concentration`： nutrient % of DM（如 CP min 11, max 14）
- `daily_total`： absolute daily amount（如 Ca g/day）
- `ratio`： nutrient ratio（如 Ca:P ratio）
- `inclusion`： feed inclusion %（`feed_constraints` 参数）

新增 needed：beef 版的 balance 约束（参考 dairy 的 `mp_balance` / `me_balance` 实现模式），让优化器能在迭代中调用 NRCBeefService 评估日粮并计算供需差。
