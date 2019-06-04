import asyncio
import logging
from collections import defaultdict
from contextlib import suppress
from typing import Dict, Iterable, Optional

import discord

from valuebot import RoleConfig, Roles

log = logging.getLogger(__name__)

__all__ = ["RoleManager"]


def find_role(guild: discord.Guild, role: RoleConfig) -> Optional[discord.Role]:
    """Find a role in a guild.

    Args:
        guild: Guild to find role in.
        role: Role to find.

    Returns:
        Discord Role for the role in question. If it doesn't exist, `None` is
        returned.
    """
    for dis_role in guild.roles:
        if dis_role.name == role.name:
            return dis_role

    return None


class RoleManager:
    roles: Roles
    _guild_locks: Dict[int, asyncio.Lock]

    def __init__(self, roles: Roles):
        self.roles = roles
        self._guild_locks = defaultdict(asyncio.Lock)

    async def assign_role(self, member: discord.Member, role: RoleConfig, *,
                          reason: str = "switching role") -> None:
        """Assign a role to a member.

        Args:
            member: Member to assign role to.
            role: Role to assign.
            reason: Reason to provide for changing roles.
        """
        other_roles = set(self.roles)
        other_roles.discard(role)

        new_dis_role, other_dis_roles = await asyncio.gather(
            self.get_role(member.guild, role),
            self.get_roles(member.guild, other_roles),
        )

        await asyncio.gather(
            member.remove_roles(*other_dis_roles.values(), reason=reason),
            member.add_roles(new_dis_role, reason=reason),
        )

    async def get_roles(self, guild: discord.Guild, roles: Iterable[RoleConfig]) -> Dict[RoleConfig, discord.Role]:
        await self.ensure_roles(guild)

        dis_roles: Dict[RoleConfig, discord.Role] = {}
        missing_roles = {role.name: role for role in roles}

        for dis_role in guild.roles:
            role = missing_roles.pop(dis_role.name, None)
            if role:
                dis_roles[role] = dis_role

        if missing_roles:
            raise ValueError(f"Guild {guild} is missing roles: {list(missing_roles.keys())}")

        return dis_roles

    async def get_role(self, guild: discord.Guild, role: RoleConfig) -> discord.Role:
        dis_role = find_role(guild, role)
        if dis_role:
            return dis_role

        log.info(f"couldn't find role {role} in {guild}")
        await self.ensure_roles(guild)

        dis_role = find_role(guild, role)
        if dis_role:
            return dis_role
        else:
            raise ValueError(f"Couldn't find role {role} in guild {guild}")

    async def _ensure_roles(self, guild: discord.Guild) -> None:
        missing_roles = {role.name: role for role in self.roles}

        for dis_role in guild.roles:
            with suppress(KeyError):
                del missing_roles[dis_role.name]

        if not missing_roles:
            return

        log.info(f"Guild {guild} is missing the following roles: {missing_roles}")

        fs = []

        for role in missing_roles.values():
            fs.append(guild.create_role(name=role.name, reason="valuebot ensuring roles"))

        await asyncio.gather(*fs)

        log.info(f"created {len(fs)} roles for guild {guild}")

    async def ensure_roles(self, guild: discord.Guild) -> None:
        """Make sure the given guild has all roles.

        Args:
            guild: Guild to ensure roles for.
        """
        async with self._guild_locks[guild.id]:
            return await self._ensure_roles(guild)
