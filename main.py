import os
import io
import aiohttp
import discord
from discord.ext import commands

# Intents 설정
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# 데이터 저장용 딕셔너리들
user_rates = {}        # 로벅스 환율
user_token_rates = {}  # 블레이드볼 토큰 환율
deathball_tiers = {}   # 데스볼 티어/순위 데이터


@bot.event
async def on_ready():
    print(f"✅ 로그인 성공: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ 슬래시 명령어 총 {len(synced)}개 동기화 완료")
    except Exception as e:
        print(f"❌ 명령어 동기화 실패: {e}")


# ==========================================
# 1. 뷰(버튼) 클래스 모음
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
class RateModal(discord.ui.Modal, title="💎 로벅스 환율 설정"):
    rate = discord.ui.TextInput(label="1만원당 로벅스", placeholder="예: 1300")
    async def on_submit(self, interaction: discord.Interaction):
        user_rates[interaction.user.id] = int(self.rate.value.replace(",", "").strip())
        await interaction.response.send_message("✅ 로벅스 환율이 성공적으로 설정되었습니다!", ephemeral=True)

class WonModal(discord.ui.Modal, title="💰 원화 → 로벅스 비교 계산"):
    won = discord.ui.TextInput(label="원화 금액", placeholder="예: 50000")
    async def on_submit(self, interaction: discord.Interaction):
        won_val = int(self.won.value.replace(",", "").strip())
        rate = user_rates.get(interaction.user.id, 1300)
        
        tab_rbx = (won_val / 10000) * rate * 0.7
        official_rbx = won_val * (1000 / 15000)
        diff_rbx = tab_rbx - official_rbx
        percent_diff = ((tab_rbx - official_rbx) / official_rbx) * 100 if official_rbx > 0 else 0
        
        msg = (
            f"💰 **입력 금액: {won_val:,}원**\n\n"
            f"📌 **공식 홈페이지 구매 시:** 약 `{official_rbx:,.0f}R`\n"
            f"🚀 **현재 탭 방식(환율 적용):** 수수료 반영 후 **`{tab_rbx:,.0f}R`**\n\n"
            f"✨ **비교 결과:** 공홈보다 **`{diff_rbx:+,.0f}R`** (`{percent_diff:+.1f}%`) 더 이득입니다!"
        )
        await interaction.response.send_message(msg, ephemeral=True)

class RbxModal(discord.ui.Modal, title="💎 로벅스 → 원화 계산"):
    rbx = discord.ui.TextInput(label="로벅스 금액", placeholder="예: 130000")
    async def on_submit(self, interaction: discord.Interaction):
        rate = user_rates.get(interaction.user.id, 1300)
        won = (int(self.rbx.value.replace(",", "").strip()) / rate) * 10000
        await interaction.response.send_message(f"💵 환전 예상 원화: **{won:,.0f}원**", ephemeral=True)

class TokenRateModal(discord.ui.Modal, title="⚔️ 토큰 환율 설정"):
    rate = discord.ui.TextInput(label="1,000 토큰당 가격 (원)", placeholder="예: 5000")
    async def on_submit(self, interaction: discord.Interaction):
        user_token_rates[interaction.user.id] = int(self.rate.value.replace(",", "").strip())
        await interaction.response.send_message("✅ 토큰 환율이 성공적으로 설정되었습니다!", ephemeral=True)

class WonToTokenModal(discord.ui.Modal, title="💰 원화 → 토큰 계산"):
    won = discord.ui.TextInput(label="사용할 원화 금액", placeholder="예: 10000")
    async def on_submit(self, interaction: discord.Interaction):
        rate = user_token_rates.get(interaction.user.id, 5000)
        tokens = (int(self.won.value.replace(",", "").strip()) / rate) * 1000
        await interaction.response.send_message(f"💰 획득 가능 토큰: **{tokens:,.0f} T**", ephemeral=True)

class TokenToWonModal(discord.ui.Modal, title="⚔️ 토큰 → 원화 계산"):
    tokens = discord.ui.TextInput(label="계산할 토큰 수량", placeholder="예: 5000")
    async def on_submit(self, interaction: discord.Interaction):
        rate = user_token_rates.get(interaction.user.id, 5000)
        won = (int(self.tokens.value.replace(",", "").strip()) / 1000) * rate
        await interaction.response.send_message(f"🪙 필요 원화 금액: **{won:,.0f}원**", ephemeral=True)


# ==========================================
# 3. 봇 명령어 등록
# ==========================================
@bot.tree.command(name="로벅스메뉴", description="로벅스 환율 설정 및 계산기 메뉴를 불러옵니다.")
async def robux_menu(interaction: discord.Interaction):
    if interaction.channel.name != "robux-계산기":
        await interaction.response.send_message("❌ 이 명령어는 **#robux-계산기** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    embed = discord.Embed(
        title="💎 로벅스 환율 & 공홈 비교 계산기", 
        description="원하시는 버튼을 클릭하여 환율을 설정하거나 공홈 대비 이득을 계산해 보세요.", 
        color=discord.Color.from_rgb(88, 101, 242)
    )
    embed.set_footer(text="Robux Calculator System")
    await interaction.response.send_message(embed=embed, view=RobuxView())


@bot.tree.command(name="토큰메뉴", description="블레이드볼 토큰 시세 계산기 메뉴를 불러옵니다.")
async def token_menu(interaction: discord.Interaction):
    if interaction.channel.name != "블레이드볼-토큰계산":
        await interaction.response.send_message("❌ 이 명령어는 **#블레이드볼-토큰계산** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    embed = discord.Embed(
        title="⚔️ 블레이드 볼 토큰 계산기", 
        description="토큰 시세 환율 설정 및 원화 환산 메뉴입니다.", 
        color=discord.Color.from_rgb(254, 231, 92)
    )
    embed.set_footer(text="Blade Ball Token System")
    await interaction.response.send_message(embed=embed, view=TokenView())


@bot.tree.command(name="티어등록", description="순위 번호와 이름을 입력하면 해당 순위부터 아래로 한 칸씩 밀려납니다.")
async def register_tier(interaction: discord.Interaction, rank: int, name: str):
    if interaction.channel.name != "korean-deathball-tier":
        await interaction.response.send_message("❌ 이 명령어는 **#korean-deathball-tier** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    if rank < 1:
        await interaction.response.send_message("❌ 순위는 1 이상의 숫자로 입력해주세요!", ephemeral=True)
        return

    new_tiers = {}
    for r, current_name in deathball_tiers.items():
        if r >= rank:
            new_tiers[r + 1] = current_name
        else:
            new_tiers[r] = current_name

    new_tiers[rank] = name
    deathball_tiers.clear()
    deathball_tiers.update(new_tiers)

    await interaction.response.send_message(f"✅ **{rank}등**에 **{name}** 님이 등록되며, 하위 순위가 자동으로 밀려났습니다!", ephemeral=True)


@bot.tree.command(name="티어제거", description="입력한 순위의 사람을 제거하고 아래 순위들을 한 칸씩 앞으로 당깁니다.")
async def remove_tier(interaction: discord.Interaction, rank: int):
    if interaction.channel.name != "korean-deathball-tier":
        await interaction.response.send_message("❌ 이 명령어는 **#korean-deathball-tier** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    if rank not in deathball_tiers:
        await interaction.response.send_message(f"❌ **{rank}등**에 등록된 사용자가 없습니다!", ephemeral=True)
        return

    removed_name = deathball_tiers.pop(rank)
    
    new_tiers = {}
    for r, current_name in deathball_tiers.items():
        if r > rank:
            new_tiers[r - 1] = current_name
        else:
            new_tiers[r] = current_name

    deathball_tiers.clear()
    deathball_tiers.update(new_tiers)

    await interaction.response.send_message(f"🗑️ **{rank}등**({removed_name} 님)이 제거되었고, 하위 순위가 앞으로 당겨졌습니다!", ephemeral=True)


@bot.tree.command(name="티어초기화", description="등록된 모든 티어 순위 데이터를 초기화합니다.")
async def reset_tier(interaction: discord.Interaction):
    if interaction.channel.name != "korean-deathball-tier":
        await interaction.response.send_message("❌ 이 명령어는 **#korean-deathball-tier** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    deathball_tiers.clear()
    await interaction.response.send_message("⚠️ 모든 티어 순위표 데이터가 초기화되었습니다.", ephemeral=True)


@bot.tree.command(name="티어순위", description="세련된 디자인의 데스볼 티어 순위표를 보여줍니다.")
async def show_leaderboard(interaction: discord.Interaction):
    if interaction.channel.name != "korean-deathball-tier":
        await interaction.response.send_message("❌ 이 명령어는 **#korean-deathball-tier** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    if not deathball_tiers:
        await interaction.response.send_message("❌ 아직 등록된 순위 정보가 없습니다. `/티어등록` 명령어로 순위를 추가해보세요!", ephemeral=True)
        return

    sorted_ranks = sorted(deathball_tiers.keys())

    description = ""
    medals = ["🥇", "🥈", "🥉"]
    
    for rank in sorted_ranks:
        name = deathball_tiers.get(rank)
        if rank <= 3:
            rank_icon = medals[rank - 1]
        else:
            rank_icon = f"`[{rank:2d}]`"
            
        description += f"{rank_icon}  **{name}**\n"

    embed = discord.Embed(
        title="🏆 Korean Deathball Leaderboard",
        description=description,
        color=discord.Color.from_rgb(255, 69, 0)
    )
    embed.add_field(name="📊 총 등록 인원", value=f"**{len(deathball_tiers)}명** 참가 중", inline=False)
    embed.set_footer(text="Updated Live • Deathball Tier System")
    
    await interaction.response.send_message(embed=embed)


# ==========================================
# 4. 봇 프로필 이미지 & 이름 변경 명령어
# ==========================================
@bot.tree.command(name="이미지변경", description="이미지 링크(URL)를 입력하여 봇의 프로필 사진을 변경합니다.")
async def change_bot_avatar(interaction: discord.Interaction, image_url: str):
    await interaction.response.defer(ephemeral=True)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    await interaction.followup.send("❌ 이미지 링크에서 사진을 불러오지 못했습니다. 올바른 직링크인지 확인해주세요.", ephemeral=True)
                    return
                
                image_bytes = await resp.read()

        await bot.user.edit(avatar=image_bytes)
        await interaction.followup.send("✨ 성공적으로 봇의 프로필 이미지가 변경되었습니다!", ephemeral=True)

    except discord.HTTPException as e:
        await interaction.followup.send(f"❌ 이미지 변경 실패 (디스코드 제한): 너무 자주 변경했거나 지원하지 않는 형식입니다. ({e})", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ 오류가 발생했습니다: {e}", ephemeral=True)


@bot.tree.command(name="봇이름변경", description="명령어로 봇의 이름을 변경합니다.")
async def change_bot_name(interaction: discord.Interaction, new_name: str):
    await interaction.response.defer(ephemeral=True)

    try:
        await bot.user.edit(username=new_name)
        await interaction.followup.send(f"✨ 성공적으로 봇의 이름이 **'{new_name}'**(으)로 변경되었습니다!", ephemeral=True)

    except discord.HTTPException as e:
        await interaction.followup.send(f"❌ 이름 변경 실패: 디스코드에서 이름을 너무 자주 바꾸면 제한될 수 있습니다. ({e})", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ 오류가 발생했습니다: {e}", ephemeral=True)


# 봇 실행
token = os.environ.get("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("❌ DISCORD_TOKEN이 설정되지 않았습니다!")
