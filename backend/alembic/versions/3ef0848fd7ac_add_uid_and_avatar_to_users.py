"""add uid and avatar to users

Revision ID: 3ef0848fd7ac
Revises: 381df8ee6844
Create Date: 2026-08-21 14:51:02.967068

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import uuid


# revision identifiers, used by Alembic.
revision: str = '3ef0848fd7ac'
down_revision: Union[str, Sequence[str], None] = '381df8ee6844'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. 加列（uid 先可空，便于回填存量数据）
    op.add_column('users', sa.Column('uid', sa.String(36), nullable=True))
    op.add_column('users', sa.Column('avatar_url', sa.String(512), nullable=True))

    # 2. 回填存量用户的 uid（UUID）
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM users")).fetchall()
    for (user_id,) in rows:
        conn.execute(
            sa.text("UPDATE users SET uid = :uid WHERE id = :id"),
            {"uid": str(uuid.uuid4()), "id": user_id},
        )

    # 3. 设非空 + 唯一索引
    op.alter_column('users', 'uid', existing_type=sa.String(36), nullable=False)
    op.create_index('ix_users_uid', 'users', ['uid'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_users_uid', table_name='users')
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'uid')
