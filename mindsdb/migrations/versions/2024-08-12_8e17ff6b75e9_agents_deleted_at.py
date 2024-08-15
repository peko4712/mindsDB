"""agents-deleted-at

Revision ID: 8e17ff6b75e9
Revises: 45eb2eb61f70
Create Date: 2024-08-12 19:13:44.327111

"""
from alembic import op
import sqlalchemy as sa
import mindsdb.interfaces.storage.db  # noqa


# revision identifiers, used by Alembic.
revision = '8e17ff6b75e9'
down_revision = '45eb2eb61f70'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('agents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))

    with op.batch_alter_table('skills', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('skills', schema=None) as batch_op:
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')

    with op.batch_alter_table('agents', schema=None) as batch_op:
        batch_op.drop_column('deleted_at')
    # ### end Alembic commands ###
