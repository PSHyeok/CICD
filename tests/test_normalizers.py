from cicd_router.models import ManifestProjectChange, RepoManifestHook
from cicd_router.normalizers import normalize_repo_manifest


def test_repo_manifest_preserves_project_path_ownership() -> None:
    event = normalize_repo_manifest(
        RepoManifestHook(
            event_id="evt-7",
            manifest="default.xml",
            branch="main",
            revision="abc123",
            projects=[
                ManifestProjectChange(
                    name="platform/core", revision="111", changed_files=["src/a.py"]
                ),
                ManifestProjectChange(
                    name="apps/web", revision="222", changed_files=["web/index.ts"]
                ),
            ],
        )
    )
    assert event.repository_files == {
        "platform/core": ["src/a.py"],
        "apps/web": ["web/index.ts"],
    }
    assert event.metadata["project_revisions"]["apps/web"] == "222"

