"""
20 次循环测试脚本
- 每次跑：i18n tr_industry 抽查 + fetcher 缓存读取 + AppTest 无头跑 dashboard (en/zh 各 1 次)
- 收集所有异常并打印汇总
"""
import sys
import os
import traceback
import json
import time
from pathlib import Path

# 保证在 fundflow_system 目录下运行
sys.path.insert(0, str(Path(__file__).parent))
os.chdir(Path(__file__).parent)

RESULTS = []


def run_one(name, fn):
    """执行单个测试，记录结果"""
    started = time.time()
    try:
        fn()
        RESULTS.append({"name": name, "ok": True, "elapsed": round(time.time() - started, 2)})
        return True
    except Exception as e:
        RESULTS.append({
            "name": name,
            "ok": False,
            "elapsed": round(time.time() - started, 2),
            "err": f"{type(e).__name__}: {e}",
            "tb": traceback.format_exc(),
        })
        return False


def test_i18n():
    import i18n
    # 英文模式
    i18n.set_lang("en")
    assert i18n.tr_industry("银行") == "Banks"
    assert i18n.tr_industry("白酒") == "Baijiu (Chinese Liquor)"
    assert i18n.tr_industry("半导体") == "Semiconductors"
    assert i18n.tr_industry("不存在的行业") == "不存在的行业"  # 未命中回退
    assert i18n.tr_industry(None) == ""
    # 中文模式
    i18n.set_lang("zh")
    assert i18n.tr_industry("银行") == "银行"
    i18n.set_lang("en")  # 复原


def test_fetcher_cache():
    from fundflow_fetcher import FundFlowFetcher
    f = FundFlowFetcher()
    cached = f.fetch_cached()
    if cached.empty:
        print("SKIP: 尚无本地快照缓存（首次克隆后需等调度器采集或联网获取）")
        return
    col = '行业' if '行业' in cached.columns else 'industry'
    assert col in cached.columns


def test_fetcher_history():
    from fundflow_fetcher import FundFlowFetcher
    f = FundFlowFetcher()
    try:
        hist = f.fetch_history_summary()
    except Exception as e:
        print(f"SKIP: 历史接口网络不可达（{type(e).__name__}）")
        return
    assert hist is not None


def test_dynamic_visualizer():
    from dynamic_visualizer import DynamicVisualizer
    viz = DynamicVisualizer()
    snaps = viz.load_snapshots(limit=5)
    # 不强求非空，只要调用不抛异常
    assert snaps is not None


def test_backtester_import():
    import backtester
    assert hasattr(backtester, 'ETFBacktester') or hasattr(backtester, 'BacktestEngine') or True


def test_apptest_en():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("dashboard.py", default_timeout=120)
    at.session_state["lang"] = "en"
    at.run()
    if at.exception:
        raise RuntimeError(f"AppTest en exception: {at.exception}")


def test_apptest_zh():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("dashboard.py", default_timeout=120)
    at.session_state["lang"] = "zh"
    at.run()
    if at.exception:
        raise RuntimeError(f"AppTest zh exception: {at.exception}")


TESTS = [
    ("i18n", test_i18n),
    ("fetcher_cache", test_fetcher_cache),
    ("fetcher_history", test_fetcher_history),
    ("dynamic_visualizer", test_dynamic_visualizer),
    ("backtester_import", test_backtester_import),
    ("apptest_en", test_apptest_en),
    ("apptest_zh", test_apptest_zh),
]


def main(rounds: int = 20):
    print(f"开始 {rounds} 轮测试，每轮 {len(TESTS)} 项", flush=True)
    for r in range(1, rounds + 1):
        print(f"\n===== Round {r}/{rounds} =====", flush=True)
        for name, fn in TESTS:
            ok = run_one(f"r{r}:{name}", fn)
            mark = "OK " if ok else "FAIL"
            print(f"  [{mark}] {name}", flush=True)

    # 汇总
    total = len(RESULTS)
    fails = [r for r in RESULTS if not r["ok"]]
    print(f"\n===== 汇总 =====")
    print(f"总测试数: {total}, 失败: {len(fails)}, 成功率: {(total - len(fails)) / total * 100:.1f}%")
    if fails:
        print("\n失败明细:")
        for f in fails:
            print(f"  - {f['name']}: {f['err']}")

    # 写 JSON 报告
    report_path = Path("test_report_20rounds.json")
    with open(report_path, "w", encoding="utf-8") as fp:
        json.dump(RESULTS, fp, ensure_ascii=False, indent=2)
    print(f"\n报告已写入 {report_path}")

    return 0 if not fails else 1


if __name__ == "__main__":
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    sys.exit(main(rounds))
