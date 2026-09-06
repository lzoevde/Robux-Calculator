import os
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

bot_config = {"rbx1": 1000, "rbx2": 1000}
user_rates = {}


def get_panel_embed():
    r1 = bot_config["rbx1"]
    r2 = bot_config["rbx2"]
    return discord.Embed(
        title="💎 로벅스 효율 계산기",
        description=(
            f"• 1번 조건: 1만원당 {r1:,} R\n• 2번 조건: 1.5만원당 {r2:,} R"
        ),
        color=discord.Color.blue(),
    )


class DirectInputModal(discord.ui.Modal, title="직접 입력"):
    amount = discord.ui.TextInput(label="로벅스 또는 원화", placeholder="24000")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True, ephemeral=True)
            val = int(self.amount.value.replace("R", "").replace(",", "").strip())
            r1, r2 = bot_config["rbx1"], bot_config["rbx2"]
            c1, c2 = (val / r1) * 10000, (val / r2) * 15000
            await interaction.followup.send(
                f"목표 {val}R -> 1번: {c1:,.0f}원 / 2번: {c2:,.0f}원", ephemeral=True
            )
        except:
            await interaction.followup.send("❌ 숫자를 올바르게 입력하세요!", ephemeral=True)


class CalculatorView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="500 R", style=discord.ButtonStyle.secondary)
    async def b500(self, interaction: discord.Interaction, button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        r1, r2 = bot_config["rbx1"], bot_config["rbx2"]
        await interaction.followup.send(
            f"500R 필요금액 -> 1번: {(500/r1)*10000:,.0f}원 / 2번: {(500/r2)*15000:,.0f}원", 
            ephemeral=True
        )

    @discord.ui.button(label="직접 입력", style=discord.ButtonStyle.success)
    async def bdir(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(DirectInputModal())


@bot.tree.command(name="setrate", description="1만원당 로벅스 값을 설정합니다.")
async def set_rate(interaction: discord.Interaction, amount: int):
    user_id = interaction.user.id
    user_rates[user_id] = amount
    await interaction.response.send_message(
        f"✅ 환율 설정 완료!\n1만원 = {amount:,}R\n(30% 수수료 적용됨)",
        ephemeral=True
    )


@bot.tree.command(name="rcalc", description="로벅스를 원화로 변환합니다.")
async def r_calculate(interaction: discord.Interaction, rbx: int):
    user_id = interaction.user.id
    
    if user_id not in user_rates:
        await interaction.response.send_message(
            "❌ 먼저 `/setrate`으로 환율을 설정하세요!\n예: `/setrate 1300`",
            ephemeral=True
        )
        return
    
    rate = user_rates[user_id]
    won = (rbx / rate) * 10000
    
    await interaction.response.send_message(
        f"💎 {rbx:,}R = {won:,.0f}원\n(환율: 1만원당 {rate:,}R)",
        ephemeral=True
    )


@bot.tree.command(name="woncalc", description="원화를 로벅스로 변환합니다. (30% 수수료 적용)")
async def won_calculate(interaction: discord.Interaction, won: int):
    user_id = interaction.user.id
    
    if user_id not in user_rates:
        await interaction.response.send_message(
            "❌ 먼저 `/setrate`으로 환율을 설정하세요!\n예: `/setrate 1300`",
            ephemeral=True
        )
        return
    
    rate = user_rates[user_id]
    rbx_before = (won / 10000) * rate
    rbx_after = rbx_before * 0.7
    fee = rbx_before - rbx_after
    
    await interaction.response.send_message(
        f"💰 **거래 정보**\n"
        f"고객 지불: {won:,}원\n"
        f"제공 R: {rbx_after:,.0f}R\n"
        f"┣ 원가: {rbx_before:,.0f}R\n"
        f"┗ 수수료(30%): {fee:,.0f}R",
        ephemeral=True
    )


@bot.event
async def on_ready():
    print(f"✅ 로그인: {bot.user}")
    synced = await bot.tree.sync()
    print(f"✅ 명령어: {len(synced)}개")


@bot.tree.command(name="calculator", description="계산 패널을 띄웁니다.")
async def panel(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await interaction.followup.send(embed=get_panel_embed(), view=CalculatorView())


bot.run(os.environ.get("DISCORD_TOKEN"))
