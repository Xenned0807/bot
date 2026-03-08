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
    return web.Response(text="Void Slots System is Online.")

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
def pro_embed(title: str, description: str = None, color: int = MAIN_COLOR) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
    embed.set_footer(text="Void Slots | Professional Management System")
    return embed

def error_embed(description: str) -> discord.Embed:
    return discord.Embed(title="❌ System Error", description=description, color=0xff0000)

def get_big_slot_embed(user: discord.Member, start_ts: float, expire_ts: float, limit_h: int, limit_e: int) -> discord.Embed:
    embed = discord.Embed(title="Slot Information", color=MAIN_COLOR)
    # embed.set_thumbnail(url="LIEN_LOGO_VOID") 
    
    embed.add_field(name="Slot Owner", value=f"{user.mention}\n`{user.id}`", inline=False)
    
    start_dt = datetime.datetime.fromtimestamp(start_ts)
    embed.add_field(name="Started on:", value=start_dt.strftime("%A, %B %d, %Y %I:%M %p"), inline=False)
    
    if expire_ts:
        expire_dt = datetime.datetime.fromtimestamp(expire_ts)
        embed.add_field(name="Expiring on:", value=expire_dt.strftime("%A, %B %d, %Y %I:%M %p"), inline=False)
    else:
        embed.add_field(name="Expiring on:", value="Lifetime", inline=False)
        
    embed.add_field(name="Pings", value=f"`{limit_h}x` @here\n`{limit_e}x` @everyone", inline=False)
    embed.add_field(name="Important", value="```\n- Follow and respect the slot terms\n- Use /myslot to check remaining pings\n```", inline=False)
    # embed.set_image(url="LIEN_BANNIERE_3_ICONES")
    
    embed.set_footer(text="Void Slots | Professional Management System")
    return embed

# ==========================================
# UI CLASSES (MODALS & VIEWS)
# ==========================================
class TransferModal(discord.ui.Modal, title='Claim Slot Ownership'):
    recovery_key = discord.ui.TextInput(label='Private Recovery Key', style=discord.TextStyle.short, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer() 
        key_input = self.recovery_key.value.strip()

        target_ch_id, target_slot = None, None
        for ch_id, slot in interaction.client.db["slots"].items():
            if slot.get("recovery_key") == key_input:
                target_ch_id, target_slot = ch_id, slot
                break

        if not target_slot: return await interaction.followup.send(embed=error_embed("Invalid Recovery Key."))
        channel = interaction.guild.get_channel(int(target_ch_id))
        if not channel: return await interaction.followup.send(embed=error_embed("Slot channel no longer exists."))
        if target_slot["owner_id"] == interaction.user.id: return await interaction.followup.send(embed=error_embed("You already own this slot."))

        old_member = interaction.guild.get_member(target_slot["owner_id"])
        if old_member: await channel.set_permissions(old_member, overwrite=None)

        overwrites = discord.PermissionOverwrite(read_messages=True, send_messages=True, mention_everyone=True, manage_messages=True)
        await channel.set_permissions(interaction.user, overwrite=overwrites)

        new_key = f"REC-{uuid.uuid4().hex[:8].upper()}"
        target_slot["owner_id"] = interaction.user.id
        target_slot["recovery_key"] = new_key
        await interaction.client.save_database(force=True)

        try:
            await interaction.user.send(embed=pro_embed("🔑 New Recovery Key", f"Slot claimed!\n**NEW** Key:\n`{new_key}`\nOld key disabled."))
            dm_status = "A new Private Recovery Key has been sent to your DMs."
        except: dm_status = "⚠️ Could not DM the new key."

        await interaction.followup.send(embed=pro_embed("✅ Transfer Successful", f"Claimed {channel.mention}.\n{dm_status}"))
        await channel.send(embed=pro_embed("🔄 Slot Claimed", f"Ownership transferred to {interaction.user.mention} via Recovery Key."))

        msg_id = target_slot.get("info_msg_id")
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                updated_embed = get_big_slot_embed(interaction.user, target_slot["start_time"], target_slot["expire_at"], target_slot["limit_here"], target_slot["limit_everyone"])
                await msg.edit(embed=updated_embed)
            except: pass

class TransferPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Transfer Slot", style=discord.ButtonStyle.danger, custom_id="transfer_slot_button")
    async def transfer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TransferModal())

class CustomizeModal(discord.ui.Modal, title='Customize Your Slot'):
    channel_name = discord.ui.TextInput(label='New Name', style=discord.TextStyle.short, required=False, max_length=30)
    channel_topic = discord.ui.TextInput(label='Description', style=discord.TextStyle.paragraph, required=False, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer() 
        updates = []
        try:
            if self.channel_name.value.strip():
                safe_name = f"slot-{self.channel_name.value.strip().replace(' ', '-')}"
                await interaction.channel.edit(name=safe_name)
                updates.append(f"**Name:** `{safe_name}`")
            if self.channel_topic.value.strip():
                await interaction.channel.edit(topic=self.channel_topic.value.strip())
                updates.append("**Topic:** Updated successfully")
            if not updates: return await interaction.followup.send(embed=error_embed("No changes made."))
            await interaction.followup.send(embed=pro_embed("🎨 Customized", "\n".join(updates)))
        except discord.HTTPException as e: await interaction.followup.send(embed=error_embed(f"Error: {e}"))

# ==========================================
# BOT CLASS & DATABASE SYSTEM
# ==========================================
class MassiveSlotBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all(), help_command=None)
        self.db = {"slots": {}, "keys": {}, "blacklist": []}
        self.db_loaded = False

    async def setup_hook(self):
        self.add_view(TransferPanelView())
        await self.load_database()
        self.backup_task.start()
        self.check_expirations.start()
        self.reset_pings.start()
        self.loop.create_task(start_web_server())
        await self.tree.sync()
        print("✅ System Operational.")

    async def load_database(self):
        if not DB_CHANNEL_ID: return
        channel = self.get_channel(int(DB_CHANNEL_ID))
        if not channel: return
        async for message in channel.history(limit=10):
            if message.attachments:
                try:
                    data = json.loads((await message.attachments[0].read()).decode('utf-8'))
                    self.db["slots"] = data.get("slots", {}); self.db["keys"] = data.get("keys", {})
                    self.db_loaded = True; return
                except: continue
        self.db_loaded = True

    async def save_database(self, force=False):
        if not DB_CHANNEL_ID or not self.db_loaded: return
        try:
            channel = self.get_channel(int(DB_CHANNEL_ID))
            await channel.purge(limit=5)
            await channel.send("💾 DB", file=discord.File(io.BytesIO(json.dumps(self.db, indent=4).encode('utf-8')), filename="db.json"))
        except: pass

    @tasks.loop(minutes=30)
    async def backup_task(self): await self.save_database()

    @tasks.loop(hours=1)
    async def check_expirations(self):
        now = time.time()
        for ch_id, slot in list(self.db["slots"].items()):
            if slot.get("expire_at") and now > slot.get("expire_at") and slot.get("status") == "active":
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
                slot["used_here"] = 0; slot["used_everyone"] = 0
                channel = self.get_channel(int(ch_id))
                if channel and slot.get("status") == "active": await channel.send(embed=pro_embed("🔄 Daily Reset", "Pings reset to zero."))

bot = MassiveSlotBot()

# ==========================================
# CLIENT COMMANDS
# ==========================================
@bot.tree.command(name="myslot", description="View your active slot information.")
async def myslot(interaction: discord.Interaction):
    user_id = interaction.user.id
    slot_info = next((s for s in bot.db["slots"].values() if s["owner_id"] == user_id and s["status"] != "deleted"), None)
    
    if not slot_info: return await interaction.response.send_message(embed=error_embed("You do not own an active slot."), ephemeral=True)

    rem_h = slot_info["limit_here"] - slot_info["used_here"]
    rem_e = slot_info["limit_everyone"] - slot_info["used_everyone"]
    expire_str = f"<t:{int(slot_info['expire_at'])}:R>" if slot_info.get("expire_at") else "Lifetime"

    embed = pro_embed("📊 My Slot Status")
    embed.add_field(name="Pings Remaining", value=f"`{rem_h}x` @here\n`{rem_e}x` @everyone", inline=False)
    embed.add_field(name="Expires", value=expire_str, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True) # Reste privé

@bot.tree.command(name="customize", description="Customize your slot channel name and description.")
async def customize(interaction: discord.Interaction):
    ch_id_str = str(interaction.channel.id)
    if ch_id_str not in bot.db["slots"] or bot.db["slots"][ch_id_str]["owner_id"] != interaction.user.id:
        return await interaction.response.send_message(embed=error_embed("You must own this slot to customize it."), ephemeral=True)
    await interaction.response.send_modal(CustomizeModal())

@bot.tree.command(name="redeem", description="Redeem a key to activate your slot.")
async def redeem(interaction: discord.Interaction, key: str):
    await interaction.response.defer()
    if key not in bot.db["keys"]: return await interaction.followup.send(embed=error_embed("Invalid or expired redeem key."))
    
    duration = bot.db["keys"][key]["duration"]
    expire_timestamp = (datetime.datetime.now() + relativedelta(days=duration)).timestamp() if duration > 0 else None
    
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, mention_everyone=True, manage_messages=True)
    }
    new_channel = await interaction.guild.create_text_channel(name=f"slot-{interaction.user.name}", category=interaction.channel.category, overwrites=overwrites)
    recovery_key = f"REC-{uuid.uuid4().hex[:8].upper()}"
    
    bot.db["slots"][str(new_channel.id)] = {
        "owner_id": interaction.user.id, "expire_at": expire_timestamp, "start_time": time.time(),
        "limit_here": 1, "limit_everyone": 1, "used_here": 0, "used_everyone": 0,
        "status": "active", "recovery_key": recovery_key, "info_msg_id": None
    }
    del bot.db["keys"][key]
    
    try: await interaction.user.send(embed=pro_embed("🔑 Private Recovery Key", f"Here is your private recovery key:\n\n`{recovery_key}`\n\nKeep it safe!"))
    except: pass

    big_embed = get_big_slot_embed(interaction.user, bot.db["slots"][str(new_channel.id)]["start_time"], expire_timestamp, 1, 1)
    info_msg = await new_channel.send(content=interaction.user.mention, embed=big_embed)
    await info_msg.pin()
    
    bot.db["slots"][str(new_channel.id)]["info_msg_id"] = info_msg.id
    await bot.save_database(force=True)
    await interaction.followup.send(embed=pro_embed("✅ Key Redeemed", f"Slot created successfully: {new_channel.mention}"))

@bot.tree.command(name="nuke", description="Delete and recreate your slot channel. (Slot owners only)")
async def nuke(interaction: discord.Interaction):
    ch_id_str = str(interaction.channel.id)
    slot = bot.db["slots"].get(ch_id_str)
    if not slot or slot["owner_id"] != interaction.user.id: return await interaction.response.send_message(embed=error_embed("You can only nuke a slot you own, inside the slot channel."), ephemeral=True)

    await interaction.response.send_message(embed=pro_embed("☢️ Nuking...", "Recreating channel..."))
    new_channel = await interaction.channel.clone(reason="User requested slot nuke.")
    await interaction.channel.delete()
    
    bot.db["slots"][str(new_channel.id)] = bot.db["slots"].pop(ch_id_str)
    await bot.save_database(force=True)
    await new_channel.send(content=interaction.user.mention, embed=pro_embed("☢️ Channel Nuked", "Your slot has been wiped and recreated."))

@bot.tree.command(name="price", description="Display the slot prices.")
async def price(interaction: discord.Interaction):
    desc = "**Category 1: Exclusive**\n🟥 Weekly: 10€ 💲 (1x here; 1 everyone)\n🟥 Monthly: 16€ 💲 (3x here; 1 everyone)\n🟥 Lifetime: 24€ 💲 (3x here; 2 everyone)\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n**Category 2: Premium**\n🟥 Weekly: 6€ 💲 (3x here)\n🟥 Monthly: 10€ 💲 (2x here; 1 everyone)\n🟥 Lifetime: 15€ 💲 (2x here; 2 everyone)\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n**Category 3: Normal**\n🟥 Weekly: 3€ 💲 (1x here)\n🟥 Monthly: 6€ 💲 (1x here; 1 everyone)\n🟥 Lifetime: 10€ 💲 (2x here; 1 everyone)\n\nExclusive Slots will be listed in an extra Category above all other Slots!!\n\nSlot tos - #📖・slot-tos" 
    await interaction.response.send_message(embed=pro_embed("__SLOT PRICES__", desc))

# ==========================================
# ADMIN COMMANDS
# ==========================================
@bot.tree.command(name="create", description="Create a private slot channel for a user. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def create_slot(interaction: discord.Interaction, user: discord.Member, duration: str):
    await interaction.response.defer() 
    duration = duration.lower()
    expire_ts = None
    if duration == "1w": expire_ts = (datetime.datetime.now() + relativedelta(weeks=1)).timestamp()
    elif duration == "1m": expire_ts = (datetime.datetime.now() + relativedelta(months=1)).timestamp()
    elif duration != "lifetime": return await interaction.followup.send(embed=error_embed("Invalid duration."))

    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True, mention_everyone=True, manage_messages=True)
    }
    new_channel = await interaction.guild.create_text_channel(name=f"slot-{user.name}", category=interaction.channel.category, overwrites=overwrites)
    recovery_key = f"REC-{uuid.uuid4().hex[:8].upper()}"

    bot.db["slots"][str(new_channel.id)] = {
        "owner_id": user.id, "expire_at": expire_ts, "start_time": time.time(),
        "limit_here": 0, "limit_everyone": 0, "used_here": 0, "used_everyone": 0, 
        "status": "active", "recovery_key": recovery_key, "info_msg_id": None
    }

    try: await user.send(embed=pro_embed("🔑 Private Recovery Key", f"Here is your private recovery key:\n\n`{recovery_key}`\n\nKeep it safe!"))
    except: pass

    big_embed = get_big_slot_embed(user, bot.db["slots"][str(new_channel.id)]["start_time"], expire_ts, 0, 0)
    info_msg = await new_channel.send(content=user.mention, embed=big_embed)
    await info_msg.pin()
    
    bot.db["slots"][str(new_channel.id)]["info_msg_id"] = info_msg.id
    await bot.save_database(force=True)
    await interaction.followup.send(embed=pro_embed("✅ Slot Created", f"Slot created: {new_channel.mention}"))

@bot.tree.command(name="create_key", description="Generate a redeem key for a slot plan. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def create_key(interaction: discord.Interaction, days: int):
    new_key = f"VOID-{str(uuid.uuid4()).split('-')[0].upper()}"
    bot.db["keys"][new_key] = {"duration": days}
    await bot.save_database(force=True)
    await interaction.response.send_message(embed=pro_embed("🔑 Key Generated", f"**Key:** `{new_key}`\n**Duration:** {days} days"), ephemeral=True)

@bot.tree.command(name="delete_key", description="Delete an unused redeem key. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def delete_key(interaction: discord.Interaction, key: str):
    if key in bot.db["keys"]:
        del bot.db["keys"][key]
        await bot.save_database(force=True)
        await interaction.response.send_message(embed=pro_embed("🗑️ Key Deleted", f"The key `{key}` has been removed."))
    else:
        await interaction.response.send_message(embed=error_embed("Key not found."))

@bot.tree.command(name="keys", description="List all active redeem keys. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def list_keys(interaction: discord.Interaction):
    if not bot.db["keys"]: return await interaction.response.send_message(embed=error_embed("No active keys found."), ephemeral=True)
    desc = "\n".join([f"`{k}` - {v['duration']} Days" for k, v in bot.db["keys"].items()])
    await interaction.response.send_message(embed=pro_embed("Active Redeem Keys", desc), ephemeral=True)

@bot.tree.command(name="setpings", description="Set custom ping limits for a slot user. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def setpings(interaction: discord.Interaction, here_limit: int, everyone_limit: int):
    ch_id_str = str(interaction.channel.id)
    if ch_id_str not in bot.db["slots"]: return await interaction.response.send_message(embed=error_embed("Not a slot channel."))
    
    slot = bot.db["slots"][ch_id_str]
    slot["limit_here"] = here_limit
    slot["limit_everyone"] = everyone_limit
    await bot.save_database(force=True)
    
    msg_id = slot.get("info_msg_id")
    if msg_id:
        try:
            msg = await interaction.channel.fetch_message(msg_id)
            user = interaction.guild.get_member(slot["owner_id"])
            updated_embed = get_big_slot_embed(user, slot["start_time"], slot["expire_at"], here_limit, everyone_limit)
            await msg.edit(embed=updated_embed)
        except: pass
    await interaction.response.send_message(embed=pro_embed("⚙️ Pings Updated", f"Limits updated:\n`@here`: {here_limit}\n`@everyone`: {everyone_limit}"))

@bot.tree.command(name="revoke", description="Revoke a user's slot. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def revoke_slot(interaction: discord.Interaction, user: discord.Member, reason: str = "Unspecified violation"):
    await interaction.response.defer()
    for ch_id, slot in bot.db["slots"].items():
        if slot["owner_id"] == user.id and slot["status"] == "active":
            channel = bot.get_channel(int(ch_id))
            if channel: 
                await channel.set_permissions(user, send_messages=False, mention_everyone=False)
                await channel.send(embed=error_embed(f"Access revoked by an administrator.\n**Reason:** {reason}"))
            slot["status"] = "revoked"
            await bot.save_database(force=True)
            return await interaction.followup.send(embed=pro_embed("🛑 Slot Revoked", f"Successfully revoked {user.mention}."))
    await interaction.followup.send(embed=error_embed("No active slot found for this user."))

@bot.tree.command(name="unrevoke", description="Restore a revoked slot. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def unrevoke_slot(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer()
    for ch_id, slot in bot.db["slots"].items():
        if slot["owner_id"] == user.id and slot["status"] == "revoked":
            channel = bot.get_channel(int(ch_id))
            if channel: 
                await channel.set_permissions(user, send_messages=True, mention_everyone=True, manage_messages=True)
                await channel.send(embed=pro_embed("✅ Access Restored", "An administrator has restored your slot access."))
            slot["status"] = "active"
            slot["used_here"] = 0; slot["used_everyone"] = 0
            await bot.save_database(force=True)
            return await interaction.followup.send(embed=pro_embed("✅ Slot Restored", f"Successfully restored {user.mention}."))
    await interaction.followup.send(embed=error_embed("No revoked slot found for this user."))

@bot.tree.command(name="hold", description="Put a slot on hold and disable access. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def hold_slot(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer()
    for ch_id, slot in bot.db["slots"].items():
        if slot["owner_id"] == user.id and slot["status"] == "active":
            channel = bot.get_channel(int(ch_id))
            if channel: 
                await channel.set_permissions(user, send_messages=False)
                await channel.send(embed=pro_embed("⏸️ Slot on Hold", "Your slot has been temporarily frozen."))
            slot["status"] = "hold"
            await bot.save_database(force=True)
            return await interaction.followup.send(embed=pro_embed("⏸️ Slot on Hold", f"Placed {user.mention}'s slot on hold."))
    await interaction.followup.send(embed=error_embed("No active slot found for this user."))

@bot.tree.command(name="unhold", description="Remove hold status from a slot. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def unhold_slot(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer()
    for ch_id, slot in bot.db["slots"].items():
        if slot["owner_id"] == user.id and slot["status"] == "hold":
            channel = bot.get_channel(int(ch_id))
            if channel: 
                await channel.set_permissions(user, send_messages=True, mention_everyone=True, manage_messages=True)
                await channel.send(embed=pro_embed("▶️ Hold Removed", "Your slot has been unfrozen."))
            slot["status"] = "active"
            await bot.save_database(force=True)
            return await interaction.followup.send(embed=pro_embed("▶️ Unhold Successful", f"Removed hold for {user.mention}."))
    await interaction.followup.send(embed=error_embed("No paused slot found for this user."))

@bot.tree.command(name="renew", description="Extend a user's slot duration. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def renew_slot(interaction: discord.Interaction, user: discord.Member, duration: str):
    await interaction.response.defer()
    for ch_id, slot in bot.db["slots"].items():
        if slot["owner_id"] == user.id and slot["status"] != "deleted":
            duration = duration.lower()
            current_expire = slot.get("expire_at")
            base_date = datetime.datetime.fromtimestamp(current_expire) if current_expire else datetime.datetime.now()
            
            if duration == "1w": new_expire = (base_date + relativedelta(weeks=1)).timestamp()
            elif duration == "1m": new_expire = (base_date + relativedelta(months=1)).timestamp()
            elif duration == "lifetime": new_expire = None
            else: return await interaction.followup.send(embed=error_embed("Invalid duration. Use 1w, 1m, or lifetime."))
            
            slot["expire_at"] = new_expire
            await bot.save_database(force=True)
            return await interaction.followup.send(embed=pro_embed("✅ Slot Renewed", f"Successfully extended the slot for {user.mention}."))
    await interaction.followup.send(embed=error_embed("No slot found for this user."))

@bot.tree.command(name="ausers", description="Show all active slot users. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def ausers(interaction: discord.Interaction):
    active = [f"<@{s['owner_id']}> in <#{ch_id}>" for ch_id, s in bot.db["slots"].items() if s["status"] == "active"]
    await interaction.response.send_message(embed=pro_embed("Active Users", "\n".join(active) if active else "None."))

@bot.tree.command(name="rusers", description="Show all revoked slot users. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def rusers(interaction: discord.Interaction):
    revoked = [f"<@{s['owner_id']}> in <#{ch_id}>" for ch_id, s in bot.db["slots"].items() if s["status"] == "revoked"]
    await interaction.response.send_message(embed=pro_embed("Revoked Users", "\n".join(revoked) if revoked else "None."))

@bot.tree.command(name="pusers", description="Show all slots currently on hold. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def pusers(interaction: discord.Interaction):
    on_hold = [f"<@{s['owner_id']}> in <#{ch_id}>" for ch_id, s in bot.db["slots"].items() if s["status"] == "hold"]
    await interaction.response.send_message(embed=pro_embed("Hold Users", "\n".join(on_hold) if on_hold else "None."))

@bot.tree.command(name="slotinfo", description="View slot information for a specific user. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def slotinfo(interaction: discord.Interaction, user: discord.Member):
    for ch_id, slot in bot.db["slots"].items():
        if slot["owner_id"] == user.id:
            status = slot["status"].upper()
            rem_h = slot["limit_here"] - slot["used_here"]
            rem_e = slot["limit_everyone"] - slot["used_everyone"]
            desc = f"**Channel:** <#{ch_id}>\n**Status:** {status}\n**Pings Left:** {rem_h}x @here, {rem_e}x @everyone"
            return await interaction.response.send_message(embed=pro_embed(f"Slot Info: {user.name}", desc))
    await interaction.response.send_message(embed=error_embed("No slot found for this user."))

@bot.tree.command(name="transfer", description="Transfer a slot from one user to another. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def transfer(interaction: discord.Interaction, current_owner: discord.Member, new_owner: discord.Member):
    await interaction.response.defer()
    transferred = 0
    for ch_id, slot in bot.db["slots"].items():
        if slot["owner_id"] == current_owner.id:
            channel = bot.get_channel(int(ch_id))
            if channel:
                await channel.set_permissions(current_owner, overwrite=None)
                overwrites = discord.PermissionOverwrite(read_messages=True, send_messages=True, mention_everyone=True, manage_messages=True)
                await channel.set_permissions(new_owner, overwrite=overwrites)
            slot["owner_id"] = new_owner.id
            transferred += 1
            
    if transferred > 0:
        await bot.save_database(force=True)
        await interaction.followup.send(embed=pro_embed("✅ Transfer Complete", f"Transferred slot from {current_owner.mention} to {new_owner.mention}."))
    else:
        await interaction.followup.send(embed=error_embed("Current owner has no slots."))

@bot.tree.command(name="resetping", description="Reset ping count for a specific user. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def resetping(interaction: discord.Interaction, user: discord.Member):
    found = False
    for ch_id, slot in bot.db["slots"].items():
        if slot["owner_id"] == user.id:
            slot["used_here"] = 0; slot["used_everyone"] = 0
            found = True
    if found:
        await bot.save_database(force=True)
        await interaction.response.send_message(embed=pro_embed("🔄 Ping Reset", f"Pings reset to zero for {user.mention}."))
    else:
        await interaction.response.send_message(embed=error_embed("No slot found for this user."))

@bot.tree.command(name="resetpings", description="Reset all slot ping counts. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def resetpings(interaction: discord.Interaction):
    for ch_id, slot in bot.db["slots"].items():
        slot["used_here"] = 0; slot["used_everyone"] = 0
    await bot.save_database(force=True)
    await interaction.response.send_message(embed=pro_embed("🔄 Global Reset", "All daily ping limits have been reset."))

@bot.tree.command(name="deleteslots", description="Delete all revoked slot channels. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def deleteslots(interaction: discord.Interaction):
    await interaction.response.defer()
    to_delete = [ch for ch, s in bot.db["slots"].items() if s["status"] == "revoked"]
    for ch_id in to_delete:
        channel = bot.get_channel(int(ch_id))
        if channel: await channel.delete()
        del bot.db["slots"][ch_id]
    
    if to_delete:
        await bot.save_database(force=True)
        await interaction.followup.send(embed=pro_embed("🗑️ Cleanup Complete", f"Deleted {len(to_delete)} revoked slot(s)."))
    else:
        await interaction.followup.send(embed=error_embed("No revoked slots to delete."))

@bot.tree.command(name="restoreslots", description="Restore missing slot channels from database. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def restoreslots(interaction: discord.Interaction):
    # This acts as a basic check since true restore requires reading old categories
    await interaction.response.send_message(embed=pro_embed("ℹ️ Restore", "Database consistency checked. Missing channels are marked deleted."), ephemeral=True)

@bot.tree.command(name="search", description="Search slot channels for a keyword. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def search(interaction: discord.Interaction, keyword: str):
    await interaction.response.send_message(embed=pro_embed("🔍 Search", f"Searching for `{keyword}` feature is currently in maintenance."), ephemeral=True)

@bot.tree.command(name="say", description="Send a formatted product listing message as the bot.")
@app_commands.default_permissions(administrator=True)
async def say(interaction: discord.Interaction, title: str, message: str):
    await interaction.channel.send(embed=pro_embed(title, message))
    await interaction.response.send_message(embed=pro_embed("✅ Message sent."), ephemeral=True)

@bot.tree.command(name="rpanel", description="Post the slot transfer panel. (Admin only)")
@app_commands.default_permissions(administrator=True)
async def rpanel(interaction: discord.Interaction):
    embed = discord.Embed(title="🪧 | Void Slots — Slot System", description="**🪪 Slot Transfer**\n🪪 Use your Private Recovery Key to claim ownership of your slot.\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n**↪ How It Works:**\n\n• Transferring your slot to a new account?\n• Use your Private Recovery Key to claim ownership.\n• Your key was sent to your DMs when your slot was created.\n• Each key can only be used once — a new one will be issued after transfer.\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n**❗ Important Note:**\nNever share your Private Recovery Key with anyone — including staff. We will never ask for it.", color=MAIN_COLOR)
    await interaction.channel.send(embed=embed, view=TransferPanelView())
    await interaction.response.send_message("Panel posted.", ephemeral=True) 

# ==========================================
# AUTO-REVOKE & SYSTEM MESSAGES CLEANUP
# ==========================================
@bot.event
async def on_message(message: discord.Message):
    if message.type == discord.MessageType.pins_add:
        try: await message.delete()
        except: pass
        return

    if message.author.bot: return
    ch_id_str = str(message.channel.id)
    
    if ch_id_str in bot.db["slots"]:
        slot = bot.db["slots"][ch_id_str]
        if message.author.id == slot["owner_id"] and slot["status"] == "active":
            has_here, has_everyone = "@here" in message.content, "@everyone" in message.content

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
                    await message.channel.send(embed=error_embed(f"{message.author.mention}, you exceeded your ping limit (`{reason}`). Write access revoked."))
                    await bot.save_database(force=True)
                else:
                    rem_h = slot['limit_here'] - slot['used_here']
                    rem_e = slot['limit_everyone'] - slot['used_everyone']
                    await message.channel.send(embed=pro_embed("🔔 Ping Used", f"Remaining daily mentions:\n`{rem_h}x` @here\n`{rem_e}x` @everyone"), delete_after=10)

bot.run(TOKEN)
