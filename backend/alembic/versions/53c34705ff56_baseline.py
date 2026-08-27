"""baseline

Revision ID: 53c34705ff56
Revises:
Create Date: 2026-08-20 20:15:54.969996

说明：原 baseline 为空（基础表当时由 main.py 的 create_all 创建）。
C4 收口：补齐基础表创建，使全新库可完全通过 alembic upgrade head 自举。
后续增量迁移（role/public_images/is_visible/uid/avatar_url）保持不变。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '53c34705ff56'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # users：历史形态 6 列（role/uid/avatar_url 由后续迁移追加）
    op.create_table('users',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('username', sa.String(length=50), nullable=False),
    sa.Column('email', sa.String(length=100), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # images
    op.create_table('images',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False, comment='存储文件名（UUID）'),
    sa.Column('original_name', sa.String(length=255), nullable=False, comment='用户上传的原始文件名'),
    sa.Column('custom_name', sa.String(length=255), nullable=True, comment='用户自定义名称（可选）'),
    sa.Column('date_dir', sa.String(length=8), nullable=False, comment='日期子目录'),
    sa.Column('file_path', sa.String(length=500), nullable=False, comment='原图（原格式）存储路径'),
    sa.Column('thumbnail_path', sa.String(length=500), nullable=True, comment='缩略图存储路径'),
    sa.Column('file_size', sa.Integer(), nullable=False, comment='文件大小（字节）'),
    sa.Column('mime_type', sa.String(length=50), nullable=False, comment='MIME 类型'),
    sa.Column('width', sa.Integer(), nullable=True, comment='图片宽度'),
    sa.Column('height', sa.Integer(), nullable=True, comment='图片高度'),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_images_id'), 'images', ['id'], unique=False)
    op.create_index(op.f('ix_images_user_id'), 'images', ['user_id'], unique=False)

    # tags
    op.create_table('tags',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tags_id'), 'tags', ['id'], unique=False)
    op.create_index(op.f('ix_tags_name'), 'tags', ['name'], unique=True)

    # image_tags（多对多中间表）
    op.create_table('image_tags',
    sa.Column('image_id', sa.Integer(), nullable=False),
    sa.Column('tag_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['image_id'], ['images.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('image_id', 'tag_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('image_tags')
    op.drop_index(op.f('ix_tags_name'), table_name='tags')
    op.drop_index(op.f('ix_tags_id'), table_name='tags')
    op.drop_table('tags')
    op.drop_index(op.f('ix_images_user_id'), table_name='images')
    op.drop_index(op.f('ix_images_id'), table_name='images')
    op.drop_table('images')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
