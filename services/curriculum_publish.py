"""Publish approved Curriculum Designer drafts into immutable lab packages."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from aieic_shared.schemas.curriculum import CurriculumMaterial

from services.database import (
    CourseRecord,
    EventRecord,
    LabPackageRecord,
    LabRecord,
    build_engine,
    create_session_factory,
    ensure_schema,
)


class CurriculumPackagePublisher:
    """Owns the Orchestrator-side approval transaction."""

    def __init__(self, database_url: str) -> None:
        self._engine = build_engine(database_url)
        ensure_schema(self._engine)
        self._session_factory = create_session_factory(self._engine)

    def publish(
        self,
        *,
        draft: CurriculumMaterial,
        approved_by: str,
        notes: str = "",
        tutor_instructions: str | None = None,
    ) -> str:
        """Publish `draft` idempotently and return package_id."""
        package_id = f"{draft.course_id}:{draft.lab_id}:v{draft.version}"
        now = datetime.now(timezone.utc)

        with self._session_factory() as session:
            existing = session.get(LabPackageRecord, package_id)
            if existing is not None:
                lab = session.get(LabRecord, draft.lab_id)
                if lab is not None and lab.active_package_id != package_id:
                    lab.active_package_id = package_id
                    lab.updated_at = now
                    session.commit()
                return package_id

            course = session.get(CourseRecord, draft.course_id)
            if course is None:
                session.add(CourseRecord(course_id=draft.course_id, title=draft.course_id))

            lab = session.get(LabRecord, draft.lab_id)
            if lab is None:
                lab = LabRecord(
                    lab_id=draft.lab_id,
                    course_id=draft.course_id,
                    title=draft.title,
                    phase="pre_lab",
                    active_package_id=package_id,
                )
                session.add(lab)
            else:
                lab.course_id = draft.course_id
                lab.title = draft.title
                lab.active_package_id = package_id
                lab.updated_at = now

            session.add(
                LabPackageRecord(
                    package_id=package_id,
                    course_id=draft.course_id,
                    lab_id=draft.lab_id,
                    version=draft.version,
                    status="approved",
                    title=draft.title,
                    spec_markdown=draft.spec_markdown,
                    quiz_json=[q.model_dump(mode="json") for q in draft.quiz],
                    rubric_json=draft.rubric.model_dump(mode="json"),
                    tutor_instructions=tutor_instructions,
                    assessment_config_json={},
                    source_artifacts_json=[],
                    created_by=approved_by,
                    approved_by=approved_by,
                    approved_at=now,
                    created_at=now,
                )
            )
            session.add(
                EventRecord(
                    event_id=str(uuid4()),
                    event_type="curriculum.approved",
                    course_id=draft.course_id,
                    lab_id=draft.lab_id,
                    source="orchestrator",
                    actor_type="instructor",
                    actor_id=approved_by,
                    payload_json={
                        "package_id": package_id,
                        "version": draft.version,
                        "notes": notes,
                    },
                    occurred_at=now,
                )
            )
            session.commit()
            return package_id
