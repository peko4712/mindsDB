"""add provider to agent

Revision ID: 45eb2eb61f70
Revises: 459a4cd24933
Create Date: 2024-07-19 00:48:47.629700

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, select, update
import mindsdb.interfaces.storage.db  # noqa


# revision identifiers, used by Alembic.
revision = '45eb2eb61f70'
down_revision = '459a4cd24933'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('agents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('provider', sa.String(), nullable=True))

    with op.batch_alter_table('chat_bots', schema=None) as batch_op:
        batch_op.alter_column('database_id',
                              existing_type=sa.INTEGER(),
                              nullable=True)

    # code for migrating 'provider' from 'params' to its own column
    agents = table('agents',
                   sa.Column('id', sa.Integer, primary_key=True),
                   sa.Column('params', sa.JSON),
                   sa.Column('provider', sa.String()))

    conn = op.get_bind()
    for agent in conn.execute(select(agents)):
        if agent.params and 'provider' in agent.params:
            conn.execute(update(agents).where(agents.c.id == agent.id).values(provider=agent.params['provider']))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('chat_bots', schema=None) as batch_op:
        batch_op.alter_column('database_id',
                              existing_type=sa.INTEGER(),
                              nullable=False)

    with op.batch_alter_table('agents', schema=None) as batch_op:
        batch_op.drop_column('provider')

    # ### end Alembic commands ###
