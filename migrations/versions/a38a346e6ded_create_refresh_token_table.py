"""Create refresh_token table

Revision ID: a38a346e6ded
Revises: 
Create Date: 2020-03-15 19:26:18.544300

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a38a346e6ded"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # check whether the `refresh_token` table already exists. We should
    # not try to re-create the table in deployments whose DB was created
    # before this "initial state" migration code was added.
    conn = op.get_bind()
    inspector = sa.engine.reflection.Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    if "refresh_token" in tables:
        return

    op.create_table(
        "refresh_token",
        sa.Column("token", sa.VARCHAR(), nullable=False),
        sa.Column("jti", sa.VARCHAR(), nullable=False),
        sa.Column("username", sa.VARCHAR(), nullable=False),
        sa.Column("userid", sa.VARCHAR(), nullable=False),
        sa.Column("expires", sa.BIGINT(), nullable=False),
        sa.PrimaryKeyConstraint("token", name="refresh_token_pkey"),
        sa.UniqueConstraint("jti", name="refresh_token_jti_key"),
    )


def downgrade():
    op.drop_table("refresh_token")
