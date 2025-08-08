import os
from dotenv import load_dotenv
import discord
from discord.ext import commands

# Charger les variables d'environnement
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("❌ Le token Discord est introuvable. Ajoute-le dans .env ou dans Render.")

# Intents Discord
intents = discord.Intents.default()
intents.members = True
intents.presences = True

# Créer le bot
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user} !")

@bot.event
async def on_disconnect():
    print("⚠️ Bot déconnecté, tentative de reconnexion...")

@bot.event
async def on_resumed():
    print("♻️ Session Discord reprise.")

@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong !")

# Lancer le bot
bot.run(TOKEN)
