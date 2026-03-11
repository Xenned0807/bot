import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Select, View, Button
import os
from flask import Flask
from threading import Thread

# ==========================================
# 1. KEEP-ALIVE SYSTEM
# ==========================================
app = Flask(__name__)
@app.route('/')
def home(): return "Void Market is Online"
def run(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): Thread(target=run).start()

# ==========================================
# 2. CONFIGURATION
# ==========================================
class VoidMarketBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(CatalogueView())
        await self.tree.sync()

bot = VoidMarketBot()

BANNER_URL = "https://cdn.discordapp.com/attachments/1461729802343026924/1481107023092514887/AD_SERVICES_1.gif?ex=69b21be7&is=69b0ca67&hm=98b23b586698306b0b230036e71865d5e0d1a2f976586ca077e401aef32b770a"
LINE = "──────────────────────────────────"

# ==========================================
# 3. NAVIGATION & CATEGORIES
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

class CatalogueDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label='Discord Services', emoji='<:discord:1480254596470538332>', value='ds'),
            discord.SelectOption(label='Streaming & VOD', emoji='<:etoile2:1481089511646691338>', value='st'),
            discord.SelectOption(label='Software & AI', emoji='<:web:1481088736237457559>', value='sw'),
            discord.SelectOption(label='Social Boost', emoji='<:rocket2:1481087095878451250>', value='sb')
        ]
        super().__init__(placeholder='Browse Void Market Products', options=options, custom_id='dropdown_void')

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(color=0x2B2D31)
        val = self.values[0]
        
        if val == 'ds':
            embed.title = "<:discord:1480254596470538332> | Discord Services"
            embed.add_field(name="<a:nitro:1481087743873519747> Nitro & Boosts", value="<:dot:1481087122684383382> **Nitro Monthly**: 3.99€\n<:dot:1481087122684383382> **Promo 1M**: 0.20€ | **3M**: 0.50€\n<:dot:1481087122684383382> **Boosts x14 (1M)**: 1.50€ | **(3M)**: 2.30€", inline=False)
            embed.add_field(name="<a:diamond:1481087586280673321> Real Members", value="<:dot:1481087122684383382> **500**: 4.20€ | **1000**: 6.00€\n<:dot:1481087122684383382> **5000**: 19.90€", inline=False)
            embed.add_field(name="<:coche:1470525470528241695> Aged Accounts (FA)", value="<:dot:1481087122684383382> **2015**: 69.99€ | **2017**: 6.49€\n<:dot:1481087122684383382> **2021**: 2.49€ | **2025**: 0.75€", inline=False)

        elif val == 'st':
            embed.title = "<:etoile2:1481089511646691338> | Streaming & VOD"
            embed.description = "### <:money:1481087153848189171> Premium Subscriptions (Prices x3)"
            
            embed.add_field(name="🟢 Spotify Premium", value=(
                "<:dot:1481087122684383382> **LIFETIME PREMIUM (KEY)**: 10.99€\n"
                "<:dot:1481087122684383382> **Family Owner LIFETIME**: 9.49€\n"
                "<:dot:1481087122684383382> **6 Months**: 8.99€\n"
                "<:dot:1481087122684383382> **3 Months**: 5.99€"
                "<:dot:1481087122684383382> **2 Months**: 3.49€"
                "<:dot:1481087122684383382> **1 Months**: 1.99€"
            ), inline=False)
            
            embed.add_field(name="🔴 Netflix Premium", value=(
                "<:dot:1481087122684383382> **1 Month**: 1.20€\n"
                "<:dot:1481087122684383382> **3 Months**: 1.49€\n"
                "<:dot:1481087122684383382> **6 Months**: 2.00€\n"
                "<:dot:1481087122684383382> **LIFETIME 4K Premium**: 4.99€\n"
                "<:dot:1481087122684383382> **Full Access**: 7.99€"
                "<:dot:1481087122684383382> **Full Access [5-Profiles]**: 9.99€"
                
            ), inline=False)
            
            embed.add_field(name="🔵 Disney Plus", value=(
                "<:dot:1481087122684383382> **12 Months**: 1.49€\n"
                "<:dot:1481087122684383382> **LIFETIME**: 2.00€\n"
                "<:dot:1481087122684383382> **Private Account**: 4.99€"
            ), inline=False)
            
            embed.add_field(name="➕ Others (1.20€/u)", value="<:dot:1481087122684383382> Crunchyroll, Nord VPN, Prime Video, Paramount+, Capcut Pro, DAZN", inline=False)

        elif val == 'sw':
            embed.title = "<:web:1481088736237457559> | Software & AI"
            embed.add_field(name="<:question2:1481087011698774270> AI Tools", value="<:dot:1481087122684383382> **ChatGPT Plus**: 5.00€\n<:dot:1481087122684383382> **Canva Pro**: 1.20€", inline=False)
            embed.add_field(name="<:stock:1481088748891672626> Developer Tools", value="<:dot:1481087122684383382> **Boost Tool Source**: 15.00€", inline=False)

        elif val == 'sb':
            embed.title = "<:rocket2:1481087095878451250> | Social Boost"
            embed.add_field(name="<:attention:1481088721469313088> Social Panel", value="<:dot:1481087122684383382> **Full Panel Access**: 10.00€", inline=False)
            embed.add_field(name="<a:diamond:1481087586280673321> TikTok", value="<:dot:1481087122684383382> **Fol**: 2€/1k | **Like**: 0.5€/1k | **View**: 0.3€/1k", inline=False)
            embed.add_field(name="<a:diamond:1481087586280673321> Instagram", value="<:dot:1481087122684383382> **Fol**: 2.5€/1k | **Like**: 2€/1k | **View**: 0.5€/1k", inline=False)

        embed.set_footer(text="To place an order, please open a ticket.")
        try:
            await interaction.response.send_message(embed=embed, view=BackView(), ephemeral=True)
        except:
            await interaction.response.edit_message(embed=embed, view=BackView())

class CatalogueView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CatalogueDropdown())

# ==========================================
# 4. COMMANDES
# ==========================================
@bot.tree.command(name="stock", description="Official layout with internal header")
@app_commands.default_permissions(administrator=True)
async def stock(interaction: discord.Interaction):
    header = discord.Embed(color=0x2B2D31)
    header.set_image(url=BANNER_URL)
    
    desc = f"""## <:cart:1481081418476945582> **| Void Market — Official Stock**
-# <:info:1481086978387869867> Select a category below to view our products.

{LINE}
<:discord:1480254596470538332> **Discord Services**
Nitro, Server Boosts, Accounts, Tokens, Members...

{LINE}
<:etoile2:1481089511646691338> **Streaming & VOD**
Spotify, Netflix, Disney+, Crunchyroll, VPN...

{LINE}
<:web:1481088736237457559> **Software & AI**
ChatGPT Plus, Canva Pro, Boost Tool...

{LINE}
<:rocket2:1481087095878451250> **Social Boost**
TikTok, Instagram, Panel Access...

{LINE}
<:attention:1481088721469313088> **Important Note:**
-# <:ticket2:1481087046465356009> Simply open a ticket to purchase!"""

    content = discord.Embed(description=desc, color=0x2B2D31)
    content.set_footer(text="Void Market © 2026")

    await interaction.channel.send(embeds=[header, content], view=CatalogueView())
    await interaction.response.send_message("✅ Stock deployed!", ephemeral=True)

@bot.tree.command(name="web", description="Website layout")
@app_commands.default_permissions(administrator=True)
async def web(interaction: discord.Interaction):
    desc = f"""## <:store:1481087026815303810> **| Void Market — Website**
{LINE}
<:arrow:1481087177730293860> Instant Delivery
<:arrow:1481087177730293860> 24/7 Customer Support
<:arrow:1481087177730293860> Simple and Secure Payment"""
    
    embed = discord.Embed(description=desc, color=0x2B2D31)
    embed.set_image(url=BANNER_URL)
    
    view = View()
    btn = Button(label="Go to Website", style=discord.ButtonStyle.link, url="https://voidmrkt.mysellauth.com/", emoji="<:store:1481087026815303810>")
    view.add_item(btn)

    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Website link deployed!", ephemeral=True)

if __name__ == "__main__":
    keep_alive()
    bot.run(os.environ.get("DISCORD_TOKEN"))
