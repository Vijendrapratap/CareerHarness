"""apply_sessions and resume_files

Revision ID: e27b5f0a9c13
Revises: d91f3a6c2e40
Create Date: 2026-09-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.domain.models

revision: str = 'e27b5f0a9c13'
down_revision: Union[str, Sequence[str], None] = 'd91f3a6c2e40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'resume_files',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('content', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_resume_files_tenant_id'), 'resume_files', ['tenant_id'], unique=False)
    op.create_table(
        'apply_sessions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('mode', sa.String(length=16), nullable=False),
        sa.Column('resume_version_id', sa.String(length=36), nullable=True),
        sa.Column('ats', sa.String(length=32), nullable=False),
        sa.Column('apply_url', sa.String(length=1024), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('fields', app.domain.models.PortableJSON(), nullable=False),
        sa.Column('questions', app.domain.models.PortableJSON(), nullable=False),
        sa.Column('result_code', sa.String(length=32), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('screenshot_path', sa.String(length=512), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['job_listings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_apply_sessions_tenant_id'), 'apply_sessions', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_table('apply_sessions')
    op.drop_table('resume_files')
