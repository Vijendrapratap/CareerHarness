"""candidate_journey and profile_sections

Revision ID: b7e1c2a9d4f0
Revises: 27889c9aff99
Create Date: 2026-09-22 05:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.domain.models

revision: str = 'b7e1c2a9d4f0'
down_revision: Union[str, Sequence[str], None] = '27889c9aff99'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'candidate_journeys',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('stage', sa.String(length=32), nullable=False, server_default='counsel'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id')
    )
    op.create_table(
        'profile_sections',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('section', sa.String(length=64), nullable=False),
        sa.Column('step', sa.String(length=64), nullable=False),
        sa.Column('body', app.domain.models.PortableJSON(), nullable=False),
        sa.Column('input_mode', sa.String(length=16), nullable=False, server_default='text'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'step', name='uq_profile_sections_tenant_step')
    )


def downgrade() -> None:
    op.drop_table('profile_sections')
    op.drop_table('candidate_journeys')
