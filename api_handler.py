import aiohttp
import os
import json

# 환경변수를 안전하게 가져오기
BASE_URL = os.getenv("MC_API_BASE")
if not BASE_URL:
    print("❌ MC_API_BASE 환경변수가 설정되지 않았습니다.")
    BASE_URL = "https://api.planetearth.kr"  # 기본값
else:
    print(f"✅ MC_API_BASE: {BASE_URL}")

async def get_discord_info(discord_id):
    """Discord ID로 마인크래프트 정보 조회 (개선된 버전)"""
    # 다양한 엔드포인트 시도
    possible_endpoints = [
        f"/discord?discord={discord_id}"
    ]
    
    async with aiohttp.ClientSession() as session:
        for endpoint in possible_endpoints:
            url = f"{BASE_URL}{endpoint}"
            print(f"🔍 시도 중: {url}")
            
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as res:
                    print(f"   📊 응답 상태: HTTP {res.status}")
                    
                    if res.status == 200:
                        data = await res.json()
                        print(f"✅ Discord 정보 조회 성공: {discord_id}")
                        print(f"   🎯 올바른 엔드포인트: {endpoint}")
                        return data
                    elif res.status == 404:
                        print(f"   ❌ 404 Not Found - 다음 엔드포인트 시도")
                        continue
                    else:
                        print(f"   ⚠️ HTTP {res.status} - 응답 내용 확인")
                        try:
                            error_data = await res.json()
                            print(f"   📄 오류 내용: {error_data}")
                        except:
                            error_text = await res.text()
                            print(f"   📄 오류 내용: {error_text}")
                        
            except aiohttp.ClientTimeout:
                print(f"   ⏰ 타임아웃")
                continue
            except Exception as e:
                print(f"   ❌ 오류: {e}")
                continue
    
    print(f"❌ 모든 엔드포인트에서 Discord 정보 조회 실패: {discord_id}")
    return {"status": "FAILED", "message": "All endpoints failed", "discord_id": discord_id}

async def get_resident_info(uuid):
    """UUID로 거주민 정보 조회 (개선된 버전)"""
    # 다양한 엔드포인트 시도
    possible_endpoints = [
        f"/resident?uuid={uuid}"
    ]
    
    async with aiohttp.ClientSession() as session:
        for endpoint in possible_endpoints:
            url = f"{BASE_URL}{endpoint}"
            print(f"🔍 시도 중: {url}")
            
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as res:
                    print(f"   📊 응답 상태: HTTP {res.status}")
                    
                    if res.status == 200:
                        data = await res.json()
                        print(f"✅ 거주민 정보 조회 성공: {uuid}")
                        print(f"   🎯 올바른 엔드포인트: {endpoint}")
                        return data
                    elif res.status == 404:
                        print(f"   ❌ 404 Not Found - 다음 엔드포인트 시도")
                        continue
                    else:
                        print(f"   ⚠️ HTTP {res.status} - 응답 내용 확인")
                        try:
                            error_data = await res.json()
                            print(f"   📄 오류 내용: {error_data}")
                        except:
                            error_text = await res.text()
                            print(f"   📄 오류 내용: {error_text}")
                        
            except aiohttp.ClientTimeout:
                print(f"   ⏰ 타임아웃")
                continue
            except Exception as e:
                print(f"   ❌ 오류: {e}")
                continue
    
    print(f"❌ 모든 엔드포인트에서 거주민 정보 조회 실패: {uuid}")
    return {"status": "FAILED", "message": "All endpoints failed", "uuid": uuid}

async def test_api_endpoints():
    """API 엔드포인트 테스트"""
    test_endpoints = [
        "/",
        "/api",
        "/v1",
        "/discord",
        "/resident",
        "/player",
        "/user"
    ]
    
    async with aiohttp.ClientSession() as session:
        for endpoint in test_endpoints:
            url = f"{BASE_URL}{endpoint}"
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as res:
                    print(f"🔍 {url} -> HTTP {res.status}")
                    if res.status == 200:
                        try:
                            data = await res.json()
                            print(f"   ✅ 응답: {json.dumps(data, indent=2, ensure_ascii=False)[:200]}...")
                        except:
                            text = await res.text()
                            print(f"   ✅ 응답: {text[:200]}...")
                    elif res.status == 404:
                        print(f"   ❌ 404 Not Found")
                    else:
                        print(f"   ⚠️ 상태코드: {res.status}")
            except Exception as e:
                print(f"   ❌ 오류: {e}")

# 테스트 함수
async def main():
    print("=== API 엔드포인트 테스트 ===")
    await test_api_endpoints()
    
    print("\n=== Discord 정보 조회 테스트 ===")
    # 테스트용 Discord ID (실제 값으로 변경)
    test_discord_id = "753079165779050647"
    discord_result = await get_discord_info(test_discord_id)
    print(f"Discord 조회 결과: {json.dumps(discord_result, indent=2, ensure_ascii=False)}")
    
    print("\n=== 거주민 정보 조회 테스트 ===")
    # 테스트용 UUID (실제 값으로 변경)
    test_uuid = "550e8400-e29b-41d4-a716-446655440000"
    resident_result = await get_resident_info(test_uuid)
    print(f"거주민 조회 결과: {json.dumps(resident_result, indent=2, ensure_ascii=False)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())