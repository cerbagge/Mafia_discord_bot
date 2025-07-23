import os
import asyncio
import discord
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from queue_manager import queue_manager
from role_manager import assign_role_and_nick
import time

def get_env_int(key, default=None):
    value = os.getenv(key)
    if value is None:
        if default is not None:
            return default
        raise ValueError(f"환경변수 {key}가 설정되지 않았습니다.")
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"환경변수 {key}의 값 '{value}'을(를) 정수로 변환할 수 없습니다.")

class RateLimiter:
    def __init__(self, max_requests=70, time_window=900):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    def can_make_request(self):
        now = time.time()
        self.requests = [req_time for req_time in self.requests if now - req_time < self.time_window]
        return len(self.requests) < self.max_requests
    
    def record_request(self):
        self.requests.append(time.time())
    
    def get_wait_time(self):
        if not self.requests:
            return 0
        oldest_request = min(self.requests)
        return max(0, self.time_window - (time.time() - oldest_request))

async def remove_roles_and_reset_nick(member):
    try:
        roles_to_remove = [role for role in member.roles if not role.managed and role.name != "@everyone"]
        await member.remove_roles(*roles_to_remove, reason="국가 불일치로 역할 제거")
        await member.edit(nick=None)
    except Exception as e:
        print(f"❌ 역할 제거 실패: {member.display_name} - {e}")

async def update_nickname_with_nation(member: discord.Member, mc_id: str, nation: str):
    """Red_Mafia가 아닌 국가의 경우 닉네임을 '마크닉 ㅣ 국가'로 변경, Red_Mafia는 마크닉만 교체"""
    try:
        BASE_NATION = os.getenv("BASE_NATION", "Red_Mafia")
        
        # 역할 ID 가져오기
        try:
            SUCCESS_ROLE_ID = get_env_int("SUCCESS_ROLE_ID")
            SUCCESS_ROLE_ID_OUT = get_env_int("SUCCESS_ROLE_ID_OUT")
        except ValueError as e:
            print(f"❌ 역할 ID 환경변수 오류: {e}")
            SUCCESS_ROLE_ID = None
            SUCCESS_ROLE_ID_OUT = None
        
        # Red_Mafia 국민이면 기존 닉네임에서 마크닉네임 부분만 교체
        if nation == BASE_NATION:
            current_nick = member.display_name
            
            # 기존 닉네임이 '마크닉 ㅣ 콜사인' 형태인지 확인
            if " ㅣ " in current_nick:
                # 기존 콜사인 부분 유지하고 마크닉네임만 교체
                callsign_part = current_nick.split(" ㅣ ", 1)[1]  # 첫 번째 구분자 이후 모든 내용
                new_nickname = f"{mc_id} ㅣ {callsign_part}"
            else:
                # 기존 닉네임이 형태에 맞지 않으면 기본 형태로 설정
                new_nickname = f"{mc_id} ㅣ Red_Mafia"
            
            # 닉네임이 32자를 초과하지 않도록 제한
            if len(new_nickname) > 32:
                if " ㅣ " in current_nick:
                    callsign_part = current_nick.split(" ㅣ ", 1)[1]
                    max_mc_id_length = 32 - len(" ㅣ ") - len(callsign_part)
                    if max_mc_id_length > 0:
                        truncated_mc_id = mc_id[:max_mc_id_length]
                        new_nickname = f"{truncated_mc_id} ㅣ {callsign_part}"
                    else:
                        new_nickname = mc_id[:32]
                else:
                    new_nickname = mc_id[:32]
            
            # Red_Mafia 국민 역할 처리: SUCCESS_ROLE_ID_OUT 제거, SUCCESS_ROLE_ID 추가
            roles_to_add = []
            roles_to_remove = []
            
            if SUCCESS_ROLE_ID:
                in_role = member.guild.get_role(SUCCESS_ROLE_ID)
                if in_role and in_role not in member.roles:
                    roles_to_add.append(in_role)
            
            if SUCCESS_ROLE_ID_OUT:
                out_role = member.guild.get_role(SUCCESS_ROLE_ID_OUT)
                if out_role and out_role in member.roles:
                    roles_to_remove.append(out_role)
            
            # 역할 추가
            if roles_to_add:
                await member.add_roles(*roles_to_add, reason="Red_Mafia 국민 역할 부여")
                role_names = [role.name for role in roles_to_add]
                print(f"✅ {member.display_name}에게 역할 추가: {', '.join(role_names)}")
            
            # 역할 제거
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Red_Mafia 국민이므로 외국인 역할 제거")
                role_names = [role.name for role in roles_to_remove]
                print(f"🗑️ {member.display_name}에게서 역할 제거: {', '.join(role_names)}")
            
            # 닉네임 변경
            if member.display_name != new_nickname:
                await member.edit(nick=new_nickname)
                print(f"✅ Red_Mafia 국민: {member.display_name} 닉네임을 '{new_nickname}'으로 변경 (마크닉만 교체)")
            else:
                print(f"ℹ️ Red_Mafia 국민: {member.display_name}의 닉네임이 이미 '{new_nickname}'입니다.")
            return
        
        # 다른 국가면 '마크닉 ㅣ 국가' 형태로 변경
        new_nickname = f"{mc_id} ㅣ {nation}"
        
        # 닉네임이 32자를 초과하지 않도록 제한
        if len(new_nickname) > 32:
            max_mc_id_length = 32 - len(" ㅣ ") - len(nation)
            if max_mc_id_length > 0:
                truncated_mc_id = mc_id[:max_mc_id_length]
                new_nickname = f"{truncated_mc_id} ㅣ {nation}"
            else:
                new_nickname = mc_id[:32]  # 최소한 마크 닉네임만
        
        # 다른 국가 국민 역할 처리: SUCCESS_ROLE_ID 제거, SUCCESS_ROLE_ID_OUT 추가
        roles_to_add = []
        roles_to_remove = []
        
        if SUCCESS_ROLE_ID_OUT:
            out_role = member.guild.get_role(SUCCESS_ROLE_ID_OUT)
            if out_role and out_role not in member.roles:
                roles_to_add.append(out_role)
        
        if SUCCESS_ROLE_ID:
            in_role = member.guild.get_role(SUCCESS_ROLE_ID)
            if in_role and in_role in member.roles:
                roles_to_remove.append(in_role)
        
        # 역할 추가
        if roles_to_add:
            await member.add_roles(*roles_to_add, reason="외국 국민 역할 부여")
            role_names = [role.name for role in roles_to_add]
            print(f"✅ {member.display_name}에게 역할 추가: {', '.join(role_names)}")
        
        # 역할 제거
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason="외국 국민이므로 Red_Mafia 역할 제거")
            role_names = [role.name for role in roles_to_remove]
            print(f"🗑️ {member.display_name}에게서 역할 제거: {', '.join(role_names)}")
        
        # 닉네임 변경
        if member.display_name != new_nickname:
            await member.edit(nick=new_nickname)
            print(f"✅ 다른 국가 국민: {member.display_name} 닉네임을 '{new_nickname}'으로 변경")
        else:
            print(f"ℹ️ {member.display_name}의 닉네임이 이미 '{new_nickname}'입니다.")
            
    except discord.Forbidden:
        print(f"❌ {member.display_name}에 대한 권한이 없습니다 (닉네임/역할 변경 실패)")
    except discord.HTTPException as e:
        print(f"❌ Discord API 오류 ({member.display_name}): {e}")
    except Exception as e:
        print(f"❌ 예상치 못한 오류 ({member.display_name}): {e}")

async def get_user_info_by_name(session, discord_id, rate_limiter):
    """3단계 API 호출로 사용자 정보 조회: Discord ID → 마크 ID → 마을 → 국가"""
    
    try:
        # Rate limiting 체크
        if not rate_limiter.can_make_request():
            wait_time = rate_limiter.get_wait_time()
            print(f"⏳ Rate Limit 도달, {wait_time:.1f}초 대기 중...")
            await asyncio.sleep(wait_time)
        
        # 1단계: 디스코드 ID → 마크 ID
        rate_limiter.record_request()
        url1 = f"https://api.planetearth.kr/discord?discord={discord_id}"
        print(f"🔗 1단계 API 호출: {url1}")
        
        async with session.get(url1, timeout=aiohttp.ClientTimeout(total=10)) as r1:
            print(f"📥 1단계 응답: Status={r1.status}")
            if r1.status != 200:
                return {"success": False, "error": f"마크ID 조회 실패 ({r1.status})"}
            
            data1 = await r1.json()
            print(f"📋 1단계 데이터: {data1}")
            
            if not data1.get('data') or not data1['data']:
                return {"success": False, "error": "마크ID 데이터 없음"}
            
            mc_id = data1['data'][0].get('name')
            if not mc_id:
                return {"success": False, "error": "마크ID 없음"}
            
            print(f"✅ 마크 ID 획득: {mc_id}")
        
        await asyncio.sleep(5)  # API 간 대기시간
        
        # 2단계: 마크 ID → 마을
        if not rate_limiter.can_make_request():
            wait_time = rate_limiter.get_wait_time()
            await asyncio.sleep(wait_time)
        
        rate_limiter.record_request()
        url2 = f"https://api.planetearth.kr/resident?name={mc_id}"
        print(f"🔗 2단계 API 호출: {url2}")
        
        async with session.get(url2, timeout=aiohttp.ClientTimeout(total=10)) as r2:
            print(f"📥 2단계 응답: Status={r2.status}")
            if r2.status != 200:
                return {"success": False, "error": f"마을 조회 실패 ({r2.status})", "mc_id": mc_id}
            
            data2 = await r2.json()
            print(f"📋 2단계 데이터: {data2}")
            
            if not data2.get('data') or not data2['data']:
                return {"success": False, "error": "마을 데이터 없음", "mc_id": mc_id}
            
            town = data2['data'][0].get('town')
            if not town:
                return {"success": False, "error": "마을 없음", "mc_id": mc_id}
            
            print(f"✅ 마을 획득: {town}")
        
        await asyncio.sleep(5)  # API 간 대기시간
        
        # 3단계: 마을 → 국가
        if not rate_limiter.can_make_request():
            wait_time = rate_limiter.get_wait_time()
            await asyncio.sleep(wait_time)
        
        rate_limiter.record_request()
        url3 = f"https://api.planetearth.kr/town?name={town}"
        print(f"🔗 3단계 API 호출: {url3}")
        
        async with session.get(url3, timeout=aiohttp.ClientTimeout(total=10)) as r3:
            print(f"📥 3단계 응답: Status={r3.status}")
            if r3.status != 200:
                return {"success": False, "error": f"국가 조회 실패 ({r3.status})", "mc_id": mc_id, "town": town}
            
            data3 = await r3.json()
            print(f"📋 3단계 데이터: {data3}")
            
            if not data3.get('data') or not data3['data']:
                return {"success": False, "error": "국가 데이터 없음", "mc_id": mc_id, "town": town}
            
            nation = data3['data'][0].get('nation')
            if not nation:
                return {"success": False, "error": "국가 없음", "mc_id": mc_id, "town": town}
            
            print(f"✅ 국가 획득: {nation}")
        
        await asyncio.sleep(5)  # API 간 대기시간
        
        return {
            "success": True, 
            "mc_id": mc_id, 
            "town": town, 
            "nation": nation
        }
        
    except asyncio.TimeoutError:
        print(f"⏰ API 타임아웃 발생 (Discord ID: {discord_id})")
        return {"success": False, "error": "API 호출 타임아웃"}
    except Exception as e:
        print(f"💥 예외 발생 (Discord ID: {discord_id}): {str(e)}")
        return {"success": False, "error": f"API 호출 중 오류: {str(e)}"}

def setup_scheduler(bot):
    try:
        GUILD_ID = get_env_int("GUILD_ID")
        SUCCESS_CHANNEL_ID = get_env_int("SUCCESS_CHANNEL_ID")
        FAILURE_CHANNEL_ID = get_env_int("FAILURE_CHANNEL_ID")
        
        print(f"🔧 스케줄러 설정:")
        print(f"   - GUILD_ID: {GUILD_ID}")
        print(f"   - SUCCESS_CHANNEL_ID: {SUCCESS_CHANNEL_ID}")
        print(f"   - FAILURE_CHANNEL_ID: {FAILURE_CHANNEL_ID}")
        
    except ValueError as e:
        print(f"❌ 환경변수 오류: {e}")
        return

    scheduler = AsyncIOScheduler()
    rate_limiter = RateLimiter()

    async def process_single_user(member, guild, success_channel, failure_channel, session):
        try:
            print(f"🔄 처리 중: {member.display_name} ({member.id})")

            BASE_NATION = os.getenv("BASE_NATION", "Red_Mafia")
            remove_role_on_fail = os.getenv("REMOVE_ROLE_IF_WRONG_NATION", "true").lower() == "true"

            # 3단계 API 호출로 사용자 정보 조회
            user_info = await get_user_info_by_name(session, member.id, rate_limiter)
            
            if not user_info["success"]:
                error_msg = user_info["error"]
                mc_id = user_info.get("mc_id", "알 수 없음")
                town = user_info.get("town", "")
                
                print(f"❌ API 조회 실패: {member.display_name} - {error_msg}")
                
                # 에러 메시지 구성
                if mc_id != "알 수 없음":
                    if town:
                        error_detail = f"IGN: `{mc_id}`, 마을: `{town}` - {error_msg}"
                    else:
                        error_detail = f"IGN: `{mc_id}` - {error_msg}"
                else:
                    error_detail = error_msg
                
                await failure_channel.send(f"⚠️ {member.mention} 인증 실패 - {error_detail}")
                return False

            mc_id = user_info["mc_id"]
            town = user_info["town"]
            nation = user_info["nation"]

            # 국가 검증 및 닉네임 처리
            if nation != BASE_NATION:
                if remove_role_on_fail:
                    await remove_roles_and_reset_nick(member)
                    print(f"🧹 역할 제거됨: {member.display_name}")
                else:
                    print(f"⚠️ 역할 유지됨: {member.display_name}")
                
                # 다른 국가인 경우에도 닉네임은 업데이트
                await update_nickname_with_nation(member, mc_id, nation)
                
                await failure_channel.send(f"⚠️ {member.mention} 인증 실패 - 국가 불일치 (IGN: `{mc_id}`, 마을: `{town}`, 국가: `{nation}`)")
                return False

            # Red_Mafia 국민인 경우 기존 로직으로 역할 할당 및 닉네임 설정
            await update_nickname_with_nation(member, mc_id, nation)
            await success_channel.send(f"✅ {member.mention} 인증 성공! IGN: `{mc_id}`, 마을: `{town}`, 국가: `{nation}`")
            print(f"✅ 인증 성공: {member.display_name} -> {mc_id} ({town}, {nation})")
            return True

        except Exception as e:
            print(f"❌ 처리 중 오류 ({member.display_name}): {e}")
            return False

    async def process_queue():
        guild = bot.get_guild(GUILD_ID)
        success_channel = bot.get_channel(SUCCESS_CHANNEL_ID)
        failure_channel = bot.get_channel(FAILURE_CHANNEL_ID)

        if not guild:
            print(f"❌ 길드를 찾을 수 없습니다 (ID: {GUILD_ID})")
            return
        if not success_channel:
            print(f"❌ 성공 채널을 찾을 수 없습니다 (ID: {SUCCESS_CHANNEL_ID})")
            return
        if not failure_channel:
            print(f"❌ 실패 채널을 찾을 수 없습니다 (ID: {FAILURE_CHANNEL_ID})")
            return

        failed_users = []
        processed_count = 0
        success_count = 0
        batch_size = 3  # API 대기시간 때문에 배치 크기 줄임
        current_batch = 0

        # aiohttp 세션 생성
        async with aiohttp.ClientSession() as session:
            while user_id := queue_manager.get_next():
                processed_count += 1
                current_batch += 1

                member = guild.get_member(user_id)
                if not member:
                    print(f"⚠️ 멤버를 찾을 수 없습니다 (ID: {user_id})")
                    failed_users.append(f"<@{user_id}>")
                    continue

                success = await process_single_user(member, guild, success_channel, failure_channel, session)

                if success:
                    success_count += 1
                else:
                    failed_users.append(member.mention)

                # 배치마다 더 긴 대기시간 (API 호출이 많아짐)
                if current_batch >= batch_size:
                    print(f"📦 배치 완료: {current_batch}명 처리, 다음 배치까지 10초 대기")
                    current_batch = 0
                    await asyncio.sleep(10)

        # 실패 유저 리스트 전송
        if failed_users:
            chunk_size = 10
            for i in range(0, len(failed_users), chunk_size):
                chunk = failed_users[i:i + chunk_size]
                await failure_channel.send(f"❌ 인증 실패 유저 ({i+1}-{min(i+chunk_size, len(failed_users))}/{len(failed_users)}): {', '.join(chunk)}")

        if processed_count > 0:
            print(f"📊 대기열 처리 완료: 총 {processed_count}명 (성공: {success_count}, 실패: {len(failed_users)})")

    # 1분마다 대기열 처리 (API 대기시간 고려해서 간격 늘릴 수 있음)
    scheduler.add_job(process_queue, "interval", seconds=60)

    # 자동 실행 스케줄 설정 - FIX: 동기 함수로 변경
    try:
        auto_day = get_env_int("AUTO_EXECUTION_DAY", 6)
        auto_hour = get_env_int("AUTO_EXECUTION_HOUR", 2)
        auto_minute = get_env_int("AUTO_EXECUTION_MINUTE", 0)

        def schedule_auto_roles():
            """스케줄러에서 호출할 동기 함수"""
            try:
                # 현재 실행 중인 이벤트 루프 가져오기
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 이미 실행 중인 루프에서 코루틴 스케줄링
                    asyncio.ensure_future(add_auto_roles(bot))
                else:
                    # 루프가 실행 중이 아니면 새로 실행
                    loop.run_until_complete(add_auto_roles(bot))
            except RuntimeError:
                # 이벤트 루프가 없는 경우 새 루프 생성
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(add_auto_roles(bot))
                finally:
                    loop.close()
            except Exception as e:
                print(f"❌ 자동 역할 스케줄 실행 오류: {e}")

        scheduler.add_job(
            schedule_auto_roles,
            "cron",
            day_of_week=auto_day,
            hour=auto_hour,
            minute=auto_minute
        )
        day_names = ["월", "화", "수", "목", "금", "토", "일"]
        day_str = day_names[auto_day]

        print(f"🕒 자동 실행 스케줄: 매주 {day_str}요일 {auto_hour}:{auto_minute:02d}")


    except ValueError as e:
        print(f"⚠️ 자동 실행 스케줄 설정 실패: {e}")

    scheduler.start()
    print("🚀 스케줄러 시작됨")

async def add_auto_roles(bot):
    try:
        GUILD_ID = get_env_int("GUILD_ID")
        guild = bot.get_guild(GUILD_ID)

        if not guild:
            print(f"❌ 자동 역할 처리: 길드를 찾을 수 없습니다 (ID: {GUILD_ID})")
            return

        auto_roles_file = "auto_roles.txt"
        if not os.path.exists(auto_roles_file):
            print(f"⚠️ 자동 역할 파일이 없습니다: {auto_roles_file}")
            return

        added_count = 0
        processed_roles = 0

        with open(auto_roles_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f.readlines(), 1):
                role_id = line.strip()
                if not role_id or role_id.startswith("#"):
                    continue

                try:
                    role = guild.get_role(int(role_id))
                    if role:
                        for member in role.members:
                            if not queue_manager.is_user_in_queue(member.id):
                                queue_manager.add_user(member.id)
                                added_count += 1
                        processed_roles += 1
                        print(f"🔄 자동 역할 처리: {role.name} - {len(role.members)}명 추가")
                    else:
                        print(f"⚠️ 역할 없음 (ID: {role_id}, 라인: {line_num})")
                except Exception as e:
                    print(f"❌ 역할 처리 오류 (ID: {role_id}, 라인: {line_num}): {e}")

        print(f"📋 자동 역할 처리 완료: {processed_roles}개 역할, 총 {added_count}명 추가")

    except Exception as e:
        print(f"❌ 자동 역할 처리 중 오류: {e}")

async def get_queue_status():
    return {
        "queue_size": queue_manager.get_queue_size(),
        "processing": queue_manager.is_processing()
    }

async def clear_queue():
    cleared_count = queue_manager.clear_queue()
    print(f"🧹 대기열 초기화 완료: {cleared_count}명 제거됨")
    return cleared_count