import os
import random
import aiohttp
import asyncio
import discord
from discord.ext import commands
from datetime import datetime

# Intents 설정
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# 데이터 저장용 딕셔너리 및 세트
user_rates = {}          # 로벅스 환율
user_token_rates = {}    # 블레이드볼 토큰 환율
deathball_tiers = {}     # 한국 데스볼 티어 순위표
matchup_participants = set() # 내전 참가자 명단

# 🗺️ 데스볼 맵 리스트
deathball_maps = ["클래식 아레나", "네온 시티", "볼케이노"]

# 전역 aiohttp 세션
http_session: aiohttp.ClientSession = None


@bot.event
async def on_ready():
    global http_session
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession()

    print(f"========================================")
    print(f"✅ 로그인 성공: {bot.user}")
    print(f"🚀 디스코드 봇이 정상적으로 가동되었습니다.")
    print(f"========================================")
    try:
        synced = await bot.tree.sync()
        print(f"✅ 슬래시 명령어 총 {len(synced)}개 동기화 완료")
    except Exception as e:
        print(f"❌ 명령어 동기화 실패: {e}")


# ==========================================
# 🛠️ 로블록스 프로필 조회 함수
# ==========================================
async def get_roblox_user_info(username: str):
    global http_session
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession()

    try:
        url_search = "https://users.roblox.com/v1/usernames/users"
        payload = {"usernames": [username], "excludeBannedUsers": True}
        
        async with http_session.post(url_search, json=payload) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            if not data.get("data"):
                return None
            
            user_info = data["data"][0]
            user_id = user_info["id"]
            real_name = user_info["name"]
            display_name = user_info.get("displayName", real_name)

        # 계정 생성일 및 가입 일수 실시간 계산 (매일 날짜가 자동으로 갱신됨)
        url_detail = f"https://users.roblox.com/v1/users/{user_id}"
        created_at_str = "정보 없음"
        account_age_days = 0
        async with http_session.get(url_detail) as resp:
            if resp.status == 200:
                detail_data = await resp.json()
                raw_date = detail_data.get("created")
                if raw_date:
                    dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                    created_at_str = dt.strftime("%Y년 %m월 %d일")
                    now_utc = datetime.now(dt.tzinfo)
                    account_age_days = (now_utc - dt).days

        # 📜 이전 닉네임 히스토리 조회
        url_history = f"https://users.roblox.com/v1/users/{user_id}/username-history"
        previous_names = []
        async with http_session.get(url_history) as resp:
            if resp.status == 200:
                history_data = await resp.json()
                for item in history_data.get("data", []):
                    prev_name = item.get("name")
                    if prev_name and prev_name not in previous_names:
                        previous_names.append(prev_name)

        # 아바타 이미지 조회
        url_avatar = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=420x420&format=Png&isCircular=false"
        avatar_url = None
        async with http_session.get(url_avatar) as resp:
            if resp.status == 200:
                avatar_data = await resp.json()
                if avatar_data.get("data"):
                    avatar_url = avatar_data["data"][0]["imageUrl"]

        profile_url = f"https://www.roblox.com/users/{user_id}/profile"

        return {
            "user_id": user_id,
            "real_name": real_name,
            "display_name": display_name,
            "profile_url": profile_url,
            "avatar_url": avatar_url,
            "created_at": created_at_str,
            "age_days": account_age_days,
            "previous_names": previous_names
        }
    except Exception as e:
        print(f"❌ Roblox API 오류: {e}")
        return None


async def get_latest_username_by_id(user_id: int):
    global http_session
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession()

    try:
        url_detail = f"https://users.roblox.com/v1/users/{user_id}"
        async with http_session.get(url_detail) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("name"), data.get("displayName")
    except Exception:
        pass
    return None, None


# ==========================================
# 🎨 UI 뷰 클래스 모음
# ==========================================
class RobuxView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="⚙️ 환율 설정", style=discord.ButtonStyle.primary, custom_id="robux_set_rate")
    async def set_rate_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RateModal())
    
    @discord.ui.button(label="💵 원화 ➔ 로벅스", style=discord.ButtonStyle.success, custom_id="robux_won_to_rbx")
    async def won_to_rbx(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WonModal())
    
    @discord.ui.button(label="💎 로벅스 ➔ 원화", style=discord.ButtonStyle.danger, custom_id="robux_rbx_to_won")
    async def rbx_to_won(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RbxModal())
    
    @discord.ui.button(label="📊 내 환율 확인", style=discord.ButtonStyle.secondary, custom_id="robux_check_rate")
    async def check_rate(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id in user_rates:
            await interaction.response.send_message(f"💡 현재 설정된 환율: 1만원당 **{user_rates[user_id]:,}R**", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 환율이 설정되지 않았습니다.\n**[⚙️ 환율 설정]** 버튼을 먼저 클릭해주세요!", ephemeral=True)


class TokenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="⚙️ 토큰 환율 설정", style=discord.ButtonStyle.primary, custom_id="token_set_rate")
    async def set_token_rate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TokenRateModal())
    
    @discord.ui.button(label="💵 원화 ➔ 토큰", style=discord.ButtonStyle.success, custom_id="token_won_to_token")
    async def won_to_token(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WonToTokenModal())
    
    @discord.ui.button(label="⚔️ 토큰 ➔ 원화", style=discord.ButtonStyle.danger, custom_id="token_token_to_won")
    async def token_to_won(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TokenToWonModal())
    
    @discord.ui.button(label="📊 내 토큰 환율 확인", style=discord.ButtonStyle.secondary, custom_id="token_check_rate")
    async def check_token_rate(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id in user_token_rates:
            await interaction.response.send_message(f"💡 현재 설정된 토큰 환율: **1,000 토큰당 {user_token_rates[user_id]:,}원**", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 토큰 환율이 설정되지 않았습니다.\n**[⚙️ 토큰 환율 설정]** 버튼을 먼저 클릭해주세요!", ephemeral=True)


class RobloxProfileView(discord.ui.View):
    def __init__(self, profile_url: str):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="🔗 로블록스 공식 프로필 바로가기", style=discord.ButtonStyle.link, url=profile_url))


class MatchupRegisterView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ 참가하기", style=discord.ButtonStyle.success, custom_id="matchup_join_btn")
    async def join_matchup(self, interaction: discord.Interaction, button: discord.ui.Button):
        matchup_participants.add(interaction.user.display_name)
        participants_list = "\n".join([f"• `{name}`" for name in matchup_participants]) if matchup_participants else "아직 참가자가 없습니다."
        
        embed = interaction.message.embeds[0]
        embed.clear_fields()
        embed.add_field(name=f"👥 실시간 참가 명단 ({len(matchup_participants)}명)", value=participants_list, inline=False)
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="❌ 참가 취소", style=discord.ButtonStyle.danger, custom_id="matchup_cancel_btn")
    async def cancel_matchup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.display_name in matchup_participants:
            matchup_participants.remove(interaction.user.display_name)
        participants_list = "\n".join([f"• `{name}`" for name in matchup_participants]) if matchup_participants else "아직 참가자가 없습니다."
        
        embed = interaction.message.embeds[0]
        embed.clear_fields()
        embed.add_field(name=f"👥 실시간 참가 명단 ({len(matchup_participants)}명)", value=participants_list, inline=False)
        await interaction.response.edit_message(embed=embed)


# --- 모달 클래스 모음 ---
class RateModal(discord.ui.Modal, title="💎 로벅스 환율 설정"):
    rate = discord.ui.TextInput(label="1만원당 로벅스 (숫자만 입력)", placeholder="예: 1300")
    async def on_submit(self, interaction: discord.Interaction):
        user_rates[interaction.user.id] = int(self.rate.value.replace(",", "").strip())
        await interaction.response.send_message("✅ 로벅스 환율이 성공적으로 저장되었습니다!", ephemeral=True)

class WonModal(discord.ui.Modal, title="💰 원화 ➔ 로벅스 계산기"):
    won = discord.ui.TextInput(label="원화 금액 (원)", placeholder="예: 50000")
    async def on_submit(self, interaction: discord.Interaction):
        won_val = int(self.won.value.replace(",", "").strip())
        rate = user_rates.get(interaction.user.id, 1300)
        tab_rbx = (won_val / 10000) * rate * 0.7
        official_rbx = won_val * (1000 / 15000)
        diff_rbx = tab_rbx - official_rbx
        percent_diff = ((tab_rbx - official_rbx) / official_rbx) * 100 if official_rbx > 0 else 0
        
        embed = discord.Embed(title="💰 로벅스 환전 비교 결과", color=discord.Color.blurple())
        embed.add_field(name="입력 금액", value=f"`{won_val:,}원`", inline=False)
        embed.add_field(name="📌 공식 홈페이지", value=f"`{official_rbx:,.0f}R`", inline=True)
        embed.add_field(name="🚀 적용 환율 방식", value=f"**`{tab_rbx:,.0f}R`**", inline=True)
        embed.add_field(name="✨ 효율 비교", value=f"공홈보다 **`{diff_rbx:+,.0f}R`** (`{percent_diff:+.1f}%`) 더 이득!", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class RbxModal(discord.ui.Modal, title="💎 로벅스 ➔ 원화 계산기"):
    rbx = discord.ui.TextInput(label="로벅스 수량 (R)", placeholder="예: 130000")
    async def on_submit(self, interaction: discord.Interaction):
        rate = user_rates.get(interaction.user.id, 1300)
        won = (int(self.rbx.value.replace(",", "").strip()) / rate) * 10000
        await interaction.response.send_message(f"💵 환전 예상 금액: **{won:,.0f}원**", ephemeral=True)

class TokenRateModal(discord.ui.Modal, title="⚔️ 토큰 환율 설정"):
    rate = discord.ui.TextInput(label="1,000 토큰당 가격 (원)", placeholder="예: 5000")
    async def on_submit(self, interaction: discord.Interaction):
        user_token_rates[interaction.user.id] = int(self.rate.value.replace(",", "").strip())
        await interaction.response.send_message("✅ 토큰 환율이 성공적으로 저장되었습니다!", ephemeral=True)

class WonToTokenModal(discord.ui.Modal, title="💰 원화 ➔ 토큰 계산기"):
    won = discord.ui.TextInput(label="사용할 원화 금액 (원)", placeholder="예: 10000")
    async def on_submit(self, interaction: discord.Interaction):
        rate = user_token_rates.get(interaction.user.id, 5000)
        tokens = (int(self.won.value.replace(",", "").strip()) / rate) * 1000
        await interaction.response.send_message(f"💰 획득 가능 토큰: **{tokens:,.0f} T**", ephemeral=True)

class TokenToWonModal(discord.ui.Modal, title="⚔️ 토큰 ➔ 원화 계산기"):
    tokens = discord.ui.TextInput(label="계산할 토큰 수량 (T)", placeholder="예: 5000")
    async def on_submit(self, interaction: discord.Interaction):
        rate = user_token_rates.get(interaction.user.id, 5000)
        won = (int(self.tokens.value.replace(",", "").strip()) / 1000) * rate
        await interaction.response.send_message(f"🪙 필요 원화 금액: **{won:,.0f}원**", ephemeral=True)


# ==========================================
# 🧹 일반 메시지 명령어 (청소 기능)
# ==========================================
@bot.command(name="청소")
async def clear_messages(ctx, amount: int = 10):
    try:
        await ctx.message.delete()
        deleted = await ctx.channel.purge(limit=amount)
        msg = await ctx.send(f"🧹 최근 메시지 **{len(deleted)}개**를 깨끗하게 청소했습니다!")
        await asyncio.sleep(3)
        await msg.delete()
    except Exception as e:
        await ctx.send(f"❌ 메시지를 삭제할 권한이 없거나 오류가 발생했습니다: {e}", delete_after=5)


# ==========================================
# 🎯 슬래시 명령어
# ==========================================
@bot.tree.command(name="로벅스메뉴", description="로벅스 환율 설정 및 계산기 패널을 불러옵니다.")
async def robux_menu(interaction: discord.Interaction):
    if interaction.channel.name != "robux-계산기":
        await interaction.response.send_message("❌ 이 명령어는 **#robux-계산기** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return
    embed = discord.Embed(title="💎 로벅스 환율 & 공홈 비교 계산기", description="아래 버튼을 눌러 환율을 설정하거나 계산기를 이용하세요.", color=discord.Color.blurple())
    await interaction.response.send_message(embed=embed, view=RobuxView())


@bot.tree.command(name="토큰메뉴", description="블레이드볼 토큰 시세 계산기 패널을 불러옵니다.")
async def token_menu(interaction: discord.Interaction):
    if interaction.channel.name != "블레이드볼-토큰계산":
        await interaction.response.send_message("❌ 이 명령어는 **#블레이드볼-토큰계산** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return
    embed = discord.Embed(title="⚔️ 블레이드 볼 토큰 계산기", description="토큰 시세 환율 설정 및 환전 계산 메뉴입니다.", color=discord.Color.gold())
    await interaction.response.send_message(embed=embed, view=TokenView())


@bot.tree.command(name="핑", description="봇의 실시간 응답 속도를 확인합니다.")
async def bot_ping(interaction: discord.Interaction):
    if interaction.channel.name != "bot-ping":
        await interaction.response.send_message("❌ 이 명령어는 **#bot-ping** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title="🏓 퐁!", color=discord.Color.green() if latency < 100 else discord.Color.red())
    embed.add_field(name="⚡ 봇 응답 속도", value=f"`{latency}ms`", inline=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="내전팀랜덤", description="참가자 닉네임을 콤마(,)로 구분해 입력하면 2개 팀으로 무작위 배정합니다.")
async def random_teams(interaction: discord.Interaction, players: str):
    if interaction.channel.name != "게임-내전":
        await interaction.response.send_message("❌ 이 명령어는 **#게임-내전** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return
    player_list = [p.strip() for p in players.split(",") if p.strip()]
    if len(player_list) < 2:
        await interaction.response.send_message("❌ 최소 2명 이상의 닉네임을 입력해주세요!", ephemeral=True)
        return
    random.shuffle(player_list)
    mid = len(player_list) // 2
    embed = discord.Embed(title="⚔️ 데스볼 내전 랜덤 팀 배정", color=discord.Color.blurple())
    embed.add_field(name="🔵 [ A 팀 ]", value="\n".join([f"• `{p}`" for p in player_list[:mid]]), inline=True)
    embed.add_field(name="🔴 [ B 팀 ]", value="\n".join([f"• `{p}`" for p in player_list[mid:]]), inline=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="토너먼트생성", description="참가자 닉네임을 콤마(,)로 입력해 토너먼트 대진표를 만듭니다.")
async def tournament_matchup(interaction: discord.Interaction, players: str):
    if interaction.channel.name != "데스볼-토너먼트-표":
        await interaction.response.send_message("❌ 이 명령어는 **#데스볼-토너먼트-표** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return
    player_list = [p.strip() for p in players.split(",") if p.strip()]
    if len(player_list) < 2:
        await interaction.response.send_message("❌ 최소 2명 이상의 닉네임을 입력해주세요!", ephemeral=True)
        return
    random.shuffle(player_list)
    embed = discord.Embed(title="🏆 데스볼 토너먼트 대진표", color=discord.Color.gold())
    for i in range(0, len(player_list) - 1, 2):
        embed.add_field(name=f"⚔️ Match {i//2 + 1}", value=f"`{player_list[i]}`  VS  `{player_list[i+1]}`", inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="맵추천", description="등록된 데스볼 맵 중 하나를 무작위로 추첨해 줍니다.")
async def recommend_map(interaction: discord.Interaction):
    if interaction.channel.name != "데스볼-맵-추천":
        await interaction.response.send_message("❌ 이 명령어는 **#데스볼-맵-추천** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return
    if not deathball_maps:
        await interaction.response.send_message("❌ 등록된 맵이 없습니다.", ephemeral=True)
        return
    chosen_map = random.choice(deathball_maps)
    embed = discord.Embed(title="🗺️ 데스볼 랜덤 맵 추첨 결과", description=f"# **🏟️ {chosen_map}**", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="맵추가", description="추첨 풀에 새로운 데스볼 맵을 추가합니다.")
async def add_map(interaction: discord.Interaction, map_name: str):
    if map_name in deathball_maps:
        await interaction.response.send_message(f"⚠️ **{map_name}** 맵은 이미 목록에 존재합니다!", ephemeral=True)
        return
    deathball_maps.append(map_name)
    await interaction.response.send_message(f"✅ 새로운 맵 **'{map_name}'**이(가) 추가되었습니다!", ephemeral=True)


@bot.tree.command(name="맵삭제", description="등록된 데스볼 맵을 목록에서 제거합니다.")
async def remove_map(interaction: discord.Interaction, map_name: str):
    if map_name in deathball_maps:
        deathball_maps.remove(map_name)
        await interaction.response.send_message(f"🗑️ **'{map_name}'** 맵이 목록에서 제거되었습니다.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ 목록에 **'{map_name}'** 맵이 존재하지 않습니다.", ephemeral=True)


@bot.tree.command(name="맵목록", description="현재 등록된 모든 데스볼 맵 목록을 확인합니다.")
async def list_maps(interaction: discord.Interaction):
    if not deathball_maps:
        await interaction.response.send_message("❌ 등록된 맵이 없습니다.", ephemeral=True)
        return
    map_str = "\n".join([f"• `{m}`" for m in deathball_maps])
    embed = discord.Embed(title="📋 등록된 데스볼 맵 목록", description=map_str, color=discord.Color.blurple())
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="내전등록메뉴", description="버튼으로 참가자를 모집하는 내전 등록 패널을 생성합니다.")
async def matchup_menu(interaction: discord.Interaction):
    if interaction.channel.name != "데스볼-내전-등록":
        await interaction.response.send_message("❌ 이 명령어는 **#데스볼-내전-등록** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return
    global matchup_participants
    matchup_participants.clear()
    embed = discord.Embed(title="📝 데스볼 내전 참가자 모집", description="아래 버튼을 눌러 내전에 참여하거나 취소하세요!", color=discord.Color.orange())
    embed.add_field(name="👥 실시간 참가 명단 (0명)", value="아직 참가자가 없습니다.", inline=False)
    await interaction.response.send_message(embed=embed, view=MatchupRegisterView())


@bot.tree.command(name="로블록스조회", description="로블록스 유저의 프로필을 조회합니다.")
async def roblox_lookup(interaction: discord.Interaction, roblox_username: str):
    if interaction.channel.name != "roblox-id":
        await interaction.response.send_message("❌ 이 명령어는 **#roblox-id** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return
    
    await interaction.response.defer()
    info = await get_roblox_user_info(roblox_username)
    if not info:
        await interaction.followup.send("❌ 존재하지 않는 유저입니다.", ephemeral=True)
        return
    
    embed = discord.Embed(title=f"{info['real_name']}", color=discord.Color.blurple())
    embed.add_field(name="👤 표시 이름", value=f"`{info['display_name']}`", inline=True)
    embed.add_field(name="📅 계정 생성일", value=f"{info['created_at']} ({info['age_days']:,}일째)", inline=True)
    
    # 이전 아이디 표시
    if info['previous_names']:
        prev_str = ", ".join([f"`{name}`" for name in info['previous_names']])
    else:
        prev_str = "`없음`"
    embed.add_field(name="📜 이전 아이디", value=prev_str, inline=False)

    if info['avatar_url']:
        embed.set_thumbnail(url=info['avatar_url'])
    await interaction.followup.send(embed=embed, view=RobloxProfileView(info['profile_url']))


@bot.tree.command(name="한국인플레이어조회", description="데스볼 한국인 플레이어를 조회합니다.")
async def deathball_korean_lookup(interaction: discord.Interaction, roblox_username: str):
    if interaction.channel.name != "death-ball-korean-player":
        await interaction.response.send_message("❌ 이 명령어는 **#death-ball-korean-player** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return
    
    await interaction.response.defer()
    info = await get_roblox_user_info(roblox_username)
    if not info:
        await interaction.followup.send("❌ 존재하지 않는 유저입니다.", ephemeral=True)
        return
        
    embed = discord.Embed(title=f"{info['real_name']}", color=discord.Color.red())
    embed.add_field(name="👤 표시 이름", value=f"`{info['display_name']}`", inline=True)
    embed.add_field(name="📅 계정 생성일", value=f"{info['created_at']} ({info['age_days']:,}일째)", inline=True)
    
    # 이전 아이디 표시
    if info['previous_names']:
        prev_str = ", ".join([f"`{name}`" for name in info['previous_names']])
    else:
        prev_str = "`없음`"
    embed.add_field(name="📜 이전 아이디", value=prev_str, inline=False)

    if info['avatar_url']:
        embed.set_thumbnail(url=info['avatar_url'])
    await interaction.followup.send(embed=embed, view=RobloxProfileView(info['profile_url']))


# ==========================================
# 🏆 닉네임 자동 동기화 티어 시스템
# ==========================================
async def generate_tier_embed(tiers_dict, title, color_val, thumbnail_url=None):
    if not tiers_dict:
        return None
    description = ""
    medals = ["🥇", "🥈", "🥉"]
    for rank in sorted(tiers_dict.keys()):
        data = tiers_dict[rank]
        latest_name, latest_display = await get_latest_username_by_id(data["user_id"])
        display_str = f"{latest_name} (@{latest_display})" if latest_name else f"{data['username']} (갱신 실패)"
        rank_icon = medals[rank - 1] if rank <= 3 else f"`[{rank:2d}]`"
        description += f"{rank_icon}  **{display_str}**\n"

    embed = discord.Embed(title=title, description=description, color=color_val)
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    embed.add_field(name="📊 총 등록 인원", value=f"**{len(tiers_dict)}명** (실시간 동기화 🟢)", inline=False)
    return embed


@bot.tree.command(name="티어등록", description="한국 데스볼 티어에 유저를 등록합니다.")
async def register_tier(interaction: discord.Interaction, rank: int, roblox_username: str):
    if interaction.channel.name != "korean-deathball-tier":
        await interaction.response.send_message("❌ **#korean-deathball-tier** 채널에서만 가능합니다.", ephemeral=True)
        return
    
    await interaction.response.defer()
    info = await get_roblox_user_info(roblox_username)
    if not info:
        await interaction.followup.send("❌ 유저를 찾을 수 없습니다.", ephemeral=True)
        return
    
    new_tiers = {r + (1 if r >= rank else 0): d for r, d in deathball_tiers.items()}
    new_tiers[rank] = {"user_id": info["user_id"], "username": info["real_name"], "display_name": info["display_name"]}
    deathball_tiers.clear()
    deathball_tiers.update(new_tiers)

    embed = await generate_tier_embed(deathball_tiers, "🏆 Korean Deathball Leaderboard", discord.Color.orange(), info['avatar_url'])
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="티어제거", description="한국 데스볼 순위에서 유저를 제거합니다.")
async def remove_tier(interaction: discord.Interaction, rank: int):
    if interaction.channel.name != "korean-deathball-tier":
        return
    if rank not in deathball_tiers:
        await interaction.response.send_message("❌ 해당 순위에 등록된 유저가 없습니다.", ephemeral=True)
        return
    
    await interaction.response.defer()
    deathball_tiers.pop(rank)
    new_tiers = { (r - 1 if r > rank else r): d for r, d in deathball_tiers.items() }
    deathball_tiers.clear()
    deathball_tiers.update(new_tiers)
    embed = await generate_tier_embed(deathball_tiers, "🏆 Korean Deathball Leaderboard", discord.Color.orange())
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="티어초기화", description="한국 데스볼 티어 순위표를 초기화합니다.")
async def reset_tier(interaction: discord.Interaction):
    if interaction.channel.name != "korean-deathball-tier":
        return
    deathball_tiers.clear()
    await interaction.response.send_message("⚠️ 티어 순위표가 초기화되었습니다.", ephemeral=True)


@bot.tree.command(name="티어순위", description="한국 데스볼 티어 순위표를 확인합니다.")
async def show_leaderboard(interaction: discord.Interaction):
    if interaction.channel.name != "korean-deathball-tier":
        return
    if not deathball_tiers:
        await interaction.response.send_message("❌ 현재 등록된 순위가 없습니다.", ephemeral=True)
        return
    
    await interaction.response.defer()
    embed = await generate_tier_embed(deathball_tiers, "🏆 Korean Deathball Leaderboard", discord.Color.orange())
    await interaction.followup.send(embed=embed)


# ==========================================
# 🚀 봇 실행 메인 함수 (웹서버 제거 버전)
# ==========================================
async def main():
    global http_session
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN이 환경 변수에 설정되지 않았습니다!")
        return

    try:
        async with bot:
            await bot.start(token)
    finally:
        if http_session and not http_session.closed:
            await http_session.close()

if __name__ == "__main__":
    asyncio.run(main())
