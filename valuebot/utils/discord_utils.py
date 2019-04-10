import logging
from typing import Any, Optional

from discord import Client, Message, TextChannel
from discord.state import ConnectionState

__all__ = ["get_state", "get_message"]

log = logging.getLogger(__name__)


def get_state(obj: Any) -> ConnectionState:
    """Get the connection state from a Discord model.

    Args:
        obj: Discord class to extract state from

    Raises:
        TypeError: If the provided object doesn't have access to the state
    """
    if isinstance(obj, ConnectionState):
        return obj
    elif isinstance(obj, Client):
        # noinspection PyProtectedMember
        return obj._connection

    try:
        # noinspection PyProtectedMember
        return obj._state
    except AttributeError:
        raise TypeError(f"{obj} doesn't have access to the connection state!")


async def get_message(channel: TextChannel, message_id: int) -> Message:
    """Get a message by its id.

    Args:
        channel: Channel to get message from
        message_id: Message id to get

    Raises:
        Exceptions raised by `TextChannel.fetch_message`.

    Returns:
        Message with the given id.
    """
    state = get_state(channel)

    # noinspection PyProtectedMember
    msg: Optional[Message] = state._get_message(message_id)
    if msg:
        return msg

    log.debug(f"Couldn't find message {message_id} in state, using fetch...")
    return await channel.fetch_message(message_id)
