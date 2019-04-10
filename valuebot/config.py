import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Set, TypeVar, Union

import yaml

from .utils import update_map_recursively

__all__ = ["MENTION_VALUE", "Config", "load_config"]

log = logging.getLogger(__name__)

MENTION_VALUE = "@mention"


@dataclass()
class PointsConfig:
    """Config for points cog."""
    increase_reactions: Set[str]
    decrease_reactions: Set[str]


@dataclass()
class Config:
    """Config for valuebot."""
    discord_token: str
    command_prefixes: Set[str]

    postgres_dsn: str
    postgres_points_table: str
    points: PointsConfig

    def __str__(self) -> str:
        redacted_keys = {"discord_token", "postgres_dsn"}
        redacted_str = 5 * "*"

        str_repr = repr(self)

        for redacted_key in redacted_keys:
            try:
                value = repr(getattr(self, redacted_key))
            except AttributeError:
                pass
            else:
                if value:
                    str_repr = str_repr.replace(value, redacted_str, 1)

        return str_repr


def load_env_config(delimiter: str = None) -> Dict[str, Any]:
    """Build a nested config from the environment variables.

    Args:
        delimiter: Namespace separator.
    """
    if not delimiter:
        delimiter = "__"

    data: Dict[str, Any] = {}

    for raw_key, raw_value in os.environ.items():
        *parts, key = raw_key.lower().split(delimiter)

        try:
            value = yaml.safe_load(raw_value)
        except Exception:
            log.info(f"Couldn't parse environment variable {raw_key} = {raw_value!r}")
            continue

        container = data
        for part in parts:
            try:
                container = container[part]
            except KeyError:
                container = container[part] = {}
            except Exception:
                log.info(f"Couldn't traverse path {parts} from {raw_key} in {container}")
                break
        else:
            container[key] = value

    return data


def load_file_config(location: str = None) -> Optional[Dict[str, Any]]:
    """Load config from file.

    Args:
        location: Config file location.
    """
    try:
        with open(location or "config.yml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except OSError as e:
        log.warning(f"Couldn't read config file {location}! : {e!r}")
    else:
        return data

    return None


DEFAULT = object()

T = TypeVar("T")
V = TypeVar("V")
U = TypeVar("U")


class ConfigError(Exception):
    ...


def get_value(container: Mapping[T, V], key: T, *, default: U = DEFAULT, msg: str = None) -> Union[V, U]:
    """Get the value of a key from a container.

    Args:
        container: Container to access value from
        key: Key to get
        default: Default value to use if key doesn't exist.
            If not set the function will raise an error
        msg: Message text to use for the error if key
            doesn't exist and no default is set.

    Raises:
        ConfigError: If key doesn't exist in container and no default is set.

    Returns:
        Value of the key in the container or the default value if set.
    """
    try:
        return container[key]
    except KeyError:
        if default is DEFAULT:
            raise ConfigError(msg or f"\"{key}\" needs to be set!")
        else:
            return default


def get_value_seq(container: Mapping[T, V], key: T, *, default: U = DEFAULT, msg: str = None) -> Union[List[V], U]:
    """Get the list value of a key from a container.

    Args:
        container: Container to access value from
        key: Key to get
        default: Default value to use if key doesn't exist.
            If not set the function will raise an error
        msg: Message text to use for the error if key
            doesn't exist and no default is set.

    Raises:
        ConfigError: If key doesn't exist in container and no default is set.

    Returns:
        List value of the given key, or the default if set.
        If the key points to a non-list value it is converted
        to a list with a single element.
    """
    value = get_value(container, key, default=default, msg=msg)
    if isinstance(value, list):
        return value
    else:
        return [value]


def get_value_map(container: Mapping[T, V], key: T, *, default: U = DEFAULT, msg: str = None) -> Union[Mapping, U]:
    """Get a nested mapping value of a key from a container.

    Args:
        container: Container to access value from
        key: Key to get
        default: Default value to use if key doesn't exist.
            If not set the function will raise an error
        msg: Message text to use for the error if key
            doesn't exist and no default is set.

    Raises:
        ConfigError: If key doesn't exist in container and no default is set or
            if the value isn't a mapping.

    Returns:
        Mapping value of the key in the container, or default if set.
    """
    value = get_value(container, key, default=default, msg=msg)
    if isinstance(value, Mapping):
        return value

    raise ConfigError(f"{key} must be an object, not {type(value)}")


def build_points_config(container: Mapping) -> PointsConfig:
    """Build the points config from a container."""
    return PointsConfig(
        increase_reactions=set(get_value_seq(container, "increase_reaction", default=["👍"])),
        decrease_reactions=set(get_value_seq(container, "decrease_reaction", default=["👎"])),
    )


def build_config(container: Mapping) -> Config:
    """Build the config from a container."""
    return Config(
        discord_token=get_value(container, "discord_token"),
        command_prefixes=set(get_value_seq(container, "command_prefix", default=[MENTION_VALUE])),
        postgres_dsn=get_value(container, "postgres_dsn", default="postgresql://postgres@localhost"),
        postgres_points_table=get_value(container, "postgres_points_table", default="points"),
        points=build_points_config(get_value_map(container, "points", default={})),
    )


def load_config(*,
                load_file: bool = True,
                load_env: bool = True,
                file_location: str = None,
                env_delimiter: str = None) -> Config:
    """Load and build the config.

    Args:
        load_file: Whether to load the config file
        load_env: Whether to load config from the environment
        file_location: Specify config file location (defaults to "config.yml")
        env_delimiter: Specify the environment namespace delimiter (defaults to "__")

    Raises:
        ConfigError: If the loaded config is invalid
    """
    if load_file:
        data = load_file_config(file_location) or {}
    else:
        data = {}

    if load_env:
        update_map_recursively(data, load_env_config(env_delimiter))

    return build_config(data)
