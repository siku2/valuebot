import logging
from ast import literal_eval
from typing import Callable, Dict, Optional, Set

import asyncpg
from discord import Colour, Embed, PartialEmoji, RawReactionActionEvent, User
from discord.ext.commands import Cog, CommandError, Context, command

from .bot import ValueBot

__all__ = ["ensure_points_table", "get_user_points", "user_change_points", "user_set_points", "PointCog"]

log = logging.getLogger(__name__)

ARITH_OPS: Dict[str, Callable[[float, float], float]] = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: a / b,
    "^": lambda a, b: a ** b,
}


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


class PointCog(Cog, name="Point"):
    bot: ValueBot

    def __init__(self, bot: ValueBot) -> None:
        self.bot = bot

    @property
    def postgres_connection(self) -> asyncpg.Connection:
        return self.bot.postgres_connection

    @property
    def postgres_points_table(self) -> str:
        return self.bot.config.postgres_points_table

    @property
    def point_increase_reactions(self) -> Set[str]:
        return self.bot.config.points.increase_reactions

    @property
    def point_decrease_reactions(self) -> Set[str]:
        return self.bot.config.points.decrease_reactions

    @Cog.listener()
    async def on_ready(self) -> None:
        log.info("making sure points table exists")
        await ensure_points_table(self.postgres_connection, self.postgres_points_table)

    async def handle_reaction_change(self, payload: RawReactionActionEvent, added: bool) -> None:
        emoji: PartialEmoji = payload.emoji
        emoji_name: str = emoji.name

        if emoji_name in self.point_increase_reactions:
            change = 1
        elif emoji_name in self.point_decrease_reactions:
            change = -1
        else:
            return

        if log.isEnabledFor(logging.DEBUG):
            log.debug(
                f"handling reaction change (added={added}) {emoji_name} "
                f"[msg={payload.message_id}, channel={payload.channel_id}, guild={payload.guild_id}]"
            )

        if not added:
            change *= -1

        await user_change_points(self.postgres_connection, self.postgres_points_table, payload.user_id, payload.guild_id, change)

    @Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent) -> None:
        await self.handle_reaction_change(payload, True)

    @Cog.listener()
    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent) -> None:
        await self.handle_reaction_change(payload, False)

    async def show_points(self, ctx: Context, *, user: User = None) -> None:
        pass

    @command("points")
    async def points_cmd(self, ctx: Context, user: User = None, *, value: str = None) -> None:
        """Change/Inspect a user's points."""
        if value:
            value = value.replace(" ", "")

        user_id = user.id if user else ctx.author.id
        guild_id: Optional[int] = ctx.guild.id if ctx.guild else None

        if not value:
            await self.show_points(ctx, user=user)
            return

        try:
            arith_op_str = value[0]
            arith_op = ARITH_OPS[arith_op_str]
        except KeyError:
            arith_op_str = "="
            arith_op = None
        else:
            value = value[1:]

        try:
            numeric_value = literal_eval(value)
        except Exception:
            log.debug(f"Couldn't interpret {value} as numeric. Showing points for user instead!")
            await self.show_points(ctx, user=user)
            return

        if not isinstance(numeric_value, (int, float)):
            raise CommandError(f"{numeric_value} (\"{value}\") is not a number!")

        current_value = await get_user_points(self.postgres_connection, self.postgres_points_table, user_id, guild_id) or 0

        if arith_op is not None:
            try:
                new_value = arith_op(current_value, numeric_value)
            except Exception:
                raise CommandError(f"Invalid operation {current_value} {arith_op_str} {value}")
        else:
            new_value = numeric_value

        new_value = round(new_value)

        if new_value == current_value:
            raise CommandError(f"{user.mention} already has {current_value} point(s)")

        await user_set_points(self.postgres_connection, self.postgres_points_table, user.id, guild_id, new_value)

        log.info(f"changed {user}'s points from {current_value} to {new_value}")

        embed = Embed(description=f"{user.mention} now has **{new_value}** points, changed from previous {current_value}", colour=Colour.green())
        await ctx.send(embed=embed)
