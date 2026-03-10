import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Select, View
import os
from flask import Flask
from threading import Thread

# ==========================================
# 1. KEEP-ALIVE SYSTEM (FOR RENDER)
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Void Market Bot is running smoothly!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ==========================================
# 2. BOT CONFIGURATION & SYNC
# ==========================================
class VoidMarketBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        # Prefix is still required by the library, but we will use Slash Commands
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Keeps the view active even after the bot restarts
        self.add_view(CatalogueView())
        # Syncs the slash commands globally with Discord
        await self.tree.sync()
        print("Slash commands synced successfully!")

bot = VoidMarketBot()

@bot.event
async def on_ready():
    print(f'Successfully logged in as {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Void Market Stock"))

# ==========================================
# 3. CATALOGUE DROPDOWN MENU (INTERACTIVE)
# ==========================================
class CatalogueDropdown(Select):
    def __init__(self):
        # Dropdown options (Categories)
        options = [
            discord.SelectOption(
                label='Discord Services',
                description='Nitro, Server Boosts, Tokens, Accounts...',
                emoji='👾', # Replace with a custom emoji ID like <:name:ID>
                value='discord_services'
            ),
            discord.SelectOption(
                label='Streaming & VOD',
                description='Netflix, Disney+, Spotify, DAZN...',
                emoji='🍿', 
                value='streaming_services'
            ),
            discord.SelectOption(
                label='Software & AI',
                description='ChatGPT Plus, Canva Pro, VPN...',
                emoji='💻', 
                value='software_ai'
            ),
            discord.SelectOption(
                label='Social Boost',
                description='Panel & Social Media Boosts...',
                emoji='🚀', 
                value='social_boost'
            )
        ]
        super().__init__(placeholder='Browse Void Market Products', min_values=1, max_values=1, options=options, custom_id='void_market_stock_menu')

    # What happens when a user selects a category
    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        
        info_embed = discord.Embed(color=0x2B2D31) # Dark Discord background color
        
        if choice == 'discord_services':
            info_embed.title = "👾 | Stock: Discord Services"
            info_embed.description = "Here are our current prices for Discord-related services:"
            info_embed.add_field(name="💎 Nitro & Promos", value="• **Nitro (Classic/Boost)**: $[Price]\n• **Nitro Promos**: $[Price]", inline=False)
            info_embed.add_field(name="🚀 Boosts & Tools", value="• **Server Boosts**: $[Price]\n• **Boost Tool**: $[Price]", inline=False)
            info_embed.add_field(name="👥 Members & Tokens", value="• **Real Members**: $[Price]\n• **Tokens (Classic & Nitro)**: $[Price]", inline=False)
            info_embed.add_field(name="⚙️ Accounts & Misc", value="• **Aged Accounts**: $[Price]\n• **Decorations**: $[Price]", inline=False)

        elif choice == 'streaming_services':
            info_embed.title = "🍿 | Stock: Streaming & VOD"
            info_embed.description = "Enjoy your favorite movies, series, and music at the best prices:"
            info_embed.add_field(name="📺 Movies & Series", value="• **Netflix**: $[Price]\n• **Disney+**: $[Price]\n• **Prime Video**: $[Price]\n• **Paramount+**: $[Price]", inline=False)
            info_embed.add_field(name="🎵 Music & Anime", value="• **Spotify Premium**: $[Price]\n• **Crunchyroll**: $[Price]", inline=False)
            info_embed.add_field(name="⚽ Sports", value="• **DAZN**: $[Price]", inline=False)

        elif choice == 'software_ai':
            info_embed.title = "💻 | Stock: Software & AI"
            info_embed.description = "Boost your productivity and secure your connection:"
            info_embed.add_field(name="🤖 Artificial Intelligence", value="• **ChatGPT Plus**: $[Price]", inline=False)
            info_embed.add_field(name="🎨 Design & Editing", value="• **Canva Pro**: $[Price]\n• **CapCut Pro**: $[Price]", inline=False)
            info_embed.add_field(name="🔒 Security", value="• **Nord VPN**: $[Price]", inline=False)

        elif choice == 'social_boost':
            info_embed.title = "🚀 | Stock: Social Boost"
            info_embed.description = "Grow your social media presence effortlessly:"
            info_embed.add_field(name="📈 Boosts", value="• **Social Boost (Followers, Views...)**: $[Price]\n• **Panel Access**: $[Price]", inline=False)

        info_embed.set_footer(text="To place an order, please open a ticket in the dedicated channel.")

        # SENDING THE MESSAGE IN EPHEMERAL MODE (Only the user sees it)
        await interaction.response.send_message(embed=info_embed, ephemeral=True)

class CatalogueView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CatalogueDropdown())

# ==========================================
# 4. SLASH COMMAND (/stock)
# ==========================================
@bot.tree.command(name="stock", description="Deploys the Void Market official stock embed in the current channel.")
@app_commands.default_permissions(administrator=True) # Only admins can see and use this command
async def stock(interaction: discord.Interaction):
    # The Main Professional Embed
    embed = discord.Embed(
        title="🛒 | Void Market — Official Stock",
        description="Welcome to the **Void Market** store.\nSelect a category from the menu below to view our available products and real-time pricing.\n\n---",
        color=0xE50914 # Pro Red Color
    )
    
    # ⚠️ UNCOMMENT THE LINE BELOW AND PASTE YOUR IMAGE LINK FOR THE BANNER
    embed.set_image(url="https://files.catbox.moe/l23tfy.jpg")
    
    # \n\n--- creates the sleek separator lines you wanted
    embed.add_field(name="👾 Discord Services", value="Nitro, Server Boosts, Tokens, Accounts...\n\n---", inline=False)
    embed.add_field(name="🍿 Streaming & VOD", value="Netflix, Disney+, Spotify, Crunchyroll...\n\n---", inline=False)
    embed.add_field(name="💻 Software & AI", value="ChatGPT Plus, Canva Pro, Nord VPN...\n\n---", inline=False)
    embed.add_field(name="🚀 Social Boost", value="Panel, Boosts for your social media...\n\n---", inline=False)
    
    embed.add_field(name="❗ How to purchase?", value="> Simply open a ticket in the order channel after making your choice!", inline=False)
    
    embed.set_footer(text="Void Market © 2026", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

    # Sends the embed and the dropdown menu to the channel
    await interaction.channel.send(embed=embed, view=CatalogueView())
    
    # Replies to the admin who used the command (only the admin sees this confirmation)
    await interaction.response.send_message("✅ Stock embed deployed successfully!", ephemeral=True)

# ==========================================
# 5. BOT STARTUP
# ==========================================
if __name__ == "__main__":
    keep_alive() 
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("ERROR: DISCORD_TOKEN environment variable not found.")
