import os
import asyncio
import discord
import aiohttp
import json
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from queue_manager import queue_manager
from role_manager import assign_role_and_nick
import time

# 예외 사용자 파일 경로
EXCEPTION_USERS_FILE = "exception_users.json"

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

# 예외 사용자 관리 함수들 - 디버깅 로그 추가
def load_exception_users():
    """예외 사용자 목록을 JSON 파일에서 로드"""
    try:
        if os.path.exists(EXCEPTION_USERS_FILE):
            print(f"🔍 예외 사용자 파일 로드 시도: {EXCEPTION_USERS_FILE}")
            with open(EXCEPTION_USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                exception_users = set(data.get("exception_users", []))
                print(f"📋 예외 사용자 로드 완료: {len(exception_users)}명 - {list(exception_users)}")
                return exception_users
        else:
            print(f"⚠️ 예외 사용자 파일이 존재하지 않음: {EXCEPTION_USERS_FILE}")
            return set()
    except Exception as e:
        print(f"❌ 예외 사용자 파일 로드 오류: {e}")
        import traceback
        traceback.print_exc()
        return set()

def save_exception_users(exception_users):
    """예외 사용자 목록을 JSON 파일에 저장"""
    try:
        print(f"💾 예외 사용자 파일 저장 시도: {len(exception_users)}명 - {list(exception_users)}")
        
        # 디렉토리 생성 (필요한 경우)
        os.makedirs(os.path.dirname(EXCEPTION_USERS_FILE) if os.path.dirname(EXCEPTION_USERS_FILE) else '.', exist_ok=True)
        
        data = {"exception_users": list(exception_users)}
        with open(EXCEPTION_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 예외 사용자 파일 저장 완료: {EXCEPTION_USERS_FILE}")
        return True
    except Exception as e:
        print(f"❌ 예외 사용자 파일 저장 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

def add_exception_user(user_id):
    """예외 사용자 추가"""
    try:
        print(f"➕ 예외 사용자 추가 시도: {user_id}")
        exception_users = load_exception_users()
        user_id_str = str(user_id)
        
        if user_id_str in exception_users:
            print(f"⚠️ 이미 예외 목록에 있는 사용자: {user_id}")
            return True  # 이미 있어도 성공으로 처리
            
        exception_users.add(user_id_str)
        result = save_exception_users(exception_users)
        
        if result:
            print(f"✅ 예외 사용자 추가 완료: {user_id}")
        else:
            print(f"❌ 예외 사용자 추가 실패: {user_id}")
            
        return result
    except Exception as e:
        print(f"❌ 예외 사용자 추가 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

def remove_exception_user(user_id):
    """예외 사용자 제거"""
    try:
        print(f"➖ 예외 사용자 제거 시도: {user_id}")
        exception_users = load_exception_users()
        user_id_str = str(user_id)
        
        if user_id_str not in exception_users:
            print(f"⚠️ 예외 목록에 없는 사용자: {user_id}")
            return True  # 없어도 성공으로 처리
            
        exception_users.discard(user_id_str)
        result = save_exception_users(exception_users)
        
        if result:
            print(f"✅ 예외 사용자 제거 완료: {user_id}")
        else:
            print(f"❌ 예외 사용자 제거 실패: {user_id}")
            
        return result
    except Exception as e:
        print(f"❌ 예외 사용자 제거 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

def is_exception_user(user_id):
    """사용자가 예외 목록에 있는지 확인"""
    try:
        exception_users = load_exception_users()
        user_id_str = str(user_id)
        is_exception = user_id_str in exception_users
        print(f"🔍 예외 사용자 확인: {user_id} -> {is_exception}")
        return is_exception
    except Exception as e:
        print(f"❌ 예외 사용자 확인 중 오류: {e}")
        return False

def get_exception_users_list():
    """예외 사용자 목록 반환"""
    try:
        exception_users = load_exception_users()
        users_list = list(exception_users)
        print(f"📋 예외 사용자 목록 반환: {len(users_list)}명 - {users_list}")
        return users_list
    except Exception as e:
        print(f"❌ 예외 사용자 목록 반환 중 오류: {e}")
        return []

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

# /국민확인 명령어를 위한 단일 사용자 처리 함수 (콘솔 로그 포함)
async def process_single_user_with_logs(member, session, rate_limiter):
    """단일 사용자 처리 (콘솔 로그 포함)"""
    try:
        print(f"🔍 /국민확인 명령어 실행: {member.display_name} ({member.id})")
        
        BASE_NATION = os.getenv("BASE_NATION", "Red_Mafia")
        
        # 3단계 API 호출로 사용자 정보 조회
        user_info = await get_user_info_by_name(session, member.id, rate_limiter)
        
        if not user_info["success"]:
            error_msg = user_info["error"]
            mc_id = user_info.get("mc_id", "알 수 없음")
            town = user_info.get("town", "")
            
            print(f"❌ /국민확인 API 조회 실패: {member.display_name} - {error_msg}")
            
            # 에러 메시지 구성
            if mc_id != "알 수 없음":
                if town:
                    error_detail = f"IGN: `{mc_id}`, 마을: `{town}` - {error_msg}"
                else:
                    error_detail = f"IGN: `{mc_id}` - {error_msg}"
            else:
                error_detail = error_msg
            
            return {"success": False, "message": f"⚠️ {member.mention} 인증 실패 - {error_detail}"}

        mc_id = user_info["mc_id"]
        town = user_info["town"]
        nation = user_info["nation"]
        
        print(f"📋 /국민확인 결과: {member.display_name} -> IGN: {mc_id}, 마을: {town}, 국가: {nation}")

        # 국가 검증 및 닉네임 처리
        if nation != BASE_NATION:
            # 다른 국가인 경우에도 닉네임은 업데이트
            await update_nickname_with_nation(member, mc_id, nation)
            print(f"⚠️ /국민확인: {member.display_name}는 다른 국가 ({nation}) 국민입니다.")
            
            return {"success": False, "message": f"⚠️ {member.mention} 인증 실패 - 국가 불일치 (IGN: `{mc_id}`, 마을: `{town}`, 국가: `{nation}`)"}

        # Red_Mafia 국민인 경우 기존 로직으로 역할 할당 및 닉네임 설정
        await update_nickname_with_nation(member, mc_id, nation)
        print(f"✅ /국민확인 성공: {member.display_name} -> {mc_id} ({town}, {nation})")
        
        return {"success": True, "message": f"✅ {member.mention} 인증 성공! IGN: `{mc_id}`, 마을: `{town}`, 국가: `{nation}`"}

    except Exception as e:
        print(f"❌ /국민확인 처리 중 오류 ({member.display_name}): {e}")
        return {"success": False, "message": f"❌ 처리 중 오류가 발생했습니다: {str(e)}"}

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

            # 예외 사용자 확인 - 중요한 부분!
            if is_exception_user(member.id):
                print(f"🚫 예외 사용자로 설정됨 - 처리 건너뜀: {member.display_name} ({member.id})")
                return True  # 예외 사용자는 성공으로 처리하여 더 이상 처리하지 않음

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
        exception_count = 0  # 예외 사용자 카운트 추가
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

                # 예외 사용자 체크를 여기서도 한 번 더 확인
                if is_exception_user(member.id):
                    exception_count += 1
                    print(f"🚫 예외 사용자 건너뜀: {member.display_name} ({member.id})")
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
            print(f"📊 대기열 처리 완료: 총 {processed_count}명 (성공: {success_count}, 실패: {len(failed_users)}, 예외제외: {exception_count})")

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
        exception_count = 0

        # 예외 사용자 목록 미리 로드
        exception_users_set = load_exception_users()
        print(f"🚫 예외 사용자 목록 로드: {len(exception_users_set)}명")

        with open(auto_roles_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f.readlines(), 1):
                role_id = line.strip()
                if not role_id or role_id.startswith("#"):
                    continue

                try:
                    role = guild.get_role(int(role_id))
                    if role:
                        role_added_count = 0
                        role_exception_count = 0
                        
                        for member in role.members:
                            # 예외 사용자인지 확인 (문자열로 비교)
                            if str(member.id) in exception_users_set:
                                role_exception_count += 1
                                exception_count += 1
                                print(f"🚫 예외 사용자 제외: {member.display_name} ({member.id})")
                                continue
                                
                            if not queue_manager.is_user_in_queue(member.id):
                                queue_manager.add_user(member.id)
                                role_added_count += 1
                                added_count += 1
                        
                        processed_roles += 1
                        print(f"🔄 자동 역할 처리: {role.name} - 총 {len(role.members)}명 중 {role_added_count}명 추가, {role_exception_count}명 예외 제외")
                    else:
                        print(f"⚠️ 역할 없음 (ID: {role_id}, 라인: {line_num})")
                except Exception as e:
                    print(f"❌ 역할 처리 오류 (ID: {role_id}, 라인: {line_num}): {e}")

        # 예외 대상 목록 출력
        if exception_users_set:
            exception_mentions = []
            for user_id in exception_users_set:
                member = guild.get_member(int(user_id))
                if member:
                    exception_mentions.append(member.display_name)
                else:
                    exception_mentions.append(f"<@{user_id}>")
            
            print(f"🚫 예외대상: {', '.join(exception_mentions)} (총 {len(exception_users_set)}명)")
        
        print(f"📋 자동 역할 처리 완료: {processed_roles}개 역할, 총 {added_count}명 추가, {exception_count}명 예외 제외")

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

# 새로운 함수들 추가

async def handle_exception_command(interaction, action, target_user=None):
    """예외설정 명령어 처리"""
    try:
        print(f"🔧 예외설정 명령어 처리: {action}, 대상: {target_user.display_name if target_user else '없음'}")
        
        if action == "목록":
            exception_users = get_exception_users_list()
            if not exception_users:
                await interaction.response.send_message("📋 예외 설정된 사용자가 없습니다.", ephemeral=True)
                return
            
            guild = interaction.guild
            user_mentions = []
            for user_id in exception_users:
                member = guild.get_member(int(user_id))
                if member:
                    user_mentions.append(f"{member.display_name} ({member.mention})")
                else:
                    user_mentions.append(f"<@{user_id}> (서버에 없음)")
            
            embed = discord.Embed(
                title="🚫 예외 설정 사용자 목록",
                description="\n".join(user_mentions),
                color=0xff6b6b
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        elif action == "추가":
            if not target_user:
                await interaction.response.send_message("❌ 추가할 사용자를 지정해주세요.", ephemeral=True)
                return
            
            print(f"➕ 예외 사용자 추가 시도: {target_user.display_name} ({target_user.id})")
            
            if add_exception_user(target_user.id):
                await interaction.response.send_message(
                    f"✅ {target_user.mention}을(를) 예외 목록에 추가했습니다.\n"
                    f"이제 이 사용자는 자동 역할 부여 및 대기열 처리에서 제외됩니다.", 
                    ephemeral=True
                )
                print(f"🚫 예외 사용자 추가 완료: {target_user.display_name} ({target_user.id})")
            else:
                await interaction.response.send_message("❌ 예외 목록 저장에 실패했습니다.", ephemeral=True)
                
        elif action == "제거":
            if not target_user:
                await interaction.response.send_message("❌ 제거할 사용자를 지정해주세요.", ephemeral=True)
                return
            
            print(f"➖ 예외 사용자 제거 시도: {target_user.display_name} ({target_user.id})")
            
            if remove_exception_user(target_user.id):
                await interaction.response.send_message(
                    f"✅ {target_user.mention}을(를) 예외 목록에서 제거했습니다.\n"
                    f"이제 이 사용자는 자동 역할 부여 및 대기열 처리에 포함됩니다.", 
                    ephemeral=True
                )
                print(f"✅ 예외 사용자 제거 완료: {target_user.display_name} ({target_user.id})")
            else:
                await interaction.response.send_message("❌ 예외 목록 저장에 실패했습니다.", ephemeral=True)
        
    except Exception as e:
        print(f"❌ 예외설정 명령어 처리 오류: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            await interaction.response.send_message("❌ 명령어 처리 중 오류가 발생했습니다.", ephemeral=True)
        except:
            # 이미 응답했을 수도 있으니 followup 시도
            try:
                await interaction.followup.send("❌ 명령어 처리 중 오류가 발생했습니다.", ephemeral=True)
            except:
                pass

async def handle_citizen_check_command(interaction, target_user):
    """국민확인 명령어 처리"""
    try:
        print(f"🔍 국민확인 명령어 처리: {target_user.display_name} ({target_user.id})")
        
        await interaction.response.defer()
        
        rate_limiter = RateLimiter()
        
        async with aiohttp.ClientSession() as session:
            result = await process_single_user_with_logs(target_user, session, rate_limiter)
            
            if result["success"]:
                embed = discord.Embed(
                    title="✅ 국민확인 성공",
                    description=result["message"],
                    color=0x00ff00
                )
            else:
                embed = discord.Embed(
                    title="❌ 국민확인 실패",
                    description=result["message"],
                    color=0xff0000
                )
            
            await interaction.followup.send(embed=embed)
            
    except Exception as e:
        print(f"❌ 국민확인 명령어 처리 오류: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            await interaction.followup.send("❌ 명령어 처리 중 오류가 발생했습니다.")
        except:
            pass

# 대기열에 사용자 추가할 때 예외 사용자 체크하는 헬퍼 함수
def add_users_to_queue_with_exception_check(user_ids, guild=None):
    """예외 사용자를 제외하고 대기열에 사용자들을 추가"""
    try:
        exception_users_set = load_exception_users()
        added_count = 0
        exception_count = 0
        
        for user_id in user_ids:
            if str(user_id) in exception_users_set:
                exception_count += 1
                if guild:
                    member = guild.get_member(user_id)
                    member_name = member.display_name if member else f"ID:{user_id}"
                    print(f"🚫 예외 사용자 제외: {member_name} ({user_id})")
                continue
                
            if not queue_manager.is_user_in_queue(user_id):
                queue_manager.add_user(user_id)
                added_count += 1
        
        print(f"📋 대기열 추가 완료: {added_count}명 추가, {exception_count}명 예외 제외")
        return {"added": added_count, "excluded": exception_count}
        
    except Exception as e:
        print(f"❌ 대기열 추가 중 오류: {e}")
        return {"added": 0, "excluded": 0}

# 역할 기반 대기열 추가 함수 (예외 사용자 체크 포함)
async def add_role_members_to_queue(guild, role_id):
    """특정 역할의 멤버들을 예외 사용자를 제외하고 대기열에 추가"""
    try:
        role = guild.get_role(role_id)
        if not role:
            print(f"❌ 역할을 찾을 수 없습니다 (ID: {role_id})")
            return {"added": 0, "excluded": 0, "error": "역할을 찾을 수 없음"}
        
        user_ids = [member.id for member in role.members]
        result = add_users_to_queue_with_exception_check(user_ids, guild)
        
        print(f"🔄 역할 '{role.name}' 처리: 총 {len(user_ids)}명 중 {result['added']}명 추가, {result['excluded']}명 예외 제외")
        return result
        
    except Exception as e:
        print(f"❌ 역할 멤버 대기열 추가 중 오류: {e}")
        return {"added": 0, "excluded": 0, "error": str(e)}

# 기존 export 함수들은 그대로 유지
async def get_user_info_by_name_export(session, discord_id, rate_limiter):
    return await get_user_info_by_name(session, discord_id, rate_limiter)

async def process_single_user_with_logs_export(member, session, rate_limiter):
    return await process_single_user_with_logs(member, session, rate_limiter)
