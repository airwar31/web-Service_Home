class DeviceManager:
    def __init__(self):
        self.devices = {
            "light": False,
            "heating": False,
            "temperature": 20  # default temperature
        }

    def turn_on_light(self):
        self.devices["light"] = True
        return "Свет включен"

    def turn_off_light(self):
        self.devices["light"] = False
        return "Свет выключен"

    def turn_on_heating(self):
        self.devices["heating"] = True
        return "Отопление включено"

    def turn_off_heating(self):
        self.devices["heating"] = False
        return "Отопление выключено"

    def set_temperature(self, value):
        try:
            temp = int(value)
            self.devices["temperature"] = temp
            return f"Температура установлена на {temp}°C"
        except ValueError:
            return "Неверное значение температуры"

    def increase_temperature(self):
        self.devices["temperature"] += 1
        return f"Температура повышена до {self.devices['temperature']}°C"

    def decrease_temperature(self):
        self.devices["temperature"] -= 1
        return f"Температура понижена до {self.devices['temperature']}°C"

    def get_status(self):
        status = {
            "light": "включен" if self.devices["light"] else "выключен",
            "heating": "включено" if self.devices["heating"] else "выключено",
            "temperature": self.devices["temperature"]
        }
        return status
