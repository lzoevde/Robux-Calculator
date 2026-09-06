import os
import discord
from discord.ext import commands

# Intents 완벽 설정
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# 사용자별 환율 저장
user_rates = {}

# 자주 쓰는 환율 프리셋
RATE_PRESETS = {
    "low": 1200,
    "normal": 1300,
    "high": 1400,
    "custom": None
}


@bot.event
async def on_ready():
    print(f"✅ 로그인: {bot.user}")
    synced = await bot.tree.sync()
    print(f"✅ 명령어: {len(synced)}개")


@bot.tree.command(name="로벅스", description="로벅스 계산기 메인 메뉴")
async def robux_menu(interaction: discord.Interaction):
    try:
        embed = discord.Embed(
            title="💎 로벅스 계산기",
            description="아래 버튼을 선택하세요",
            color=discord.Color.blue()
        )
        
        class MenuView(discord.ui.View):
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
                        f"현재 환율: 1만원당 {user_rates[user_id]:,}R",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ 환율을 설정하지 않았습니다.\n'환율 설정' 버튼을 클릭해주세요.",
                        ephemeral=True
                    )
        
        await interaction.response.send_message(embed=embed, view=MenuView())
    except Exception as e:
        print(f"오류: {e}")
        await interaction.response.send_message("오류가 발생했습니다.", ephemeral=True)


class RateModal(discord.ui.Modal, title="환율 설정"):
    rate = discord.ui.TextInput(label="1만원당 로벅스", placeholder="예: 1300")
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            rate_value = int(self.rate.value)
            user_rates[user_id] = rate_value
            await interaction.response.send_message(
                f"✅ 환율 설정 완료!\n1만원 = {rate_value:,}R\n(30% 수수료 적용)",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message("❌ 숫자를 입력해주세요.", ephemeral=True)
        except Exception as e:
            print(f"오류: {e}")
            await interaction.response.send_message("오류가 발생했습니다.", ephemeral=True)


class WonModal(discord.ui.Modal, title="원화 → 로벅스"):
    won = discord.ui.TextInput(label="원화 금액", placeholder="예: 100000")
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            if user_id not in user_rates:
                await interaction.response.send_message(
                    "❌ 먼저 환율을 설정하세요!",
                    ephemeral=True
                )
                return
            
            won_value = int(self.won.value)
            rate = user_rates[user_id]
            rbx_before = (won_value / 10000) * rate
            rbx_after = rbx_before * 0.7
            fee = rbx_before - rbx_after
            
            embed = discord.Embed(
                title="💰 거래 정보",
                color=discord.Color.green()
            )
            embed.add_field(name="고객 지불", value=f"{won_value:,}원", inline=False)
            embed.add_field(name="제공 R", value=f"{rbx_after:,.0f}R", inline=False)
            embed.add_field(name="원가", value=f"{rbx_before:,.0f}R", inline=True)
            embed.add_field(name="수수료(30%)", value=f"{fee:,.0f}R", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ 숫자를 입력해주세요.", ephemeral=True)
        except Exception as e:
            print(f"오류: {e}")
            await interaction.response.send_message("오류가 발생했습니다.", ephemeral=True)


class RbxModal(discord.ui.Modal, title="로벅스 → 원화"):
    rbx = discord.ui.TextInput(label="로벅스 금액", placeholder="예: 130000")
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            if user_id not in user_rates:
                await interaction.response.send_message(
                    "❌ 먼저 환율을 설정하세요!",
                    ephemeral=True
                )
                return
            
            rbx_value = int(self.rbx.value)
            rate = user_rates[user_id]
            won_value = (rbx_value / rate) * 10000
            
            embed = discord.Embed(
                title="💎 환전 정보",
                color=discord.Color.red()
            )
            embed.add_field(name="로벅스", value=f"{rbx_value:,}R", inline=False)
            embed.add_field(name="원화", value=f"{won_value:,.0f}원", inline=False)
            embed.add_field(name="환율", value=f"1만원당 {rate:,}R", inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ 숫자를 입력해주세요.", ephemeral=True)
        except Exception as e:
            print(f"오류: {e}")
            await interaction.response.send_message("오류가 발생했습니다.", ephemeral=True)


@bot.tree.command(name="도움말", description="봇 사용법")
async def help_command(interaction: discord.Interaction):
    try:
        embed = discord.Embed(
            title="📖 로벅스 계산기 사용법",
            description="이 봇으로 로벅스를 쉽게 환전할 수 있습니다!",
            color=discord.Color.blue()
        )
        embed.add_field(name="/로벅스", value="메인 메뉴 실행", inline=False)
        embed.add_field(name="/도움말", value="사용법 보기", inline=False)
        embed.add_field(name="💡 팁", value="'메인 메뉴' 버튼을 누르고 환율을 먼저 설정하세요!", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"오류: {e}")
        await interaction.response.send_message("오류가 발생했습니다.", ephemeral=True)


bot.run(os.environ.get("DISCORD_TOKEN"))
