"""Initial schema: patients, doctors, doctor_working_hours, appointments.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-17

Creates all tables and constraints as defined in the data model (README §11).

Key constraints:
- ``patients.email`` is unique (one record per email address).
- ``doctor_working_hours`` has a unique constraint on (doctor_id, weekday)
  and check constraints on weekday range and start_time < end_time.
- ``appointments.status`` is constrained to 'booked' or 'cancelled'.
- A cancelled appointment always has a reason and timestamp.
- A partial unique index on ``(doctor_id, start_time) WHERE status = 'booked'``
  is the database-level exclusivity guarantee (README §10, §16).
- An index on ``(patient_id, start_time)`` speeds up the upcoming-appointments query.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── patients ────────────────────────────────────────────────────────────
    op.create_table(
        "patients",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("fullname", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_patients"),
        sa.UniqueConstraint("email", name="uq_patients_email"),
    )

    # ── doctors ─────────────────────────────────────────────────────────────
    op.create_table(
        "doctors",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("fullname", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id", name="pk_doctors"),
    )

    # ── doctor_working_hours ─────────────────────────────────────────────────
    op.create_table(
        "doctor_working_hours",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("doctor_id", sa.BigInteger(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_doctor_working_hours"),
        sa.ForeignKeyConstraint(
            ["doctor_id"], ["doctors.id"],
            name="fk_working_hours_doctor",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("doctor_id", "weekday", name="uq_working_hours_doctor_weekday"),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_working_hours_weekday"),
        sa.CheckConstraint("start_time < end_time", name="ck_working_hours_range"),
    )

    # ── appointments ────────────────────────────────────────────────────────
    op.create_table(
        "appointments",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("doctor_id", sa.BigInteger(), nullable=False),
        sa.Column("patient_id", sa.BigInteger(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="booked"),
        sa.Column("cancellation_reason", sa.String(500), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_appointments"),
        sa.ForeignKeyConstraint(
            ["doctor_id"], ["doctors.id"],
            name="fk_appointments_doctor",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"], ["patients.id"],
            name="fk_appointments_patient",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('booked', 'cancelled')",
            name="ck_appointments_status",
        ),
        sa.CheckConstraint(
            "status = 'booked' OR "
            "(cancellation_reason IS NOT NULL AND cancelled_at IS NOT NULL)",
            name="ck_appointments_cancel_fields",
        ),
    )

    # Partial unique index: one booked appointment per doctor per slot.
    # This is the database-level exclusivity guarantee (README §11, §16).
    op.create_index(
        "uq_appointments_doctor_start_booked",
        "appointments",
        ["doctor_id", "start_time"],
        unique=True,
        postgresql_where=sa.text("status = 'booked'"),
    )

    # Composite index for the patient's upcoming-appointments query.
    op.create_index(
        "ix_appointments_patient_start",
        "appointments",
        ["patient_id", "start_time"],
    )


def downgrade() -> None:
    op.drop_index("ix_appointments_patient_start", table_name="appointments")
    op.drop_index("uq_appointments_doctor_start_booked", table_name="appointments")
    op.drop_table("appointments")
    op.drop_table("doctor_working_hours")
    op.drop_table("doctors")
    op.drop_table("patients")
