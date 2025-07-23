import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal
import aiohttp
import os
import time

from queue_manager import queue_manager

MC_API_BASE = os.getenv("MC_API_BASE")  # 예: https://api.planetearth.kr
BASE_NATION = os.getenv("BASE_NATION", "Red_Magfia")  # .env에서 국가 설정



class SlashCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_admin(interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator
    
    def is_admin_ctx(self, ctx):
        """접두사 커맨드용 관리자 권한 확인"""
        return ctx.author.guild_permissions.administrator

    # 접두사 커맨드 pe 추가
    @commands.command(name="pe")
    async def pe_prefix(self, ctx, user_id: str):
        """접두사 버전: $pe <user_id>"""
        # 관리자 권한 확인
        if not self.is_admin_ctx(ctx):
            await ctx.send("🚫 이 명령어는 관리자만 사용할 수 있습니다.", delete_after=5)
            return
        
        try:
            queue_manager.add_user(int(user_id))
            await ctx.send(f"✅ <@{user_id}> 대기열에 추가됨")
        except ValueError:
            await ctx.send("🚫 올바른 유저 ID를 입력해주세요.")
        except Exception as e:
            await ctx.send(f"🚫 오류 발생: `{str(e)}`")

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

    @app_commands.command(name="pe", description="유저를 인증 대기열에 추가")
    @app_commands.describe(user_id="디스코드 유저 ID")
    @app_commands.check(is_admin)
    async def pe(self, interaction: discord.Interaction, user_id: str):
        try:
            queue_manager.add_user(int(user_id))
            await interaction.response.send_message(f"✅ <@{user_id}> 대기열에 추가됨", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"🚫 오류 발생: `{str(e)}`", ephemeral=True)

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

        async with aiohttp.ClientSession() as session:
            for member in members:
                discord_id = member.id

                try:
                    # 1단계: 디스코드 ID → 마크 ID
                    url1 = f"https://api.planetearth.kr/discord?discord={discord_id}"
                    async with session.get(url1, timeout=aiohttp.ClientTimeout(total=10)) as r1:
                        if r1.status != 200:
                            errors.append(f"{member.mention} - 마크ID 조회 실패 ({r1.status})")
                            continue
                        data1 = await r1.json()
                        mc_id = data1['data'][0]['name']
                        if not mc_id:
                            errors.append(f"{member.mention} - 마크ID 없음")
                            continue
                        time.sleep(5)

                    # 2단계: 마크 ID → 마을
                    url2 = f"https://api.planetearth.kr/resident?name={mc_id}"
                    async with session.get(url2, timeout=aiohttp.ClientTimeout(total=10)) as r2:
                        if r2.status != 200:
                            errors.append(f"{member.mention} (마크: {mc_id}) - 마을 조회 실패 ({r2.status})")
                            continue
                        data2 = await r2.json()
                        town = data2['data'][0]['town']
                        if not town:
                            errors.append(f"{member.mention} (마크: {mc_id}) - 마을 없음")
                            continue
                        time.sleep(5)

                    # 3단계: 마을 → 국가
                    url3 = f"https://api.planetearth.kr/town?name={town}"
                    async with session.get(url3, timeout=aiohttp.ClientTimeout(total=10)) as r3:
                        if r3.status != 200:
                            errors.append(f"{member.mention} (마을: {town}) - 국가 조회 실패 ({r3.status})")
                            continue
                        data3 = await r3.json()
                        nation = data3['data'][0]['nation']
                        if not nation:
                            errors.append(f"{member.mention} (마을: {town}) - 국가 없음")
                            continue
                        time.sleep(5)

                        if nation != BASE_NATION:
                            not_base_nation.append(f"{member.mention} (국가: {nation}, 마크: {mc_id})")

                except Exception as e:
                    errors.append(f"{member.mention} - 오류 발생: {str(e)[:50]}")

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
            estimated_time = queue_size * 57  # 대략 배치당 57초 추정
            minutes = estimated_time // 60
            seconds = estimated_time % 60

        if minutes > 0:
            time_str = f"약 {minutes}분 {seconds}초"
        else:
            time_str = f"약 {seconds}초"

        embed.add_field(
            name="⏰ 예상 완료 시간",
            value=time_str,
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

    # 접두사 커맨드 에러 핸들러
    @pe_prefix.error
    async def pe_prefix_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("🚫 이 명령어는 관리자만 사용할 수 있습니다.", delete_after=5)
        else:
            await ctx.send(f"❗ 오류 발생: `{str(error)}`", delete_after=5)

    @pe.error
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