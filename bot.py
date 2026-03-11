import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Select, View, Button
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
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(CatalogueView())
        await self.tree.sync()
        print("Slash commands synced successfully!")

bot = VoidMarketBot()

@bot.event
async def on_ready():
    print(f'Successfully logged in as {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Void Market"))

# ==========================================
# 3. CATALOGUE DROPDOWN MENU (INTERACTIVE)
# ==========================================
class CatalogueDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label='Discord Services', description='Nitro, Server Boosts, Tokens, Accounts...', emoji='<:discord:1480254596470538332>', value='discord_services'),
            discord.SelectOption(label='Streaming & VOD', description='Netflix, Disney+, Spotify, DAZN...', emoji='<:etoile2:1481089511646691338>', value='streaming_services'),
            discord.SelectOption(label='Software & AI', description='ChatGPT Plus, Canva Pro, VPN...', emoji='<:web:1481088736237457559>', value='software_ai'),
            discord.SelectOption(label='Social Boost', description='Panel & Social Media Boosts...', emoji='<:rocket2:1481087095878451250>', value='social_boost')
        ]
        super().__init__(placeholder='Browse Void Market Products', min_values=1, max_values=1, options=options, custom_id='void_market_stock_menu')

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        info_embed = discord.Embed(color=0x2B2D31)
        
        if choice == 'discord_services':
            info_embed.title = "<:discord:1480254596470538332> | Stock: Discord Services"
            info_embed.description = "Current prices for Discord-related services:"
            info_embed.add_field(name="<a:nitro:1481087743873519747> Nitro & Promos", value="- **Nitro (Classic/Boost)**: <:money:1481087153848189171> [Price]\n- **Nitro Promos**: <:money:1481087153848189171> [Price]", inline=False)
            info_embed.add_field(name="<:serverboost:1481087138115358783> Boosts & Tools", value="- **Server Boosts**: <:money:1481087153848189171> [Price]\n- **Boost Tool**: <:money:1481087153848189171> [Price]", inline=False)

        elif choice == 'streaming_services':
            info_embed.title = "<:etoile2:1481089511646691338> | Stock: Streaming & VOD"
            info_embed.description = "Movies, series, and music at the best prices:"
            info_embed.add_field(name="<:coche:1470525470528241695> Subscriptions", value="- **Netflix**: <:money:1481087153848189171> [Price]\n- **Disney+**: <:money:1481087153848189171> [Price]\n- **Spotify**: <:money:1481087153848189171> [Price]", inline=False)

        elif choice == 'software_ai':
            info_embed.title = "<:web:1481088736237457559> | Stock: Software & AI"
            info_embed.description = "Productivity and security tools:"
            info_embed.add_field(name="<:coche:1470525470528241695> AI & Design", value="- **ChatGPT Plus**: <:money:1481087153848189171> [Price]\n- **Canva Pro**: <:money:1481087153848189171> [Price]", inline=False)

        elif choice == 'social_boost':
            info_embed.title = "<:rocket2:1481087095878451250> | Stock: Social Boost"
            info_embed.description = "Grow your social media presence:"
            info_embed.add_field(name="<a:diamond:1481087586280673321> Growth", value="- **Social Boost**: <:money:1481087153848189171> [Price]\n- **Panel Access**: <:money:1481087153848189171> [Price]", inline=False)

        info_embed.set_footer(text="To place an order, please open a ticket.")
        await interaction.response.send_message(embed=info_embed, ephemeral=True)

class CatalogueView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CatalogueDropdown())

# ==========================================
# 4. SLASH COMMANDS (/stock & /web)
# ==========================================

@bot.tree.command(name="stock", description="Deploys the Void Market official stock embed.")
@app_commands.default_permissions(administrator=True)
async def stock(interaction: discord.Interaction):
    description_text = """## <:stock:1481088748891672626> **| Void Market — Official Stock**
-# <:info:1481086978387869867> Our team is here to help. Select a category below to view our products.

---
<:discord:1480254596470538332> **Discord Services**
- Nitro, Server Boosts, Tokens, Accounts...
- Delivery is instant and secure.

---
<:etoile2:1481089511646691338> **Streaming & VOD**
- Netflix, Disney+, Spotify, Crunchyroll...
- Premium accounts at the best market price.

---
<:web:1481088736237457559> **Software & AI**
- ChatGPT Plus, Canva Pro, Nord VPN...
- Boost your productivity effortlessly.

---
<:rocket2:1481087095878451250> **Social Boost**
- Panel, Boosts for your social media...
- Fast delivery to grow your audience.

---
<:attention:1481088721469313088> **Important Note:**
-# By purchasing, you agree to our terms. Simply open a ticket in the order channel after making your choice!"""

    embed = discord.Embed(description=description_text, color=0x2B2D31)
    embed.set_image(url="https://cdn.discordapp.com/attachments/1461729802343026924/1481090421181644820/banner.jpg?ex=69b20c71&is=69b0baf1&hm=446b81abefcc0c5f2e5ef067460ca49f02b03e54c098c0f1c79b1398d1f387be") 
    embed.set_footer(text="Void Market © 2026", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

    await interaction.channel.send(embed=embed, view=CatalogueView())
    await interaction.response.send_message("✅ Stock embed deployed!", ephemeral=True)

@bot.tree.command(name="web", description="Deploys the Void Market website embed.")
@app_commands.default_permissions(administrator=True)
async def web(interaction: discord.Interaction):
    embed = discord.Embed(
        title="<:store:1481087026815303810> Website",
        description="<:arrow:1481087177730293860> Instant Delivery\n<:arrow:1481087177730293860> Support 24/24\n<:arrow:1481087177730293860> Simple and Secure Payment",
        color=0x2B2D31
    )
    # embed.set_image(url="Lien_Banner_Web_Optionnel")
    
    view = View()
    button = Button(
        label="Go to Website", 
        style=discord.ButtonStyle.link,
        url="https://voidmrkt.mysellauth.com/", 
        emoji=discord.PartialEmoji.from_str("<:store:1481087026815303810>")
    )
    view.add_item(button)

    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Website embed deployed!", ephemeral=True)

if __name__ == "__main__":
    keep_alive() 
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
