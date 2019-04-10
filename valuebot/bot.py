import logging
from typing import List, Set

import asyncpg
from discord import Colour, Embed
from discord.ext.commands import Bot, CommandError, Context, when_mentioned_or

from .config import Config, MENTION_VALUE

__all__ = ["ValueBot", "create_bot"]

log = logging.getLogger(__name__)


def create_command_prefix(prefixes: Set[str]):
    """Create the command prefix argument from the config.

    Args:
        prefixes: Set of prefixes from the config

    Returns:
        Either a list of strings or a callable which should be passed
        to the "command_prefix" of a `discord.Bot`.
    """
    sorted_prefixes: List[str] = sorted(prefixes, key=len, reverse=True)

    if MENTION_VALUE in prefixes:
        sorted_prefixes.remove(MENTION_VALUE)
        return when_mentioned_or(*sorted_prefixes)
    else:
        return sorted_prefixes


class ValueBot(Bot):
    """Value bot

    Attributes:
        config (Config): Config used for the bot
        postgres_connection (asyncpg.Connection): Postgres connection used by the bot
    """

    config: Config
    postgres_connection: asyncpg.Connection

    def __init__(self, config: Config, postgres_connection: asyncpg.Connection, **kwargs) -> None:
        command_prefix = create_command_prefix(config.command_prefixes)
        super().__init__(command_prefix=command_prefix, **kwargs)

        self.config = config
        self.postgres_connection = postgres_connection

    @classmethod
    async def on_command(cls, ctx: Context) -> None:
        log.info(f"Command \"{ctx.command}\" invoked by {ctx.author}")

    async def on_command_error(self, ctx: Context, exception: CommandError) -> None:
        log.info(f"Command Error in {ctx.command}: {exception!r}")

        embed = Embed(description=str(exception), colour=Colour.red())
        await ctx.send(embed=embed)


def add_cogs(bot: ValueBot) -> None:
    """Add cogs to the bot."""
    from .points import PointCog

    bot.add_cog(PointCog(bot))


async def create_bot(config: Config, **kwargs) -> ValueBot:
    """Create a `ValueBot` instance.

    Args:
        config: Config to use
        **kwargs: Additional keyword arguments to pass to the constructor
    """
    log.info("connecting to postgres database")
    postgres_connection = await asyncpg.connect(config.postgres_dsn)

    bot = ValueBot(config, postgres_connection, **kwargs)

    add_cogs(bot)

    return bot
