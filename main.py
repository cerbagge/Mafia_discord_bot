import discord
from discord.ext import commands
import asyncio
import sys

# 설정 로드
try:
    from config import config
except ImportError:
    print("❌ config.py 파일을 찾을 수 없습니다. config.py 파일을 생성해주세요.")
    sys.exit(1)

# Intents 설정
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    """봇 준비 완료 시 실행"""
    print(f"✅ 봇 로그인됨: {bot.user}")
    print(f"✅ 길드 ID: {config.GUILD_ID}")
    print(f"✅ Success Channel: {config.SUCCESS_CHANNEL_ID}")
    print(f"✅ Failure Channel: {config.FAILURE_CHANNEL_ID}")
    
    # 확장 로드
    print("📦 확장 로드 중...")
    await load_extensions()
    
    # 슬래시 명령어 동기화
    try:
        if config.GUILD_ID:
            # 특정 길드에만 동기화 (테스트용, 즉시 반영됨)
            guild = discord.Object(id=config.GUILD_ID)
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            print(f"✅ 길드 {config.GUILD_ID}에 슬래시 명령어 동기화 완료")
        else:
            # 전역 동기화 (최대 1시간 소요)
            await bot.tree.sync()
            print("✅ 전역 슬래시 명령어 동기화 완료")
            
        # 등록된 명령어 목록 출력
        commands = bot.tree.get_commands()
        if commands:
            print(f"📝 등록된 명령어 ({len(commands)}개):")
            for cmd in commands:
                print(f"   - /{cmd.name}: {cmd.description}")
        else:
            print("⚠️ 등록된 명령어가 없습니다!")
            
    except Exception as e:
        print(f"❌ 슬래시 명령어 동기화 실패: {e}")
    
    # 스케줄러 설정
    try:
        from scheduler import setup_scheduler
        setup_scheduler(bot)
        print("✅ 스케줄러 설정 완료")
    except Exception as e:
        print(f"❌ 스케줄러 설정 실패: {e}")
        
    print("🚀 봇이 완전히 준비되었습니다!")

@bot.event
async def on_member_join(member):
    """새로운 멤버가 서버에 들어올 때 자동으로 대기열에 추가"""
    if not config.AUTO_ADD_NEW_MEMBERS:
        return
    
    from queue_manager import queue_manager
    
    print(f"👋 새 멤버 입장: {member.display_name} ({member.id})")
    
    # 대기열에 추가
    queue_manager.add_user(member.id)
    print(f"📝 대기열에 자동 추가됨: {member.display_name}")
    
    # 환영 메시지 (선택사항)
    try:
        if config.WELCOME_CHANNEL_ID:
            welcome_channel = bot.get_channel(config.WELCOME_CHANNEL_ID)
            if welcome_channel:
                await welcome_channel.send(
                    f"🎉 {member.mention}님 환영합니다! "
                    f"마인크래프트 계정 연동을 위해 자동으로 인증 대기열에 추가되었습니다. "
                    f"잠시만 기다려주세요!"
                )
    except Exception as e:
        print(f"⚠️ 환영 메시지 전송 실패: {e}")

@bot.event
async def on_error(event, *args, **kwargs):
    """오류 발생 시 로그"""
    import traceback
    print(f"❌ 이벤트 오류 발생: {event}")
    traceback.print_exc()

# 확장 로드 함수
async def load_extensions():
    """확장 모듈 로드"""
    extensions = ["commands"]  # scheduler는 별도로 처리하므로 제외
    
    for extension in extensions:
        try:
            await bot.load_extension(extension)
            print(f"✅ 확장 로드됨: {extension}")
        except Exception as e:
            print(f"❌ 확장 로드 실패 {extension}: {e}")

# 디버그용 명령어 추가
@bot.tree.command(name="테스트", description="봇이 작동하는지 테스트")
async def test_command(interaction: discord.Interaction):
    """봇 테스트 명령어"""
    embed = discord.Embed(title="🤖 봇 상태 테스트", color=0x00ff00)
    embed.add_field(name="상태", value="✅ 정상 작동 중", inline=False)
    embed.add_field(name="지연시간", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="서버", value=interaction.guild.name, inline=True)
    embed.add_field(name="채널", value=interaction.channel.name, inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def main():
    """메인 실행 함수"""
    # 토큰 검증
    if not config.DISCORD_TOKEN:
        print("❌ Discord 토큰이 설정되지 않았습니다!")
        print("💡 .env 파일에 DISCORD_TOKEN을 설정해주세요.")
        return
        
    # 봇 실행
    try:
        async with bot:
            await bot.start(config.DISCORD_TOKEN)
    except discord.LoginFailure:
        print("❌ Discord 토큰이 잘못되었습니다!")
        print("💡 Discord Developer Portal에서 새로운 토큰을 생성해주세요.")
    except Exception as e:
        print(f"❌ 봇 실행 중 오류: {e}")

# 메인 실행
if __name__ == "__main__":
    try:
        print("🚀 Discord Bot 시작 중...")
        config.print_config_status()
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 봇이 안전하게 종료됩니다...")
    except Exception as e:
        print(f"❌ 치명적 오류: {e}")
        sys.exit(1)