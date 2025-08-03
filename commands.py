import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal, List
import aiohttp
import os
import time

# 안전한 import 처리
try:
    from queue_manager import queue_manager
    print("✅ queue_manager 로드 성공")
except ImportError as e:
    print(f"❌ queue_manager 로드 실패: {e}")
    # 더미 queue_manager 클래스 생성
    class DummyQueueManager:
        def get_queue_size(self): return 0
        def is_processing(self): return False
        def add_user(self, user_id): pass
        def clear_queue(self): return 0
    queue_manager = DummyQueueManager()

try:
    from exception_manager import exception_manager
    print("✅ exception_manager 로드 성공")
except ImportError as e:
    print(f"❌ exception_manager 로드 실패: {e}")
    # 더미 exception_manager 클래스 생성
    class DummyExceptionManager:
        def get_exceptions(self): return []
        def add_exception(self, user_id): return True
        def remove_exception(self, user_id): return True
    exception_manager = DummyExceptionManager()

# callsign_manager 안전하게 import
try:
    from callsign_manager import callsign_manager, validate_callsign, get_user_display_info
    print("✅ callsign_manager 모듈 로드됨 (commands.py)")
    CALLSIGN_ENABLED = True
except ImportError as e:
    print(f"⚠️ callsign_manager 모듈을 로드할 수 없습니다 (commands.py): {e}")
    print("📝 콜사인 기능이 비활성화됩니다.")
    callsign_manager = None
    CALLSIGN_ENABLED = False
    
    # 대체 함수 정의
    def validate_callsign(callsign: str):
        return False, "콜사인 기능이 비활성화됨"
    
    def get_user_display_info(user_id: int, mc_id: str = None, nation: str = None):
        if nation:
            return f"{mc_id} ㅣ {nation}"
        return mc_id or 'Unknown'

# town_role_manager 안전하게 import
try:
    from town_role_manager import town_role_manager, get_towns_in_nation
    print("✅ town_role_manager 모듈 로드됨 (commands.py)")
    TOWN_ROLE_ENABLED = True
except ImportError as e:
    print(f"⚠️ town_role_manager 모듈을 로드할 수 없습니다 (commands.py): {e}")
    print("📝 마을 역할 기능이 비활성화됩니다.")
    town_role_manager = None
    TOWN_ROLE_ENABLED = False
    
    # 대체 함수 정의 - 개선된 버전
    async def get_towns_in_nation(nation_name: str):
        """대체 함수: town_role_manager가 없을 때 기본 마을 목록 반환"""
        print(f"⚠️ town_role_manager가 없어서 대체 함수 사용: {nation_name}")
        try:
            api_base = MC_API_BASE or "https://api.planetearth.kr"
            
            async with aiohttp.ClientSession() as session:
                url = f"{api_base}/nation?name={nation_name}"
                print(f"🔍 대체 API 호출: {url}")
                
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as response:
                    if response.status != 200:
                        print(f"❌ API 응답 오류: HTTP {response.status}")
                        return ["Seoul", "Busan", "Incheon"]  # 기본 테스트 마을
                    
                    data = await response.json()
                    if not data.get('data') or not data['data']:
                        print(f"❌ 국가 데이터 없음: {nation_name}")
                        return ["Seoul", "Busan", "Incheon"]  # 기본 테스트 마을
                    
                    nation_data = data['data'][0]
                    towns = nation_data.get('towns', [])
                    
                    if not towns:
                        print(f"ℹ️ {nation_name}에 마을이 없습니다.")
                        return ["Seoul", "Busan", "Incheon"]  # 기본 테스트 마을
                    
                    print(f"✅ {nation_name} 마을 목록: {len(towns)}개")
                    return towns
                    
        except Exception as e:
            print(f"❌ 대체 함수에서 오류: {e}")
            # 최후의 대체 마을 목록
            return ["Seoul", "Busan", "Incheon", "Daegu", "Daejeon", "Gwangju", "Ulsan"]

# 환경변수 로드 - 기본값 설정
MC_API_BASE = os.getenv("MC_API_BASE", "https://api.planetearth.kr")
BASE_NATION = os.getenv("BASE_NATION", "Red_Mafia")
SUCCESS_ROLE_ID = int(os.getenv("SUCCESS_ROLE_ID", "0"))
SUCCESS_ROLE_ID_OUT = int(os.getenv("SUCCESS_ROLE_ID_OUT", "0"))

# verify_town_in_nation 함수 추가
async def verify_town_in_nation(town_name: str, nation_name: str) -> bool:
    """마을이 특정 국가에 속하는지 확인하는 함수"""
    try:
        towns = await get_towns_in_nation(nation_name)
        return town_name in towns
    except Exception as e:
        print(f"❌ 마을 검증 오류: {e}")
        return False

# 자동완성 함수를 독립적으로 정의 - 개선된 버전
async def town_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    """마을 이름 자동완성 - 개선된 버전"""
    try:
        print(f"🔍 자동완성 요청: current='{current}', user={interaction.user.display_name}")
        
        if not TOWN_ROLE_ENABLED:
            print("⚠️ TOWN_ROLE_ENABLED가 False입니다.")
            return [app_commands.Choice(name="마을 역할 기능이 비활성화됨", value="disabled")]
            
        # 캐시된 마을 목록이 있다면 사용 (빠른 응답을 위해)
        if hasattr(town_autocomplete, '_cached_towns') and hasattr(town_autocomplete, '_cache_time'):
            current_time = time.time()
            # 캐시가 5분 이내라면 사용
            if current_time - town_autocomplete._cache_time < 300:
                print(f"📦 캐시된 마을 목록 사용: {len(town_autocomplete._cached_towns)}개")
                towns = town_autocomplete._cached_towns
            else:
                towns = None
        else:
            towns = None
        
        # 캐시가 없거나 만료된 경우 새로 가져오기
        if towns is None:
            print(f"🌐 API에서 마을 목록 가져오는 중... (국가: {BASE_NATION})")
            try:
                # 타임아웃을 짧게 설정 (자동완성은 3초 제한)
                towns = await get_towns_in_nation(BASE_NATION)
                print(f"✅ API에서 {len(towns) if towns else 0}개 마을 가져옴")
                
                # 캐시 저장
                if towns:
                    town_autocomplete._cached_towns = towns
                    town_autocomplete._cache_time = time.time()
                    print(f"💾 마을 목록 캐시됨")
                    
            except Exception as api_error:
                print(f"❌ API 호출 실패: {api_error}")
                # API 실패 시 기본 안내 메시지
                return [app_commands.Choice(name="마을 목록을 불러올 수 없습니다", value="api_error")]
        
        if not towns:
            print(f"⚠️ {BASE_NATION}에 마을이 없습니다.")
            return [app_commands.Choice(name=f"{BASE_NATION}에 마을이 없습니다", value="no_towns")]
        
        print(f"🏘️ 총 {len(towns)}개 마을 발견")
        
        # 현재 입력값으로 필터링
        if current:
            # 대소문자 구분 없이 검색
            current_lower = current.lower()
            filtered_towns = []
            
            for town in towns:
                town_lower = town.lower()
                # 시작하는 마을을 먼저, 포함하는 마을을 나중에
                if town_lower.startswith(current_lower):
                    filtered_towns.insert(0, town)
                elif current_lower in town_lower:
                    filtered_towns.append(town)
            
            print(f"🔍 '{current}' 검색 결과: {len(filtered_towns)}개 마을")
        else:
            # 입력이 없으면 처음 25개 마을 반환
            filtered_towns = towns[:25]
            print(f"📋 전체 마을 목록에서 처음 {len(filtered_towns)}개 반환")
        
        # Discord 제한인 25개까지만 반환
        limited_towns = filtered_towns[:25]
        
        # Choice 객체 생성
        choices = []
        for town in limited_towns:
            # 마을 이름이 너무 길면 잘라서 표시
            display_name = town if len(town) <= 100 else town[:97] + "..."
            choices.append(app_commands.Choice(name=display_name, value=town))
        
        print(f"✅ 자동완성 완료: {len(choices)}개 선택지 반환")
        return choices
        
    except Exception as e:
        print(f"💥 자동완성 함수에서 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        
        # 오류 시 기본 안내 메시지 반환
        return [app_commands.Choice(name="오류가 발생했습니다. 관리자에게 문의하세요", value="error")]

class TownRoleConfirmView(discord.ui.View):
    """마을 역할 연동 확인 버튼 뷰"""
    
    def __init__(self, town_name: str, role_id: int, role_obj: discord.Role, is_valid_town: bool):
        super().__init__(timeout=60.0)  # 60초 타임아웃
        self.town_name = town_name
        self.role_id = role_id
        self.role_obj = role_obj
        self.is_valid_town = is_valid_town
        self.result = None
    
    @discord.ui.button(label="✅ 연동하기", style=discord.ButtonStyle.green)
    async def confirm_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        """연동 확인 버튼"""
        self.result = "confirm"
        
        # 매핑 추가
        if TOWN_ROLE_ENABLED and town_role_manager:
            town_role_manager.add_mapping(self.town_name, self.role_id)
        
        embed = discord.Embed(
            title="✅ 마을-역할 연동 완료",
            description=f"**{self.town_name}** 마을이 {self.role_obj.mention} 역할과 연동되었습니다.",
            color=0x00ff00
        )
        
        embed.add_field(
            name="📋 연동 정보",
            value=f"• **마을:** {self.town_name}\n• **역할:** {self.role_obj.mention}\n• **역할 ID:** {self.role_id}",
            inline=False
        )
        
        if not self.is_valid_town:
            embed.add_field(
                name="⚠️ 참고사항",
                value=f"이 마을은 **{BASE_NATION}** 소속이 아닐 수 있습니다.\n관리자가 수동으로 연동을 승인했습니다.",
                inline=False
            )
        
        # 버튼 비활성화
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()
    
    @discord.ui.button(label="❌ 취소하기", style=discord.ButtonStyle.red)
    async def cancel_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        """연동 취소 버튼"""
        self.result = "cancel"
        
        embed = discord.Embed(
            title="❌ 마을-역할 연동 취소",
            description=f"**{self.town_name}** 마을과 {self.role_obj.mention} 역할의 연동이 취소되었습니다.",
            color=0xff6600
        )
        
        # 버튼 비활성화
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()
    
    async def on_timeout(self):
        """타임아웃 시 처리"""
        for item in self.children:
            item.disabled = True

class SlashCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def is_admin(interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator

    async def send_long_message_via_webhook(self, interaction: discord.Interaction, embeds_data):
        """웹훅을 통해 긴 메시지를 여러 개로 나누어 전송"""
        try:
            # 웹훅 생성
            webhook = await interaction.channel.create_webhook(name="국민확인봇")
            
            # 각 임베드 데이터를 개별 메시지로 전송
            for embed_data in embeds_data:
                embed = discord.Embed(
                    title=embed_data["title"],
                    color=embed_data["color"]
                )
                
                for field in embed_data["fields"]:
                    embed.add_field(
                        name=field["name"],
                        value=field["value"],
                        inline=field.get("inline", False)
                    )
                
                await webhook.send(embed=embed)
            
            # 웹훅 삭제
            await webhook.delete()
            
        except Exception as e:
            # 웹훅 실패 시 기존 방식으로 폴백
            print(f"웹훅 전송 실패: {e}")
            embed = discord.Embed(
                title="🛡️ 국민 확인 결과 (요약)",
                description="전체 결과가 너무 길어서 요약본만 표시됩니다.",
                color=0x00bfff
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="도움말", description="봇의 모든 명령어를 확인합니다")
    async def 도움말(self, interaction: discord.Interaction):
        """봇의 모든 명령어와 설명을 표시 - 개선된 버전"""
        
        # 관리자 권한 확인
        is_admin = interaction.user.guild_permissions.administrator
        
        # 메인 임베드 생성
        embed = discord.Embed(
            title="📖 국민확인봇 명령어 가이드",
            description=f"안녕하세요 {interaction.user.mention}님! 🎉\n사용 가능한 명령어들을 확인해보세요.",
            color=0x2f3136
        )
        
        # 썸네일 추가 (봇 아바타)
        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)
        
        # 일반 사용자 명령어
        user_commands_info = {
            "확인": {
                "emoji": "✅",
                "desc": "자신의 국적을 확인하고 역할을 받습니다",
                "usage": "`/확인`",
                "note": "마인크래프트 계정이 연동되어 있어야 합니다"
            },
            "콜사인": {
                "emoji": "🏷️",
                "desc": "개인 콜사인을 설정합니다",
                "usage": "`/콜사인 텍스트:콜사인이름`",
                "note": "최대 20자, 국가명 대신 표시됩니다" if CALLSIGN_ENABLED else "콜사인 기능이 비활성화됨"
            },
            "도움말": {
                "emoji": "📖",
                "desc": "봇의 모든 명령어를 확인합니다",
                "usage": "`/도움말`",
                "note": "언제든지 사용 가능합니다"
            }
        }
        
        user_cmd_text = ""
        for cmd_name, info in user_commands_info.items():
            user_cmd_text += f"{info['emoji']} **{info['usage']}**\n"
            user_cmd_text += f"   └ {info['desc']}\n"
            user_cmd_text += f"   └ 💡 *{info['note']}*\n\n"
        
        embed.add_field(
            name="👥 일반 사용자 명령어",
            value=user_cmd_text.strip(),
            inline=False
        )
        
        # 관리자 명령어 - 카테고리별로 분류
        if is_admin:
            # 기본 관리 명령어
            basic_admin_text = ""
            basic_admin_commands = {
                "테스트": "봇의 기본 기능을 테스트합니다",
                "스케줄확인": "자동 실행 스케줄 정보를 확인합니다"
            }
            
            for cmd_name, desc in basic_admin_commands.items():
                basic_admin_text += f"🔧 **`/{cmd_name}`** - {desc}\n"
            
            embed.add_field(
                name="🛠️ 기본 관리 명령어",
                value=basic_admin_text,
                inline=True
            )
            
            # 사용자 관리 명령어
            user_mgmt_text = ""
            user_mgmt_commands = {
                "국민확인": "사용자들의 국적을 확인합니다",
                "예외설정": "자동실행 예외 대상을 관리합니다"
            }
            
            # 콜사인 관리 추가 (활성화된 경우)
            if CALLSIGN_ENABLED:
                user_mgmt_commands["콜사인관리"] = "사용자 콜사인을 관리합니다"
            
            for cmd_name, desc in user_mgmt_commands.items():
                user_mgmt_text += f"👤 **`/{cmd_name}`** - {desc}\n"
            
            embed.add_field(
                name="👥 사용자 관리",
                value=user_mgmt_text,
                inline=True
            )
            
            # 대기열 관리 명령어
            queue_mgmt_text = ""
            queue_mgmt_commands = {
                "대기열상태": "현재 대기열 상태를 확인합니다",
                "대기열초기화": "대기열을 모두 비웁니다",
                "자동실행시작": "자동 역할 부여를 수동으로 시작합니다",
                "자동실행": "자동 등록할 역할을 설정합니다"
            }
            
            for cmd_name, desc in queue_mgmt_commands.items():
                queue_mgmt_text += f"📋 **`/{cmd_name}`** - {desc}\n"
            
            embed.add_field(
                name="📋 대기열 관리",
                value=queue_mgmt_text,
                inline=False
            )
            
            # 마을 역할 관리 (활성화된 경우에만)
            if TOWN_ROLE_ENABLED:
                town_mgmt_text = (
                    "🏘️ **`/마을역할 기능:추가`** - 마을과 역할을 연동합니다\n"
                    "🏘️ **`/마을역할 기능:제거`** - 마을 역할 연동을 해제합니다\n"
                    "🏘️ **`/마을역할 기능:목록`** - 연동된 마을-역할 목록을 확인합니다\n"
                    "🏘️ **`/마을역할 기능:마을목록`** - 마을 연동 가이드를 확인합니다\n"
                    "🧪 **`/마을테스트`** - 마을 검증 기능을 테스트합니다"
                )
                
                embed.add_field(
                    name="🏘️ 마을 역할 관리",
                    value=town_mgmt_text,
                    inline=False
                )
                
                # 마을 역할 기능 설명 추가
                embed.add_field(
                    name="💡 마을 역할 연동 방법",
                    value="1. **정확한 마을 이름** 입력\n"
                          "2. **자동 검증** 후 결과 확인\n"
                          "3. **버튼 선택**으로 연동 진행/취소\n"
                          "4. **미검증 마을**도 수동 연동 가능",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🏘️ 마을 역할 관리",
                    value="🔴 **비활성화됨** - town_role_manager 모듈이 필요합니다.",
                    inline=False
                )
            
            # 콜사인 기능 설명 (활성화된 경우에만)
            if CALLSIGN_ENABLED:
                callsign_text = (
                    "🏷️ **`/콜사인 텍스트:콜사인이름`** - 개인 콜사인을 설정합니다\n"
                    "🏷️ **`/콜사인관리 기능:목록`** - 설정된 콜사인 목록을 확인합니다\n"
                    "🏷️ **`/콜사인관리 기능:제거`** - 사용자의 콜사인을 제거합니다\n"
                    "🏷️ **`/콜사인관리 기능:초기화`** - 모든 콜사인을 삭제합니다"
                )
                
                embed.add_field(
                    name="🏷️ 콜사인 관리",
                    value=callsign_text,
                    inline=False
                )
                
                # 콜사인 기능 설명 추가
                embed.add_field(
                    name="💡 콜사인 사용법",
                    value="1. **개인 콜사인**: `/콜사인 텍스트:나만의콜사인`\n"
                          "2. **자동 적용**: 국민 확인 시 국가명 대신 콜사인 사용\n"
                          "3. **길이 제한**: 최대 20자까지 설정 가능\n"
                          "4. **우선순위**: 콜사인 > 국가명 순으로 표시",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🏷️ 콜사인 관리",
                    value="🔴 **비활성화됨** - callsign_manager 모듈이 필요합니다.",
                    inline=False
                )
        else:
            # 관리자가 아닌 경우
            total_admin_commands = 11 + (1 if CALLSIGN_ENABLED else 0) + (5 if TOWN_ROLE_ENABLED else 0)
            embed.add_field(
                name="🛡️ 관리자 전용 명령어",
                value=f"🔒 관리자 전용 명령어 **{total_admin_commands}개**가 있습니다.\n"
                      f"관리자 권한이 필요합니다.",
                inline=False
            )
        
        # 봇 상태 정보
        queue_size = queue_manager.get_queue_size()
        is_processing = queue_manager.is_processing()
        processing_status = "🔄 처리 중" if is_processing else "⏸️ 대기 중"
        
        # 마을 역할 상태 추가 (안전하게)
        try:
            town_mapping_count = town_role_manager.get_mapping_count() if TOWN_ROLE_ENABLED and town_role_manager else 0
        except:
            town_mapping_count = 0
        
        # 콜사인 상태 추가 (안전하게)
        try:
            callsign_count = callsign_manager.get_callsign_count() if CALLSIGN_ENABLED and callsign_manager else 0
        except:
            callsign_count = 0
        
        status_text = (
            f"🌐 **API 상태**: {'🟢 연결됨' if MC_API_BASE else '🔴 설정 필요'}\n"
            f"🏴 **기본 국가**: {BASE_NATION}\n"
            f"🏘️ **마을 역할**: {'🟢 활성화' if TOWN_ROLE_ENABLED else '🔴 비활성화'}\n"
            f"🏷️ **콜사인 기능**: {'🟢 활성화' if CALLSIGN_ENABLED else '🔴 비활성화'}\n"
            f"🎯 **연동된 마을**: {town_mapping_count}개\n"
            f"🏷️ **설정된 콜사인**: {callsign_count}개\n"
            f"📋 **대기열**: {queue_size}명 ({processing_status})"
        )
        
        embed.add_field(
            name="📊 봇 상태",
            value=status_text,
            inline=True
        )
        
        # 사용 팁
        tips_text = (
            "💡 `/확인` 명령어로 언제든 역할을 다시 받을 수 있어요!\n"
            f"💡 {'`/콜사인`으로 개인 콜사인을 설정하세요.' if CALLSIGN_ENABLED else '콜사인 기능이 비활성화되어 있습니다.'}\n"
            "💡 마인크래프트 계정 연동이 필요합니다.\n"
            f"💡 {'관리자는 `/마을역할`로 마을 역할을 관리하세요.' if TOWN_ROLE_ENABLED else ''}\n"
            "💡 문제가 있다면 관리자에게 문의하세요."
        )
        
        embed.add_field(
            name="💡 사용 팁",
            value=tips_text,
            inline=True
        )
        
        # 푸터 정보
        total_commands = len(self.bot.tree.get_commands())
        embed.set_footer(
            text=f"🤖 {self.bot.user.name} • 총 {total_commands}개 명령어 • 권한: {'관리자' if is_admin else '일반 사용자'}",
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )
        
        # 현재 시간 추가
        import datetime
        embed.timestamp = datetime.datetime.now()
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="콜사인", description="개인 콜사인을 설정합니다")
    @app_commands.describe(텍스트="설정할 콜사인 (최대 20자)")
    async def 콜사인(self, interaction: discord.Interaction, 텍스트: str):
        """사용자 콜사인 설정"""
        
        # 콜사인 기능이 비활성화된 경우
        if not CALLSIGN_ENABLED:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ 기능 비활성화",
                    description="콜사인 기능이 비활성화되어 있습니다.\n"
                              "`callsign_manager.py` 파일이 필요합니다.",
                    color=0xff0000
                ),
                ephemeral=True
            )
            return
        
        await interaction.response.defer(thinking=True)
        
        user_id = interaction.user.id
        callsign = 텍스트.strip()
        
        # 콜사인 유효성 검사
        is_valid, message = validate_callsign(callsign)
        if not is_valid:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ 콜사인 설정 실패",
                    description=f"**오류:** {message}",
                    color=0xff0000
                ),
                ephemeral=True
            )
            return
        
        # 사용자의 국가 정보 확인
        user_nation = None
        mc_id = None
        
        try:
            async with aiohttp.ClientSession() as session:
                # 1단계: 디스코드 ID → 마크 ID
                url1 = f"{MC_API_BASE}/discord?discord={user_id}"
                async with session.get(url1, timeout=aiohttp.ClientTimeout(total=10)) as r1:
                    if r1.status == 200:
                        data1 = await r1.json()
                        if data1.get('data') and data1['data']:
                            mc_id = data1['data'][0].get('name')
                            if mc_id:
                                time.sleep(2)
                                
                                # 2단계: 마크 ID → 마을
                                url2 = f"{MC_API_BASE}/resident?name={mc_id}"
                                async with session.get(url2, timeout=aiohttp.ClientTimeout(total=10)) as r2:
                                    if r2.status == 200:
                                        data2 = await r2.json()
                                        if data2.get('data') and data2['data']:
                                            town = data2['data'][0].get('town')
                                            if town:
                                                time.sleep(2)
                                                
                                                # 3단계: 마을 → 국가
                                                url3 = f"{MC_API_BASE}/town?name={town}"
                                                async with session.get(url3, timeout=aiohttp.ClientTimeout(total=10)) as r3:
                                                    if r3.status == 200:
                                                        data3 = await r3.json()
                                                        if data3.get('data') and data3['data']:
                                                            user_nation = data3['data'][0].get('nation')
        except Exception as e:
            print(f"⚠️ 콜사인 설정 시 국가 확인 오류: {e}")
        
        # 기존 콜사인 확인
        old_callsign = callsign_manager.get_callsign(user_id)
        
        try:
            # 콜사인 설정
            callsign_manager.set_callsign(user_id, callsign)
            
            # 닉네임 변경 시도 (BASE_NATION 국민인 경우에만)
            nickname_changed = False
            nickname_change_msg = ""
            
            if user_nation == BASE_NATION and mc_id:
                try:
                    member = interaction.guild.get_member(user_id)
                    if member:
                        new_nickname = f"{mc_id} ㅣ {callsign}"
                        await member.edit(nick=new_nickname)
                        nickname_changed = True
                        nickname_change_msg = f"• 닉네임이 **``{new_nickname}``**로 즉시 변경됨"
                        print(f"✅ 콜사인 설정 후 즉시 닉네임 변경: {new_nickname}")
                except discord.Forbidden:
                    nickname_change_msg = "• ⚠️ 닉네임 변경 권한 없음"
                except Exception as e:
                    nickname_change_msg = f"• ⚠️ 닉네임 변경 실패: {str(e)[:50]}"
            elif user_nation and user_nation != BASE_NATION:
                nickname_change_msg = f"• ℹ️ {BASE_NATION} 국민이 아니므로 닉네임 변경 안됨"
            elif not user_nation:
                nickname_change_msg = "• ⚠️ 국가 정보 확인 불가로 닉네임 변경 안됨"
            
            # 응답 메시지 생성
            if old_callsign:
                embed = discord.Embed(
                    title="✅ 콜사인 변경 완료",
                    description=f"콜사인이 **{callsign}**로 변경되었습니다.",
                    color=0x00ff00
                )
                embed.add_field(
                    name="📋 변경 내역",
                    value=f"• **이전:** {old_callsign}\n• **현재:** {callsign}",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="✅ 콜사인 설정 완료",
                    description=f"콜사인이 **{callsign}**로 설정되었습니다.",
                    color=0x00ff00
                )
            
            # 닉네임 변경 결과 추가
            if nickname_change_msg:
                embed.add_field(
                    name="🔄 닉네임 변경",
                    value=nickname_change_msg,
                    inline=False
                )
            
            # 국가별 안내 메시지
            if user_nation == BASE_NATION:
                if nickname_changed:
                    embed.add_field(
                        name="💡 안내",
                        value=f"• {BASE_NATION} 국민이므로 콜사인이 즉시 적용되었습니다.\n"
                              "• 마인크래프트 정보가 변경되면 `/확인` 명령어를 사용하세요.",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="💡 안내",
                        value=f"• {BASE_NATION} 국민이므로 다음 `/확인` 시 콜사인이 적용됩니다.\n"
                              "• `/확인` 명령어로 즉시 적용할 수 있습니다.",
                        inline=False
                    )
            elif user_nation:
                embed.add_field(
                    name="💡 안내",
                    value=f"• 현재 **{user_nation}** 소속으로 확인됩니다.\n"
                          f"• {BASE_NATION} 국민이 아니므로 콜사인이 닉네임에 적용되지 않습니다.\n"
                          f"• {BASE_NATION}으로 이주 후 `/확인` 명령어를 사용하세요.",
                    inline=False
                )
            else:
                embed.add_field(
                    name="💡 안내",
                    value="• 국가 정보를 확인할 수 없습니다.\n"
                          "• 마인크래프트 계정 연동을 확인하고 `/확인` 명령어를 사용하세요.\n"
                          f"• {BASE_NATION} 국민인 경우에만 콜사인이 적용됩니다.",
                    inline=False
                )
            
            # 콜사인 형식 안내
            if user_nation == BASE_NATION:
                embed.add_field(
                    name="🏷️ 적용된 닉네임 형식",
                    value=f"**형식:** `{mc_id or '마인크래프트닉네임'} ㅣ {callsign}`",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🏷️ 닉네임 형식 (참고용)",
                    value=f"**{BASE_NATION} 국민 시:** `마인크래프트닉네임 ㅣ {callsign}`\n"
                          f"**현재 ({user_nation or '확인불가'}):** `마인크래프트닉네임 ㅣ {user_nation or '국가명'}`",
                    inline=False
                )
            
            print(f"✅ 콜사인 설정: {interaction.user.display_name} ({user_id}) -> {callsign} (국가: {user_nation})")
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 오류 발생",
                description=f"콜사인 설정 중 오류가 발생했습니다.\n{str(e)}",
                color=0xff0000
            )
            print(f"❌ 콜사인 설정 오류: {e}")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="콜사인관리", description="콜사인을 관리합니다 (관리자 전용)")
    @app_commands.describe(
        기능="수행할 작업을 선택하세요",
        대상="(제거 시만) 대상 사용자 멘션 또는 사용자 ID"
    )
    @app_commands.check(is_admin)
    async def 콜사인관리(
        self,
        interaction: discord.Interaction,
        기능: Literal["목록", "제거", "초기화"],
        대상: str = None
    ):
        """콜사인 관리 (관리자 전용)"""
        
        # 콜사인 기능이 비활성화된 경우
        if not CALLSIGN_ENABLED:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ 기능 비활성화",
                    description="콜사인 기능이 비활성화되어 있습니다.\n"
                              "`callsign_manager.py` 파일이 필요합니다.",
                    color=0xff0000
                ),
                ephemeral=True
            )
            return
        
        if 기능 == "목록":
            # 콜사인 목록 표시
            try:
                all_callsigns = callsign_manager.get_all_callsigns()
                
                embed = discord.Embed(
                    title="📋 콜사인 목록",
                    color=0x00bfff
                )
                
                if not all_callsigns:
                    embed.description = "현재 설정된 콜사인이 없습니다."
                else:
                    embed.description = f"총 **{len(all_callsigns)}개**의 콜사인이 설정되어 있습니다."
                    
                    # 10개씩 나누어서 표시
                    items = list(all_callsigns.items())
                    for i in range(0, len(items), 10):
                        chunk = items[i:i+10]
                        field_items = []
                        
                        for user_id, callsign in chunk:
                            field_items.append(f"• <@{user_id}> → **{callsign}**")
                        
                        embed.add_field(
                            name=f"콜사인 목록 ({i+1}-{min(i+10, len(items))})",
                            value="\n".join(field_items),
                            inline=False
                        )
                        
            except Exception as e:
                embed = discord.Embed(
                    title="❌ 오류",
                    description=f"콜사인 목록을 가져오는 중 오류가 발생했습니다.\n{str(e)}",
                    color=0xff0000
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        elif 기능 == "초기화":
            # 모든 콜사인 삭제
            try:
                cleared_count = callsign_manager.clear_all_callsigns()
                
                embed = discord.Embed(
                    title="🧹 콜사인 초기화 완료",
                    description=f"**{cleared_count}개**의 콜사인이 모두 삭제되었습니다.",
                    color=0xff6600
                )
                
                embed.add_field(
                    name="⚠️ 주의사항",
                    value="삭제된 콜사인은 복구할 수 없습니다.\n"
                          "사용자들이 다시 설정해야 합니다.",
                    inline=False
                )
                
            except Exception as e:
                embed = discord.Embed(
                    title="❌ 오류 발생",
                    description=f"콜사인 초기화 중 오류가 발생했습니다.\n{str(e)}",
                    color=0xff0000
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        elif 기능 == "제거":
            # 특정 사용자 콜사인 제거
            if not 대상:
                await interaction.response.send_message(
                    "❌ 제거 기능을 사용할 때는 대상을 입력해야 합니다.\n"
                    "예: `/콜사인관리 기능:제거 대상:@사용자` 또는 `/콜사인관리 기능:제거 대상:123456789`",
                    ephemeral=True
                )
                return
            
            # 멘션 형식 처리
            target_clean = 대상.replace('<@', '').replace('>', '').replace('!', '')
            
            try:
                user_id = int(target_clean)
            except ValueError:
                await interaction.response.send_message(
                    "❌ 올바른 사용자 ID 또는 멘션을 입력해주세요.\n"
                    "예: `@사용자` 또는 `123456789`",
                    ephemeral=True
                )
                return
            
            # 사용자 존재 확인 (선택사항)
            guild = interaction.guild
            member = guild.get_member(user_id)
            user_mention = member.mention if member else f"<@{user_id}>"
            user_name = member.display_name if member else f"ID: {user_id}"
            
            # 콜사인 제거
            try:
                old_callsign = callsign_manager.get_callsign(user_id)
                
                if callsign_manager.remove_callsign(user_id):
                    embed = discord.Embed(
                        title="✅ 콜사인 제거 완료",
                        description=f"{user_mention}님의 콜사인을 제거했습니다.",
                        color=0x00ff00
                    )
                    
                    if old_callsign:
                        embed.add_field(
                            name="📋 제거된 콜사인",
                            value=f"**{old_callsign}**",
                            inline=False
                        )
                else:
                    embed = discord.Embed(
                        title="⚠️ 콜사인 없음",
                        description=f"{user_mention}님은 콜사인을 설정하지 않았습니다.",
                        color=0xffaa00
                    )
                    
            except Exception as e:
                embed = discord.Embed(
                    title="❌ 오류 발생",
                    description=f"콜사인 제거 중 오류가 발생했습니다.\n{str(e)}",
                    color=0xff0000
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="마을역할", description="마을과 역할을 연동합니다")
    @app_commands.describe(
        기능="수행할 작업을 선택하세요",
        역할="(추가 시만) 연동할 역할을 멘션하거나 역할 ID 입력",
        마을="(추가 시만) 연동할 마을 이름 (정확한 이름 입력)"
    )
    @app_commands.autocomplete(마을=town_autocomplete)
    @app_commands.check(is_admin)
    async def 마을역할(
        self,
        interaction: discord.Interaction,
        기능: Literal["추가", "제거", "목록", "마을목록"],
        역할: str = None,
        마을: str = None
    ):
        """마을과 역할 연동 관리"""
        
        # 마을 역할 기능이 비활성화된 경우
        if not TOWN_ROLE_ENABLED:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ 기능 비활성화",
                    description="마을 역할 기능이 비활성화되어 있습니다.\n"
                              "`town_role_manager.py` 파일이 필요합니다.",
                    color=0xff0000
                ),
                ephemeral=True
            )
            return
        
        if 기능 == "마을목록":
            # BASE_NATION의 마을 목록 표시 - 간단한 안내 메시지로 변경
            embed = discord.Embed(
                title=f"🏘️ {BASE_NATION} 마을 목록 확인 방법",
                description=f"API 호출을 줄이기 위해 마을 목록을 자동으로 가져오지 않습니다.",
                color=0x00bfff
            )
            
            embed.add_field(
                name="📋 마을 확인 방법",
                value=f"1. **웹사이트 확인**: {MC_API_BASE}/nation?name={BASE_NATION}\n"
                      f"2. **마을 추가 시**: 정확한 마을 이름을 입력하면 자동으로 검증됩니다\n"
                      f"3. **잘못된 마을**: {BASE_NATION} 소속이 아닌 경우 오류 메시지가 표시됩니다",
                inline=False
            )
            
            # 현재 매핑된 마을들 표시
            if TOWN_ROLE_ENABLED and town_role_manager:
                try:
                    mapped_towns = town_role_manager.get_mapped_towns()
                    if mapped_towns:
                        # 10개씩 나누어서 표시
                        for i in range(0, len(mapped_towns), 10):
                            chunk = mapped_towns[i:i+10]
                            field_name = f"✅ 이미 연동된 마을 ({i+1}-{min(i+10, len(mapped_towns))} / {len(mapped_towns)})"
                            embed.add_field(
                                name=field_name,
                                value="\n".join([f"• {town}" for town in chunk]),
                                inline=False
                            )
                    else:
                        embed.add_field(
                            name="ℹ️ 연동된 마을",
                            value="아직 연동된 마을이 없습니다.",
                            inline=False
                        )
                except:
                    embed.add_field(
                        name="ℹ️ 연동된 마을",
                        value="마을 정보를 가져올 수 없습니다.",
                        inline=False
                    )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        elif 기능 == "목록":
            # 현재 연동된 마을-역할 목록 표시
            try:
                mappings = town_role_manager.get_all_mappings()
                
                embed = discord.Embed(
                    title="📋 마을-역할 연동 목록",
                    color=0x00bfff
                )
                
                if not mappings:
                    embed.description = "현재 연동된 마을-역할이 없습니다."
                else:
                    embed.description = f"총 **{len(mappings)}개**의 마을-역할이 연동되어 있습니다."
                    
                    # 10개씩 나누어서 표시
                    items = list(mappings.items())
                    for i in range(0, len(items), 10):
                        chunk = items[i:i+10]
                        field_items = []
                        
                        for town_name, role_id in chunk:
                            # 역할이 존재하는지 확인
                            role = interaction.guild.get_role(role_id)
                            if role:
                                field_items.append(f"• **{town_name}** → {role.mention}")
                            else:
                                field_items.append(f"• **{town_name}** → ⚠️ 역할 없음 (ID: {role_id})")
                        
                        embed.add_field(
                            name=f"연동 목록 ({i+1}-{min(i+10, len(items))})",
                            value="\n".join(field_items),
                            inline=False
                        )
            except Exception as e:
                embed = discord.Embed(
                    title="❌ 오류",
                    description=f"마을-역할 목록을 가져오는 중 오류가 발생했습니다.\n{str(e)}",
                    color=0xff0000
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # 추가/제거 시 매개변수 검증
        if 기능 == "추가":
            if not 역할 or not 마을:
                await interaction.response.send_message(
                    "❌ 추가 기능을 사용할 때는 역할과 마을을 모두 입력해야 합니다.\n"
                    "예: `/마을역할 기능:추가 역할:@마을역할 마을:Seoul`",
                    ephemeral=True
                )
                return
            
            # 역할 ID 추출
            role_clean = 역할.replace('<@&', '').replace('>', '').replace('<@', '').replace('!', '')
            try:
                role_id = int(role_clean)
            except ValueError:
                await interaction.response.send_message(
                    "❌ 올바른 역할 ID 또는 멘션을 입력해주세요.\n"
                    "예: `@역할이름` 또는 `123456789`",
                    ephemeral=True
                )
                return
            
            # 역할 존재 확인
            guild = interaction.guild
            role_obj = guild.get_role(role_id)
            if not role_obj:
                await interaction.response.send_message(
                    f"❌ 역할을 찾을 수 없습니다. (ID: {role_id})",
                    ephemeral=True
                )
                return
            
            # 마을이 BASE_NATION에 존재하는지 확인 - 버튼 선택 방식
            await interaction.response.defer(thinking=True)
            
            try:
                print(f"🔍 마을 검증 시작: {마을} in {BASE_NATION}")
                is_valid_town = await verify_town_in_nation(마을, BASE_NATION)
                
                # 검증 결과에 따른 임베드 생성
                if is_valid_town:
                    embed = discord.Embed(
                        title="✅ 마을 검증 완료",
                        description=f"**{마을}**은(는) **{BASE_NATION}** 소속 마을입니다.",
                        color=0x00ff00
                    )
                    embed.add_field(
                        name="🏘️ 연동 정보",
                        value=f"• **마을:** {마을}\n• **역할:** {role_obj.mention}\n• **상태:** ✅ 검증됨",
                        inline=False
                    )
                else:
                    embed = discord.Embed(
                        title="⚠️ 마을 검증 경고",
                        description=f"**{마을}**은(는) **{BASE_NATION}** 소속이 아니거나 존재하지 않는 마을입니다.",
                        color=0xff9900
                    )
                    embed.add_field(
                        name="🏘️ 연동 정보",
                        value=f"• **마을:** {마을}\n• **역할:** {role_obj.mention}\n• **상태:** ⚠️ 미검증",
                        inline=False
                    )
                    embed.add_field(
                        name="💡 안내",
                        value="마을이 검증되지 않았지만 수동으로 연동할 수 있습니다.\n"
                              "연동을 진행하시겠습니까?",
                        inline=False
                    )
                
                # 공통 추가 정보
                embed.add_field(
                    name="🔧 다음 단계",
                    value="아래 버튼을 클릭하여 연동을 진행하거나 취소하세요.\n"
                          "60초 후 자동으로 취소됩니다.",
                    inline=False
                )
                
                # 버튼 뷰 생성
                view = TownRoleConfirmView(마을, role_id, role_obj, is_valid_town)
                
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                return
                    
            except Exception as e:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="❌ 오류 발생",
                        description=f"마을 확인 중 오류가 발생했습니다.\n{str(e)}",
                        color=0xff0000
                    ),
                    ephemeral=True
                )
                return
            
        elif 기능 == "제거":
            if not 마을:
                await interaction.response.send_message(
                    "❌ 제거 기능을 사용할 때는 마을 이름을 입력해야 합니다.\n"
                    "예: `/마을역할 기능:제거 마을:Seoul`",
                    ephemeral=True
                )
                return
            
            # 매핑 제거
            try:
                if town_role_manager.remove_mapping(마을):
                    embed = discord.Embed(
                        title="✅ 마을-역할 연동 해제",
                        description=f"**{마을}** 마을의 역할 연동이 해제되었습니다.",
                        color=0x00ff00
                    )
                else:
                    embed = discord.Embed(
                        title="⚠️ 연동되지 않은 마을",
                        description=f"**{마을}**은(는) 연동되지 않은 마을입니다.",
                        color=0xffaa00
                    )
            except Exception as e:
                embed = discord.Embed(
                    title="❌ 오류 발생",
                    description=f"마을 연동 해제 중 오류가 발생했습니다.\n{str(e)}",
                    color=0xff0000
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="확인", description="자신의 국적을 확인하고 역할을 받습니다")
    async def 확인(self, interaction: discord.Interaction):
        """사용자 본인의 국적 확인 및 역할 부여 - 마을 역할 및 콜사인 포함"""
        await interaction.response.defer(thinking=True)
        
        member = interaction.user
        discord_id = member.id
        
        print(f"🔍 /확인 명령어 시작 - 사용자: {member.display_name} (ID: {discord_id})")
        
        try:
            async with aiohttp.ClientSession() as session:
                # 1단계: 디스코드 ID → 마크 ID
                url1 = f"{MC_API_BASE}/discord?discord={discord_id}"
                print(f"  🔗 1단계 API 호출: {url1}")
                
                async with session.get(url1, timeout=aiohttp.ClientTimeout(total=10)) as r1:
                    print(f"  📥 1단계 응답: HTTP {r1.status}")
                    if r1.status != 200:
                        await interaction.followup.send(
                            embed=discord.Embed(
                                title="❌ 확인 실패",
                                description="마인크래프트 계정 정보를 찾을 수 없습니다.\n디스코드와 마인크래프트 계정이 연동되어 있는지 확인해주세요.",
                                color=0xff0000
                            ),
                            ephemeral=True
                        )
                        return
                    
                    data1 = await r1.json()
                    print(f"  📋 1단계 데이터: {data1}")
                    
                    if not data1.get('data') or not data1['data']:
                        await interaction.followup.send(
                            embed=discord.Embed(
                                title="❌ 확인 실패",
                                description="마인크래프트 계정 정보가 없습니다.\n디스코드와 마인크래프트 계정이 연동되어 있는지 확인해주세요.",
                                color=0xff0000
                            ),
                            ephemeral=True
                        )
                        return
                        
                    mc_id = data1['data'][0].get('name')
                    if not mc_id:
                        await interaction.followup.send(
                            embed=discord.Embed(
                                title="❌ 확인 실패",
                                description="마인크래프트 닉네임을 찾을 수 없습니다.",
                                color=0xff0000
                            ),
                            ephemeral=True
                        )
                        return
                    
                    print(f"  ✅ 마크 ID 획득: {mc_id}")
                    time.sleep(2)

                # 2단계: 마크 ID → 마을
                url2 = f"{MC_API_BASE}/resident?name={mc_id}"
                print(f"  🔗 2단계 API 호출: {url2}")
                
                async with session.get(url2, timeout=aiohttp.ClientTimeout(total=10)) as r2:
                    print(f"  📥 2단계 응답: HTTP {r2.status}")
                    if r2.status != 200:
                        await interaction.followup.send(
                            embed=discord.Embed(
                                title="❌ 확인 실패",
                                description=f"마을 정보를 조회할 수 없습니다.\n마인크래프트 닉네임: **{mc_id}**",
                                color=0xff0000
                            ),
                            ephemeral=True
                        )
                        return
                        
                    data2 = await r2.json()
                    print(f"  📋 2단계 데이터: {data2}")
                    
                    if not data2.get('data') or not data2['data']:
                        await interaction.followup.send(
                            embed=discord.Embed(
                                title="❌ 확인 실패",
                                description=f"마을에 소속되어 있지 않습니다.\n마인크래프트 닉네임: **{mc_id}**",
                                color=0xff0000
                            ),
                            ephemeral=True
                        )
                        return
                        
                    town = data2['data'][0].get('town')
                    if not town:
                        await interaction.followup.send(
                            embed=discord.Embed(
                                title="❌ 확인 실패",
                                description=f"마을 정보가 없습니다.\n마인크래프트 닉네임: **{mc_id}**",
                                color=0xff0000
                            ),
                            ephemeral=True
                        )
                        return
                    
                    print(f"  ✅ 마을 획득: {town}")
                    time.sleep(2)

                # 3단계: 마을 → 국가
                url3 = f"{MC_API_BASE}/town?name={town}"
                print(f"  🔗 3단계 API 호출: {url3}")
                
                async with session.get(url3, timeout=aiohttp.ClientTimeout(total=10)) as r3:
                    print(f"  📥 3단계 응답: HTTP {r3.status}")
                    if r3.status != 200:
                        await interaction.followup.send(
                            embed=discord.Embed(
                                title="❌ 확인 실패",
                                description=f"국가 정보를 조회할 수 없습니다.\n마을: **{town}**",
                                color=0xff0000
                            ),
                            ephemeral=True
                        )
                        return
                        
                    data3 = await r3.json()
                    print(f"  📋 3단계 데이터: {data3}")
                    
                    if not data3.get('data') or not data3['data']:
                        await interaction.followup.send(
                            embed=discord.Embed(
                                title="❌ 확인 실패",
                                description=f"국가에 소속되어 있지 않습니다.\n마을: **{town}**",
                                color=0xff0000
                            ),
                            ephemeral=True
                        )
                        return
                        
                    nation = data3['data'][0].get('nation')
                    if not nation:
                        await interaction.followup.send(
                            embed=discord.Embed(
                                title="❌ 확인 실패",
                                description=f"국가 정보가 없습니다.\n마을: **{town}**",
                                color=0xff0000
                            ),
                            ephemeral=True
                        )
                        return
                    
                    print(f"  ✅ 국가 획득: {nation}")

            # 역할 부여 및 닉네임 변경
            guild = interaction.guild
            member = guild.get_member(discord_id)
            
            if not member:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="❌ 오류",
                        description="서버에서 사용자를 찾을 수 없습니다.",
                        color=0xff0000
                    ),
                    ephemeral=True
                )
                return

            # 새 닉네임 설정 (콜사인 고려 - BASE_NATION 국민만)
            if CALLSIGN_ENABLED and callsign_manager and nation == BASE_NATION:
                try:
                    user_callsign = callsign_manager.get_callsign(discord_id)
                    if user_callsign:
                        new_nickname = f"{mc_id} ㅣ {user_callsign}"
                        print(f"  🏷️ BASE_NATION 국민 콜사인 적용: {user_callsign}")
                    else:
                        new_nickname = f"{mc_id} ㅣ {nation}"
                        print(f"  🏴 BASE_NATION 국민 콜사인 없음: 국가명 사용")
                except Exception as e:
                    print(f"  ⚠️ 콜사인 확인 오류: {e}")
                    new_nickname = f"{mc_id} ㅣ {nation}"
            else:
                new_nickname = f"{mc_id} ㅣ {nation}"
                if nation != BASE_NATION:
                    print(f"  🌍 다른 국가 소속으로 콜사인 미적용: {nation}")
            
            # 변경 사항 추적
            changes = []
            
            try:
                # 닉네임 변경
                if member.display_name != new_nickname:
                    await member.edit(nick=new_nickname)
                    changes.append(f"• 닉네임이 **``{new_nickname}``**로 변경됨")
                    print(f"  ✅ 닉네임 변경: {new_nickname}")
                else:
                    print(f"  ℹ️ 닉네임 유지: {new_nickname}")
            except discord.Forbidden:
                changes.append("• ⚠️ 닉네임 변경 권한 없음")
                print(f"  ⚠️ 닉네임 변경 권한 없음")
            except Exception as e:
                changes.append(f"• ⚠️ 닉네임 변경 실패: {str(e)[:50]}")
                print(f"  ⚠️ 닉네임 변경 실패: {e}")

            # 매핑된 마을 역할 부여 (새로운 시스템)
            town_role_added = None
            if TOWN_ROLE_ENABLED and town_role_manager:
                try:
                    role_id = town_role_manager.get_role_id(town)
                    if role_id:
                        town_role = guild.get_role(role_id)
                        if town_role:
                            if town_role not in member.roles:
                                await member.add_roles(town_role)
                                town_role_added = town_role.name
                                changes.append(f"• **{town_role.name}** 마을 역할 추가됨")
                                print(f"  ✅ 매핑된 마을 역할 부여: {town_role.name}")
                            else:
                                print(f"  ℹ️ 이미 마을 역할 보유: {town_role.name}")
                        else:
                            changes.append(f"• ⚠️ 마을 역할을 찾을 수 없음 (ID: {role_id})")
                            print(f"  ⚠️ 마을 역할 없음: {role_id}")
                    else:
                        changes.append(f"• ℹ️ **{town}** 마을은 역할이 연동되지 않음")
                        print(f"  ℹ️ {town} 마을은 역할이 매핑되지 않음")
                except Exception as e:
                    changes.append(f"• ⚠️ 마을 역할 처리 실패: {str(e)[:50]}")
                    print(f"  ⚠️ 마을 역할 처리 실패: {e}")

            # 국가별 역할 부여 (기존 로직)
            role_added = None
            role_removed = None
            
            if nation == BASE_NATION:
                # 국민인 경우
                if SUCCESS_ROLE_ID != 0:
                    success_role = guild.get_role(SUCCESS_ROLE_ID)
                    if success_role:
                        if success_role not in member.roles:
                            try:
                                await member.add_roles(success_role)
                                role_added = success_role.name
                                changes.append(f"• **{success_role.name}** 역할 추가됨")
                                print(f"  ✅ 국민 역할 부여: {success_role.name}")
                            except Exception as e:
                                changes.append(f"• ⚠️ 국민 역할 부여 실패: {str(e)[:50]}")
                                print(f"  ⚠️ 국민 역할 부여 실패: {e}")
                        else:
                            print(f"  ℹ️ 이미 국민 역할 보유: {success_role.name}")
                
                # 비국민 역할 제거
                if SUCCESS_ROLE_ID_OUT != 0:
                    out_role = guild.get_role(SUCCESS_ROLE_ID_OUT)
                    if out_role and out_role in member.roles:
                        try:
                            await member.remove_roles(out_role)
                            role_removed = out_role.name
                            changes.append(f"• **{out_role.name}** 역할 제거됨")
                            print(f"  ✅ 비국민 역할 제거: {out_role.name}")
                        except Exception as e:
                            changes.append(f"• ⚠️ 비국민 역할 제거 실패: {str(e)[:50]}")
                            print(f"  ⚠️ 비국민 역할 제거 실패: {e}")
                
                # 성공 메시지 (국민)
                embed = discord.Embed(
                    title="✅ 국민 확인 완료",
                    description=f"**{BASE_NATION}** 국민으로 확인되었습니다!",
                    color=0x00ff00
                )
                
            else:
                # 비국민인 경우
                if SUCCESS_ROLE_ID_OUT != 0:
                    out_role = guild.get_role(SUCCESS_ROLE_ID_OUT)
                    if out_role:
                        if out_role not in member.roles:
                            try:
                                await member.add_roles(out_role)
                                role_added = out_role.name
                                changes.append(f"• **{out_role.name}** 역할 추가됨")
                                print(f"  ✅ 비국민 역할 부여: {out_role.name}")
                            except Exception as e:
                                changes.append(f"• ⚠️ 비국민 역할 부여 실패: {str(e)[:50]}")
                                print(f"  ⚠️ 비국민 역할 부여 실패: {e}")
                        else:
                            print(f"  ℹ️ 이미 비국민 역할 보유: {out_role.name}")
                
                # 국민 역할 제거
                if SUCCESS_ROLE_ID != 0:
                    success_role = guild.get_role(SUCCESS_ROLE_ID)
                    if success_role and success_role in member.roles:
                        try:
                            await member.remove_roles(success_role)
                            role_removed = success_role.name
                            changes.append(f"• **{success_role.name}** 역할 제거됨")
                            print(f"  ✅ 국민 역할 제거: {success_role.name}")
                        except Exception as e:
                            changes.append(f"• ⚠️ 국민 역할 제거 실패: {str(e)[:50]}")
                            print(f"  ⚠️ 국민 역할 제거 실패: {e}")
                
                # 성공 메시지 (비국민)
                embed = discord.Embed(
                    title="⚠️ 다른 국가 소속",
                    description=f"**{nation}** 국가에 소속되어 있습니다.",
                    color=0xff9900
                )

            # 공통 정보 추가
            embed.add_field(
                name="🎮 마인크래프트 정보",
                value=f"**닉네임:** {mc_id}\n**마을:** {town}\n**국가:** {nation}",
                inline=False
            )
            
            # 콜사인 정보 표시 (국가별로 다르게 표시)
            if CALLSIGN_ENABLED and callsign_manager:
                try:
                    user_callsign = callsign_manager.get_callsign(discord_id)
                    if user_callsign:
                        if nation == BASE_NATION:
                            embed.add_field(
                                name="🏷️ 콜사인 정보",
                                value=f"**설정된 콜사인:** {user_callsign}\n**닉네임에 표시:** 콜사인 우선 ✅\n💡 {BASE_NATION} 국민이므로 콜사인이 적용됩니다.",
                                inline=False
                            )
                        else:
                            embed.add_field(
                                name="🏷️ 콜사인 정보",
                                value=f"**설정된 콜사인:** {user_callsign}\n**닉네임에 표시:** 실제 국가명 우선 ⚠️\n💡 {BASE_NATION} 국민이 아니므로 콜사인이 적용되지 않습니다.",
                                inline=False
                            )
                    else:
                        if nation == BASE_NATION:
                            embed.add_field(
                                name="🏷️ 콜사인 정보",
                                value="**설정된 콜사인:** 없음\n**닉네임에 표시:** 국가명 사용\n💡 `/콜사인` 명령어로 설정하면 국가명 대신 표시됩니다.",
                                inline=False
                            )
                        else:
                            embed.add_field(
                                name="🏷️ 콜사인 정보", 
                                value=f"**설정된 콜사인:** 없음\n**닉네임에 표시:** 실제 국가명 사용\n💡 {BASE_NATION} 국민이 아니므로 콜사인 기능을 사용할 수 없습니다.",
                                inline=False
                            )
                except:
                    pass
            
            # 마을 역할 연동 상태 표시
            if TOWN_ROLE_ENABLED and town_role_manager:
                try:
                    role_id = town_role_manager.get_role_id(town)
                    if role_id:
                        town_role = guild.get_role(role_id)
                        if town_role:
                            embed.add_field(
                                name="🏘️ 마을 역할",
                                value=f"**{town}** → {town_role.mention}",
                                inline=False
                            )
                        else:
                            embed.add_field(
                                name="🏘️ 마을 역할",
                                value=f"**{town}** → ⚠️ 역할 없음 (ID: {role_id})",
                                inline=False
                            )
                    else:
                        embed.add_field(
                            name="🏘️ 마을 역할",
                            value=f"**{town}** → ℹ️ 역할 연동 안됨",
                            inline=False
                        )
                except:
                    embed.add_field(
                        name="🏘️ 마을 역할",
                        value=f"**{town}** → ⚠️ 역할 정보 확인 불가",
                        inline=False
                    )
            
            # 변경 사항 표시
            if changes:
                # 너무 많은 변경사항이 있을 경우 요약
                if len("\n".join(changes)) > 1000:
                    changes = changes[:10]  # 최대 10개만 표시
                    changes.append("• ...")
                
                embed.add_field(
                    name="🔄 변경 사항",
                    value="\n".join(changes),
                    inline=False
                )
            else:
                embed.add_field(
                    name="ℹ️ 변경 사항",
                    value="변경된 사항이 없습니다.",
                    inline=False
                )
            
            # 마을 역할 연동 안내 (역할이 연동되지 않은 경우)
            if TOWN_ROLE_ENABLED and town_role_manager:
                try:
                    if not town_role_manager.get_role_id(town):
                        embed.add_field(
                            name="💡 안내",
                            value=f"**{town}** 마을의 역할 연동이 필요하면 관리자에게 문의하세요.\n"
                                  f"관리자는 `/마을역할 기능:추가`로 역할을 연동할 수 있습니다.",
                            inline=False
                        )
                except:
                    pass
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            print(f"🏁 /확인 처리 완료 - {member.display_name}: {nation}, {town}")

        except Exception as e:
            print(f"💥 /확인 예외 발생: {e}")
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ 오류 발생",
                    description=f"처리 중 오류가 발생했습니다.\n{str(e)[:100]}",
                    color=0xff0000
                ),
                ephemeral=True
            )

    @app_commands.command(name="마을테스트", description="[관리자] 마을 검증 기능을 테스트합니다")
    @app_commands.describe(마을="테스트할 마을 이름")
    @app_commands.check(is_admin)
    async def 마을테스트(self, interaction: discord.Interaction, 마을: str = None):
        """마을 검증 기능 디버깅"""
        await interaction.response.defer(thinking=True)
        
        embed = discord.Embed(
            title="🧪 마을 검증 테스트",
            color=0x00ff00
        )
        
        # 기본 정보
        embed.add_field(
            name="🔧 환경 설정",
            value=f"• **TOWN_ROLE_ENABLED**: {TOWN_ROLE_ENABLED}\n"
                  f"• **BASE_NATION**: {BASE_NATION}\n"
                  f"• **MC_API_BASE**: {MC_API_BASE}",
            inline=False
        )
        
        # town_role_manager 상태
        if TOWN_ROLE_ENABLED and town_role_manager:
            try:
                mapping_count = town_role_manager.get_mapping_count()
                embed.add_field(
                    name="🏘️ town_role_manager 상태",
                    value=f"• **상태**: 정상 로드됨\n• **매핑된 마을**: {mapping_count}개",
                    inline=False
                )
            except:
                embed.add_field(
                    name="🏘️ town_role_manager 상태",
                    value="• **상태**: 로드됨 (일부 메서드 사용 불가)",
                    inline=False
                )
        else:
            embed.add_field(
                name="🏘️ town_role_manager 상태",
                value="• **상태**: 로드되지 않음 또는 비활성화",
                inline=False
            )
        
        # 마을 검증 테스트
        if 마을:
            try:
                print(f"🧪 마을 검증 테스트 시작: {마을}")
                is_valid = await verify_town_in_nation(마을, BASE_NATION)
                
                if is_valid:
                    embed.add_field(
                        name="✅ 마을 검증 결과",
                        value=f"• **마을**: {마을}\n"
                              f"• **결과**: **{BASE_NATION}** 소속 ✅\n"
                              f"• **상태**: 연동 가능",
                        inline=False
                    )
                    embed.color = 0x00ff00
                else:
                    embed.add_field(
                        name="❌ 마을 검증 결과",
                        value=f"• **마을**: {마을}\n"
                              f"• **결과**: **{BASE_NATION}** 소속 아님 ❌\n"
                              f"• **상태**: 연동 불가",
                        inline=False
                    )
                    embed.color = 0xff0000
                    
            except Exception as e:
                embed.add_field(
                    name="❌ 마을 검증 실패",
                    value=f"• **마을**: {마을}\n• **오류**: {str(e)[:100]}",
                    inline=False
                )
                embed.color = 0xff0000
        else:
            # 샘플 마을들로 테스트
            test_towns = ["Seoul", "NonExistentTown", "TestTown"]
            test_results = []
            
            for test_town in test_towns:
                try:
                    is_valid = await verify_town_in_nation(test_town, BASE_NATION)
                    status = "✅ 유효" if is_valid else "❌ 무효"
                    test_results.append(f"• **{test_town}**: {status}")
                except Exception as e:
                    test_results.append(f"• **{test_town}**: ❌ 오류 - {str(e)[:30]}")
            
            embed.add_field(
                name="🔍 샘플 마을 테스트",
                value="\n".join(test_results),
                inline=False
            )
        
        # API 테스트
        try:
            async with aiohttp.ClientSession() as session:
                # API 연결 테스트
                url = f"{MC_API_BASE}/nation?name={BASE_NATION}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as response:
                    if response.status == 200:
                        embed.add_field(
                            name="🌐 API 연결 테스트",
                            value=f"• **상태**: ✅ 정상 연결\n• **응답 코드**: HTTP {response.status}",
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="🌐 API 연결 테스트",
                            value=f"• **상태**: ⚠️ 응답 코드 이상\n• **응답 코드**: HTTP {response.status}",
                            inline=False
                        )
        except Exception as e:
            embed.add_field(
                name="🌐 API 연결 테스트",
                value=f"• **상태**: ❌ 연결 실패\n• **오류**: {str(e)[:50]}",
                inline=False
            )
        
        # 해결 방법 제안
        embed.add_field(
            name="💡 사용 방법",
            value="1. `/마을역할 기능:추가 역할:@역할이름 마을:정확한마을이름`\n"
                  "2. 마을 이름은 정확히 입력해야 합니다 (대소문자 구분)\n"
                  "3. 검증 후 **버튼**으로 연동 진행/취소 선택\n"
                  "4. 미검증 마을도 수동 연동 가능\n"
                  "5. 특정 마을 테스트: `/마을테스트 마을:마을이름`",
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="테스트", description="봇의 기본 기능을 테스트합니다")
    @app_commands.check(is_admin)
    async def 테스트(self, interaction: discord.Interaction):
        """봇 테스트 명령어"""
        await interaction.response.defer(thinking=True)
        
        embed = discord.Embed(
            title="🧪 봇 테스트 결과",
            color=0x00ff00
        )
        
        # 기본 정보
        embed.add_field(
            name="🤖 봇 정보",
            value=f"**봇 이름:** {self.bot.user.name}\n**핑:** {round(self.bot.latency * 1000)}ms",
            inline=False
        )
        
        # 서버 정보
        guild = interaction.guild
        embed.add_field(
            name="🏰 서버 정보",
            value=f"**서버 이름:** {guild.name}\n**멤버 수:** {guild.member_count}명",
            inline=False
        )
        
        # 환경변수 확인
        env_status = []
        env_status.append(f"MC_API_BASE: {'✅' if MC_API_BASE else '❌'}")
        env_status.append(f"BASE_NATION: {'✅' if BASE_NATION else '❌'}")
        env_status.append(f"SUCCESS_ROLE_ID: {'✅' if SUCCESS_ROLE_ID != 0 else '❌'}")
        env_status.append(f"TOWN_ROLE_ENABLED: {'✅' if TOWN_ROLE_ENABLED else '❌'}")
        env_status.append(f"CALLSIGN_ENABLED: {'✅' if CALLSIGN_ENABLED else '❌'}")
        
        embed.add_field(
            name="⚙️ 환경변수 상태",
            value="\n".join(env_status),
            inline=False
        )
        
        # 대기열 상태
        queue_size = queue_manager.get_queue_size()
        is_processing = queue_manager.is_processing()
        
        embed.add_field(
            name="📋 대기열 상태",
            value=f"**대기 중:** {queue_size}명\n**처리 상태:** {'🔄 처리 중' if is_processing else '⏸️ 대기 중'}",
            inline=False
        )
        
        # 예외 관리자 상태
        exception_count = len(exception_manager.get_exceptions())
        embed.add_field(
            name="🚫 예외 관리자",
            value=f"**예외 사용자:** {exception_count}명",
            inline=False
        )
        
        # 마을 역할 관리자 상태
        if TOWN_ROLE_ENABLED and town_role_manager:
            try:
                town_mapping_count = town_role_manager.get_mapping_count()
                embed.add_field(
                    name="🏘️ 마을 역할 관리자",
                    value=f"**연동된 마을:** {town_mapping_count}개",
                    inline=False
                )
            except:
                embed.add_field(
                    name="🏘️ 마을 역할 관리자",
                    value="**상태:** 로드됨 (일부 기능 제한)",
                    inline=False
                )
        
        # 콜사인 관리자 상태
        if CALLSIGN_ENABLED and callsign_manager:
            try:
                callsign_count = callsign_manager.get_callsign_count()
                embed.add_field(
                    name="🏷️ 콜사인 관리자",
                    value=f"**설정된 콜사인:** {callsign_count}개",
                    inline=False
                )
            except:
                embed.add_field(
                    name="🏷️ 콜사인 관리자",
                    value="**상태:** 로드됨 (일부 기능 제한)",
                    inline=False
                )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="스케줄확인", description="자동 실행 스케줄 정보를 확인합니다")
    @app_commands.check(is_admin)
    async def 스케줄확인(self, interaction: discord.Interaction):
        """스케줄러 상태 확인"""
        try:
            from scheduler import get_scheduler_info
            
            info = get_scheduler_info()
            
            embed = discord.Embed(
                title="📅 자동 실행 스케줄 정보",
                color=0x00ff00 if info["running"] else 0xff0000
            )
            
            # 스케줄러 상태
            status = "🟢 실행 중" if info["running"] else "🔴 중지됨"
            embed.add_field(
                name="⚙️ 스케줄러 상태",
                value=status,
                inline=False
            )
            
            # 자동 실행 설정
            day_names = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
            day_name = day_names[info["auto_execution_day"]]
            
            embed.add_field(
                name="🕒 자동 실행 스케줄",
                value=f"**매주 {day_name}** {info['auto_execution_hour']:02d}:{info['auto_execution_minute']:02d}",
                inline=False
            )
            
            # 등록된 작업들
            if info["jobs"]:
                job_list = []
                for job in info["jobs"]:
                    job_list.append(f"• **{job['name']}**\n  다음 실행: {job['next_run']}")
                
                embed.add_field(
                    name="📋 등록된 작업",
                    value="\n\n".join(job_list),
                    inline=False
                )
            else:
                embed.add_field(
                    name="📋 등록된 작업",
                    value="등록된 작업이 없습니다.",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ImportError:
            embed = discord.Embed(
                title="❌ 오류",
                description="scheduler 모듈을 로드할 수 없습니다.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ 오류 발생",
                description=f"스케줄 정보를 가져오는 중 오류가 발생했습니다.\n{str(e)}",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="자동실행시작", description="자동 역할 부여를 수동으로 시작합니다")
    @app_commands.check(is_admin)
    async def 자동실행시작(self, interaction: discord.Interaction):
        """자동 역할 부여를 수동으로 실행"""
        await interaction.response.defer(thinking=True)
        
        try:
            from scheduler import manual_execute_auto_roles
            
            # 현재 대기열 상태 확인
            current_queue_size = queue_manager.get_queue_size()
            
            embed = discord.Embed(
                title="🚀 자동 역할 실행 시작",
                description="auto_roles.txt 파일의 역할 멤버들을 대기열에 추가하고 있습니다...",
                color=0xffaa00
            )
            
            embed.add_field(
                name="📋 현재 상태",
                value=f"기존 대기열: **{current_queue_size}명**",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # 자동 역할 실행
            result = await manual_execute_auto_roles(self.bot)
            
            if result["success"]:
                embed = discord.Embed(
                    title="✅ 자동 역할 실행 완료",
                    description=result["message"],
                    color=0x00ff00
                )
                
                new_queue_size = queue_manager.get_queue_size()
                
                embed.add_field(
                    name="📊 결과",
                    value=f"• 추가된 사용자: **{result.get('added_count', 0)}명**\n• 현재 대기열: **{new_queue_size}명**",
                    inline=False
                )
                
                if new_queue_size > 0:
                    estimated_time = new_queue_size * 36  # 대략 배치당 36초 추정
                    minutes = estimated_time // 60
                    seconds = estimated_time % 60
                    
                    if minutes > 0:
                        time_str = f"약 {minutes}분 {seconds}초"
                    else:
                        time_str = f"약 {seconds}초"
                    
                    embed.add_field(
                        name="⏰ 예상 완료 시간",
                        value=time_str,
                        inline=False
                    )
            else:
                embed = discord.Embed(
                    title="❌ 자동 역할 실행 실패",
                    description=result["message"],
                    color=0xff0000
                )
            
            # 새로운 메시지로 결과 전송
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except ImportError:
            embed = discord.Embed(
                title="❌ 오류",
                description="scheduler 모듈을 로드할 수 없습니다.",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ 오류 발생",
                description=f"자동 역할 실행 중 오류가 발생했습니다.\n{str(e)}",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="예외설정", description="자동실행 예외 대상을 관리합니다")
    @app_commands.describe(
        기능="수행할 작업을 선택하세요",
        대상="(추가/제거 시만) 유저 멘션 또는 유저 ID"
    )
    @app_commands.check(is_admin)
    async def 예외설정(
        self,
        interaction: discord.Interaction,
        기능: Literal["추가", "제거", "목록"],
        대상: str = None
    ):
        """자동실행 예외 대상 관리"""
        
        if 기능 == "목록":
            # 예외 목록 표시
            exceptions = exception_manager.get_exceptions()
            
            embed = discord.Embed(
                title="📋 자동실행 예외 목록",
                color=0x00bfff
            )
            
            if not exceptions:
                embed.description = "현재 예외 설정된 사용자가 없습니다."
            else:
                embed.description = f"총 **{len(exceptions)}명**이 예외 설정되어 있습니다."
                
                # 10명씩 나누어서 표시
                for i in range(0, len(exceptions), 10):
                    chunk = exceptions[i:i+10]
                    mentions = [f"<@{user_id}>" for user_id in chunk]
                    
                    embed.add_field(
                        name=f"예외 대상 ({i+1}-{min(i+10, len(exceptions))})",
                        value="\n".join(mentions),
                        inline=False
                    )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # 추가/제거 시 대상이 필요함
        if not 대상:
            await interaction.response.send_message(
                "❌ 추가/제거 기능을 사용할 때는 대상을 입력해야 합니다.\n"
                "예: `/예외설정 기능:추가 대상:@사용자` 또는 `/예외설정 기능:추가 대상:123456789`",
                ephemeral=True
            )
            return
        
        # 멘션 형식 처리 (< > 제거)
        target_clean = 대상.replace('<@', '').replace('>', '').replace('!', '')
        
        try:
            user_id = int(target_clean)
        except ValueError:
            await interaction.response.send_message(
                "❌ 올바른 사용자 ID 또는 멘션을 입력해주세요.\n"
                "예: `@사용자` 또는 `123456789`",
                ephemeral=True
            )
            return
        
        # 사용자 존재 확인
        guild = interaction.guild
        member = guild.get_member(user_id)
        if not member:
            await interaction.response.send_message(
                f"❌ 사용자를 찾을 수 없습니다. (ID: {user_id})",
                ephemeral=True
            )
            return
        
        if 기능 == "추가":
            if exception_manager.add_exception(user_id):
                embed = discord.Embed(
                    title="✅ 예외 추가 완료",
                    description=f"{member.mention}님을 자동실행 예외 목록에 추가했습니다.",
                    color=0x00ff00
                )
            else:
                embed = discord.Embed(
                    title="⚠️ 이미 예외 설정됨",
                    description=f"{member.mention}님은 이미 예외 목록에 있습니다.",
                    color=0xffaa00
                )
        
        elif 기능 == "제거":
            if exception_manager.remove_exception(user_id):
                embed = discord.Embed(
                    title="✅ 예외 제거 완료",
                    description=f"{member.mention}님을 자동실행 예외 목록에서 제거했습니다.",
                    color=0x00ff00
                )
            else:
                embed = discord.Embed(
                    title="⚠️ 예외 목록에 없음",
                    description=f"{member.mention}님은 예외 목록에 없습니다.",
                    color=0xffaa00
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="국민확인", description="디스코드 아이디를 이용해서 국민이 어떤 나라에 속해있는지 알려줍니다")
    @app_commands.describe(
        대상="확인할 대상 유형을 선택하세요",
        멘션or아이디="유저: @유저 또는 유저ID / 역할: @역할 또는 역할ID"
    )
    @app_commands.check(is_admin)
    async def 국민확인(
        self,
        interaction: discord.Interaction,
        대상: Literal["유저", "역할"],
        멘션or아이디: str
    ):
        guild = interaction.guild
        members = []
        target_type = 대상
        target_name = None

        # 멘션 형식 처리 (< > 제거)
        input_clean = 멘션or아이디.replace('<@', '').replace('<@&', '').replace('>', '').replace('!', '')

        try:
            input_int = int(input_clean)
        except ValueError:
            await interaction.response.send_message(
                "❌ 올바른 형식을 입력해주세요.\n"
                f"**{대상} 선택 시**: {'@유저이름 또는 유저ID' if 대상 == '유저' else '@역할이름 또는 역할ID'}",
                ephemeral=True
            )
            return

        if 대상 == "유저":
            # 유저 처리 - 즉시 처리
            member = guild.get_member(input_int)
            if member:
                members.append(member)
                target_name = member.display_name
            else:
                await interaction.response.send_message("❌ 유저를 찾을 수 없습니다.", ephemeral=True)
                return
                
            # 유저는 즉시 처리
            await self._handle_immediate_processing(interaction, members, target_type, target_name)
            
        elif 대상 == "역할":
            # 역할 처리 - 대기열로 처리
            role = guild.get_role(input_int)
            if role:
                members.extend(role.members)
                target_name = role.name
            else:
                await interaction.response.send_message("❌ 역할을 찾을 수 없습니다.", ephemeral=True)
                return
                
            # 역할은 대기열로 처리
            await self._handle_queue_processing(interaction, members, target_type, target_name)

    async def _handle_queue_processing(self, interaction: discord.Interaction, members: list, target_type: str, target_name: str):
        """대기열을 통한 처리"""
        await interaction.response.defer(thinking=True)
        
        added_count = 0
        already_in_queue = 0
        
        # 대기열에 사용자 추가
        for member in members:
            try:
                queue_manager.add_user(member.id)
                added_count += 1
            except:
                already_in_queue += 1
        
        # 결과 메시지 생성
        embed = discord.Embed(
            title="🔄 대기열 추가 완료",
            color=0x00ff00
        )
        
        if target_type == "유저":
            embed.description = f"**{target_name}** 사용자 처리"
        else:
            embed.description = f"**{target_name}** 역할 멤버 {len(members)}명 처리"
        
        embed.add_field(
            name="📋 처리 현황",
            value=f"• 새로 추가: **{added_count}명**\n• 이미 대기 중: **{already_in_queue}명**",
            inline=False
        )
        
        current_queue_size = queue_manager.get_queue_size()
        processing_status = "처리 중" if queue_manager.is_processing() else "대기 중"
        
        embed.add_field(
            name="🎯 대기열 상태",
            value=f"• 총 대기 인원: **{current_queue_size}명**\n• 현재 상태: **{processing_status}**",
            inline=False
        )
        
        if added_count > 0:
            embed.add_field(
                name="⏰ 예상 처리 시간",
                value="1분마다 자동으로 처리되며, 완료 시 결과가 해당 채널에 전송됩니다.",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _handle_immediate_processing(self, interaction: discord.Interaction, members: list, target_type: str, target_name: str):
        """기존 즉시 처리 방식 (API 제한 위험)"""
        await interaction.response.defer(thinking=True)

        not_base_nation = []
        errors = []

        print(f"🔍 /국민확인 명령어 시작 - 대상: {target_type} '{target_name}', 총 {len(members)}명")

        async with aiohttp.ClientSession() as session:
            for idx, member in enumerate(members, 1):
                discord_id = member.id
                print(f"📋 [{idx}/{len(members)}] 처리 중: {member.display_name} (ID: {discord_id})")

                try:
                    # 1단계: 디스코드 ID → 마크 ID
                    url1 = f"{MC_API_BASE}/discord?discord={discord_id}"
                    print(f"  🔗 1단계 API 호출: {url1}")
                    
                    async with session.get(url1, timeout=aiohttp.ClientTimeout(total=10)) as r1:
                        print(f"  📥 1단계 응답: HTTP {r1.status}")
                        if r1.status != 200:
                            error_msg = f"마크ID 조회 실패 ({r1.status})"
                            errors.append(f"{member.mention} - {error_msg}")
                            print(f"  ❌ {error_msg}")
                            continue
                        
                        data1 = await r1.json()
                        print(f"  📋 1단계 데이터: {data1}")
                        
                        if not data1.get('data') or not data1['data']:
                            error_msg = "마크ID 데이터 없음"
                            errors.append(f"{member.mention} - {error_msg}")
                            print(f"  ❌ {error_msg}")
                            continue
                            
                        mc_id = data1['data'][0].get('name')
                        if not mc_id:
                            error_msg = "마크ID 없음"
                            errors.append(f"{member.mention} - {error_msg}")
                            print(f"  ❌ {error_msg}")
                            continue
                        
                        print(f"  ✅ 마크 ID 획득: {mc_id}")
                        time.sleep(5)

                    # 2단계: 마크 ID → 마을
                    url2 = f"{MC_API_BASE}/resident?name={mc_id}"
                    print(f"  🔗 2단계 API 호출: {url2}")
                    
                    async with session.get(url2, timeout=aiohttp.ClientTimeout(total=10)) as r2:
                        print(f"  📥 2단계 응답: HTTP {r2.status}")
                        if r2.status != 200:
                            error_msg = f"마을 조회 실패 ({r2.status})"
                            errors.append(f"{member.mention} (마크: {mc_id}) - {error_msg}")
                            print(f"  ❌ {error_msg}")
                            continue
                            
                        data2 = await r2.json()
                        print(f"  📋 2단계 데이터: {data2}")
                        
                        if not data2.get('data') or not data2['data']:
                            error_msg = "마을 데이터 없음"
                            errors.append(f"{member.mention} (마크: {mc_id}) - {error_msg}")
                            print(f"  ❌ {error_msg}")
                            continue
                            
                        town = data2['data'][0].get('town')
                        if not town:
                            error_msg = "마을 없음"
                            errors.append(f"{member.mention} (마크: {mc_id}) - {error_msg}")
                            print(f"  ❌ {error_msg}")
                            continue
                        
                        print(f"  ✅ 마을 획득: {town}")
                        time.sleep(5)

                    # 3단계: 마을 → 국가
                    url3 = f"{MC_API_BASE}/town?name={town}"
                    print(f"  🔗 3단계 API 호출: {url3}")
                    
                    async with session.get(url3, timeout=aiohttp.ClientTimeout(total=10)) as r3:
                        print(f"  📥 3단계 응답: HTTP {r3.status}")
                        if r3.status != 200:
                            error_msg = f"국가 조회 실패 ({r3.status})"
                            errors.append(f"{member.mention} (마을: {town}) - {error_msg}")
                            print(f"  ❌ {error_msg}")
                            continue
                            
                        data3 = await r3.json()
                        print(f"  📋 3단계 데이터: {data3}")
                        
                        if not data3.get('data') or not data3['data']:
                            error_msg = "국가 데이터 없음"
                            errors.append(f"{member.mention} (마을: {town}) - {error_msg}")
                            print(f"  ❌ {error_msg}")
                            continue
                            
                        nation = data3['data'][0].get('nation')
                        if not nation:
                            error_msg = "국가 없음"
                            errors.append(f"{member.mention} (마을: {town}) - {error_msg}")
                            print(f"  ❌ {error_msg}")
                            continue
                        
                        print(f"  ✅ 국가 획득: {nation}")
                        time.sleep(5)

                        if nation != BASE_NATION:
                            not_base_nation.append(f"{member.mention} (국가: {nation}, 마크: {mc_id})")
                            print(f"  ⚠️ 다른 국가 소속: {nation}")
                        else:
                            print(f"  ✅ {BASE_NATION} 국민 확인")

                except Exception as e:
                    error_msg = f"오류 발생: {str(e)[:50]}"
                    errors.append(f"{member.mention} - {error_msg}")
                    print(f"  💥 예외 발생: {e}")

        print(f"🏁 /국민확인 처리 완료 - 총 {len(members)}명 중 다른국가: {len(not_base_nation)}명, 오류: {len(errors)}명")

        # 메시지를 여러 개의 임베드로 분할하여 준비
        embeds_data = []
        
        # 첫 번째 임베드 (기본 응답)
        main_embed = {
            "title": f"🛡️ 국민 확인 결과",
            "color": 0x00bfff,
            "fields": []
        }

        # 대상 정보 추가
        if target_type == "유저":
            description = f"**{target_name}** 사용자 확인 완료"
        else:
            description = f"**{target_name}** 역할 ({len(members)}명) 확인 완료"
        
        main_embed["description"] = description

        # not_base_nation이 있으면 일부를 첫 번째 임베드에 추가
        if not_base_nation:
            display_count = min(10, len(not_base_nation))
            value = "\n".join(not_base_nation[:display_count])
            if len(not_base_nation) > 10:
                value += f"\n...그리고 {len(not_base_nation) - 10}명 더"
            
            main_embed["fields"].append({
                "name": f"⚠️ 다른 국가 소속 ({len(not_base_nation)}명)",
                "value": value,
                "inline": False
            })

        # errors가 있으면 일부를 첫 번째 임베드에 추가
        if errors:
            display_count = min(10, len(errors))
            value = "\n".join(errors[:display_count])
            if len(errors) > 10:
                value += f"\n...그리고 {len(errors) - 10}개 더"
                
            main_embed["fields"].append({
                "name": f"⚠️ 오류 또는 실패 ({len(errors)}명)",
                "value": value,
                "inline": False
            })

        if not main_embed["fields"]:
            main_embed["fields"].append({
                "name": f"✅ {BASE_NATION} 국민 확인 완료",
                "value": f"모든 {len(members)}명이 {BASE_NATION} 소속입니다!",
                "inline": False
            })

        # 첫 번째 응답 전송
        embed = discord.Embed(
            title=main_embed["title"],
            color=main_embed["color"]
        )
        
        if "description" in main_embed:
            embed.description = main_embed["description"]
            
        for field in main_embed["fields"]:
            embed.add_field(
                name=field["name"],
                value=field["value"],
                inline=field.get("inline", False)
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

        # 추가 데이터가 있으면 웹훅으로 전송
        # not_base_nation 추가 페이지들
        if len(not_base_nation) > 10:
            for i in range(10, len(not_base_nation), 15):
                chunk = not_base_nation[i:i+15]
                embed_data = {
                    "title": f"⚠️ 다른 국가 소속 (추가 {(i-10)//15 + 1}페이지)",
                    "color": 0xff9900,
                    "fields": [
                        {
                            "name": f"멤버 목록 ({i+1}-{min(i+15, len(not_base_nation))} / {len(not_base_nation)})",
                            "value": "\n".join(chunk),
                            "inline": False
                        }
                    ]
                }
                embeds_data.append(embed_data)

        # errors 추가 페이지들
        if len(errors) > 10:
            for i in range(10, len(errors), 15):
                chunk = errors[i:i+15]
                embed_data = {
                    "title": f"⚠️ 오류 또는 실패 (추가 {(i-10)//15 + 1}페이지)",
                    "color": 0xff0000,
                    "fields": [
                        {
                            "name": f"오류 목록 ({i+1}-{min(i+15, len(errors))} / {len(errors)})",
                            "value": "\n".join(chunk),
                            "inline": False
                        }
                    ]
                }
                embeds_data.append(embed_data)

        # 추가 임베드가 있으면 웹훅으로 전송
        if embeds_data:
            await self.send_long_message_via_webhook(interaction, embeds_data)

    @app_commands.command(name="대기열상태", description="현재 대기열 상태를 확인합니다")
    @app_commands.check(is_admin)
    async def 대기열상태(self, interaction: discord.Interaction):
        """대기열 상태 확인 명령어"""
        queue_size = queue_manager.get_queue_size()
        is_processing = queue_manager.is_processing()
        
        embed = discord.Embed(
            title="📋 대기열 상태",
            color=0x00ff00 if queue_size == 0 else 0xffaa00
        )
        
        embed.add_field(
            name="🎯 현재 대기열",
            value=f"**{queue_size}명** 대기 중",
            inline=True
        )
        
        status_text = "🔄 처리 중" if is_processing else "⏸️ 대기 중"
        embed.add_field(
            name="📊 처리 상태",
            value=status_text,
            inline=True
        )
        
        if queue_size > 0:
            estimated_time = queue_size * 36  # 대략 배치당 36초 추정
            minutes = estimated_time // 60
            seconds = estimated_time % 60
            hours = minutes // 60
            
            if hours > 0:
                minutes = minutes % 60
                time_str = f"약 {hours}시간 {minutes}분 {seconds}초"
            elif minutes > 0:
                time_str = f"약 {minutes}분 {seconds}초"
            else:
                time_str = f"약 {seconds}초"

            embed.add_field(
                name="⏰ 예상 완료 시간",
                value=time_str,
                inline=True
            )
        else:
            embed.add_field(
                name="⏰ 예상 완료 시간",
                value="대기열이 비어있습니다",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="대기열초기화", description="대기열을 모두 비웁니다")
    @app_commands.check(is_admin)
    async def 대기열초기화(self, interaction: discord.Interaction):
        """대기열 초기화 명령어"""
        cleared_count = queue_manager.clear_queue()
        
        embed = discord.Embed(
            title="🧹 대기열 초기화 완료",
            description=f"**{cleared_count}명**이 대기열에서 제거되었습니다.",
            color=0xff6600
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="자동실행", description="자동 등록할 역할을 설정")
    @app_commands.describe(역할id="역할 ID")
    @app_commands.check(is_admin)
    async def 자동실행(self, interaction: discord.Interaction, 역할id: str):
        try:
            path = "auto_roles.txt"
            with open(path, "a") as f:
                f.write(f"{역할id}\n")
            await interaction.response.send_message(f"🔁 자동실행 역할 추가됨: <@&{역할id}>", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 오류: {str(e)}", ephemeral=True)

    # 에러 핸들러
    @확인.error
    @테스트.error
    @마을테스트.error
    @스케줄확인.error
    @자동실행시작.error
    @예외설정.error
    @국민확인.error  
    @대기열상태.error
    @대기열초기화.error
    @자동실행.error
    @도움말.error
    @마을역할.error
    @콜사인.error
    @콜사인관리.error
    async def on_app_command_error(self, interaction: discord.Interaction, error):
        # 이미 응답된 상호작용인지 확인
        if interaction.response.is_done():
            # 이미 응답된 경우 followup 사용
            try:
                if isinstance(error, app_commands.CheckFailure):
                    await interaction.followup.send("🚫 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True)
                else:
                    await interaction.followup.send(f"❗ 오류 발생: `{str(error)}`", ephemeral=True)
            except:
                # followup도 실패하면 콘솔에만 출력
                print(f"Error handling failed: {error}")
        else:
            # 아직 응답하지 않은 경우 response 사용
            try:
                if isinstance(error, app_commands.CheckFailure):
                    await interaction.response.send_message("🚫 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True)
                else:
                    await interaction.response.send_message(f"❗ 오류 발생: `{str(error)}`", ephemeral=True)
            except:
                print(f"Error response failed: {error}")

async def setup(bot):
    await bot.add_cog(SlashCommands(bot))
