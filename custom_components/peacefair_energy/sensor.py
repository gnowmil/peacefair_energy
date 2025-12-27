"""Peacefair Energy Monitor 的 Sensor 平台。"""
import logging
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
    RestoreSensor,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import (
    COORDINATOR,
    DOMAIN,
    POWER_FACTOR,
    VERSION,
    CONF_SUMMER_MONTHS,
    CONF_SUMMER_TIER1,
    CONF_SUMMER_TIER2,
    CONF_NON_SUMMER_TIER1,
    CONF_NON_SUMMER_TIER2,
    CONF_PRICE_L1,
    CONF_PRICE_L2,
    CONF_PRICE_L3,
    DEFAULT_SUMMER_MONTHS,
    DEFAULT_SUMMER_TIER1,
    DEFAULT_SUMMER_TIER2,
    DEFAULT_NON_SUMMER_TIER1,
    DEFAULT_NON_SUMMER_TIER2,
    DEFAULT_PRICE_L1,
    DEFAULT_PRICE_L2,
    DEFAULT_PRICE_L3,
)

_LOGGER = logging.getLogger(__name__)

# 基礎電氣參數傳感器定義
SENSOR_TYPES = {
    SensorDeviceClass.VOLTAGE: {
        "name": "Voltage",
        "unit": UnitOfElectricPotential.VOLT,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:flash",
    },
    SensorDeviceClass.CURRENT: {
        "name": "Current",
        "unit": UnitOfElectricCurrent.AMPERE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:current-ac",
    },
    SensorDeviceClass.POWER: {
        "name": "Power",
        "unit": UnitOfPower.WATT,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:power-plug",
    },
    SensorDeviceClass.ENERGY: {
        "name": "Total Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:meter-electric",
    },
    SensorDeviceClass.FREQUENCY: {
        "name": "Frequency",
        "unit": UnitOfFrequency.HERTZ,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:sine-wave",
    },
    POWER_FACTOR: {
        "name": "Power Factor",
        "unit": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:angle-acute",
        "device_class": SensorDeviceClass.POWER_FACTOR,
    },
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """設置傳感器平台。"""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    ident = coordinator.host.replace(".", "_")
    entities = []

    # 1. 創建基礎電氣參數傳感器
    for sensor_type in SENSOR_TYPES:
        entities.append(PeacefairSensor(coordinator, sensor_type, ident))

    # 2. 創建本月電量統計傳感器 (RestoreSensor)
    # 用於計算階梯電價，替代外部的 sensor.month_real
    monthly_sensor = PeacefairMonthlyEnergy(coordinator, ident, config_entry)
    entities.append(monthly_sensor)

    # 3. 創建階梯電價相關傳感器 (依賴本月電量傳感器)
    entities.append(PeacefairLevelSensor(coordinator, ident, config_entry, monthly_sensor))
    entities.append(PeacefairPriceSensor(coordinator, ident, config_entry, monthly_sensor))

    async_add_entities(entities)


class PeacefairSensor(CoordinatorEntity, SensorEntity):
    """基礎 Peacefair 傳感器 (電壓、電流等)。"""

    def __init__(self, coordinator, sensor_type, ident):
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._ident = ident
        sensor_info = SENSOR_TYPES[sensor_type]

        self._attr_name = f"{ident} {sensor_info['name']}"
        self._attr_unique_id = f"{DOMAIN}_{self._ident}_{self._sensor_type}"
        self._attr_native_unit_of_measurement = sensor_info.get("unit")
        self._attr_state_class = sensor_info.get("state_class")
        self._attr_icon = sensor_info.get("icon")
        self._attr_device_class = sensor_info.get("device_class", self._sensor_type)

        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._ident)},
            "name": f"Peacefair Energy Monitor {self._ident}",
            "manufacturer": "Peacefair",
            "model": "PZEM-004T",
            "sw_version": VERSION,
        }

    @property
    def native_value(self):
        if self.coordinator.data:
            return self.coordinator.data.get(self._sensor_type)
        return None

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None


class PeacefairMonthlyEnergy(CoordinatorEntity, RestoreSensor):
    """
    計算本月用電量的傳感器。
    
    邏輯：
    1. 記錄每個月初的總電量 (start_energy)。
    2. 本月用電量 = 當前總電量 - start_energy。
    3. 每月 1 號自動重置 start_energy。
    4. 重啟時恢復狀態，防止數據丟失。
    """

    def __init__(self, coordinator, ident, config_entry):
        super().__init__(coordinator)
        self._ident = ident
        self._attr_name = f"{ident} Monthly Energy"
        self._attr_unique_id = f"{DOMAIN}_{ident}_month_real"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_icon = "mdi:calendar-month"
        
        # 狀態變量
        self._start_energy = None
        self._last_reset_month = None

    async def async_added_to_hass(self):
        """當實體添加到 HA 時調用。恢復狀態。"""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            # 恢復屬性
            self._start_energy = state.attributes.get("start_energy")
            self._last_reset_month = state.attributes.get("last_reset_month")
            
            # 如果恢復的值有效，且沒有新的 coordinator 數據，可以暫時恢復狀態值
            if self._start_energy is not None and self.native_value is None:
                try:
                    self._attr_native_value = float(state.state)
                except (ValueError, TypeError):
                    pass

    @property
    def extra_state_attributes(self):
        """保存狀態屬性以便恢復。"""
        return {
            "start_energy": self._start_energy,
            "last_reset_month": self._last_reset_month,
        }

    @property
    def native_value(self):
        """計算本月用電量。"""
        # 獲取當前總電量
        current_total = self.coordinator.data.get(SensorDeviceClass.ENERGY) if self.coordinator.data else None
        
        if current_total is None:
            return self._attr_native_value  # 如果沒有新數據，返回舊數據（如果有的話）

        now = dt_util.now()
        current_month = now.month

        # 初始化（第一次運行）
        if self._start_energy is None or self._last_reset_month is None:
            self._start_energy = current_total
            self._last_reset_month = current_month
            return 0.0

        # 每月重置邏輯：如果月份變了，重置基準值
        if self._last_reset_month != current_month:
            self._start_energy = current_total
            self._last_reset_month = current_month
            return 0.0

        # 正常計算
        monthly_usage = current_total - self._start_energy
        # 防止設備重置導致的負數（例如 PZEM 被重置了）
        if monthly_usage < 0:
            self._start_energy = current_total
            return 0.0

        return round(monthly_usage, 3)


class PeacefairCalculatedSensor(CoordinatorEntity, SensorEntity):
    """階梯電價相關傳感器的基類。"""
    
    def __init__(self, coordinator, ident, config_entry, monthly_sensor):
        super().__init__(coordinator)
        self._ident = ident
        self._config_entry = config_entry
        self._monthly_sensor = monthly_sensor
        
    @property
    def _current_month_energy(self):
        """獲取本月用電量。"""
        val = self._monthly_sensor.native_value
        try:
            return float(val) if val is not None else 0.0
        except (ValueError, TypeError):
            return 0.0

    @property
    def _options(self):
        """獲取配置選項。"""
        return self._config_entry.options

    def _get_current_level(self):
        """計算當前階梯等級 (1, 2, 3)。"""
        monthly_energy = self._current_month_energy
        now = dt_util.now()
        
        # 獲取配置
        summer_months_str = self._options.get(CONF_SUMMER_MONTHS, DEFAULT_SUMMER_MONTHS)
        try:
            summer_months = [int(x.strip()) for x in summer_months_str.split(",")]
        except ValueError:
            summer_months = [5, 6, 7, 8, 9, 10] # Fallback

        is_summer = now.month in summer_months
        
        if is_summer:
            limit1 = self._options.get(CONF_SUMMER_TIER1, DEFAULT_SUMMER_TIER1)
            limit2 = self._options.get(CONF_SUMMER_TIER2, DEFAULT_SUMMER_TIER2)
        else:
            limit1 = self._options.get(CONF_NON_SUMMER_TIER1, DEFAULT_NON_SUMMER_TIER1)
            limit2 = self._options.get(CONF_NON_SUMMER_TIER2, DEFAULT_NON_SUMMER_TIER2)

        if monthly_energy <= limit1:
            return 1
        elif monthly_energy <= limit2:
            return 2
        else:
            return 3


class PeacefairLevelSensor(PeacefairCalculatedSensor):
    """顯示當前用電階梯等級 (1, 2, 3)。"""

    def __init__(self, coordinator, ident, config_entry, monthly_sensor):
        super().__init__(coordinator, ident, config_entry, monthly_sensor)
        self._attr_name = f"{ident} Electricity Level"
        self._attr_unique_id = f"{DOMAIN}_{ident}_electricity_level"
        self._attr_native_unit_of_measurement = "Level"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:elevation-rise"

    @property
    def native_value(self):
        return self._get_current_level()


class PeacefairPriceSensor(PeacefairCalculatedSensor):
    """顯示當前實時電價 (CNY/kWh)。"""

    def __init__(self, coordinator, ident, config_entry, monthly_sensor):
        super().__init__(coordinator, ident, config_entry, monthly_sensor)
        self._attr_name = f"{ident} Current Price"
        self._attr_unique_id = f"{DOMAIN}_{ident}_current_price"
        self._attr_native_unit_of_measurement = "CNY/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:currency-cny"

    @property
    def native_value(self):
        level = self._get_current_level()
        
        if level == 1:
            return self._options.get(CONF_PRICE_L1, DEFAULT_PRICE_L1)
        elif level == 2:
            return self._options.get(CONF_PRICE_L2, DEFAULT_PRICE_L2)
        else:
            return self._options.get(CONF_PRICE_L3, DEFAULT_PRICE_L3)