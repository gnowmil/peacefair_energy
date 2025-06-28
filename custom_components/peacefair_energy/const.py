"""Constants for the Peacefair Energy Monitor integration."""

DOMAIN = "peacefair_energy"
VERSION = "0.7.0"  # Note: This is typically defined in manifest.json now.

# --- Local constants for dictionary keys ---
# This is the fix for the ImportError. We define our own constant here.
POWER_FACTOR = "power_factor"

# Default values for configuration
DEFAULT_SCAN_INTERVAL = 15
DEFAULT_SLAVE = 1
DEFAULT_PROTOCOL = "ModbusRTU Over UDP/IP"
DEFAULT_PORT = 9000

# --- Keys for hass.data storage ---
COORDINATOR = "coordinator"
# Corrected typo from "un_subdiscript" to a more descriptive and correct name.
# This change must also be applied in __init__.py where this constant is used.
UNSUBSCRIBE_LISTENER = "unsubscribe_listener"

# --- Protocols mapping ---
PROTOCOLS = {
    "ModbusRTU Over UDP/IP": "rtuoverudp",
    "ModbusRTU Over TCP/IP": "rtuovertcp",
}

# --- Storage path ---
# Note: Modern integrations often use Home Assistant's built-in storage helpers.
STORAGE_PATH = f".storage/{DOMAIN}"


# --- Other constants from the original file ---
# Their usage should be verified across the entire component to see if they are still needed.
DEVICE_CLASS_FREQUENCY = "frequency"
GATHER_TIME = "gather_time"


# --- Deprecated constants from older versions ---
# These are no longer used after refactoring __init__.py and can be safely removed.
# They are commented out here for reference.
#
# ENERGY_SENSOR = "energy_sensor"
# DEVICES = "devices"
