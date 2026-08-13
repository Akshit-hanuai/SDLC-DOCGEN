import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentVersion, Project
from app.models.review import Review
from app.models.user import User
from app.services.audit import log_action
from app.services.generate.generator import generate_document
from app.services.git_service import tag_baseline

VALID_DECISIONS = {"approved", "rejected"}


async def get_user(session: AsyncSession, username: str) -> User:
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(username=username, full_name=username, role="reviewer")
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def submit_for_review(session: AsyncSession, document: Document, user_id: uuid.UUID | None = None) -> Document:
    document.status = "in_review"
    await session.commit()
    await log_action(session, document.project_id, user_id, "submit", "document", str(document.id))
    return document


async def review_section(
    session: AsyncSession,
    document: Document,
    version: DocumentVersion,
    section_id: str,
    reviewer: User,
    decision: str,
    comment: str | None = None,
) -> Review:
    if decision not in VALID_DECISIONS:
        raise ValueError(f"decision must be one of {VALID_DECISIONS}")
    review = Review(
        document_id=document.id,
        version=version.version,
        section_id=section_id,
        reviewer_id=reviewer.id,
        decision=decision,
        comment=comment,
    )
    session.add(review)
    if decision == "rejected":
        document.status = "changes_requested"
    await session.commit()
    await log_action(
        session, document.project_id, reviewer.id, "review", "review", str(review.id),
        {"decision": decision, "section_id": section_id, "version": version.version},
    )
    return review


async def approve_document(
    session: AsyncSession,
    document: Document,
    version: DocumentVersion,
    approver: User,
) -> dict:
    document.status = "approved"
    document.git_commit_sha = version.git_commit_sha
    project = await session.get(Project, document.project_id)
    tag = tag_baseline(project, document, version.version, version.git_commit_sha)
    await session.commit()
    await log_action(
        session, document.project_id, approver.id, "approve", "document", str(document.id),
        {"version": version.version, "git_tag": tag},
    )
    return {"status": document.status, "version": version.version, "git_tag": tag}


async def regenerate_section(
    session: AsyncSession,
    project,
    document: Document,
    version: DocumentVersion,
    section_id: str,
    comment: str,
    user_id: uuid.UUID | None = None,
    target_field: str | None = None,
) -> tuple[DocumentVersion, dict]:
    document, new_version, report = await generate_document(
        session,
        project,
        document.doc_type,
        user_id=user_id,
        regenerate_section=section_id,
        reviewer_comment=comment,
        target_field=target_field,
        previous_version=version,
    )
    document.status = "in_review"
    await session.commit()
    await log_action(
        session, document.project_id, user_id, "regenerate", "document_version", f"{document.id}:{new_version.version}",
        {"section_id": section_id},
    )
    return new_version, report


def section_statuses(reviews: list[Review], section_ids: list[str]) -> dict[str, str]:
    statuses = {sid: "not_reviewed" for sid in section_ids}
    for review in reviews:
        statuses[review.section_id] = review.decision
    return statuses


def version_diff(prev: dict, curr: dict) -> list[dict]:
    prev_sections = prev.get("sections", {})
    curr_sections = curr.get("sections", {})
    changes: list[dict] = []
    for sid in sorted(set(prev_sections) | set(curr_sections)):
        before = prev_sections.get(sid)
        after = curr_sections.get(sid)
        if before is None:
            action = "added"
        elif after is None:
            action = "removed"
        elif before != after:
            action = "modified"
        else:
            action = "unchanged"
        changes.append({"section_id": sid, "action": action, "changed": action != "unchanged"})
    return changes
