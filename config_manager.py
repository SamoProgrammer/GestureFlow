# config_manager.py
import json
import os

DEFAULT_SETTINGS_FILE = "settings.json"

DEFAULT_CONFIG = {
    "camera_resolution_width": 480,
    "camera_resolution_height": 360,
    "smoothing_factor": 0.20,
    "raw_target_buffer_size": 5,
    "mouse_move_threshold": 1,
    "active_region_x_min_percent": 0.15,
    "active_region_x_max_percent": 0.85,
    "active_region_y_min_percent": 0.15,
    "active_region_y_max_percent": 0.85,
    "pinch_threshold_distance": 25.0, # Ensure this is float for precision
    "double_click_window_sec": 0.4,
    "sensitivity": 1.5,
    "target_fps": 60, # Target processing FPS
    # MediaPipe settings
    "mp_model_complexity": 0,
    "mp_min_detection_confidence": 0.6,
    "mp_min_tracking_confidence": 0.5,
}

class ConfigManager:
    def __init__(self, filepath=DEFAULT_SETTINGS_FILE):
        self.filepath = filepath
        self.config = self.load_config()

    def load_config(self):
        """Loads configuration from the JSON file. Returns default if file not found or invalid."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    loaded_config = json.load(f)
                    # Ensure all default keys are present, add if missing
                    config = DEFAULT_CONFIG.copy()
                    config.update(loaded_config) # loaded_config overrides defaults
                    return config
            except json.JSONDecodeError:
                print(f"Error: Could not decode JSON from {self.filepath}. Using default settings.")
                return DEFAULT_CONFIG.copy()
            except Exception as e:
                print(f"Error loading config file {self.filepath}: {e}. Using default settings.")
                return DEFAULT_CONFIG.copy()
        else:
            print(f"Info: Config file {self.filepath} not found. Using default settings and creating file.")
            # Save default config if file doesn't exist to create it
            self.save_config(DEFAULT_CONFIG.copy()) # Save a copy
            return DEFAULT_CONFIG.copy()

    def save_config(self, config_data=None):
        """Saves the given configuration data (or current self.config) to the JSON file."""
        data_to_save = config_data if config_data is not None else self.config
        try:
            with open(self.filepath, 'w') as f:
                json.dump(data_to_save, f, indent=4)
            print(f"Info: Configuration saved to {self.filepath}")
        except Exception as e:
            print(f"Error: Could not save configuration to {self.filepath}: {e}")

    def get(self, key, default_value=None):
        """Gets a configuration value by key."""
        return self.config.get(key, default_value if default_value is not None else DEFAULT_CONFIG.get(key))

    def set(self, key, value):
        """Sets a configuration value and updates the internal config dictionary."""
        self.config[key] = value
        # Optionally, you could auto-save here, or have an explicit save method call
        # self.save_config() # Uncomment if you want to save on every set

    def get_all_settings(self):
        """Returns the entire configuration dictionary."""
        return self.config.copy()

if __name__ == '__main__':
    # Example Usage
    config_manager = ConfigManager("test_settings.json")
    print("Initial loaded/default config:", config_manager.get_all_settings())

    config_manager.set("sensitivity", 2.0)
    config_manager.set("new_setting", "test_value") # Add a new setting
    config_manager.save_config() # Explicit save

    reloaded_config_manager = ConfigManager("test_settings.json")
    print("Reloaded config:", reloaded_config_manager.get_all_settings())
    print("Sensitivity:", reloaded_config_manager.get("sensitivity"))
    print("New Setting:", reloaded_config_manager.get("new_setting"))

    # Clean up test file
    if os.path.exists("test_settings.json"):
        os.remove("test_settings.json")
