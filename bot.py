import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import datetime
import asyncio
from aiohttp import web # NOUVELLE LIGNE : Pour le serveur web de Render
from dateutil.relativedelta import relativedelta 

# --- CONFIGURATION ---
# On récupère le token depuis les variables d'environnement de Render
TOKEN = os.getenv("DISCORD_TOKEN")
DATA_FILE = "slots_data.json"

# Defining the limits for each plan
PLANS = {
    "1w": {"name": "1 Week", "here": 1, "everyone": 0, "duration": {"weeks": 1}},
    "1m": {"name": "1 Month", "here": 1, "everyone": 1, "duration": {"months": 1}},
    "lifetime": {"name": "Lifetime", "here": 1, "everyone": 2, "duration": None}
}

# --- DATA MANAGEMENT ---
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# --- WEB SERVER FOR RENDER ---
# Ce mini-serveur permet à Render de voir que le bot est en vie
async def handle_web(request):
    return web.Response(text="Bot is running smoothly!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render attribue automatiquement un port via la variable PORT
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

# --- BOT CLASS ---
class SlotBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True 
        super().__init__(command_prefix="!", intents=intents)
        self.slots_data = load_data()

    async def setup_hook(self):
        await self.tree.sync()
        self.check_expirations.start()
        # On lance le faux serveur web en même temps que le bot
        self.loop.create_task(start_web_server())
        print("Bot is ready and commands are synced!")

    @tasks.loop(hours=1)
    async def check_expirations(self):
        now = datetime.datetime.now().timestamp()
        to_delete = []

        for channel_id_str, slot in self.slots_data.items():
            if slot["expire_at"] and now > slot["expire_at"]:
                channel = self.get_channel(int(channel_id_str))
                if channel:
                    embed = discord.Embed(
                        title="⏳ Slot Expired",
                        description=f"<@{slot['owner_id']}>, your channel rental has ended.",
                        color=discord.Color.red()
                    )
                    owner = channel.guild.get_member(slot["owner_id"])
                    if owner:
                        await channel.set_permissions(owner, send_messages=False, mention_everyone=False)
                    await channel.send(embed=embed)
                to_delete.append(channel_id_str)
        
        for ch_id in to_delete:
            del self.slots_data[ch_id]
        if to_delete:
            save_data(self.slots_data)

bot = SlotBot()

# --- SLASH COMMANDS ---

@bot.tree.command(name="screate", description="Create a personal slot channel for a client")
@app_commands.describe(plan="The rental duration", client="The member who purchased")
@app_commands.choices(plan=[
    app_commands.Choice(name="1 Week", value="1w"),
    app_commands.Choice(name="1 Month", value="1m"),
    app_commands.Choice(name="Lifetime", value="lifetime")
])
@app_commands.default_permissions(manage_channels=True)
async def screate(interaction: discord.Interaction, plan: app_commands.Choice[str], client: discord.Member):
    guild = interaction.guild
    plan_data = PLANS[plan.value]

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        client: discord.PermissionOverwrite(read_messages=True, send_messages=True, mention_everyone=True, manage_messages=True)
    }

    category = interaction.channel.category 
    channel_name = f"slot-{client.name}"
    
    new_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)

    expire_timestamp = None
    if plan_data["duration"]:
        expire_date = datetime.datetime.now() + relativedelta(**plan_data["duration"])
        expire_timestamp = expire_date.timestamp()

    bot.slots_data[str(new_channel.id)] = {
        "owner_id": client.id,
        "plan": plan.value,
        "expire_at": expire_timestamp,
        "used_here": 0,
        "used_everyone": 0,
        "limit_here": plan_data["here"],
        "limit_everyone": plan_data["everyone"]
    }
    save_data(bot.slots_data)

    embed = discord.Embed(
        title="🎉 Creation of your Personal Slot",
        description=f"Welcome to your channel <@{client.id}>!\nYou can promote your services here.",
        color=discord.Color.green()
    )
    embed.add_field(name="Plan", value=plan_data['name'], inline=True)
    if expire_timestamp:
        embed.add_field(name="Expires on", value=f"<t:{int(expire_timestamp)}:d>", inline=True)
    else:
        embed.add_field(name="Expires on", value="Never (Lifetime)", inline=True)
        
    embed.add_field(name="Allowed Mentions", value=f"`@here` : {plan_data['here']}\n`@everyone` : {plan_data['everyone']}", inline=False)
    embed.set_footer(text="Use /pings to see your remaining mentions.")

    await new_channel.send(content=client.mention, embed=embed)
    await interaction.response.send_message(f"✅ The slot has been created: {new_channel.mention}", ephemeral=True)


@bot.tree.command(name="pings", description="Check the number of remaining mentions for this slot")
async def pings(interaction: discord.Interaction):
    channel_id_str = str(interaction.channel.id)
    
    if channel_id_str not in bot.slots_data:
        await interaction.response.send_message("❌ This channel is not a registered slot.", ephemeral=True)
        return

    slot = bot.slots_data[channel_id_str]
    
    if slot["owner_id"] != interaction.user.id and not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("❌ You are not the owner of this slot.", ephemeral=True)
        return

    rem_here = slot["limit_here"] - slot["used_here"]
    rem_every = slot["limit_everyone"] - slot["used_everyone"]

    embed = discord.Embed(
        title="📊 Your Remaining Mentions",
        color=discord.Color.blue()
    )
    embed.add_field(name="`@here` Mentions", value=f"{rem_here} remaining", inline=True)
    embed.add_field(name="`@everyone` Mentions", value=f"{rem_every} remaining", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    channel_id_str = str(message.channel.id)
    
    if channel_id_str in bot.slots_data:
        slot = bot.slots_data[channel_id_str]
        
        if message.author.id == slot["owner_id"]:
            has_here = "@here" in message.content
            has_everyone = "@everyone" in message.content

            if has_here or has_everyone:
                revoked = False
                reason = ""

                if has_everyone:
                    slot["used_everyone"] += 1
                    if slot["used_everyone"] > slot["limit_everyone"]:
                        revoked = True
                        reason = "@everyone"
                
                if has_here and not revoked:
                    slot["used_here"] += 1
                    if slot["used_here"] > slot["limit_here"]:
                        revoked = True
                        reason = "@here"

                if revoked:
                    await message.channel.set_permissions(message.author, send_messages=False, mention_everyone=False)
                    await message.delete()

                    embed_revoke = discord.Embed(
                        title="🛑 Slot Revoked",
                        description=f"<@{message.author.id}>, you have exceeded your mention limit (`{reason}`). You have lost write access to this channel.",
                        color=discord.Color.dark_red()
                    )
                    embed_revoke.set_footer(text="Please contact the administration if you believe this is an error.")
                    await message.channel.send(embed=embed_revoke)

                else:
                    rem_here = slot["limit_here"] - slot["used_here"]
                    rem_every = slot["limit_everyone"] - slot["used_everyone"]
                    
                    embed_info = discord.Embed(
                        title="🔔 Mention Used",
                        description="Here is your new mention balance for this slot:",
                        color=discord.Color.gold()
                    )
                    embed_info.add_field(name="`@here` Mentions", value=f"{rem_here} remaining", inline=True)
                    embed_info.add_field(name="`@everyone` Mentions", value=f"{rem_every} remaining", inline=True)
                    
                    await message.channel.send(content=message.author.mention, embed=embed_info)

                save_data(bot.slots_data)

    await bot.process_commands(message)

# Lancement du bot avec la vérification que le token existe bien
if TOKEN is None:
    print("ERREUR: La variable d'environnement DISCORD_TOKEN n'est pas définie.")
else:
    bot.run(TOKEN)
