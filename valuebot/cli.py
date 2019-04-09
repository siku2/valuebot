import asyncio
import logging
from asyncio import AbstractEventLoop

import click
import colorlog


def setup_logging() -> None:
    """Prepare logging."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    formatter = colorlog.ColoredFormatter("{log_color}{levelname:8}{reset} {name:24} {blue}{message}", style="{")
    handler.setFormatter(formatter)

    root.addHandler(handler)

    valuebot = logging.getLogger("valuebot")
    valuebot.setLevel(logging.DEBUG)


def get_loop() -> AbstractEventLoop:
    """Get the event loop"""
    return asyncio.get_event_loop()


@click.command()
@click.option("--config", "-c", default="config.yml")
def cli(config: str) -> None:
    """Simple CLI for starting and managing valuebot."""
    setup_logging()

    log = logging.getLogger(__name__)

    import valuebot

    log.debug("loading config")
    config = valuebot.load_config(file_location=config)

    loop = get_loop()
    log.debug("creating bot")
    bot: valuebot.ValueBot = loop.run_until_complete(valuebot.create_bot(config, loop=loop))

    log.debug("running bot")
    bot.run(config.discord_token)
