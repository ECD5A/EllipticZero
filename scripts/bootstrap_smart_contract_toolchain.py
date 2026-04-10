from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provision the local smart-contract toolchain used by EllipticZero."
    )
    parser.add_argument(
        "--solc-version",
        action="append",
        dest="solc_versions",
        default=None,
        help="Solidity compiler version to install into the project-managed cache. Repeat the flag to install multiple versions.",
    )
    parser.add_argument(
        "--managed-dir",
        default=None,
        help="Override the managed solc cache directory. Defaults to .ellipticzero/tooling/solcx.",
    )
    parser.add_argument(
        "--skip-solc",
        action="store_true",
        help="Skip managed solc installation and only print the current toolchain state.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    managed_dir = Path(args.managed_dir) if args.managed_dir else root / ".ellipticzero" / "tooling" / "solcx"
    managed_dir.mkdir(parents=True, exist_ok=True)

    try:
        from solcx import get_installed_solc_versions, install_solc
        from solcx.install import SOLCX_BINARY_PATH_VARIABLE, get_executable
    except ImportError:
        print("py-solc-x is not installed in the current environment.", file=sys.stderr)
        print("Install a profile that includes smart-contract tooling first.", file=sys.stderr)
        return 2

    installed_versions = [str(version) for version in get_installed_solc_versions(solcx_binary_path=managed_dir)]
    requested_versions = [item.strip() for item in (args.solc_versions or ["0.8.20", "0.8.24", "0.8.25", "0.8.30"]) if item.strip()]
    os.environ[SOLCX_BINARY_PATH_VARIABLE] = str(managed_dir)

    if args.skip_solc:
        print(f"Managed solc directory: {managed_dir}")
        print(f"Installed versions: {', '.join(installed_versions) if installed_versions else 'none'}")
        return 0

    for version in requested_versions:
        if version not in installed_versions:
            print(f"Installing managed solc {version} into {managed_dir} ...")
            install_solc(version, show_progress=False, solcx_binary_path=managed_dir)
        else:
            print(f"Managed solc {version} already installed in {managed_dir}.")
        executable = get_executable(version, solcx_binary_path=managed_dir)
        print(f"Managed solc ready: {executable}")

    final_versions = [str(version) for version in get_installed_solc_versions(solcx_binary_path=managed_dir)]
    print(f"Installed versions: {', '.join(final_versions) if final_versions else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
