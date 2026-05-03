"""add_ai_api_base_to_user

Revision ID: c869d602a748
Revises: 5e169cfae984
Create Date: 2026-04-01 21:57:23.426841

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c869d602a748'
down_revision: Union[str, Sequence[str], None] = '5e169cfae984'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('app_user', sa.Column('ai_api_base', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('app_user', 'ai_api_base')
