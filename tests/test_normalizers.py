from cicd_router.models import PerforceHook
from cicd_router.normalizers import normalize_perforce


def test_perforce_preserves_depot_path_ownership() -> None:
    event = normalize_perforce(
        PerforceHook(
            changelist=10425,
            depot="//Game/Main",
            branch="main",
            changed_files=["Source/Game.cpp", "Content/Hero.uasset"],
        )
    )
    assert event.event_id == "p4-10425"
    assert event.repository_files == {
        "//Game/Main": ["Source/Game.cpp", "Content/Hero.uasset"]
    }
