import os
import discord
from discord.ext import commands

# Intents 설정
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# 사용자별 데이터 저장 딕셔너리
user_rates = {}        # 로벅스 환율 저장 (1만원당 로벅스)
user_token_rates = {}  # 블레이드볼 토큰 환율 저장 (1,000 토큰당 원화)


@bot.event
async def on_ready():
    print(f"✅ 로그인 성공: {bot.user}")
    synced = await bot.tree.sync()
    print(f"✅ 슬래시 명령어 총 {len(synced)}개 동기화 완료")


# ==========================================
# 1. 로벅스 계산기 명령어 (/로벅스메뉴) - #robux-계산기 전용
# ==========================================
@bot.tree.command(name="로벅스메뉴", description="로벅스 계산기 메뉴 (#robux-계산기 전용)")
async def robux_menu(interaction: discord.Interaction):
    if interaction.channel.name != "robux-계산기":
        await interaction.response.send_message(
            "❌ 이 명령어는 **#robux-계산기** 채널에서만 사용할 수 있습니다!", 
            ephemeral=True
        )
        return

    try:
        embed = discord.Embed(
            title="💎 로벅스 계산기",
            description="로벅스 환율 설정 및 환산 메뉴입니다.",
            color=discord.Color.blue()
        )
        
        class RobuxView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
            
            @discord.ui.button(label="환율 설정", style=discord.ButtonStyle.primary)
            async def set_rate_btn(self, interaction: discord.Interaction, button):
                await interaction.response.send_modal(RateModal())
            
            @discord.ui.button(label="원화→로벅스", style=discord.ButtonStyle.success)
            async def won_to_rbx(self, interaction: discord.Interaction, button):
                await interaction.response.send_modal(WonModal())
            
            @discord.ui.button(label="로벅스→원화", style=discord.ButtonStyle.danger)
            async def rbx_to_won(self, interaction: discord.Interaction, button):
                await interaction.response.send_modal(RbxModal())
            
            @discord.ui.button(label="내 환율 확인", style=discord.ButtonStyle.secondary)
            async def check_rate(self, interaction: discord.Interaction, button):
                user_id = interaction.user.id
                if user_id in user_rates:
                    await interaction.response.send_message(
                        f"현재 로벅스 환율: 1만원당 **{user_rates[user_id]:,}R**",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ 환율을 설정하지 않았습니다.\n'환율 설정' 버튼을 클릭해주세요.",
                        ephemeral=True
                    )
        
        await interaction.response.send_message(embed=embed, view=RobuxView())
    except Exception as e:
        print(f"로벅스메뉴 오류: {e}")
        await interaction.response.send_message("❌ 처리 중 오류가 발생했습니다.", ephemeral=True)


# ==========================================
# 2. 블레이드볼 토큰 계산기 명령어 (/토큰메뉴) - #블레이드볼-토큰계산 전용
# ==========================================
@bot.tree.command(name="토큰메뉴", description="블레이드볼 토큰 계산기 메뉴 (#블레이드볼-토큰계산 전용)")
async def token_menu(interaction: discord.Interaction):
    if interaction.channel.name != "블레이드볼-토큰계산":
        await interaction.response.send_message(
            "❌ 이 명령어는 **#블레이드볼-토큰계산** 채널에서만 사용할 수 있습니다!", 
            ephemeral=True
        )
        return

    try:
        embed = discord.Embed(
            title="⚔️ 블레이드 볼 토큰 계산기",
            description="블레이드볼 토큰 시세 계산 메뉴입니다.",
            color=discord.Color.gold()
        )
        
        class TokenView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
            
            @discord.ui.button(label="토큰 환율 설정", style=discord.ButtonStyle.primary)
            async def set_token_rate(self, interaction: discord.Interaction, button):
                await interaction.response.send_modal(TokenRateModal())
            
            @discord.ui.button(label="원화 → 토큰", style=discord.ButtonStyle.success)
            async def won_to_token(self, interaction: discord.Interaction, button):
                await interaction.response.send_modal(WonToTokenModal())
            
            @discord.ui.button(label="토큰 → 원화", style=discord.ButtonStyle.danger)
            async def token_to_won(self, interaction: discord.Interaction, button):
                await interaction.response.send_modal(TokenToWonModal())
            
            @discord.ui.button(label="내 토큰 환율 확인", style=discord.ButtonStyle.secondary)
            async def check_token_rate(self, interaction: discord.Interaction, button):
                user_id = interaction.user.id
                if user_id in user_token_rates:
                    await interaction.response.send_message(
                        f"현재 설정된 토큰 환율: **1,000 토큰당 {user_token_rates[user_id]:,}원**",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ 아직 토큰 환율을 설정하지 않았습니다.\n'토큰 환율 설정' 버튼을 클릭해주세요.",
                        ephemeral=True
                    )
        
        await interaction.response.send_message(embed=embed, view=TokenView())
    except Exception as e:
        print(f"토큰메뉴 오류: {e}")
        await interaction.response.send_message("❌ 처리 중 오류가 발생했습니다.", ephemeral=True)


# ==========================================
# 3. 냥코대전쟁 안전 관리 메뉴 (/냥코메뉴) - #냥코대전쟁-관리자 전용
# ==========================================
@bot.tree.command(name="냥코메뉴", description="냥코대전쟁 안전 관리 및 BCSFE 가이드 메뉴 (#냥코대전쟁-관리자 전용)")
async def battle_cats_menu(interaction: discord.Interaction):
    if interaction.channel.name != "냥코대전쟁-관리자":
        await interaction.response.send_message(
            "❌ 이 명령어는 **#냥코대전쟁-관리자** 채널에서만 사용할 수 있습니다!", 
            ephemeral=True
        )
        return

    try:
        embed = discord.Embed(
            title="🐱 냥코대전쟁 안전 세이브 관리 센터",
            description="데이터 손상 및 밴 위험 없는 안전한 편집 가이드와 도구 안내입니다.",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="🛡️ 데이터 손상 방지 안내", 
            value="디스코드 봇 서버에서 직접 세이브 파일을 변조하면 파일이 깨져 **계정이 영구 손상**될 수 있습니다. 검증된 공식 오픈소스 BCSFE 툴을 안전하게 활용하세요.", 
            inline=False
        )
        
        class BattleCatsSafeView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
            
            @discord.ui.button(label="🚨 백업 및 안전 수칙", style=discord.ButtonStyle.primary)
            async def safe_tip(self, interaction: discord.Interaction, button):
                await interaction.response.send_message(
                    "📌 **데이터 손상 방지 필수 수칙**\n1. 세이브 편집 전 반드시 **계정 백업 코드(인기코드)**를 따로 적어두세요.\n2. 과도한 통조림 및 XP 수정은 밴의 원인이 되므로 적당히 수정하세요.\n3. 알 수 없는 봇을 통한 파일 직접 업로드 변조는 데이터 증발의 위험이 큽니다.",
                    ephemeral=True
                )
            
            @discord.ui.button(label="📢 관리자 공지 작성", style=discord.ButtonStyle.danger)
            async def notice_btn(self, interaction: discord.Interaction, button):
                await interaction.response.send_modal(BattleCatsNoticeModal())
        
        await interaction.response.send_message(embed=embed, view=BattleCatsSafeView())
    except Exception as e:
        print(f"냥코메뉴 오류: {e}")
        await interaction.response.send_message("❌ 처리 중 오류가 발생했습니다.", ephemeral=True)


# 관리자 공지 모달
class BattleCatsNoticeModal(discord.ui.Modal, title="냥코 관리자 공지 작성"):
    notice_text = discord.ui.TextInput(
        label="공지 내용", 
        style=discord.TextStyle.paragraph,
        placeholder="공지할 내용을 입력하세요...",
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            embed = discord.Embed(title="📢 [냥코 관리자 공지]", description=self.notice_text.value, color=discord.Color.red())
            await interaction.channel.send(embed=embed)
            await interaction.response.send_message("✅ 공지가 성공적으로 전송되었습니다!", ephemeral=True)
        except Exception as e:
            print(f"공지 모달 오류: {e}")
            await interaction.response.send_message("❌ 공지 전송 중 오류가 발생했습니다.", ephemeral=True)


# ==========================================
# 4. 입력값 처리 모달들 (로벅스 & 토큰)
# ==========================================
class RateModal(discord.ui.Modal, title="로벅스 환율 설정"):
    rate = discord.ui.TextInput(label="1만원당 로벅스", placeholder="예: 1300")
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            clean_value = self.rate.value.replace(",", "").strip()
            rate_value = int(clean_value)
            if rate_value <= 0:
                await interaction.response.send_message("❌ 0보다 큰 숫자를 입력해주세요.", ephemeral=True)
                return
            user_rates[user_id] = rate_value
            await interaction.response.send_message(f"✅ 로벅스 환율 설정 완료: 1만원 = {rate_value:,}R", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ 숫자를 정확히 입력해주세요.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("❌ 오류가 발생했습니다.", ephemeral=True)

class WonModal(discord.ui.Modal, title="원화 → 로벅스"):
    won = discord.ui.TextInput(label="원화 금액", placeholder="예: 100000")
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            if user_id not in user_rates:
                await interaction.response.send_message("❌ 먼저 환율을 설정해주세요!", ephemeral=True)
                return
            won_val = int(self.won.value.replace(",", "").strip())
            rate = user_rates[user_id]
            rbx = (won_val / 10000) * rate * 0.7
            await interaction.response.send_message(f"💰 제공 R (수수료 30% 반영): **{rbx:,.0f}R**", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ 숫자를 입력해주세요.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("❌ 오류가 발생했습니다.", ephemeral=True)

class RbxModal(discord.ui.Modal, title="로벅스 → 원화"):
    rbx = discord.ui.TextInput(label="로벅스 금액", placeholder="예: 130000")
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            if user_id not in user_rates:
                await interaction.response.send_message("❌ 먼저 환율을 설정해주세요!", ephemeral=True)
                return
            rbx_val = int(self.rbx.value.replace(",", "").strip())
            rate = user_rates[user_id]
            won = (rbx_val / rate) * 10000
            await interaction.response.send_message(f"💎 환전 원화: **{won:,.0f}원**", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ 숫자를 입력해주세요.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("❌ 오류가 발생했습니다.", ephemeral=True)

class TokenRateModal(discord.ui.Modal, title="토큰 환율 설정"):
    rate = discord.ui.TextInput(label="1,000 토큰당 가격 (원)", placeholder="예: 5000")
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            rate_val = int(self.rate.value.replace(",", "").strip())
            if rate_val <= 0:
                await interaction.response.send_message("❌ 0보다 큰 숫자를 입력해주세요.", ephemeral=True)
                return
            user_token_rates[user_id] = rate_val
            await interaction.response.send_message(f"✅ 토큰 환율 설정 완료: 1,000T당 {rate_val:,}원", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ 숫자를 입력해주세요.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("❌ 오류가 발생했습니다.", ephemeral=True)

class WonToTokenModal(discord.ui.Modal, title="원화 → 토큰 계산"):
    won = discord.ui.TextInput(label="사용할 원화 금액", placeholder="예: 10000")
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            if user_id not in user_token_rates:
                await interaction.response.send_message("❌ 먼저 토큰 환율을 설정해주세요!", ephemeral=True)
                return
            won_val = int(self.won.value.replace(",", "").strip())
            rate = user_token_rates[user_id]
            tokens = (won_val / rate) * 1000
            await interaction.response.send_message(f"💰 받는 토큰: **{tokens:,.0f} T**", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ 숫자를 입력해주세요.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("❌ 오류가 발생했습니다.", ephemeral=True)

class TokenToWonModal(discord.ui.Modal, title="토큰 → 원화 계산"):
    tokens = discord.ui.TextInput(label="계산할 토큰 수량", placeholder="예: 5000")
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            if user_id not in user_token_rates:
                await interaction.response.send_message("❌ 먼저 토큰 환율을 설정해주세요!", ephemeral=True)
                return
            token_val = int(self.tokens.value.replace(",", "").strip())
            rate = user_token_rates[user_id]
            won = (token_val / 1000) * rate
            await interaction.response.send_message(f"🪙 필요한 원화: **{won:,.0f}원**", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ 숫자를 입력해주세요.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("❌ 오류가 발생했습니다.", ephemeral=True)


# 프로그램 최종 실행
token = os.environ.get("DISCORD_TOKEN")
if not token:
    print("❌ CRITICAL ERROR: DISCORD_TOKEN 환경 변수가 설정되지 않았습니다!")
else:
    bot.run(token)
