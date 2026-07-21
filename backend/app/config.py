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

    # --- Security ---
    # Comma-separated list of allowed CORS origins. Default is localhost only.
    # In production set this to the actual extension origin(s) and dashboard host.
    # Example: chrome-extension://abcdefg,https://trackerassist.example.com
    cors_origins: str = "http://localhost,http://127.0.0.1"

    # Shared API key for the extension<->backend trust boundary. When set, all
    # mutating endpoints and profile reads require an `X-Api-Key: <value>` header
    # or `?api_key=<value>` query param. Blank = open (fine for local dev only).
    api_key: str | None = None

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
    # Only surface a "possible match" PR on an issue page above this raw cosine.
    # Issue<->PR pairs (problem vs fix) score lower than issue<->issue, so this
    # sits just above the calibration floor: weak matches still appear but show
    # an honest low confidence rather than being hidden. Raise it toward 0.80 if
    # the "possible matches" feel noisy; lower toward the floor to see more.
    related_pr_min_similarity: float = 0.74
    related_pr_limit: int = 3
    # Two-hop related PRs: only trackers at least this similar (issue<->issue
    # cosine, the strong signal) contribute their linked PRs as suggestions.
    related_via_issue_min_similarity: float = 0.80
    # Possible-duplicate warning on issue pages: only trackers above this
    # issue<->issue cosine are flagged. High bar on purpose -- a duplicate
    # warning must be high-precision or people stop trusting it.
    duplicate_min_similarity: float = 0.88
    duplicate_limit: int = 3

    # --- Hybrid scoring weights (content stays the base; these add bounded
    #     structural boosts/penalties). Grid-searched with scripts/tune_weights.py
    #     against 34k real #ref links: this combo scores 70.0% top-1 (vs 68.5% at
    #     the old 0.20/0.05/0.10). The branch match dominates; component is weak. ---
    # A tracker number encoded in the PR's head branch (near-decisive link).
    hybrid_branch_weight: float = 0.30
    # PR and issue point at the same Ceph subsystem/component (weak signal).
    hybrid_component_weight: float = 0.03
    # PR and issue clearly point at different components (precision penalty).
    hybrid_component_penalty: float = 0.05
    # Recommendations: boost issues in the user's historical components so
    # familiar-area work ranks higher even in a broad search. Content-primary.
    rec_component_weight: float = 0.05
    # Search: hybrid lexical + semantic. Weight of the title keyword-overlap
    # score added to the embedding cosine, so an exact-title match isn't buried
    # by dense similarity. 0 = pure semantic.
    search_lexical_weight: float = 0.5

    # --- Cross-encoder reranking (precision stage over the top-K) ---
    # Off by default; needs a one-time model download and adds latency.
    rerank_enabled: bool = False
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_top_k: int = 25  # how many embedding candidates to rerank
    rerank_min_score: float = 0.10  # drop candidates below this relevance
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
    def cors_origin_list(self) -> list[str]:
        """Parse CORS_ORIGINS into a list of allowed origins."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def watsonx_configured(self) -> bool:
        """True when enough watsonx credentials are present for real Granite calls."""
        return bool(self.watsonx_api_key and self.watsonx_project_id)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (read once per process)."""
    return Settings()
