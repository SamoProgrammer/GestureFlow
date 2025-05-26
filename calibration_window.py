# calibration_window.py
import tkinter as tk
from tkinter import ttk, messagebox
import cv2 # For potential video preview in calibration
from PIL import Image, ImageTk # For potential video preview
import numpy as np # For dummy frame in test

# Constants for calibration states (optional, but can make code clearer)
CALIB_STATE_IDLE = 0
CALIB_STATE_WAITING_TOP_LEFT = 1
CALIB_STATE_WAITING_BOTTOM_RIGHT = 2
CALIB_STATE_WAITING_OPEN_HAND = 3
CALIB_STATE_WAITING_PINCH = 4

class CalibrationWindow:
    def __init__(self, tk_parent, config_manager, hand_tracker, video_streamer_ref, main_app_ref):
        self.tk_parent = tk_parent # Renamed from parent for clarity
        self.config_manager = config_manager
        self.hand_tracker = hand_tracker 
        self.video_streamer = video_streamer_ref
        self.main_app_ref = main_app_ref # Reference to the main HandMouseControllerApp instance

        self.top = tk.Toplevel(tk_parent)
        self.top.title("Calibration Settings")
        self.top.resizable(False, False)
        self.top.grab_set() 
        self.top.transient(tk_parent)

        # --- Internal state for calibration ---
        self.calibration_state = CALIB_STATE_IDLE
        self.temp_active_region_tl_norm = None 
        self.temp_active_region_br_norm = None 
        self.temp_open_hand_distances = []
        self.temp_pinch_distances = []
        self.capture_countdown = 0
        # Calculate capture duration based on main app's target FPS for accuracy
        self.ar_capture_duration_s = 2 # Seconds for AR point capture hold
        self.pinch_capture_duration_s = 3 # Seconds for pinch/open state capture
        
        # --- Main UI Setup ---
        self.notebook = ttk.Notebook(self.top)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        self.create_active_region_tab()
        self.create_pinch_threshold_tab()

        self.create_action_buttons()

        self.calib_video_label = None # For the preview in Active Region tab
        self.show_calibration_feed = False 

        self.load_current_config_values()
        self.center_window()
        self.top.protocol("WM_DELETE_WINDOW", self.close_window) # Handle explicit close

    def center_window(self):
        self.top.update_idletasks()
        width = self.top.winfo_reqwidth() # Use reqwidth for initial sizing
        height = self.top.winfo_reqheight()
        x = (self.top.winfo_screenwidth() // 2) - (width // 2)
        y = (self.top.winfo_screenheight() // 2) - (height // 2)
        self.top.geometry(f'{width}x{height}+{x}+{y}')

    def load_current_config_values(self):
        ar_x_min = self.config_manager.get("active_region_x_min_percent", 0.0)
        ar_x_max = self.config_manager.get("active_region_x_max_percent", 1.0)
        ar_y_min = self.config_manager.get("active_region_y_min_percent", 0.0)
        ar_y_max = self.config_manager.get("active_region_y_max_percent", 1.0)
        self.ar_current_label_var.set(f"X: ({ar_x_min:.2f} - {ar_x_max:.2f}), Y: ({ar_y_min:.2f} - {ar_y_max:.2f})")

        pinch_thresh = self.config_manager.get("pinch_threshold_distance", 0.0)
        self.pt_current_threshold_var.set(f"{pinch_thresh:.2f} (pixels on cam frame)")

    def create_active_region_tab(self):
        self.tab_active_region = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab_active_region, text="Active Region")

        ttk.Label(self.tab_active_region, text="Calibrate the hand movement area mapped to the screen.").pack(pady=5)
        
        self.ar_status_var = tk.StringVar(value="Status: Idle")
        ttk.Label(self.tab_active_region, textvariable=self.ar_status_var).pack(pady=5)

        self.ar_current_label_var = tk.StringVar()
        ttk.Label(self.tab_active_region, text="Current Region (Normalized):").pack(pady=(10,0))
        ttk.Label(self.tab_active_region, textvariable=self.ar_current_label_var).pack()

        self.ar_tl_button = ttk.Button(self.tab_active_region, text="1. Capture Top-Left Corner", command=self.start_capture_top_left)
        self.ar_tl_button.pack(pady=5)
        self.ar_tl_var = tk.StringVar(value="Top-Left: Not set")
        ttk.Label(self.tab_active_region, textvariable=self.ar_tl_var).pack()

        self.ar_br_button = ttk.Button(self.tab_active_region, text="2. Capture Bottom-Right Corner", command=self.start_capture_bottom_right, state=tk.DISABLED)
        self.ar_br_button.pack(pady=5)
        self.ar_br_var = tk.StringVar(value="Bottom-Right: Not set")
        ttk.Label(self.tab_active_region, textvariable=self.ar_br_var).pack()
        
        self.ar_video_frame = ttk.LabelFrame(self.tab_active_region, text="Camera Preview", width=330, height=250) # Give some initial size
        self.ar_video_frame.pack(pady=10, padx=10, fill="both", expand=True)
        self.ar_video_frame.pack_propagate(False) # Prevent frame from shrinking to fit label

    def create_pinch_threshold_tab(self):
        self.tab_pinch_threshold = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab_pinch_threshold, text="Pinch Gesture")

        ttk.Label(self.tab_pinch_threshold, text="Calibrate the pinch gesture for clicking.").pack(pady=5)

        self.pt_status_var = tk.StringVar(value="Status: Idle")
        ttk.Label(self.tab_pinch_threshold, textvariable=self.pt_status_var).pack(pady=5)

        self.pt_current_threshold_var = tk.StringVar()
        ttk.Label(self.tab_pinch_threshold, text="Current Threshold:").pack(pady=(10,0))
        ttk.Label(self.tab_pinch_threshold, textvariable=self.pt_current_threshold_var).pack()

        self.pt_open_button = ttk.Button(self.tab_pinch_threshold, text="1. Calibrate 'Open Hand' State", command=self.start_capture_open_hand)
        self.pt_open_button.pack(pady=5)
        self.pt_open_dist_var = tk.StringVar(value="Avg Open Dist: Not set")
        ttk.Label(self.tab_pinch_threshold, textvariable=self.pt_open_dist_var).pack()

        self.pt_pinch_button = ttk.Button(self.tab_pinch_threshold, text="2. Calibrate 'Pinch' State", command=self.start_capture_pinch, state=tk.DISABLED)
        self.pt_pinch_button.pack(pady=5)
        self.pt_pinch_dist_var = tk.StringVar(value="Avg Pinch Dist: Not set")
        ttk.Label(self.tab_pinch_threshold, textvariable=self.pt_pinch_dist_var).pack()

        self.pt_new_threshold_var = tk.StringVar(value="New Threshold: Not calculated")
        ttk.Label(self.tab_pinch_threshold, textvariable=self.pt_new_threshold_var).pack(pady=5)

    def create_action_buttons(self):
        button_frame = ttk.Frame(self.top, padding="10")
        button_frame.pack(fill="x", side="bottom") # Place at bottom

        self.apply_button = ttk.Button(button_frame, text="Apply & Save All", command=self.apply_and_save_settings)
        self.apply_button.pack(side="left", padx=5)

        self.reset_button = ttk.Button(button_frame, text="Reset Calibrations", command=self.reset_calibrations_to_defaults)
        self.reset_button.pack(side="left", padx=5)
        
        self.close_button = ttk.Button(button_frame, text="Close", command=self.close_window)
        self.close_button.pack(side="right", padx=5)

    def start_capture_top_left(self):
        self.ar_status_var.set(f"Status: Move index finger to TOP-LEFT. Hold for {self.ar_capture_duration_s}s or press Enter.")
        self.calibration_state = CALIB_STATE_WAITING_TOP_LEFT
        self.temp_active_region_tl_norm = None 
        self.ar_tl_var.set("Top-Left: Capturing...")
        self.ar_br_button.config(state=tk.DISABLED)
        self.top.bind('<Return>', self.capture_ar_point_on_key)
        self.show_calibration_feed = True 
        self.capture_countdown = int(self.ar_capture_duration_s * self.main_app_ref.target_fps)
        print("Starting top-left capture. Countdown frames:", self.capture_countdown)

    def start_capture_bottom_right(self):
        self.ar_status_var.set(f"Status: Move index finger to BOTTOM-RIGHT. Hold for {self.ar_capture_duration_s}s or press Enter.")
        self.calibration_state = CALIB_STATE_WAITING_BOTTOM_RIGHT
        self.temp_active_region_br_norm = None 
        self.ar_br_var.set("Bottom-Right: Capturing...")
        self.top.bind('<Return>', self.capture_ar_point_on_key)
        self.show_calibration_feed = True
        self.capture_countdown = int(self.ar_capture_duration_s * self.main_app_ref.target_fps)
        print("Starting bottom-right capture. Countdown frames:", self.capture_countdown)

    def capture_ar_point_on_key(self, event=None):
        if self.calibration_state == CALIB_STATE_WAITING_TOP_LEFT or \
           self.calibration_state == CALIB_STATE_WAITING_BOTTOM_RIGHT:
            self.capture_countdown = 1 
            print("Enter pressed, forcing AR point capture.")

    def process_ar_capture(self, norm_x, norm_y):
        if norm_x is None or norm_y is None:
            self.ar_status_var.set("Status: Hand not detected or finger not clear.")
            return

        if self.capture_countdown > 0:
            self.capture_countdown -= 1
            countdown_sec = self.capture_countdown // self.main_app_ref.target_fps + 1 if self.main_app_ref.target_fps > 0 else self.ar_capture_duration_s
            status_suffix = f"(Capturing in {countdown_sec}s...)"
            if self.calibration_state == CALIB_STATE_WAITING_TOP_LEFT:
                 self.ar_status_var.set(f"Status: Hold Top-Left {status_suffix}")
            elif self.calibration_state == CALIB_STATE_WAITING_BOTTOM_RIGHT:
                 self.ar_status_var.set(f"Status: Hold Bottom-Right {status_suffix}")
            return

        if self.calibration_state == CALIB_STATE_WAITING_TOP_LEFT:
            self.temp_active_region_tl_norm = (norm_x, norm_y)
            self.ar_tl_var.set(f"Top-Left: ({norm_x:.3f}, {norm_y:.3f})")
            self.ar_status_var.set("Status: Top-Left captured! Now set Bottom-Right.")
            self.ar_br_button.config(state=tk.NORMAL)
            self.calibration_state = CALIB_STATE_IDLE
            self.top.unbind('<Return>')
            print(f"Captured Top-Left: {self.temp_active_region_tl_norm}")
        elif self.calibration_state == CALIB_STATE_WAITING_BOTTOM_RIGHT:
            self.temp_active_region_br_norm = (norm_x, norm_y)
            self.ar_br_var.set(f"Bottom-Right: ({norm_x:.3f}, {norm_y:.3f})")
            self.ar_status_var.set("Status: Bottom-Right captured! Region defined.")
            self.calibration_state = CALIB_STATE_IDLE
            self.top.unbind('<Return>')
            print(f"Captured Bottom-Right: {self.temp_active_region_br_norm}")
        
        # self.show_calibration_feed = False # Keep feed if user wants to see result? Or stop? For now, let main loop decide.

    def start_capture_open_hand(self):
        self.pt_status_var.set(f"Status: Hold hand OPEN. Capturing for {self.pinch_capture_duration_s}s...")
        self.calibration_state = CALIB_STATE_WAITING_OPEN_HAND
        self.temp_open_hand_distances = []
        self.capture_countdown = int(self.pinch_capture_duration_s * self.main_app_ref.target_fps)
        self.pt_pinch_button.config(state=tk.DISABLED)
        self.show_calibration_feed = True
        print("Starting open hand capture. Countdown frames:", self.capture_countdown)

    def start_capture_pinch(self):
        self.pt_status_var.set(f"Status: Hold hand PINCHED. Capturing for {self.pinch_capture_duration_s}s...")
        self.calibration_state = CALIB_STATE_WAITING_PINCH
        self.temp_pinch_distances = []
        self.capture_countdown = int(self.pinch_capture_duration_s * self.main_app_ref.target_fps)
        self.show_calibration_feed = True
        print("Starting pinch capture. Countdown frames:", self.capture_countdown)

    def process_pinch_capture(self, pinch_distance_pixels):
        if pinch_distance_pixels is None or pinch_distance_pixels == float('inf'):
            self.pt_status_var.set("Status: Hand/fingers not clear for pinch.")
            return

        if self.capture_countdown > 0:
            self.capture_countdown -= 1
            countdown_sec = self.capture_countdown // self.main_app_ref.target_fps + 1 if self.main_app_ref.target_fps > 0 else self.pinch_capture_duration_s
            status_suffix = f"(Capturing in {countdown_sec}s... Dist: {pinch_distance_pixels:.1f})"
            if self.calibration_state == CALIB_STATE_WAITING_OPEN_HAND:
                self.pt_status_var.set(f"Status: Hold Open Hand {status_suffix}")
                self.temp_open_hand_distances.append(pinch_distance_pixels)
            elif self.calibration_state == CALIB_STATE_WAITING_PINCH:
                self.pt_status_var.set(f"Status: Hold Pinch {status_suffix}")
                self.temp_pinch_distances.append(pinch_distance_pixels)
            return

        if self.calibration_state == CALIB_STATE_WAITING_OPEN_HAND:
            if self.temp_open_hand_distances:
                avg_open_dist = sum(self.temp_open_hand_distances) / len(self.temp_open_hand_distances)
                self.pt_open_dist_var.set(f"Avg Open Dist: {avg_open_dist:.2f}")
                self.pt_status_var.set("Status: Open Hand captured. Now calibrate Pinch.")
                self.pt_pinch_button.config(state=tk.NORMAL)
                print(f"Captured Open Hand Avg Dist: {avg_open_dist}")
            else:
                self.pt_status_var.set("Status: Failed to capture Open Hand samples.")
            self.calibration_state = CALIB_STATE_IDLE
        elif self.calibration_state == CALIB_STATE_WAITING_PINCH:
            if self.temp_pinch_distances:
                avg_pinch_dist = sum(self.temp_pinch_distances) / len(self.temp_pinch_distances)
                self.pt_pinch_dist_var.set(f"Avg Pinch Dist: {avg_pinch_dist:.2f}")
                self.pt_status_var.set("Status: Pinch captured. Threshold calculated.")
                print(f"Captured Pinch Avg Dist: {avg_pinch_dist}")
                self.calculate_and_display_new_pinch_threshold()
            else:
                self.pt_status_var.set("Status: Failed to capture Pinch samples.")
            self.calibration_state = CALIB_STATE_IDLE
        
        # self.show_calibration_feed = False # Let main loop control based on state

    def calculate_and_display_new_pinch_threshold(self):
        try:
            avg_open_str = self.pt_open_dist_var.get()
            avg_pinch_str = self.pt_pinch_dist_var.get()
            if "Avg Open Dist: " not in avg_open_str or "Avg Pinch Dist: " not in avg_pinch_str:
                 raise ValueError("Average distances not set.")

            avg_open = float(avg_open_str.split(":")[1].strip())
            avg_pinch = float(avg_pinch_str.split(":")[1].strip())

            if avg_open > avg_pinch + 1.0: # Ensure open is meaningfully larger than pinch
                new_threshold = avg_pinch + (avg_open - avg_pinch) * 0.35 # Heuristic: 35% from pinch towards open
                new_threshold = max(5.0, new_threshold) # Ensure a minimum threshold
                self.pt_new_threshold_var.set(f"New Threshold: {new_threshold:.2f}")
                print(f"Calculated new pinch threshold: {new_threshold}")
            else:
                self.pt_new_threshold_var.set("New Threshold: Error (Open <= Pinch or too close)")
        except Exception as e:
            self.pt_new_threshold_var.set("New Threshold: Error calculating")
            print(f"Exception calculating pinch threshold: {e}")

    def apply_and_save_settings(self):
        applied_changes = False
        if self.temp_active_region_tl_norm and self.temp_active_region_br_norm:
            x_min = min(self.temp_active_region_tl_norm[0], self.temp_active_region_br_norm[0])
            x_max = max(self.temp_active_region_tl_norm[0], self.temp_active_region_br_norm[0])
            y_min = min(self.temp_active_region_tl_norm[1], self.temp_active_region_br_norm[1])
            y_max = max(self.temp_active_region_tl_norm[1], self.temp_active_region_br_norm[1])
            if x_max > x_min + 0.01 and y_max > y_min + 0.01: 
                self.config_manager.set("active_region_x_min_percent", round(x_min, 3))
                self.config_manager.set("active_region_x_max_percent", round(x_max, 3))
                self.config_manager.set("active_region_y_min_percent", round(y_min, 3))
                self.config_manager.set("active_region_y_max_percent", round(y_max, 3))
                applied_changes = True
            else: messagebox.showerror("Error", "Invalid active region. Re-calibrate.", parent=self.top)
        try:
            new_thresh_str = self.pt_new_threshold_var.get()
            if "New Threshold: " in new_thresh_str and "Error" not in new_thresh_str:
                new_threshold_val = float(new_thresh_str.split(":")[1].strip())
                self.config_manager.set("pinch_threshold_distance", round(new_threshold_val, 2))
                applied_changes = True
        except ValueError: print("Could not parse new pinch threshold for saving.")
        if applied_changes:
            self.config_manager.save_config()
            self.main_app_ref.load_settings_from_config() 
            self.load_current_config_values() 
            messagebox.showinfo("Calibration", "Settings applied and saved!", parent=self.top)
        else: messagebox.showinfo("Calibration", "No new calibrations to apply.", parent=self.top)

    def reset_calibrations_to_defaults(self):
        if messagebox.askokcancel("Confirm Reset", "Reset all calibrations to default values?", parent=self.top):
            for key in ["active_region_x_min_percent", "active_region_x_max_percent", 
                        "active_region_y_min_percent", "active_region_y_max_percent", 
                        "pinch_threshold_distance"]:
                self.config_manager.set(key, self.config_manager.DEFAULT_CONFIG[key])
            self.config_manager.save_config()
            self.main_app_ref.load_settings_from_config()
            self.load_current_config_values()
            self.temp_active_region_tl_norm = None; self.temp_active_region_br_norm = None
            self.ar_tl_var.set("Top-Left: Not set"); self.ar_br_var.set("Bottom-Right: Not set")
            self.ar_br_button.config(state=tk.DISABLED)
            self.pt_open_dist_var.set("Avg Open Dist: Not set"); self.pt_pinch_dist_var.set("Avg Pinch Dist: Not set")
            self.pt_new_threshold_var.set("New Threshold: Not calculated")
            self.pt_pinch_button.config(state=tk.DISABLED)
            messagebox.showinfo("Calibration", "Calibrations reset to defaults and saved.", parent=self.top)

    def close_window(self):
        self.show_calibration_feed = False 
        self.calibration_state = CALIB_STATE_IDLE # Reset state on close
        self.top.unbind('<Return>') # Ensure key binding is removed
        self.top.grab_release()
        self.top.destroy()
        if self.main_app_ref: # Notify main app that window is closed
            self.main_app_ref.calibration_window_instance = None
            self.main_app_ref.status_var.set(f"Status: {'Running...' if self.main_app_ref.is_control_active else 'Idle'}")


    def update_calibration_step(self, frame_for_preview=None):
        if not self.top.winfo_exists(): return

        if self.show_calibration_feed and frame_for_preview is not None:
            # frame_for_preview is expected to be BGR, already flipped by main_app
            frame_rgb = cv2.cvtColor(frame_for_preview, cv2.COLOR_BGR2RGB)
            frame_height, frame_width, _ = frame_rgb.shape
            
            self.hand_tracker.process_frame(frame_rgb) 
            hand_landmarks = self.hand_tracker.get_landmarks()

            if self.calibration_state == CALIB_STATE_WAITING_TOP_LEFT or \
               self.calibration_state == CALIB_STATE_WAITING_BOTTOM_RIGHT:
                pix_x, pix_y = self.hand_tracker.get_finger_tip_coordinates(
                    frame_width, frame_height, self.hand_tracker.INDEX_FINGER_TIP)
                if pix_x is not None:
                    norm_x, norm_y = pix_x / frame_width, pix_y / frame_height
                    self.process_ar_capture(norm_x, norm_y)
                else: self.process_ar_capture(None, None) 
            elif self.calibration_state == CALIB_STATE_WAITING_OPEN_HAND or \
                 self.calibration_state == CALIB_STATE_WAITING_PINCH:
                _, _, _, _, pinch_dist_pixels = self.hand_tracker.get_pinch_info(frame_width, frame_height)
                self.process_pinch_capture(pinch_dist_pixels if pinch_dist_pixels != float('inf') else None)
            
            # --- Display preview with landmarks ---
            preview_frame = frame_for_preview.copy() # Draw on a copy
            if hand_landmarks:
                self.hand_tracker.draw_landmarks_on_frame(preview_frame, hand_landmarks)
            if self.temp_active_region_tl_norm:
                tl_x = int(self.temp_active_region_tl_norm[0] * frame_width)
                tl_y = int(self.temp_active_region_tl_norm[1] * frame_height)
                cv2.circle(preview_frame, (tl_x, tl_y), 7, (0,255,255), -1) 
                if self.temp_active_region_br_norm: 
                     br_x = int(self.temp_active_region_br_norm[0] * frame_width)
                     br_y = int(self.temp_active_region_br_norm[1] * frame_height)
                     cv2.rectangle(preview_frame, (tl_x, tl_y), (br_x, br_y), (255,255,0), 2)

            if self.calib_video_label is None and self.ar_video_frame.winfo_exists():
                self.calib_video_label = ttk.Label(self.ar_video_frame)
                self.calib_video_label.pack(fill="both", expand=True, padx=5, pady=5)

            if self.calib_video_label and self.calib_video_label.winfo_exists():
                preview_width = self.ar_video_frame.winfo_width() - 10 # Account for padding
                preview_height = self.ar_video_frame.winfo_height() - 10
                if preview_width < 50 or preview_height < 50 : # Min size
                    preview_width, preview_height = 320,240


                # Resize frame for preview, maintaining aspect ratio
                frame_aspect_ratio = frame_width / frame_height
                label_aspect_ratio = preview_width / preview_height

                if frame_aspect_ratio > label_aspect_ratio: # Frame is wider than label area
                    new_w = preview_width
                    new_h = int(new_w / frame_aspect_ratio)
                else: # Frame is taller or same aspect
                    new_h = preview_height
                    new_w = int(new_h * frame_aspect_ratio)
                
                resized_frame = cv2.resize(preview_frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
                
                img_pil = Image.fromarray(cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB))
                img_tk = ImageTk.PhotoImage(image=img_pil)
                self.calib_video_label.imgtk = img_tk
                self.calib_video_label.configure(image=img_tk)
        elif self.calib_video_label and self.calib_video_label.winfo_exists(): # Clear preview if not showing feed
            self.calib_video_label.configure(image='')
            self.calib_video_label.imgtk = None


if __name__ == '__main__':
    from config_manager import ConfigManager 
    class MockHandTracker:
        INDEX_FINGER_TIP = 8; THUMB_TIP = 4
        def get_landmarks(self): return None
        def get_finger_tip_coordinates(self,fw,fh,fid): return (fw//2,fh//2) if fid==self.INDEX_FINGER_TIP else (None,None)
        def get_pinch_info(self,fw,fh): return (fw//2,fh//2,fw//2+10,fh//2+10,10.0)
        def process_frame(self,fr): pass
        def draw_landmarks_on_frame(self,fr,hl): pass
    class MockVideoStreamer:
        def __init__(self): self.actual_width=320; self.actual_height=240; self.stopped = False
        def read(self): return np.zeros((self.actual_height,self.actual_width,3),dtype=np.uint8)
        def isOpened(self): return True
        def stop(self): self.stopped = True
    class MockMainApp:
        def __init__(self): self.target_fps=30; self.is_control_active=False; self.status_var=tk.StringVar()
        def load_settings_from_config(self): pass
    root=tk.Tk(); root.title("Main App (Mock)")
    mock_config=ConfigManager("mock_calib_settings.json"); mock_tracker=MockHandTracker()
    mock_streamer=MockVideoStreamer(); mock_main_app_ref=MockMainApp()
    def open_calib():
        calib_win = CalibrationWindow(root,mock_config,mock_tracker,mock_streamer,mock_main_app_ref)
    ttk.Button(root,text="Open Calibration",command=open_calib).pack(padx=20,pady=20)
    root.mainloop()
    import os
    if os.path.exists("mock_calib_settings.json"): os.remove("mock_calib_settings.json")
