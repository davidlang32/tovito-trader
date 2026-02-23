#!/usr/bin/env python3
"""
Fund API - Regression Test Suite
==================================

Automated tests for all Fund API endpoints.
Run after any code changes to verify nothing is broken.

Usage:
    python test_api_regression.py                    # Run all tests
    python test_api_regression.py --verbose          # Detailed output
    python test_api_regression.py --section auth     # Test only auth endpoints
    python test_api_regression.py --stop-on-fail     # Stop at first failure
    python test_api_regression.py --report           # Generate HTML report

Sections:
    health, auth, investor, nav, withdraw

Requirements:
    - API running on localhost:8000
    - At least one verified investor account
    
Environment Variables (optional):
    TEST_EMAIL     - Investor email (default: dlang32@gmail.com)
    TEST_PASSWORD  - Investor password
    API_BASE_URL   - API URL (default: http://localhost:8000)
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
import requests


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
DEFAULT_EMAIL = os.getenv("TEST_EMAIL", "dlang32@gmail.com")
DEFAULT_PASSWORD = os.getenv("TEST_PASSWORD", "")


# ============================================================
# TEST RESULT TRACKING
# ============================================================

@dataclass
class TestResult:
    """Single test result"""
    name: str
    section: str
    passed: bool
    duration_ms: float
    message: str = ""
    request: Dict = field(default_factory=dict)
    response: Dict = field(default_factory=dict)
    error: str = ""


@dataclass
class TestSuite:
    """Test suite results"""
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    results: List[TestResult] = field(default_factory=list)
    
    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)
    
    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)
    
    @property
    def total(self) -> int:
        return len(self.results)
    
    @property
    def duration_seconds(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0
    
    def add(self, result: TestResult):
        self.results.append(result)
    
    def summary(self) -> str:
        return f"{self.passed}/{self.total} passed ({self.failed} failed) in {self.duration_seconds:.2f}s"


# ============================================================
# API CLIENT
# ============================================================

class APIClient:
    """HTTP client for API testing"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.session = requests.Session()
    
    def _headers(self, auth: bool = False) -> Dict:
        headers = {"Content-Type": "application/json"}
        if auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers
    
    def get(self, endpoint: str, auth: bool = False, params: Dict = None) -> requests.Response:
        url = f"{self.base_url}{endpoint}"
        return self.session.get(url, headers=self._headers(auth), params=params)
    
    def post(self, endpoint: str, data: Dict, auth: bool = False) -> requests.Response:
        url = f"{self.base_url}{endpoint}"
        return self.session.post(url, json=data, headers=self._headers(auth))
    
    def delete(self, endpoint: str, auth: bool = False) -> requests.Response:
        url = f"{self.base_url}{endpoint}"
        return self.session.delete(url, headers=self._headers(auth))
    
    def login(self, email: str, password: str) -> bool:
        """Login and store tokens"""
        r = self.post("/auth/login", {"email": email, "password": password})
        if r.status_code == 200:
            data = r.json()
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            return True
        return False


# ============================================================
# TEST RUNNER
# ============================================================

class TestRunner:
    """Runs API tests and collects results"""
    
    def __init__(self, base_url: str, verbose: bool = False, stop_on_fail: bool = False):
        self.client = APIClient(base_url)
        self.suite = TestSuite()
        self.verbose = verbose
        self.stop_on_fail = stop_on_fail
        self.current_section = ""
    
    def run_test(self, name: str, test_func) -> TestResult:
        """Run a single test and record result"""
        start = time.time()
        
        try:
            passed, message, request_info, response_info = test_func()
            duration = (time.time() - start) * 1000
            
            result = TestResult(
                name=name,
                section=self.current_section,
                passed=passed,
                duration_ms=duration,
                message=message,
                request=request_info or {},
                response=response_info or {}
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            result = TestResult(
                name=name,
                section=self.current_section,
                passed=False,
                duration_ms=duration,
                error=str(e)
            )
        
        self.suite.add(result)
        self._print_result(result)
        
        if not result.passed and self.stop_on_fail:
            raise StopIteration("Test failed and --stop-on-fail is set")
        
        return result
    
    def _print_result(self, result: TestResult):
        """Print test result"""
        icon = "✅" if result.passed else "❌"
        print(f"  {icon} {result.name} ({result.duration_ms:.1f}ms)")
        
        if self.verbose or not result.passed:
            if result.message:
                print(f"      {result.message}")
            if result.error:
                print(f"      Error: {result.error}")
    
    def section(self, name: str):
        """Start a new test section"""
        self.current_section = name
        print(f"\n{'='*60}")
        print(f" {name.upper()}")
        print('='*60)

    # ========================================================
    # HEALTH TESTS
    # ========================================================
    
    def test_health(self):
        """Test health endpoint"""
        def test():
            r = self.client.get("/health")
            passed = r.status_code == 200 and r.json().get("status") == "healthy"
            return passed, f"Status: {r.json()}", {"endpoint": "/health"}, r.json()
        return self.run_test("GET /health", test)
    
    def test_root(self):
        """Test root endpoint"""
        def test():
            r = self.client.get("/")
            passed = r.status_code == 200 and "name" in r.json()
            return passed, f"API: {r.json().get('name')}", {"endpoint": "/"}, r.json()
        return self.run_test("GET /", test)

    # ========================================================
    # AUTH TESTS
    # ========================================================
    
    def test_login_invalid_email(self):
        """Test login with invalid email"""
        def test():
            r = self.client.post("/auth/login", {
                "email": "nonexistent@example.com",
                "password": "password123"
            })
            passed = r.status_code == 401
            return passed, f"Status: {r.status_code}", None, r.json()
        return self.run_test("POST /auth/login (invalid email)", test)
    
    def test_login_invalid_password(self, email: str):
        """Test login with wrong password"""
        def test():
            r = self.client.post("/auth/login", {
                "email": email,
                "password": "WrongPassword123!"
            })
            passed = r.status_code == 401
            return passed, f"Status: {r.status_code}", None, r.json()
        return self.run_test("POST /auth/login (wrong password)", test)
    
    def test_login_valid(self, email: str, password: str):
        """Test login with valid credentials"""
        def test():
            r = self.client.post("/auth/login", {
                "email": email,
                "password": password
            })
            if r.status_code == 200:
                data = r.json()
                self.client.access_token = data.get("access_token")
                self.client.refresh_token = data.get("refresh_token")
                passed = "access_token" in data and "refresh_token" in data
                return passed, f"Logged in as {data.get('investor_name')}", None, {"has_tokens": True}
            return False, f"Status: {r.status_code}", None, r.json()
        return self.run_test("POST /auth/login (valid)", test)
    
    def test_auth_me(self):
        """Test get current user"""
        def test():
            r = self.client.get("/auth/me", auth=True)
            if r.status_code == 200:
                data = r.json()
                passed = "investor_id" in data and "name" in data
                return passed, f"User: {data.get('name')}", None, data
            return False, f"Status: {r.status_code}", None, r.json() if r.text else {}
        return self.run_test("GET /auth/me", test)
    
    def test_auth_me_no_token(self):
        """Test get current user without token"""
        def test():
            r = self.client.get("/auth/me", auth=False)
            passed = r.status_code in [401, 403]
            return passed, f"Status: {r.status_code} (expected 401/403)", None, {}
        return self.run_test("GET /auth/me (no token)", test)
    
    def test_refresh_token(self):
        """Test token refresh"""
        def test():
            if not self.client.refresh_token:
                return False, "No refresh token available", None, {}
            
            r = self.client.post("/auth/refresh", {
                "refresh_token": self.client.refresh_token
            })
            if r.status_code == 200:
                data = r.json()
                self.client.access_token = data.get("access_token")
                self.client.refresh_token = data.get("refresh_token")
                return True, "Tokens refreshed", None, {"has_tokens": True}
            return False, f"Status: {r.status_code}", None, r.json()
        return self.run_test("POST /auth/refresh", test)

    # ========================================================
    # INVESTOR TESTS
    # ========================================================
    
    def test_investor_profile(self):
        """Test investor profile"""
        def test():
            r = self.client.get("/investor/profile", auth=True)
            if r.status_code == 200:
                data = r.json()
                required = ["investor_id", "name", "email", "status"]
                passed = all(k in data for k in required)
                return passed, f"Profile: {data.get('name')}", None, data
            return False, f"Status: {r.status_code}", None, r.json() if r.text else {}
        return self.run_test("GET /investor/profile", test)
    
    def test_investor_position(self):
        """Test investor position"""
        def test():
            r = self.client.get("/investor/position", auth=True)
            if r.status_code == 200:
                data = r.json()
                required = ["current_shares", "current_value", "total_return_percent"]
                passed = all(k in data for k in required)
                msg = f"Value: ${data.get('current_value', 0):,.2f}, Return: {data.get('total_return_percent', 0):.2f}%"
                return passed, msg, None, data
            return False, f"Status: {r.status_code}", None, r.json() if r.text else {}
        return self.run_test("GET /investor/position", test)
    
    def test_investor_transactions(self):
        """Test investor transactions"""
        def test():
            r = self.client.get("/investor/transactions", auth=True)
            if r.status_code == 200:
                data = r.json()
                passed = "transactions" in data and "net_investment" in data
                count = len(data.get("transactions", []))
                return passed, f"{count} transactions", None, {"count": count}
            return False, f"Status: {r.status_code}", None, r.json() if r.text else {}
        return self.run_test("GET /investor/transactions", test)
    
    def test_investor_transactions_filtered(self):
        """Test investor transactions with filters"""
        def test():
            r = self.client.get("/investor/transactions", auth=True, params={
                "limit": 5,
                "transaction_type": "Contribution"
            })
            if r.status_code == 200:
                data = r.json()
                transactions = data.get("transactions", [])
                # Check filter worked
                all_contributions = all(t.get("type") == "Contribution" for t in transactions)
                passed = len(transactions) <= 5 and all_contributions
                return passed, f"{len(transactions)} contributions", None, {"count": len(transactions)}
            return False, f"Status: {r.status_code}", None, r.json() if r.text else {}
        return self.run_test("GET /investor/transactions (filtered)", test)

    # ========================================================
    # NAV TESTS
    # ========================================================
    
    def test_nav_current(self):
        """Test current NAV"""
        def test():
            r = self.client.get("/nav/current", auth=True)
            if r.status_code == 200:
                data = r.json()
                required = ["nav_per_share", "date", "total_portfolio_value"]
                passed = all(k in data for k in required)
                msg = f"NAV: ${data.get('nav_per_share', 0):.4f} on {data.get('date')}"
                return passed, msg, None, data
            return False, f"Status: {r.status_code}", None, r.json() if r.text else {}
        return self.run_test("GET /nav/current", test)
    
    def test_nav_history(self):
        """Test NAV history"""
        def test():
            r = self.client.get("/nav/history", auth=True, params={"days": 7})
            if r.status_code == 200:
                data = r.json()
                passed = "history" in data and "current" in data
                count = len(data.get("history", []))
                return passed, f"{count} days of history", None, {"count": count}
            return False, f"Status: {r.status_code}", None, r.json() if r.text else {}
        return self.run_test("GET /nav/history", test)
    
    def test_nav_performance(self):
        """Test fund performance"""
        def test():
            r = self.client.get("/nav/performance", auth=True)
            if r.status_code == 200:
                data = r.json()
                required = ["ytd_return", "since_inception", "current_nav"]
                passed = all(k in data for k in required)
                msg = f"YTD: {data.get('ytd_return', 0):.2f}%, Inception: {data.get('since_inception', 0):.2f}%"
                return passed, msg, None, data
            return False, f"Status: {r.status_code}", None, r.json() if r.text else {}
        return self.run_test("GET /nav/performance", test)

    def test_benchmark_chart(self):
        """Test benchmark chart endpoint returns PNG"""
        def test():
            r = self.client.get("/nav/benchmark-chart", auth=True, params={"days": 30})
            if r.status_code == 200:
                content_type = r.headers.get("content-type", "")
                is_png = "image/png" in content_type
                size = len(r.content)
                passed = is_png and size > 100
                msg = f"PNG image, {size:,} bytes"
                return passed, msg, None, {"size": size, "content_type": content_type}
            return False, f"Status: {r.status_code}", None, {}
        return self.run_test("GET /nav/benchmark-chart", test)

    def test_benchmark_data(self):
        """Test benchmark data endpoint returns JSON with nav_per_share"""
        def test():
            r = self.client.get("/nav/benchmark-data", auth=True, params={"days": 30})
            if r.status_code == 200:
                data = r.json()
                has_fund = "fund" in data
                has_benchmarks = "benchmarks" in data
                # Fund items should include nav_per_share for interactive chart
                fund_has_nav = (
                    len(data.get("fund", [])) == 0
                    or "nav_per_share" in data["fund"][0]
                )
                passed = has_fund and has_benchmarks and fund_has_nav
                tickers = list(data.get("benchmarks", {}).keys())
                msg = f"Fund series (nav_per_share={fund_has_nav}) + benchmarks: {tickers}"
                return passed, msg, None, {"tickers": tickers}
            return False, f"Status: {r.status_code}", None, r.json() if r.text else {}
        return self.run_test("GET /nav/benchmark-data", test)

    # ========================================================
    # FUND FLOW TESTS
    # ========================================================

    def test_fund_flow_estimate(self):
        """Test fund flow withdrawal estimate"""
        def test():
            r = self.client.get("/fund-flow/estimate", auth=True,
                                params={"flow_type": "withdrawal", "amount": 1000})
            if r.status_code == 200:
                data = r.json()
                required = ["flow_type", "amount", "estimated_tax", "net_proceeds"]
                passed = all(k in data for k in required)
                msg = f"$1000 → Tax: ${data.get('estimated_tax', 0):.2f}, Net: ${data.get('net_proceeds', 0):.2f}"
                return passed, msg, None, data
            return False, f"Status: {r.status_code}", None, r.json() if r.text else {}
        return self.run_test("GET /fund-flow/estimate (withdrawal)", test)

    def test_fund_flow_estimate_contribution(self):
        """Test fund flow contribution estimate"""
        def test():
            r = self.client.get("/fund-flow/estimate", auth=True,
                                params={"flow_type": "contribution", "amount": 1000})
            if r.status_code == 200:
                data = r.json()
                required = ["flow_type", "amount", "estimated_shares"]
                passed = all(k in data for k in required)
                msg = f"$1000 → Shares: {data.get('estimated_shares', 0):.4f}"
                return passed, msg, None, data
            return False, f"Status: {r.status_code}", None, r.json() if r.text else {}
        return self.run_test("GET /fund-flow/estimate (contribution)", test)

    def test_fund_flow_requests_list(self):
        """Test listing fund flow requests"""
        def test():
            r = self.client.get("/fund-flow/requests", auth=True)
            if r.status_code == 200:
                data = r.json()
                passed = "requests" in data and "total" in data
                count = data.get("total", 0)
                return passed, f"{count} fund flow requests", None, {"count": count}
            return False, f"Status: {r.status_code}", None, r.json() if r.text else {}
        return self.run_test("GET /fund-flow/requests", test)

    # ========================================================
    # RUN ALL TESTS
    # ========================================================
    
    def run_all(self, email: str, password: str, sections: List[str] = None):
        """Run all tests"""
        print("\n" + "="*60)
        print(" FUND API REGRESSION TEST SUITE")
        print("="*60)
        print(f"\n  Base URL: {self.client.base_url}")
        print(f"  Email: {email}")
        print(f"  Time: {self.suite.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        all_sections = ["health", "auth", "investor", "nav", "fund-flow"]
        run_sections = sections or all_sections
        
        try:
            # Health
            if "health" in run_sections:
                self.section("Health Check")
                self.test_health()
                self.test_root()
            
            # Auth
            if "auth" in run_sections:
                self.section("Authentication")
                self.test_login_invalid_email()
                self.test_login_invalid_password(email)
                self.test_login_valid(email, password)
                self.test_auth_me()
                self.test_auth_me_no_token()
                self.test_refresh_token()
            elif not self.client.access_token:
                # Need to login for other tests
                self.client.login(email, password)
            
            # Investor
            if "investor" in run_sections:
                self.section("Investor Data")
                self.test_investor_profile()
                self.test_investor_position()
                self.test_investor_transactions()
                self.test_investor_transactions_filtered()
            
            # NAV
            if "nav" in run_sections:
                self.section("NAV Data")
                self.test_nav_current()
                self.test_nav_history()
                self.test_nav_performance()
            
            # Fund Flow
            if "fund-flow" in run_sections:
                self.section("Fund Flow")
                self.test_fund_flow_estimate()
                self.test_fund_flow_estimate_contribution()
                self.test_fund_flow_requests_list()
                
        except StopIteration:
            print("\n⛔ Stopped due to test failure (--stop-on-fail)")
        
        self.suite.end_time = datetime.now()
        return self.suite


# ============================================================
# REPORT GENERATION
# ============================================================

def generate_html_report(suite: TestSuite, output_path: Path):
    """Generate HTML test report"""
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Fund API Test Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
        .stat {{ background: #f9f9f9; padding: 15px 25px; border-radius: 6px; text-align: center; }}
        .stat.passed {{ border-left: 4px solid #4CAF50; }}
        .stat.failed {{ border-left: 4px solid #f44336; }}
        .stat .value {{ font-size: 32px; font-weight: bold; }}
        .stat .label {{ color: #666; font-size: 14px; }}
        .section {{ margin: 30px 0; }}
        .section h2 {{ color: #555; font-size: 18px; margin-bottom: 10px; }}
        .test {{ display: flex; align-items: center; padding: 10px; border-bottom: 1px solid #eee; }}
        .test:hover {{ background: #f9f9f9; }}
        .test .icon {{ font-size: 18px; margin-right: 10px; }}
        .test .name {{ flex: 1; }}
        .test .duration {{ color: #999; font-size: 12px; }}
        .test.passed .icon {{ color: #4CAF50; }}
        .test.failed .icon {{ color: #f44336; }}
        .test.failed {{ background: #fff5f5; }}
        .message {{ color: #666; font-size: 12px; margin-left: 28px; }}
        .timestamp {{ color: #999; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 Fund API Test Report</h1>
        
        <div class="summary">
            <div class="stat passed">
                <div class="value">{suite.passed}</div>
                <div class="label">Passed</div>
            </div>
            <div class="stat failed">
                <div class="value">{suite.failed}</div>
                <div class="label">Failed</div>
            </div>
            <div class="stat">
                <div class="value">{suite.duration_seconds:.2f}s</div>
                <div class="label">Duration</div>
            </div>
        </div>
"""
    
    # Group by section
    sections = {}
    for r in suite.results:
        if r.section not in sections:
            sections[r.section] = []
        sections[r.section].append(r)
    
    for section_name, results in sections.items():
        html += f"""
        <div class="section">
            <h2>{section_name}</h2>
"""
        for r in results:
            status_class = "passed" if r.passed else "failed"
            icon = "✅" if r.passed else "❌"
            html += f"""
            <div class="test {status_class}">
                <span class="icon">{icon}</span>
                <span class="name">{r.name}</span>
                <span class="duration">{r.duration_ms:.1f}ms</span>
            </div>
"""
            if r.message and not r.passed:
                html += f'            <div class="message">{r.message}</div>\n'
        
        html += "        </div>\n"
    
    html += f"""
        <div class="timestamp">
            Generated: {suite.end_time.strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>
"""
    
    output_path.write_text(html, encoding='utf-8')
    return output_path


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='Fund API Regression Test Suite',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Sections: health, auth, investor, nav, withdraw

Examples:
  python test_api_regression.py
  python test_api_regression.py --verbose
  python test_api_regression.py --section auth --section investor
  python test_api_regression.py --report
"""
    )
    parser.add_argument('--base-url', default=DEFAULT_BASE_URL, help='API base URL')
    parser.add_argument('--email', default=DEFAULT_EMAIL, help='Test user email')
    parser.add_argument('--password', default=DEFAULT_PASSWORD, help='Test user password')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--stop-on-fail', action='store_true', help='Stop on first failure')
    parser.add_argument('--section', action='append', dest='sections', help='Run specific section(s)')
    parser.add_argument('--report', action='store_true', help='Generate HTML report')
    parser.add_argument('--report-path', default='test_report.html', help='HTML report path')
    args = parser.parse_args()
    
    # Check password
    if not args.password:
        print("❌ Password required. Use --password or set TEST_PASSWORD environment variable.")
        print("\nExample:")
        print(f'  python test_api_regression.py --email {args.email} --password "YourPassword123!"')
        sys.exit(1)
    
    # Run tests
    runner = TestRunner(args.base_url, args.verbose, args.stop_on_fail)
    suite = runner.run_all(args.email, args.password, args.sections)
    
    # Print summary
    print("\n" + "="*60)
    print(" SUMMARY")
    print("="*60)
    print(f"\n  {suite.summary()}")
    
    if suite.failed > 0:
        print("\n  ❌ FAILED TESTS:")
        for r in suite.results:
            if not r.passed:
                print(f"     • {r.section}: {r.name}")
                if r.message:
                    print(f"       {r.message}")
    else:
        print("\n  🎉 All tests passed!")
    
    # Generate report
    if args.report:
        report_path = Path(args.report_path)
        generate_html_report(suite, report_path)
        print(f"\n  📄 Report saved: {report_path.absolute()}")
    
    # Exit code
    sys.exit(0 if suite.failed == 0 else 1)


if __name__ == '__main__':
    main()
