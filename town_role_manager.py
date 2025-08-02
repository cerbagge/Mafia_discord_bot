# town_role_manager.py
"""
마을-역할 매핑 관리 시스템
기존 Discord 역할과 마인크래프트 마을을 연동하는 기능을 제공합니다.
"""

import json
import os
import aiohttp
from typing import Dict, List, Optional

class TownRoleManager:
    """마을-역할 매핑을 관리하는 클래스"""
    
    def __init__(self, filename: str = "town_role_mapping.json"):
        self.filename = filename
        self._mapping: Dict[str, int] = {}  # town_name -> role_id
        self.load_mapping()
    
    def load_mapping(self):
        """마을-역할 매핑을 파일에서 로드"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._mapping = data.get('town_role_mapping', {})
                print(f"✅ 마을 역할 매핑 로드: {len(self._mapping)}개")
            else:
                print(f"📁 마을 역할 매핑 파일이 없어서 새로 생성합니다: {self.filename}")
                self.save_mapping()
        except Exception as e:
            print(f"❌ 마을 역할 매핑 로드 실패: {e}")
            self._mapping = {}
    
    def save_mapping(self):
        """마을-역할 매핑을 파일에 저장"""
        try:
            data = {
                'town_role_mapping': self._mapping,
                'count': len(self._mapping),
                'description': '마을 이름과 Discord 역할 ID의 매핑 정보'
            }
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"💾 마을 역할 매핑 저장: {len(self._mapping)}개")
        except Exception as e:
            print(f"❌ 마을 역할 매핑 저장 실패: {e}")
    
    def add_mapping(self, town_name: str, role_id: int) -> bool:
        """마을-역할 매핑 추가"""
        self._mapping[town_name] = role_id
        self.save_mapping()
        print(f"➕ 마을 역할 매핑 추가: {town_name} -> {role_id}")
        return True
    
    def remove_mapping(self, town_name: str) -> bool:
        """마을-역할 매핑 제거"""
        if town_name in self._mapping:
            del self._mapping[town_name]
            self.save_mapping()
            print(f"➖ 마을 역할 매핑 제거: {town_name}")
            return True
        return False
    
    def get_role_id(self, town_name: str) -> Optional[int]:
        """마을에 해당하는 역할 ID 반환"""
        return self._mapping.get(town_name)
    
    def get_all_mappings(self) -> Dict[str, int]:
        """모든 매핑 반환"""
        return self._mapping.copy()
    
    def get_mapped_towns(self) -> List[str]:
        """매핑된 마을 목록 반환"""
        return list(self._mapping.keys())
    
    def get_mapping_count(self) -> int:
        """매핑된 마을-역할 개수 반환"""
        return len(self._mapping)
    
    def is_town_mapped(self, town_name: str) -> bool:
        """마을이 역할과 매핑되어 있는지 확인"""
        return town_name in self._mapping
    
    def clear_all_mappings(self) -> int:
        """모든 매핑 삭제 및 삭제된 개수 반환"""
        count = len(self._mapping)
        self._mapping.clear()
        self.save_mapping()
        print(f"🗑️ 모든 마을 역할 매핑 삭제: {count}개")
        return count

# 전역 마을 역할 관리자 인스턴스
town_role_manager = TownRoleManager()

async def get_towns_in_nation(nation_name: str) -> List[str]:
    """특정 국가의 마을 목록 조회"""
    try:
        # config에서 API 베이스 URL 가져오기
        try:
            from config import config
            api_base = config.MC_API_BASE
        except:
            import os
            api_base = os.getenv("MC_API_BASE", "https://api.planetearth.kr")
        
        async with aiohttp.ClientSession() as session:
            url = f"{api_base}/nation?name={nation_name}"
            print(f"🔍 국가 정보 조회: {url}")
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    print(f"❌ 국가 정보 조회 실패: HTTP {response.status}")
                    return []
                
                data = await response.json()
                if not data.get('data') or not data['data']:
                    print(f"❌ 국가 데이터 없음: {nation_name}")
                    return []
                
                nation_data = data['data'][0]
                towns = nation_data.get('towns', [])
                
                if not towns:
                    print(f"ℹ️ {nation_name}에 마을이 없습니다.")
                    return []
                
                print(f"✅ {nation_name} 마을 목록: {len(towns)}개")
                return towns
                
    except Exception as e:
        print(f"❌ 마을 목록 조회 오류: {e}")
        return []

def get_town_role_status(town_name: str, guild=None) -> Dict[str, any]:
    """마을의 역할 연동 상태를 반환"""
    role_id = town_role_manager.get_role_id(town_name)
    
    status = {
        'town_name': town_name,
        'is_mapped': role_id is not None,
        'role_id': role_id,
        'role_exists': False,
        'role_name': None,
        'role_mention': None
    }
    
    if role_id and guild:
        role = guild.get_role(role_id)
        if role:
            status['role_exists'] = True
            status['role_name'] = role.name
            status['role_mention'] = role.mention
    
    return status

# 유틸리티 함수들
def format_town_role_info(town: str, guild=None) -> str:
    """마을 역할 정보를 포맷된 문자열로 반환"""
    status = get_town_role_status(town, guild)
    
    if not status['is_mapped']:
        return f"**{town}** → ℹ️ 역할 연동 안됨"
    elif status['role_exists']:
        return f"**{town}** → {status['role_mention']}"
    else:
        return f"**{town}** → ⚠️ 역할 없음 (ID: {status['role_id']})"

def get_unmapped_towns(all_towns: List[str]) -> List[str]:
    """매핑되지 않은 마을 목록 반환"""
    mapped_towns = town_role_manager.get_mapped_towns()
    return [town for town in all_towns if town not in mapped_towns]

def get_mapped_towns_with_roles(guild) -> List[Dict[str, any]]:
    """매핑된 마을들의 역할 정보 반환"""
    results = []
    for town_name, role_id in town_role_manager.get_all_mappings().items():
        role = guild.get_role(role_id) if guild else None
        results.append({
            'town': town_name,
            'role_id': role_id,
            'role': role,
            'role_exists': role is not None
        })
    return results

if __name__ == "__main__":
    # 테스트 코드
    print("🧪 TownRoleManager 테스트")
    
    # 매핑 추가 테스트
    town_role_manager.add_mapping("TestTown", 123456789)
    print(f"매핑 개수: {town_role_manager.get_mapping_count()}")
    
    # 매핑 조회 테스트
    role_id = town_role_manager.get_role_id("TestTown")
    print(f"TestTown 역할 ID: {role_id}")
    
    # 상태 정보 테스트
    status = get_town_role_status("TestTown")
    print(f"TestTown 상태: {status}")
    
    # 매핑 제거 테스트
    town_role_manager.remove_mapping("TestTown")
    print(f"매핑 개수: {town_role_manager.get_mapping_count()}")
    
    print("✅ 테스트 완료")