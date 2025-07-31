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

# 예외 관리자 로드
try:
    from exception_manager import exception_manager
    print("✅ exception_manager 모듈 로드됨")
except ImportError:
    print("⚠️ exception_manager.py 파일을 찾을 수 없습니다. 예외 관리 기능이 비활성화됩니다.")
    exception_manager = None

# scheduler 모듈 로드 (자동 처리에 필요)
try:
    from scheduler import is_exception_user
    print("✅ scheduler 모듈에서 예외 사용자 확인 함수 로드됨")
except ImportError:
    print("⚠️ scheduler.py에서 is_exception_user 함수를 로드할 수 없습니다.")
    is_exception_user = None

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
    
    # 멤버 자동 추가 설정 확인
    auto_add_status = getattr(config, 'AUTO_ADD_NEW_MEMBERS', True)
    print(f"✅ 새 멤버 자동 추가: {'활성화' if auto_add_status else '비활성화'}")
    
    # 예외 관리자 초기화
    if exception_manager:
        try:
            exception_count = len(exception_manager.get_exceptions())
            print(f"✅ 예외 관리자 초기화 완료 (예외 사용자: {exception_count}명)")
        except Exception as e:
            print(f"⚠️ 예외 관리자 초기화 오류: {e}")
    
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
        print("🔧 스케줄러 설정:")
        print(f"   - GUILD_ID: {config.GUILD_ID}")
        print(f"   - SUCCESS_CHANNEL_ID: {config.SUCCESS_CHANNEL_ID}")
        print(f"   - FAILURE_CHANNEL_ID: {config.FAILURE_CHANNEL_ID}")
        
        # 스케줄 시간 정보 추가
        auto_execution_day = getattr(config, 'AUTO_EXECUTION_DAY', 2)  # 기본값: 수요일(2)
        auto_execution_hour = getattr(config, 'AUTO_EXECUTION_HOUR', 3)  # 기본값: 03시
        auto_execution_minute = getattr(config, 'AUTO_EXECUTION_MINUTE', 24)  # 기본값: 24분
        
        # 요일 한글 변환
        day_names = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        korean_day = day_names[auto_execution_day] if 0 <= auto_execution_day <= 6 else "알 수 없음"
        
        print(f"🕒 자동 실행 스케줄: 매주 {korean_day} {auto_execution_hour:02d}:{auto_execution_minute:02d}")
        
        setup_scheduler(bot)
        print("🚀 스케줄러 시작됨")
        print("✅ 스케줄러 설정 완료")
    except Exception as e:
        print(f"❌ 스케줄러 설정 실패: {e}")
        import traceback
        traceback.print_exc()
        
    print("🚀 봇이 완전히 준비되었습니다!")

@bot.event
async def on_member_join(member):
    """새로운 멤버가 서버에 들어올 때 자동으로 대기열에 추가"""
    try:
        print(f"👋 새 멤버 입장 감지: {member.display_name} ({member.id})")
        
        # AUTO_ADD_NEW_MEMBERS 설정 확인 (기본값: True)
        auto_add_enabled = getattr(config, 'AUTO_ADD_NEW_MEMBERS', True)
        if not auto_add_enabled:
            print(f"⚠️ 자동 추가 비활성화 상태 - {member.display_name} 건너뜀")
            return
        
        # queue_manager 로드
        try:
            from queue_manager import queue_manager
        except ImportError as e:
            print(f"❌ queue_manager 로드 실패: {e}")
            return
        
        # 예외 사용자 확인 (두 가지 방법으로 확인)
        is_exception = False
        
        # 방법 1: exception_manager 사용
        if exception_manager:
            try:
                is_exception = exception_manager.is_exception(member.id)
                print(f"🔍 exception_manager 확인: {member.display_name} -> 예외 사용자: {is_exception}")
            except Exception as e:
                print(f"⚠️ exception_manager 확인 오류: {e}")
        
        # 방법 2: scheduler의 is_exception_user 함수 사용 (fallback)
        if not is_exception and is_exception_user:
            try:
                is_exception = is_exception_user(member.id)
                print(f"🔍 scheduler 확인: {member.display_name} -> 예외 사용자: {is_exception}")
            except Exception as e:
                print(f"⚠️ scheduler 예외 확인 오류: {e}")
        
        # 예외 사용자 처리
        if is_exception:
            print(f"🚫 예외 사용자이므로 대기열 추가 제외: {member.display_name} ({member.id})")
            
            # 예외 사용자용 환영 메시지 (선택사항)
            try:
                welcome_channel_id = getattr(config, 'WELCOME_CHANNEL_ID', None)
                if welcome_channel_id:
                    welcome_channel = bot.get_channel(welcome_channel_id)
                    if welcome_channel:
                        await welcome_channel.send(
                            f"🎉 {member.mention}님 환영합니다! "
                            f"예외 설정으로 인해 자동 인증 대상에서 제외됩니다."
                        )
                        print(f"📨 예외 사용자 환영 메시지 전송됨: {member.display_name}")
            except Exception as e:
                print(f"⚠️ 예외 사용자 환영 메시지 전송 실패: {e}")
            return
        
        # 대기열에 추가
        try:
            # 이미 대기열에 있는지 확인
            if hasattr(queue_manager, 'is_user_in_queue') and queue_manager.is_user_in_queue(member.id):
                print(f"ℹ️ 이미 대기열에 있음: {member.display_name}")
            else:
                queue_manager.add_user(member.id)
                print(f"✅ 대기열에 추가됨: {member.display_name} (현재 대기열: {queue_manager.get_queue_size()}명)")
                
                # 성공 채널에 알림 (선택사항)
                try:
                    success_channel = bot.get_channel(config.SUCCESS_CHANNEL_ID)
                    if success_channel:
                        await success_channel.send(f"📝 새 멤버 대기열 추가: {member.mention} (대기: {queue_manager.get_queue_size()}명)")
                except Exception as e:
                    print(f"⚠️ 대기열 추가 알림 전송 실패: {e}")
        except Exception as e:
            print(f"❌ 대기열 추가 실패: {member.display_name} - {e}")
            return
        
        # 환영 메시지
        try:
            welcome_channel_id = getattr(config, 'WELCOME_CHANNEL_ID', None)
            if welcome_channel_id:
                welcome_channel = bot.get_channel(welcome_channel_id)
                if welcome_channel:
                    await welcome_channel.send(
                        f"🎉 {member.mention}님 환영합니다! "
                        f"마인크래프트 계정 연동을 위해 자동으로 인증 대기열에 추가되었습니다. "
                        f"잠시만 기다려주세요! (현재 대기: {queue_manager.get_queue_size()}명)"
                    )
                    print(f"📨 환영 메시지 전송됨: {member.display_name}")
            else:
                print(f"ℹ️ 환영 채널이 설정되지 않음 (WELCOME_CHANNEL_ID)")
        except Exception as e:
            print(f"⚠️ 환영 메시지 전송 실패: {e}")
            
    except Exception as e:
        print(f"❌ on_member_join 이벤트 처리 중 오류: {e}")
        import traceback
        traceback.print_exc()

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
            # 이미 로드된 경우 언로드 후 다시 로드
            if extension in bot.extensions:
                await bot.unload_extension(extension)
            await bot.load_extension(extension)
            print(f"✅ 확장 로드됨: {extension}")
        except Exception as e:
            print(f"❌ 확장 로드 실패 {extension}: {e}")
            import traceback
            traceback.print_exc()

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
        import traceback
        traceback.print_exc()

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
        import traceback
        traceback.print_exc()
        sys.exit(1)
