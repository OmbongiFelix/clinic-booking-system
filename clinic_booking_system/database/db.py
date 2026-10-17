# database/db.py
"""Shared SQLAlchemy declarative base.

All ORM model classes inherit from ``Base``. The single shared ``Base``
means a single ``MetaData`` object, which Alembic uses to auto-generate
migrations (``target_metadata = Base.metadata`` in ``alembic/env.py``).

``MappedAsDataclass`` gives every model a generated ``__init__`` based on
the ``Mapped`` annotations, avoiding boilerplate ``__init__`` methods.
``kw_only=True`` prevents field-order errors when a parent class has
fields without defaults and a child adds fields with defaults.
"""

from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass


class Base(MappedAsDataclass, DeclarativeBase, kw_only=True):
    """Single shared Base → single MetaData.

    kw_only avoids dataclass field-order errors when mixing fields that
    have defaults (e.g. ``server_default``) with fields that do not.
    """
