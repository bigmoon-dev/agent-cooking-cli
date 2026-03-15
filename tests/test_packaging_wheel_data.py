import os
import subprocess
import sys
from pathlib import Path


def test_wheel_includes_profiles_and_acceptance_cases(tmp_path: Path):
    project_root = Path(__file__).resolve().parents[1]

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    # Build wheel
    subprocess.check_call(
        [sys.executable, "setup.py", "bdist_wheel", "-d", str(dist_dir)],
        cwd=str(project_root),
        env={**os.environ},
    )

    wheels = list(dist_dir.glob("*.whl"))
    assert wheels, "wheel not built"
    wheel_path = wheels[0]

    # Install wheel into an isolated target dir (no venv needed)
    target = tmp_path / "site"
    target.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(target), str(wheel_path)],
        env={**os.environ},
    )

    # Verify data files exist in installed package
    pkg_dir = target / "triageflow"
    assert (pkg_dir / "profiles" / "embedded_system_v1.yaml").exists()
    assert (pkg_dir / "acceptance" / "cases" / "001_golden_path_embedded.yaml").exists()
