"""Utility helpers for working with supported locales and translations."""
from __future__ import annotations

SUPPORTED_LANGUAGES = ("zh-CN", "en-US")

LANGUAGE_LABELS = {
    "zh-CN": "Chinese",
    "en-US": "English",
}


def normalize_locale(locale: str | None) -> str:
    """Return a supported locale, falling back to zh-CN."""
    if not locale:
        return "zh-CN"
    locale = locale.strip()
    if locale in SUPPORTED_LANGUAGES:
        return locale
    # Handle e.g., en, en-US, en_us differences
    lowered = locale.lower()
    if lowered.startswith("en"):
        return "en-US"
    if lowered.startswith("zh"):
        return "zh-CN"
    return "zh-CN"


def get_language_label(locale: str | None) -> str:
    """Return a human-friendly language name for prompts."""
    normalized = normalize_locale(locale)
    return LANGUAGE_LABELS.get(normalized, LANGUAGE_LABELS["zh-CN"])


# ==============================================================================
# Centralized Translations Dictionary
# ==============================================================================

TRANSLATIONS = {
    "zh-CN": {
        # ==========================================================================
        # Export Translations (from formulation_tools.py)
        # ==========================================================================
        "export.sheet_results": "配方结果",
        "export.sheet_notes": "配方说明",
        "export.sheet_constraints": "约束条件",
        "export.date": "导出日期",
        "export.status": "优化状态",
        "export.total_cost": "总成本",
        "export.cost_unit": "元/公斤干物质",
        "export.dmi": "日干物质采食量",
        "export.ingredients": "饲料配方明细",
        "export.feed_name": "饲料名称",
        "export.amount": "日饲喂量 (kg/day)",
        "export.dm_percent": "干物质比例 (%)",
        "export.nutrients_header": "原料含量 (% DM)",
        "export.nutrition_profile": "整体营养成分分析",
        "export.nutrient": "营养成分",
        "export.content": "含量 (% DM)",
        "export.notes_none": "暂无配方说明",
        "export.constraint_validation": "营养约束验证",
        "export.constraint_type": "约束类型",
        "export.condition": "约束条件",
        "export.actual": "实际值",
        "export.unit": "单位",
        "export.satisfaction": "满足情况",
        "export.feed_constraints": "饲料用量约束",
        "export.min_percent": "最小比例 (%)",
        "export.max_percent": "最大比例 (%)",
        "export.no_feed_constraints": "无饲料用量约束",
        "export.chart_title": "营养成分组成图",
        "export.satisfied": "✓ 满足",
        "export.unsatisfied": "✗ 不满足",
        "export.con_concentration": "浓度约束",
        "export.con_dmi": "干物质采食量约束",
        "export.con_daily": "日摄入约束",
        "export.con_ratio": "比例约束",
        "export.target": "目标",
        "export.range": "范围内",
        "export.daily_intake_needed": "需要日采食量",
        "export.cannot_calculate": "无法计算",
        "export.denom_zero": "分母为零",
        "export.error_no_formulation": "未找到成功的配方。请先运行配方优化。",
        "export.error_no_db": "未找到饲料数据库。导出可能不包含完整的饲料信息。",
        "export.success": "✅ 成功导出 {filename}。",
        "export.fail": "导出配方时出错: {error}",
        # NASEM sheet translations
        "export.sheet_nasem": "NASEM分析",
        "export.nasem_production": "产奶预测",
        "export.nasem_predicted_milk": "预测产奶量 (kg/day)",
        "export.nasem_mp_allow_milk": "MP允许产奶量 (kg)",
        "export.nasem_ne_allow_milk": "NE允许产奶量 (kg)",
        "export.nasem_limiting_factor": "限制因素",
        "export.nasem_milk_fat": "乳脂 (g/g)",
        "export.nasem_milk_protein": "乳蛋白 (g/g)",
        "export.nasem_energy_balance": "能量平衡",
        "export.nasem_me_intake": "ME摄入 (Mcal/d)",
        "export.nasem_me_required": "ME需求 (Mcal/d)",
        "export.nasem_me_balance": "ME平衡",
        "export.nasem_protein_balance": "蛋白质平衡",
        "export.nasem_mp_intake": "MP摄入 (g/d)",
        "export.nasem_mp_required": "MP需求 (g/d)",
        "export.nasem_mp_balance": "MP平衡",
        "export.nasem_rdp_intake": "RDP摄入 (g/d)",
        "export.nasem_other_metrics": "其他指标",
        "export.nasem_dmi": "干物质采食量 (kg)",
        "export.nasem_dcad": "DCAD (meq)",
        "export.nasem_lys_mp": "赖氨酸占MP比例 (%)",
        "export.nasem_met_mp": "蛋氨酸占MP比例 (%)",
        "export.nasem_no_animal_input": "未提供动物参数,跳过NASEM分析",
        # Profitability section
        "export.sheet_summary": "配方摘要",
        "export.key_nutrients": "关键营养指标",
        "export.profitability": "经济效益分析",
        "export.input_section": "输入参数 (黄色单元格可编辑)",
        "export.herd_size": "牛群规模 (头)",
        "export.milk_price": "奶价 (元/kg)",
        "export.cost_per_kg_dm": "成本 (元/kg DM)",
        "export.cost_per_cow_day": "每头日成本 (元)",
        "export.revenue_per_cow_day": "每头日收入 (元)",
        "export.profit_per_cow_day": "每头日利润 (元)",
        "export.herd_profit_day": "牛群日利润 (元)",
        "export.herd_profit_month": "牛群月利润 (元)",
        "export.fc_ratio": "粗精比",
        "export.forage": "粗料",
        "export.concentrate": "精料",
        "export.price_per_kg": "价格 (元/kg)",
        "export.cost_per_day": "日成本 (元)",

        # ==========================================================================
        # Tool/Parser Translations (from message_parser.py)
        # ==========================================================================
        "tool.executing": "正在执行 {tool_name}",
        "tool.data_analysis": "数据分析",
        "tool.formulation": "饲料配方",
        "tool.completed": "已完成",
        "tool.operations_completed": "{count}项操作 已完成",
        # Excel tools
        "tool.excel.inspect_file": "分析 {filename} 文件结构",
        "tool.excel.inspect_files": "分析 {count} 个文件结构",
        "tool.excel.query": "查询 {filename}:{sheet}{preview}",
        "tool.excel.read": "读取 {filename} 中的{coord}",
        "tool.excel.preview_rows": "预览数据",
        "tool.excel.summary_stats": "统计信息",
        "tool.excel.grouping": "数据分组",
        "tool.excel.filtering": "数据筛选",
        "tool.excel.counting": "记录计数",
        "tool.excel.range": "范围 {coord}",
        "tool.excel.row": "第 {coord} 行",
        # File tools
        "tool.file.write": "写入文件 {filename}",
        "tool.file.list_current": "列出当前目录内容",
        "tool.file.list_dir": "列出目录 {dirname} 内容",
        "tool.file.read": "读取文件 {filename}",
        # Bash tools
        "tool.bash.list_files": "列出文件",
        "tool.bash.change_dir": "切换目录",
        "tool.bash.create_dir": "创建目录",
        "tool.bash.remove_files": "删除文件",
        "tool.bash.move_copy": "移动/复制文件",
        "tool.bash.search": "搜索文件内容",
        "tool.bash.view": "查看文件内容",
        "tool.bash.run_cmd": "执行 {cmd} 命令",
        "tool.bash.run_shell": "执行命令",
        "tool.execute": "执行 {tool_name}",
        # Formulation tools
        "tool.formulation.add_feed": "添加饲料 {name} 到饲料库 [{feedbase}] (干物质{dm}%, ¥{cost}/kg)",
        "tool.formulation.optimize": "进行配方优化",
        "tool.formulation.check_feeds": "检查可用饲料库",
        "tool.formulation.export": "导出配方为 {format} 格式",
        "tool.formulation.list_feedbases": "获取饲料基础库列表",
        "tool.formulation.run_tool": "执行配方工具 {tool_name}",

        # ==========================================================================
        # Model/Message Translations (from models.py)
        # ==========================================================================
        "role.researcher": "🔬 正在切换到研究专员",
        "role.coder": "💻 正在切换到代码专员",
        "role.nutritionist": "🥛 返回营养师",
        "role.transition": "切换到 {role}",
        "file.ready_download": "{filename} 已准备好下载",
        "file.status_ready": "准备下载",
        "analysis.initializing": "{type}: 正在初始化...",
        "calc.expression": "计算: {expression}",
    },

    "en-US": {
        # ==========================================================================
        # Export Translations
        # ==========================================================================
        "export.sheet_results": "Formulation Results",
        "export.sheet_notes": "Formulation Notes",
        "export.sheet_constraints": "Constraints",
        "export.date": "Date",
        "export.status": "Status",
        "export.total_cost": "Total Cost",
        "export.cost_unit": "CNY/kg DM",
        "export.dmi": "DMI",
        "export.ingredients": "Ingredients",
        "export.feed_name": "Feed Name",
        "export.amount": "Amount (kg/day)",
        "export.dm_percent": "DM %",
        "export.nutrients_header": "Nutrients (% DM)",
        "export.nutrition_profile": "Nutrition Profile",
        "export.nutrient": "Nutrient",
        "export.content": "Content (% DM)",
        "export.notes_none": "No notes available",
        "export.constraint_validation": "Nutrient Constraints Validation",
        "export.constraint_type": "Type",
        "export.condition": "Condition",
        "export.actual": "Actual",
        "export.unit": "Unit",
        "export.satisfaction": "Status",
        "export.feed_constraints": "Feed Constraints",
        "export.min_percent": "Min %",
        "export.max_percent": "Max %",
        "export.no_feed_constraints": "No feed constraints",
        "export.chart_title": "Nutrition Composition",
        "export.satisfied": "✓ Pass",
        "export.unsatisfied": "✗ Fail",
        "export.con_concentration": "Concentration",
        "export.con_dmi": "DMI Constraint",
        "export.con_daily": "Daily Intake",
        "export.con_ratio": "Ratio",
        "export.target": "Target",
        "export.range": "In range",
        "export.daily_intake_needed": "Daily intake needed",
        "export.cannot_calculate": "Cannot calculate",
        "export.denom_zero": "Denominator zero",
        "export.error_no_formulation": "No successful formulation found. Please run optimization first.",
        "export.error_no_db": "Feed database not found. Export may not include complete feed information.",
        "export.success": "✅ Successfully exported {filename}.",
        "export.fail": "Error exporting formulation: {error}",
        # NASEM sheet translations
        "export.sheet_nasem": "NASEM Analysis",
        "export.nasem_production": "Production Predictions",
        "export.nasem_predicted_milk": "Predicted Milk (kg/day)",
        "export.nasem_mp_allow_milk": "MP Allowable Milk (kg)",
        "export.nasem_ne_allow_milk": "NE Allowable Milk (kg)",
        "export.nasem_limiting_factor": "Limiting Factor",
        "export.nasem_milk_fat": "Milk Fat (g/g)",
        "export.nasem_milk_protein": "Milk Protein (g/g)",
        "export.nasem_energy_balance": "Energy Balance",
        "export.nasem_me_intake": "ME Intake (Mcal/d)",
        "export.nasem_me_required": "ME Required (Mcal/d)",
        "export.nasem_me_balance": "ME Balance",
        "export.nasem_protein_balance": "Protein Balance",
        "export.nasem_mp_intake": "MP Intake (g/d)",
        "export.nasem_mp_required": "MP Required (g/d)",
        "export.nasem_mp_balance": "MP Balance",
        "export.nasem_rdp_intake": "RDP Intake (g/d)",
        "export.nasem_other_metrics": "Other Metrics",
        "export.nasem_dmi": "DMI (kg)",
        "export.nasem_dcad": "DCAD (meq)",
        "export.nasem_lys_mp": "Lys % of MP",
        "export.nasem_met_mp": "Met % of MP",
        "export.nasem_no_animal_input": "No animal input provided, NASEM analysis skipped",
        # Profitability section
        "export.sheet_summary": "Summary",
        "export.key_nutrients": "Key Nutrients",
        "export.profitability": "Profitability Analysis",
        "export.input_section": "Inputs (edit yellow cells)",
        "export.herd_size": "Herd Size",
        "export.milk_price": "Milk Price (¥/kg)",
        "export.cost_per_kg_dm": "Cost (¥/kg DM)",
        "export.cost_per_cow_day": "Cost/Cow/Day (¥)",
        "export.revenue_per_cow_day": "Revenue/Cow/Day (¥)",
        "export.profit_per_cow_day": "Profit/Cow/Day (¥)",
        "export.herd_profit_day": "Herd Profit/Day (¥)",
        "export.herd_profit_month": "Herd Profit/Month (¥)",
        "export.fc_ratio": "F:C Ratio",
        "export.forage": "Forage",
        "export.concentrate": "Concentrate",
        "export.price_per_kg": "Price (¥/kg)",
        "export.cost_per_day": "Cost/Day (¥)",

        # ==========================================================================
        # Tool/Parser Translations
        # ==========================================================================
        "tool.executing": "Executing {tool_name}",
        "tool.data_analysis": "Data Analysis",
        "tool.formulation": "Formulation",
        "tool.completed": "Completed",
        "tool.operations_completed": "{count} operations completed",
        # Excel tools
        "tool.excel.inspect_file": "Inspect structure of {filename}",
        "tool.excel.inspect_files": "Inspect structure of {count} files",
        "tool.excel.query": "Query {filename}:{sheet}{preview}",
        "tool.excel.read": "Read {coord} from {filename}",
        "tool.excel.preview_rows": "preview rows",
        "tool.excel.summary_stats": "summary stats",
        "tool.excel.grouping": "grouping data",
        "tool.excel.filtering": "filtering data",
        "tool.excel.counting": "counting records",
        "tool.excel.range": "range {coord}",
        "tool.excel.row": "row {coord}",
        # File tools
        "tool.file.write": "Write file {filename}",
        "tool.file.list_current": "List current directory",
        "tool.file.list_dir": "List contents of {dirname}",
        "tool.file.read": "Read file {filename}",
        # Bash tools
        "tool.bash.list_files": "List files",
        "tool.bash.change_dir": "Change directory",
        "tool.bash.create_dir": "Create directory",
        "tool.bash.remove_files": "Remove files",
        "tool.bash.move_copy": "Move or copy files",
        "tool.bash.search": "Search file contents",
        "tool.bash.view": "View file contents",
        "tool.bash.run_cmd": "Run command {cmd}",
        "tool.bash.run_shell": "Run shell command",
        "tool.execute": "Execute {tool_name}",
        # Formulation tools
        "tool.formulation.add_feed": "Add feed {name} to feedbase [{feedbase}] (DM {dm}%, ¥{cost}/kg)",
        "tool.formulation.optimize": "Run ration optimization",
        "tool.formulation.check_feeds": "Check available feeds",
        "tool.formulation.export": "Export formulation as {format}",
        "tool.formulation.list_feedbases": "List feedbases",
        "tool.formulation.run_tool": "Run formulation tool {tool_name}",

        # ==========================================================================
        # Model/Message Translations
        # ==========================================================================
        "role.researcher": "🔬 Delegating to researcher",
        "role.coder": "💻 Delegating to coder",
        "role.nutritionist": "🥛 Returning to nutritionist",
        "role.transition": "Transitioning to {role}",
        "file.ready_download": "{filename} ready for download",
        "file.status_ready": "Ready to download",
        "analysis.initializing": "{type}: Initializing...",
        "calc.expression": "Calculate: {expression}",
    }
}


def t(key: str, locale: str | None = None, **kwargs) -> str:
    """
    Get translation for key with optional interpolation.
    
    Args:
        key: Translation key (e.g., "export.sheet_summary")
        locale: Locale code (defaults to zh-CN)
        **kwargs: Interpolation values (e.g., filename="test.xlsx")
    
    Returns:
        Translated string with interpolated values
    
    Example:
        t("export.success", "zh-CN", filename="配方.xlsx")
        # Returns: "✅ 成功导出 配方.xlsx。"
    """
    locale = normalize_locale(locale)
    translations = TRANSLATIONS.get(locale, TRANSLATIONS["zh-CN"])
    text = translations.get(key, key)  # Fall back to key if not found
    
    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            # If format string has placeholders that aren't provided, return as-is
            return text
    return text


def get_export_texts(locale: str | None = None) -> dict:
    """
    Get all export translations as a flat dict for backward compatibility.
    Maps old EXPORT_TRANSLATIONS keys to new t() calls.
    
    Args:
        locale: Locale code
    
    Returns:
        Dict with export keys (without 'export.' prefix)
    """
    locale = normalize_locale(locale)
    translations = TRANSLATIONS.get(locale, TRANSLATIONS["zh-CN"])
    
    # Extract all export.* keys and remove prefix
    result = {}
    for key, value in translations.items():
        if key.startswith("export."):
            short_key = key[7:]  # Remove "export." prefix
            result[short_key] = value
    
    return result
