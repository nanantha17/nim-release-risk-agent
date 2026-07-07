import os, requests
from pydantic import BaseModel, Field
from nat.data_models.function import FunctionBaseConfig
from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

def _fetch_raw_stats(repo: str, max_commits: int) -> dict:
    """Helper to fetch and aggregate raw commit data from GitHub."""
    list_url = f"https://api.github.com/repos/{repo}/commits?per_page={max_commits}"
    list_resp = requests.get(list_url, headers=HEADERS)
    if list_resp.status_code != 200:
        return {}

    lines_added = 0
    lines_deleted = 0
    unique_authors = set()

    for commit in list_resp.json():
        email = commit.get("commit", {}).get("author", {}).get("email")
        if email:
            unique_authors.add(email)

        detail_url = commit.get("url")
        if detail_url:
            detail_resp = requests.get(detail_url, headers=HEADERS)
            if detail_resp.status_code == 200:
                stats = detail_resp.json().get("stats", {})
                lines_added += stats.get("additions", 0)
                lines_deleted += stats.get("deletions", 0)

    return {"added": lines_added, "deleted": lines_deleted, "authors": len(unique_authors)}
class RepoInput(BaseModel):
    repo: str = Field(description="GitHub repo as 'owner/name', e.g. 'microsoft/vscode'")

class RepoMetricsConfig(FunctionBaseConfig, name="github_metrics_toolkit"):
    max_commits: int = Field(default=10, description="Number of commits to scan")

class GetPRVelocityConfig(FunctionBaseConfig, name="get_pr_velocity"):
    pass

@register_function(config_type=GetPRVelocityConfig)
async def get_pr_velocity_tool(config: GetPRVelocityConfig, builder: Builder):
    async def _wrapper(repo: str) -> dict:
        resp = requests.get(f"https://api.github.com/repos/{repo}/pulls?state=closed&per_page=20", headers=HEADERS)
        prs = resp.json()
        return {"repo": repo, "closed_pr_count": len(prs)}
    yield FunctionInfo.from_fn(
        _wrapper,
        input_schema=RepoInput,
        description="Returns recent closed PR count for a GitHub repo as a proxy for PR merge velocity."
    )


class GetLinesChangedConfig(FunctionBaseConfig, name="get_lines_of_code_changed"):
    max_commits: int = Field(default=10, description="Number of commits to scan")

@register_function(config_type=GetLinesChangedConfig)
async def get_lines_changed_tool(config: GetLinesChangedConfig, builder: Builder):
    async def _wrapper(repo: str) -> dict:
        stats = _fetch_raw_stats(repo, config.max_commits)
        return {"repo": repo, "total_lines_changed": stats.get("added", 0) + stats.get("deleted", 0)}
    yield FunctionInfo.from_fn(_wrapper, input_schema=RepoInput,
        description="Returns total lines of code changed (additions + deletions) for a repository.")

class GetContributorCountConfig(FunctionBaseConfig, name="get_unique_contributor_count"):
    max_commits: int = Field(default=10, description="Number of commits to scan")

@register_function(config_type=GetContributorCountConfig)
async def get_contributor_count_tool(config: GetContributorCountConfig, builder: Builder):
    async def _wrapper(repo: str) -> dict:
        stats = _fetch_raw_stats(repo, config.max_commits)
        return {"repo": repo, "num_contributors": stats.get("authors", 0)}
    yield FunctionInfo.from_fn(_wrapper, input_schema=RepoInput,
        description="Returns the number of unique contributors active in recent commits.")



class ReleaseMetricsInput(BaseModel):
    package_name: str = Field(default="unknown", description="Name of the package or repo")
    version: str = Field(default="1.0.0", description="Version string")
    test_coverage: float = Field(default=70, description="Test coverage %")
    code_coverage: float = Field(default=70, description="Code coverage %")
    branch_coverage: float = Field(default=70, description="Branch coverage %")
    past_defects_total: int = Field(default=5, description="Total defects in last 3 releases")
    critical_defects: int = Field(default=0, description="Critical/P0 defects")
    defect_resolution_rate: float = Field(default=90, description="% defects resolved")
    cyclomatic_complexity: float = Field(default=10, description="Average cyclomatic complexity")
    lines_of_code_changed: int = Field(default=0, description="LOC changed")
    num_contributors: int = Field(default=1, description="Number of contributors")
    build_success_rate: float = Field(default=90, description="CI build success rate %")
    avg_pr_review_time_hours: float = Field(default=24, description="Avg PR review time")
    open_issues: int = Field(default=10, description="Open issues at release time")

class ScoreReleaseRiskConfig(FunctionBaseConfig, name="score_release_risk"):
    api_url: str = "http://localhost:8000/predict"


@register_function(config_type=ScoreReleaseRiskConfig)
async def score_release_risk_tool(config: ScoreReleaseRiskConfig, builder: Builder):
    async def _wrapper(package_name: str = "unknown", version: str = "1.0.0",
                        test_coverage: float = 70, code_coverage: float = 70,
                        branch_coverage: float = 70, past_defects_total: int = 5,
                        critical_defects: int = 0, defect_resolution_rate: float = 90,
                        cyclomatic_complexity: float = 10, lines_of_code_changed: int = 0,
                        num_contributors: int = 1, build_success_rate: float = 90,
                        avg_pr_review_time_hours: float = 24, open_issues: int = 10) -> dict:
        payload = {
            "package_name": package_name, "version": version,
            "test_coverage": test_coverage, "code_coverage": code_coverage,
            "branch_coverage": branch_coverage, "past_defects_total": past_defects_total,
            "critical_defects": critical_defects, "defect_resolution_rate": defect_resolution_rate,
            "cyclomatic_complexity": cyclomatic_complexity, "lines_of_code_changed": lines_of_code_changed,
            "num_contributors": num_contributors, "build_success_rate": build_success_rate,
            "avg_pr_review_time_hours": avg_pr_review_time_hours, "open_issues": open_issues,
        }
        resp = requests.post(config.api_url, json=payload)
        resp.raise_for_status()
        return resp.json()

    yield FunctionInfo.from_fn(
        _wrapper,
        input_schema=ReleaseMetricsInput,
        description=(
            "Sends release metrics to the risk predictor and returns risk_score, "
            "risk_level, confidence, and top risk factors. Fill lines_of_code_changed "
            "and num_contributors from gathered GitHub signals; use the field defaults "
            "for anything not directly available."
        ),
    )