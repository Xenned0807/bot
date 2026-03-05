
import discord
from discord.ext import commands, tasks
import json
import os
import datetime
import asyncio
import io
from aiohttp import web
from dateutil.relativedelta import relativedelta 

# --- CONFIGURATION ---
TOKEN = os.getenv("DISCORD_TOKEN")
DB_CHANNEL_ID = os.getenv("DB_CHANNEL_ID") # The ID of the private Discord channel for database

# --- DISCORD CHANNEL DATABASE ---
async def load_data(bot):
    if not DB_CHANNEL_ID:
        print("ERROR: DB_CHANNEL_ID environment variable is missing!")
        return {"admins": [], "slots": {}}
        
    channel = bot.get_channel(int(DB_CHANNEL_ID))
    if not channel:
        print("ERROR: Could not find the database channel. Check the ID and bot permissions.")
        return {"admins": [], "slots": {}}

    # Look for the last message with an attachment
    async for message in channel.history(limit=10):
        if message.attachments:
            try:
                file_bytes = await message.attachments[0].read()
                data = json.loads(file_bytes.decode('utf-8'))
                print("✅ Database loaded from Discord channel successfully.")
                if "slots" not in data:
                    return {"admins": [], "slots": data}
                return data
            except Exception as e:
                print(f"Error parsing database: {e}")
                
    print("ℹ️ No database file found in channel. Starting fresh.")
    return {"admins": [], "slots": {}}

async def save_data(bot):
    if not DB_CHANNEL_ID:
        return
        
    channel = bot.get_channel(int(DB_CHANNEL_ID))
    if not channel:
        return

    # Convert the dictionary to a JSON file in memory
    data_str = json.dumps(bot.slots_data, indent=4)
    file = discord.File(io.BytesIO(data_str.encode('utf-8')), filename="slots_data.json")
    
    # Purge old messages in the DB channel to keep it clean (optional but recommended)
    try:
        await channel.purge(limit=5)
    except Exception:
        pass # In case bot lacks manage_messages permission in that specific channel
        
    await channel.send("💾 Auto-backup of slots data", file=file)

# --- WEB SERVER FOR RENDER ---
async def handle_web(request):
    return web.Response(text="Bot is running smoothly!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)
bot.slots_data = {"admins": [], "slots": {}} # Default empty state until loaded

# --- PERMISSIONS CHECK ---
def is_bot_admin():
    async def predicate(ctx):
        if ctx.author.guild_permissions.administrator:
            return True
        if ctx.author.id in bot.slots_data.get("admins", []):
            return True
        return False
    return commands.check(predicate)

# --- EVENTS ---
@bot.event
async def on_ready():
    # Only run setup once (on_ready can trigger multiple times if connection drops)
    if not hasattr(bot, 'startup_done'):
        # Load the data from the Discord channel
        bot.slots_data = await load_data(bot)
        
        bot.check_expirations.start()
        bot.reset_pings.start()
        bot.loop.create_task(start_web_server())
        
        bot.startup_done = True
        print(f"Bot connected as {bot.user} | Prefix: +")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument. Please check the command syntax.")
    elif isinstance(error, commands.CommandNotFound):
        pass 
    else:
        print(f"Error: {error}")

# --- BACKGROUND TASKS ---
@tasks.loop(hours=1)
async def check_expirations():
    now = datetime.datetime.now().timestamp()
    to_delete = []

    for channel_id_str, slot in bot.slots_data["slots"].items():
        if slot["expire_at"] and now > slot["expire_at"]:
            channel = bot.get_channel(int(channel_id_str))
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
        del bot.slots_data["slots"][ch_id]
        
    if to_delete:
        await save_data(bot)

@tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=datetime.timezone.utc))
async def reset_pings():
    for channel_id_str, slot in bot.slots_data["slots"].items():
        slot["used_here"] = 0
        slot["used_everyone"] = 0
        
        channel = bot.get_channel(int(channel_id_str))
        if channel:
            owner = channel.guild.get_member(slot["owner_id"])
            if owner:
                await channel.set_permissions(owner, send_messages=True, mention_everyone=True, manage_messages=True)
            
            embed = discord.Embed(
                title="🔄 Daily Pings Reset",
                description=f"<@{slot['owner_id']}>, your daily pings have been reset to zero! You can now use your allowed mentions again.",
                color=discord.Color.blue()
            )
            await channel.send(embed=embed)
            
    await save_data(bot)

# --- COMMANDS ---

@bot.command(name="addowner")
@commands.has_permissions(administrator=True) 
async def addowner(ctx, member: discord.Member):
    if member.id not in bot.slots_data["admins"]:
        bot.slots_data["admins"].append(member.id)
        await save_data(bot)
        await ctx.send(f"✅ {member.mention} has been added as a bot admin.")
    else:
        await ctx.send(f"⚠️ {member.mention} is already a bot admin.")


@bot.command(name="screate")
@is_bot_admin()
async def screate(ctx, duration: str, client: discord.Member):
    guild = ctx.guild
    duration = duration.lower()

    expire_timestamp = None
    duration_text = "Unknown"
    
    if duration == "1w":
        expire_date = datetime.datetime.now() + relativedelta(weeks=1)
        expire_timestamp = expire_date.timestamp()
        duration_text = "1 Week"
    elif duration == "1m":
        expire_date = datetime.datetime.now() + relativedelta(months=1)
        expire_timestamp = expire_date.timestamp()
        duration_text = "1 Month"
    elif duration == "lifetime":
        expire_timestamp = None
        duration_text = "Lifetime"
    else:
        await ctx.send("❌ Invalid duration. Please use `1w`, `1m`, or `lifetime`.")
        return

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        client: discord.PermissionOverwrite(read_messages=True, send_messages=True, mention_everyone=True, manage_messages=True)
    }

    category = ctx.channel.category 
    channel_name = f"slot-{client.name}"
    
    new_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)

    bot.slots_data["slots"][str(new_channel.id)] = {
        "owner_id": client.id,
        "expire_at": expire_timestamp,
        "limit_here": 0,       
        "limit_everyone": 0,   
        "used_here": 0,
        "used_everyone": 0
    }
    await save_data(bot)

    embed = discord.Embed(
        title="🎉 Personal Slot Created",
        description=f"Welcome to your channel <@{client.id}>!\nYou can promote your services here.",
        color=discord.Color.green()
    )
    embed.add_field(name="Plan", value=duration_text, inline=True)
    if expire_timestamp:
        embed.add_field(name="Expires on", value=f"<t:{int(expire_timestamp)}:d>", inline=True)
    else:
        embed.add_field(name="Expires on", value="Never (Lifetime)", inline=True)
        
    embed.set_footer(text="An admin needs to configure your daily pings with +setpings.")

    await new_channel.send(content=client.mention, embed=embed)
    await ctx.send(f"✅ The slot has been created: {new_channel.mention}. Don't forget to use `+setpings` inside it.")


@bot.command(name="setpings")
@is_bot_admin()
async def setpings(ctx, limit_here: int, limit_everyone: int):
    channel_id_str = str(ctx.channel.id)
    
    if channel_id_str not in bot.slots_data["slots"]:
        await ctx.send("❌ This channel is not a registered slot.")
        return

    slot = bot.slots_data["slots"][channel_id_str]
    slot["limit_here"] = limit_here
    slot["limit_everyone"] = limit_everyone
    await save_data(bot)

    embed = discord.Embed(
        title="⚙️ Daily Pings Configured",
        description=f"The daily ping limits for this slot have been updated.",
        color=discord.Color.green()
    )
    embed.add_field(name="`@here` Limit", value=str(limit_here), inline=True)
    embed.add_field(name="`@everyone` Limit", value=str(limit_everyone), inline=True)
    embed.set_footer(text="Pings will automatically reset every 24 hours.")
    
    await ctx.send(embed=embed)


@bot.command(name="pings")
async def pings(ctx):
    channel_id_str = str(ctx.channel.id)
    
    if channel_id_str not in bot.slots_data["slots"]:
        await ctx.send("❌ This channel is not a registered slot.")
        return

    slot = bot.slots_data["slots"][channel_id_str]
    
    if slot["owner_id"] != ctx.author.id and ctx.author.id not in bot.slots_data["admins"] and not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ You do not have permission to view this.")
        return

    rem_here = slot["limit_here"] - slot["used_here"]
    rem_every = slot["limit_everyone"] - slot["used_everyone"]

    embed = discord.Embed(
        title="📊 Your Daily Mentions Left",
        color=discord.Color.blue()
    )
    embed.add_field(name="`@here` Mentions", value=f"{rem_here} remaining", inline=True)
    embed.add_field(name="`@everyone` Mentions", value=f"{rem_every} remaining", inline=True)
    embed.set_footer(text="These limits reset every 24 hours.")
    
    await ctx.send(embed=embed)


@bot.command(name="list")
@is_bot_admin()
async def list_slots(ctx):
    if not bot.slots_data["slots"]:
        await ctx.send("📭 There are no active slots at the moment.")
        return

    embed = discord.Embed(
        title="📋 List of Active Slots",
        color=discord.Color.purple()
    )
    
    for channel_id_str, slot in bot.slots_data["slots"].items():
        channel = bot.get_channel(int(channel_id_str))
        channel_name = channel.mention if channel else f"Deleted Channel ({channel_id_str})"
        
        expire_at = slot["expire_at"]
        if expire_at:
            expire_text = f"<t:{int(expire_at)}:f>"
        else:
            expire_text = "Never (Lifetime)"
            
        embed.add_field(
            name=f"Owner: @{bot.get_user(slot['owner_id'])}", 
            value=f"**Channel:** {channel_name}\n**Expires:** {expire_text}", 
            inline=False
        )
        
    await ctx.send(embed=embed)


@bot.command(name="sdelete", aliases=["sclose"])
@is_bot_admin()
async def sdelete(ctx, client: discord.Member):
    to_delete = []
    
    for channel_id_str, slot in bot.slots_data["slots"].items():
        if slot["owner_id"] == client.id:
            to_delete.append(channel_id_str)
            
    if not to_delete:
        await ctx.send(f"❌ {client.mention} doesn't own any active slots.")
        return
        
    for ch_id in to_delete:
        channel = bot.get_channel(int(ch_id))
        if channel:
            await channel.delete(reason=f"Slot deleted by {ctx.author.name}")
        del bot.slots_data["slots"][ch_id]
        
    await save_data(bot)
    await ctx.send(f"✅ Successfully deleted {len(to_delete)} slot(s) for {client.mention}.")


@bot.command(name="sextend")
@is_bot_admin()
async def sextend(ctx, client: discord.Member, duration: str):
    duration = duration.lower()
    slots_found = []
    
    for channel_id_str, slot in bot.slots_data["slots"].items():
        if slot["owner_id"] == client.id:
            slots_found.append(channel_id_str)
            
    if not slots_found:
        await ctx.send(f"❌ {client.mention} doesn't own any active slots.")
        return
        
    if duration not in ["1w", "1m", "lifetime"]:
        await ctx.send("❌ Invalid duration. Please use `1w`, `1m`, or `lifetime`.")
        return
        
    for ch_id in slots_found:
        slot = bot.slots_data["slots"][ch_id]
        
        if duration == "lifetime":
            slot["expire_at"] = None
        else:
            current_expire = slot["expire_at"]
            if current_expire:
                base_date = datetime.datetime.fromtimestamp(current_expire)
            else: 
                base_date = datetime.datetime.now()
                
            if duration == "1w":
                new_date = base_date + relativedelta(weeks=1)
            elif duration == "1m":
                new_date = base_date + relativedelta(months=1)
                
            slot["expire_at"] = new_date.timestamp()
            
    await save_data(bot)
    await ctx.send(f"✅ Successfully extended {len(slots_found)} slot(s) for {client.mention} by {duration}.")


# --- MENTIONS MONITORING ---
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    channel_id_str = str(message.channel.id)
    
    if channel_id_str in bot.slots_data["slots"]:
        slot = bot.slots_data["slots"][channel_id_str]
        
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
                        description=f"<@{message.author.id}>, you have exceeded your daily mention limit (`{reason}`). You have lost write access to this channel until the daily reset.",
                        color=discord.Color.dark_red()
                    )
                    await message.channel.send(embed=embed_revoke)

                else:
                    rem_here = slot["limit_here"] - slot["used_here"]
                    rem_every = slot["limit_everyone"] - slot["used_everyone"]
                    
                    embed_info = discord.Embed(
                        title="🔔 Mention Used",
                        description="Here is your remaining daily balance:",
                        color=discord.Color.gold()
                    )
                    embed_info.add_field(name="`@here` Mentions", value=f"{rem_here} remaining", inline=True)
                    embed_info.add_field(name="`@everyone` Mentions", value=f"{rem_every} remaining", inline=True)
                    
                    await message.channel.send(content=message.author.mention, embed=embed_info)

                await save_data(bot)

    await bot.process_commands(message)


if TOKEN is None:
    print("ERROR: DISCORD_TOKEN environment variable is not set.")
else:
    bot.run(TOKEN)
