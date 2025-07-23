import os
from dotenv import load_dotenv
from typing import Optional, Union

class Config:
    """환경변수를 중앙에서 관리하는 클래스"""
    
    def __init__(self):
        # .env 파일 로드 (우선순위: 현재 디렉토리 > 상위 디렉토리)
        for env_path in ['.env', '../.env']:
            if os.path.exists(env_path):
                load_dotenv(env_path)
                print(f"🔧 환경변수 로드: {env_path}")
                break
        else:
            print("⚠️ .env 파일을 찾을 수 없습니다. 시스템 환경변수를 사용합니다.")
        
        # 환경변수 로드 및 검증
        self._load_and_validate()
    
    def _load_and_validate(self):
        """환경변수 로드 및 검증"""
        # Discord 토큰
        self.DISCORD_TOKEN = self._get_env("DISCORD_TOKEN") or self._get_env("BOT_TOKEN")
        if not self.DISCORD_TOKEN:
            raise ValueError("❌ DISCORD_TOKEN 또는 BOT_TOKEN이 필요합니다.")

        # API 설정
        self.MC_API_BASE = self._get_env("MC_API_BASE", "https://api.planetearth.kr")
        
        # Discord 서버 설정
        self.GUILD_ID = self._get_env_int("GUILD_ID")
        self.SUCCESS_ROLE_ID = self._get_env_int("SUCCESS_ROLE_ID")
        
        # 채널 설정
        self.LOG_CHANNEL_ID = self._get_env_int("LOG_CHANNEL_ID")
        self.SUCCESS_CHANNEL_ID = self._get_env_int("SUCCESS_CHANNEL_ID")
        self.FAILURE_CHANNEL_ID = self._get_env_int("FAILURE_CHANNEL_ID")
        self.WELCOME_CHANNEL_ID = self._get_env_int("WELCOME_CHANNEL_ID")
        
        # 자동 실행 설정
        self.AUTO_ROLE_IDS = self._get_env("AUTO_ROLE_IDS", "")
        self.AUTO_EXECUTION_DAY = self._get_env_int("AUTO_EXECUTION_DAY", 6)
        self.AUTO_EXECUTION_HOUR = self._get_env_int("AUTO_EXECUTION_HOUR", 2)
        self.AUTO_EXECUTION_MINUTE = self._get_env_int("AUTO_EXECUTION_MINUTE", 0)

        # 범위 유효성 검사
        if not (0 <= self.AUTO_EXECUTION_HOUR <= 23):
            raise ValueError("❌ AUTO_EXECUTION_HOUR는 0~23 사이여야 합니다.")
        if not (0 <= self.AUTO_EXECUTION_MINUTE <= 59):
            raise ValueError("❌ AUTO_EXECUTION_MINUTE는 0~59 사이여야 합니다.")
        
        # 추가 설정
        self.AUTO_ADD_NEW_MEMBERS = self._get_env_bool("AUTO_ADD_NEW_MEMBERS", True)

        # 인증 관련 설정
        self.BASE_NATION = self._get_env("BASE_NATION", "Red_Mafia")
        self.REMOVE_ROLE_IF_WRONG_NATION = self._get_env_bool("REMOVE_ROLE_IF_WRONG_NATION", True)
        
        # 필수 항목 검증
        self._validate_config()
    
    def _get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """환경변수 가져오기"""
        return os.getenv(key, default)
    
    def _get_env_int(self, key: str, default: Optional[int] = None) -> Optional[int]:
        """환경변수를 int로 변환하여 가져오기"""
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            print(f"⚠️ {key}의 값 '{value}'을(를) 정수로 변환할 수 없습니다. 기본값 사용: {default}")
            return default
    
    def _get_env_bool(self, key: str, default: bool = False) -> bool:
        """환경변수를 bool로 변환하여 가져오기"""
        value = os.getenv(key, "").lower()
        return value in ("true", "1", "yes", "on") if value else default
    
    def _validate_config(self):
        """필수 환경변수 검증"""
        required_vars = {
            "DISCORD_TOKEN": self.DISCORD_TOKEN,
            "GUILD_ID": self.GUILD_ID,
            "SUCCESS_ROLE_ID": self.SUCCESS_ROLE_ID,
            "SUCCESS_CHANNEL_ID": self.SUCCESS_CHANNEL_ID,
            "FAILURE_CHANNEL_ID": self.FAILURE_CHANNEL_ID
        }
        
        missing_vars = []
        for var_name, var_value in required_vars.items():
            if var_value is None:
                missing_vars.append(var_name)
        
        if missing_vars:
            print(f"❌ 필수 환경변수가 설정되지 않았습니다: {', '.join(missing_vars)}")
            raise ValueError(f"필수 환경변수가 누락되었습니다: {', '.join(missing_vars)}")
    
    def print_config_status(self):
        """설정 상태 출력"""
        print("📋 환경변수 상태:")
        config_items = [
            ("DISCORD_TOKEN", "✅ 설정됨" if self.DISCORD_TOKEN else "❌ 누락"),
            ("MC_API_BASE", self.MC_API_BASE),
            ("GUILD_ID", self.GUILD_ID),
            ("SUCCESS_ROLE_ID", self.SUCCESS_ROLE_ID),
            ("SUCCESS_CHANNEL_ID", self.SUCCESS_CHANNEL_ID),
            ("FAILURE_CHANNEL_ID", self.FAILURE_CHANNEL_ID),
            ("WELCOME_CHANNEL_ID", self.WELCOME_CHANNEL_ID),
            ("AUTO_ADD_NEW_MEMBERS", self.AUTO_ADD_NEW_MEMBERS),
            ("BASE_NATION", self.BASE_NATION),
            ("REMOVE_ROLE_IF_WRONG_NATION", self.REMOVE_ROLE_IF_WRONG_NATION),
        ]
        
        for name, value in config_items:
            print(f"   - {name}: {value if value is not None else '❌ 누락'}")
    
    def get_auto_role_ids(self) -> list[int]:
        """자동 역할 ID 리스트 반환"""
        if not self.AUTO_ROLE_IDS:
            return []
        
        role_ids = []
        for role_id_str in self.AUTO_ROLE_IDS.split(','):
            role_id_str = role_id_str.strip()
            if role_id_str:
                try:
                    role_ids.append(int(role_id_str))
                except ValueError:
                    print(f"⚠️ 잘못된 역할 ID: {role_id_str}")
        
        return role_ids


# 전역 설정 인스턴스
try:
    config = Config()
    print("✅ 환경변수 설정 완료")
    config.print_config_status()
except Exception as e:
    print(f"❌ 환경변수 설정 실패: {e}")
    raise
