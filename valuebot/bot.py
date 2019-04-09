import logging

import asyncpg
from discord import Colour, Embed
from discord.ext.commands import Bot, CommandError, Context

from .config import Config

__all__ = ["ValueBot", "create_bot"]

log = logging.getLogger(__name__)


class ValueBot(Bot):
    """Value bot

    Attributes:
        config (Config): Config used for the bot
        postgres_connection (asyncpg.Connection): Postgres connection used by the bot
    """

    config: Config
    postgres_connection: asyncpg.Connection

    def __init__(self, config: Config, postgres_connection: asyncpg.Connection, **kwargs) -> None:
        super().__init__(config.command_prefix, **kwargs)
        self.config = config
        self.postgres_connection = postgres_connection

    async def on_command_error(self, ctx: Context, exception: CommandError) -> None:
        log.info(f"Command Error in {ctx}: {exception!r}")

        embed = Embed(description=str(exception), colour=Colour.red())
        await ctx.send(embed=embed)


async def create_bot(config: Config, **kwargs) -> ValueBot:
    """Create a `ValueBot` instance.

    Args:
        config: Config to use
        **kwargs: Additional keyword arguments to pass to the constructor
    """
    log.info("connecting to postgres database")
    postgres_connection = await asyncpg.connect(config.postgres_dsn)

    return ValueBot(config, postgres_connection, **kwargs)
