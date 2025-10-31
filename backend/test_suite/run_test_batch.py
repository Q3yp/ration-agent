#!/usr/bin/env python3
"""
Enhanced test runner for beef cattle formulation scenarios.
Creates timestamped test runs with session tracking and metadata.
"""

import asyncio
import httpx
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Test account credentials
TEST_EMAIL = "test@wuitu.com"
TEST_PASSWORD = "testacc"
API_BASE_URL = "http://localhost:8000"

# Test scenarios directory
TEST_SCENARIOS_FILE = Path(__file__).parent / "scenarios" / "beef_scenarios.json"
TEST_RUNS_DIR = Path(__file__).parent / "test_runs"


async def login(client: httpx.AsyncClient) -> str:
    """Login and return JWT token"""
    login_data = {
        "username": TEST_EMAIL,
        "password": TEST_PASSWORD
    }

    response = await client.post(
        f"{API_BASE_URL}/auth/jwt/login",
        data=login_data
    )

    if response.status_code != 200:
        raise Exception(f"Login failed: {response.status_code} - {response.text}")

    data = response.json()
    return data["access_token"]


async def create_session(client: httpx.AsyncClient, token: str, animal_type: str = "beef_cow") -> str:
    """Create a new session and return session_id"""
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"{API_BASE_URL}/sessions/create",
        json={"animal_type": animal_type},
        headers=headers
    )

    if response.status_code != 200:
        raise Exception(f"Session creation failed: {response.status_code} - {response.text}")

    data = response.json()
    return data["session_id"]


async def send_message(client: httpx.AsyncClient, token: str, session_id: str, message: str):
    """Send a message to the chat endpoint"""
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"{API_BASE_URL}/chat/stream/{session_id}",
        json={"message": message},
        headers=headers,
        timeout=5.0
    )

    if response.status_code not in [200, 202]:
        print(f"  ⚠️  Warning: Message send returned {response.status_code}")


async def run_scenario(
    client: httpx.AsyncClient,
    token: str,
    scenario: Dict,
    animal_type: str = "beef_cow"
) -> Dict:
    """Create session and send prompt for a single scenario"""
    print(f"\n{'='*80}")
    print(f"场景 {scenario['id']}: {scenario['name']}")
    print(f"{'='*80}")

    try:
        # Create session
        print("  创建会话中...")
        session_id = await create_session(client, token, animal_type)
        print(f"  ✓ 会话已创建: {session_id}")

        # Send prompt
        print("  发送配方请求...")
        await send_message(client, token, session_id, scenario['prompt'])
        print(f"  ✓ 请求已发送（代理将自主完成配方）")

        return {
            "scenario_id": scenario['id'],
            "scenario_name": scenario['name'],
            "session_id": session_id,
            "prompt": scenario['prompt'],
            "status": "submitted",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        print(f"  ✗ 错误: {str(e)}")
        return {
            "scenario_id": scenario['id'],
            "scenario_name": scenario['name'],
            "session_id": None,
            "prompt": scenario['prompt'],
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def create_test_run_directory(timestamp: str) -> Path:
    """Create a timestamped directory for test run"""
    test_run_dir = TEST_RUNS_DIR / timestamp
    test_run_dir.mkdir(parents=True, exist_ok=True)
    return test_run_dir


def save_test_manifest(test_run_dir: Path, results: List[Dict], metadata: Dict):
    """Save test run manifest with session mappings"""
    manifest = {
        "metadata": metadata,
        "scenarios": results
    }

    manifest_file = test_run_dir / "manifest.json"
    with open(manifest_file, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n📝 Test manifest saved to: {manifest_file}")


def load_scenarios(scenarios_file: Path = None) -> List[Dict]:
    """Load scenarios from JSON file or use embedded scenarios"""
    if scenarios_file and scenarios_file.exists():
        with open(scenarios_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    # Embedded scenarios (same as test_beef_scenarios.py)
    return [
        {
            "id": 1,
            "name": "育肥初期（架子牛）",
            "prompt": """场景1：育肥初期（架子牛）

牛群状态：
- 100头西门塔尔杂交架子牛
- 刚入栏15天，已完成驱虫和基础免疫
- 平均体重300公斤
- 健康状况良好，采食量逐步增加

饲喂目标：
- 促进骨架和肌肉的快速生长
- 目标日增重（ADG）1.5公斤/天
- 需要高能量、中高蛋白日粮
- 确保瘤胃健康，防止酸中毒

请使用系统默认肉牛饲料库，自主配制完整的日粮配方，完成后自动导出配方结果。请完全自主进行，无需等待我的进一步指示。"""
        },
        {
            "id": 2,
            "name": "妊娠晚期母牛（保胎）",
            "prompt": """场景2：妊娠晚期母牛（保胎）

牛群状态：
- 50头安格斯经产母牛
- 平均体重550公斤
- 处于妊娠最后60天（第8-9个月）
- 体况评分（BCS）为5.5（9分制）

饲喂目标：
- 维持母牛体况在5.5-6.0
- 支持胎儿快速生长（70%的胎儿生长发生在该阶段）
- 为即将到来的泌乳期储备能量
- 防止过度肥胖导致难产
- 满足微量元素和维生素需求

请使用系统默认肉牛饲料库，自主配制完整的日粮配方，完成后自动导出配方结果。请完全自主进行，无需等待我的进一步指示。"""
        },
        {
            "id": 3,
            "name": "后备母牛（培育期）",
            "prompt": """场景3：后备母牛（培育期）

牛群状态：
- 80头10月龄的后备小母牛
- 平均体重260公斤

饲喂目标：
- 经济方式使其稳定生长
- 目标：14-15月龄时体重达到350-380公斤（成年体重的60-65%）
- 日增重（ADG）控制在0.7-0.8公斤/天
- 避免过肥影响乳腺发育

请使用系统默认肉牛饲料库，自主配制完整的日粮配方，完成后自动导出配方结果。请完全自主进行，无需等待我的进一步指示。"""
        },
        # Add more scenarios as needed...
    ]


async def main(
    scenarios_file: Path = None,
    animal_type: str = "beef_cow",
    scenario_ids: List[int] = None
):
    """Run test batch with session tracking"""
    # Generate timestamp for this test run
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("="*80)
    print("肉牛配方场景自动化测试 - 增强版")
    print("="*80)
    print(f"测试时间戳: {timestamp}")
    print(f"测试账号: {TEST_EMAIL}")
    print(f"动物类型: {animal_type}")
    print(f"API地址: {API_BASE_URL}")
    print("="*80)

    # Load scenarios
    scenarios = load_scenarios(scenarios_file)

    # Filter scenarios if specific IDs provided
    if scenario_ids:
        scenarios = [s for s in scenarios if s['id'] in scenario_ids]

    print(f"场景总数: {len(scenarios)}")

    # Create test run directory
    test_run_dir = create_test_run_directory(timestamp)
    print(f"测试目录: {test_run_dir}")
    print("="*80)

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Login
        print("\n登录中...")
        try:
            token = await login(client)
            print("✓ 登录成功")
        except Exception as e:
            print(f"✗ 登录失败: {e}")
            return

        # Fire all scenarios concurrently
        print(f"\n🚀 并发提交所有 {len(scenarios)} 个场景...")
        tasks = [run_scenario(client, token, scenario, animal_type) for scenario in scenarios]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        successful = []
        failed = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed.append({
                    "scenario_id": scenarios[i]['id'],
                    "scenario_name": scenarios[i]['name'],
                    "error": str(result),
                    "status": "failed"
                })
            elif result['status'] == 'submitted':
                successful.append(result)
            else:
                failed.append(result)

        # Save test manifest
        metadata = {
            "timestamp": timestamp,
            "test_account": TEST_EMAIL,
            "animal_type": animal_type,
            "total_scenarios": len(scenarios),
            "successful": len(successful),
            "failed": len(failed),
            "api_url": API_BASE_URL
        }

        save_test_manifest(test_run_dir, successful + failed, metadata)

        # Create session mapping file (for easy reference)
        session_mapping = {
            r['scenario_name']: r['session_id']
            for r in successful
        }

        mapping_file = test_run_dir / "session_mapping.json"
        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(session_mapping, f, indent=2, ensure_ascii=False)

        # Print summary
        print(f"\n{'='*80}")
        print("测试完成汇总")
        print(f"{'='*80}")

        print(f"\n成功提交: {len(successful)}/{len(scenarios)}")
        print(f"失败: {len(failed)}/{len(scenarios)}")

        if successful:
            print(f"\n✅ 已提交的会话 ID:")
            for r in successful:
                print(f"  场景{r['scenario_id']:2d} ({r['scenario_name']}): {r['session_id']}")

        if failed:
            print(f"\n❌ 失败的场景:")
            for r in failed:
                print(f"  场景{r['scenario_id']:2d} ({r['scenario_name']}): {r.get('error', 'Unknown error')}")

        print(f"\n{'='*80}")
        print(f"测试运行 ID: {timestamp}")
        print(f"结果目录: {test_run_dir}")
        print("="*80)
        print("\n所有场景已提交，代理正在后台自主完成配方")
        print("请使用以下命令提取结果:")
        print(f"  python test_suite/extract_test_results.py {timestamp}")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    import sys

    # Parse command line arguments
    animal_type = "beef_cow"
    scenario_ids = None

    if len(sys.argv) > 1:
        # First arg can be animal type
        animal_type = sys.argv[1]

    if len(sys.argv) > 2:
        # Remaining args are scenario IDs
        scenario_ids = [int(x) for x in sys.argv[2:]]

    asyncio.run(main(
        scenarios_file=TEST_SCENARIOS_FILE,
        animal_type=animal_type,
        scenario_ids=scenario_ids
    ))
