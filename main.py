import os
import discord
from discord.ext import commands

# Intents 완벽 설정
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# 사용자별 데이터 저장 딕셔너리
user_rates = {}        # 로벅스 환율 저장 (1만원당 로벅스)
user_token_rates = {}  # 블레이드볼 토큰 환율 저장 (1,000 토큰당 원화)


@bot.event
async def on_ready():
    print(f"✅ 로그인: {bot.user}")
    synced = await bot.tree.sync()
    print(f"✅ 명령어: {len(synced)}개")


# ==========================================
# 1. 통합 메인 메뉴 명령어 (/계산기 또는 /메뉴)
# ==========================================
@bot.tree.command(name="메뉴", description="로벅스 및 블레이드볼 통합 계산기 메인 메뉴")
async def main_menu(interaction: discord.Interaction):
    try:
        embed = discord.Embed(
            title="💎 로블록스 통합 계산기",
            description="원하시는 계산 기능을 아래 버튼에서 선택해주세요!\n*(실수 방지를 위해 입력값과 환율을 꼼꼼히 확인합니다)*",
            color=discord.Color.blue()
        )
        
        class IntegratedMenuView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
            
            # --- 로벅스 관련 버튼 ---
            @discord.ui.button(label="💵 로벅스 환율 설정", style=discord.ButtonStyle.primary, row=0)
            async def set_robux_rate(self, interaction: discord.Interaction, button):
                await interaction.response.send_modal(RateModal())
            
            @discord.ui.button(label="원화 → 로벅스", style=discord.ButtonStyle.success, row=0)
            async def won_to_rbx(self, interaction: discord.Interaction, button):
                await interaction.response.send_modal(WonModal())
            
            @discord.ui.button(label="로벅스 → 원화", style=discord.ButtonStyle.danger, row=0)
            async def rbx_to_won(self, interaction: discord.Interaction, button):
                await interaction.response.send_modal(RbxModal())
            
            # --- 블레이드볼 토큰 관련 버튼 ---
            @discord.ui.button(label="⚔️ 토큰 환율 설정", style=discord.ButtonStyle.primary, row=1)
            async def set_token_rate(self, interaction: discord.Interaction, button):
                await interaction.response.send_modal(TokenRateModal())
            
            @discord.ui.button(label="원화 → 토큰", style=discord.ButtonStyle.success, row=1)
            async def won_to_token(self, interaction: discord.Interaction, button):
                await interaction.response.send_modal(WonToTokenModal())
            
            @discord.ui.button(label="토큰 → 원화", style=discord.ButtonStyle.danger, row=1)
            async def token_to_won(self, interaction: discord.Interaction, button):
                await interaction.response.send_modal(TokenToWonModal())
            
            # --- 내 설정 확인 버튼 ---
            @discord.ui.button(label="🔍 내 설정 확인", style=discord.ButtonStyle.secondary, row=2)
            async def check_my_rates(self, interaction: discord.Interaction, button):
                user_id = interaction.user.id
                
                rbx_text = f"1만원당 **{user_rates[user_id]:,}R**" if user_id in user_rates else "❌ 미설정"
                token_text = f"1,000 토큰당 **{user_token_rates[user_id]:,}원**" if user_id in user_token_rates else "❌ 미설정"
                
                embed_check = discord.Embed(
                    title="📊 내 환율 설정 현황",
                    color=discord.Color.purple()
                )
                embed_check.add_field(name="💎 로벅스 환율", value=rbx_text, inline=False)
                embed_check.add_field(name="⚔️ 블레이드볼 토큰 환율", value=token_text, inline=False)
                
                await interaction.response.send_message(embed=embed_check, ephemeral=True)
        
        await interaction.response.send_message(embed=embed, view=IntegratedMenuView())
    except Exception as e:
        print(f"오류: {e}")
        await interaction.response.send_message("❌ 오류가 발생했습니다.", ephemeral=True)


# ==========================================
# 2. 로벅스 관련 모달 (Modals)
# ==========================================
class RateModal(discord.ui.Modal, title="로벅스 환율 설정"):
    rate = discord.ui.TextInput(label="1만원당 로벅스", placeholder="예: 1300 (콤마 없이 숫자만)")
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            clean_value = self.rate.value.replace(",", "").strip()
            rate_value = int(clean_value)
            
            if rate_value <= 0:
                await interaction.response.send_message("❌ 0보다 큰 숫자를 입력해주세요.", ephemeral=True)
                return
                
            user_rates[user_id] = rate_value
            await interaction.response.send_message(
                f"✅ **로벅스 환율 설정 완료!**\n> 1만원 = **{rate_value:,}R** (30% 수수료 적용)",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message("❌ 숫자를 정확히 입력해주세요.", ephemeral=True)
        except Exception as e:
            print(f"오류: {e}")
            await interaction.response.send_message("❌ 오류가 발생했습니다.", ephemeral=True)


class WonModal(discord.ui.Modal, title="원화 → 로벅스"):
    won = discord.ui.TextInput(label="원화 금액", placeholder="예: 100000 (콤마 없이 숫자만)")
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            if user_id not in user_rates:
                await interaction.response.send_message("❌ 먼저 **로벅스 환율 설정**을 진행해주세요!", ephemeral=True)
                return
            
            clean_value = self.won.value.replace(",", "").strip()
            won_value = int(clean_value)
            rate = user_rates[user_id]
            
            rbx_before = (won_value / 10000) * rate
            rbx_after = rbx_before * 0.7
            fee = rbx_before - rbx_after
            
            embed = discord.Embed(title="💰 로벅스 거래 정보", color=discord.Color.green())
            embed.add_field(name="고객 지불", value=f"{won_value:,}원", inline=False)
            embed.add_field(name="제공 R (수수료 30% 반영)", value=f"**{rbx_after:,.0f}R**", inline=False)
            embed.add_field(name="원가", value=f"{rbx_before:,.0f}R", inline=True)
            embed.add_field(name="수수료(30%)", value=f"{fee:,.0f}R", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ 숫자를 정확히 입력해주세요.", ephemeral=True)
        except Exception as e:
            print(f"오류: {e}")
            await interaction.response.send_message("❌ 오류가 발생했습니다.", ephemeral=True)


class RbxModal(discord.ui.Modal, title="로벅스 → 원화"):
    rbx = discord.ui.TextInput(label="로벅스 금액", placeholder="예: 130000 (콤마 없이 숫자만)")
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            if user_id not in user_rates:
                await interaction.response.send_message("❌ 먼저 **로벅스 환율 설정**을 진행해주세요!", ephemeral=True)
                return
            
            clean_value = self.rbx.value.replace(",", "").strip()
            rbx_value = int(clean_value)
            rate = user_rates[user_id]
            
            won_value = (rbx_value / rate) * 10000
            
            embed = discord.Embed(title="💎 환전 정보", color=discord.Color.red())
            embed.add_field(name="로벅스", value=f"{rbx_value:,}R", inline=False)
            embed.add_field(name="원화", value=f"**{won_value:,.0f}원**", inline=False)
            embed.add_field(name="적용 환율", value=f"1만원당 {rate:,}R", inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ 숫자를 정확히 입력해주세요.", ephemeral=True)
        except Exception as e:
            print(f"오류: {e}")
            await interaction.response.send_message("❌ 오류가 발생했습니다.", ephemeral=True)


# ==========================================
# 3. 블레이드볼 토큰 관련 모달 (Modals)
# ==========================================
class TokenRateModal(discord.ui.Modal, title="토큰 환율 설정"):
    rate = discord.ui.TextInput(label="1,000 토큰당 가격 (원)", placeholder="예: 5000 또는 4650")
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            clean_value = self.rate.value.replace(",", "").strip()
            rate_value = int(clean_value)
            
            if rate_value <= 0:
                await interaction.response.send_message("❌ 0보다 큰 숫자를 입력해주세요.", ephemeral=True)
                return
                
            user_token_rates[user_id] = rate_value
            await interaction.response.send_message(
                f"✅ **토큰 환율 설정 완료!**\n> 기준: **1,000 토큰당 {rate_value:,}원**",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message("❌ 숫자를 올바르게 입력해주세요. (예: 5000)", ephemeral=True)
        except Exception as e:
            print(f"오류: {e}")
            await interaction.response.send_message("❌ 오류가 발생했습니다.", ephemeral=True)


class WonToTokenModal(discord.ui.Modal, title="원화 → 토큰 계산"):
    won = discord.ui.TextInput(label="사용할 원화 금액", placeholder="예: 10000 (콤마 없이 숫자만)")
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            if user_id not in user_token_rates:
                await interaction.response.send_message("❌ 먼저 **토큰 환율 설정**을 진행해주세요!", ephemeral=True)
                return
            
            clean_value = self.won.value.replace(",", "").strip()
            won_value = int(clean_value)
            rate = user_token_rates[user_id] # 1000토큰당 원화 가격
            
            tokens = (won_value / rate) * 1000
            
            embed = discord.Embed(title="💰 원화 → 토큰 환산 결과", color=discord.Color.green())
            embed.add_field(name="지불하는 원화", value=f"{won_value:,}원", inline=False)
            embed.add_field(name="받게 되는 토큰", value=f"**{tokens:,.0f} T**", inline=False)
            embed.add_field(name="적용된 환율", value=f"1,000 토큰당 {rate:,}원", inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ 금액은 숫자로만 정확히 입력해주세요.", ephemeral=True)
        except Exception as e:
            print(f"오류: {e}")
            await interaction.response.send_message("❌ 오류가 발생했습니다.", ephemeral=True)


class TokenToWonModal(discord.ui.Modal, title="토큰 → 원화 계산"):
    tokens = discord.ui.TextInput(label="계산할 토큰 수량", placeholder="예: 5000 (콤마 없이 숫자만)")
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            if user_id not in user_token_rates:
                await interaction.response.send_message("❌ 먼저 **토큰 환율 설정**을 진행해주세요!", ephemeral=True)
                return
            
            clean_value = self.tokens.value.replace(",", "").strip()
            token_value = int(clean_value)
            rate = user_token_rates[user_id] # 1000토큰당 원화 가격
            
            won_value = (token_value / 1000) * rate
            
            embed = discord.Embed(title="🪙 토큰 → 원화 환산 결과", color=discord.Color.red())
            embed.add_field(name="계산할 토큰", value=f"{token_value:,} T", inline=False)
            embed.add_field(name="지불해야 할 원화", value=f"**{won_value:,.0f}원**", inline=False)
            embed.add_field(name="적용된 환율", value=f"1,000 토큰당 {rate:,}원", inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ 토큰 수량은 숫자로만 정확히 입력해주세요.", ephemeral=True)
        except Exception as e:
            print(f"오류: {e}")
            await interaction.response.send_message("❌ 오류가 발생했습니다.", ephemeral=True)


# ==========================================
# 4. 도움말 명령어
# ==========================================
@bot.tree.command(name="도움말", description="봇 사용법 안내")
async def help_command(interaction: discord.Interaction):
    try:
        embed = discord.Embed(
            title="📖 로블록스 통합 계산기 사용법",
            description="안전한 거래를 위한 환산 봇입니다.",
            color=discord.Color.blue()
        )
        embed.add_field(name="/메뉴", value="로벅스 및 블레이드볼 계산 메뉴를 엽니다.", inline=False)
        embed.add_field(name="사용 방법", value="1. 먼저 각 항목의 **[환율 설정]** 버튼을 눌러 시세를 지정합니다.\n2. 원하는 계산 버튼(**원화↔로벅스** 또는 **원화↔토큰**)을 눌러 금액을 확인합니다.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"오류: {e}")
        await interaction.response.send_message("❌ 오류가 발생했습니다.", ephemeral=True)


# 프로그램 실행 (맨 마지막에 딱 1개만 존재해야 함)
bot.run(os.environ.get("DISCORD_TOKEN"))
