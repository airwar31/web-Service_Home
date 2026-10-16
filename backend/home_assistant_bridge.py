"""Home Assistant bridge: publish voice intents to HA via REST API or MQTT.

Behavior:
 - If environment variables HA_URL and HA_TOKEN are set, the bridge will attempt
   to call Home Assistant REST services for common actions.
 - If MQTT_BROKER is set, the bridge will publish a generic intent JSON to
   MQTT topic (default: homeassistant/voice/commands). This allows Home Assistant
   automations to subscribe and map intents to devices (recommended for flexible mapping).

The bridge is best-effort and non-blocking from the app side; failures are logged
but do not raise to the caller.
"""
from __future__ import annotations

import os
import json
import threading
from typing import Dict, Any, Optional
from pathlib import Path

try:
    import requests
except Exception:
    requests = None  # type: ignore

try:
    import paho.mqtt.client as mqtt
except Exception:
    mqtt = None  # type: ignore


HA_URL = os.getenv("HA_URL")
HA_TOKEN = os.getenv("HA_TOKEN")
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "homeassistant/voice/commands")
HA_MAP_PATH = os.path.join(os.path.dirname(__file__), "ha_map.json")


def _call_ha_service(domain: str, service: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Call Home Assistant REST API service endpoint.

    Returns parsed JSON on success or None on failure.
    """
    if not HA_URL or not HA_TOKEN:
        return None
    if requests is None:
        print("home_assistant_bridge: requests library not installed")
        return None

    url = HA_URL.rstrip("/") + f"/api/services/{domain}/{service}"
    headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=6)
        if resp.status_code >= 400:
            print(f"home_assistant_bridge: HA service call failed {resp.status_code}: {resp.text}")
            return None
        try:
            return resp.json()
        except Exception:
            return {"status": "ok"}
    except Exception as e:
        print(f"home_assistant_bridge: Exception calling HA service: {e}")
        return None


def call_service(domain: str, service: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Public wrapper to call Home Assistant service via REST API.

    Returns dict with keys: success: bool, result: Optional[dict], error: Optional[str]
    """
    try:
        if not HA_URL or not HA_TOKEN:
            return {"success": False, "result": None, "error": "HA_URL or HA_TOKEN not configured"}
        res = _call_ha_service(domain, service, data)
        if res is None:
            return {"success": True, "result": {}, "error": None}
        return {"success": True, "result": res, "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}


def _publish_mqtt(payload: Dict[str, Any]) -> None:
    if not MQTT_BROKER:
        return
    if mqtt is None:
        print("home_assistant_bridge: paho-mqtt not installed")
        return

    try:
        client = mqtt.Client()
        if MQTT_USER:
            client.username_pw_set(MQTT_USER, MQTT_PASS)
        client.connect(MQTT_BROKER, MQTT_PORT, 10)
        client.loop_start()
        client.publish(MQTT_TOPIC, json.dumps(payload), qos=0, retain=False)
        client.loop_stop()
        client.disconnect()
    except Exception as e:
        print(f"home_assistant_bridge: MQTT publish failed: {e}")


_ACTION_TO_HA: Dict[str, tuple[str, str]] = {
    # action -> (domain, service)
    "turn_on_light": ("light", "turn_on"),
    "turn_off_light": ("light", "turn_off"),
    "open_curtain": ("cover", "open_cover"),
    "close_curtain": ("cover", "close_cover"),
    "start_vacuum": ("vacuum", "start"),
    "stop_vacuum": ("vacuum", "stop"),
    "set_temperature": ("climate", "set_temperature"),
    "set_humidity": ("climate", "set_humidity"),
}


def _prepare_ha_data(parsed: Dict[str, Any]) -> Dict[str, Any]:
    params = parsed.get("params", {}) or {}
    room = params.get("room")
    data: Dict[str, Any] = {}
    # Prefer entity_id/area_id mapping from ha_map.json when available
    mapped = {}
    try:
        if Path(HA_MAP_PATH).exists():
            with open(HA_MAP_PATH, "r", encoding="utf-8") as f:
                mapped = json.load(f)
    except Exception:
        mapped = {}

    if room:
        # If mapping exists for room, try to pick appropriate entity or area
        room_map = mapped.get(room) or {}
        # If mapping provides a thermostat/entity for climate, prefer that
        if room_map:
            # put the whole mapping in data for calling services that accept entity_id
            data.update(room_map)
        else:
            # Fallback to area_id with raw room name
            data["area_id"] = str(room)

    # For set_temperature include temperature
    if parsed.get("action") == "set_temperature" and "value" in params:
        data["temperature"] = float(params["value"])
    if parsed.get("action") == "set_humidity" and "value" in params:
        data["humidity"] = float(params["value"])

    return data



def notify_home_assistant(parsed: Dict[str, Any]) -> None:
    """Notify Home Assistant about a parsed intent.

    This function is safe to call from the main thread; it will try REST first,
    then publish MQTT as fallback / parallel signal. Errors are printed but not raised.
    """
    try:
        action = parsed.get("action")
        payload = {"action": action, "params": parsed.get("params", {}), "raw": parsed.get("raw")}

        # Try REST mapping first
        mapped = _ACTION_TO_HA.get(action)
        if mapped and HA_URL and HA_TOKEN and requests:
            domain, service = mapped
            data = _prepare_ha_data(parsed)
            print(f"home_assistant_bridge: calling HA service {domain}.{service} with {data}")
            _call_ha_service(domain, service, data)

        # Always publish MQTT if broker configured so automations can react
        if MQTT_BROKER and mqtt:
            print(f"home_assistant_bridge: publishing intent to MQTT topic {MQTT_TOPIC}")
            _publish_mqtt(payload)

    except Exception as e:
        print(f"home_assistant_bridge: unexpected error: {e}")


def notify_home_assistant_async(parsed: Dict[str, Any]) -> None:
    """Run notify_home_assistant in a separate daemon thread."""
    try:
        t = threading.Thread(target=notify_home_assistant, args=(parsed,), daemon=True)
        t.start()
    except Exception as e:
        print(f"home_assistant_bridge: failed to start thread: {e}")
