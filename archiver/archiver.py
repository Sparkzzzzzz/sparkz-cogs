"""
Archiver Cog for Red-DiscordBot
Allows archiving channels and categories with full state restoration.
"""

import asyncio
import discord
from datetime import datetime, timezone
from typing import Optional

from redbot.core import commands, Config, checks
from redbot.core.bot import Red

CHANNEL_ICONS = {
    "text": "💬",
    "voice": "🔊",
    "stage_voice": "🎙️",
    "forum": "📋",
    "news": "📣",
}


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
        """Return permission overwrites: deny everyone + all roles, allow only admin roles."""
        admin_role_ids = set(await self.config.guild(guild).admin_roles())
        admin_roles = [guild.get_role(r) for r in admin_role_ids if guild.get_role(r)]

        # Start by explicitly denying every role in the server
        overwrites = {}
        for role in guild.roles:
            if role in admin_roles:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True)
            else:
                overwrites[role] = discord.PermissionOverwrite(view_channel=False)

        return overwrites

    def _serialize_overwrites(self, overwrites: dict) -> list:
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
            "category_snapshot_id": category_snapshot_id,
            "overwrites": self._serialize_overwrites(channel.overwrites),
            "archived_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _snapshot_category(self, category: discord.CategoryChannel) -> dict:
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
    #  archive group
    # ------------------------------------------------------------------ #

    @commands.group(name="archive")
    @checks.admin_or_permissions(manage_guild=True)
    async def archive_group(self, ctx: commands.Context):
        """Archiving commands."""

    # ---- archive admins ------------------------------------------------

    @archive_group.group(name="admins")
    async def archive_admins(self, ctx: commands.Context):
        """Manage roles that can see archived channels."""

    @archive_admins.command(name="add")
    async def archive_admins_add(self, ctx: commands.Context, *roles: discord.Role):
        """Add roles that can view the archive category. Syncs permissions to all archived channels immediately."""
        if not roles:
            return await ctx.send("Please specify at least one role.")
        async with self.config.guild(ctx.guild).admin_roles() as admin_roles:
            added = []
            for role in roles:
                if role.id not in admin_roles:
                    admin_roles.append(role.id)
                    added.append(role.name)
        if not added:
            return await ctx.send("Those roles were already in the list.")
        await ctx.send(
            f"✅ Added archive admin roles: {', '.join(added)}. Syncing permissions to all archived channels..."
        )
        synced, failed = await self._sync_archive_permissions(ctx.guild)
        await ctx.send(
            f"🔄 Synced permissions on {synced} channel(s)."
            + (f"\n⚠️ Failed on {failed} channel(s)." if failed else "")
        )

    @archive_admins.command(name="remove")
    async def archive_admins_remove(self, ctx: commands.Context, *roles: discord.Role):
        """Remove roles from the archive admin list. Syncs permissions to all archived channels immediately."""
        if not roles:
            return await ctx.send("Please specify at least one role.")
        async with self.config.guild(ctx.guild).admin_roles() as admin_roles:
            removed = []
            for role in roles:
                if role.id in admin_roles:
                    admin_roles.remove(role.id)
                    removed.append(role.name)
        if not removed:
            return await ctx.send("Those roles weren't in the list.")
        await ctx.send(
            f"✅ Removed archive admin roles: {', '.join(removed)}. Syncing permissions to all archived channels..."
        )
        synced, failed = await self._sync_archive_permissions(ctx.guild)
        await ctx.send(
            f"🔄 Synced permissions on {synced} channel(s)."
            + (f"\n⚠️ Failed on {failed} channel(s)." if failed else "")
        )

    @archive_admins.command(name="sync")
    async def archive_admins_sync(self, ctx: commands.Context):
        """Manually sync current admin role permissions to every channel in the archive category."""
        cat_id = await self.config.guild(ctx.guild).archive_category_id()
        if not cat_id:
            return await ctx.send("❌ No archive category set.")

        # Re-fetch fresh from cache
        archive_cat = ctx.guild.get_channel(cat_id)
        if not archive_cat:
            return await ctx.send("❌ Archive category not found in this server.")

        admin_roles = await self._admin_roles(ctx.guild)
        roles_text = (
            ", ".join(r.name for r in admin_roles) if admin_roles else "*(none)*"
        )
        channels = list(archive_cat.channels)

        await ctx.send(
            f"🔄 Found **{len(channels)}** channel(s) in **{archive_cat.name}**\n"
            f"Admin roles being applied: {roles_text}"
        )

        synced, failed = await self._sync_archive_permissions(ctx.guild)
        await ctx.send(
            f"✅ Done — synced {synced} channel(s)."
            + (
                f"\n⚠️ Failed on {failed} channel(s) — check logs with `[p]traceback`."
                if failed
                else ""
            )
        )

    # ---- archive createcategory ----------------------------------------

    @archive_group.command(name="createcategory")
    async def archive_create_category(self, ctx: commands.Context, *, name: str):
        """
        Create a new archive category with admin-only permissions.
        If no archive category is currently set, prompts to use this one as the destination.

        Example: [p]archive createcategory Old Channels
        """
        overwrites = await self._build_archive_overwrites(ctx.guild)

        try:
            new_cat = await ctx.guild.create_category(name, overwrites=overwrites)
        except discord.Forbidden:
            return await ctx.send("❌ I don't have permission to create categories.")
        except discord.HTTPException as e:
            return await ctx.send(f"❌ Failed to create category: {e}")

        current_archive_cat = await self._get_archive_category(ctx.guild)

        if current_archive_cat is None:
            await ctx.send(
                f"✅ Created category **{new_cat.name}**.\n"
                f"⚠️ No archive category is currently set. "
                f"Would you like to set **{new_cat.name}** as the archive destination? "
                f"Reply with `yes` or `no`."
            )

            def check(m):
                return (
                    m.author == ctx.author
                    and m.channel == ctx.channel
                    and m.content.lower() in ("yes", "no", "y", "n")
                )

            try:
                reply = await self.bot.wait_for("message", check=check, timeout=30.0)
            except TimeoutError:
                return await ctx.send(
                    "⏱️ Timed out. Category was created but not set as the archive destination."
                )

            if reply.content.lower() in ("yes", "y"):
                await self.config.guild(ctx.guild).archive_category_id.set(new_cat.id)
                await ctx.send(
                    f"✅ **{new_cat.name}** is now set as the archive category."
                )
            else:
                await ctx.send(
                    f"👍 Category **{new_cat.name}** created but not set as the archive destination."
                )
        else:
            await ctx.send(
                f"✅ Created category **{new_cat.name}**.\n"
                f"ℹ️ Your current archive destination is still **{current_archive_cat.name}**. "
                f"Use `{ctx.clean_prefix}category set` to change it."
            )

    # ---- archive add <channels> ----------------------------------------

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
                await channel.edit(category=archive_cat)
                await asyncio.sleep(0.3)
                await self._apply_overwrites(channel, archive_overwrites)
                moved.append(channel.mention)
                await asyncio.sleep(0.5)

        await ctx.send(f"✅ Archived {len(moved)} channel(s): {', '.join(moved)}")

    # ---- archive <category> --------------------------------------------

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

        moved = []
        failed = []
        channels = list(category.channels)
        for i, channel in enumerate(channels):
            try:
                # Step 1: move the channel into the archive category
                await channel.edit(category=archive_cat)
                await asyncio.sleep(0.3)
                # Step 2: apply archive overwrites one target at a time
                await self._apply_overwrites(channel, archive_overwrites)
                moved.append(channel.name)
            except discord.Forbidden:
                failed.append(channel.name)
            except discord.HTTPException as e:
                failed.append(f"{channel.name} ({e})")
            if i < len(channels) - 1:
                await asyncio.sleep(0.5)

        await category.delete(reason=f"Archived by {ctx.author}")

        msg = f"✅ Archived category **{snapshot['name']}** — moved {len(moved)}/{len(snapshot['children'])} channel(s)."
        if failed:
            msg += f"\n⚠️ Failed on: {', '.join(failed)}"
        await ctx.send(msg)

    # ---- archive settings ----------------------------------------------

    @archive_group.command(name="settings")
    async def archive_settings(self, ctx: commands.Context):
        """Show the current archiver configuration for this server."""
        guild = ctx.guild
        archive_cat = await self._get_archive_category(guild)
        admin_roles = await self._admin_roles(guild)
        items = await self.config.guild(guild).archived_items()

        cat_value = (
            f"**{archive_cat.name}** (ID: {archive_cat.id})"
            if archive_cat
            else "*(not set)*"
        )
        roles_value = (
            ", ".join(r.mention for r in admin_roles) if admin_roles else "*(none set)*"
        )

        cat_count = sum(1 for v in items.values() if v["type"] == "category")
        ch_count = sum(1 for v in items.values() if v["type"] == "channel")
        total_channels = ch_count + sum(
            len(v["snapshot"]["children"])
            for v in items.values()
            if v["type"] == "category"
        )

        embed = discord.Embed(
            title="⚙️ Archiver Settings",
            color=discord.Color.og_blurple(),
        )
        embed.add_field(name="📁 Archive Category", value=cat_value, inline=False)
        embed.add_field(name="🔑 Admin Roles", value=roles_value, inline=False)
        embed.add_field(
            name="📊 Archive Stats",
            value=(
                f"**{cat_count}** archived categor{'y' if cat_count == 1 else 'ies'}\n"
                f"**{ch_count}** individually archived channel{'s' if ch_count != 1 else ''}\n"
                f"**{total_channels}** total channel{'s' if total_channels != 1 else ''} stored"
            ),
            inline=False,
        )
        embed.set_footer(text=f"Server: {guild.name}")
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------ #
    #  archived list  (reads JSON, displays as original structure)
    # ------------------------------------------------------------------ #

    @commands.command(name="archived")
    @checks.admin_or_permissions(manage_guild=True)
    async def archived_list(self, ctx: commands.Context):
        """
        List all archived items exactly as they originally were —
        categories with their channels grouped underneath.
        """
        items = await self.config.guild(ctx.guild).archived_items()
        if not items:
            return await ctx.send("📭 Nothing has been archived yet.")

        # Separate categories and lone channels, sort by archived_at
        categories = sorted(
            [(k, v) for k, v in items.items() if v["type"] == "category"],
            key=lambda x: x[1]["snapshot"].get("archived_at", ""),
        )
        lone_channels = sorted(
            [(k, v) for k, v in items.items() if v["type"] == "channel"],
            key=lambda x: x[1]["snapshot"].get("archived_at", ""),
        )

        embeds = []

        # --- Archived categories ---
        for _key, entry in categories:
            snap = entry["snapshot"]
            ts = snap.get("archived_at", "")[:10] or "unknown date"
            children = sorted(snap.get("children", []), key=lambda c: c["position"])

            lines = []
            for ch in children:
                icon = CHANNEL_ICONS.get(ch["type"].replace("ChannelType.", ""), "💬")
                suffix = ""
                if ch.get("topic"):
                    suffix = f"  — *{ch['topic'][:60]}{'…' if len(ch['topic']) > 60 else ''}*"
                lines.append(f"{icon} **#{ch['name']}**{suffix}")

            channel_block = "\n".join(lines) if lines else "*No channels*"

            embed = discord.Embed(
                title=f"📁 {snap['name']}",
                description=channel_block,
                color=discord.Color.gold(),
            )
            embed.set_footer(text=f"Archived on {ts}  •  {len(children)} channel(s)")
            embeds.append(embed)

        # --- Lone channels (grouped into one embed) ---
        if lone_channels:
            lines = []
            for _key, entry in lone_channels:
                snap = entry["snapshot"]
                icon = CHANNEL_ICONS.get(snap["type"].replace("ChannelType.", ""), "💬")
                ts = snap.get("archived_at", "")[:10] or "?"
                original_cat_id = snap.get("category_id")
                original_cat = (
                    ctx.guild.get_channel(original_cat_id) if original_cat_id else None
                )
                cat_note = f" *(was in: {original_cat.name})*" if original_cat else ""
                lines.append(f"{icon} **#{snap['name']}**{cat_note}  — archived {ts}")

            embed = discord.Embed(
                title="📄 Individually Archived Channels",
                description="\n".join(lines),
                color=discord.Color.blurple(),
            )
            embeds.append(embed)

        if not embeds:
            return await ctx.send("📭 Nothing has been archived yet.")

        # Send all embeds (Discord allows up to 10 per message)
        for i in range(0, len(embeds), 10):
            await ctx.send(embeds=embeds[i : i + 10])

    # ------------------------------------------------------------------ #
    #  unarchive
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

        async with self.config.guild(ctx.guild).archived_items() as items_mutable:
            del items_mutable[match_key]

    # ------------------------------------------------------------------ #
    #  Restore helpers
    # ------------------------------------------------------------------ #

    async def _restore_category(self, ctx: commands.Context, snapshot: dict):
        guild = ctx.guild
        overwrites = self._deserialize_overwrites(guild, snapshot["overwrites"])

        new_cat = await guild.create_category(
            snapshot["name"],
            overwrites=overwrites,
            position=snapshot["position"],
        )

        children = sorted(snapshot["children"], key=lambda c: c["position"])
        restored = []
        failed = []
        for ch_snap in children:
            try:
                await self._restore_channel_to_category(guild, ch_snap, new_cat)
                restored.append(ch_snap["name"])
            except discord.Forbidden:
                failed.append(ch_snap["name"])
            except discord.HTTPException as e:
                failed.append(f"{ch_snap['name']} ({e})")

        msg = f"✅ Restored category **{snapshot['name']}** with {len(restored)}/{len(children)} channel(s)."
        if failed:
            msg += f"\n⚠️ Failed to restore: {', '.join(failed)}"
        await ctx.send(msg)

    async def _restore_channel(self, ctx: commands.Context, snapshot: dict):
        guild = ctx.guild
        overwrites = self._deserialize_overwrites(guild, snapshot["overwrites"])
        original_cat = (
            guild.get_channel(snapshot["category_id"])
            if snapshot.get("category_id")
            else None
        )

        try:
            await self._create_channel_from_snapshot(
                guild, snapshot, original_cat, overwrites
            )
            dest = original_cat.name if original_cat else "no category"
            await ctx.send(f"✅ Restored channel **#{snapshot['name']}** to {dest}.")
        except discord.Forbidden:
            await ctx.send(
                f"❌ Missing permissions to restore **#{snapshot['name']}**."
            )
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to restore **#{snapshot['name']}**: {e}")

    async def _restore_channel_to_category(
        self,
        guild: discord.Guild,
        snapshot: dict,
        category: discord.CategoryChannel,
    ):
        overwrites = self._deserialize_overwrites(guild, snapshot["overwrites"])
        await self._create_channel_from_snapshot(guild, snapshot, category, overwrites)
        await asyncio.sleep(0.75)

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

        if ch_type in ("text", "ChannelType.text"):
            if snapshot.get("topic"):
                kwargs["topic"] = snapshot["topic"]
            if snapshot.get("slowmode_delay"):
                kwargs["slowmode_delay"] = snapshot["slowmode_delay"]
            if snapshot.get("nsfw"):
                kwargs["nsfw"] = snapshot["nsfw"]
            channel = await guild.create_text_channel(**kwargs)

        elif ch_type in ("voice", "ChannelType.voice"):
            if snapshot.get("bitrate"):
                kwargs["bitrate"] = snapshot["bitrate"]
            if snapshot.get("user_limit"):
                kwargs["user_limit"] = snapshot["user_limit"]
            channel = await guild.create_voice_channel(**kwargs)

        elif ch_type in ("stage_voice", "ChannelType.stage_voice"):
            channel = await guild.create_stage_channel(**kwargs)

        elif ch_type in ("forum", "ChannelType.forum"):
            channel = await guild.create_forum(**kwargs)

        else:
            channel = await guild.create_text_channel(**kwargs)

        return channel

    async def _apply_overwrites(
        self, channel: discord.abc.GuildChannel, overwrites: dict
    ):
        """Apply a full set of permission overwrites to a channel using set_permissions."""
        # Remove any existing overwrites not in the new set
        for target in list(channel.overwrites):
            if target not in overwrites:
                await channel.set_permissions(target, overwrite=None)
                await asyncio.sleep(0.3)
        # Set each new overwrite individually
        for target, overwrite in overwrites.items():
            await channel.set_permissions(target, overwrite=overwrite)
            await asyncio.sleep(0.3)

    async def _sync_archive_permissions(self, guild: discord.Guild):
        """Apply current admin role overwrites to every channel in the archive category.
        Returns (synced_count, failed_count)."""
        cat_id = await self.config.guild(guild).archive_category_id()
        if not cat_id:
            return 0, 0
        archive_cat = guild.get_channel(cat_id)
        if not archive_cat:
            return 0, 0

        new_overwrites = await self._build_archive_overwrites(guild)
        synced = 0
        failed = 0

        import logging

        log = logging.getLogger("red.archiver")

        # Update the category itself first
        try:
            await self._apply_overwrites(archive_cat, new_overwrites)
        except discord.Forbidden as e:
            log.error(f"Forbidden updating category {archive_cat.name}: {e}")
        except discord.HTTPException as e:
            log.error(f"HTTPException updating category {archive_cat.name}: {e}")

        # Update every channel inside it
        channels = list(archive_cat.channels)
        for i, channel in enumerate(channels):
            try:
                await self._apply_overwrites(channel, new_overwrites)
                synced += 1
            except discord.Forbidden as e:
                failed += 1
                log.error(f"Forbidden syncing #{channel.name} ({channel.id}): {e}")
            except discord.HTTPException as e:
                failed += 1
                log.error(
                    f"HTTPException syncing #{channel.name} ({channel.id}): {e.status} {e.text}"
                )
            if i < len(channels) - 1:
                await asyncio.sleep(0.5)

        return synced, failed


async def setup(bot: Red):
    await bot.add_cog(Archiver(bot))
