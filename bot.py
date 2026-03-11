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
# 2. BOT CONFIGURATION
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

bot = VoidMarketBot()

# OFFICIAL BANNER URL
BANNER_URL = "https://cdn.discordapp.com/attachments/1461729802343026924/1481090421181644820/banner.jpg?ex=69b20c71&is=69b0baf1&hm=446b81abefcc0c5f2e5ef067460ca49f02b03e54c098c0f1c79b1398d1f387be"

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

# ==========================================
# 3. INTERACTIVE NAVIGATION (BACK BUTTON)
# ==========================================
class BackView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Back to Menu", style=discord.ButtonStyle.gray, emoji="<:arrow:1481087177730293860>")
    async def back_button(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="<:stock:1481088748891672626> | Interactive Catalogue",
            description="Select a category below to browse our prices and services.",
            color=0x2B2D31
        )
        await interaction.response.edit_message(embed=embed, view=CatalogueView())

# ==========================================
# 4. DROPDOWN MENU (ENGLISH & UPDATED PRICES)
# ==========================================
class CatalogueDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label='Discord Services', description='Nitro, Boosts, Tokens, Accounts...', emoji='<:discord:1480254596470538332>', value='discord_services'),
            discord.SelectOption(label='Streaming & VOD', description='Netflix, Disney+, Spotify...', emoji='<:etoile2:1481089511646691338>', value='streaming_services'),
            discord.SelectOption(label='Software & AI', description='ChatGPT Plus, Canva, Tools...', emoji='<:web:1481088736237457559>', value='software_ai'),
            discord.SelectOption(label='Social Boost', description='Followers, Likes, Panel...', emoji='<:rocket2:1481087095878451250>', value='social_boost')
        ]
        super().__init__(placeholder='Browse Void Market Products', min_values=1, max_values=1, options=options, custom_id='void_market_stock_menu')

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        embed = discord.Embed(color=0x2B2D31)
        
        if choice == 'discord_services':
            embed.title = "<:discord:1480254596470538332> | Stock: Discord Services"
            embed.add_field(name="<a:nitro:1481087743873519747> Nitro & Promos", value="<:dot:1481087122684383382> **Nitro Monthly**: 3.99€\n<:dot:1481087122684383382> **Nitro Promo (1M)**: 0.20€\n<:dot:1481087122684383382> **Nitro Promo (3M)**: 0.50€", inline=False)
            embed.add_field(name="<:serverboost:1481087138115358783> Server Boosts (x14)", value="<:dot:1481087122684383382> **1 Month**: 1.50€\n<:dot:1481087122684383382> **3 Months**: 2.30€", inline=False)
            embed.add_field(name="<:coche:1470525470528241695> Aged Accounts", value="<:dot:1481087122684383382> **2015**: 69.99€ | **2017**: 6.49€\n<:dot:1481087122684383382> **2021**: 2.49€ | **2025**: 0.75€", inline=False)

        elif choice == 'streaming_services':
            embed.title = "<:etoile2:1481089511646691338> | Stock: Streaming & VOD"
            embed.description = "### <:money:1481087153848189171> Price: 1.20€ / item"
            embed.add_field(name="<:coche:1470525470528241695> Available Services", value="- Spotify, Netflix, Disney+, Crunchyroll, Nord VPN, Prime Video, Paramount+, Capcut Pro, DAZN", inline=False)

        elif choice == 'software_ai':
            embed.title = "<:web:1481088736237457559> | Stock: Software & AI"
            embed.add_field(name="<:question2:1481087011698774270> Artificial Intelligence", value="<:dot:1481087122684383382> **ChatGPT Plus**: 5.00€\n<:dot:1481087122684383382> **Canva Pro**: 1.20€", inline=False)
            embed.add_field(name="<:stock:1481088748891672626> Developer Tools", value="<:dot:1481087122684383382> **Boost Tool Source Code**: 15.00€", inline=False)

        elif choice == 'social_boost':
            embed.title = "<:rocket2:1481087095878451250> | Stock: Social Boost"
            embed.add_field(name="<:attention:1481088721469313088> **Social Boost Panel**", value="<:dot:1481087122684383382> **Full Access**: 10.00€", inline=False)
            embed.add_field(name="📱 Social Networks", value="<:dot:1481087122684383382> **TikTok Followers**: 2€ / 1k\n<:dot:1481087122684383382> **Instagram Followers**: 2.5€ / 1k", inline=False)

        embed.set_footer(text="To place an order, please open a ticket.")
        
        # PRO NAVIGATION LOGIC
        if interaction.message.type == discord.MessageType.chat_input_command:
            await interaction.response.send_message(embed=embed, view=BackView(), ephemeral=True)
        else:
            await interaction.response.edit_message(embed=embed, view=BackView())

class CatalogueView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CatalogueDropdown())

# ==========================================
# 5. SLASH COMMANDS
# ==========================================

@bot.tree.command(name="stock", description="Deploys the official stock embed with header banner.")
@app_commands.default_permissions(administrator=True)
async def stock(interaction: discord.Interaction):
    description_text = """## <:stock:1481088748891672626> **| Void Market — Official Stock**
-# <:info:1481086978387869867> Our team is here to help. Select a category below to view our products.

---
<:discord:1480254596470538332> **Discord Services**
- Nitro, Server Boosts, Accounts, Tokens...

---
<:etoile2:1481089511646691338> **Streaming & VOD**
- Netflix, Disney+, Spotify, Crunchyroll...

---
<:web:1481088736237457559> **Software & AI**
- ChatGPT Plus, Canva Pro, Boost Tool...

---
<:rocket2:1481087095878451250> **Social Boost**
- TikTok, Instagram, Panel Access...

---
<:attention:1481088721469313088> **Important Note:**
-# <:ticket2:1481087046465356009> By purchasing, you agree to our terms. Simply open a ticket!"""

    embed = discord.Embed(description=description_text, color=0x2B2D31)
    embed.set_footer(text="Void Market © 2026", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

    # PRO HEADER DISPLAY
    await interaction.channel.send(BANNER_URL) 
    await interaction.channel.send(embed=embed, view=CatalogueView())
    await interaction.response.send_message("✅ Stock deployed successfully!", ephemeral=True)

@bot.tree.command(name="web", description="Deploys the website access embed.")
@app_commands.default_permissions(administrator=True)
async def web(interaction: discord.Interaction):
    description_web = """## <:store:1481087026815303810> **| Void Market — Website**
<:arrow:1481087177730293860> Instant Delivery
<:arrow:1481087177730293860> 24/7 Customer Support
<:arrow:1481087177730293860> Simple and Secure Payment"""
    
    embed = discord.Embed(description=description_web, color=0x2B2D31)
    view = View()
    button = Button(label="Go to Website", style=discord.ButtonStyle.link, url="https://voidmrkt.mysellauth.com/", emoji=discord.PartialEmoji.from_str("<:store:1481087026815303810>"))
    view.add_item(button)

    # BANNER HEADER
    await interaction.channel.send(BANNER_URL)
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Website link deployed!", ephemeral=True)

if __name__ == "__main__":
    keep_alive() 
    bot.run(os.environ.get("DISCORD_TOKEN"))
