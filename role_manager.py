import discord
import os

def get_env_int(key, default=None):
    """환경변수를 안전하게 int로 변환"""
    value = os.getenv(key)
    if value is None:
        if default is not None:
            return default
        raise ValueError(f"환경변수 {key}가 설정되지 않았습니다.")
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"환경변수 {key}의 값 '{value}'을(를) 정수로 변환할 수 없습니다.")

try:
    SUCCESS_ROLE_ID = get_env_int("SUCCESS_ROLE_ID")
    print(f"✅ SUCCESS_ROLE_ID: {SUCCESS_ROLE_ID}")
except ValueError as e:
    print(f"❌ role_manager.py 환경변수 오류: {e}")
    SUCCESS_ROLE_ID = None

async def assign_role_and_nick(member: discord.Member, nickname: str, nation: str = None):
    """역할 부여 및 닉네임 설정 (국가 정보 포함)"""
    if SUCCESS_ROLE_ID is None:
        print(f"❌ SUCCESS_ROLE_ID가 설정되지 않아 역할을 부여할 수 없습니다.")
        return
        
    try:
        # 역할 부여 (Red_Mafia 소속인 경우에만)
        role = member.guild.get_role(SUCCESS_ROLE_ID)
        if role and nation == "Red_Mafia":
            if role not in member.roles:
                await member.add_roles(role)
                print(f"✅ {member.display_name}에게 역할 '{role.name}' 부여")
            else:
                print(f"ℹ️ {member.display_name}는 이미 '{role.name}' 역할을 가지고 있습니다.")
        elif not role:
            print(f"❌ 역할을 찾을 수 없습니다 (ID: {SUCCESS_ROLE_ID})")
            
        # 닉네임 설정 (국가 유무에 따라)
        if nation:
            new_nickname = f"{nickname} ㅣ {nation}"
        else:
            new_nickname = f"{nickname} ㅣ 국가 없음"
            
        # 닉네임이 32자를 초과하지 않도록 제한
        if len(new_nickname) > 32:
            # 마크 닉네임 부분을 줄여서 맞춤
            max_nickname_length = 32 - len(" ㅣ ") - len(nation if nation else "국가 없음")
            if max_nickname_length > 0:
                truncated_nickname = nickname[:max_nickname_length]
                new_nickname = f"{truncated_nickname} ㅣ {nation if nation else '국가 없음'}"
            else:
                new_nickname = nickname[:32]  # 최소한 마크 닉네임만
        
        if member.display_name != new_nickname:
            await member.edit(nick=new_nickname)
            print(f"✅ {member.display_name} 닉네임을 '{new_nickname}'으로 변경")
        else:
            print(f"ℹ️ {member.display_name}의 닉네임이 이미 '{new_nickname}'입니다.")
            
    except discord.Forbidden:
        print(f"❌ {member.display_name}에 대한 권한이 없습니다 (역할 부여/닉네임 변경 실패)")
    except discord.HTTPException as e:
        print(f"❌ Discord API 오류 ({member.display_name}): {e}")
    except Exception as e:
        print(f"❌ 예상치 못한 오류 ({member.display_name}): {e}")