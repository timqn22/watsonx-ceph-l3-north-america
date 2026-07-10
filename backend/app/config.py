"""Application configuration.

All settings load from environment variables / a local ``.env`` file via
pydantic-settings. No secrets live in code. Every field has a safe default so
the app boots with zero configuration (using local/fake fallbacks), which keeps
the demo runnable before real credentials are provisioned.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings, populated from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database ---
    database_url: str = "sqlite:///./trackerassist.db"

    # --- Redmine ---
    redmine_url: str = "https://tracker.ceph.com"
    redmine_api_key: str | None = None
    redmine_project_id: str | None = None

    # --- GitHub ---
    github_token: str | None = None
    github_repos: str = "ceph/ceph"

    # --- watsonx.ai ---
    watsonx_api_key: str | None = None
    watsonx_project_id: str | None = None
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"
    watsonx_embed_model_id: str = "ibm/granite-embedding-278m-multilingual"
    embedder_backend: str = "auto"  # auto | watsonx | local | hash
    # Local (Hugging Face) embedding model used by the LocalEmbedder backend.
    # Defaults to IBM's open Granite embedding model -- real Granite, no quota.
    local_embed_model: str = "ibm-granite/granite-embedding-278m-multilingual"

    # --- Matching / scheduling ---
    link_min_similarity: float = 0.72
    # Higher bar for declaring an issue "already being worked on" by a PR.
    in_progress_min_similarity: float = 0.82
    # Granite cosine has a high domain baseline (unrelated Ceph items still
    # score ~0.7 because they share jargon). We subtract this floor and rescale
    # so the *displayed* confidence is meaningful; cos<=floor -> 0% confidence.
    similarity_floor: float = 0.70
    # Only surface a "possible match" PR on an issue page above this raw cosine,
    # and never show more than this many.
    related_pr_min_similarity: float = 0.80
    related_pr_limit: int = 3
    sync_open_minutes: int = 15
    sync_closed_hours: int = 6
    max_issues: int = 2000
    max_pulls: int = 500

    # --- Local ingest ---
    raw_issues_dir: str | None = None

    # --- Dashboard ---
    # If set, the /dashboard page requires ?token=<this>. Blank = open (fine on
    # localhost for a demo).
    dashboard_token: str | None = None
    # If set, POST /admin/rescrape requires ?token=<this> (or X-Admin-Token
    # header). Blank = open. This is a state-changing endpoint, so set it in any
    # shared/hosted deployment.
    admin_token: str | None = None

    @property
    def github_repo_list(self) -> list[str]:
        """Parse GITHUB_REPOS into a clean list of ``owner/name`` strings."""
        return [r.strip() for r in self.github_repos.split(",") if r.strip()]

    @property
    def watsonx_configured(self) -> bool:
        """True when enough watsonx credentials are present for real Granite calls."""
        return bool(self.watsonx_api_key and self.watsonx_project_id)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (read once per process)."""
    return Settings()
