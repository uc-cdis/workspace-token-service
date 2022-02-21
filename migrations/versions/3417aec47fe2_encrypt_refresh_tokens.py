"""Encrypt refresh tokens

Revision ID: 3417aec47fe2
Revises: 27833deaf81f
Create Date: 2022-02-16 16:30:05.188696

"""
from alembic import op
from cryptography.fernet import Fernet

from wts.utils import get_config_var


# revision identifiers, used by Alembic.
revision = "3417aec47fe2"
down_revision = "27833deaf81f"
branch_labels = None
depends_on = None


def upgrade():
    print("Encrypting all existing refresh tokens in the DB")
    encryption_key = Fernet(get_config_var("ENCRYPTION_KEY"))
    connection = op.get_bind()
    results = connection.execute("SELECT token FROM refresh_token").fetchall()
    for i, (decrypted_token,) in enumerate(results):
        if i % 10 == 0:
            print(f"  {i}/{len(results)}")
        encrypted_token = encryption_key.encrypt(
            bytes(decrypted_token, encoding="utf8")
        ).decode("utf8")
        connection.execute(
            f"UPDATE refresh_token SET token='{encrypted_token}' WHERE token='{decrypted_token}'"
        )
    print("Done")


def downgrade():
    print("Decrypting all existing refresh tokens in the DB")
    encryption_key = Fernet(get_config_var("ENCRYPTION_KEY"))
    connection = op.get_bind()
    results = connection.execute("SELECT token FROM refresh_token").fetchall()
    for i, (encrypted_token,) in enumerate(results):
        if i % 10 == 0:
            print(f"  {i}/{len(results)}")
        decrypted_token = encryption_key.decrypt(
            bytes(encrypted_token, encoding="utf8")
        ).decode("utf8")
        connection.execute(
            f"UPDATE refresh_token SET token='{decrypted_token}' WHERE token='{encrypted_token}'"
        )
    print("Done")
