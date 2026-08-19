"""
Instructor-facing router.

All endpoints are prefixed /orchestrator/instructor/*.

Maps directly to the four Figma dashboard tabs + sidebar AI actions.
See INTERFACE_CONTRACT.md §Frontend → Orchestrator Mapping for the full table.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from pydantic import BaseModel

from aieic_shared.schemas.curriculum import CurriculumMaterial, TypoCheckResponse
from aieic_shared.schemas.orchestrator import DashboardResponse, InstructorApprovalRequest

router = APIRouter(prefix="/orchestrator/instructor", tags=["instructor"])
logger = logging.getLogger(__name__)


# ── Dependency helpers ────────────────────────────────────────────────────────

def _dashboard(request: Request):
    return request.app.state.dashboard_service

def _curriculum(request: Request):
    return request.app.state.curriculum

def _assessment(request: Request):
    return request.app.state.assessment


# ── Request bodies not already in aieic-shared ────────────────────────────────

class RequestChangesBody(BaseModel):
    lab_id: str
    feedback: str
    requested_by: str

class GenerateQuizBody(BaseModel):
    lab_id: str
    course_id: str = "csc580"
    title: str = ""
    learning_objectives: list[str] = []
    difficulty: str = "intermediate"
    estimated_duration_min: int = 90
    instructor_id: str = "instructor"

class CheckTyposBody(BaseModel):
    lab_id: str

class UploadInstructionsBody(BaseModel):
    lab_id: str
    instructions: str

class CompleteReviewBody(BaseModel):
    instructor_score: float
    notes: str = ""

class QueuedResponse(BaseModel):
    status: str = "queued"

class GradeBatchResponse(BaseModel):
    lab_id: str
    submissions_queued: int

class UploadMaterialResponse(BaseModel):
    status: str = "uploaded"
    file_count: int


async def _generate_material_task(curriculum, body: GenerateQuizBody) -> None:
    try:
        await curriculum.generate(
            course_id=body.course_id,
            lab_id=body.lab_id,
            title=body.title,
            learning_objectives=body.learning_objectives,
            difficulty=body.difficulty,
            estimated_duration_min=body.estimated_duration_min,
            instructor_id=body.instructor_id,
        )
    except Exception as exc:
        logger.error(f"[generate_material_task] {exc}")


# ── Tab 1: Material Preview ───────────────────────────────────────────────────

@router.get("/dashboard/{lab_id}", response_model=DashboardResponse)
async def get_dashboard(
    lab_id: str,
    request: Request,
    tab: Optional[str] = Query(
        default=None,
        description="material | activity | grades | stats  (omit = all tabs)",
    ),
):
    """
    Unified dashboard payload — populates all four Figma tabs in one call.

    The Orchestrator calls Curriculum Designer, Participant Agent, and
    Assessment Agent in parallel, then assembles the response.

    Use `?tab=activity` to refresh only the Student Activity tab cheaply.
    """
    try:
        return await _dashboard(request).build(lab_id=lab_id, tab=tab)
    except Exception as exc:
        logger.error(f"[dashboard] Build failed: {exc}")
        raise HTTPException(status_code=500, detail="Failed to build dashboard")


@router.get("/material/{lab_id}", response_model=CurriculumMaterial)
async def get_material(lab_id: str, request: Request):
    """Fetch the current editable curriculum draft for a lab."""
    try:
        return await _curriculum(request).get(lab_id)
    except Exception as exc:
        logger.error(f"[get_material] {exc}")
        raise HTTPException(status_code=502, detail="Curriculum Designer unavailable")


@router.post("/material/approve", response_model=CurriculumMaterial)
async def approve_material(body: InstructorApprovalRequest, request: Request):
    """
    Instructor clicks "Approve" in the Material Preview tab.
    Publishes an immutable lab package, then marks the draft approved.
    """
    curriculum = _curriculum(request)
    try:
        internal_data = await curriculum._get(f"/curriculum/{body.lab_id}/internal")
        draft = CurriculumMaterial(**internal_data)
        publisher = getattr(request.app.state, "curriculum_publisher", None)
        if publisher is not None:
            publisher.publish(
                draft=draft,
                approved_by=body.approved_by,
                notes=body.notes,
                tutor_instructions=internal_data.get("agent_instructions"),
            )
        return await curriculum.approve(
            lab_id=body.lab_id,
            approved_by=body.approved_by,
            notes=body.notes,
        )
    except Exception as exc:
        logger.error(f"[approve_material] {exc}")
        raise HTTPException(status_code=502, detail="Material approval failed")


@router.post("/material/request-changes", response_model=CurriculumMaterial)
async def request_material_changes(body: RequestChangesBody, request: Request):
    """
    Instructor clicks "Request Changes" — triggers regeneration.
    Status moves back to 'pending'.
    """
    try:
        return await _curriculum(request).request_changes(
            lab_id=body.lab_id,
            feedback=body.feedback,
            requested_by=body.requested_by,
        )
    except Exception as exc:
        logger.error(f"[request_changes] {exc}")
        raise HTTPException(status_code=502, detail="Curriculum Designer unavailable")


# ── Sidebar AI Actions ────────────────────────────────────────────────────────

@router.post("/material/generate-quiz", response_model=CurriculumMaterial)
async def generate_quiz(body: GenerateQuizBody, request: Request):
    """
    Sidebar AI action: "Generate Quiz".
    Calls Curriculum Designer to generate a full lab from learning objectives.
    """
    try:
        return await _curriculum(request).generate(
            course_id=body.course_id,
            lab_id=body.lab_id,
            title=body.title,
            learning_objectives=body.learning_objectives,
            difficulty=body.difficulty,
            estimated_duration_min=body.estimated_duration_min,
            instructor_id=body.instructor_id,
        )
    except Exception as exc:
        logger.error(f"[generate_quiz] {exc}")
        raise HTTPException(status_code=502, detail="Curriculum Designer unavailable")


@router.post("/material/generate-with-material", response_model=CurriculumMaterial)
async def generate_with_material(
    request: Request,
    lab_id: str = Form(...),
    title: str = Form(...),
    learning_objectives: str = Form(...),
    difficulty: str = Form("intermediate"),
    estimated_duration_min: int = Form(90),
    instructor_id: str = Form("instructor"),
    course_id: str = Form("csc580"),
    agent_instructions: str = Form(""),
    file: Optional[UploadFile] = File(None),
):
    """
    One-shot UI flow: form fields + optional reference PDF/TXT/MD -> generated
    spec, quiz, and rubric. The frontend still talks only to Orchestrator.
    """
    data = {
        "lab_id": lab_id,
        "title": title,
        "learning_objectives": learning_objectives,
        "difficulty": difficulty,
        "estimated_duration_min": str(estimated_duration_min),
        "instructor_id": instructor_id,
        "course_id": course_id,
        "agent_instructions": agent_instructions,
    }

    files = None
    if file is not None and file.filename:
        content = await file.read()
        files = {
            "file": (
                file.filename,
                content,
                file.content_type or "application/octet-stream",
            )
        }

    try:
        payload = await _curriculum(request)._post(
            "/curriculum/generate-with-material",
            data=data,
            files=files,
        )
        return CurriculumMaterial(**payload)
    except Exception as exc:
        logger.error(f"[generate_with_material] {exc}")
        raise HTTPException(status_code=502, detail="Curriculum Designer unavailable")


@router.post("/material/generate-tasks", response_model=QueuedResponse)
async def generate_lab_tasks(
    body: GenerateQuizBody,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Sidebar AI action: "Generate Lab Tasks".

    Curriculum Designer currently exposes one generation endpoint for the full
    lab package, so this queues that generation path and returns immediately.
    """
    background_tasks.add_task(_generate_material_task, _curriculum(request), body)
    return QueuedResponse()


@router.post("/material/check-typos", response_model=TypoCheckResponse)
async def check_typos(body: CheckTyposBody, request: Request):
    """Sidebar AI action: "Check for Typos & Errors"."""
    try:
        return await _curriculum(request).check_typos(lab_id=body.lab_id)
    except Exception as exc:
        logger.error(f"[check_typos] {exc}")
        raise HTTPException(status_code=502, detail="Curriculum Designer unavailable")


# ── Tab 3: Graded Submissions — manual review ─────────────────────────────────

@router.post("/review/{submission_id}/complete")
async def complete_review(
    submission_id: str,
    body: CompleteReviewBody,
    request: Request,
):
    """
    Instructor completes a manual review of a flagged / pending submission.
    Forwards to Assessment Agent's review queue.
    """
    try:
        return await _assessment(request).complete_review(
            submission_id=submission_id,
            instructor_score=body.instructor_score,
            notes=body.notes,
        )
    except Exception as exc:
        logger.error(f"[complete_review] {exc}")
        raise HTTPException(status_code=502, detail="Assessment Agent unavailable")


@router.post("/grade-batch", response_model=GradeBatchResponse)
async def grade_batch(
    lab_id: str = Query(...),
    request: Request = None,
):
    """
    Trigger grading for all pending submissions.

    The Assessment Agent grades submissions at submit time today. Until it
    exposes a true batch queue endpoint, report how many existing lab results
    are still pending or in review so the dashboard button has a stable
    Orchestrator contract.
    """
    try:
        results = await _assessment(request).list_results(assignment_id=lab_id)
    except Exception as exc:
        logger.error(f"[grade_batch] {exc}")
        raise HTTPException(status_code=502, detail="Assessment Agent unavailable")

    queued = sum(1 for r in results if r.status in {"pending", "in_review"})
    return GradeBatchResponse(lab_id=lab_id, submissions_queued=queued)


@router.get("/submission/{submission_id}")
async def get_submission(submission_id: str, request: Request):
    """Get full detail for a single submission (for instructor review modal)."""
    try:
        return await _assessment(request).get_result(submission_id)
    except Exception as exc:
        logger.error(f"[get_submission] {exc}")
        raise HTTPException(status_code=502, detail="Assessment Agent unavailable")


@router.post("/material/upload", response_model=UploadMaterialResponse)
async def upload_material(
    request: Request,
    lab_id: str = Form(...),
    course_id: str = Form("csc580"),
    instructor_id: str = Form("instructor"),
    files: Optional[list[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
):
    """
    Upload instructor material through the Orchestrator.

    The dashboard may send either `files` or a single `file` field. Curriculum
    Designer currently accepts one file per request, so multiple uploads are
    forwarded one at a time.
    """
    del course_id, instructor_id

    uploads = list(files or [])
    if file is not None:
        uploads.append(file)
    uploads = [upload for upload in uploads if upload.filename]

    if not uploads:
        raise HTTPException(status_code=400, detail="At least one file is required")

    curriculum = _curriculum(request)
    try:
        for upload in uploads:
            content = await upload.read()
            await curriculum._post(
                f"/curriculum/{lab_id}/upload-material",
                files={
                    "file": (
                        upload.filename,
                        content,
                        upload.content_type or "application/octet-stream",
                    )
                },
            )
    except Exception as exc:
        logger.error(f"[upload_material] {exc}")
        raise HTTPException(status_code=502, detail="Curriculum Designer unavailable")

    return UploadMaterialResponse(file_count=len(uploads))


@router.post("/material/upload-instructions")
async def upload_instructions(body: UploadInstructionsBody, request: Request):
    """Save instructor-provided tutoring instructions through the Orchestrator."""
    if not body.instructions.strip():
        raise HTTPException(status_code=400, detail="Instructions cannot be empty")
    try:
        return await _curriculum(request)._post(
            f"/curriculum/{body.lab_id}/upload-instructions",
            json={"instructions": body.instructions},
        )
    except Exception as exc:
        logger.error(f"[upload_instructions] {exc}")
        raise HTTPException(status_code=502, detail="Curriculum Designer unavailable")


@router.get("/grades/csv")
async def download_grades_csv(
    lab_id: str = Query(...),
    request: Request = None,
):
    """
    Download all grades as CSV.

    TODO: stream the CSV rather than loading all results into memory.
    For v0.1, this is acceptable given class sizes (~35 students).
    """
    import csv
    import io
    from fastapi.responses import StreamingResponse

    assessment = _assessment(request)
    try:
        results = await assessment.list_results(assignment_id=lab_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Assessment Agent unavailable")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["student_id", "score", "status", "feedback"])
    for r in results:
        score = r.final_score if r.final_score is not None else r.automated_score
        writer.writerow([
            r.student_id,
            score,
            r.status,
            r.feedback.summary if r.feedback else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=grades_{lab_id}.csv"},
    )
