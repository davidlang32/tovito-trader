"""
Package Upgrade Script
======================

Interactive upgrade script that applies dependency upgrades in the dev
environment, runs tests, and reports results. Never auto-deploys to production.

Usage:
    python scripts/devops/upgrade_packages.py --all-minor
    python scripts/devops/upgrade_packages.py --package fastapi
    python scripts/devops/upgrade_packages.py --dry-run --all-minor
    python scripts/devops/upgrade_packages.py --npm --all-minor
    python scripts/devops/upgrade_packages.py --rollback 2026-02-26_150000
    python scripts/devops/upgrade_packages.py --list-snapshots
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import os
import sys
import re
import json
import shutil
import argparse
import subprocess
import time
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.safe_logging import get_safe_logger

logger = get_safe_logger(__name__)


class PackageUpgrader:
    """
    Manages dependency upgrades in the development environment.

    Safety guards:
    - Refuses to run if TOVITO_ENV=production
    - Creates file snapshots before any changes
    - Runs test suite after upgrades to verify nothing breaks
    - Never commits, pushes, or deploys -- leaves that for the user
    """

    def __init__(self, project_root=None):
        self.project_root = Path(project_root or PROJECT_ROOT)
        self.frontend_dir = (
            self.project_root / 'apps' / 'investor_portal'
            / 'frontend' / 'investor_portal'
        )
        self.snapshot_dir = self.project_root / 'data' / 'devops' / 'upgrade_snapshots'
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Environment check
    # ------------------------------------------------------------------

    def check_environment(self):
        """
        Verify we are running in the development environment.

        Returns:
            bool: True if safe to proceed, False if production.
        """
        env = os.environ.get('TOVITO_ENV', 'development')
        if env == 'production':
            print('[ERROR] Refusing to run in production environment.')
            return False
        print('[OK] Environment: development')
        return True

    # ------------------------------------------------------------------
    # Pre-upgrade backup
    # ------------------------------------------------------------------

    def pre_upgrade_backup(self):
        """
        Snapshot current dependency files before making changes.

        Returns:
            dict: snapshot_dir path, list of copied files, db_backup_status.
        """
        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        snap_dir = self.snapshot_dir / timestamp
        snap_dir.mkdir(parents=True, exist_ok=True)

        copied_files = []

        # Python requirements files
        for fname in ('requirements.txt', 'requirements-full.txt'):
            src = self.project_root / fname
            if src.exists():
                shutil.copy2(str(src), str(snap_dir / fname))
                copied_files.append(fname)

        # npm dependency files
        for fname in ('package.json', 'package-lock.json'):
            src = self.frontend_dir / fname
            if src.exists():
                shutil.copy2(str(src), str(snap_dir / fname))
                copied_files.append(fname)

        # Database backup (non-fatal)
        db_backup_status = 'skipped'
        try:
            from scripts.utilities.backup_database import DatabaseBackup
            result = DatabaseBackup().create_backup()
            db_backup_status = result.get('status', 'unknown')
        except Exception as exc:
            try:
                db_backup_status = f'failed: {exc}'
            except UnicodeEncodeError:
                db_backup_status = f'failed: {ascii(exc)}'

        print(f'[BACKUP] Snapshot created: {snap_dir}')
        for f in copied_files:
            print(f'  - {f}')
        print(f'  Database backup: {db_backup_status}')

        return {
            'snapshot_dir': str(snap_dir),
            'files_copied': copied_files,
            'db_backup_status': db_backup_status,
        }

    # ------------------------------------------------------------------
    # Outdated package discovery
    # ------------------------------------------------------------------

    def get_outdated_packages(self):
        """
        Query pip for outdated packages and classify each upgrade type.

        Returns:
            list[dict]: Each dict has name, current, latest, upgrade_type
                        (major / minor / patch).
        """
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'list', '--outdated', '--format=json'],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f'[WARN] pip list --outdated returned exit code {result.returncode}')
            return []

        try:
            raw = json.loads(result.stdout)
        except json.JSONDecodeError:
            print('[WARN] Could not parse pip outdated output.')
            return []

        packages = []
        for pkg in raw:
            name = pkg.get('name', '')
            current = pkg.get('version', '0.0.0')
            latest = pkg.get('latest_version', current)
            upgrade_type = self._classify_upgrade(current, latest)
            packages.append({
                'name': name,
                'current': current,
                'latest': latest,
                'upgrade_type': upgrade_type,
            })

        return packages

    @staticmethod
    def _classify_upgrade(current_str, latest_str):
        """
        Compare two version strings and return 'major', 'minor', or 'patch'.

        Uses packaging.version.Version when available, falls back to simple
        tuple comparison on dotted segments.
        """
        try:
            from packaging.version import Version
            cur = Version(current_str)
            lat = Version(latest_str)
            if lat.major != cur.major:
                return 'major'
            if lat.minor != cur.minor:
                return 'minor'
            return 'patch'
        except Exception:
            # Fallback: split on dots
            cur_parts = [int(x) for x in re.findall(r'\d+', current_str)]
            lat_parts = [int(x) for x in re.findall(r'\d+', latest_str)]
            # Pad to at least 3 segments
            while len(cur_parts) < 3:
                cur_parts.append(0)
            while len(lat_parts) < 3:
                lat_parts.append(0)
            if lat_parts[0] != cur_parts[0]:
                return 'major'
            if lat_parts[1] != cur_parts[1]:
                return 'minor'
            return 'patch'

    # ------------------------------------------------------------------
    # pip upgrades
    # ------------------------------------------------------------------

    def upgrade_pip_packages(self, packages=None, all_minor=False, dry_run=False):
        """
        Upgrade Python packages via pip.

        Args:
            packages: List of specific package names to upgrade to latest.
            all_minor: If True, upgrade all packages with minor/patch updates
                       (skip major).
            dry_run: If True, only print what would happen.

        Returns:
            dict: upgraded, failed, skipped lists.
        """
        outdated = self.get_outdated_packages()
        if not outdated:
            print('[OK] All Python packages are up to date.')
            return {'upgraded': [], 'failed': [], 'skipped': []}

        # Decide which packages to upgrade
        targets = []
        skipped = []
        if packages:
            pkg_set = {p.lower() for p in packages}
            for pkg in outdated:
                if pkg['name'].lower() in pkg_set:
                    targets.append(pkg)
                else:
                    skipped.append(pkg)
        elif all_minor:
            for pkg in outdated:
                if pkg['upgrade_type'] in ('minor', 'patch'):
                    targets.append(pkg)
                else:
                    skipped.append(pkg)
        else:
            # Nothing selected -- show what is available and skip all
            print('[INFO] Outdated Python packages:')
            for pkg in outdated:
                print(f'  {pkg["name"]}: {pkg["current"]} -> {pkg["latest"]} ({pkg["upgrade_type"]})')
            print('[INFO] Use --all-minor or --package NAME to upgrade.')
            return {'upgraded': [], 'failed': [], 'skipped': outdated}

        if not targets:
            print('[OK] No matching Python packages to upgrade.')
            return {'upgraded': [], 'failed': [], 'skipped': skipped}

        upgraded = []
        failed = []

        for pkg in targets:
            spec = f'{pkg["name"]}=={pkg["latest"]}'
            if dry_run:
                print(f'[DRY-RUN] Would upgrade: {pkg["name"]} {pkg["current"]} -> {pkg["latest"]}')
                upgraded.append(pkg)
                continue

            print(f'[UPGRADE] {pkg["name"]} {pkg["current"]} -> {pkg["latest"]} ...', end=' ')
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', spec],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print('[OK]')
                upgraded.append(pkg)
            else:
                print('[FAILED]')
                failed.append({**pkg, 'error': result.stderr[:200]})

        return {'upgraded': upgraded, 'failed': failed, 'skipped': skipped}

    # ------------------------------------------------------------------
    # npm upgrades
    # ------------------------------------------------------------------

    def upgrade_npm_packages(self, packages=None, all_minor=False, dry_run=False):
        """
        Upgrade npm packages in the frontend directory.

        Args:
            packages: List of specific package names.
            all_minor: If True, run npm update (minor/patch only by semver).
            dry_run: If True, only print what would happen.

        Returns:
            dict: upgraded, failed, skipped lists.
        """
        if not self.frontend_dir.exists():
            print('[WARN] Frontend directory not found; skipping npm upgrades.')
            return {'upgraded': [], 'failed': [], 'skipped': []}

        npm_cmd = shutil.which('npm')
        if not npm_cmd:
            print('[WARN] npm not found on PATH; skipping npm upgrades.')
            return {'upgraded': [], 'failed': [], 'skipped': []}

        upgraded = []
        failed = []
        skipped = []

        if packages:
            for pkg_name in packages:
                if dry_run:
                    print(f'[DRY-RUN] Would npm install {pkg_name}@latest')
                    upgraded.append({'name': pkg_name})
                    continue

                print(f'[UPGRADE] npm install {pkg_name}@latest ...', end=' ')
                result = subprocess.run(
                    [npm_cmd, 'install', f'{pkg_name}@latest'],
                    capture_output=True,
                    text=True,
                    cwd=str(self.frontend_dir),
                )
                if result.returncode == 0:
                    print('[OK]')
                    upgraded.append({'name': pkg_name})
                else:
                    print('[FAILED]')
                    failed.append({'name': pkg_name, 'error': result.stderr[:200]})

        elif all_minor:
            if dry_run:
                print('[DRY-RUN] Would run: npm update')
                result = subprocess.run(
                    [npm_cmd, 'outdated', '--json'],
                    capture_output=True,
                    text=True,
                    cwd=str(self.frontend_dir),
                )
                try:
                    outdated = json.loads(result.stdout) if result.stdout.strip() else {}
                    for name, info in outdated.items():
                        print(f'  {name}: {info.get("current", "?")} -> {info.get("wanted", "?")}')
                        upgraded.append({'name': name})
                except json.JSONDecodeError:
                    pass
            else:
                print('[UPGRADE] Running npm update ...')
                result = subprocess.run(
                    [npm_cmd, 'update'],
                    capture_output=True,
                    text=True,
                    cwd=str(self.frontend_dir),
                )
                if result.returncode == 0:
                    print('[OK] npm update completed.')
                    upgraded.append({'name': '_npm_update_'})
                else:
                    print('[FAILED] npm update failed.')
                    failed.append({'name': '_npm_update_', 'error': result.stderr[:200]})
        else:
            print('[INFO] Use --all-minor or --package NAME to upgrade npm packages.')

        return {'upgraded': upgraded, 'failed': failed, 'skipped': skipped}

    # ------------------------------------------------------------------
    # Test suite runner
    # ------------------------------------------------------------------

    def run_test_suite(self):
        """
        Run the full pytest suite and parse results.

        Returns:
            dict: passed, failed, errors, total, duration_seconds,
                  output_tail (last 20 lines), exit_code.
        """
        print('[TEST] Running pytest tests/ -v --tb=short ...')
        start = time.time()
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', 'tests/', '-v', '--tb=short'],
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
        )
        duration = time.time() - start

        output_lines = result.stdout.splitlines()
        output_tail = output_lines[-20:] if len(output_lines) >= 20 else output_lines

        passed = 0
        failed = 0
        errors = 0

        # pytest summary line looks like: "806 passed, 2 failed, 1 error in 45.23s"
        for line in reversed(output_lines):
            match_passed = re.search(r'(\d+)\s+passed', line)
            match_failed = re.search(r'(\d+)\s+failed', line)
            match_errors = re.search(r'(\d+)\s+error', line)
            if match_passed or match_failed or match_errors:
                if match_passed:
                    passed = int(match_passed.group(1))
                if match_failed:
                    failed = int(match_failed.group(1))
                if match_errors:
                    errors = int(match_errors.group(1))
                break

        total = passed + failed + errors

        if result.returncode == 0:
            print(f'[TEST] {passed} passed in {duration:.1f}s')
        else:
            print(f'[TEST] {passed} passed, {failed} failed, {errors} errors in {duration:.1f}s')

        return {
            'passed': passed,
            'failed': failed,
            'errors': errors,
            'total': total,
            'duration_seconds': round(duration, 1),
            'output_tail': output_tail,
            'exit_code': result.returncode,
        }

    # ------------------------------------------------------------------
    # Update requirements files on disk
    # ------------------------------------------------------------------

    def update_requirements_files(self, upgraded_packages):
        """
        Update version constraints in requirements.txt and requirements-full.txt
        to reflect newly upgraded packages.

        Only updates lines that already mention the package (direct dependencies).
        Transitive-only dependencies are skipped.

        Args:
            upgraded_packages: list of dicts with 'name' and 'latest' keys.

        Returns:
            list[str]: File names that were modified.
        """
        req_files = ['requirements.txt', 'requirements-full.txt']
        modified = []

        for req_file in req_files:
            path = self.project_root / req_file
            if not path.exists():
                continue

            content = path.read_text(encoding='utf-8')
            original = content

            for pkg in upgraded_packages:
                name = pkg.get('name', '')
                latest = pkg.get('latest', '')
                if not name or not latest:
                    continue

                # Match lines like: package>=1.2.3  or  package==1.2.3
                # Package names in requirements can use hyphens or underscores
                # pip normalises both, so we match either form
                escaped = re.escape(name)
                # Allow hyphen/underscore interchangeability
                flexible_name = escaped.replace(r'\-', r'[\-_]').replace(r'\_', r'[\-_]')
                pattern = re.compile(
                    rf'^({flexible_name}\s*(?:>=|==|~=)\s*)[\d][^\s#]*',
                    re.IGNORECASE | re.MULTILINE,
                )
                new_content, count = pattern.subn(rf'\g<1>{latest}', content)
                if count > 0:
                    content = new_content

            if content != original:
                path.write_text(content, encoding='utf-8')
                modified.append(req_file)
                print(f'[OK] Updated {req_file}')

        if not modified:
            print('[INFO] No requirements files needed updating (transitive deps only).')

        return modified

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def rollback(self, snapshot_date):
        """
        Restore dependency files from a previous snapshot and re-install.

        Args:
            snapshot_date: Directory name (YYYY-MM-DD_HHMMSS) under
                           data/devops/upgrade_snapshots/.

        Returns:
            dict: status, details.
        """
        snap_dir = self.snapshot_dir / snapshot_date
        if not snap_dir.exists():
            print(f'[ERROR] Snapshot not found: {snap_dir}')
            return {'status': 'error', 'detail': 'Snapshot not found.'}

        print(f'[ROLLBACK] Restoring from {snap_dir} ...')
        restored = []

        # Restore Python requirements
        for fname in ('requirements.txt', 'requirements-full.txt'):
            src = snap_dir / fname
            if src.exists():
                dst = self.project_root / fname
                shutil.copy2(str(src), str(dst))
                restored.append(fname)
                print(f'  Restored {fname}')

        # Re-install Python packages from the restored full requirements
        full_req = self.project_root / 'requirements-full.txt'
        if full_req.exists():
            print('[ROLLBACK] Re-installing Python packages ...')
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '-r', str(full_req)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                print('[WARN] pip install returned errors during rollback.')

        # Restore npm files
        npm_cmd = shutil.which('npm')
        for fname in ('package.json', 'package-lock.json'):
            src = snap_dir / fname
            if src.exists():
                dst = self.frontend_dir / fname
                shutil.copy2(str(src), str(dst))
                restored.append(fname)
                print(f'  Restored {fname}')

        if npm_cmd and (snap_dir / 'package.json').exists():
            print('[ROLLBACK] Re-installing npm packages ...')
            subprocess.run(
                [npm_cmd, 'install'],
                capture_output=True,
                text=True,
                cwd=str(self.frontend_dir),
            )

        print(f'[OK] Rollback complete. Restored: {", ".join(restored)}')
        return {'status': 'success', 'restored': restored}

    # ------------------------------------------------------------------
    # List snapshots
    # ------------------------------------------------------------------

    def list_snapshots(self):
        """Print available upgrade snapshots."""
        if not self.snapshot_dir.exists():
            print('[INFO] No snapshots found.')
            return

        dirs = sorted(
            [d for d in self.snapshot_dir.iterdir() if d.is_dir()],
            reverse=True,
        )
        if not dirs:
            print('[INFO] No snapshots found.')
            return

        print('Available snapshots:')
        for d in dirs:
            files = [f.name for f in d.iterdir() if f.is_file()]
            print(f'  {d.name}  ({", ".join(files)})')

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def generate_upgrade_summary(self, snapshot, pip_results, npm_results, test_results):
        """
        Print a formatted upgrade summary with next steps.

        Args:
            snapshot: dict from pre_upgrade_backup().
            pip_results: dict from upgrade_pip_packages().
            npm_results: dict from upgrade_npm_packages() (may be None).
            test_results: dict from run_test_suite() (may be None for dry-run).
        """
        pip_upgraded = pip_results.get('upgraded', [])
        pip_failed = pip_results.get('failed', [])
        pip_skipped = pip_results.get('skipped', [])

        minor_count = sum(1 for p in pip_upgraded if p.get('upgrade_type') == 'minor')
        patch_count = sum(1 for p in pip_upgraded if p.get('upgrade_type') == 'patch')
        major_count = sum(1 for p in pip_upgraded if p.get('upgrade_type') == 'major')

        npm_upgraded = (npm_results or {}).get('upgraded', [])

        sep = '=' * 60

        print()
        print(sep)
        print('UPGRADE SUMMARY')
        print(sep)
        print(f'Snapshot: {snapshot.get("snapshot_dir", "N/A")}')
        print()
        print('Python Packages:')
        parts = []
        if minor_count:
            parts.append(f'{minor_count} minor')
        if patch_count:
            parts.append(f'{patch_count} patch')
        if major_count:
            parts.append(f'{major_count} major')
        detail = f' ({", ".join(parts)})' if parts else ''
        print(f'  Upgraded: {len(pip_upgraded)}{detail}')
        print(f'  Failed:   {len(pip_failed)}')
        print(f'  Skipped:  {len(pip_skipped)} (major version changes)')
        print()
        print('npm Packages:')
        print(f'  Upgraded: {len(npm_upgraded)}')

        if test_results:
            print()
            print('Test Results:')
            print(f'  Passed:  {test_results["passed"]}')
            print(f'  Failed:  {test_results["failed"]}')
            print(f'  Duration: {test_results["duration_seconds"]}s')

            if test_results['exit_code'] == 0:
                print('  Status: [OK] ALL TESTS PASSED')
                print()
                print(sep)
                # Build concise commit message hint
                upgrade_descs = []
                for p in pip_upgraded:
                    upgrade_descs.append(f'{p["name"]} {p["current"]}->{p["latest"]}')
                commit_hint = ', '.join(upgrade_descs[:5])
                if len(upgrade_descs) > 5:
                    commit_hint += f', +{len(upgrade_descs) - 5} more'

                print('NEXT STEPS (manual):')
                print('  git add requirements.txt requirements-full.txt')
                print(f'  git commit -m "Upgrade: {commit_hint}"')
                print('  git push origin main')
                print('  railway up')
                print(sep)
            else:
                print('  Status: [ERROR] TESTS FAILED')
                print()
                print(sep)
                print('[ERROR] TESTS FAILED - upgrades NOT safe to promote')
                print()
                snap_name = Path(snapshot.get('snapshot_dir', '')).name
                print('To rollback:')
                print(f'  python scripts/devops/upgrade_packages.py --rollback {snap_name}')
                print(sep)
        else:
            # Dry-run -- no test results
            print()
            print(sep)
            print('[INFO] Dry-run complete. No packages were changed.')
            print(sep)

    # ------------------------------------------------------------------
    # Main orchestrator
    # ------------------------------------------------------------------

    def run(self, packages=None, all_minor=False, include_npm=False, dry_run=False):
        """
        Full upgrade workflow.

        1. check_environment() -- abort if production
        2. pre_upgrade_backup() -- snapshot current state
        3. get_outdated_packages() -- show what is available
        4. upgrade_pip_packages() -- apply upgrades
        5. if include_npm: upgrade_npm_packages()
        6. if not dry_run: run_test_suite()
        7. if tests pass and not dry_run: update_requirements_files()
        8. generate_upgrade_summary()

        NEVER commits, pushes, or deploys.
        """
        # 1. Safety guard
        if not self.check_environment():
            return

        # 2. Snapshot
        snapshot = self.pre_upgrade_backup()

        # 3. Show outdated packages
        outdated = self.get_outdated_packages()
        if outdated:
            print()
            print(f'[INFO] {len(outdated)} outdated Python package(s) found:')
            for pkg in outdated:
                print(f'  {pkg["name"]}: {pkg["current"]} -> {pkg["latest"]} ({pkg["upgrade_type"]})')
            print()
        else:
            print('[OK] All Python packages are up to date.')

        # 4. Upgrade pip packages
        pip_results = self.upgrade_pip_packages(
            packages=packages,
            all_minor=all_minor,
            dry_run=dry_run,
        )

        # 5. Optionally upgrade npm
        npm_results = None
        if include_npm:
            npm_results = self.upgrade_npm_packages(
                packages=packages,
                all_minor=all_minor,
                dry_run=dry_run,
            )

        # 6. Run tests (skip for dry runs)
        test_results = None
        if not dry_run:
            test_results = self.run_test_suite()

        # 7. Update requirements files if tests pass
        if test_results and test_results['exit_code'] == 0:
            self.update_requirements_files(pip_results.get('upgraded', []))

        # 8. Summary
        self.generate_upgrade_summary(snapshot, pip_results, npm_results, test_results)


# ======================================================================
# CLI
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Upgrade packages in dev environment'
    )
    parser.add_argument(
        '--all-minor',
        action='store_true',
        help='Upgrade all minor/patch packages',
    )
    parser.add_argument(
        '--package',
        type=str,
        help='Upgrade a specific package',
    )
    parser.add_argument(
        '--npm',
        action='store_true',
        help='Include npm packages',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would change without upgrading',
    )
    parser.add_argument(
        '--rollback',
        type=str,
        metavar='SNAPSHOT',
        help='Rollback to a specific snapshot (YYYY-MM-DD_HHMMSS)',
    )
    parser.add_argument(
        '--list-snapshots',
        action='store_true',
        help='List available snapshots',
    )
    args = parser.parse_args()

    upgrader = PackageUpgrader()

    if args.list_snapshots:
        upgrader.list_snapshots()
        return

    if args.rollback:
        if not upgrader.check_environment():
            return
        upgrader.rollback(args.rollback)
        return

    packages = [args.package] if args.package else None
    upgrader.run(
        packages=packages,
        all_minor=args.all_minor,
        include_npm=args.npm,
        dry_run=args.dry_run,
    )


if __name__ == '__main__':
    main()
