"""interview_events

Revision ID: c4a8e1b27d11
Revises: b7e1c2a9d4f0
Create Date: 2026-09-22 05:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c4a8e1b27d11'
down_revision: Union[str, Sequence[str], None] = 'b7e1c2a9d4f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'interview_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('application_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reminder_24h_sent', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('reminder_1h_sent', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['applications_tracked.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('application_id', 'starts_at', name='uq_interview_events_app_starts')
    )
    op.create_index(op.f('ix_interview_events_application_id'), 'interview_events', ['application_id'], unique=False)
    op.create_index(op.f('ix_interview_events_tenant_id'), 'interview_events', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_table('interview_events')
