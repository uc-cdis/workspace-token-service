"""Add IDP

Revision ID: 27833deaf81f
Revises: a38a346e6ded
Create Date: 2020-03-15 19:38:26.321139

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "27833deaf81f"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("refresh_token", sa.Column("idp", sa.VARCHAR))
    op.execute("UPDATE refresh_token SET idp='default'")
    op.alter_column("refresh_token", "idp", nullable=False)


def downgrade():
    op.drop_column("refresh_token", "idp")
