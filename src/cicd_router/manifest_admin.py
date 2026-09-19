from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from .manifests import SqliteManifestProvider
from .models import RoutingManifest


def import_manifest(database: str | Path, manifest_file: str | Path) -> str:
    with Path(manifest_file).open(encoding="utf-8") as handle:
        manifest = RoutingManifest.model_validate(yaml.safe_load(handle))
    SqliteManifestProvider(database).replace(manifest)
    return manifest.manifest_version


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CI/CD routing manifest 관리 명령"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    import_command = commands.add_parser(
        "import", help="YAML manifest를 SQLite에 활성 버전으로 등록합니다."
    )
    import_command.add_argument("--db", required=True, help="SQLite 파일 경로")
    import_command.add_argument("--file", required=True, help="manifest YAML 경로")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "import":
        version = import_manifest(args.db, args.file)
        print(f"activated manifest: {version}")


if __name__ == "__main__":
    main()
