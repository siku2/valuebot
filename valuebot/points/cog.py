import logging
from ast import literal_eval
from datetime import datetime
from typing import Callable, Dict, Optional, Set, cast

import asyncpg
import discord
from discord.ext.commands import Cog, CommandError, Context, command, guild_only

from valuebot import RoleConfig, ValueBot
from valuebot.utils import get_message
from .db import ensure_points_table, get_user_points, user_change_points, user_set_points
from .roles import RoleManager

__all__ = ["PointCog"]

log = logging.getLogger(__name__)

ARITH_OPS: Dict[str, Callable[[float, float], float]] = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: a / b,
    "^": lambda a, b: a ** b,
}


class PointCog(Cog, name="Point"):
    """Keep track of user points."""
    bot: ValueBot
    role_manager: RoleManager

    def __init__(self, bot: ValueBot) -> None:
        self.bot = bot
        self.role_manager = RoleManager(bot.config.points.roles)

    @property
    def pg_conn(self) -> asyncpg.Connection:
        return self.bot.postgres_connection

    @property
    def pg_points_table(self) -> str:
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
        await ensure_points_table(self.pg_conn, self.pg_points_table)

    async def handle_reaction_change(self, payload: discord.RawReactionActionEvent, added: bool) -> None:
        if payload.guild_id is None:
            log.debug(f"ignoring reaction by {payload.user_id} in DMs.")
            return

        emoji: discord.PartialEmoji = payload.emoji
        emoji_name: str = emoji.name

        if emoji_name in self.point_increase_reactions:
            change = 1
        elif emoji_name in self.point_decrease_reactions:
            change = -1
        else:
            return

        log.debug(
            f"handling reaction change (added={added}) {emoji_name} "
            f"[msg={payload.message_id}, channel={payload.channel_id}, guild={payload.guild_id}]"
        )

        if not added:
            change *= -1

        channel: Optional[discord.TextChannel] = self.bot.get_channel(payload.channel_id)
        if not channel:
            log.warning(f"Can't track reaction change, channel with id {payload.channel_id} not in cache")
            return

        message = await get_message(channel, payload.message_id)
        user_id = message.author.id
        guild_id = message.guild.id if message.guild else None

        log.debug(f"Changing points of {message.author} by {change}")

        await self.change_points(user_id, guild_id, change)

    @Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        await self.handle_reaction_change(payload, True)

    @Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        await self.handle_reaction_change(payload, False)

    async def show_points(self, ctx: Context, *, user: discord.User = None) -> None:
        """Show the amount of points a user has."""
        user = user or ctx.author
        guild_id = ctx.guild.id if ctx.guild else None

        embed = discord.Embed(colour=discord.Colour.blue(), timestamp=datetime.utcnow())
        embed.set_author(name=user.display_name, icon_url=user.avatar_url)

        # remove point first for the special case of user == author
        author_points = await self.change_points(ctx.author.id, guild_id, -1)

        if user == ctx.author:
            points = author_points
        else:
            points = await self.get_points(user.id, guild_id)

        if points is None:
            embed.description = f"{user.mention} hasn't received any points yet."
        else:
            role = self.get_role_for(points)
            if role:
                role_text = f" and is part of the role **{role.name}**"
            else:
                role_text = ""

            embed.description = f"{user.mention} currently has **{points}** point(s) {role_text}"

        embed.set_footer(
            text=f"You paid a point to see the points of {user.name}. You now have {author_points} point(s).")

        await self.bot.send_embed(ctx, embed)

    @guild_only()
    @command("points", aliases=["alter"])
    async def points_cmd(self, ctx: Context, user: discord.User = None, *, value: str = None) -> None:
        """Change/Inspect a user's points."""
        if value:
            value = value.replace(" ", "")

        user_id = user.id if user else ctx.author.id
        guild_id: Optional[int] = ctx.guild.id if ctx.guild else None

        if not value:
            await self.show_points(ctx, user=user)
            return

        perms = cast(discord.TextChannel, ctx.channel).permissions_for(ctx.author)
        if not perms.administrator:
            raise CommandError("Your are missing the Administrator permission to manipulate points.")

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

        current_value = await self.get_points(user_id, guild_id) or 0

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

        await self.set_points(user.id, guild_id, new_value)

        log.info(f"changed {user}'s points from {current_value} to {new_value}")

        embed = discord.Embed(
            description=f"{user.mention} now has **{new_value}** point(s), changed from previous {current_value}",
            colour=discord.Colour.green())
        await self.bot.send_embed(ctx, embed)

    def get_role_for(self, points: int) -> Optional[RoleConfig]:
        """Get the role (if available) for the given amount of points."""
        return self.bot.config.points.roles.get_role(points)

    async def get_points(self, user_id: int, guild_id: Optional[int]) -> Optional[int]:
        """Get a user's points.

        Returns:
            The amount of points the user has in the provided guild (or globally
            if the guild is `None`). Returns `None` if the user doesn't have
            any points yet.
        """
        return await get_user_points(self.pg_conn, self.pg_points_table, user_id, guild_id)

    async def set_points(self, user_id: int, guild_id: Optional[int], value: int) -> int:
        """Set a user's points to a specific value.

        Args:
            user_id: User whose points to set.
            guild_id: Guild to set the points for, `None` for global.
            value: Amount of points to set to.

        Returns:
            The new amount of points.
        """
        prev_points = await self.get_points(user_id, guild_id)
        await user_set_points(self.pg_conn, self.pg_points_table, user_id, guild_id, value)
        self.bot.loop.create_task(self.on_points_change(user_id, guild_id, prev_points, value))

        return value

    async def change_points(self, user_id: int, guild_id: Optional[int], change: int) -> int:
        """Change a user's points relative to their current amount.

        Args:
            user_id: User whose points to set.
            guild_id: Guild to set the points for, `None` for global.
            change: Points to add to the user's current points. Can be negative
                to subtract points.

        Returns:
            The new amount of points.
        """
        prev_points = await self.get_points(user_id, guild_id)
        await user_change_points(self.pg_conn, self.pg_points_table, user_id, guild_id, change)

        if prev_points:
            next_points = prev_points + change
        else:
            next_points = change

        self.bot.loop.create_task(self.on_points_change(user_id, guild_id, prev_points, next_points))

        return prev_points or 0

    async def on_points_change(self, user_id: int, guild_id: Optional[int],
                               old_points: Optional[int], new_points: Optional[int]) -> None:
        """Called when a user's points changes."""
        log.info(f"handling points change from {old_points} to {new_points} for {user_id} (guild={guild_id})")

        if not guild_id:
            return

        guild: Optional[discord.Guild] = self.bot.get_guild(guild_id)
        if not guild:
            return

        if not cast(discord.Member, guild.me).guild_permissions.manage_roles:
            log.debug(f"unable to adjust roles in {guild}: missing permissions")
            return

        member: Optional[discord.Member] = guild.get_member(user_id)
        if not member:
            return

        role = self.get_role_for(new_points)
        await self.role_manager.assign_role(member, role)
