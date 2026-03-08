"""Custom SQLAlchemy column types."""

import uuid

from sqlalchemy import BINARY, TypeDecorator
from sqlalchemy.engine.interfaces import Dialect


class MySQLUUID(TypeDecorator[uuid.UUID]):
    """Stores UUID as BINARY(16) for MySQL/MariaDB compatibility."""

    impl = BINARY(16)
    cache_ok = True

    def process_bind_param(self, value: uuid.UUID | str | None, dialect: Dialect) -> bytes | None:
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        return value.bytes

    def process_result_value(self, value: bytes | None, dialect: Dialect) -> uuid.UUID | None:
        if value is None:
            return None
        return uuid.UUID(bytes=value)
