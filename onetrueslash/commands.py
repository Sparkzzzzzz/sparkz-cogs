import asyncio
import functools
import heapq
import operator
from typing import Awaitable, Callable, Dict, List, cast

import discord
from rapidfuzz import fuzz
from redbot.core import app_commands, commands
from redbot.core.bot import Red
from redbot.core.commands.help import HelpSettings
from redbot.core.i18n import set_contextual_locale

from .context import InterContext
from .utils import walk_aliases


@app_commands.command(
    name="command",
    description="Run a command via slash.",
    extras={"red_force_enable": True},
)
@app_commands.describe(input="The full command to run (e.g., ban @user)")
async def command(interaction: discord.Interaction, input: str) -> None:
    """
    Run a command via slash.

    Parameters
    -----------
    input: str
        The full command to run, including arguments.
    """
    assert isinstance(interaction.client, Red)
    set_contextual_locale(str(interaction.guild_locale or interaction.locale))
    ctx = await InterContext.from_interaction(interaction, recreate_message=True)

    parts = input.split()
    if not parts:
        await interaction.response.send_message(
            "❌ Please provide a command to run.", ephemeral=True
        )
        return

    cmd_name = parts[0]
    actual = interaction.client.get_command(cmd_name)
    error = None

    ferror: asyncio.Task = asyncio.create_task(
        interaction.client.wait_for("command_error", check=lambda c, _: c is ctx)
    )
    ferror.add_done_callback(lambda _: setattr(ctx, "interaction", interaction))

    # Fake a message so Redbot's command processor sees it
    ctx.message.content = f"{ctx.prefix}{input}"
    await interaction.client.invoke(ctx)

    if not interaction.response.is_done():
        ctx._deferring = True
        await interaction.response.defer(ephemeral=True)
    if ferror.done():
        error = ferror.exception() or ferror.result()[1]
    ferror.cancel()

    if ctx._deferring and not interaction.is_expired():
        if error is None:
            if ctx._ticked:
                await interaction.followup.send(ctx._ticked, ephemeral=True)
            else:
                await interaction.delete_original_response()
        elif isinstance(error, commands.CommandNotFound):
            await interaction.followup.send(
                f"❌ Command `{cmd_name}` was not found.", ephemeral=True
            )
        elif isinstance(error, commands.CheckFailure):
            await interaction.followup.send(
                f"❌ You don't have permission to run `{cmd_name}`.", ephemeral=True
            )


@command.autocomplete("input")
async def command_autocomplete(
    interaction: discord.Interaction, current: str
) -> List[app_commands.Choice[str]]:
    assert isinstance(interaction.client, Red)

    if not await interaction.client.allowed_by_whitelist_blacklist(interaction.user):
        return []

    ctx = await InterContext.from_interaction(interaction)
    if not await interaction.client.message_eligible_as_command(ctx.message):
        return []

    help_settings = await HelpSettings.from_context(ctx)

    if current:
        extracted = cast(
            List[str],
            await asyncio.get_event_loop().run_in_executor(
                None,
                heapq.nlargest,
                6,
                walk_aliases(interaction.client, show_hidden=help_settings.show_hidden),
                functools.partial(fuzz.token_sort_ratio, current),
            ),
        )
        extracted.append("help")
    else:
        extracted = ["help"]

    _filter: Callable[[commands.Command], Awaitable[bool]] = operator.methodcaller(
        "can_run" if help_settings.show_hidden else "can_see", ctx
    )

    matches: Dict[commands.Command, str] = {}
    for name in extracted:
        command = interaction.client.get_command(name)
        if not command or command in matches:
            continue
        try:
            if name == "help" and await command.can_run(ctx) or await _filter(command):
                if len(name) > 100:
                    name = name[:99] + "\N{HORIZONTAL ELLIPSIS}"
                matches[command] = name
        except commands.CommandError:
            pass
    return [app_commands.Choice(name=name, value=name) for name in matches.values()]


@command.error
async def command_error(interaction: discord.Interaction, error: Exception):
    assert isinstance(interaction.client, Red)
    if isinstance(error, app_commands.CommandInvokeError):
        error = error.original
    error = getattr(error, "original", error)
    await interaction.client.on_command_error(
        await InterContext.from_interaction(interaction, recreate_message=True),
        commands.CommandInvokeError(error),
    )
