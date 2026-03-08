import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import os
import datetime
import time
import io
import uuid
from aiohttp import web
from dateutil.relativedelta import relativedelta

# ==========================================
# CONFIGURATION
# ==========================================
TOKEN = os.getenv("DISCORD_TOKEN")
DB_CHANNEL_ID = os.getenv("DB_CHANNEL_ID")
MAIN_COLOR = 0x7110FF

# ==========================================
# WEB SERVER FOR RENDER
# ==========================================
async def handle_web(request):
    return web.Response(text="Professional Slot System is Online and Operational.")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌐 Web server started on port {port}")

# ==========================================
# EMBED BUILDERS
# ==========================================
def pro_embed(title: str, description: str = None, color: int = MAIN_COLOR, user: discord.Member = None) -> discord.Embed:
    """Generates a strict, professional embed for all bot responses."""
    embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
    embed.set_footer(text="AD Slots | Professional Management System")
    if user:
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
    return embed

def error_embed(description: str) -> discord.Embed:
    """Standardized error embed."""
    return discord.Embed(title="❌ System Error", description=description, color=0xff0000)

# ==========================================
# UI CLASSES (MODALS & VIEWS)
# ==========================================
class CustomizeModal(discord.ui.Modal, title='Customize Your Slot'):
    channel_name = discord.ui.TextInput(
        label='New Channel Name',
        style=discord.TextStyle.short,
        placeholder='e.g., xen-shop',
        required=False,
        max_length=30
    )

    channel_topic = discord.ui.TextInput(
        label='Channel Description (Topic)',
        style=discord.TextStyle.paragraph,
        placeholder='Describe your services here...',
        required=False,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        new_name = self.channel_name.value.strip()
        new_topic = self.channel_topic.value.strip()
        updates = []
        
        try:
            if new_name:
                safe_name = f"slot-{new_name.replace(' ', '-')}"
                await channel.edit(name=safe_name)
                updates.append(f"**Name:** `{safe_name}`")
            if new_topic:
                await channel.edit(topic=new_topic)
                updates.append("**Topic:** Updated successfully")

            if not updates:
                return await interaction.followup.send(embed=error_embed("No changes were made. You left all fields blank."))

            await interaction.followup.send(embed=pro_embed("🎨 Slot Customized", "\n".join(updates)))
        except discord.Forbidden:
            await interaction.followup.send(embed=error_embed("The bot lacks permissions to edit this channel."))
        except discord.HTTPException as e:
            await interaction.followup.send(embed=error_embed(f"An error occurred: {e}"))

class TransferModal(discord.ui.Modal, title='Transfer Your Slot'):
    new_owner_id = discord.ui.TextInput(
        label='New Owner User ID',
        style=discord.TextStyle.short,
        placeholder='e.g., 123456789012345678',
        required=True,
        max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ch_id_str = str(interaction.channel.id)
        
        if ch_id_str not in interaction.client.db["slots"]:
            return await interaction.followup.send(embed=error_embed("This channel is not a registered slot."))
            
        slot = interaction.client.db["slots"][ch_id_str]
        
        # Verify ownership or admin
        if slot["owner_id"] != interaction.user.id and not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send(embed=error_embed("Only the slot owner or an administrator can transfer this slot."))
            
        try:
            new_user_id = int(self.new_owner_id.value.strip())
            new_member = await interaction.guild.fetch_member(new_user_id)
        except (ValueError, discord.NotFound):
            return await interaction.followup.send(embed=error_embed("Invalid User ID. Please make sure the user is in this server."))

        if new_member.bot:
            return await interaction.followup.send(embed=error_embed("You cannot transfer a slot to a bot."))

        # Transfer Permissions
        old_member = interaction.guild.get_member(slot["owner_id"])
        if old_member:
            await interaction.channel.set_permissions(old_member, overwrite=None) # Remove old owner permissions
            
        overwrites = discord.PermissionOverwrite(read_messages=True, send_messages=True, mention_everyone=True, manage_messages=True)
        await interaction.channel.set_permissions(new_member, overwrite=overwrites)
        
        # Update DB
        slot["owner_id"] = new_member.id
        await interaction.client.save_database(force=True)
        
        await interaction.followup.send(embed=pro_embed("✅ Transfer Successful", f"You have successfully transferred this slot to {new_member.mention}."))
        await interaction.channel.send(embed=pro_embed("🔄 Slot Transferred", f"This slot has been transferred to a new owner: {new_member.mention}."))

class TransferPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Persistent View

    @discord.ui.button(label="Transfer Slot", style=discord.ButtonStyle.primary, custom_id="transfer_slot_button", emoji="🔄")
    async def transfer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TransferModal())

# ==========================================
# BOT CLASS & DATABASE SYSTEM
# ==========================================
class MassiveSlotBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True 
        intents.members = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        
        self.db = {"slots": {}, "keys": {}, "blacklist": []}
        self.db_loaded = False

    async def setup_hook(self):
        self.add_view(TransferPanelView()) # Register the persistent view for the transfer panel
        await self.load_database()
        self.backup_task.start()
        self.check_expirations.start()
        self.reset_pings.start()
        self.loop.create_task(start_web_server())
        await self.tree.sync()
        print("✅ Slash commands globally synchronized.")

    async def load_database(self):
        if not DB_CHANNEL_ID: return
        channel = self.get_channel(int(DB_CHANNEL_ID))
        if not channel: return

        async for message in channel.history(limit=10):
            if message.attachments:
                try:
                    file_bytes = await message.attachments[0].read()
                    data = json.loads(file_bytes.decode('utf-8'))
                    self.db["slots"] = data.get("slots", {})
                    self.db["keys"] = data.get("keys", {})
                    self.db["blacklist"] = data.get("blacklist", [])
                    self.db_loaded = True
                    print("✅ Database loaded successfully.")
                    return
                except Exception:
                    continue
        self.db_loaded = True

    async def save_database(self, force=False):
        if not DB_CHANNEL_ID or not self.db_loaded: return
        channel = self.get_channel(int(DB_CHANNEL_ID))
        if not channel: return

        data_str = json.dumps(self.db, indent=4)
        file = discord.File(io.BytesIO(data_str.encode('utf-8')), filename="slots_database.json")
        try:
            await channel.purge(limit=5)
            await channel.send("💾 Auto-backup of slots data", file=file)
            if force: print("💾 Emergency save completed.")
        except Exception:
            pass

    @tasks.loop(minutes=30)
    async def backup_task(self):
        await self.save_database()

    @tasks.loop(hours=1)
    async def check_expirations(self):
        now = time.time()
        for ch_id, slot in list(self.db["slots"].items()):
            if slot.get("expire_at") and now > slot["expire_at"] and slot.get("status") == "active":
                channel = self.get_channel(int(ch_id))
                if channel:
                    owner = channel.guild.get_member(slot["owner_id"])
                    if owner: await channel.set_permissions(owner, send_messages=False, mention_everyone=False)
                    await channel.send(embed=error_embed(f"<@{slot['owner_id']}>, your slot rental has expired."))
                self.db["slots"][ch_id]["status"] = "expired"

    @tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=datetime.timezone.utc))
    async def reset_pings(self):
        for ch_id, slot in self.db["slots"].items():
            if slot.get("status") in ["active", "hold"]:
                slot["used_here"] = 0
                slot["used_everyone"] = 0
                if slot.get("status") == "active":
                    channel = self.get_channel(int(ch_id))
                    if channel: await channel.send(embed=pro_embed("🔄 Daily Reset", "Your daily mentions have been reset to zero."))

bot = MassiveSlotBot()

# ==========================================
# CLIENT COMMANDS
# ==========================================
@bot.tree.command(name="myslot", description="View your active slot information.")
async def myslot(interaction: discord.Interaction):
    user_id = interaction.user.id
    slot_info = next((s for s in bot.db["slots"].values() if s["owner_id"] == user_id and s["status"] != "deleted"), None)
    
    if not slot_info: return await interaction.response.send_message(embed=error_embed("You do not own an active slot."), ephemeral=True)

    embed = pro_embed("Slot Information")
    embed.add_field(name="Slot Owner", value=f"{interaction.user.mention}\n`{user_id}`", inline=False)
    
    start = slot_info.get("start_time", time.time())
    embed.add_field(name="Started on:", value=f"<t:{int(start)}:F>", inline=False)
    
    expire = slot_info.get("expire_at")
    embed.add_field(name="Expiring on:", value=f"<t:{int(expire)}:F>" if expire else "Lifetime", inline=False)
    
    rem_h = slot_info["limit_here"] - slot_info["used_here"]
    rem_e = slot_info["limit_everyone"] - slot_info["used_everyone"]
    embed.add_field(name="Pings", value=f"`{rem_h}x` @here\n`{rem_e}x` @everyone", inline=False)
    embed.add_field(name="Important", value="```\n- Follow and respect the slot terms\n- Use /myslot to check remaining pings\n```", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="customize", description="Customize your slot channel name and description.")
async def customize(interaction: discord.Interaction):
    ch_id_str = str(interaction.channel.id)
    if ch_id_str not in bot.db["slots"]: return await interaction.response.send_message(embed=error_embed("This command can only be used inside a valid slot channel."), ephemeral=True)
    slot = bot.db["slots"][ch_id_str]
    if slot["owner_id"] != interaction.user.id: return await interaction.response.send_message(embed=error_embed("Only the slot owner can customize this channel."), ephemeral=True)
    if slot["status"] != "active": return await interaction.response.send_message(embed=error_embed("Your slot must be active to customize it."), ephemeral=True)
    await interaction.response.send_modal(CustomizeModal())

@bot.tree.command(name="nuke", description="Delete and recreate your slot channel. (Slot owners only)")
async def nuke(interaction: discord.Interaction):
    ch_id_str = str(interaction.channel.id)
    slot = bot.db["slots"].get(ch_id_str)
    if not slot or slot["owner_id"] != interaction.user.id: return await interaction.response.send_message(embed=error_embed("You can only nuke a slot you own, inside the slot channel."), ephemeral=True)

    await interaction.response.send_message(embed=pro_embed("☢️ Nuking...", "Recreating channel..."), ephemeral=True)
    new_channel = await interaction.channel.clone(reason="User requested slot nuke.")
    await interaction.channel.delete()
    
    bot.db["slots"][str(new_channel.id)] = bot.db["slots"].pop(ch_id_str)
    await bot.save_database(force=True)
    await new_channel.send(content=interaction.user.mention, embed=pro_embed("☢️ Channel Nuked", "Your slot has been wiped and recreated."))

@bot.tree.command(name="redeem", description="Redeem a key to activate your slot.")
async def redeem(interaction: discord.Interaction, key: str):
    if key not in bot.db["keys"]: return await interaction.response.send_message(embed=error_embed("Invalid or expired redeem key."), ephemeral=True)
    
    duration = bot.db["keys"][key]["duration"]
    expire_timestamp = (datetime.datetime.now() + relativedelta(days=duration)).timestamp() if duration > 0 else None
    
    category = interaction.channel.category 
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, mention_everyone=True, manage_messages=True)
    }
    
    new_channel = await interaction.guild.create_text_channel(name=f"slot-{interaction.user.name}", category=category, overwrites=overwrites)
    
    bot.db["slots"][str(new_channel.id)] = {
        "owner_id": interaction.user.id,
        "expire_at": expire_timestamp,
        "start_time": time.time(),
        "limit_here": 1, "limit_everyone": 1, "used_here": 0, "used_everyone": 0,
        "status": "active"
    }
    del bot.db["keys"][key]
    await bot.save_database(force=True)
    
    await interaction.response.send_message(embed=pro_embed("✅ Key Redeemed", f"Slot created successfully: {new_channel.mention}"), ephemeral=True)
    await new_channel.send(content=interaction.user.mention, embed=pro_embed("🎉 Welcome", "Your slot is now active. Please wait for an admin to set your ping limits."))

# ==========================================
# ADMIN COMMANDS
# ==========================================
@bot.tree.command(name="rpanel", description="Post the slot transfer panel. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def rpanel(interaction: discord.Interaction):
    embed = pro_embed("🔄 Slot Transfer Management", "Click the button below to transfer the ownership of this slot to another user. You will need their Discord User ID.")
    await interaction.channel.send(embed=embed, view=TransferPanelView())
    await interaction.response.send_message("Panel posted.", ephemeral=True)

@bot.tree.command(name="transfer", description="Transfer a slot from one user to another. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def transfer(interaction: discord.Interaction, current_owner: discord.Member, new_owner: discord.Member):
    await interaction.response.defer(ephemeral=True)
    transferred = 0
    for ch_id, slot in bot.db["slots"].items():
        if slot["owner_id"] == current_owner.id:
            channel = bot.get_channel(int(ch_id))
            if channel:
                await channel.set_permissions(current_owner, overwrite=None)
                overwrites = discord.PermissionOverwrite(read_messages=True, send_messages=True, mention_everyone=True, manage_messages=True)
                await channel.set_permissions(new_owner, overwrite=overwrites)
                await channel.send(embed=pro_embed("🔄 Slot Transferred", f"Admin transferred this slot to {new_owner.mention}."))
            slot["owner_id"] = new_owner.id
            transferred += 1
            
    if transferred > 0:
        await bot.save_database(force=True)
        await interaction.followup.send(embed=pro_embed("✅ Transfer Complete", f"Successfully transferred {transferred} slot(s) to {new_owner.mention}."))
    else:
        await interaction.followup.send(embed=error_embed(f"{current_owner.mention} does not own any active slots."))

@bot.tree.command(name="create", description="Create a private slot channel for a user. (Admin only)")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(user="The owner of the slot", duration="Duration: 1w, 1m, or lifetime")
async def create_slot(interaction: discord.Interaction, user: discord.Member, duration: str):
    await interaction.response.defer(ephemeral=True)
    duration = duration.lower()
    expire_timestamp = None
    if duration == "1w": expire_timestamp = (datetime.datetime.now() + relativedelta(weeks=1)).timestamp()
    elif duration == "1m": expire_timestamp = (datetime.datetime.now() + relativedelta(months=1)).timestamp()
    elif duration != "lifetime": return await interaction.followup.send(embed=error_embed("Invalid duration. Use `1w`, `1m`, or `lifetime`."))

    category = interaction.channel.category
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True, mention_everyone=True, manage_messages=True)
    }
    new_channel = await interaction.guild.create_text_channel(name=f"slot-{user.name}", category=category, overwrites=overwrites)

    bot.db["slots"][str(new_channel.id)] = {
        "owner_id": user.id, "expire_at": expire_timestamp, "start_time": time.time(),
        "limit_here": 0, "limit_everyone": 0, "used_here": 0, "used_everyone": 0, "status": "active"
    }
    await bot.save_database(force=True)
    await interaction.followup.send(embed=pro_embed("✅ Slot Created", f"Slot successfully created: {new_channel.mention}"))
    await new_channel.send(content=user.mention, embed=pro_embed("🎉 Welcome", "Your slot has been configured. An admin will set your ping limits shortly."))

@bot.tree.command(name="create_key", description="Generate a redeem key for a slot plan. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def create_key(interaction: discord.Interaction, days: int):
    new_key = f"AD-{str(uuid.uuid4()).split('-')[0].upper()}"
    bot.db["keys"][new_key] = {"duration": days}
    await bot.save_database(force=True)
    await interaction.response.send_message(embed=pro_embed("🔑 Key Generated", f"**Key:** `{new_key}`\n**Duration:** {days} days"), ephemeral=True)

@bot.tree.command(name="keys", description="List all active redeem keys. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def list_keys(interaction: discord.Interaction):
    if not bot.db["keys"]: return await interaction.response.send_message(embed=error_embed("No active keys found."), ephemeral=True)
    desc = "\n".join([f"`{k}` - {v['duration']} Days" for k, v in bot.db["keys"].items()])
    await interaction.response.send_message(embed=pro_embed("Active Redeem Keys", desc), ephemeral=True)

@bot.tree.command(name="ausers", description="Show all active slot users. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def ausers(interaction: discord.Interaction):
    active = [f"<@{s['owner_id']}> in <#{ch_id}>" for ch_id, s in bot.db["slots"].items() if s["status"] == "active"]
    desc = "\n".join(active) if active else "No active slots found."
    await interaction.response.send_message(embed=pro_embed("Active Users", desc), ephemeral=True)

@bot.tree.command(name="revoke", description="Revoke a user's slot. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def revoke_slot(interaction: discord.Interaction, user: discord.Member, reason: str = "Unspecified violation"):
    for ch_id, slot in bot.db["slots"].items():
        if slot["owner_id"] == user.id and slot["status"] == "active":
            channel = bot.get_channel(int(ch_id))
            if channel: 
                await channel.set_permissions(user, send_messages=False, mention_everyone=False)
                await channel.send(embed=error_embed(f"Access revoked by an administrator.\n**Reason:** {reason}"))
            slot["status"] = "revoked"
            await bot.save_database(force=True)
            return await interaction.response.send_message(embed=pro_embed("🛑 Slot Revoked", f"Successfully revoked {user.mention}."), ephemeral=True)
    await interaction.response.send_message(embed=error_embed("No active slot found for this user."), ephemeral=True)

@bot.tree.command(name="unrevoke", description="Restore a revoked slot. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def unrevoke_slot(interaction: discord.Interaction, user: discord.Member):
    for ch_id, slot in bot.db["slots"].items():
        if slot["owner_id"] == user.id and slot["status"] == "revoked":
            channel = bot.get_channel(int(ch_id))
            if channel: 
                await channel.set_permissions(user, send_messages=True, mention_everyone=True, manage_messages=True)
                await channel.send(embed=pro_embed("✅ Access Restored", "An administrator has restored your slot access."))
            slot["status"] = "active"
            slot["used_here"] = 0; slot["used_everyone"] = 0
            await bot.save_database(force=True)
            return await interaction.response.send_message(embed=pro_embed("✅ Slot Restored", f"Successfully restored {user.mention}."), ephemeral=True)
    await interaction.response.send_message(embed=error_embed("No revoked slot found for this user."), ephemeral=True)

@bot.tree.command(name="hold", description="Put a slot on hold and disable access. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def hold_slot(interaction: discord.Interaction, user: discord.Member):
    for ch_id, slot in bot.db["slots"].items():
        if slot["owner_id"] == user.id and slot["status"] == "active":
            channel = bot.get_channel(int(ch_id))
            if channel: 
                await channel.set_permissions(user, send_messages=False)
                await channel.send(embed=pro_embed("⏸️ Slot on Hold", "Your slot has been temporarily frozen by an administrator."))
            slot["status"] = "hold"
            await bot.save_database(force=True)
            return await interaction.response.send_message(embed=pro_embed("⏸️ Slot on Hold", f"Placed {user.mention}'s slot on hold."), ephemeral=True)
    await interaction.response.send_message(embed=error_embed("No active slot found for this user."), ephemeral=True)

@bot.tree.command(name="setpings", description="Set custom ping limits for a slot. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def setpings(interaction: discord.Interaction, here_limit: int, everyone_limit: int):
    ch_id_str = str(interaction.channel.id)
    if ch_id_str not in bot.db["slots"]: return await interaction.response.send_message(embed=error_embed("This channel is not a registered slot."), ephemeral=True)
    bot.db["slots"][ch_id_str]["limit_here"] = here_limit
    bot.db["slots"][ch_id_str]["limit_everyone"] = everyone_limit
    await bot.save_database(force=True)
    await interaction.response.send_message(embed=pro_embed("⚙️ Pings Updated", f"Limits updated successfully:\n`@here`: {here_limit}\n`@everyone`: {everyone_limit}"), ephemeral=True)

@bot.tree.command(name="say", description="Send a formatted product listing message as the bot.")
@app_commands.default_permissions(administrator=True)
async def say(interaction: discord.Interaction, title: str, message: str):
    await interaction.channel.send(embed=pro_embed(title, message))
    await interaction.response.send_message(embed=pro_embed("✅ Message sent."), ephemeral=True)

# ==========================================
# AUTO-REVOKE MENTION MONITORING
# ==========================================
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot: return
    ch_id_str = str(message.channel.id)
    
    if ch_id_str in bot.db["slots"]:
        slot = bot.db["slots"][ch_id_str]
        if message.author.id == slot["owner_id"] and slot["status"] == "active":
            has_here = "@here" in message.content
            has_everyone = "@everyone" in message.content

            if has_here or has_everyone:
                revoked, reason = False, ""
                if has_everyone:
                    slot["used_everyone"] += 1
                    if slot["used_everyone"] > slot["limit_everyone"]: revoked, reason = True, "@everyone"
                if has_here and not revoked:
                    slot["used_here"] += 1
                    if slot["used_here"] > slot["limit_here"]: revoked, reason = True, "@here"

                if revoked:
                    slot["status"] = "revoked"
                    await message.channel.set_permissions(message.author, send_messages=False, mention_everyone=False)
                    await message.delete()
                    await message.channel.send(embed=error_embed(f"{message.author.mention}, you exceeded your ping limit (`{reason}`). Write access has been revoked until the daily reset."))
                    await bot.save_database(force=True)
                else:
                    rem_h = slot['limit_here'] - slot['used_here']
                    rem_e = slot['limit_everyone'] - slot['used_everyone']
                    await message.channel.send(embed=pro_embed("🔔 Ping Used", f"Remaining daily mentions:\n`{rem_h}x` @here\n`{rem_e}x` @everyone"), delete_after=10)

bot.run(TOKEN)
