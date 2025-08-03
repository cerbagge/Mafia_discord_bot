import json
import os
from typing import Dict, Optional

class CallsignManager:
    """사용자 콜사인을 관리하는 클래스"""
    
    def __init__(self, filename: str = "callsigns.json"):
        self.filename = filename
        self._callsigns: Dict[int, str] = {}  # user_id -> callsign
        self.load_callsigns()
    
    def load_callsigns(self):
        """콜사인 목록을 파일에서 로드"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 문자열 키를 정수로 변환
                    raw_callsigns = data.get('callsigns', {})
                    self._callsigns = {int(k): v for k, v in raw_callsigns.items()}
                print(f"✅ 콜사인 목록 로드: {len(self._callsigns)}개")
            else:
                print(f"📁 콜사인 파일이 없어서 새로 생성합니다: {self.filename}")
                self.save_callsigns()
        except Exception as e:
            print(f"❌ 콜사인 목록 로드 실패: {e}")
            self._callsigns = {}
    
    def save_callsigns(self):
        """콜사인 목록을 파일에 저장"""
        try:
            data = {
                'callsigns': {str(k): v for k, v in self._callsigns.items()},  # 정수 키를 문자열로 변환
                'count': len(self._callsigns),
                'description': '사용자 Discord ID와 콜사인의 매핑 정보'
            }
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"💾 콜사인 목록 저장: {len(self._callsigns)}개")
        except Exception as e:
            print(f"❌ 콜사인 목록 저장 실패: {e}")
    
    def set_callsign(self, user_id: int, callsign: str) -> bool:
        """사용자 콜사인 설정"""
        self._callsigns[user_id] = callsign
        self.save_callsigns()
        print(f"✅ 콜사인 설정: {user_id} -> {callsign}")
        return True
    
    def get_callsign(self, user_id: int) -> Optional[str]:
        """사용자 콜사인 조회"""
        return self._callsigns.get(user_id)
    
    def remove_callsign(self, user_id: int) -> bool:
        """사용자 콜사인 제거"""
        if user_id in self._callsigns:
            del self._callsigns[user_id]
            self.save_callsigns()
            print(f"🗑️ 콜사인 제거: {user_id}")
            return True
        return False
    
    def get_all_callsigns(self) -> Dict[int, str]:
        """모든 콜사인 반환"""
        return self._callsigns.copy()
    
    def get_callsign_count(self) -> int:
        """설정된 콜사인 개수 반환"""
        return len(self._callsigns)
    
    def has_callsign(self, user_id: int) -> bool:
        """사용자가 콜사인을 설정했는지 확인"""
        return user_id in self._callsigns
    
    def clear_all_callsigns(self) -> int:
        """모든 콜사인 삭제 및 삭제된 개수 반환"""
        count = len(self._callsigns)
        self._callsigns.clear()
        self.save_callsigns()
        print(f"🧹 모든 콜사인 삭제: {count}개")
        return count
    
    def find_users_by_callsign(self, callsign: str) -> list:
        """특정 콜사인을 사용하는 사용자 ID 목록 반환"""
        return [user_id for user_id, user_callsign in self._callsigns.items() if user_callsign == callsign]

# 전역 콜사인 관리자 인스턴스
callsign_manager = CallsignManager()

# 유틸리티 함수들
def get_user_display_info(user_id: int, mc_id: str = None, nation: str = None) -> str:
    """사용자의 표시 정보를 반환 (콜사인 포함)"""
    callsign = callsign_manager.get_callsign(user_id)
    
    if callsign:
        if nation:
            return f"{mc_id} ㅣ {callsign}"
        else:
            return f"{mc_id or 'Unknown'} ㅣ {callsign}"
    else:
        if nation:
            return f"{mc_id} ㅣ {nation}"
        else:
            return mc_id or 'Unknown'

def validate_callsign(callsign: str) -> tuple[bool, str]:
    """콜사인 유효성 검사"""
    # 길이 제한 (Discord 닉네임 32자 제한 고려)
    if len(callsign) > 20:
        return False, "콜사인이 너무 깁니다. (최대 20자)"
    
    if len(callsign) < 1:
        return False, "콜사인이 너무 짧습니다. (최소 1자)"
    
    # 금지된 문자 확인
    forbidden_chars = ['@', '#', ':', '```', '`']
    for char in forbidden_chars:
        if char in callsign:
            return False, f"콜사인에 금지된 문자가 포함되어 있습니다: {char}"
    
    # Discord 멘션 형태 방지
    if callsign.startswith('<') and callsign.endswith('>'):
        return False, "콜사인이 Discord 멘션 형태입니다."
    
    return True, "유효한 콜사인입니다."

if __name__ == "__main__":
    # 테스트 코드
    print("🧪 CallsignManager 테스트")
    
    # 콜사인 설정 테스트
    callsign_manager.set_callsign(123456789, "TestCallsign")
    print(f"콜사인 개수: {callsign_manager.get_callsign_count()}")
    
    # 콜사인 조회 테스트
    callsign = callsign_manager.get_callsign(123456789)
    print(f"테스트 사용자 콜사인: {callsign}")
    
    # 유효성 검사 테스트
    valid, message = validate_callsign("ValidCallsign")
    print(f"유효성 검사: {valid} - {message}")
    
    # 콜사인 제거 테스트
    callsign_manager.remove_callsign(123456789)
    print(f"콜사인 개수: {callsign_manager.get_callsign_count()}")
    
    print("✅ 테스트 완료")