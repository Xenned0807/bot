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
            discord.SelectOption(label='Discord Services', description='Nitro, Server Boosts, Tokens, Accounts...', emoji='<:serverboost:1481083615273025627>', value='discord_services'),
            discord.SelectOption(label='Streaming & VOD', description='Netflix, Disney+, Spotify, DAZN...', emoji='🍿', value='streaming_services'),
            discord.SelectOption(label='Software & AI', description='ChatGPT Plus, Canva Pro, VPN...', emoji='💻', value='software_ai'),
            discord.SelectOption(label='Social Boost', description='Panel & Social Media Boosts...', emoji='<:rocket2:1481082136319754382>', value='social_boost')
        ]
        super().__init__(placeholder='Browse Void Market Products', min_values=1, max_values=1, options=options, custom_id='void_market_stock_menu')

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        
        info_embed = discord.Embed(color=0x7110ff) # VOID MARKET PURPLE
        
        if choice == 'discord_services':
            info_embed.title = "<:serverboost:1481083615273025627> | Stock: Discord Services"
            info_embed.description = "Here are our current prices for Discord-related services:"
            info_embed.add_field(name="💎 Nitro & Promos", value="<:dot:1481083633446948954> **Nitro (Classic/Boost)**: <:money:1481081399548186674> [Price]\n<:dot:1481083633446948954> **Nitro Promos**: <:money:1481081399548186674> [Price]", inline=False)
            info_embed.add_field(name="<:rocket2:1481082136319754382> Boosts & Tools", value="<:dot:1481083633446948954> **Server Boosts**: <:money:1481081399548186674> [Price]\n<:dot:1481083633446948954> **Boost Tool**: <:money:1481081399548186674> [Price]", inline=False)

        elif choice == 'streaming_services':
            info_embed.title = "🍿 | Stock: Streaming & VOD"
            info_embed.description = "Enjoy your favorite movies, series, and music at the best prices:"
            info_embed.add_field(name="📺 Movies & Series", value="<:dot:1481083633446948954> **Netflix**: <:money:1481081399548186674> [Price]\n<:dot:1481083633446948954> **Disney+**: <:money:1481081399548186674> [Price]", inline=False)

        elif choice == 'software_ai':
            info_embed.title = "💻 | Stock: Software & AI"
            info_embed.description = "Boost your productivity and secure your connection:"
            info_embed.add_field(name="🤖 Artificial Intelligence", value="<:dot:1481083633446948954> **ChatGPT Plus**: <:money:1481081399548186674> [Price]", inline=False)

        elif choice == 'social_boost':
            info_embed.title = "<:rocket2:1481082136319754382> | Stock: Social Boost"
            info_embed.description = "Grow your social media presence effortlessly:"
            info_embed.add_field(name="📈 Boosts", value="<:dot:1481083633446948954> **Social Boost**: <:money:1481081399548186674> [Price]\n<:dot:1481083633446948954> **Panel Access**: <:money:1481081399548186674> [Price]", inline=False)

        # Utilisation de l'emoji ticket dans le footer
        info_embed.set_footer(text="To place an order, please open a ticket in the dedicated channel.")
        await interaction.response.send_message(embed=info_embed, ephemeral=True)

class CatalogueView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CatalogueDropdown())

# ==========================================
# 4. SLASH COMMANDS (/stock & /web)
# ==========================================

# --- COMMANDE /STOCK ---
@bot.tree.command(name="stock", description="Deploys the Void Market official stock embed.")
@app_commands.default_permissions(administrator=True)
async def stock(interaction: discord.Interaction):
    
    # Structure Markdown Ultime avec tes Emojis Custom !
    description_text = """## <:cart:1481081418476945582> **| Void Market — Official Stock**
-# <:info:1481081383181881445> Our team is here to help. Select a category below to view our products.

<:serverboost:1481083615273025627> **Discord Services**
<:dot:1481083633446948954> Nitro, Server Boosts, Tokens, Accounts...
<:dot:1481083633446948954> Delivery is instant and secure.

🍿 **Streaming & VOD**
<:dot:1481083633446948954> Netflix, Disney+, Spotify, Crunchyroll...
<:dot:1481083633446948954> Premium accounts at the best market price.

💻 **Software & AI**
<:dot:1481083633446948954> ChatGPT Plus, Canva Pro, Nord VPN...
<:dot:1481083633446948954> Boost your productivity effortlessly.

<:rocket2:1481082136319754382> **Social Boost**
<:dot:1481083633446948954> Panel, Boosts for your social media...
<:dot:1481083633446948954> Fast delivery to grow your audience.

<:question2:1481082264602546227> **Important Note:**
-# <:ticket2:1481082245698814034> By purchasing, you agree to our terms. Simply open a ticket in the order channel after making your choice!"""

    embed = discord.Embed(
        description=description_text,
        color=0x7110ff # VOID MARKET PURPLE
    )
    
    # Bannière Catbox activée !
    embed.set_image(url="https://files.catbox.moe/l23tfy.jpg") 
    
    embed.set_footer(text="Void Market © 2026", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

    await interaction.channel.send(embed=embed, view=CatalogueView())
    await interaction.response.send_message("✅ Stock embed deployed successfully!", ephemeral=True)


# --- COMMANDE /WEB ---
@bot.tree.command(name="web", description="Deploys the Void Market website embed with direct link.")
@app_commands.default_permissions(administrator=True)
async def web(interaction: discord.Interaction):
    
    # Embed du site web avec la flèche (arrow)
    embed = discord.Embed(
        title="<:cart:1481081418476945582> Website",
        description="<:arrow:1481083646948671509> Instant Delivery\n<:arrow:1481083646948671509> Support 24/24\n<:arrow:1481083646948671509> Simple and Secure Payment\n\n**https://voidmrkt.mysellauth.com/**",
        color=0x7110ff # VOID MARKET PURPLE
    )
    
    # ⚠️ Tu peux rajouter le lien d'une autre image ici pour l'embed /web !
    embed.set_image(url="https://files.catbox.moe/l23tfy.jpg") 
    
    # Bouton avec ton emoji caddie !
    view = View()
    button = Button(
        label="Go to Website", 
        style=discord.ButtonStyle.link,
        url="https://voidmrkt.mysellauth.com/", 
        emoji=discord.PartialEmoji.from_str("<:cart:1481081418476945582>")
    )
    view.add_item(button)

    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Website embed deployed successfully!", ephemeral=True)

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
