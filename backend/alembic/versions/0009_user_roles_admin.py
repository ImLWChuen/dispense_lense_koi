"""Add user roles, department, timestamps, and seed admin user

Revision ID: 0009_user_roles_admin
Revises: 0008_observation_metadata
Create Date: 2026-09-20 17:30:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision: str = "0009_user_roles_admin"
down_revision: Union[str, None] = "0008_observation_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add role column
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=64),
            nullable=False,
            server_default="technician",
            comment="User role (e.g. admin, engineer, technician, viewer)",
        ),
    )
    # 2. Add department column
    op.add_column(
        "users",
        sa.Column(
            "department",
            sa.String(length=128),
            nullable=True,
            comment="Employee assigned department / production line",
        ),
    )
    # 3. Add created_at column
    op.add_column(
        "users",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Account creation timestamp",
        ),
    )
    # 4. Add last_login column
    op.add_column(
        "users",
        sa.Column(
            "last_login",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last successful login timestamp",
        ),
    )

    # 5. Seed / update existing users with appropriate roles and departments
    conn = op.get_bind()
    conn.execute(
        text(
            """
            UPDATE users
            SET role = 'admin',
                first_name = COALESCE(first_name, 'System'),
                last_name = COALESCE(last_name, 'Admin'),
                department = 'Executive & Operations Oversight'
            WHERE email = 'admin@example.com'
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE users
            SET role = 'technician',
                first_name = COALESCE(first_name, 'Alex'),
                last_name = COALESCE(last_name, 'Chen'),
                department = 'SMT Line 1 - Dispensing'
            WHERE email = 'tech@example.com'
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE users
            SET role = 'viewer',
                first_name = COALESCE(first_name, 'Marcus'),
                last_name = COALESCE(last_name, 'Vance'),
                department = 'Quality Audit & Compliance'
            WHERE email = 'viewer@example.com'
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE users
            SET role = 'engineer',
                department = 'Process Engineering'
            WHERE email = 'sarah.mitchell@example.com'
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE users
            SET role = 'technician',
                department = 'SMT Line 2 - Dispensing'
            WHERE email = 'jaynetan@gmail.com'
            """
        )
    )


def downgrade() -> None:
    op.drop_column("users", "last_login")
    op.drop_column("users", "created_at")
    op.drop_column("users", "department")
    op.drop_column("users", "role")
