"""BYOK Key Vault API Router."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.core.keyvault import keyvault
from app.core.model_router import ModelRouterError
from app.core.model_router import router as model_router
from app.core.outbox import outbox
from app.domain.models import ApiKey
from app.domain.schemas import KeyResponse, KeySaveRequest

router = APIRouter(prefix="/api/keys", tags=["Key Vault"])


@router.post("", response_model=KeyResponse, status_code=status.HTTP_201_CREATED)
async def register_key(
    req: KeySaveRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Registers and envelope-encrypts a provider API key (KY-01, KY-02)."""
    # 1. Minimal probe validation call
    try:
        await model_router.probe_key(provider=req.provider, raw_key=req.api_key)
    except ModelRouterError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Key validation failed: {str(exc)}",
        ) from exc

    # 2. Store envelope-encrypted key
    stored = await keyvault.store_key(
        session=session,
        tenant_id=tenant_id,
        provider=req.provider,
        raw_key=req.api_key,
        is_default=req.is_default,
    )

    # 3. Emit key.validated outbox event
    await outbox.record_event(
        session=session,
        tenant_id=tenant_id,
        event_name="key.validated",
        payload={"provider": req.provider, "masked": stored.masked_preview},
    )
    await session.commit()

    return KeyResponse(
        id=stored.id,
        provider=stored.provider,
        masked_preview=stored.masked_preview,
        status=stored.status,
        is_default=stored.is_default,
        last_validated_at=stored.last_validated_at,
    )


@router.get("", response_model=List[KeyResponse])
async def list_keys(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Lists registered API keys for the current tenant (masked only, KY-02)."""
    query = select(ApiKey).where(ApiKey.tenant_id == tenant_id)
    records = (await session.execute(query)).scalars().all()
    return [
        KeyResponse(
            id=r.id,
            provider=r.provider,
            masked_preview=r.masked_preview,
            status=r.status,
            is_default=r.is_default,
            last_validated_at=r.last_validated_at,
        )
        for r in records
    ]


@router.delete("/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(
    provider: str,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Purges a registered key for a provider."""
    stmt = delete(ApiKey).where(ApiKey.tenant_id == tenant_id, ApiKey.provider == provider.lower())
    await session.execute(stmt)
    await session.commit()
