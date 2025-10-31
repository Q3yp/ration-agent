#!/usr/bin/env python3
"""
Extract test results for a given test run timestamp.
Collects exported formulation files and session data.
"""

import asyncio
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dump_session import dump_session


async def extract_test_results(timestamp: str):
    """
    Extract all results for a test run.

    Args:
        timestamp: Test run timestamp (e.g., '20251030_120000')
    """
    # Define paths
    test_suite_dir = Path(__file__).parent
    test_runs_dir = test_suite_dir / "test_runs"
    test_run_dir = test_runs_dir / timestamp
    files_dir = Path(__file__).parent.parent / "files"

    # Check if test run exists
    if not test_run_dir.exists():
        print(f"❌ Test run not found: {test_run_dir}")
        print(f"\nAvailable test runs:")
        if test_runs_dir.exists():
            for run in sorted(test_runs_dir.iterdir(), reverse=True):
                if run.is_dir():
                    print(f"  - {run.name}")
        sys.exit(1)

    # Load manifest
    manifest_file = test_run_dir / "manifest.json"
    if not manifest_file.exists():
        print(f"❌ Manifest not found: {manifest_file}")
        sys.exit(1)

    with open(manifest_file, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    print("="*80)
    print(f"提取测试结果 - {timestamp}")
    print("="*80)
    print(f"测试账号: {manifest['metadata'].get('test_account', 'unknown')}")
    print(f"动物类型: {manifest['metadata'].get('animal_type', 'unknown')}")
    print(f"场景总数: {manifest['metadata'].get('total_scenarios', 0)}")
    print(f"成功场景: {manifest['metadata'].get('successful', 0)}")
    print(f"失败场景: {manifest['metadata'].get('failed', 0)}")
    print("="*80)

    # Create results directory structure
    results_dir = test_run_dir / "results"
    results_dir.mkdir(exist_ok=True)

    # Create subdirectories
    (results_dir / "success").mkdir(exist_ok=True)
    (results_dir / "failed").mkdir(exist_ok=True)
    (results_dir / "formulations").mkdir(exist_ok=True)

    # Process each scenario
    successful_extractions = []
    failed_extractions = []

    print(f"\n📦 处理 {len(manifest['scenarios'])} 个场景...\n")

    for scenario in manifest['scenarios']:
        scenario_id = scenario['scenario_id']
        scenario_name = scenario['scenario_name']
        session_id = scenario.get('session_id')
        status = scenario['status']

        print(f"场景 {scenario_id:2d}: {scenario_name}")

        if status != "submitted" or not session_id:
            print(f"  ⊘ 跳过 (状态: {status})")
            failed_extractions.append({
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "reason": "未成功提交"
            })
            continue

        try:
            # Create scenario directory
            scenario_dir_name = f"场景{scenario_id:02d}_{scenario_name}"
            scenario_dir = results_dir / "success" / scenario_dir_name
            scenario_dir.mkdir(exist_ok=True)

            # 1. Dump session data
            print(f"  📥 导出会话数据...")
            await dump_session(session_id, scenario_dir, include_artifacts=True)

            # 2. Find and copy Excel formulation files
            session_files_dir = files_dir / session_id
            if session_files_dir.exists():
                excel_files = list(session_files_dir.glob("*.xlsx"))
                if excel_files:
                    print(f"  📊 发现 {len(excel_files)} 个配方文件")
                    for excel_file in excel_files:
                        # Copy to scenario directory
                        dest_file = scenario_dir / excel_file.name
                        shutil.copy2(excel_file, dest_file)
                        print(f"    ✓ {excel_file.name}")

                        # Also copy to formulations directory with scenario prefix
                        formulation_file = results_dir / "formulations" / f"场景{scenario_id:02d}_{excel_file.name}"
                        shutil.copy2(excel_file, formulation_file)
                else:
                    print(f"  ⚠️  未找到配方文件")
                    failed_extractions.append({
                        "scenario_id": scenario_id,
                        "scenario_name": scenario_name,
                        "session_id": session_id,
                        "reason": "未找到配方文件"
                    })
                    continue
            else:
                print(f"  ⚠️  会话文件目录不存在: {session_files_dir}")
                failed_extractions.append({
                    "scenario_id": scenario_id,
                    "scenario_name": scenario_name,
                    "session_id": session_id,
                    "reason": "会话文件目录不存在"
                })
                continue

            # 3. Save scenario metadata
            metadata = {
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "session_id": session_id,
                "prompt": scenario.get("prompt", ""),
                "timestamp": scenario.get("timestamp", ""),
            }

            metadata_file = scenario_dir / "metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            successful_extractions.append({
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "session_id": session_id,
                "formulation_files": len(excel_files) if session_files_dir.exists() and excel_files else 0
            })

            print(f"  ✅ 提取完成\n")

        except Exception as e:
            print(f"  ❌ 提取失败: {e}\n")
            failed_extractions.append({
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "session_id": session_id,
                "reason": str(e)
            })

    # Generate extraction report
    report = {
        "timestamp": timestamp,
        "total_scenarios": len(manifest['scenarios']),
        "successful_extractions": len(successful_extractions),
        "failed_extractions": len(failed_extractions),
        "success_details": successful_extractions,
        "failed_details": failed_extractions,
    }

    report_file = test_run_dir / "extraction_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Print summary
    print("="*80)
    print("提取完成汇总")
    print("="*80)
    print(f"\n成功提取: {len(successful_extractions)}/{len(manifest['scenarios'])}")
    print(f"失败: {len(failed_extractions)}/{len(manifest['scenarios'])}")

    if successful_extractions:
        print(f"\n✅ 成功提取的场景:")
        for item in successful_extractions:
            print(f"  场景{item['scenario_id']:2d} ({item['scenario_name']}): {item['formulation_files']} 个配方文件")

    if failed_extractions:
        print(f"\n❌ 提取失败的场景:")
        for item in failed_extractions:
            print(f"  场景{item['scenario_id']:2d} ({item['scenario_name']}): {item['reason']}")

    print(f"\n{'='*80}")
    print(f"结果目录: {results_dir}")
    print(f"提取报告: {report_file}")
    print(f"{'='*80}\n")

    # Run cost analysis
    print("📊 计算成本分析...\n")
    await run_cost_analysis(test_run_dir)


async def run_cost_analysis(test_run_dir: Path):
    """Run cost analysis on extracted test results"""
    from calculate_test_costs import (
        calculate_cost,
        extract_tokens_from_messages,
        HAIKU_4_5_INPUT_PRICE,
        HAIKU_4_5_OUTPUT_PRICE
    )

    results_dir = test_run_dir / "results" / "success"
    if not results_dir.exists():
        print("⚠️  No successful results to analyze")
        return

    total_input = 0
    total_output = 0
    total_tokens = 0
    scenario_costs = []

    for scenario_dir in sorted(results_dir.iterdir()):
        if not scenario_dir.is_dir():
            continue

        # Find messages.json file
        messages_files = list(scenario_dir.glob("*_messages.json"))
        if not messages_files:
            continue

        messages_file = messages_files[0]
        input_tokens, output_tokens, tokens = extract_tokens_from_messages(messages_file)
        cost = calculate_cost(input_tokens, output_tokens)

        total_input += input_tokens
        total_output += output_tokens
        total_tokens += tokens

        scenario_costs.append({
            "scenario": scenario_dir.name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": tokens,
            "cost": cost
        })

    # Save cost analysis
    cost_analysis = {
        "pricing": {
            "input_price_per_1m": HAIKU_4_5_INPUT_PRICE,
            "output_price_per_1m": HAIKU_4_5_OUTPUT_PRICE,
            "model": "claude-haiku-4.5"
        },
        "summary": {
            "total_scenarios": len(scenario_costs),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_tokens,
            "total_cost": calculate_cost(total_input, total_output),
            "average_cost_per_scenario": calculate_cost(total_input, total_output) / len(scenario_costs) if scenario_costs else 0,
            "average_tokens_per_scenario": total_tokens / len(scenario_costs) if scenario_costs else 0
        },
        "scenarios": sorted(scenario_costs, key=lambda x: x['cost'], reverse=True)
    }

    cost_file = test_run_dir / "cost_analysis.json"
    with open(cost_file, 'w', encoding='utf-8') as f:
        json.dump(cost_analysis, f, indent=2, ensure_ascii=False)

    print(f"成本分析:")
    print(f"  总场景数: {len(scenario_costs)}")
    print(f"  总输入 tokens: {total_input:,}")
    print(f"  总输出 tokens: {total_output:,}")
    print(f"  总 tokens: {total_tokens:,}")
    print(f"  总成本: ${cost_analysis['summary']['total_cost']:.4f}")
    print(f"  平均成本/场景: ${cost_analysis['summary']['average_cost_per_scenario']:.4f}")
    print(f"\n💾 成本分析已保存: {cost_file}\n")


async def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python extract_test_results.py <timestamp>")
        print("\nExample:")
        print("  python extract_test_results.py 20251030_120000")
        print("\nAvailable test runs:")
        test_runs_dir = Path(__file__).parent / "test_runs"
        if test_runs_dir.exists():
            for run in sorted(test_runs_dir.iterdir(), reverse=True):
                if run.is_dir():
                    print(f"  - {run.name}")
        sys.exit(1)

    timestamp = sys.argv[1]
    await extract_test_results(timestamp)


if __name__ == "__main__":
    asyncio.run(main())
