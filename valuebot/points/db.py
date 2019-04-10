import logging
from typing import Optional

import asyncpg

__all__ = ["ensure_points_table", "get_user_points", "user_change_points", "user_set_points"]

log = logging.getLogger(__name__)


async def ensure_points_table(postgres_connection: asyncpg.Connection, table: str) -> None:
    """Ensure the points table exists.

    Args:
        postgres_connection: Connection to execute with
        table: Table name
    """
    await postgres_connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {table}
        (
            points   INTEGER DEFAULT 0  NOT NULL,
            user_id  BIGINT             NOT NULL,
            guild_id BIGINT  DEFAULT -1 NOT NULL,
            CONSTRAINT points_pk
                PRIMARY KEY (user_id, guild_id)
        );

        CREATE INDEX IF NOT EXISTS points_guild_id_user_id_index
            ON {table} (guild_id, user_id);

        CREATE INDEX IF NOT EXISTS points_points_index
            ON {table} (points DESC);
    """)


async def get_user_points(postgres_connection: asyncpg.Connection, table: str, user_id: int, guild_id: Optional[int]) -> Optional[int]:
    """Get a user's points.

    Args:
        postgres_connection: Connection to execute statement with
        table: Points table
        user_id: user id of the user
        guild_id: guild id of the guild. Can be `None` if global
    """
    if guild_id is None:
        guild_id = -1

    row = await postgres_connection.fetchrow(f"SELECT points FROM {table} WHERE user_id = $1 AND guild_id = $2;",
                                             user_id, guild_id)
    if row is None:
        return None

    return row["points"]


async def user_change_points(postgres_connection: asyncpg.Connection, table: str, user_id: int, guild_id: Optional[int], change: int) -> None:
    """Change a user's points relative to the previous amount.

    Args:
        postgres_connection: Connection to execute statement with
        table: Points table
        user_id: user id of the user
        guild_id: guild id of the guild. Can be `None` if global
        change: Relative change compared to previous amount.
            Positive for increase, negative for decrease.
    """
    if guild_id is None:
        guild_id = -1

    await postgres_connection.execute(f"INSERT INTO {table} VALUES ($1, $2, $3) ON CONFLICT ON CONSTRAINT points_pk DO "
                                      f"UPDATE SET points = {table}.points + $1;",
                                      change, user_id, guild_id)


async def user_set_points(postgres_connection: asyncpg.Connection, table: str, user_id: int, guild_id: Optional[int], points: int) -> None:
    """Set a user's points to a specific amount.

        Args:
            postgres_connection: Connection to execute statement with
            table: Points table
            user_id: user id of the user
            guild_id: guild id of the guild. Can be `None` if global
            points: Points to set
        """
    if guild_id is None:
        guild_id = -1

    await postgres_connection.execute(f"INSERT INTO {table} VALUES ($1, $2, $3) ON CONFLICT ON CONSTRAINT points_pk DO "
                                      f"UPDATE SET points = $1;",
                                      points, user_id, guild_id)
