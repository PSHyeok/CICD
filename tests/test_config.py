from pathlib import Path

from cicd_router.config import load_config


def test_example_config_is_valid() -> None:
    root = Path(__file__).parents[1]
    config = load_config(root / "config" / "policies.example.yaml")
    assert [policy.id for policy in config.pipelines] == [
        "backend-jenkins",
        "game-build-jenkins",
    ]
