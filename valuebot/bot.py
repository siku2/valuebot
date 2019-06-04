import logging
from typing import Callable, List, Set, Union

import asyncpg
from discord import Colour, Embed, Message
from discord.abc import Messageable
from discord.ext.commands import Bot, CommandError, Context, when_mentioned_or

from .config import Config, MENTION_VALUE

__all__ = ["ValueBot", "create_bot"]

log = logging.getLogger(__name__)

DISCORD_MSG_LEN_LIMIT = 2000


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


def truncate_str(s: str, max_len: int, *, suffix: str = "[...]") -> str:
    """Truncate a string so it's no longer than max_len.

    Args:
        s: String to truncate.
        max_len: Max length which will not be exceeded by the returned string.
        suffix: Suffix to append to the end of the string if it's too long.

    Returns:
        New string which is guaranteed to have a length smaller or equal to
        max_len.
    """
    if len(s) <= max_len:
        return s
    else:
        adj_len = max_len - len(suffix)
        if adj_len > 0:
            return s[:adj_len] + suffix
        else:
            return suffix


def embed_to_text(embed: Embed, *, max_len: int = DISCORD_MSG_LEN_LIMIT) -> str:
    """Convert an embed to a text representation.

    Args:
        embed: Embed to convert to text.
        max_len: Max length of the message.
            Defaults to the discord message length limit.
            If negative the value is subtracted from the discord limit.

    Returns:
        Text representation of the embed.
    """
    if max_len < 0:
        max_len = DISCORD_MSG_LEN_LIMIT - max_len

    chars_left = max_len

    text = ""

    desc = embed.description
    if desc:
        desc = truncate_str(desc, chars_left)
        chars_left -= len(desc)
        text += desc

    title = embed.title
    if title:
        title = f"**{title}**\n\n"
        if len(title) <= chars_left:
            chars_left -= len(title)
            text = title + text

    author_name = embed.author.name
    if author_name:
        author_name = f"[{author_name}]\n"
        if len(author_name) <= chars_left:
            chars_left -= len(author_name)
            text = author_name + text

    footer = embed.footer.text
    if footer:
        footer = f"\n\n*{footer}*"
        if len(footer) <= chars_left:
            chars_left -= len(footer)
            text += footer

    return text


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
        await self.send_embed(ctx, embed)

    async def send_embed(self, target: Messageable, embed: Embed, *,
                         content: str = None,
                         raw_converter: Union[str, Callable[[Embed], str]] = None,
                         **kwargs) -> Message:
        """Send an embed respecting the `use_embeds` config value.

        If the config dictates that no embeds should be send, the embed
        is converted to a raw text message.

        Args:
            target: Target to send the message to.
            embed: Embed to send.
            content: Text content in addition to the embed to send.
            raw_converter: Converter function or text to be sent if no embed
                should be sent.
            **kwargs: Additional arguments to pass to the send method.

        Returns:
            Message that was sent.
        """

        if self.config.use_embeds:
            return await target.send(content=content, embed=embed, **kwargs)
        else:
            if raw_converter:
                if isinstance(raw_converter, str):
                    text = raw_converter
                else:
                    text = raw_converter(embed)
            else:
                if content:
                    text = f"{content}\n\n"
                    text += embed_to_text(embed, max_len=-len(text))
                else:
                    text = embed_to_text(embed)

            return await target.send(content=text, **kwargs)


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
