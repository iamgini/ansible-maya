# Copyright 2026 Ansible Maya Contributors
# Licensed under the Apache License, Version 2.0

"""Spec-Kit API routes - two-phase generation."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ansible_maya.core.providers import get_provider
from ansible_maya.core.spec_generator import SpecGenerator
from ansible_maya.handlers.orchestrator import AIOpsEvent, PlaybookOrchestrator

router = APIRouter()

# In-memory spec storage (replace with Redis/DB in production)
# LIMITATION: Does NOT work with AAP/EDA automated workflows because:
#   1. In-memory only - lost on API restart
#   2. AAP jobs can't pause mid-execution for approval
#   3. Phase 1 and Phase 2 would be different job runs
# USE CASE: Local CLI, interactive API testing, manual workflows
# ALTERNATIVE: Use multi_agent_review=true for automated AAP/EDA workflows
_specs_store = {}


class SpecResponse(BaseModel):
    """Execution spec response."""

    spec_id: str
    steps: str
    event_id: str
    requires_approval: bool
    message: str


class PlaybookFromSpecRequest(BaseModel):
    """Request to generate playbook from approved spec."""

    approved: bool = True


@router.post("/plan", response_model=SpecResponse)
async def generate_execution_plan(event: AIOpsEvent):
    """Generate execution plan (spec) from event.

    This is Phase 1 of two-phase generation.
    Returns a plain-English specification for user approval.
    """
    try:
        # Get LLM provider
        provider = get_provider()

        # Generate spec
        spec_gen = SpecGenerator(provider)
        spec = await spec_gen.generate_spec(event)

        # Store spec for Phase 2
        _specs_store[spec.spec_id] = spec

        return SpecResponse(
            spec_id=spec.spec_id,
            steps=spec.steps,
            event_id=event.event_id,
            requires_approval=True,
            message="Review the execution plan. Approve to generate playbook.",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Spec generation failed: {str(e)}")


@router.post("/{spec_id}/generate")
async def generate_from_spec(spec_id: str, request: PlaybookFromSpecRequest):
    """Generate playbook from approved spec.

    This is Phase 2 of two-phase generation.
    Requires spec_id from Phase 1.
    """
    # Retrieve spec
    spec = _specs_store.get(spec_id)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Spec {spec_id} not found")

    if not request.approved:
        return {"message": "Spec not approved. No playbook generated."}

    try:
        # Get provider
        provider = get_provider()

        # Generate playbook with spec context
        orchestrator = PlaybookOrchestrator(provider=provider)

        # Enhance event description with approved spec
        enhanced_event = spec.event
        enhanced_event.description = (
            f"{spec.event.description}\n\nApproved execution plan:\n{spec.steps}"
        )

        # Generate playbook
        response = await orchestrator.handle_event(enhanced_event)

        # Clean up spec
        del _specs_store[spec_id]

        return {
            "spec_id": spec_id,
            "playbook": response.playbook,
            "confidence_score": response.confidence_score,
            "validation_result": response.validation_result.dict(),
            "message": "Playbook generated from approved spec",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Playbook generation from spec failed: {str(e)}"
        )


@router.get("/{spec_id}")
async def get_spec(spec_id: str):
    """Retrieve execution spec by ID."""
    spec = _specs_store.get(spec_id)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Spec {spec_id} not found")

    return {
        "spec_id": spec.spec_id,
        "steps": spec.steps,
        "event_id": spec.event.event_id,
        "event_type": spec.event.event_type,
        "requires_approval": spec.requires_approval,
    }
