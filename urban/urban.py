import aiohttp
import discord
from redbot.core import commands


class Urban(commands.Cog):
    """Urban Dictionary lookup with pagination."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def define(self, ctx, *, term: str):
        """Search Urban Dictionary for a definition."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://api.urbandictionary.com/v0/define?term={term}"
            ) as resp:
                if resp.status != 200:
                    return await ctx.send("❌ Unable to contact Urban Dictionary.")
                data = await resp.json()

        defs = data.get("list", [])
        if not defs:
            return await ctx.send(f"No definitions found for `{term}`.")

        await self._send_page(ctx, term, defs, 0)

    async def _send_page(self, ctx, term, defs, index):
        """Send an embed for the current definition index."""
        entry = defs[index]
        embed = discord.Embed(
            title=f"{term} — {index + 1}/{len(defs)}",
            description=entry.get("definition", "No definition found."),
            color=discord.Color.blue(),
        )
        if entry.get("example"):
            embed.add_field(name="Example", value=entry["example"], inline=False)
        embed.set_footer(
            text=f"👍 {entry.get('thumbs_up', 0)}  👎 {entry.get('thumbs_down', 0)} • by {entry.get('author', 'unknown')}"
        )

        # Build buttons
        view = discord.ui.View()

        # Previous button
        prev_button = discord.ui.Button(
            label="Previous", style=discord.ButtonStyle.primary
        )

        async def prev_callback(interaction):
            await interaction.response.edit_message(
                embed=self._build_embed(term, defs, (index - 1) % len(defs)),
                view=self._build_view(ctx, term, defs, (index - 1) % len(defs)),
            )

        prev_button.callback = prev_callback
        view.add_item(prev_button)

        # Next button
        next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.primary)

        async def next_callback(interaction):
            await interaction.response.edit_message(
                embed=self._build_embed(term, defs, (index + 1) % len(defs)),
                view=self._build_view(ctx, term, defs, (index + 1) % len(defs)),
            )

        next_button.callback = next_callback
        view.add_item(next_button)

        # Close button
        close_button = discord.ui.Button(
            label="Close", style=discord.ButtonStyle.danger
        )

        async def close_callback(interaction):
            await interaction.message.delete()

        close_button.callback = close_callback
        view.add_item(close_button)

        await ctx.send(embed=embed, view=view)

    def _build_embed(self, term, defs, index):
        """Build embed for a given definition."""
        entry = defs[index]
        embed = discord.Embed(
            title=f"{term} — {index + 1}/{len(defs)}",
            description=entry.get("definition", "No definition found."),
            color=discord.Color.blue(),
        )
        if entry.get("example"):
            embed.add_field(name="Example", value=entry["example"], inline=False)
        embed.set_footer(
            text=f"👍 {entry.get('thumbs_up', 0)}  👎 {entry.get('thumbs_down', 0)} • by {entry.get('author', 'unknown')}"
        )
        return embed

    def _build_view(self, ctx, term, defs, index):
        """Rebuild navigation view for given index."""
        view = discord.ui.View()

        prev_button = discord.ui.Button(
            label="Previous", style=discord.ButtonStyle.primary
        )

        async def prev_callback(interaction):
            await interaction.response.edit_message(
                embed=self._build_embed(term, defs, (index - 1) % len(defs)),
                view=self._build_view(ctx, term, defs, (index - 1) % len(defs)),
            )

        prev_button.callback = prev_callback
        view.add_item(prev_button)

        next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.primary)

        async def next_callback(interaction):
            await interaction.response.edit_message(
                embed=self._build_embed(term, defs, (index + 1) % len(defs)),
                view=self._build_view(ctx, term, defs, (index + 1) % len(defs)),
            )

        next_button.callback = next_callback
        view.add_item(next_button)

        close_button = discord.ui.Button(
            label="Close", style=discord.ButtonStyle.danger
        )

        async def close_callback(interaction):
            await interaction.message.delete()

        close_button.callback = close_callback
        view.add_item(close_button)

        return view
