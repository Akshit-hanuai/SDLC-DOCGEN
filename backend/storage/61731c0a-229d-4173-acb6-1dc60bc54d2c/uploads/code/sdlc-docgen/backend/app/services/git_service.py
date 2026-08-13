import re
from pathlib import Path

from git import Actor, Repo

from app.config import settings

AUTHOR = Actor("sdlc-docgen", "docgen@local")


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"


def _repo(project) -> Repo:
    slug = _slugify(project.name)
    bare = Path(settings.git_repos_root) / f"{slug}.git"
    work = Path(settings.git_work_root) / slug

    if not bare.exists():
        Repo.init(bare, bare=True)
    if not (work / ".git").exists():
        if work.exists():
            import shutil

            shutil.rmtree(work)
        work.mkdir(parents=True, exist_ok=True)
        Repo.clone_from(str(bare), str(work))
    return Repo(work)


def commit_version(project, doc, version: int, files: dict[str, str], message_meta: dict) -> str:
    repo = _repo(project)
    workdir = Path(repo.working_tree_dir)
    for rel, source in files.items():
        target = workdir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(source).read_bytes())
    repo.index.add([str(p) for p in files.keys()])

    summary = " ".join(f"{k}={v}" for k, v in message_meta.items())
    message = f"[{doc.doc_type}] v{version} auto-version | {summary}"
    sha = repo.index.commit(message, author=AUTHOR, committer=AUTHOR).hexsha
    if repo.remotes:
        repo.remotes.origin.push()
    return sha


def tag_baseline(project, doc, version: int, sha: str) -> str:
    repo = _repo(project)
    tag = f"baseline-{doc.doc_type.lower()}-v{version}"
    repo.create_tag(tag, ref=sha, force=True)
    if repo.remotes:
        repo.remotes.origin.push(tag)
    return tag


def repo_commit_list(project, limit: int = 50) -> list[dict]:
    repo = _repo(project)
    commits = []
    for commit in repo.iter_commits(max_count=limit):
        commits.append(
            {
                "sha": commit.hexsha,
                "message": commit.message.strip(),
                "author": str(commit.author),
                "date": commit.authored_datetime.isoformat(),
            }
        )
    return commits
