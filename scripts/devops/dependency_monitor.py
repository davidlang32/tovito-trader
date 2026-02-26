"""
TOVITO TRADER - Dependency Monitor

Checks for outdated Python (pip) and npm packages, generates structured
reports, and sends notifications via Discord webhook and email.

Usage:
    python scripts/devops/dependency_monitor.py
    python scripts/devops/dependency_monitor.py --no-notify
    python scripts/devops/dependency_monitor.py --pip-only
    python scripts/devops/dependency_monitor.py --npm-only
    python scripts/devops/dependency_monitor.py --json
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.safe_logging import get_safe_logger

logger = get_safe_logger(__name__)


class DependencyMonitor:
    """Checks pip and npm packages for available updates and reports results.

    Generates structured JSON reports, human-readable console output, and
    optional Discord / email notifications when outdated packages are found.
    """

    def __init__(self, project_root=None):
        self.project_root = Path(project_root or PROJECT_ROOT)
        self.frontend_dir = (
            self.project_root
            / "apps"
            / "investor_portal"
            / "frontend"
            / "investor_portal"
        )
        self.report_dir = self.project_root / "data" / "devops" / "dependency_reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Version classification
    # ------------------------------------------------------------------

    @staticmethod
    def classify_upgrade(current_version: str, latest_version: str) -> str:
        """Classify the upgrade distance between two version strings.

        Args:
            current_version: Currently installed version string.
            latest_version: Latest available version string.

        Returns:
            One of 'major', 'minor', 'patch', or 'unknown'.
        """
        try:
            from packaging.version import Version

            cur = Version(current_version)
            lat = Version(latest_version)

            if lat.major > cur.major:
                return "major"
            elif lat.minor > cur.minor:
                return "minor"
            elif lat.micro > cur.micro:
                return "patch"
            # Same version or pre-release difference
            return "patch"
        except Exception:
            return "unknown"

    # ------------------------------------------------------------------
    # pip check
    # ------------------------------------------------------------------

    def _load_requirements_constraints(self, requirements_file: str) -> dict:
        """Load package names from a requirements file.

        Returns a dict mapping lowercased package name -> requirements filename.
        """
        constraints = {}
        req_path = self.project_root / requirements_file
        if not req_path.exists():
            return constraints
        try:
            with open(req_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("-"):
                        continue
                    # Extract package name before any version specifier
                    for sep in (">=", "<=", "==", "!=", "~=", ">", "<", "["):
                        if sep in line:
                            line = line[: line.index(sep)]
                            break
                    pkg_name = line.strip().lower().replace("-", "-")
                    if pkg_name:
                        constraints[pkg_name] = requirements_file
        except Exception:
            pass
        return constraints

    def check_pip_packages(self, requirements_file: str = "requirements-full.txt") -> list:
        """Check for outdated pip packages.

        Runs ``pip list --outdated --format=json`` and cross-references the
        results with the project's requirements files.

        Args:
            requirements_file: Primary requirements file to check against.

        Returns:
            List of dicts with keys: name, current, latest, constraint,
            requirements_file, upgrade_type.
        """
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--outdated", "--format=json"],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except FileNotFoundError:
            logger.warning("pip not found -- skipping Python package check")
            return []
        except subprocess.TimeoutExpired:
            logger.warning("pip list timed out after 120s")
            return []

        if result.returncode != 0 and not result.stdout.strip():
            logger.warning("pip list returned exit code %d", result.returncode)
            return []

        try:
            outdated_raw = json.loads(result.stdout) if result.stdout.strip() else []
        except json.JSONDecodeError:
            logger.error("Failed to parse pip JSON output")
            return []

        # Build constraints map from both requirements files
        constraints = self._load_requirements_constraints(requirements_file)
        constraints.update(self._load_requirements_constraints("requirements.txt"))

        packages = []
        for pkg in outdated_raw:
            name = pkg.get("name", "")
            current = pkg.get("version", "")
            latest = pkg.get("latest_version", "")
            name_lower = name.lower()

            req_file = constraints.get(name_lower, None)

            packages.append(
                {
                    "name": name,
                    "current": current,
                    "latest": latest,
                    "constraint": req_file is not None,
                    "requirements_file": req_file or "",
                    "upgrade_type": self.classify_upgrade(current, latest),
                }
            )

        return packages

    # ------------------------------------------------------------------
    # npm check
    # ------------------------------------------------------------------

    def check_npm_packages(self) -> list:
        """Check for outdated npm packages in the frontend directory.

        Runs ``npm outdated --json`` in the frontend directory.  npm returns
        exit code 1 when outdated packages exist, so we must inspect stdout
        regardless of the return code.

        Returns:
            List of dicts with keys: name, current, wanted, latest, upgrade_type.
        """
        if not self.frontend_dir.exists():
            logger.warning(
                "Frontend directory not found: %s -- skipping npm check",
                self.frontend_dir,
            )
            return []

        try:
            result = subprocess.run(
                ["npm", "outdated", "--json"],
                capture_output=True,
                text=True,
                cwd=str(self.frontend_dir),
                timeout=120,
            )
        except FileNotFoundError:
            logger.warning("npm not found -- skipping npm package check")
            return []
        except subprocess.TimeoutExpired:
            logger.warning("npm outdated timed out after 120s")
            return []

        # npm returns exit code 1 when outdated packages exist -- that is normal
        stdout = result.stdout.strip()
        if not stdout:
            return []

        try:
            outdated_raw = json.loads(stdout)
        except json.JSONDecodeError:
            logger.error("Failed to parse npm JSON output")
            return []

        # npm outdated --json returns a dict when packages are outdated,
        # but may return an empty list [] or other non-dict when none are
        if not isinstance(outdated_raw, dict):
            return []

        packages = []
        for name, info in outdated_raw.items():
            current = info.get("current", "")
            wanted = info.get("wanted", "")
            latest = info.get("latest", "")

            packages.append(
                {
                    "name": name,
                    "current": current,
                    "wanted": wanted,
                    "latest": latest,
                    "upgrade_type": self.classify_upgrade(current, latest) if current and latest else "unknown",
                }
            )

        return packages

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_report(self, pip_results: list, npm_results: list) -> dict:
        """Build a structured report dict from raw check results.

        Args:
            pip_results: Output of :meth:`check_pip_packages`.
            npm_results: Output of :meth:`check_npm_packages`.

        Returns:
            Report dict with counts, breakdown by upgrade type, and full
            package lists.
        """
        def _count_type(pkgs, upgrade_type):
            return sum(1 for p in pkgs if p.get("upgrade_type") == upgrade_type)

        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "pip_outdated_count": len(pip_results),
            "npm_outdated_count": len(npm_results),
            "pip_major": _count_type(pip_results, "major"),
            "pip_minor": _count_type(pip_results, "minor"),
            "pip_patch": _count_type(pip_results, "patch"),
            "npm_major": _count_type(npm_results, "major"),
            "npm_minor": _count_type(npm_results, "minor"),
            "npm_patch": _count_type(npm_results, "patch"),
            "pip_packages": pip_results,
            "npm_packages": npm_results,
        }

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def format_text_report(self, report: dict) -> str:
        """Produce a human-readable text report for console output.

        Args:
            report: Structured report dict from :meth:`generate_report`.

        Returns:
            Multi-line string formatted for terminal display.
        """
        lines = []
        lines.append("=" * 60)
        lines.append("  DEPENDENCY UPDATE REPORT")
        lines.append("  Generated: {}".format(report["timestamp"]))
        lines.append("=" * 60)
        lines.append("")

        # Summary
        pip_total = report["pip_outdated_count"]
        npm_total = report["npm_outdated_count"]
        total = pip_total + npm_total

        if total == 0:
            lines.append("[OK] All packages are up to date.")
            lines.append("")
            return "\n".join(lines)

        lines.append("[REPORT] Summary")
        lines.append("  Python (pip): {} outdated ({} major, {} minor, {} patch)".format(
            pip_total, report["pip_major"], report["pip_minor"], report["pip_patch"],
        ))
        lines.append("  Node (npm):   {} outdated ({} major, {} minor, {} patch)".format(
            npm_total, report["npm_major"], report["npm_minor"], report["npm_patch"],
        ))
        lines.append("")

        # Detailed pip packages grouped by upgrade type
        if pip_total > 0:
            lines.append("-" * 60)
            lines.append("  Python Packages (pip)")
            lines.append("-" * 60)
            for upgrade_type in ("major", "minor", "patch", "unknown"):
                pkgs = [p for p in report["pip_packages"] if p["upgrade_type"] == upgrade_type]
                if not pkgs:
                    continue
                for p in pkgs:
                    tag = "[{}]".format(upgrade_type.upper())
                    req_info = ""
                    if p.get("requirements_file"):
                        req_info = "  ({})".format(p["requirements_file"])
                    lines.append("  {} {} {} -> {}{}".format(
                        tag, p["name"], p["current"], p["latest"], req_info,
                    ))
            lines.append("")

        # Detailed npm packages grouped by upgrade type
        if npm_total > 0:
            lines.append("-" * 60)
            lines.append("  Node Packages (npm)")
            lines.append("-" * 60)
            for upgrade_type in ("major", "minor", "patch", "unknown"):
                pkgs = [p for p in report["npm_packages"] if p["upgrade_type"] == upgrade_type]
                if not pkgs:
                    continue
                for p in pkgs:
                    tag = "[{}]".format(upgrade_type.upper())
                    lines.append("  {} {} {} -> {}".format(
                        tag, p["name"], p["current"], p["latest"],
                    ))
            lines.append("")

        return "\n".join(lines)

    def format_discord_embed(self, report: dict) -> dict:
        """Build a Discord embed dict for webhook posting.

        Args:
            report: Structured report dict from :meth:`generate_report`.

        Returns:
            Embed dict compatible with :func:`src.utils.discord.post_embed`.
        """
        total = report["pip_outdated_count"] + report["npm_outdated_count"]
        color = 0xFFD600 if total > 0 else 0x00C853  # gold if outdated, green if current

        fields = [
            {
                "name": "Python (pip)",
                "value": "{} outdated ({} major, {} minor, {} patch)".format(
                    report["pip_outdated_count"],
                    report["pip_major"],
                    report["pip_minor"],
                    report["pip_patch"],
                ),
                "inline": True,
            },
            {
                "name": "Node (npm)",
                "value": "{} outdated ({} major, {} minor, {} patch)".format(
                    report["npm_outdated_count"],
                    report["npm_major"],
                    report["npm_minor"],
                    report["npm_patch"],
                ),
                "inline": True,
            },
        ]

        # List top 5 major updates if any
        major_pkgs = [
            p for p in report["pip_packages"] + report["npm_packages"]
            if p.get("upgrade_type") == "major"
        ]
        if major_pkgs:
            top5 = major_pkgs[:5]
            detail_lines = []
            for p in top5:
                detail_lines.append(
                    "{}: {} -> {}".format(p["name"], p["current"], p["latest"])
                )
            fields.append(
                {
                    "name": "Top Major Updates",
                    "value": "\n".join(detail_lines),
                    "inline": False,
                }
            )

        description = ""
        if total == 0:
            description = "All packages are up to date."
        else:
            description = "{} package(s) have updates available.".format(total)

        embed = {
            "title": "Dependency Update Report",
            "description": description,
            "color": color,
            "fields": fields,
            "footer": {"text": "Run: python scripts/devops/upgrade_packages.py --dry-run"},
            "timestamp": report["timestamp"],
        }

        return embed

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_report(self, report: dict) -> Path:
        """Save report as JSON to the reports directory.

        Args:
            report: Structured report dict from :meth:`generate_report`.

        Returns:
            Path to the saved JSON file.
        """
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        filename = "deps_{}.json".format(date_str)
        filepath = self.report_dir / filename

        with open(filepath, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)

        print("[OK] Report saved to {}".format(filepath))
        return filepath

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def send_notifications(self, report: dict) -> None:
        """Send Discord and email notifications if there are outdated packages.

        Skips silently when no packages are outdated or when notification
        credentials are not configured.  Notification failures are non-fatal.

        Args:
            report: Structured report dict from :meth:`generate_report`.
        """
        total = report["pip_outdated_count"] + report["npm_outdated_count"]
        if total == 0:
            print("[OK] All packages current -- no notifications needed")
            return

        # Discord notification
        webhook_url = os.getenv("DISCORD_ALERTS_WEBHOOK_URL", "")
        if webhook_url:
            try:
                from src.utils.discord import post_embed

                embed = self.format_discord_embed(report)
                success = post_embed(webhook_url, embed)
                if success:
                    print("[OK] Discord notification sent")
                else:
                    print("[WARN] Discord notification failed")
            except Exception as exc:
                try:
                    print("[WARN] Discord notification error: {}".format(exc))
                except UnicodeEncodeError:
                    print("[WARN] Discord notification error: {}".format(ascii(str(exc))))
        else:
            print("[WARN] DISCORD_ALERTS_WEBHOOK_URL not set -- skipping Discord")

        # Email notification
        admin_email = os.getenv("ADMIN_EMAIL", "") or os.getenv("ALERT_EMAIL", "")
        if admin_email:
            try:
                from src.automation.email_service import EmailService

                service = EmailService()
                subject = "Dependency Report: {} outdated package(s)".format(total)
                body = self.format_text_report(report)
                service.send_email(
                    to_email=admin_email,
                    subject=subject,
                    message=body,
                    html=False,
                    email_type="Alert",
                )
                print("[OK] Email notification sent to admin")
            except Exception as exc:
                try:
                    print("[WARN] Email notification error: {}".format(exc))
                except UnicodeEncodeError:
                    print("[WARN] Email notification error: {}".format(ascii(str(exc))))
        else:
            print("[WARN] ADMIN_EMAIL not set -- skipping email notification")

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, notify: bool = True, pip_only: bool = False, npm_only: bool = False) -> dict:
        """Run the full dependency check pipeline.

        Args:
            notify: Send Discord/email notifications if outdated packages found.
            pip_only: Only check pip packages.
            npm_only: Only check npm packages.

        Returns:
            Structured report dict.
        """
        print("[CHECK] Starting dependency check...")
        print("")

        pip_results = []
        npm_results = []

        if not npm_only:
            print("[CHECK] Checking Python (pip) packages...")
            pip_results = self.check_pip_packages()
            print("  Found {} outdated pip package(s)".format(len(pip_results)))

        if not pip_only:
            print("[CHECK] Checking Node (npm) packages...")
            npm_results = self.check_npm_packages()
            print("  Found {} outdated npm package(s)".format(len(npm_results)))

        print("")

        report = self.generate_report(pip_results, npm_results)

        # Print text report
        text_report = self.format_text_report(report)
        print(text_report)

        # Save JSON report
        self.save_report(report)

        # Send notifications
        if notify:
            self.send_notifications(report)

        return report


def main():
    """CLI entry point for dependency monitoring."""
    parser = argparse.ArgumentParser(description="Check for outdated dependencies")
    parser.add_argument(
        "--no-notify",
        action="store_true",
        help="Skip notifications (Discord and email)",
    )
    parser.add_argument(
        "--pip-only",
        action="store_true",
        help="Check pip packages only",
    )
    parser.add_argument(
        "--npm-only",
        action="store_true",
        help="Check npm packages only",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output JSON to stdout instead of text report",
    )

    args = parser.parse_args()

    monitor = DependencyMonitor()
    report = monitor.run(
        notify=not args.no_notify,
        pip_only=args.pip_only,
        npm_only=args.npm_only,
    )

    if args.json_output:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
