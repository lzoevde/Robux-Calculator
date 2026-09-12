import os
import random
import aiohttp
import discord
from discord.ext import commands
from datetime import datetime

# Intents 설정
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# 데이터 저장용 딕셔너리들
user_rates = {}          # 로벅스 환율
user_token_rates = {}    # 블레이드볼 토큰 환율
deathball_tiers = {}     # 한국 데스볼 티어 데이터
japanese_tiers = {}      # 일본 유저 티어 데이터


@bot.event
async def on_ready():
    print(f"✅ 로그인 성공: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ 슬래시 명령어 총 {len(synced)}개 동기화 완료")
    except Exception as e:
        print(f"❌ 명령어 동기화 실패: {e}")


# ==========================================
# 🛠️ 로블록스 통합 API: 닉네임 검색, 아바타, 생성일, 접속 게임, 닉네임 이력
# ==========================================
async def get_roblox_user_info(username: str):
    async with aiohttp.ClientSession() as session:
        # 1. 닉네임으로 User ID 검색
        url_search = "https://users.roblox.com/v1/usernames/users"
        payload = {"usernames": [username], "excludeBannedUsers": True}
        
        async with session.post(url_search, json=payload) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            if not data.get("data"):
                return None
            
            user_info = data["data"][0]
            user_id = user_info["id"]
            real_name = user_info["name"]
            display_name = user_info.get("displayName", real_name)

        # 2. 유저 상세 정보 (계정 생성일 등) 가져오기
        url_detail = f"https://users.roblox.com/v1/users/{user_id}"
        created_at_str = "정보 없음"
        account_age_days = 0
        async with session.get(url_detail) as resp:
            if resp.status == 200:
                detail_data = await resp.json()
                raw_date = detail_data.get("created")
                if raw_date:
                    dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                    created_at_str = dt.strftime("%Y년 %m월 %d일")
                    account_age_days = (datetime.now(dt.tzinfo) - dt).days

        # 3. 아바타 썸네일 가져오기
        url_avatar = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=420x420&format=Png&isCircular=false"
        avatar_url = None
        async with session.get(url_avatar) as resp:
            if resp.status == 200:
                avatar_data = await resp.json()
                if avatar_data.get("data"):
                    avatar_url = avatar_data["data"][0]["imageUrl"]

        # 4. 현재 접속 중인 게임(플레이 상태) 가져오기
        url_presence = "https://presence.roblox.com/v1/presence/users"
        presence_payload = {"userIds": [user_id]}
        current_game = "offline (접속 중 아님)"
        async with session.post(url_presence, json=presence_payload) as resp:
            if resp.status == 200:
                p_data = await resp.json()
                if p_data.get("presenceNotifications") or p_data.get("userPresences"):
                    presences = p_data.get("userPresences", [])
                    if presences:
                        p_type = presences[0].get("userPresenceType")
                        if p_type == 2:
                            game_name = presences[0].get("lastLocation", "알 수 없는 장소")
                            current_game = f"🎮 플레이 중: {game_name}"
                        elif p_type == 1:
                            current_game = "🟢 온라인 (로비/웹 접속 중)"
                        else:
                            current_game = "⚪ 오프라인"

        # 5. 이전 닉네임(변경 이력) 가져오기 (최대 10개)
        url_history = f"https://users.roblox.com/v1/users/{user_id}/username-history?limit=10&sortOrder=Desc"
        past_names = []
        async with session.get(url_history) as resp:
            if resp.status == 200:
                h_data = await resp.json()
                items = h_data.get("data", [])
                if items:
                    past_names = [item.get("name") for item in items[:10]]

        profile_url = f"https://www.roblox.com/users/{user_id}/profile"

        return {
            "real_name": real_name,
            "display_name": display_name,
            "profile_url": profile_url,
            "avatar_url": avatar_url,
            "created_at": created_at_str,
            "age_days": account_age_days,
            "current_game": current_game,
            "past_names": past_names
        }


# ==========================================
# 1. 뷰(버튼) 및 모달 클래스 모음
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


class RobloxProfileView(discord.ui.View):
    def __init__(self, profile_url: str):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="🔗 로블록스 공식 프로필 바로가기", style=discord.ButtonStyle.link, url=profile_url))


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
# 2. 채널 명령어 모음
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


# --- #bot-ping 채널 전용 핑 명령어 ---
@bot.tree.command(name="핑", description="봇의 실시간 반응 속도와 상태를 확인합니다.")
async def bot_ping(interaction: discord.Interaction):
    if interaction.channel.name != "bot-ping":
        await interaction.response.send_message("❌ 이 명령어는 **#bot-ping** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    latency = round(bot.latency * 1000)
    
    if latency < 100:
        status_text = "🟢 매우 쾌적함"
        color = discord.Color.green()
    elif latency < 250:
        status_text = "🟡 보통"
        color = discord.Color.gold()
    else:
        status_text = "🔴 지연 발생 중"
        color = discord.Color.red()

    embed = discord.Embed(
        title="🏓 Pong! Bot Status",
        color=color
    )
    embed.add_field(name="⚡ 봇 응답 속도 (Latency)", value=f"`{latency}ms`", inline=True)
    embed.add_field(name="📊 네트워크 상태", value=status_text, inline=True)
    embed.set_footer(text="Roblox Bot Ping System")

    await interaction.response.send_message(embed=embed)


# --- #게임-내전 채널 전용 내전 팀 편성 명령어 ---
@bot.tree.command(name="내전팀랜덤", description="참가자 닉네임을 콤마(,)로 구분해 입력하면 2개 팀으로 무작위 배정합니다.")
async def random_teams(interaction: discord.Interaction, players: str):
    if interaction.channel.name != "게임-내전":
        await interaction.response.send_message("❌ 이 명령어는 **#게임-내전** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    # 쉼표(,) 기준으로 유저 분리 후 공백 제거
    player_list = [p.strip() for p in players.split(",") if p.strip()]

    if len(player_list) < 2:
        await interaction.response.send_message("❌ 최소 2명 이상의 닉네임을 콤마(,)로 구분해서 입력해주세요! (예: `제드,에이즈,디코,로블록스`)", ephemeral=True)
        return

    # 무작위 섞기
    random.shuffle(player_list)
    mid = len(player_list) // 2
    team_a = player_list[:mid]
    team_b = player_list[mid:]

    embed = discord.Embed(
        title="⚔️ 데스볼 내전 랜덤 팀 편성 대진표",
        description=f"총 참가 인원: **{len(player_list)}명**",
        color=discord.Color.from_rgb(114, 137, 218)
    )
    embed.add_field(name="🔵 [ A 팀 ]", value="\n".join([f"• `{p}`" for p in team_a]) if team_a else "없음", inline=True)
    embed.add_field(name="🔴 [ B 팀 ]", value="\n".join([f"• `{p}`" for p in team_b]) if team_b else "없음", inline=True)
    embed.set_footer(text="Deathball Custom Match System")

    await interaction.response.send_message(embed=embed)


# --- #roblox-id 채널 전용 종합 조회 기능 ---
@bot.tree.command(name="로블록스조회", description="로블록스 유저의 프로필, 생성일, 접속 상태, 닉네임 이력을 조회합니다.")
async def roblox_lookup(interaction: discord.Interaction, roblox_username: str):
    if interaction.channel.name != "roblox-id":
        await interaction.response.send_message("❌ 이 명령어는 **#roblox-id** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    await interaction.response.defer()

    info = await get_roblox_user_info(roblox_username)
    if not info:
        await interaction.followup.send(f"❌ '{roblox_username}'은(는) 존재하지 않는 로블록스 유저이거나 탈퇴한 계정입니다.", ephemeral=True)
        return

    past_str = ", ".join([f"`{name}`" for name in info["past_names"]]) if info["past_names"] else "없음"

    embed = discord.Embed(
        title=f"🔍 로블록스 유저 프로필: {info['real_name']}",
        color=discord.Color.from_rgb(0, 162, 255)
    )
    embed.add_field(name="👤 표시 이름", value=f"`{info['display_name']}`", inline=True)
    embed.add_field(name="📅 계정 생성일", value=f"{info['created_at']}\n(가입한 지 **{info['age_days']:,}일**째)", inline=True)
    embed.add_field(name="🟢 접속 상태", value=info['current_game'], inline=False)
    embed.add_field(name="🔤 이전 닉네임 이력", value=past_str, inline=False)

    if info['avatar_url']:
        embed.set_thumbnail(url=info['avatar_url'])
    
    embed.set_footer(text="Roblox Advanced Lookup System")

    view = RobloxProfileView(info['profile_url'])
    await interaction.followup.send(embed=embed, view=view)


# --- 한국 데스볼 티어 채널 (#korean-deathball-tier) ---
@bot.tree.command(name="티어등록", description="로블록스 닉네임을 입력하여 한국 티어에 등록합니다.")
async def register_tier(interaction: discord.Interaction, rank: int, roblox_username: str):
    if interaction.channel.name != "korean-deathball-tier":
        await interaction.response.send_message("❌ 이 명령어는 **#korean-deathball-tier** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    if rank < 1:
        await interaction.response.send_message("❌ 순위는 1 이상의 숫자로 입력해주세요!", ephemeral=True)
        return

    await interaction.defer()

    info = await get_roblox_user_info(roblox_username)
    if not info:
        await interaction.followup.send(f"❌ '{roblox_username}'은(는) 존재하지 않는 로블록스 유저입니다.", ephemeral=True)
        return

    user_display = f"{info['real_name']} (@{info['display_name']})"

    new_tiers = {}
    for r, current_name in deathball_tiers.items():
        if r >= rank:
            new_tiers[r + 1] = current_name
        else:
            new_tiers[r] = current_name

    new_tiers[rank] = user_display
    deathball_tiers.clear()
    deathball_tiers.update(new_tiers)

    sorted_ranks = sorted(deathball_tiers.keys())
    description = f"✅ **{rank}등**에 **{user_display}** 님이 등록되었습니다!\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for r in sorted_ranks:
        n = deathball_tiers.get(r)
        rank_icon = medals[r - 1] if r <= 3 else f"`[{r:2d}]`"
        description += f"{rank_icon}  **{n}**\n"

    embed = discord.Embed(
        title="🏆 Korean Deathball Leaderboard",
        description=description,
        color=discord.Color.from_rgb(255, 69, 0)
    )
    if info['avatar_url']:
        embed.set_thumbnail(url=info['avatar_url'])
    embed.add_field(name="📊 총 등록 인원", value=f"**{len(deathball_tiers)}명** 참가 중", inline=False)
    embed.set_footer(text="Updated Live • Korean Tier System")

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="티어제거", description="한국 데스볼 지정 순위의 사람을 제거합니다.")
async def remove_tier(interaction: discord.Interaction, rank: int):
    if interaction.channel.name != "korean-deathball-tier":
        await interaction.response.send_message("❌ 이 명령어는 **#korean-deathball-tier** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    if rank not in deathball_tiers:
        await interaction.response.send_message(f"❌ 한국 티어 **{rank}등**에 등록된 사용자가 없습니다!", ephemeral=True)
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

    sorted_ranks = sorted(deathball_tiers.keys())
    description = f"🗑️ **{rank}등**({removed_name})이 제거되었습니다!\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for r in sorted_ranks:
        n = deathball_tiers.get(r)
        rank_icon = medals[r - 1] if r <= 3 else f"`[{r:2d}]`"
        description += f"{rank_icon}  **{n}**\n"

    embed = discord.Embed(
        title="🏆 Korean Deathball Leaderboard",
        description=description,
        color=discord.Color.from_rgb(255, 69, 0)
    )
    embed.add_field(name="📊 총 등록 인원", value=f"**{len(deathball_tiers)}명** 참가 중", inline=False)
    embed.set_footer(text="Updated Live • Korean Tier System")

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="티어초기화", description="한국 데스볼 티어 순위표 데이터를 초기화합니다.")
async def reset_tier(interaction: discord.Interaction):
    if interaction.channel.name != "korean-deathball-tier":
        await interaction.response.send_message("❌ 이 명령어는 **#korean-deathball-tier** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    deathball_tiers.clear()
    await interaction.response.send_message("⚠️ 한국 데스볼 티어 순위표 데이터가 초기화되었습니다.", ephemeral=True)


@bot.tree.command(name="티어순위", description="한국 데스볼 티어 순위표를 보여줍니다.")
async def show_leaderboard(interaction: discord.Interaction):
    if interaction.channel.name != "korean-deathball-tier":
        await interaction.response.send_message("❌ 이 명령어는 **#korean-deathball-tier** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    if not deathball_tiers:
        await interaction.response.send_message("❌ 아직 등록된 한국 순위 정보가 없습니다.", ephemeral=True)
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
    embed.set_footer(text="Updated Live • Korean Tier System")
    
    await interaction.response.send_message(embed=embed)


# --- 일본 유저 티어 채널 (#japanese-deathball-tier) ---
@bot.tree.command(name="일본유저티어등록", description="로블록스 닉네임을 입력하여 일본 유저 티어에 등록합니다.")
async def register_jp_tier(interaction: discord.Interaction, rank: int, roblox_username: str):
    if interaction.channel.name != "japanese-deathball-tier":
        await interaction.response.send_message("❌ 이 명령어는 **#japanese-deathball-tier** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    if rank < 1:
        await interaction.response.send_message("❌ 순위는 1 이상의 숫자로 입력해주세요!", ephemeral=True)
        return

    await interaction.defer()

    info = await get_roblox_user_info(roblox_username)
    if not info:
        await interaction.followup.send(f"❌ '{roblox_username}'은(는) 존재하지 않는 로블록스 유저입니다.", ephemeral=True)
        return

    user_display = f"{info['real_name']} (@{info['display_name']})"

    new_tiers = {}
    for r, current_name in japanese_tiers.items():
        if r >= rank:
            new_tiers[r + 1] = current_name
        else:
            new_tiers[r] = current_name

    new_tiers[rank] = user_display
    japanese_tiers.clear()
    japanese_tiers.update(new_tiers)

    sorted_ranks = sorted(japanese_tiers.keys())
    description = f"✅ 일본 유저 **{rank}등**에 **{user_display}** 님이 등록되었습니다!\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for r in sorted_ranks:
        n = japanese_tiers.get(r)
        rank_icon = medals[r - 1] if r <= 3 else f"`[{r:2d}]`"
        description += f"{rank_icon}  **{n}**\n"

    embed = discord.Embed(
        title="🏆 Japanese User Deathball Leaderboard",
        description=description,
        color=discord.Color.from_rgb(255, 105, 180)
    )
    if info['avatar_url']:
        embed.set_thumbnail(url=info['avatar_url'])
    embed.add_field(name="📊 총 등록 인원", value=f"**{len(japanese_tiers)}명** 참가 중", inline=False)
    embed.set_footer(text="Updated Live • Japanese User Tier System")

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="일본유저티어제거", description="일본 데스볼 유저를 제거합니다.")
async def remove_jp_tier(interaction: discord.Interaction, rank: int):
    if interaction.channel.name != "japanese-deathball-tier":
        await interaction.response.send_message("❌ 이 명령어는 **#japanese-deathball-tier** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    if rank not in japanese_tiers:
        await interaction.response.send_message(f"❌ 일본 유저 티어 **{rank}등**에 등록된 사용자가 없습니다!", ephemeral=True)
        return

    removed_name = japanese_tiers.pop(rank)
    
    new_tiers = {}
    for r, current_name in japanese_tiers.items():
        if r > rank:
            new_tiers[r - 1] = current_name
        else:
            new_tiers[r] = current_name

    japanese_tiers.clear()
    japanese_tiers.update(new_tiers)

    sorted_ranks = sorted(japanese_tiers.keys())
    description = f"🗑️ 일본 유저 **{rank}등**({removed_name})이 제거되었습니다!\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for r in sorted_ranks:
        n = japanese_tiers.get(r)
        rank_icon = medals[r - 1] if r <= 3 else f"`[{r:2d}]`"
        description += f"{rank_icon}  **{n}**\n"

    embed = discord.Embed(
        title="🏆 Japanese User Deathball Leaderboard",
        description=description,
        color=discord.Color.from_rgb(255, 105, 180)
    )
    embed.add_field(name="📊 총 등록 인원", value=f"**{len(japanese_tiers)}명** 참가 중", inline=False)
    embed.set_footer(text="Updated Live • Japanese User Tier System")

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="일본유저티어초기화", description="일본 데스볼 유저 티어 순위표 데이터를 초기화합니다.")
async def reset_jp_tier(interaction: discord.Interaction):
    if interaction.channel.name != "japanese-deathball-tier":
        await interaction.response.send_message("❌ 이 명령어는 **#japanese-deathball-tier** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    japanese_tiers.clear()
    await interaction.response.send_message("⚠️ 일본 유저 티어 순위표 데이터가 초기화되었습니다.", ephemeral=True)


@bot.tree.command(name="일본유저티어순위", description="일본 데스볼 유저 티어 순위표를 보여줍니다.")
async def show_jp_leaderboard(interaction: discord.Interaction):
    if interaction.channel.name != "japanese-deathball-tier":
        await interaction.response.send_message("❌ 이 명령어는 **#japanese-deathball-tier** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    if not japanese_tiers:
        await interaction.response.send_message("❌ 아직 등록된 일본 유저 순위 정보가 없습니다.", ephemeral=True)
        return

    sorted_ranks = sorted(japanese_tiers.keys())
    description = ""
    medals = ["🥇", "🥈", "🥉"]
    
    for rank in sorted_ranks:
        name = japanese_tiers.get(rank)
        if rank <= 3:
            rank_icon = medals[rank - 1]
        else:
            rank_icon = f"`[{rank:2d}]`"
        description += f"{rank_icon}  **{name}**\n"

    embed = discord.Embed(
        title="🏆 Japanese User Deathball Leaderboard",
        description=description,
        color=discord.Color.from_rgb(255, 105, 180)
    )
    embed.add_field(name="📊 총 등록 인원", value=f"**{len(japanese_tiers)}명** 참가 중", inline=False)
    embed.set_footer(text="Updated Live • Japanese User Tier System")
    
    await interaction.response.send_message(embed=embed)


# ==========================================
# 3. 봇 프로필 이미지 & 이름 변경 명령어
# ==========================================
@bot.tree.command(name="이미지변경", description="이미지 링크(URL)를 입력하여 봇의 프로필 사진을 변경합니다.")
async def change_bot_avatar(interaction: discord.Interaction, image_url: str):
    await interaction.response.defer(ephemeral=True)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    await interaction.followup.send("❌ 이미지 링크에서 사진을 불러오지 못했습니다.", ephemeral=True)
                    return
                image_bytes = await resp.read()

        await bot.user.edit(avatar=image_bytes)
        await interaction.followup.send("✨ 성공적으로 봇의 프로필 이미지가 변경되었습니다!", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"❌ 오류 발생: {e}", ephemeral=True)


@bot.tree.command(name="봇이름변경", description="명령어로 봇의 이름을 변경합니다.")
async def change_bot_name(interaction: discord.Interaction, new_name: str):
    await interaction.response.defer(ephemeral=True)

    try:
        await bot.user.edit(username=new_name)
        await interaction.followup.send(f"✨ 성공적으로 봇의 이름이 **'{new_name}'**(으)로 변경되었습니다!", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"❌ 오류 발생: {e}", ephemeral=True)


# 봇 실행
token = os.environ.get("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("❌ DISCORD_TOKEN이 설정되지 않았습니다!")
