from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_DIST = "/dist"


def read_repo_file(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_frontend_build_output_path_is_consistent_across_configs():
    vite_config = read_repo_file("web-ui/vite.config.ts")
    dockerfile = read_repo_file("Dockerfile")
    frontend_dockerfile = read_repo_file("web-ui/Dockerfile")
    dockerignore = read_repo_file(".dockerignore")
    start_script = read_repo_file("start.sh")
    dockerignore_lines = dockerignore.splitlines()

    assert "path.resolve(__dirname, '../dist')" in vite_config
    assert (
        f"COPY --from=frontend-builder {ROOT_DIST} /app/dist" in dockerfile
    ), "Docker multi-stage copy must use the Vite build output path."
    assert (
        f"COPY --from=builder {ROOT_DIST} /usr/share/nginx/html"
        in frontend_dockerfile
    ), "Frontend-only Docker build must use the Vite build output path."
    assert "dist/" in dockerignore_lines
    assert "web-ui/dist" not in dockerignore_lines
    assert '[ ! -d "dist" ]' in start_script
    assert "cp -r web-ui/dist ./" not in start_script
