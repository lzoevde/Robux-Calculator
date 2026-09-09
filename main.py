import os
import discord
from discord.ext import commands
import random
import re

# Intents 설정 (메시지 읽기 및 상호작용 권한 필수)
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# 데이터 저장용 딕셔너리들
user_rates = {}        # 로벅스 환율
user_token_rates = {}  # 블레이드볼 토큰 환율
word_chain_games = {}  # 끝말잇기 게임 상태 관리

def check_korean_dictionary(word):
    """
    외부 API 오류 없이 순수 한글 구조와 형태를 엄격하게 검증하는 함수
    - 숫자, 영어, 특수문자, 자음/모음 단독 입력은 무조건 차단
    - 온전한 한글 음절로만 이루어진 2글자 이상 단어만 허용
    """
    if len(word) < 2:
        return False
        
    # 오직 완성된 한글(가-힣)로만 이루어져 있는지 정규식 검사 (숫자, 영어, 자음/모음 단독 입력 차단)
    if not re.fullmatch(r"[가-힣]+", word):
        return False
        
    # '자자자'처럼 같은 글자가 3번 이상 연속되거나 비정상적인 반복 패턴 차단
    for i in range(len(word) - 2):
        if word[i] == word[i+1] == word[i+2]:
            return False
            
    return True


@bot.event
async def on_ready():
    print(f"✅ 로그인 성공: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ 슬래시 명령어 총 {len(synced)}개 동기화 완료")
    except Exception as e:
        print(f"❌ 명령어 동기화 실패: {e}")


# ==========================================
# 1. 로벅스 계산기 명령어 (/로벅스메뉴)
# ==========================================
@bot.tree.command(name="로벅스메뉴", description="로벅스 계산기 메뉴 (#robux-계산기 전용)")
async def robux_menu(interaction: discord.Interaction):
    if interaction.channel.name != "robux-계산기":
        await interaction.response.send_message("❌ 이 명령어는 **#robux-계산기** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    try:
        embed = discord.Embed(title="💎 로벅스 계산기", description="로벅스 환율 설정 및 환산 메뉴입니다.", color=discord.Color.blue())
        
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
        
        await interaction.response.send_message(embed=embed, view=RobuxView())
    except Exception as e:
        print(f"로벅스메뉴 오류: {e}")
        await interaction.response.send_message("❌ 처리 중 오류가 발생했습니다.", ephemeral=True)


# ==========================================
# 2. 블레이드볼 토큰 계산기 명령어 (/토큰메뉴)
# ==========================================
@bot.tree.command(name="토큰메뉴", description="블레이드볼 토큰 계산기 메뉴 (#블레이드볼-토큰계산 전용)")
async def token_menu(interaction: discord.Interaction):
    if interaction.channel.name != "블레이드볼-토큰계산":
        await interaction.response.send_message("❌ 이 명령어는 **#블레이드볼-토큰계산** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    try:
        embed = discord.Embed(title="⚔️ 블레이드 볼 토큰 계산기", description="블레이드볼 토큰 시세 계산 메뉴입니다.", color=discord.Color.gold())
        
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
        
        await interaction.response.send_message(embed=embed, view=TokenView())
    except Exception as e:
        print(f"토큰메뉴 오류: {e}")
        await interaction.response.send_message("❌ 처리 중 오류가 발생했습니다.", ephemeral=True)


# ==========================================
# 3. 냥코대전쟁 안전 관리 메뉴 (/냥코메뉴)
# ==========================================
@bot.tree.command(name="냥코메뉴", description="냥코대전쟁 안전 관리 메뉴 (#냥코대전쟁-관리자 전용)")
async def battle_cats_menu(interaction: discord.Interaction):
    if interaction.channel.name != "냥코대전쟁-관리자":
        await interaction.response.send_message("❌ 이 명령어는 **#냥코대전쟁-관리자** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    try:
        embed = discord.Embed(title="🐱 냥코대전쟁 안전 세이브 관리 센터", description="데이터 손상 및 밴 위험 없는 안전한 편집 가이드와 도구 안내입니다.", color=discord.Color.orange())
        
        class BattleCatsSafeView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
            
            @discord.ui.button(label="🚨 백업 및 안전 수칙", style=discord.ButtonStyle.primary, custom_id="bc_safe_tip")
            async def safe_tip(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.send_message("📌 **데이터 손상 방지 필수 수칙**\n1. 세이브 편집 전 반드시 **계정 백업 코드**를 따로 적어두세요.\n2. 과도한 통조림 및 XP 수정은 밴의 원인이 됩니다.", ephemeral=True)
            
            @discord.ui.button(label="📢 관리자 공지 작성", style=discord.ButtonStyle.danger, custom_id="bc_notice_btn")
            async def notice_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.send_modal(BattleCatsNoticeModal())
        
        await interaction.response.send_message(embed=embed, view=BattleCatsSafeView())
    except Exception as e:
        print(f"냥코메뉴 오류: {e}")
        await interaction.response.send_message("❌ 처리 중 오류가 발생했습니다.", ephemeral=True)


# ==========================================
# 4. 끝말잇기 명령어 (/끝말잇기시작)
# ==========================================
@bot.tree.command(name="끝말잇기시작", description="현재 채널에서 봇과 끝말잇기를 시작합니다! (#끝말잇기 전용)")
async def start_word_chain(interaction: discord.Interaction):
    if interaction.channel.name != "끝말잇기":
        await interaction.response.send_message("❌ 이 명령어는 **#끝말잇기** 채널에서만 사용할 수 있습니다!", ephemeral=True)
        return

    channel_id = interaction.channel.id
    start_word = "참외"
    
    word_chain_games[channel_id] = {
        "current_word": start_word,
        "used_words": [start_word]
    }
    
    embed = discord.Embed(
        title="🎮 봇과 함께하는 끝말잇기!",
        description=f"게임이 시작되었습니다!\n\n첫 번째 단어: **{start_word}**\n👉 **'{start_word[-1]}'** (으)로 시작하는 단어를 채팅으로 입력해주세요!",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)


# ==========================================
# 5. 끝말잇기 실시간 채팅 감지
# ==========================================
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    if message.channel.name == "끝말잇기":
        content = message.content.strip()

        if content.startswith("!") or content.startswith("/"):
            return

        channel_id = message.channel.id
        if channel_id not in word_chain_games:
            return

        game = word_chain_games[channel_id]
        current_word = game["current_word"]
        last_char = current_word[-1]

        # 1. 마지막 글자로 시작하는지 확인
        if not content.startswith(last_char):
            await message.add_reaction("❌")
            await message.channel.send(f"❌ 틀렸습니다! **'{last_char}'**(으)로 시작하는 단어를 말해주세요.")
            return

        # 2. 두 글자 이상인지 확인 및 한글 형태 검증
        if not check_korean_dictionary(content):
            await message.add_reaction("❌")
            await message.channel.send(f"❌ 올바른 한글 단어가 아니거나 형식에 어긋납니다: **{content}**")
            return

        # 3. 중복 단어 확인
        if content in game["used_words"]:
            await message.add_reaction("❌")
            await message.channel.send("❌ 이미 사용된 단어입니다!")
            return

        # 정답 처리
        game["used_words"].append(content)
        game["current_word"] = content
        await message.add_reaction("✅")

        # 봇의 답변 생성
        next_first_char = content[-1]
        sample_suffixes = ["구기자", "나라", "나무", "바다", "하늘", "사람", "마을", "다리", "노을", "가방", "지도"]
        
        bot_word = None
        for suffix in sample_suffixes:
            candidate = next_first_char + suffix
            if candidate not in game["used_words"]:
                bot_word = candidate
                break
        
        if not bot_word:
            bot_word = f"{next_first_char}나라"

        game["used_words"].append(bot_word)
        game["current_word"] = bot_word

        await message.channel.send(f"🤖 봇의 답변: **{bot_word}** (이어서 입력하세요: **'{bot_word[-1]}'**(으)로 시작)")


# ==========================================
# 6. 모달(팝업창) 클래스 모음
# ==========================================
class BattleCatsNoticeModal(discord.ui.Modal, title="냥코 관리자 공지 작성"):
    notice_text = discord.ui.TextInput(label="공지 내용", style=discord.TextStyle.paragraph, placeholder="공지할 내용을 입력하세요...", required=True)
    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📢 [냥코 관리자 공지]", description=self.notice_text.value, color=discord.Color.red())
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ 공지가 전송되었습니다!", ephemeral=True)

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


# 봇 실행
token = os.environ.get("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("❌ DISCORD_TOKEN이 설정되지 않았습니다!")
