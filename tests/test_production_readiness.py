"""
Production Readiness Test / 上线标准测试

Tests included:
1. All crisis module APIs return 200 and valid JSON
2. All PDF download URLs are reachable
3. All required data fields are present
4. Frontend static files are accessible
5. No Python import errors
"""

import json
import urllib.request
import urllib.error
import time
import socket
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://127.0.0.1:8188"
TIMEOUT = 15

# 确保能导入项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def wait_for_server(max_wait=30):
    """等待服务器启动"""
    start = time.time()
    while time.time() - start < max_wait:
        try:
            with socket.create_connection(("127.0.0.1", 8188), timeout=1):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False


def fetch_url(url, method="GET", body=None):
    """获取URL返回内容"""
    req = urllib.request.Request(
        url,
        method=method,
        headers={"Content-Type": "application/json"} if body else {},
        data=json.dumps(body).encode("utf-8") if body else None,
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            content = resp.read()
            return resp.status, content, resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), ""
    except Exception as e:
        return -1, str(e).encode(), ""


def test_server_available():
    """测试服务器是否可访问"""
    assert wait_for_server(30), "Server not available on port 8188"
    status, content, _ = fetch_url(f"{BASE_URL}/api/users")
    assert status == 200, f"Server health check failed: {status}"
    print("[OK] Server is available")


def test_crisis_apis():
    """测试所有危机专题API"""
    endpoints = [
        ("/api/crisis/list", "GET", None),
        ("/api/crisis/gfc_2008", "GET", None),
        ("/api/crisis/gfc_2008/timeline", "GET", None),
        ("/api/crisis/gfc_2008/macro", "GET", None),
        ("/api/crisis/gfc_2008/institutions", "GET", None),
        ("/api/crisis/gfc_2008/multi-timeline", "GET", None),
        ("/api/crisis/compare/2008", "GET", None),
        ("/api/crisis/risk/dashboard", "GET", None),
        ("/api/crisis/risk/yield-curve", "GET", None),
        ("/api/crisis/risk/liquidity", "GET", None),
        ("/api/crisis/risk/valuation", "GET", None),
        ("/api/crisis/risk/cross-cycle", "GET", None),
        ("/api/crisis/policy/toolbox", "GET", None),
        ("/api/crisis/transmission/graph", "GET", None),
        ("/api/crisis/recovery/dashboard", "GET", None),
        ("/api/crisis/policy/historical", "GET", None),
        ("/api/crisis/policy/simulate", "POST", {"selected_tools": ["rate_cut", "qe"], "severity": "moderate"}),
    ]
    
    failures = []
    for path, method, body in endpoints:
        status, content, _ = fetch_url(f"{BASE_URL}{path}", method, body)
        if status != 200:
            failures.append(f"{method} {path}: status {status}")
            continue
        try:
            json.loads(content)
        except json.JSONDecodeError:
            failures.append(f"{method} {path}: invalid JSON")
    
    assert not failures, f"API failures: {failures}"
    print(f"[OK] All {len(endpoints)} crisis APIs passed")


def test_crisis_data_integrity():
    """测试危机数据完整性"""
    status, content, _ = fetch_url(f"{BASE_URL}/api/crisis/list")
    assert status == 200
    data = json.loads(content)
    crises = data.get("crises", [])
    assert len(crises) >= 5, f"Expected at least 5 crises, got {len(crises)}"
    
    for crisis in crises:
        assert "id" in crisis
        assert "name_zh" in crisis
        assert "name_en" in crisis
        assert "institutional_analyses" in crisis
        for analysis in crisis.get("institutional_analyses", []):
            assert "institution" in analysis
            assert "report" in analysis
            assert "key_finding_zh" in analysis
            assert "download_url" in analysis
            assert "summary_zh" in analysis
            assert "conclusion_zh" in analysis
    
    print(f"[OK] Crisis data integrity passed for {len(crises)} crises")


def test_pdf_urls():
    """测试所有PDF下载链接是否可访问"""
    status, content, _ = fetch_url(f"{BASE_URL}/api/crisis/list")
    data = json.loads(content)
    
    pdf_urls = []
    for crisis in data.get("crises", []):
        for analysis in crisis.get("institutional_analyses", []):
            url = analysis.get("download_url", "")
            if url:
                pdf_urls.append((analysis["institution"], analysis["report"], url))
    
    failures = []
    success_count = 0
    
    def check_url(item):
        institution, report, url = item
        browser_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        def try_check(headers):
            for method in ["HEAD", "GET"]:
                try:
                    req = urllib.request.Request(url, method=method, headers=headers)
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        return institution, report, resp.status, resp.headers.get("Content-Type", "")
                except Exception:
                    continue
            return None

        # 先尝试最小请求头：部分站点（如 IMF）对浏览器 User-Agent 返回 403
        result = try_check({})
        if result and result[2] == 200:
            return result

        # 再尝试浏览器请求头：部分站点（如 companiesmarketcap）需要 User-Agent
        result = try_check(browser_headers)
        if result:
            return result

        return institution, report, -1, "Failed with both minimal and browser headers"
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(check_url, item): item for item in pdf_urls}
        for future in as_completed(futures):
            institution, report, status, ctype = future.result()
            if status == 200:
                success_count += 1
                print(f"[OK] PDF reachable: {institution} - {report}")
            else:
                failures.append(f"{institution} - {report}: status {status}, {ctype}")
    
    assert not failures, f"PDF failures: {failures}"
    print(f"[OK] All {success_count} PDF URLs reachable")


def test_static_files():
    """测试前端静态文件"""
    files = ["/static/index.html", "/static/app.js?v=7"]
    for f in files:
        status, content, ctype = fetch_url(f"{BASE_URL}{f}")
        assert status == 200, f"Static file {f} failed: {status}"
        assert len(content) > 0, f"Static file {f} is empty"
        if f.endswith(".html"):
            assert "text/html" in ctype, f"{f} wrong content type: {ctype}"
    print("[OK] Static files accessible")


def test_python_imports():
    """测试Python模块可导入"""
    import data_sources.crisis_tracker
    import data_sources.risk_monitor
    import data_sources.policy_simulator
    
    # Test all major functions exist and return serializable data
    from data_sources.crisis_tracker import get_all_crisis_data, get_crisis_detail
    from data_sources.risk_monitor import get_risk_dashboard
    from data_sources.policy_simulator import simulate_policies, get_transmission_graph
    
    crises = get_all_crisis_data()
    assert len(crises) > 0
    json.dumps(crises)
    
    detail = get_crisis_detail("gfc_2008")
    assert "error" not in detail
    json.dumps(detail)
    
    dashboard = get_risk_dashboard()
    assert "risk_score" in dashboard
    json.dumps(dashboard)
    
    sim = simulate_policies(["rate_cut"], "moderate")
    assert "metrics" in sim
    assert "market_recovery_months" in sim["metrics"]
    json.dumps(sim)
    
    graph = get_transmission_graph()
    assert "nodes" in graph
    json.dumps(graph)
    
    print("[OK] Python imports and functions passed")


def main():
    print("=== 上线标准测试 ===\n")
    test_server_available()
    test_python_imports()
    test_crisis_apis()
    test_crisis_data_integrity()
    test_pdf_urls()
    test_static_files()
    print("\n=== 所有测试通过，系统达到上线标准 ===")


if __name__ == "__main__":
    main()
