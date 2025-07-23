from collections import deque

# queue_manager.py에 다음 메서드를 추가하세요

class QueueManager:
    def __init__(self):
        self.queue = []  # 또는 다른 데이터 구조
        self.processing = False
    
    def is_user_in_queue(self, user_id: int) -> bool:
        """사용자가 이미 대기열에 있는지 확인"""
        return user_id in self.queue
    
    def add_user(self, user_id: int):
        """사용자를 대기열에 추가 (중복 방지)"""
        if not self.is_user_in_queue(user_id):
            self.queue.append(user_id)
            return True
        return False
    
    def get_next(self):
        """대기열에서 다음 사용자 가져오기"""
        if self.queue:
            return self.queue.pop(0)
        return None
    
    def get_queue_size(self) -> int:
        """현재 대기열 크기 반환"""
        return len(self.queue)
    
    def is_processing(self) -> bool:
        """현재 처리 중인지 여부 반환"""
        return self.processing
    
    def clear_queue(self) -> int:
        """대기열 초기화 및 제거된 항목 수 반환"""
        count = len(self.queue)
        self.queue.clear()
        return count

queue_manager = QueueManager()
