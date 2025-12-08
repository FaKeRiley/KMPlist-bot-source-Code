import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
from discord import app_commands
import os


# --- Konfiguration ---
ALLOWED_USER_ID =   # Nur diese User-ID darf /nuke benutzen
EXCLUDED_CHANNEL_IDS = [1422292807229505587, 1422283431022428]  # Channels, die nicht genutzt werden dürfen
REQUIRED_IMAGE_CHANNEL_IDS = [1422284161867059353, 1422301215584161812, 1422300749089607690, 1427029363060113428]  # Channels, in denen ein Bild Pflicht ist 
REPORT_APPROVAL_CHANNEL_ID = 1425598450795286639
LOG_FILE = "logs.txt"
PENALTY_FILE = "penalty.txt"
REPORT_STATS_FILE = "report_stats.txt"
TICKET_CATEGORY_ID = 1422304059531984937  # Kategorie für Tickets
SUPPORT_ROLE_ID = 1422287414935687219     # Rolle, die Tickets sehen kann
# Setze hier deine Whitelist-Rollen-ID ein:
WHITELIST_ROLE_ID = 1422613247755812914  # <- anpassen!
# ---------------------

intents = discord.Intents.default()
bot = commands.Bot(command_prefix=None, intents=intents)  # Nur Slash-Commands

# Ticket Counter
ticket_counter = 1

@bot.event
async def on_ready():
    print(f"✅ Eingeloggt als {bot.user} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Slash Commands synchronisiert: {len(synced)}")
    except Exception as e:
        print(f"Fehler beim Syncen: {e}")
    bot.add_view(VerifyButton())  # Button dauerhaft aktiv machen
    print(f"✅ Bot ist online als {bot.user}")


def add_penalty(user_id: int, grund: str):
    with open(PENALTY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{user_id} | {grund}\n")


# ---------- /report command ----------
class ReportApprovalView(discord.ui.View):
    def __init__(self, reporter_id: int, target_channel_id: int, embed: discord.Embed):
        super().__init__(timeout=None)
        self.reporter_id = reporter_id
        self.target_channel_id = target_channel_id
        self.embed = embed

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.success)
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only admins can approve reports.", ephemeral=True)
            return

        target_channel = interaction.guild.get_channel(self.target_channel_id)
        if not target_channel:
            await interaction.response.send_message("❌ Target channel not found.", ephemeral=True)
            return

        approved_embed = discord.Embed(title="📌 New Report (approved)", color=discord.Color.red())
        for field in self.embed.fields:
            approved_embed.add_field(name=field.name, value=field.value, inline=False)
        if self.embed.image:
            approved_embed.set_image(url=self.embed.image.url)
        approved_embed.add_field(name="✅ Status", value="Approved ✅", inline=False)

        msg = await target_channel.send(embed=approved_embed)

        # Write to log file
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(
                f"Reporter: {interaction.user} ({interaction.user.id}) | "
                f"TargetChannel: {target_channel.name} ({target_channel.id}) | "
                f"MessageID: {msg.id}\n"
            )

        add_report_stat(str(self.reporter_id))

        await interaction.response.edit_message(
            content=f"✅ Report has been approved and posted in {target_channel.mention}.",
            embed=None, view=None
        )

    @discord.ui.button(label="❌ Deny + Penalty", style=discord.ButtonStyle.danger)
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only admins can deny reports.", ephemeral=True)
            return

        # Add penalty
        add_penalty(self.reporter_id, "Report was denied by the team.")

        await interaction.response.edit_message(
            content=f"❌ Report was denied. A penalty has been added.",
            embed=None, view=None
        )


@bot.tree.command(name="report", description="Post an embed about a user into a channel")
@app_commands.describe(
    user="Name or text about the user",
    userid="The user ID",
    grund="Why?",
    channel="Which channel should it be posted in?",
    bild="Optional image"
)
async def report(
    interaction: discord.Interaction,
    user: str,
    userid: str,
    grund: str,
    channel: discord.TextChannel,
    bild: discord.Attachment = None
):
    # Check if channel is allowed
    if channel.id in EXCLUDED_CHANNEL_IDS:
        await interaction.response.send_message("❌ You cannot send a report to this channel.", ephemeral=True)
        return

    # --- Approval system ---
    if channel.id in REQUIRED_IMAGE_CHANNEL_IDS:
        approval_channel = bot.get_channel(REPORT_APPROVAL_CHANNEL_ID)
        if not approval_channel:
            await interaction.response.send_message("❌ Error: The approval channel could not be found.", ephemeral=True)
            return

        # Inform user
        await interaction.response.send_message(
            f"🕵️ Your report will first be reviewed in the approval channel before being published in {channel.mention}.",
            ephemeral=True
        )

        # Embed for the approval channel
        embed = discord.Embed(title="🕵️ New Report", color=discord.Color.dark_red())
        embed.add_field(name="👤 User (Text)", value=user, inline=False)
        embed.add_field(
            name="🆔 User ID",
            value=f"{userid}\n[➡️ Go to VRChat profile](https://vrchat.com/home/user/{userid})",
            inline=False
        )
        embed.add_field(name="📝 Reason", value=grund, inline=False)
        embed.add_field(name="👮 Reported by", value=interaction.user.mention, inline=False)
        embed.add_field(name="📨 Target Channel", value=channel.mention, inline=False)
        if bild:
            embed.set_image(url=bild.url)

        # View + send message
        view = ReportApprovalView(interaction.user.id, channel.id, embed)
        await approval_channel.send(
            content=f"📩 **New report awaiting approval:** from <@{interaction.user.id}> → Target: {channel.mention}",
            embed=embed,
            view=view
        )
        return

    # --- Normal report (no approval needed) ---
    embed = discord.Embed(title="📌 New Report", color=discord.Color.red())
    embed.add_field(name="👤 User", value=user, inline=False)
    embed.add_field(
        name="🆔 User ID",
        value=f"{userid}\n[➡️ Go to VRChat profile](https://vrchat.com/home/user/{userid})",
        inline=False
    )
    embed.add_field(name="📝 Reason", value=grund, inline=False)
    embed.add_field(name="👮 Reported by", value=interaction.user.mention, inline=False)
    if bild:
        embed.set_image(url=bild.url)

    msg = await channel.send(embed=embed)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(
            f"Reporter: {interaction.user} ({interaction.user.id}) | "
            f"User: {user} | UserID: {userid} | "
            f"Reason: {grund} | Channel: {channel.name} ({channel.id}) | "
            f"MessageID: {msg.id}\n"
        )

    add_report_stat(str(interaction.user.id))
    await interaction.response.send_message(f"✅ Your report has been posted in {channel.mention}!", ephemeral=True)



# ---------- /search command ----------
@bot.tree.command(name="search", description="Search the logs for any variables of a report")
@app_commands.describe(query="Search term (e.g. Reporter, User, UserID, Reason, Channel or MessageID)")
async def search(interaction: discord.Interaction, query: str):
    results = []
    guild_id = interaction.guild.id

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if query.lower() in line.lower():
                    parts = line.strip().split(" | ")
                    channel_part = next((p for p in parts if p.startswith("Channel:")), "")
                    message_part = next((p for p in parts if p.startswith("MessageID:")), "")
                    if channel_part and message_part:
                        try:
                            channel_id = int(channel_part.split("(")[-1].rstrip(")"))
                            message_id = int(message_part.split(":")[-1])
                            msg_link = f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
                            line += f" | [🔗 To the report]({msg_link})"
                        except:
                            pass
                    results.append(line)
    except FileNotFoundError:
        await interaction.response.send_message("❌ There are no logs yet.", ephemeral=True)
        return

    if not results:
        await interaction.response.send_message("❌ No entries found.", ephemeral=True)
        return

    display_results = results[:10]
    if len(results) > 10:
        display_results.append(f"...and {len(results)-10} more matches.")

    embed = discord.Embed(
        title=f"🔍 Search results for '{query}'",
        description="\n".join(display_results),
        color=discord.Color.blue()
    )

    message = await interaction.response.send_message(embed=embed)
    sent_message = await interaction.original_response()
    await sent_message.delete(delay=60)


# ---------- /nuke command ----------
@bot.tree.command(name="nuke", description="Löscht (so gut wie) alle Nachrichten in einem Channel — nur für autorisierte User")
@app_commands.describe(
    channel="Welcher Channel soll geleert werden?",
    confirm="Bestätige True um wirklich zu löschen (Schutz gegen versehentliches Ausführen)."
)
async def nuke(interaction: discord.Interaction, channel: discord.TextChannel, confirm: bool):
    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message("❌ Du bist nicht berechtigt, diesen Command auszuführen.", ephemeral=True)
        return

    if not confirm:
        await interaction.response.send_message("❗ Du musst `confirm=True` setzen, um den Nuke tatsächlich auszuführen.", ephemeral=True)
        return

    await interaction.response.send_message(f"💥 Nuke wird gestartet für {channel.mention}. Ältere Nachrichten (>~14 Tage) können nicht im Bulk gelöscht werden.", ephemeral=True)

    bot_member = channel.guild.me
    perms = channel.permissions_for(bot_member)
    if not (perms.manage_messages and perms.read_messages and perms.send_messages):
        await interaction.followup.send("❌ Bot benötigt die Rechte: Manage Messages, Read Messages und Send Messages in dem Ziel-Channel.", ephemeral=True)
        return

    try:
        deleted = await channel.purge(limit=200000)
        count = len(deleted)
        await interaction.followup.send(f"✅ Nuke abgeschlossen: {count} Nachrichten wurden entfernt (so weit möglich).", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Fehler beim Löschen: {e}", ephemeral=True)


# ---------- /ticket command ----------
@bot.tree.command(name="ticket", description="Create a support ticket")
async def ticket(interaction: discord.Interaction):
    global ticket_counter
    guild = interaction.guild
    category = guild.get_channel(TICKET_CATEGORY_ID)
    
    if category is None:
        await interaction.response.send_message("❌ Ticket category does not exist.", ephemeral=True)
        return

    channel_name = f"ticket-{ticket_counter}-{interaction.user.name}"
    ticket_counter += 1

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True),
        guild.get_role(SUPPORT_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True)
    }

    ticket_channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        topic=f"Ticket from {interaction.user} ({interaction.user.id})"
    )

    embed = discord.Embed(
        title="🎫 Support Ticket",
        description=f"Hello {interaction.user.mention}, a supporter will contact you shortly.\nPress ❌ below to close the ticket.",
        color=discord.Color.green()
    )

    # ----- View + Button -----
    class TicketCloseView(View):
        def __init__(self, ticket_channel):
            super().__init__(timeout=None)
            self.ticket_channel = ticket_channel

        @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, emoji="❌")
        async def close_ticket(self, interaction: discord.Interaction, button: Button):
            # Optional: Rechte prüfen
            if not (interaction.user.guild_permissions.manage_channels or interaction.user == ticket_channel.topic_user):
                await interaction.response.send_message("❌ You don't have permission to close this ticket.", ephemeral=True)
                return
            
            await interaction.response.send_message("🗑️ Closing ticket...", ephemeral=True)
            await self.ticket_channel.delete()

    # Ticket erstellen + Button einfügen
    view = TicketCloseView(ticket_channel)
    await ticket_channel.send(content=interaction.user.mention, embed=embed, view=view)
    await interaction.response.send_message(f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)


    # ---------- /say command ----------
@bot.tree.command(name="say", description="Lässt den Bot eine Nachricht schreiben (nur für Admin)")
@app_commands.describe(message="Die Nachricht, die der Bot schreiben soll")
async def say(interaction: discord.Interaction, message: str):
    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message("❌ Du bist nicht berechtigt, diesen Command zu nutzen.", ephemeral=True)
        return

    await interaction.channel.send(message)
    await interaction.response.send_message(f"✅ Nachricht gesendet: {message}", ephemeral=True)

   # ---------- /close command ----------
@bot.tree.command(name="close", description="Schließt ein Ticket nach 60 Minuten (nur Admins)")
async def close(interaction: discord.Interaction):
    # Nur Admins erlaubt
    if not interaction.user.guild_permissions.administrator and interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message(
            "❌ Du bist nicht berechtigt, diesen Command zu nutzen.",
            ephemeral=True
        )
        return

    channel = interaction.channel

    # Prüfen, ob der Channel ein Ticket-Channel ist
    if not channel.name.startswith("ticket-"):
        await interaction.response.send_message(
            "❌ Dieser Command kann nur in Ticket-Channels genutzt werden.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "⏳ Dieses Ticket wird in **60 Minuten** automatisch geschlossen.",
        ephemeral=True
    )
    await channel.send("🔒 Dieses Ticket wird in **60 Minuten** automatisch gelöscht. Bitte sichere vorher alle wichtigen Nachrichten.")

    try:
        # 60 Minuten warten
        await asyncio.sleep(60 * 60)

        # Channel löschen
        await channel.delete(reason="Ticket automatisch nach 60 Minuten geschlossen.")
    except discord.NotFound:
        print(f"⚠️ Channel {channel.name} wurde bereits gelöscht.")
    except discord.Forbidden:
        print(f"❌ Keine Berechtigung, um den Channel {channel.name} zu löschen.")
    except Exception as e:
        print(f"⚠️ Unerwarteter Fehler beim Löschen von {channel.name}: {e}")

# ---------- /penalty ----------
@bot.tree.command(name="penalty", description="Fügt einem User eine Strafe hinzu (nur Admin)")
@app_commands.describe(user_id="ID des Users", grund="Grund der Penalty")
async def penalty(interaction: discord.Interaction, user_id: str, grund: str):
    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message("❌ Du bist nicht berechtigt, diesen Command zu nutzen.", ephemeral=True)
        return

    # Loggen in penalty.txt
    with open(PENALTY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{user_id} | {grund}\n")

    # Zählen, wie viele Penalties der User hat
    try:
        with open(PENALTY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        count = sum(1 for line in lines if line.startswith(user_id))
    except FileNotFoundError:
        count = 1

    await interaction.response.send_message(f"✅ Penalty hinzugefügt. User hat jetzt {count} Penalties.", ephemeral=True)

    # Automatischer Bann nach 3 Penalties
    if count >= 3:
        guild = interaction.guild
        try:
            member = await guild.fetch_member(int(user_id))  # Holt den Member auch wenn er nicht gecached ist
            await member.ban(reason="Automatischer Bann nach 3 Penalties")
            await interaction.followup.send(f"⚠️ {member} wurde automatisch gebannt wegen 3 Penalties.")
        except discord.NotFound:
            await interaction.followup.send(f"❌ User mit ID {user_id} konnte nicht gefunden werden, kein Bann möglich.")
        except discord.Forbidden:
            await interaction.followup.send(f"❌ Ich habe keine Rechte, {user_id} zu bannen.")
        except Exception as e:
            await interaction.followup.send(f"❌ Fehler beim Bann: {e}")


# ---------- /myp (view your own penalties) ----------
@bot.tree.command(name="myp", description="Shows your own penalties")
async def myp(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    try:
        with open(PENALTY_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.startswith(user_id)]
    except FileNotFoundError:
        lines = []

    if not lines:
        await interaction.response.send_message("✅ You have no penalties.", ephemeral=True)
        return

    embed = discord.Embed(title="📄 Your Penalties", color=discord.Color.orange())
    for i, line in enumerate(lines, 1):
        parts = line.split(" | ")
        embed.add_field(name=f"Penalty #{i}", value=f"Reason: {parts[1]}", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)



# ---------- /lookp (Admin-Command, Penalties eines Users ansehen) ----------
@bot.tree.command(name="lookp", description="Zeigt die Penalties eines Users an (nur Admins)")
@app_commands.describe(user_id="ID des Users")
async def lookp(interaction: discord.Interaction, user_id: str):
    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message("❌ Du bist nicht berechtigt, diesen Command zu nutzen.", ephemeral=True)
        return

    try:
        with open(PENALTY_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.startswith(user_id)]
    except FileNotFoundError:
        lines = []

    if not lines:
        await interaction.response.send_message(f"✅ User {user_id} hat keine Penalties.", ephemeral=True)
        return

    embed = discord.Embed(title=f"📄 Penalties von User {user_id}", color=discord.Color.orange())
    for i, line in enumerate(lines, 1):
        parts = line.split(" | ")
        embed.add_field(name=f"Penalty #{i}", value=f"Grund: {parts[1]}", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------- /removep ----------
@bot.tree.command(name="removep", description="Entfernt eine Penalty von einem User (nur Admin)")
@app_commands.describe(user_id="ID des Users", count="Nummer der zu entfernenden Penalty (optional, Standard letzte)")
async def removep(interaction: discord.Interaction, user_id: str, count: int = None):
    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message("❌ Du bist nicht berechtigt, diesen Command zu nutzen.", ephemeral=True)
        return

    try:
        with open(PENALTY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        user_lines = [line for line in lines if line.startswith(user_id)]
        if not user_lines:
            await interaction.response.send_message("❌ Dieser User hat keine Penalties.", ephemeral=True)
            return

        # Standard: letzte Penalty entfernen
        if count is None:
            line_to_remove = user_lines[-1]
        else:
            if count < 1 or count > len(user_lines):
                await interaction.response.send_message("❌ Ungültige Penalty-Nummer.", ephemeral=True)
                return
            line_to_remove = user_lines[count - 1]

        lines.remove(line_to_remove)

        with open(PENALTY_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)

        await interaction.response.send_message(f"✅ Penalty entfernt: {line_to_remove.strip()}", ephemeral=True)
    except FileNotFoundError:
        await interaction.response.send_message("❌ Keine Penalties vorhanden.", ephemeral=True)

       
def add_report_stat(user_id: str):
    # Erhöht den Report-Zähler eines Users
    stats = {}

    # Vorhandene Stats laden (robust gegen fehlerhafte Zeilen)
    if os.path.exists(REPORT_STATS_FILE):
        with open(REPORT_STATS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    uid, cnt = line.split(" | ")
                    stats[uid] = int(cnt)
                except ValueError:
                    continue

    # Count hochzählen
    stats[user_id] = stats.get(user_id, 0) + 1

    # Datei überschreiben
    with open(REPORT_STATS_FILE, "w", encoding="utf-8") as f:
        for uid, cnt in stats.items():
            f.write(f"{uid} | {cnt}\n")


def get_report_stats():
    # Lädt alle Report-Statistiken zurück als dict
    stats = {}
    if os.path.exists(REPORT_STATS_FILE):
        with open(REPORT_STATS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    uid, cnt = line.split(" | ")
                    stats[uid] = int(cnt)
                except ValueError:
                    continue
    return stats


# ---------- /leaderboard ----------
@bot.tree.command(name="leaderboard", description="Shows the reporters leaderboard")
async def leaderboard(interaction: discord.Interaction):
    stats = get_report_stats()

    if not stats:
        await interaction.response.send_message("📊 No reports yet.", ephemeral=True)
        return

    # Sort by count (Top 10)
    sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)[:10]

    embed = discord.Embed(title="🏆 Report Leaderboard", color=discord.Color.gold())
    for i, (uid, cnt) in enumerate(sorted_stats, start=1):
        # Try to get the user's name
        name = f"User {uid}"
        try:
            member = interaction.guild.get_member(int(uid))
            if member:
                name = member.display_name
            else:
                try:
                    member = await interaction.guild.fetch_member(int(uid))
                    name = member.display_name
                except Exception:
                    name = f"User {uid}"
        except Exception:
            name = f"User {uid}"

        embed.add_field(name=f"{i}. {name}", value=f"📑 Reports: {cnt}", inline=False)

    await interaction.response.send_message(embed=embed)


def remove_report_stat(user_id: str):
    # Load existing stats
    stats = get_report_stats()

    if user_id not in stats:
        return False

    # Decrease count by 1
    stats[user_id] = max(0, stats[user_id] - 1)

    # Overwrite file
    with open(REPORT_STATS_FILE, "w", encoding="utf-8") as f:
        for uid, cnt in stats.items():
            f.write(f"{uid} | {cnt}\n")

    return True


@bot.tree.command(name="delreport", description="Deletes a report by message ID (admin only)")
@app_commands.describe(message_id="The ID of the report message")
async def delreport(interaction: discord.Interaction, message_id: str):
    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message("❌ You are not authorized to use this command.", ephemeral=True)
        return

    if not os.path.exists(LOG_FILE):
        await interaction.response.send_message("❌ No logs exist.", ephemeral=True)
        return

    deleted_line = None
    reporter_id = None
    channel_id = None

    # Search logs
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        if message_id in line:
            deleted_line = line.strip()
            # Cleanly extract reporter ID: first number in the line
            import re
            match = re.search(r"\d{17,}", line)  # Discord IDs have 17–19 digits
            if match:
                reporter_id = match.group()
            # Extract channel ID (if present)
            match_channel = re.search(r"Channel:\s*.*\((\d+)\)", line)
            if match_channel:
                channel_id = int(match_channel.group(1))
            continue
        new_lines.append(line)

    if not deleted_line:
        await interaction.response.send_message("❌ No report found with this message ID.", ephemeral=True)
        return

    # Save logs
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    # Delete message on Discord
    deleted_msg_info = ""
    if channel_id:
        try:
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                msg = await channel.fetch_message(int(message_id))
                await msg.delete()
                deleted_msg_info = "🗑️ Report message deleted on Discord.\n"
        except Exception:
            deleted_msg_info = "⚠️ Message could not be deleted on Discord.\n"

    # Adjust leaderboard
    leaderboard_info = ""
    if reporter_id:
        success = remove_report_stat(reporter_id)
        if success:
            leaderboard_info = f"📉 <@{reporter_id}> lost 1 point on the leaderboard."
        else:
            leaderboard_info = "⚠️ Reporter could not be adjusted on the leaderboard."
    else:
        leaderboard_info = "⚠️ Reporter ID could not be determined."

    # Send embed
    embed = discord.Embed(
        title="🗑️ Report Deleted",
        description=f"{deleted_msg_info}{leaderboard_info}",
        color=discord.Color.red()
    )
    await interaction.response.send_message(embed=embed)


class VerifyButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # No timeout, stays active

    @discord.ui.button(label="✅ Verify", style=discord.ButtonStyle.green, custom_id="verify_button")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(WHITELIST_ROLE_ID)
        if not role:
            await interaction.response.send_message("❌ Whitelist role not found!", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.response.send_message("✅ You are already verified!", ephemeral=True)
            return

        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("🎉 You have been successfully verified!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error while adding the role: {e}", ephemeral=True)



# ---------- Verify Setup Command ----------
@bot.tree.command(name="verifysetup", description="Sends the verify message with button (admins only)")
async def verifysetup(interaction: discord.Interaction):
    # Only administrators may use this command
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🔒 Verification Required",
        description="Click the button below to verify yourself and gain access to the server.",
        color=discord.Color.green()
    )

    await interaction.response.send_message("✅ Verify message sent!", ephemeral=True)
    await interaction.channel.send(embed=embed, view=VerifyButton())



    # --- Bot starten ---
if __name__ == "__main__":
    bot.run("Bot Token here")
