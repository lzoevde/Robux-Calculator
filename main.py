import os
import discord
from discord.ext import commands

# Intents 설정
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# 데이터 저장용 딕셔너리들
user_rates = {}        # 로벅스 환율
user_token_rates = {}  # 블레이드볼 토큰 환율
deathball_tiers = {}   # 데스볼 티어/점수 데이터


@bot.event
async def on_ready():
    print(f"✅ 로그인 성공: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ 슬래시 명령어 총 {len(synced)}개 동기화 완료")
    except Exception as e:
        print(f"❌ 명령어 동기화 실패: {e}")


# ==========================================
# 1. 뷰(버튼) 클래스 모음 (전역으로 분리하여 응답 오류 방지)
# ==========================================
class RobuxView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="환율 설정", style=discord.ButtonStyle.primary, custom_id="robux_set_rate")
    async def set_rate_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RateModal())
    
    @discord.ui.button(label="원화→로벅스", style=discord.ButtonStyle.success, custom_id="robux_won_to_rbx")
    async def won_to_rbx(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WonModal())
    
    @discord.ui.button(label="로벅스→원화", style=discord.ButtonStyle.danger, custom_id="robux_rbx_to_won")
    async def rbx_to_won(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RbxModal())
    
    @discord.ui.button(label="내 환율 확인", style=discord.ButtonStyle.secondary, custom_id="robux_check_rate")
    async def check_rate(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id in user_rates:
            await interaction.response.send_message(f"현재 로벅스 환율: 1만원당 **{user_rates[user_id]:,}R**", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 환율을 설정하지 않았습니다.\n'환율 설정' 버튼을 클릭해주세요.", ephemeral=True)


class TokenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="토큰 환율 설정", style=discord.ButtonStyle.primary, custom_id="token_set_rate")
    async def set_token_rate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TokenRateModal())
    
    @discord.ui.button(label="원화 → 토큰", style=discord.ButtonStyle.success, custom_id="token_won_to_token")
    async def won_to_token(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WonToTokenModal())
    
    @discord.ui.button(label="토큰 → 원화", style=discord.ButtonStyle.danger, custom_id="token_token_to_won")
    async def token_to_won(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TokenToWonModal())
    
    @discord.ui.button(label="내 토큰 환율 확인", style=discord.ButtonStyle.secondary, custom_id="token_check_rate")
    async def check_token_rate(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id in user_token_rates:
            await interaction.response.send_message(f"현재 설정된 토큰 환율: **1,000 토큰당 {user_token_rates[user_id]:,}원**", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 아직 토큰 환율을 설정하지 않았습니다.\n'토큰 환율 설정' 버튼을 클릭해주세요.", ephemeral=True)


# ==========================================
# 2. 모달(팝업창) 클래스 모음
# ==========================================
class RateModal(discord.ui.Modal, title="로벅스 환율 설정"):
    rate = discord.ui.TextInput(label="1만원당 로벅스", placeholder="예: 1300")
    async def on_submit(self, interaction: discord.Interaction):
        user_rates[interaction.user.id] = int(self.rate.value.replace(",", "").strip())
        await interaction.response.send_message("✅ 로벅스 환율 설정 완료!", ephemeral=True)

class WonModal(discord.ui.Modal, title="원화 → 로벅스"):
    won = discord.ui.TextInput(label="원화 금액", placeholder="예: 100000")
    async def on_submit(self, interaction: discord.Interaction):
        rate = user_rates.get(interaction.user.id, 1300)
        rbx = (int(self.won.value.replace(",", "").strip()) / 10000) * rate * 0.7
        await interaction.response.send_message(f"💰 제공 R (수수료 반영): **{rbx:,.0f}R**", ephemeral=True)

class RbxModal(discord.ui.Modal, title="로벅스 → 원화"):
    rbx = discord.ui.TextInput(label="로벅스 금액", placeholder="예: 130000")
    async def on_submit(self, interaction: discord.Interaction):
        rate = user_rates.get(interaction.user.id, 1300)
        won = (int(self.rbx.value.replace(",", "").strip()) / rate) * 10000
        await interaction.response.send_message(f"💎 환전 원화: **{won:,.0f}원**", ephemeral=True)

class TokenRateModal(discord.ui.Modal, title="토큰 환율 설정"):
    rate = discord.ui.TextInput(label="1,000 토큰당 가격 (원)", placeholder="예: 5000")
    async def on_submit(self, interaction: discord.Interaction):
        user_token_rates[interaction.user.id] = int(self.rate.value.replace(",", "").strip())
        await interaction.response.send_message("✅ 토큰 환율 설정 완료!", ephemeral=True)

class WonToTokenModal(discord.ui.Modal, title="원화 → 토큰 계산"):
    won = discord.ui.TextInput(label="사용할 원화 금액", placeholder="예: 10000")
    async def on_submit(self, interaction: discord.Interaction):
        rate = user_token_rates.get(interaction.user.id, 5000)
        tokens = (int(self.won.value.replace(",", "").strip()) / rate) * 1000
        await interaction.response.send_message(f"💰 받는 토큰: **{tokens:,.0f} T**", ephemeral=True)

class TokenToWonModal(discord.ui.Modal, title="토큰 → 원화 계산"):
    tokens = discord.ui.TextInput(label="계산할 토큰 수량", placeholder="예: 5000")
    async def on_submit(self, interaction: discord.Interaction):
        rate = user_token_rates.get(interaction.user.id, 5000)
        won = (int(self.tokens.value.replace(",", "").strip()) / 1000) * rate
        await interaction.response.send_message(f"🪙 필요한 원화: **{won:,.0f}원**", ephemeral=True)


# ==========================================
# 3. 봇 명령어 등록
# ==========================================
@bot.tree.command(name="로벅스메뉴", description="로벅스 계산기 메뉴 (#robux-계산기 전용)")
async def robux_menu(interaction: discord.Interaction):
    if interaction.channel.name != "robux-계산기":
        await interaction.response.send_message("❌ 이 명령어는 **#robux-계산기** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    embed = discord.Embed(title="💎 로벅스 계산기", description="로벅스 환율 설정 및 환산 메뉴입니다.", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, view=RobuxView())


@bot.tree.command(name="토큰메뉴", description="블레이드볼 토큰 계산기 메뉴 (#블레이드볼-토큰계산 전용)")
async def token_menu(interaction: discord.Interaction):
    if interaction.channel.name != "블레이드볼-토큰계산":
        await interaction.response.send_message("❌ 이 명령어는 **#블레이드볼-토큰계산** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    embed = discord.Embed(title="⚔️ 블레이드 볼 토큰 계산기", description="블레이드볼 토큰 시세 계산 메뉴입니다.", color=discord.Color.gold())
    await interaction.response.send_message(embed=embed, view=TokenView())


@bot.tree.command(name="티어등록", description="특정 유저의 점수/티어를 등록합니다. (#korean-deathball-tier 전용)")
@discord.app.commands.describe(user="점수를 등록할 유저", score="점수 또는 수치 (숫자)")
async def register_tier(interaction: discord.Interaction, user: discord.Member, score: int):
    if interaction.channel.name != "korean-deathball-tier":
        await interaction.response.send_message("❌ 이 명령어는 **#korean-deathball-tier** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    deathball_tiers[user.id] = {
        "name": user.display_name,
        "score": score
    }
    await interaction.response.send_message(f"✅ **{user.display_name}** 님의 점수가 **{score}점**으로 등록(갱신)되었습니다!", ephemeral=True)


@bot.tree.command(name="티어순위", description="데스볼 티어 순위표를 보여줍니다. (#korean-deathball-tier 전용)")
async def show_leaderboard(interaction: discord.Interaction):
    if interaction.channel.name != "korean-deathball-tier":
        await interaction.response.send_message("❌ 이 명령어는 **#korean-deathball-tier** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    if not deathball_tiers:
        await interaction.response.send_message("❌ 아직 등록된 티어/점수 정보가 없습니다. `/티어등록` 명령어로 먼저 등록해주세요!", ephemeral=True)
        return

    sorted_users = sorted(deathball_tiers.values(), key=lambda x: x["score"], reverse=True)

    description = ""
    medals = ["🥇", "🥈", "🥉"]
    
    for idx, data in enumerate(sorted_users, start=1):
        rank_icon = medals[idx - 1] if idx <= 3 else f"`{idx}.`"
        description += f"{rank_icon} **{data['name']}** — {data['score']}점\n"

    embed = discord.Embed(
        title="🏆 Korean Deathball Leaderboard",
        description=description,
        color=discord.Color.from_rgb(255, 69, 0)
    )
    
    await interaction.response.send_message(embed=embed)


# 봇 실행
token = os.environ.get("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("❌ DISCORD_TOKEN이 설정되지 않았습니다!")
