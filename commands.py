import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal
import aiohttp
import os
import time

from queue_manager import queue_manager
from exception_manager import exception_manager

MC_API_BASE = os.getenv("MC_API_BASE")  # 예: https://api.planetearth.kr
BASE_NATION = os.getenv("BASE_NATION", "Red_Mafia")  # .env에서 국가 설정
SUCCESS_ROLE_ID = int(os.getenv("SUCCESS_ROLE_ID", "0"))  # 국민 역할 ID
SUCCESS_ROLE_ID_OUT = int(os.getenv("SUCCESS_ROLE_ID_OUT", "0"))  # 비국민 역할 ID

class SlashCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

    @app_commands.command(name="확인", description="자신의 국적을 확인하고 역할을 받습니다")
    async def 확인(self, interaction: discord.Interaction):
        """사용자 본인의 국적 확인 및 역할 부여"""
        await interaction.response.defer(thinking=True)
        
        member = interaction.user
        discord_id = member.id
        
        print(f"🔍 /확인 명령어 시작 - 사용자: {member.display_name} (ID: {discord_id})")
        
        try:
            async with aiohttp.ClientSession() as session:
                # 1단계: 디스코드 ID → 마크 ID
                url1 = f"https://api.planetearth.kr/discord?discord={discord_id}"
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
                url2 = f"https://api.planetearth.kr/resident?name={mc_id}"
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
                url3 = f"https://api.planetearth.kr/town?name={town}"
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

            # 새 닉네임 설정
            new_nickname = f"{mc_id} ㅣ {nation}"
            
            try:
                # 닉네임 변경
                await member.edit(nick=new_nickname)
                print(f"  ✅ 닉네임 변경: {new_nickname}")
            except discord.Forbidden:
                print(f"  ⚠️ 닉네임 변경 권한 없음")
            except Exception as e:
                print(f"  ⚠️ 닉네임 변경 실패: {e}")

            # 역할 부여
            role_added = None
            role_removed = None
            
            if nation == BASE_NATION:
                # 국민인 경우
                if SUCCESS_ROLE_ID != 0:
                    success_role = guild.get_role(SUCCESS_ROLE_ID)
                    if success_role:
                        try:
                            await member.add_roles(success_role)
                            role_added = success_role.name
                            print(f"  ✅ 국민 역할 부여: {success_role.name}")
                        except Exception as e:
                            print(f"  ⚠️ 국민 역할 부여 실패: {e}")
                
                # 비국민 역할 제거
                if SUCCESS_ROLE_ID_OUT != 0:
                    out_role = guild.get_role(SUCCESS_ROLE_ID_OUT)
                    if out_role and out_role in member.roles:
                        try:
                            await member.remove_roles(out_role)
                            role_removed = out_role.name
                            print(f"  ✅ 비국민 역할 제거: {out_role.name}")
                        except Exception as e:
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
                        try:
                            await member.add_roles(out_role)
                            role_added = out_role.name
                            print(f"  ✅ 비국민 역할 부여: {out_role.name}")
                        except Exception as e:
                            print(f"  ⚠️ 비국민 역할 부여 실패: {e}")
                
                # 국민 역할 제거
                if SUCCESS_ROLE_ID != 0:
                    success_role = guild.get_role(SUCCESS_ROLE_ID)
                    if success_role and success_role in member.roles:
                        try:
                            await member.remove_roles(success_role)
                            role_removed = success_role.name
                            print(f"  ✅ 국민 역할 제거: {success_role.name}")
                        except Exception as e:
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
            
            # 변경 사항 표시
            changes = []
            if role_added:
                changes.append(f"• **{role_added}** 역할 추가됨")
            if role_removed:
                changes.append(f"• **{role_removed}** 역할 제거됨")
            
            try:
                changes.append(f"• 닉네임이 **{new_nickname}**로 변경됨")
            except:
                pass
                
            if changes:
                embed.add_field(
                    name="🔄 변경 사항",
                    value="\n".join(changes),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            print(f"🏁 /확인 처리 완료 - {member.display_name}: {nation}")

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

    @app_commands.command(name="테스트", description="봇의 기본 기능을 테스트합니다")
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
        
        # QueueManager에 is_user_in_queue 메서드가 없다면 대체 방법 사용
        try:
            for member in members:
                # 메서드가 존재하는지 확인
                if hasattr(queue_manager, 'is_user_in_queue'):
                    if queue_manager.is_user_in_queue(member.id):
                        already_in_queue += 1
                    else:
                        queue_manager.add_user(member.id)
                        added_count += 1
                else:
                    # is_user_in_queue 메서드가 없으면 항상 추가 시도
                    # add_user에서 중복 확인을 해야 함
                    queue_manager.add_user(member.id)
                    added_count += 1
        except Exception as e:
            print(f"대기열 처리 중 오류: {e}")
            # 모든 멤버를 추가 시도
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
                    url1 = f"https://api.planetearth.kr/discord?discord={discord_id}"
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
                    url2 = f"https://api.planetearth.kr/resident?name={mc_id}"
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
                    url3 = f"https://api.planetearth.kr/town?name={town}"
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

    @확인.error
    @테스트.error
    @스케줄확인.error
    @자동실행시작.error
    @예외설정.error
    @국민확인.error  
    @대기열상태.error
    @대기열초기화.error
    @자동실행.error
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
