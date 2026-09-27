from contextlib import contextmanager

from django.db import connection, transaction


class DatabaseConnection:
    """Owns database connection lifecycle and transaction boundaries."""

    def connect(self):
        connection.ensure_connection()
        return connection

    @contextmanager
    def transaction(self):
        self.connect()
        with transaction.atomic(using=connection.alias):
            yield

    def close(self):
        connection.close()
