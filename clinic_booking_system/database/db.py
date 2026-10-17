#database/db.py
from datetime import datetime, time
from typing import List, Optional

from sqlalchemy.orm import (
    DeclarativeBase,
    MappedAsDataclass
)


class Base(MappedAsDataclass, DeclarativeBase, kw_only=True):
    """Single shared Base -> single MetaData. kw_only avoids dataclass field-order errors."""

