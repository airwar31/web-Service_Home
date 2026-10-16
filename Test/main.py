import requests
import json
from typing import Optional, Dict, Any, List

class ConnectedSamsungTV:
    def __init__(self, ha_url: str, ha_token: str, tv_entity_id: str = "media_player.samsung_7_series_55_ue55tu7500uxru"):
        self.ha_url = ha_url.rstrip('/')
        self.ha_token = ha_token
        self.tv_entity_id = tv_entity_id
        self.headers = {
            'Authorization': f'Bearer {self.ha_token}',
            'Content-Type': 'application/json'
        }
        
    def connect(self) -> bool:
        """Проверка подключения к телевизору"""
        try:
            # Просто проверяем, что entity существует
            state = self.get_state()
            if state:
                print(f"✓ Подключено к: {state.get('friendly_name', self.tv_entity_id)}")
                return True
            else:
                print("✗ Телевизор не найден или недоступен")
                return False
                
        except Exception as e:
            print(f"✗ Ошибка подключения: {e}")
            return False
    
    def _call_service(self, service: str, service_data: Optional[Dict] = None) -> bool:
        """Вызов сервиса Home Assistant"""
        url = f"{self.ha_url}/api/services/media_player/{service}"
        data = {
            "entity_id": self.tv_entity_id
        }
        
        if service_data:
            data.update(service_data)
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=data,
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Ошибка при вызове сервиса {service}: {e}")
            return False
    
    def get_state(self) -> Optional[Dict[str, Any]]:
        """Получить состояние телевизора"""
        url = f"{self.ha_url}/api/states/{self.tv_entity_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Ошибка получения состояния: {response.status_code}")
                return None
        except Exception as e:
            print(f"Ошибка при получении состояния: {e}")
            return None
    
    def turn_on(self) -> bool:
        return self._call_service("turn_on")
    
    def turn_off(self) -> bool:
        return self._call_service("turn_off")
    
    def set_volume(self, volume: float) -> bool:
        return self._call_service("volume_set", {"volume_level": volume})
    
    def volume_up(self) -> bool:
        return self._call_service("volume_up")
    
    def volume_down(self) -> bool:
        return self._call_service("volume_down")
    
    def select_source(self, source: str) -> bool:
        return self._call_service("select_source", {"source": source})
    
    def media_play(self) -> bool:
        return self._call_service("media_play")
    
    def media_pause(self) -> bool:
        return self._call_service("media_pause")
    
    def is_on(self) -> bool:
        state = self.get_state()
        return state and state.get('state') == 'on'

def test_connection():
    """Тест подключения к Home Assistant"""
    HA_URL = os.getenv("HA_URL", "http://localhost:8123")
    HA_TOKEN = os.getenv("HA_TOKEN", "")
    
    print("Подключение к телевизору:")
    tv = ConnectedSamsungTV(HA_URL, HA_TOKEN)
    if tv.connect():
        state = tv.get_state()
        print(f"Состояние телевизора: {state}")
        
        # Включить телевизор
        if tv.volume_down():
            print("✓ Команда включения отправлена")
        
        # Проверить состояние через 2 секунды


if __name__ == "__main__":
    test_connection()