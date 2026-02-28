import httpx
from datetime import datetime, timezone, timedelta
from backend.config import settings

GITHUB_BASE = "https://api.github.com"

def _get_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

async def get_daily_commits(repo: str = None) -> dict:
    """Get today's commits for the authenticated user."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()
    async with httpx.AsyncClient() as client:
        if repo:
            # Specific repo
            resp = await client.get(
                f"{GITHUB_BASE}/repos/{repo}/commits",
                params={"since": today, "author": settings.GITHUB_USERNAME},
                headers=_get_headers(),
            )
            resp.raise_for_status()
            commits = resp.json()
            return {
                "total": len(commits),
                "repos": [{
                    "name": repo.split("/")[-1],
                    "count": len(commits),
                }],
                "last_commit": commits[0]["commit"]["message"] if commits else "No commits today",
            }
        else:
            # Get user's repos and aggregate
            resp = await client.get(
                f"{GITHUB_BASE}/user/repos",
                params={"sort": "pushed", "per_page": 10},
                headers=_get_headers(),
            )
            resp.raise_for_status()
            repos = resp.json()

            total = 0
            repo_breakdown = []
            last_commit_msg = "No commits today"
            for r in repos[:5]:  # Check top 5 most recently pushed
                resp2 = await client.get(
                    f"{GITHUB_BASE}/repos/{r['full_name']}/commits",
                    params={"since": today, "author": settings.GITHUB_USERNAME},
                    headers=_get_headers(),
                )
                if resp2.status_code == 200:
                    commits = resp2.json()
                    if commits:
                        repo_breakdown.append({
                            "name": r["name"],
                            "count": len(commits),
                        })
                        total += len(commits)
                        if last_commit_msg == "No commits today":
                            last_commit_msg = commits[0]["commit"]["message"][:80]

            return {
                "total": total,
                "repos": repo_breakdown,
                "last_commit": last_commit_msg,
            }


async def get_open_prs() -> dict:
    """Get open pull requests for the authenticated user."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get PRs created by user
        resp = await client.get(
            f"{GITHUB_BASE}/search/issues",
            params={
                "q": f"type:pr state:open author:{settings.GITHUB_USERNAME}",
                "sort": "updated",
                "per_page": 10,
            },
            headers=_get_headers(),
        )
        resp.raise_for_status()
        created_prs = resp.json().get("items", [])
        
        # Get PRs where user is requested reviewer
        resp2 = await client.get(
            f"{GITHUB_BASE}/search/issues",
            params={
                "q": f"type:pr state:open review-requested:{settings.GITHUB_USERNAME}",
                "sort": "updated",
                "per_page": 10,
            },
            headers=_get_headers(),
        )
        review_prs = resp2.json().get("items", []) if resp2.status_code == 200 else []
        
        def format_pr(pr):
            return {
                "title": pr.get("title", "No title")[:60],
                "repo": pr.get("repository_url", "").split("/")[-1] if pr.get("repository_url") else "unknown",
                "number": pr.get("number"),
                "url": pr.get("html_url"),
                "state": pr.get("state"),
                "draft": pr.get("draft", False),
                "comments": pr.get("comments", 0),
                "created_at": pr.get("created_at", "")[:10],
            }
        
        return {
            "created": [format_pr(pr) for pr in created_prs],
            "review_requested": [format_pr(pr) for pr in review_prs],
            "total_created": len(created_prs),
            "total_review": len(review_prs),
        }


async def get_standup_data() -> dict:
    """
    Get standup prep data: yesterday's commits and today's open PRs.
    Perfect for "What did I work on yesterday?" queries.
    """
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).replace(hour=0, minute=0, second=0)
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get user's recent repos
        resp = await client.get(
            f"{GITHUB_BASE}/user/repos",
            params={"sort": "pushed", "per_page": 10},
            headers=_get_headers(),
        )
        resp.raise_for_status()
        repos = resp.json()
        
        yesterday_commits = []
        today_commits = []
        repos_worked = set()
        
        for r in repos[:7]:  # Check top 7 repos
            # Yesterday's commits
            resp2 = await client.get(
                f"{GITHUB_BASE}/repos/{r['full_name']}/commits",
                params={
                    "since": yesterday.isoformat(),
                    "until": today.isoformat(),
                    "author": settings.GITHUB_USERNAME,
                },
                headers=_get_headers(),
            )
            if resp2.status_code == 200:
                commits = resp2.json()
                for c in commits:
                    yesterday_commits.append({
                        "message": c["commit"]["message"].split("\n")[0][:60],
                        "repo": r["name"],
                        "sha": c["sha"][:7],
                    })
                    repos_worked.add(r["name"])
            
            # Today's commits
            resp3 = await client.get(
                f"{GITHUB_BASE}/repos/{r['full_name']}/commits",
                params={
                    "since": today.isoformat(),
                    "author": settings.GITHUB_USERNAME,
                },
                headers=_get_headers(),
            )
            if resp3.status_code == 200:
                commits = resp3.json()
                for c in commits:
                    today_commits.append({
                        "message": c["commit"]["message"].split("\n")[0][:60],
                        "repo": r["name"],
                        "sha": c["sha"][:7],
                    })
        
        # Get open PRs
        prs_data = await get_open_prs()
        
        return {
            "yesterday": {
                "commits": yesterday_commits,
                "count": len(yesterday_commits),
                "repos": list(repos_worked),
            },
            "today": {
                "commits": today_commits,
                "count": len(today_commits),
            },
            "open_prs": prs_data["total_created"],
            "review_requested": prs_data["total_review"],
        }


async def get_github_activity() -> dict:
    """
    Get combined GitHub activity: PRs + today's commits.
    For "Show my GitHub activity" or "Show my open PRs and commits" queries.
    """
    commits_data = await get_daily_commits()
    prs_data = await get_open_prs()
    
    return {
        "commits": commits_data,
        "prs": prs_data,
        "summary": {
            "commits_today": commits_data["total"],
            "open_prs": prs_data["total_created"],
            "reviews_pending": prs_data["total_review"],
        }
    }
