from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timezone, timedelta
import discord
import aiohttp
import os
import time
import re

from queue_manager import queue_manager
from exception_manager import exception_manager

# config.py에서 환경변수 가져오기
try:
    from config import config
    MC_API_BASE = config.MC_API_BASE
    BASE_NATION = config.BASE_NATION
    SUCCESS_ROLE_ID = config.SUCCESS_ROLE_ID
    SUCCESS_ROLE_ID_OUT = getattr(config, 'SUCCESS_ROLE_ID_OUT', 0)
    SUCCESS_CHANNEL_ID = config.SUCCESS_CHANNEL_ID
    FAILURE_CHANNEL_ID = config.FAILURE_CHANNEL_ID
    AUTO_EXECUTION_DAY = config.AUTO_EXECUTION_DAY
    AUTO_EXECUTION_HOUR = config.AUTO_EXECUTION_HOUR
    AUTO_EXECUTION_MINUTE = config.AUTO_EXECUTION_MINUTE
    print("✅ scheduler.py: config.py에서 환경변수 로드 완료")
except ImportError:
    # config.py가 없으면 직접 환경변수 로드
    print("⚠️ config.py를 찾을 수 없어 직접 환경변수를 로드합니다.")
    MC_API_BASE = os.getenv("MC_API_BASE", "https://api.planetearth.kr")
    BASE_NATION = os.getenv("BASE_NATION", "Red_Mafia")
    SUCCESS_ROLE_ID = int(os.getenv("SUCCESS_ROLE_ID", "0"))
    SUCCESS_ROLE_ID_OUT = int(os.getenv("SUCCESS_ROLE_ID_OUT", "0"))
    SUCCESS_CHANNEL_ID = int(os.getenv("SUCCESS_CHANNEL_ID", "0"))
    FAILURE_CHANNEL_ID = int(os.getenv("FAILURE_CHANNEL_ID", "0"))
    AUTO_EXECUTION_DAY = int(os.getenv("AUTO_EXECUTION_DAY", "2"))
    AUTO_EXECUTION_HOUR = int(os.getenv("AUTO_EXECUTION_HOUR", "3"))
    AUTO_EXECUTION_MINUTE = int(os.getenv("AUTO_EXECUTION_MINUTE", "24"))

# 스케줄러 인스턴스
scheduler = AsyncIOScheduler(timezone='Asia/Seoul')

def is_exception_user(user_id: int) -> bool:
    """예외 사용자 확인 함수 (main.py에서 사용)"""
    try:
        return exception_manager.is_exception(user_id)
    except Exception as e:
        print(f"⚠️ 예외 사용자 확인 오류: {e}")
        return False

def setup_scheduler(bot):
    """스케줄러 설정 함수 (main.py에서 호출)"""
    start_scheduler(bot)

def get_scheduler_info():
    """스케줄러 상태 정보를 반환"""
    try:
        # 스케줄러 실행 상태
        running = scheduler.running
        
        # 등록된 작업들
        jobs = []
        for job in scheduler.get_jobs():
            # 다음 실행 시간을 한국 시간으로 변환
            if job.next_run_time:
                kst = timezone(timedelta(hours=9))
                next_run = job.next_run_time.astimezone(kst).strftime("%Y-%m-%d %H:%M:%S KST")
            else:
                next_run = "없음"
            
            jobs.append({
                "id": job.id,
                "name": job.name or job.id,
                "next_run": next_run
            })
        
        return {
            "running": running,
            "jobs": jobs,
            "auto_execution_day": AUTO_EXECUTION_DAY,
            "auto_execution_hour": AUTO_EXECUTION_HOUR,
            "auto_execution_minute": AUTO_EXECUTION_MINUTE
        }
    except Exception as e:
        print(f"스케줄러 정보 조회 오류: {e}")
        return {
            "running": False,
            "jobs": [],
            "auto_execution_day": AUTO_EXECUTION_DAY,
            "auto_execution_hour": AUTO_EXECUTION_HOUR,
            "auto_execution_minute": AUTO_EXECUTION_MINUTE
        }

def abbreviate_nation_name(nation_name: str) -> str:
    """국가 이름을 축약하는 함수"""
    # 언더스코어로 분리된 단어들의 첫 글자만 가져오기
    parts = nation_name.split('_')
    if len(parts) <= 1:
        # 언더스코어가 없으면 대문자만 추출 (CamelCase 처리)
        capital_letters = re.findall(r'[A-Z]', nation_name)
        if capital_letters:
            return '.'.join(capital_letters)
        else:
            # 대문자가 없으면 처음 5글자만
            return nation_name[:5]
    else:
        # 각 단어의 첫 글자를 점으로 연결
        abbreviated = '.'.join([part[0].upper() for part in parts if part])
        return abbreviated

def create_nickname(mc_id: str, nation: str, current_nickname: str = None) -> str:
    """닉네임 생성 함수"""
    # Discord 닉네임 최대 길이
    MAX_LENGTH = 32
    SEPARATOR = " ㅣ "
    
    if nation == BASE_NATION:
        # BASE_NATION인 경우 기존 콜사인 유지 시도
        if current_nickname and " ㅣ " in current_nickname:
            # 현재 닉네임에서 콜사인 부분 추출
            parts = current_nickname.split(" ㅣ ")
            if len(parts) >= 2:
                current_callsign = parts[1]
                # 마크 닉네임이 현재 닉네임의 첫 부분과 일치하는지 확인
                if parts[0] == mc_id:
                    # 기존 콜사인 유지
                    new_nickname = f"{mc_id}{SEPARATOR}{current_callsign}"
                    if len(new_nickname) <= MAX_LENGTH:
                        return new_nickname
        
        # 기존 콜사인이 없거나 길이 초과인 경우 국가명 사용
        callsign = nation
    else:
        # 다른 국가인 경우 국가명 사용
        callsign = nation
    
    # 기본 닉네임 생성
    base_nickname = f"{mc_id}{SEPARATOR}{callsign}"
    
    # 길이 확인
    if len(base_nickname) <= MAX_LENGTH:
        return base_nickname
    
    # 길이 초과 시 국가명 축약
    abbreviated_nation = abbreviate_nation_name(callsign)
    abbreviated_nickname = f"{mc_id}{SEPARATOR}{abbreviated_nation}"
    
    # 축약해도 길이 초과인 경우
    if len(abbreviated_nickname) > MAX_LENGTH:
        # 마크 닉네임을 우선시하고 국가 부분을 더 축약
        available_length = MAX_LENGTH - len(mc_id) - len(SEPARATOR)
        if available_length > 0:
            truncated_nation = abbreviated_nation[:available_length]
            return f"{mc_id}{SEPARATOR}{truncated_nation}"
        else:
            # 극단적인 경우 마크 닉네임만
            return mc_id[:MAX_LENGTH]
    
    return abbreviated_nickname

async def send_log_message(bot, channel_id: int, embed: discord.Embed):
    """로그 메시지를 지정된 채널에 전송"""
    try:
        if channel_id == 0:
            print("⚠️ 채널 ID가 설정되지 않았습니다.")
            return
            
        channel = bot.get_channel(channel_id)
        if not channel:
            print(f"⚠️ 채널을 찾을 수 없습니다: {channel_id}")
            return
            
        await channel.send(embed=embed)
        print(f"📨 로그 메시지 전송됨: {channel.name}")
        
    except Exception as e:
        print(f"❌ 로그 메시지 전송 실패: {e}")

async def manual_execute_auto_roles(bot):
    """자동 역할 부여를 수동으로 실행"""
    try:
        print("🎯 수동 자동 역할 실행 시작")
        
        # auto_roles.txt 파일 확인
        auto_roles_path = "auto_roles.txt"
        if not os.path.exists(auto_roles_path):
            return {
                "success": False,
                "message": "auto_roles.txt 파일이 존재하지 않습니다."
            }
        
        # 역할 ID 읽기
        with open(auto_roles_path, "r") as f:
            role_ids = [line.strip() for line in f.readlines() if line.strip()]
        
        if not role_ids:
            return {
                "success": False,
                "message": "auto_roles.txt 파일에 역할 ID가 없습니다."
            }
        
        added_count = 0
        
        # 각 길드에서 역할 멤버들을 대기열에 추가
        for guild in bot.guilds:
            print(f"🏰 길드 처리: {guild.name}")
            
            for role_id_str in role_ids:
                try:
                    role_id = int(role_id_str)
                    role = guild.get_role(role_id)
                    
                    if not role:
                        print(f"⚠️ 역할을 찾을 수 없음: {role_id}")
                        continue
                    
                    print(f"👥 역할 '{role.name}' 멤버 {len(role.members)}명 처리 중")
                    
                    for member in role.members:
                        # 예외 목록 확인
                        if exception_manager.is_exception(member.id):
                            print(f"  ⏭️ 예외 대상 건너뜀: {member.display_name}")
                            continue
                        
                        # 대기열에 추가
                        if queue_manager.add_user(member.id):
                            added_count += 1
                            print(f"  ➕ 대기열 추가: {member.display_name}")
                        else:
                            print(f"  ⏭️ 이미 대기열에 있음: {member.display_name}")
                    
                except ValueError:
                    print(f"⚠️ 잘못된 역할 ID 형식: {role_id_str}")
                    continue
                except Exception as e:
                    print(f"⚠️ 역할 처리 오류 ({role_id_str}): {e}")
                    continue
        
        print(f"✅ 자동 역할 실행 완료 - {added_count}명 대기열 추가")
        
        # 자동 역할 실행 완료 로그 전송
        embed = discord.Embed(
            title="🎯 자동 역할 실행 완료",
            description=f"**{added_count}명**이 대기열에 추가되었습니다.",
            color=0x00ff00
        )
        
        embed.add_field(
            name="📋 처리된 역할",
            value=", ".join([f"<@&{role_id.strip()}>" for role_id in role_ids]) if role_ids else "없음",
            inline=False
        )
        
        current_queue_size = queue_manager.get_queue_size()
        embed.add_field(
            name="📊 대기열 현황",
            value=f"현재 대기 중: **{current_queue_size}명**",
            inline=False
        )
        
        if current_queue_size > 0:
            estimated_minutes = (current_queue_size * 36) // 60  # 배치당 36초 예상
            embed.add_field(
                name="⏰ 예상 완료 시간",
                value=f"약 {estimated_minutes}분 후" if estimated_minutes > 0 else "1분 이내",
                inline=False
            )
        
        embed.timestamp = datetime.now()
        
        await send_log_message(bot, SUCCESS_CHANNEL_ID, embed)
        
        return {
            "success": True,
            "message": f"{added_count}명이 대기열에 추가되었습니다.",
            "added_count": added_count
        }
        
    except Exception as e:
        print(f"❌ 자동 역할 실행 오류: {e}")
        
        # 자동 역할 실행 실패 로그 전송
        embed = discord.Embed(
            title="❌ 자동 역할 실행 실패",
            description="자동 역할 실행 중 오류가 발생했습니다.",
            color=0xff0000
        )
        
        embed.add_field(
            name="❌ 오류 내용",
            value=str(e)[:1000],
            inline=False
        )
        
        embed.timestamp = datetime.now()
        
        await send_log_message(bot, FAILURE_CHANNEL_ID, embed)
        
        return {
            "success": False,
            "message": f"실행 중 오류 발생: {str(e)}"
        }

def start_scheduler(bot):
    """스케줄러 시작"""
    try:
        print("🚀 스케줄러 시작")
        
        # 대기열 처리 작업 (1분마다)
        scheduler.add_job(
            process_queue_batch,
            trigger=IntervalTrigger(minutes=1),
            args=[bot],
            id="queue_processor",
            name="대기열 처리",
            replace_existing=True
        )
        
        # 자동 역할 실행 작업 (매주 지정된 요일과 시간에)
        # 요일: 월(0), 화(1), 수(2), 목(3), 금(4), 토(5), 일(6)
        day_names = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        day_name = day_names[AUTO_EXECUTION_DAY]
        
        scheduler.add_job(
            execute_auto_roles,
            trigger=CronTrigger(
                day_of_week=AUTO_EXECUTION_DAY,
                hour=AUTO_EXECUTION_HOUR,
                minute=AUTO_EXECUTION_MINUTE,
                timezone='Asia/Seoul'
            ),
            args=[bot],
            id="auto_roles_execution",
            name="자동 역할 실행",
            replace_existing=True
        )
        
        scheduler.start()
        
        print("✅ 스케줄러 시작 완료")
        print(f"   📋 대기열 처리: 1분마다")
        print(f"   🎯 자동 역할 실행: 매주 {day_name} {AUTO_EXECUTION_HOUR:02d}:{AUTO_EXECUTION_MINUTE:02d}")
        
    except Exception as e:
        print(f"❌ 스케줄러 시작 실패: {e}")

def stop_scheduler():
    """스케줄러 중지"""
    try:
        if scheduler.running:
            scheduler.shutdown()
            print("🛑 스케줄러 중지 완료")
    except Exception as e:
        print(f"❌ 스케줄러 중지 실패: {e}")

async def process_queue_batch(bot):
    """대기열에서 사용자들을 배치로 처리"""
    try:
        if queue_manager.get_queue_size() == 0:
            return
        
        print("🔄 대기열 배치 처리 시작")
        queue_manager.processing = True
        
        # 배치 크기 (한 번에 처리할 사용자 수)
        batch_size = 3
        processed_users = []
        
        for _ in range(batch_size):
            user_id = queue_manager.get_next()
            if user_id is None:
                break
            processed_users.append(user_id)
        
        if not processed_users:
            queue_manager.processing = False
            return
        
        print(f"📋 배치 처리 대상: {len(processed_users)}명")
        
        # API 세션 생성
        async with aiohttp.ClientSession() as session:
            for user_id in processed_users:
                try:
                    await process_single_user(bot, session, user_id)
                    time.sleep(10)  # API 제한을 위한 대기
                except Exception as e:
                    print(f"❌ 사용자 {user_id} 처리 실패: {e}")
        
        print(f"✅ 배치 처리 완료: {len(processed_users)}명")
        
    except Exception as e:
        print(f"❌ 배치 처리 오류: {e}")
    finally:
        queue_manager.processing = False

async def process_single_user(bot, session, user_id):
    """단일 사용자 처리"""
    member = None
    guild = None
    mc_id = None
    nation = None
    town = None
    error_message = None
    
    try:
        print(f"👤 사용자 처리 시작: {user_id}")
        
        # 모든 길드에서 해당 사용자 찾기
        for g in bot.guilds:
            m = g.get_member(user_id)
            if m:
                member = m
                guild = g
                break
        
        if not member or not guild:
            error_message = "서버에서 사용자를 찾을 수 없습니다."
            print(f"⚠️ {error_message}: {user_id}")
            
            # 실패 로그 전송
            embed = discord.Embed(
                title="❌ 사용자 처리 실패",
                description=f"**사용자 ID:** {user_id}",
                color=0xff0000
            )
            embed.add_field(
                name="❌ 오류",
                value=error_message,
                inline=False
            )
            embed.timestamp = datetime.now()
            
            await send_log_message(bot, FAILURE_CHANNEL_ID, embed)
            return
        
        # 1단계: 디스코드 ID → 마크 ID
        url1 = f"{MC_API_BASE}/discord?discord={user_id}"
        
        async with session.get(url1, timeout=aiohttp.ClientTimeout(total=10)) as r1:
            if r1.status != 200:
                error_message = f"마인크래프트 계정 연동 정보를 찾을 수 없습니다 (HTTP {r1.status})"
                print(f"  ❌ 1단계 실패: {r1.status}")
                raise Exception(error_message)
            
            data1 = await r1.json()
            if not data1.get('data') or not data1['data']:
                error_message = "마인크래프트 계정이 연동되지 않았습니다"
                print(f"  ❌ 마크 ID 데이터 없음")
                raise Exception(error_message)
            
            mc_id = data1['data'][0].get('name')
            if not mc_id:
                error_message = "마인크래프트 닉네임을 찾을 수 없습니다"
                print(f"  ❌ 마크 ID 없음")
                raise Exception(error_message)
            
            print(f"  ✅ 마크 ID: {mc_id}")
        
        time.sleep(5)
        
        # 2단계: 마크 ID → 마을
        url2 = f"{MC_API_BASE}/resident?name={mc_id}"
        
        async with session.get(url2, timeout=aiohttp.ClientTimeout(total=10)) as r2:
            if r2.status != 200:
                error_message = f"마을 정보를 조회할 수 없습니다 (HTTP {r2.status})"
                print(f"  ❌ 2단계 실패: {r2.status}")
                raise Exception(error_message)
            
            data2 = await r2.json()
            if not data2.get('data') or not data2['data']:
                error_message = "마을에 소속되어 있지 않습니다"
                print(f"  ❌ 마을 데이터 없음")
                raise Exception(error_message)
            
            town = data2['data'][0].get('town')
            if not town:
                error_message = "마을 정보가 없습니다"
                print(f"  ❌ 마을 없음")
                raise Exception(error_message)
            
            print(f"  ✅ 마을: {town}")
        
        time.sleep(5)
        
        # 3단계: 마을 → 국가
        url3 = f"{MC_API_BASE}/town?name={town}"
        
        async with session.get(url3, timeout=aiohttp.ClientTimeout(total=10)) as r3:
            if r3.status != 200:
                error_message = f"국가 정보를 조회할 수 없습니다 (HTTP {r3.status})"
                print(f"  ❌ 3단계 실패: {r3.status}")
                raise Exception(error_message)
            
            data3 = await r3.json()
            if not data3.get('data') or not data3['data']:
                error_message = "국가에 소속되어 있지 않습니다"
                print(f"  ❌ 국가 데이터 없음")
                raise Exception(error_message)
            
            nation = data3['data'][0].get('nation')
            if not nation:
                error_message = "국가 정보가 없습니다"
                print(f"  ❌ 국가 없음")
                raise Exception(error_message)
            
            print(f"  ✅ 국가: {nation}")
        
        # 역할 부여 및 닉네임 변경
        role_changes = await update_user_info(member, mc_id, nation, guild)
        
        print(f"✅ 사용자 처리 완료: {member.display_name} ({nation})")
        
        # 성공 로그 전송
        if nation == BASE_NATION:
            embed = discord.Embed(
                title="✅ 국민 확인 완료",
                description=f"**{BASE_NATION}** 국민으로 확인되었습니다!",
                color=0x00ff00
            )
        else:
            embed = discord.Embed(
                title="⚠️ 다른 국가 소속",
                description=f"**{nation}** 국가에 소속되어 있습니다.",
                color=0xff9900
            )
        
        embed.add_field(
            name="👤 사용자 정보",
            value=f"**Discord:** {member.mention}\n**닉네임:** {member.display_name}",
            inline=False
        )
        
        embed.add_field(
            name="🎮 마인크래프트 정보",
            value=f"**닉네임:** {mc_id}\n**마을:** {town}\n**국가:** {nation}",
            inline=False
        )
        
        if role_changes:
            embed.add_field(
                name="🔄 변경 사항",
                value="\n".join(role_changes),
                inline=False
            )
        
        embed.timestamp = datetime.now()
        
        await send_log_message(bot, SUCCESS_CHANNEL_ID, embed)
        
    except Exception as e:
        print(f"❌ 사용자 {user_id} 처리 중 오류: {e}")
        
        # 실패 로그 전송
        embed = discord.Embed(
            title="❌ 사용자 처리 실패",
            color=0xff0000
        )
        
        if member:
            embed.add_field(
                name="👤 사용자 정보",
                value=f"**Discord:** {member.mention}\n**닉네임:** {member.display_name}",
                inline=False
            )
        else:
            embed.add_field(
                name="👤 사용자 정보",
                value=f"**사용자 ID:** {user_id}",
                inline=False
            )
        
        if mc_id:
            minecraft_info = f"**마인크래프트 닉네임:** ``{mc_id}``"
            if town:
                minecraft_info += f"\n**마을:** {town}"
            if nation:
                minecraft_info += f"\n**국가:** {nation}"
            
            embed.add_field(
                name="🎮 마인크래프트 정보",
                value=minecraft_info,
                inline=False
            )
        
        embed.add_field(
            name="❌ 오류 내용",
            value=str(e)[:1000],  # 너무 긴 오류 메시지 제한
            inline=False
        )
        
        embed.timestamp = datetime.now()
        
        await send_log_message(bot, FAILURE_CHANNEL_ID, embed)

async def update_user_info(member, mc_id, nation, guild):
    """사용자 정보 업데이트 (역할, 닉네임) 및 변경사항 반환"""
    changes = []
    
    try:
        # 새 닉네임 생성 (기존 닉네임을 고려하여)
        current_nickname = member.display_name
        new_nickname = create_nickname(mc_id, nation, current_nickname)
        
        try:
            if current_nickname != new_nickname:
                await member.edit(nick=new_nickname)
                changes.append(f"• 닉네임이 **``{new_nickname}``**로 변경됨")
                print(f"  ✅ 닉네임 변경: {current_nickname} → {new_nickname}")
            else:
                print(f"  ℹ️ 닉네임 유지: {new_nickname}")
        except discord.Forbidden:
            changes.append("• ⚠️ 닉네임 변경 권한 없음")
            print(f"  ⚠️ 닉네임 변경 권한 없음")
        except Exception as e:
            changes.append(f"• ⚠️ 닉네임 변경 실패: {str(e)[:50]}")
            print(f"  ⚠️ 닉네임 변경 실패: {e}")
        
        # 역할 부여
        if nation == BASE_NATION:
            # 국민인 경우
            if SUCCESS_ROLE_ID != 0:
                success_role = guild.get_role(SUCCESS_ROLE_ID)
                if success_role and success_role not in member.roles:
                    try:
                        await member.add_roles(success_role)
                        changes.append(f"• **{success_role.name}** 역할 추가됨")
                        print(f"  ✅ 국민 역할 부여: {success_role.name}")
                    except Exception as e:
                        changes.append(f"• ⚠️ 국민 역할 부여 실패: {str(e)[:50]}")
                        print(f"  ⚠️ 국민 역할 부여 실패: {e}")
            
            # 비국민 역할 제거
            if SUCCESS_ROLE_ID_OUT != 0:
                out_role = guild.get_role(SUCCESS_ROLE_ID_OUT)
                if out_role and out_role in member.roles:
                    try:
                        await member.remove_roles(out_role)
                        changes.append(f"• **{out_role.name}** 역할 제거됨")
                        print(f"  ✅ 비국민 역할 제거: {out_role.name}")
                    except Exception as e:
                        changes.append(f"• ⚠️ 비국민 역할 제거 실패: {str(e)[:50]}")
                        print(f"  ⚠️ 비국민 역할 제거 실패: {e}")
        else:
            # 비국민인 경우
            if SUCCESS_ROLE_ID_OUT != 0:
                out_role = guild.get_role(SUCCESS_ROLE_ID_OUT)
                if out_role and out_role not in member.roles:
                    try:
                        await member.add_roles(out_role)
                        changes.append(f"• **{out_role.name}** 역할 추가됨")
                        print(f"  ✅ 비국민 역할 부여: {out_role.name}")
                    except Exception as e:
                        changes.append(f"• ⚠️ 비국민 역할 부여 실패: {str(e)[:50]}")
                        print(f"  ⚠️ 비국민 역할 부여 실패: {e}")
            
            # 국민 역할 제거
            if SUCCESS_ROLE_ID != 0:
                success_role = guild.get_role(SUCCESS_ROLE_ID)
                if success_role and success_role in member.roles:
                    try:
                        await member.remove_roles(success_role)
                        changes.append(f"• **{success_role.name}** 역할 제거됨")
                        print(f"  ✅ 국민 역할 제거: {success_role.name}")
                    except Exception as e:
                        changes.append(f"• ⚠️ 국민 역할 제거 실패: {str(e)[:50]}")
                        print(f"  ⚠️ 국민 역할 제거 실패: {e}")
        
        return changes
        
    except Exception as e:
        print(f"❌ 사용자 정보 업데이트 실패: {e}")
        return [f"• ❌ 업데이트 실패: {str(e)[:50]}"]

async def execute_auto_roles(bot):
    """자동 역할 실행 함수"""
    try:
        print("🎯 자동 역할 실행 시작")
        
        # auto_roles.txt 파일 확인
        auto_roles_path = "auto_roles.txt"
        if not os.path.exists(auto_roles_path):
            print("⚠️ auto_roles.txt 파일이 존재하지 않습니다.")
            
            # 실패 로그 전송
            embed = discord.Embed(
                title="❌ 자동 역할 실행 실패",
                description="auto_roles.txt 파일이 존재하지 않습니다.",
                color=0xff0000
            )
            embed.timestamp = datetime.now()
            await send_log_message(bot, FAILURE_CHANNEL_ID, embed)
            return
        
        # 역할 ID 읽기
        with open(auto_roles_path, "r") as f:
            role_ids = [line.strip() for line in f.readlines() if line.strip()]
        
        if not role_ids:
            print("⚠️ auto_roles.txt 파일에 역할 ID가 없습니다.")
            
            # 실패 로그 전송
            embed = discord.Embed(
                title="❌ 자동 역할 실행 실패",
                description="auto_roles.txt 파일에 역할 ID가 없습니다.",
                color=0xff0000
            )
            embed.timestamp = datetime.now()
            await send_log_message(bot, FAILURE_CHANNEL_ID, embed)
            return
        
        added_count = 0
        
        # 각 길드에서 역할 멤버들을 대기열에 추가
        for guild in bot.guilds:
            print(f"🏰 길드 처리: {guild.name}")
            
            for role_id_str in role_ids:
                try:
                    role_id = int(role_id_str)
                    role = guild.get_role(role_id)
                    
                    if not role:
                        print(f"⚠️ 역할을 찾을 수 없음: {role_id}")
                        continue
                    
                    print(f"👥 역할 '{role.name}' 멤버 {len(role.members)}명 처리 중")
                    
                    for member in role.members:
                        # 예외 목록 확인
                        if exception_manager.is_exception(member.id):
                            print(f"  ⏭️ 예외 대상 건너뜀: {member.display_name}")
                            continue
                        
                        # 대기열에 추가
                        if queue_manager.add_user(member.id):
                            added_count += 1
                            print(f"  ➕ 대기열 추가: {member.display_name}")
                        else:
                            print(f"  ⏭️ 이미 대기열에 있음: {member.display_name}")
                    
                except ValueError:
                    print(f"⚠️ 잘못된 역할 ID 형식: {role_id_str}")
                    continue
                except Exception as e:
                    print(f"⚠️ 역할 처리 오류 ({role_id_str}): {e}")
                    continue
        
        print(f"✅ 자동 역할 실행 완료 - {added_count}명 대기열 추가")
        
        # 자동 역할 실행 완료 로그 전송
        embed = discord.Embed(
            title="🎯 자동 역할 실행 완료",
            description=f"**{added_count}명**이 대기열에 추가되었습니다.",
            color=0x00ff00
        )
        
        embed.add_field(
            name="📋 처리된 역할",
            value=", ".join([f"<@&{role_id.strip()}>" for role_id in role_ids]) if role_ids else "없음",
            inline=False
        )
        
        current_queue_size = queue_manager.get_queue_size()
        embed.add_field(
            name="📊 대기열 현황",
            value=f"현재 대기 중: **{current_queue_size}명**",
            inline=False
        )
        
        if current_queue_size > 0:
            estimated_minutes = (current_queue_size * 36) // 60  # 배치당 36초 예상
            embed.add_field(
                name="⏰ 예상 완료 시간",
                value=f"약 {estimated_minutes}분 후" if estimated_minutes > 0 else "1분 이내",
                inline=False
            )
        
        embed.timestamp = datetime.now()
        
        await send_log_message(bot, SUCCESS_CHANNEL_ID, embed)
        
    except Exception as e:
        print(f"❌ 자동 역할 실행 오류: {e}")
        
        # 자동 역할 실행 실패 로그 전송
        embed = discord.Embed(
            title="❌ 자동 역할 실행 실패",
            description="자동 역할 실행 중 오류가 발생했습니다.",
            color=0xff0000
        )
        
        embed.add_field(
            name="❌ 오류 내용",
            value=str(e)[:1000],
            inline=False
        )
        
        embed.timestamp = datetime.now()
        
        await send_log_message(bot, FAILURE_CHANNEL_ID, embed)
