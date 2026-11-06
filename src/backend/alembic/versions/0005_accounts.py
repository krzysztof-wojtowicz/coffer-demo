"""accounts: case-insensitive e-mail, audit columns, session expiry index

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-06
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    # The app always stored normalized e-mails, so duplicates are not expected. If some exist,
    # stop instead of guessing which account to keep (deleting or renaming would lose access).
    dupes = conn.execute(
        sa.text(
            "SELECT lower(btrim(email)) AS e, count(*) FROM users "
            "GROUP BY lower(btrim(email)) HAVING count(*) > 1"
        )
    ).all()
    if dupes:
        listed = ", ".join(f"{row[0]} ({row[1]}x)" for row in dupes[:10])
        raise RuntimeError(
            "0005: users.email has case-insensitive duplicates; merge or rename them by hand "
            f"before upgrading: {listed}"
        )
    op.execute("UPDATE users SET email = lower(btrim(email)) WHERE email <> lower(btrim(email))")
    op.drop_constraint("users_email_key", "users", type_="unique")
    op.create_index("ux_users_email_lower", "users", [sa.text("lower(email)")], unique=True)

    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True)))
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "password_changed_at")
    op.drop_index("ux_users_email_lower", table_name="users")
    # E-mails stay lowercased (normalization is not reversible); uniqueness is restored.
    op.create_unique_constraint("users_email_key", "users", ["email"])
