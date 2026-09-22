"""job_fits

Revision ID: d91f3a6c2e40
Revises: c4a8e1b27d11
Create Date: 2026-09-23 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.domain.models

revision: str = 'd91f3a6c2e40'
down_revision: Union[str, Sequence[str], None] = 'c4a8e1b27d11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'job_fits',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('verdict', sa.String(length=16), nullable=False),
        sa.Column('report', app.domain.models.PortableJSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['job_listings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_job_fits_tenant_id'), 'job_fits', ['tenant_id'], unique=False)
    op.create_index('ix_job_fits_tenant_job', 'job_fits', ['tenant_id', 'job_id'], unique=True)


def downgrade() -> None:
    op.drop_table('job_fits')
