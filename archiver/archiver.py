"""
Archiver Cog for Red-DiscordBot
Allows archiving channels and categories with full state restoration.
"""

import discord
import json
import os
from datetime import datetime, timezone
from typing import Optional, Union

from redbot.core import commands, Config, checks
from redbot.core.bot import Red


class Archiver(commands.Cog):
    """Archive channels and categories, and restore them perfectly."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=114753329, force_registration=True
        )

        default_guild = {
            "archive_category_id": None,  # the designated archive category
            "admin_roles": [],  # role IDs that can see archived channels
            "archived_items": {},  # keyed by original channel/category id (str)
        }
        self.config.register_guild(**default_guild)

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    async def _get_archive_category(
        self, guild: discord.Guild
    ) -> Optional[discord.CategoryChannel]:
        cat_id = await self.config.guild(guild).archive_category_id()
        if cat_id:
            return guild.get_channel(cat_id)
        return None

    async def _admin_roles(self, guild: discord.Guild):
        ids = await self.config.guild(guild).admin_roles()
        return [guild.get_role(r) for r in ids if guild.get_role(r)]

    async def _build_archive_overwrites(self, guild: discord.Guild):
        """Return permission overwrites: default deny everyone, allow admin roles."""
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
        }
        for role in await self._admin_roles(guild):
            overwrites[role] = discord.PermissionOverwrite(view_channel=True)
        return overwrites

    def _serialize_overwrites(self, overwrites: dict) -> list:
        """Turn discord PermissionOverwrite dict into a JSON-safe list."""
        result = []
        for target, ow in overwrites.items():
            allow, deny = ow.pair()
            result.append(
                {
                    "type": "role" if isinstance(target, discord.Role) else "member",
                    "id": target.id,
                    "allow": allow.value,
                    "deny": deny.value,
                }
            )
        return result

    def _deserialize_overwrites(self, guild: discord.Guild, data: list) -> dict:
        """Rebuild overwrites dict from serialised data."""
        overwrites = {}
        for entry in data:
            if entry["type"] == "role":
                target = guild.get_role(entry["id"])
            else:
                target = guild.get_member(entry["id"])
            if target is None:
                continue
            allow = discord.Permissions(entry["allow"])
            deny = discord.Permissions(entry["deny"])
            overwrites[target] = discord.PermissionOverwrite.from_pair(allow, deny)
        return overwrites

    async def _snapshot_channel(
        self,
        channel: discord.abc.GuildChannel,
        category_snapshot_id: Optional[int] = None,
    ) -> dict:
        """Capture everything needed to perfectly restore a channel."""
        return {
            "id": channel.id,
            "name": channel.name,
            "type": str(channel.type),
            "position": channel.position,
            "topic": getattr(channel, "topic", None),
            "slowmode_delay": getattr(channel, "slowmode_delay", 0),
            "nsfw": getattr(channel, "is_nsfw", lambda: False)(),
            "bitrate": getattr(channel, "bitrate", None),
            "user_limit": getattr(channel, "user_limit", None),
            "category_id": channel.category_id,
            "category_snapshot_id": category_snapshot_id,  # ref to parent snapshot
            "overwrites": self._serialize_overwrites(channel.overwrites),
            "archived_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _snapshot_category(self, category: discord.CategoryChannel) -> dict:
        """Capture everything needed to perfectly restore a category + children."""
        children = []
        for ch in category.channels:
            children.append(
                await self._snapshot_channel(ch, category_snapshot_id=category.id)
            )

        return {
            "id": category.id,
            "name": category.name,
            "position": category.position,
            "overwrites": self._serialize_overwrites(category.overwrites),
            "children": children,
            "archived_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------ #
    #  category group
    # ------------------------------------------------------------------ #

    @commands.group(name="category")
    @checks.admin_or_permissions(manage_guild=True)
    async def category_group(self, ctx: commands.Context):
        """Manage archive categories."""

    @category_group.command(name="set")
    async def category_set(
        self, ctx: commands.Context, category: discord.CategoryChannel
    ):
        """Set an existing category as the archive destination."""
        await self.config.guild(ctx.guild).archive_category_id.set(category.id)
        await ctx.send(f"✅ Archive category set to **{category.name}**.")

    @category_group.command(name="create")
    async def category_create(self, ctx: commands.Context, *, name: str):
        """Create a new archive category (admin-eyes-only) and set it as the destination."""
        overwrites = await self._build_archive_overwrites(ctx.guild)
        category = await ctx.guild.create_category(name, overwrites=overwrites)
        await self.config.guild(ctx.guild).archive_category_id.set(category.id)
        await ctx.send(f"✅ Created and set archive category **{category.name}**.")

    # ------------------------------------------------------------------ #
    #  archive admins group
    # ------------------------------------------------------------------ #

    @commands.group(name="archive")
    @checks.admin_or_permissions(manage_guild=True)
    async def archive_group(self, ctx: commands.Context):
        """Archiving commands."""

    @archive_group.group(name="admins")
    async def archive_admins(self, ctx: commands.Context):
        """Manage roles that can see archived channels."""

    @archive_admins.command(name="add")
    async def archive_admins_add(self, ctx: commands.Context, *roles: discord.Role):
        """Add roles that can view the archive category."""
        if not roles:
            return await ctx.send("Please specify at least one role.")
        async with self.config.guild(ctx.guild).admin_roles() as admin_roles:
            added = []
            for role in roles:
                if role.id not in admin_roles:
                    admin_roles.append(role.id)
                    added.append(role.name)
        if added:
            await ctx.send(f"✅ Added archive admin roles: {', '.join(added)}")
        else:
            await ctx.send("Those roles were already in the list.")

    @archive_admins.command(name="remove")
    async def archive_admins_remove(self, ctx: commands.Context, *roles: discord.Role):
        """Remove roles from the archive admin list."""
        if not roles:
            return await ctx.send("Please specify at least one role.")
        async with self.config.guild(ctx.guild).admin_roles() as admin_roles:
            removed = []
            for role in roles:
                if role.id in admin_roles:
                    admin_roles.remove(role.id)
                    removed.append(role.name)
        if removed:
            await ctx.send(f"✅ Removed archive admin roles: {', '.join(removed)}")
        else:
            await ctx.send("Those roles weren't in the list.")

    # ------------------------------------------------------------------ #
    #  archive add <channels>
    # ------------------------------------------------------------------ #

    @archive_group.command(name="add")
    async def archive_add(
        self, ctx: commands.Context, *channels: discord.abc.GuildChannel
    ):
        """Archive individual channels (moves them into the archive category)."""
        if not channels:
            return await ctx.send("Please specify at least one channel.")

        archive_cat = await self._get_archive_category(ctx.guild)
        if not archive_cat:
            return await ctx.send(
                "❌ No archive category set. Use `category set` or `category create` first."
            )

        archive_overwrites = await self._build_archive_overwrites(ctx.guild)
        async with self.config.guild(ctx.guild).archived_items() as items:
            moved = []
            for channel in channels:
                snapshot = await self._snapshot_channel(channel)
                items[str(channel.id)] = {"type": "channel", "snapshot": snapshot}
                await channel.edit(category=archive_cat, sync_permissions=False)
                # lock down to admin-only
                await channel.edit(overwrites=archive_overwrites)
                moved.append(channel.mention)

        await ctx.send(f"✅ Archived {len(moved)} channel(s): {', '.join(moved)}")

    # ------------------------------------------------------------------ #
    #  archive <category>  (archive whole category)
    # ------------------------------------------------------------------ #

    @archive_group.command(name="category")
    async def archive_category(
        self, ctx: commands.Context, category: discord.CategoryChannel
    ):
        """Move all channels from a category into the archive, then delete the category."""
        archive_cat = await self._get_archive_category(ctx.guild)
        if not archive_cat:
            return await ctx.send(
                "❌ No archive category set. Use `category set` or `category create` first."
            )
        if category.id == archive_cat.id:
            return await ctx.send("❌ You can't archive the archive category itself.")

        snapshot = await self._snapshot_category(category)
        archive_overwrites = await self._build_archive_overwrites(ctx.guild)

        async with self.config.guild(ctx.guild).archived_items() as items:
            items[str(category.id)] = {"type": "category", "snapshot": snapshot}

        # Move every channel, apply archive perms
        for channel in list(category.channels):
            await channel.edit(category=archive_cat, sync_permissions=False)
            await channel.edit(overwrites=archive_overwrites)

        await category.delete(reason=f"Archived by {ctx.author}")
        await ctx.send(
            f"✅ Archived category **{category.name}** and moved {len(snapshot['children'])} channel(s) to the archive."
        )

    # ------------------------------------------------------------------ #
    #  archived list
    # ------------------------------------------------------------------ #

    @commands.command(name="archived")
    @checks.admin_or_permissions(manage_guild=True)
    async def archived_list(self, ctx: commands.Context):
        """List all archived channels and their original categories."""
        items = await self.config.guild(ctx.guild).archived_items()
        if not items:
            return await ctx.send("No items have been archived yet.")

        embed = discord.Embed(title="📦 Archived Items", color=discord.Color.blurple())

        category_entries = {}  # cat_id -> (cat_name, [channel_names])
        lone_channels = []

        for key, value in items.items():
            if value["type"] == "category":
                snap = value["snapshot"]
                names = [ch["name"] for ch in snap["children"]]
                category_entries[key] = (snap["name"], names, snap["archived_at"])
            elif value["type"] == "channel":
                snap = value["snapshot"]
                lone_channels.append((snap["name"], snap.get("archived_at", "?")))

        for _id, (cat_name, channels, archived_at) in category_entries.items():
            ts = archived_at[:10] if archived_at else "?"
            channel_list = (
                "\n".join(f"  • #{n}" for n in channels) or "  *(no channels)*"
            )
            embed.add_field(
                name=f"📁 {cat_name}  *(archived {ts})*",
                value=channel_list,
                inline=False,
            )

        if lone_channels:
            lone_text = "\n".join(
                f"• #{name}  *(archived {ts[:10]})*" for name, ts in lone_channels
            )
            embed.add_field(
                name="📄 Individual Channels", value=lone_text, inline=False
            )

        await ctx.send(embed=embed)

    # ------------------------------------------------------------------ #
    #  unarchive <channel or category name / id>
    # ------------------------------------------------------------------ #

    @commands.command(name="unarchive")
    @checks.admin_or_permissions(manage_guild=True)
    async def unarchive(self, ctx: commands.Context, *, target: str):
        """
        Unarchive a channel or category by name or original ID.
        Restores everything: position, permissions, and category structure.
        """
        items = await self.config.guild(ctx.guild).archived_items()
        if not items:
            return await ctx.send("Nothing is archived.")

        # Try to find matching entry (by original name or ID)
        match_key = None
        match_value = None
        target_lower = target.lower()

        for key, value in items.items():
            snap = value["snapshot"]
            if str(snap["id"]) == target or snap["name"].lower() == target_lower:
                match_key = key
                match_value = value
                break

        if match_key is None:
            return await ctx.send(f"❌ No archived item found matching `{target}`.")

        snap_type = match_value["type"]
        snapshot = match_value["snapshot"]

        if snap_type == "category":
            await self._restore_category(ctx, snapshot)
        else:
            await self._restore_channel(ctx, snapshot)

        # Remove from archive list
        async with self.config.guild(ctx.guild).archived_items() as items_mutable:
            del items_mutable[match_key]

    async def _restore_category(self, ctx: commands.Context, snapshot: dict):
        """Recreate a category and all its children exactly as they were."""
        guild = ctx.guild
        overwrites = self._deserialize_overwrites(guild, snapshot["overwrites"])

        # Create the category
        new_cat = await guild.create_category(
            snapshot["name"],
            overwrites=overwrites,
            position=snapshot["position"],
        )

        # Restore children in original position order
        children = sorted(snapshot["children"], key=lambda c: c["position"])
        for ch_snap in children:
            await self._restore_channel_to_category(guild, ch_snap, new_cat)

        await ctx.send(
            f"✅ Restored category **{snapshot['name']}** with {len(children)} channel(s)."
        )

    async def _restore_channel(self, ctx: commands.Context, snapshot: dict):
        """Restore a lone channel to its original category (if still exists) and permissions."""
        guild = ctx.guild
        overwrites = self._deserialize_overwrites(guild, snapshot["overwrites"])
        original_cat = (
            guild.get_channel(snapshot["category_id"])
            if snapshot.get("category_id")
            else None
        )

        channel = await self._create_channel_from_snapshot(
            guild, snapshot, original_cat, overwrites
        )
        dest = original_cat.name if original_cat else "no category"
        await ctx.send(f"✅ Restored channel **#{snapshot['name']}** to {dest}.")

    async def _restore_channel_to_category(
        self,
        guild: discord.Guild,
        snapshot: dict,
        category: discord.CategoryChannel,
    ):
        overwrites = self._deserialize_overwrites(guild, snapshot["overwrites"])
        await self._create_channel_from_snapshot(guild, snapshot, category, overwrites)

    async def _create_channel_from_snapshot(
        self,
        guild: discord.Guild,
        snapshot: dict,
        category: Optional[discord.CategoryChannel],
        overwrites: dict,
    ) -> discord.abc.GuildChannel:
        ch_type = snapshot["type"]
        kwargs = dict(
            name=snapshot["name"],
            overwrites=overwrites,
            category=category,
            position=snapshot["position"],
        )

        if ch_type == "text":
            if snapshot.get("topic"):
                kwargs["topic"] = snapshot["topic"]
            if snapshot.get("slowmode_delay"):
                kwargs["slowmode_delay"] = snapshot["slowmode_delay"]
            if snapshot.get("nsfw"):
                kwargs["nsfw"] = snapshot["nsfw"]
            channel = await guild.create_text_channel(**kwargs)

        elif ch_type == "voice":
            if snapshot.get("bitrate"):
                kwargs["bitrate"] = snapshot["bitrate"]
            if snapshot.get("user_limit"):
                kwargs["user_limit"] = snapshot["user_limit"]
            channel = await guild.create_voice_channel(**kwargs)

        elif ch_type == "stage_voice":
            channel = await guild.create_stage_channel(**kwargs)

        elif ch_type == "forum":
            channel = await guild.create_forum(**kwargs)

        else:
            # fallback: try text
            channel = await guild.create_text_channel(**kwargs)

        return channel


async def setup(bot: Red):
    await bot.add_cog(Archiver(bot))
