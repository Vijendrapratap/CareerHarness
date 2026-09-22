"""Counsellor API Router (Task 4)."""

from typing import Any, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.counsel import (
    CounselOrderError,
    CounselValidationError,
    get_counsel_state,
    record_answer,
)

router = APIRouter(prefix="/api/counsel", tags=["Candidate Counsellor"])


class CounselAnswerRequest(BaseModel):
    step: str
    text: str
    input_mode: Literal["text", "mic"] = "text"


class CounselStateResponse(BaseModel):
    step: Optional[str] = None
    prompt: str
    choices: List[Any] = []
    done: bool


@router.get("", response_model=CounselStateResponse)
async def get_counsel(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    return await get_counsel_state(db, tenant_id)


@router.post("/answer", response_model=CounselStateResponse)
async def submit_counsel_answer(
    request: CounselAnswerRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await record_answer(
            session=db,
            tenant_id=tenant_id,
            step=request.step,
            text=request.text,
            input_mode=request.input_mode,
        )
    except CounselOrderError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except CounselValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
