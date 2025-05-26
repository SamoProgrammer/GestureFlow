# mouse_controller_module.py
from pynput.mouse import Button, Controller as PynputMouseController
import pyautogui # For screen size, as pynput doesn't provide it directly

class MouseControllerWrapper:
    def __init__(self):
        self.mouse = PynputMouseController()
        try:
            self.screen_width, self.screen_height = pyautogui.size()
        except Exception as e:
            print(f"Warning: Could not get screen dimensions using PyAutoGUI: {e}")
            print("Defaulting screen dimensions to 1920x1080. Mouse control might be inaccurate if this is wrong.")
            self.screen_width, self.screen_height = 1920, 1080


    def move_to(self, x, y):
        """Moves the mouse cursor to the specified (x, y) coordinates."""
        # Ensure coordinates are within screen bounds for pynput
        # pynput usually handles this, but good for robustness
        safe_x = max(0, min(int(x), self.screen_width - 1))
        safe_y = max(0, min(int(y), self.screen_height - 1))
        try:
            self.mouse.position = (safe_x, safe_y)
        except Exception as e:
            # pynput can sometimes have issues on certain OS/setups (e.g., Wayland on Linux)
            print(f"Error moving mouse with pynput: {e}")


    def click(self, button_name="left", count=1):
        """
        Performs a mouse click.
        button_name: "left", "right", "middle"
        count: 1 for single click, 2 for double click
        """
        if button_name == "left":
            pynput_button = Button.left
        elif button_name == "right":
            pynput_button = Button.right
        elif button_name == "middle":
            pynput_button = Button.middle
        else:
            print(f"Warning: Unknown button name '{button_name}'. Defaulting to left click.")
            pynput_button = Button.left
        
        try:
            self.mouse.click(pynput_button, count)
        except Exception as e:
            print(f"Error clicking mouse with pynput: {e}")


    def get_position(self):
        """Returns the current mouse (x, y) position."""
        try:
            return self.mouse.position
        except Exception as e:
            print(f"Error getting mouse position with pynput: {e}")
            # Fallback or raise error
            return (self.screen_width // 2, self.screen_height // 2) 

if __name__ == '__main__':
    # Example Usage
    import time
    mouse_ctl = MouseControllerWrapper()
    
    print(f"Screen Size: {mouse_ctl.screen_width}x{mouse_ctl.screen_height}")
    
    print("Current mouse position:", mouse_ctl.get_position())
    
    target_x, target_y = mouse_ctl.screen_width // 2, mouse_ctl.screen_height // 2
    print(f"Moving mouse to center: ({target_x}, {target_y})")
    mouse_ctl.move_to(target_x, target_y)
    time.sleep(1)
    print("Current mouse position:", mouse_ctl.get_position())

    print("Performing a single left click...")
    mouse_ctl.click("left", 1)
    time.sleep(0.5)

    print("Performing a double left click...")
    mouse_ctl.click("left", 2)
    time.sleep(0.5)

    # Move to a corner
    mouse_ctl.move_to(0,0)
    print("Mouse moved to (0,0)")
