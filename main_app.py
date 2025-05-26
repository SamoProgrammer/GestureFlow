# main_app.py
# Version 0.4.1: Integrated CalibrationWindow

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import numpy as np
import time
import math 
import collections 
import cv2 # Ensure cv2 is imported for main_app operations

# Import custom modules
from config_manager import ConfigManager
from video_streamer import WebcamVideoStream
from hand_tracking_module import HandTracker
from mouse_controller_module import MouseControllerWrapper
from calibration_window import CalibrationWindow, CALIB_STATE_IDLE # Import class and state


class HandMouseControllerApp:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("Hand Gesture Mouse Control v0.4.1 (Calibration Ready)")

        # --- Initialize Modules ---
        self.config_manager = ConfigManager()
        self.mouse_controller = MouseControllerWrapper()
        
        self.load_settings_from_config() # Load initial settings

        self.hand_tracker = HandTracker(
            model_complexity=self.config_manager.get("mp_model_complexity"),
            min_detection_confidence=self.config_manager.get("mp_min_detection_confidence"),
            min_tracking_confidence=self.config_manager.get("mp_min_tracking_confidence")
        )
        self.video_stream = None
        self.calibration_window_instance = None # To hold the calibration window

        # --- Smoothing & Movement State ---
        self.prev_cursor_x, self.prev_cursor_y = self.mouse_controller.get_position()
        self.last_mouse_move_x, self.last_mouse_move_y = self.prev_cursor_x, self.prev_cursor_y
        
        self.raw_target_history_x = collections.deque(maxlen=self.config_manager.get("raw_target_buffer_size"))
        self.raw_target_history_y = collections.deque(maxlen=self.config_manager.get("raw_target_buffer_size"))

        # --- Click Detection State ---
        self.is_pinching_prev_frame = False
        self.last_click_event_time = 0

        # --- GUI Elements ---
        self.setup_gui()

        # --- Application State ---
        self.is_control_active = False
        self.root.protocol("WM_DELETE_WINDOW", self.on_app_close)
        
        print(f"Screen dimensions: {self.mouse_controller.screen_width}x{self.mouse_controller.screen_height}")
        print(f"Initial settings loaded. Target FPS: {self.target_fps}")

    def load_settings_from_config(self):
        """Loads all relevant settings from the config manager into instance variables."""
        self.cam_requested_width = self.config_manager.get("camera_resolution_width")
        self.cam_requested_height = self.config_manager.get("camera_resolution_height")
        self.cam_actual_width = self.cam_requested_width 
        self.cam_actual_height = self.cam_requested_height

        self.target_fps = self.config_manager.get("target_fps")
        self.frame_process_delay_ms = int(1000 / self.target_fps) if self.target_fps > 0 else 33

        self.smoothing_factor = self.config_manager.get("smoothing_factor")
        # Re-initialize deque if buffer size changed and deque exists
        new_buffer_size = self.config_manager.get("raw_target_buffer_size")
        if hasattr(self, 'raw_target_history_x') and self.raw_target_history_x.maxlen != new_buffer_size:
            self.raw_target_history_x = collections.deque(maxlen=new_buffer_size)
            self.raw_target_history_y = collections.deque(maxlen=new_buffer_size)
        
        self.mouse_move_threshold = self.config_manager.get("mouse_move_threshold")
        
        self.active_region_x_min_percent = self.config_manager.get("active_region_x_min_percent")
        self.active_region_x_max_percent = self.config_manager.get("active_region_x_max_percent")
        self.active_region_y_min_percent = self.config_manager.get("active_region_y_min_percent")
        self.active_region_y_max_percent = self.config_manager.get("active_region_y_max_percent")
        
        self.pinch_threshold_distance_config = self.config_manager.get("pinch_threshold_distance")
        self.double_click_window_sec = self.config_manager.get("double_click_window_sec")
        self.sensitivity_value = self.config_manager.get("sensitivity")
        if hasattr(self, 'sensitivity_scale_var'): # Update GUI if it exists
            self.sensitivity_scale_var.set(self.sensitivity_value)
        print("Settings reloaded from config.")


    def setup_gui(self):
        """Creates and lays out the Tkinter GUI elements."""
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.video_label = ttk.Label(self.main_frame)
        self.video_label.grid(row=0, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)

        self.controls_frame = ttk.Frame(self.main_frame, padding="5")
        self.controls_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E))

        self.start_stop_button = ttk.Button(self.controls_frame, text="Start Control", command=self.toggle_control_state)
        self.start_stop_button.grid(row=0, column=0, padx=5, pady=5)

        ttk.Label(self.controls_frame, text="Sensitivity:").grid(row=0, column=1, padx=(10,0), pady=5)
        self.sensitivity_scale_var = tk.DoubleVar(value=self.sensitivity_value)
        self.sensitivity_scale = ttk.Scale(
            self.controls_frame, from_=0.5, to=3.0, orient=tk.HORIZONTAL, length=150,
            variable=self.sensitivity_scale_var, command=self.on_sensitivity_changed
        )
        self.sensitivity_scale.grid(row=0, column=2, padx=5, pady=5)

        self.status_var = tk.StringVar(value="Status: Idle")
        self.status_label = ttk.Label(self.controls_frame, textvariable=self.status_var, anchor=tk.W)
        self.status_label.grid(row=0, column=3, padx=10, pady=5, sticky=(tk.W, tk.E))
        self.controls_frame.columnconfigure(3, weight=1)

        self.calibrate_button = ttk.Button(self.controls_frame, text="Calibrate", command=self.open_calibration_window)
        self.calibrate_button.grid(row=0, column=4, padx=10, pady=5)

        self.profiling_frame = ttk.LabelFrame(self.main_frame, text="Profiling (ms)", padding="5")
        self.profiling_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        self.profile_data_vars = {
            "Total": tk.DoubleVar(value=0.0), "Read": tk.DoubleVar(value=0.0),
            "PreProc": tk.DoubleVar(value=0.0), "MediaPipe": tk.DoubleVar(value=0.0),
            "ActiveRegion": tk.DoubleVar(value=0.0), "HandLogic": tk.DoubleVar(value=0.0),
            "MouseCtl": tk.DoubleVar(value=0.0), "DrawOps": tk.DoubleVar(value=0.0),
            "GUIUpdate": tk.DoubleVar(value=0.0)
        }
        row_idx, col_idx = 0, 0
        for name, var in self.profile_data_vars.items():
            ttk.Label(self.profiling_frame, text=f"{name}:").grid(row=row_idx, column=col_idx, padx=2, sticky=tk.W)
            ttk.Label(self.profiling_frame, textvariable=var).grid(row=row_idx, column=col_idx+1, padx=(0,10), sticky=tk.W)
            col_idx += 2
            if col_idx >= 6: col_idx = 0; row_idx += 1

    def on_sensitivity_changed(self, value_str):
        self.sensitivity_value = float(value_str)
        self.config_manager.set("sensitivity", self.sensitivity_value)
        # Config will be saved on app close or after calibration save.

    def open_calibration_window(self):
        if self.calibration_window_instance and self.calibration_window_instance.top.winfo_exists():
            self.calibration_window_instance.top.lift() # Bring to front if already open
            return

        if not self.video_stream or not self.video_stream.stream: # Ensure video stream is active
            self.status_var.set("Status: Start video control before calibrating.")
            print("Warning: Video control must be active to open calibration window with live feed.")
            # Optionally, allow calibration without live feed, but it's less useful.
            # For now, require video stream.
            # One could also temporarily start the video stream just for calibration.
            if not self.is_control_active: # If control is not active, try to start it for calibration
                print("Attempting to start video stream for calibration...")
                self.start_hand_control() # This will start the process_video_frame loop
                if not self.is_control_active: # If start failed
                    self.status_var.set("Status: Failed to start video for calibration.")
                    return
            # If control was already active, video_stream should be fine.


        self.calibration_window_instance = CalibrationWindow(
            self.root, # Tkinter parent for the Toplevel window
            self.config_manager,
            self.hand_tracker,
            self.video_stream, # Pass the active video_stream instance
            self # Pass this HandMouseControllerApp instance as main_app_ref
        )
        self.status_var.set("Status: Calibration Window Open")
        # We don't use wait_window here, so the main loop continues.
        # The calibration window uses grab_set() to be modal.
        # We need a way to know when it's closed to reset self.calibration_window_instance
        # The CalibrationWindow's close_window method should ideally notify the parent or
        # main_app can check if top.winfo_exists() in its loop.
        # For now, main_app will check winfo_exists.

    def toggle_control_state(self):
        if self.is_control_active:
            self.stop_hand_control()
        else:
            self.start_hand_control()

    def start_hand_control(self):
        try:
            # Ensure video_stream is only created if it doesn't exist or is stopped
            if self.video_stream is None or self.video_stream.stopped:
                self.video_stream = WebcamVideoStream(
                    src=0, 
                    width=self.cam_requested_width, 
                    height=self.cam_requested_height
                ).start()
            elif not self.video_stream.thread or not self.video_stream.thread.is_alive():
                # Stream object exists but thread is dead, try to restart
                self.video_stream.start()


            self.cam_actual_width = self.video_stream.actual_width
            self.cam_actual_height = self.video_stream.actual_height
            if self.cam_actual_width == 0 or self.cam_actual_height == 0:
                 raise ValueError("Webcam stream started with invalid dimensions.")
            print(f"Control started. Actual cam res: {self.cam_actual_width}x{self.cam_actual_height}")
        except Exception as e: # Catch broader exceptions during stream start
            self.status_var.set(f"Status: Error - {e}")
            print(f"Error starting webcam: {e}")
            if self.video_stream: self.video_stream.stop()
            self.video_stream = None
            self.is_control_active = False # Ensure control is not active
            self.start_stop_button.config(text="Start Control")
            return

        self.is_control_active = True
        self.start_stop_button.config(text="Stop Control")
        self.status_var.set("Status: Running...")
        
        try:
            self.prev_cursor_x, self.prev_cursor_y = self.mouse_controller.get_position()
            self.last_mouse_move_x, self.last_mouse_move_y = self.prev_cursor_x, self.prev_cursor_y
        except Exception as e:
            print(f"Warning: Could not get initial mouse position: {e}")
            self.prev_cursor_x, self.prev_cursor_y = self.mouse_controller.screen_width//2, self.mouse_controller.screen_height//2
            self.last_mouse_move_x, self.last_mouse_move_y = self.prev_cursor_x, self.prev_cursor_y

        self.raw_target_history_x.clear()
        self.raw_target_history_y.clear()
        
        # Start the processing loop if not already running due to recursion
        # This check helps prevent multiple loops if start_hand_control is called again
        # while a loop is technically scheduled with root.after
        if not hasattr(self, '_processing_loop_active') or not self._processing_loop_active:
            self._processing_loop_active = True
            self.process_video_frame()


    def stop_hand_control(self):
        self.is_control_active = False 
        # Video stream is stopped by on_app_close or if explicitly needed elsewhere.
        # If calibration window is open, we might want to keep video stream alive.
        # For now, stopping control implies stopping the main mouse interaction.
        self.start_stop_button.config(text="Start Control")
        if not (self.calibration_window_instance and self.calibration_window_instance.top.winfo_exists()):
            self.status_var.set("Status: Stopped.") # Only set to stopped if calib isn't open
            if self.video_stream: # Stop video if not needed for calib
                self.video_stream.stop()
                self.video_stream = None

        print("Hand control logic stopped.")
        for var in self.profile_data_vars.values(): var.set(0.0)
        self._processing_loop_active = False


    def process_video_frame(self):
        # If control is stopped, but calibration window wants to run, this loop needs to be handled.
        # For now, this loop only runs if self.is_control_active OR if calibration window is active.
        
        # Check if calibration window exists and is active
        calib_active_and_wants_feed = False
        if self.calibration_window_instance and self.calibration_window_instance.top.winfo_exists():
            if self.calibration_window_instance.calibration_state != CALIB_STATE_IDLE or \
               self.calibration_window_instance.show_calibration_feed: # Also show feed if just open
                calib_active_and_wants_feed = True
            if not self.calibration_window_instance.top.winfo_exists(): # Double check if closed
                self.calibration_window_instance = None 
                calib_active_and_wants_feed = False


        if not self.is_control_active and not calib_active_and_wants_feed:
            self._processing_loop_active = False
            # If calibration window was just closed, reload settings
            if self.calibration_window_instance is None and hasattr(self, '_calib_was_open') and self._calib_was_open:
                print("Calibration window seems closed, reloading settings.")
                self.load_settings_from_config()
                self._calib_was_open = False

            return
        
        if self.video_stream is None or self.video_stream.stopped:
            # Try to restart stream if it's needed for calibration and got stopped
            if calib_active_and_wants_feed and (self.video_stream is None or self.video_stream.stopped):
                print("Video stream stopped but calibration needs it. Attempting restart...")
                try:
                    self.video_stream = WebcamVideoStream(src=0, width=self.cam_requested_width, height=self.cam_requested_height).start()
                    self.cam_actual_width = self.video_stream.actual_width
                    self.cam_actual_height = self.video_stream.actual_height
                except Exception as e:
                    print(f"Failed to restart video stream for calibration: {e}")
                    self.status_var.set("Status: Video Error for Calib.")
                    if self.calibration_window_instance: self.calibration_window_instance.show_calibration_feed = False # Stop trying
                    self.root.after(self.frame_process_delay_ms, self.process_video_frame)
                    return
            else: # Not active and no calibration, so just return
                 self._processing_loop_active = False
                 return


        ts_total_start = time.perf_counter()
        ts_read_start = time.perf_counter()
        frame = self.video_stream.read()
        ts_read_end = time.perf_counter()
        self.profile_data_vars["Read"].set(round((ts_read_end - ts_read_start) * 1000, 2))

        if frame is None:
            self.root.after(5, self.process_video_frame) 
            return
        
        self._calib_was_open = bool(self.calibration_window_instance and self.calibration_window_instance.top.winfo_exists())


        frame_overall_processing_start_time = time.perf_counter()
        frame_copy_for_calib = frame.copy() # Make a copy for calibration window to use/modify

        # --- Pre-processing for main app ---
        ts_preproc_start = time.perf_counter()
        processed_frame_main = cv2.flip(frame, 1) 
        frame_rgb_main = cv2.cvtColor(processed_frame_main, cv2.COLOR_BGR2RGB) 
        frame_height, frame_width, _ = processed_frame_main.shape 
        ts_preproc_end = time.perf_counter()
        self.profile_data_vars["PreProc"].set(round((ts_preproc_end - ts_preproc_start) * 1000, 2))

        # --- MediaPipe Processing (on main app's RGB frame) ---
        ts_mp_start = time.perf_counter()
        self.hand_tracker.process_frame(frame_rgb_main) 
        ts_mp_end = time.perf_counter()
        self.profile_data_vars["MediaPipe"].set(round((ts_mp_end - ts_mp_start) * 1000, 2))
        
        hand_landmarks = self.hand_tracker.get_landmarks() 

        # --- Call Calibration Update if Active ---
        if calib_active_and_wants_feed:
            # Calibration window uses its own hand_tracker instance on the frame_copy_for_calib
            # or it uses the main hand_tracker results.
            # The current CalibrationWindow.update_calibration_step re-processes.
            # Let's pass the BGR frame_copy_for_calib.
            # It also needs its own HandTracker to process this frame_copy_for_calib's RGB version.
            # The current calib_window takes self.hand_tracker (main one).
            # This means calib_window.update_calibration_step will use results from frame_rgb_main.
            # This is fine if it just needs landmark data.
            # For drawing on its own preview, it should use frame_copy_for_calib.
            self.calibration_window_instance.update_calibration_step(cv2.flip(frame_copy_for_calib,1)) # Pass flipped BGR

        # --- Main App Logic (only if self.is_control_active) ---
        if self.is_control_active:
            ts_activeregion_start = time.perf_counter()
            current_sensitivity = self.sensitivity_scale_var.get() 
            center_x_cam_percent = (self.active_region_x_min_percent + self.active_region_x_max_percent) / 2
            center_y_cam_percent = (self.active_region_y_min_percent + self.active_region_y_max_percent) / 2
            base_active_width_percent = self.active_region_x_max_percent - self.active_region_x_min_percent
            base_active_height_percent = self.active_region_y_max_percent - self.active_region_y_min_percent
            effective_active_width_percent = base_active_width_percent / current_sensitivity
            effective_active_height_percent = base_active_height_percent / current_sensitivity
            current_active_x_min_p = np.clip(center_x_cam_percent - effective_active_width_percent / 2, 0.0, 1.0)
            current_active_x_max_p = np.clip(center_x_cam_percent + effective_active_width_percent / 2, 0.0, 1.0)
            current_active_y_min_p = np.clip(center_y_cam_percent - effective_active_height_percent / 2, 0.0, 1.0)
            current_active_y_max_p = np.clip(center_y_cam_percent + effective_active_height_percent / 2, 0.0, 1.0)
            if current_active_x_min_p >= current_active_x_max_p: current_active_x_max_p = current_active_x_min_p + 0.01
            if current_active_y_min_p >= current_active_y_max_p: current_active_y_max_p = current_active_y_min_p + 0.01
            ax1 = int(current_active_x_min_p * frame_width)
            ay1 = int(current_active_y_min_p * frame_height)
            ax2 = int(current_active_x_max_p * frame_width)
            ay2 = int(current_active_y_max_p * frame_height)
            ts_activeregion_end = time.perf_counter()
            self.profile_data_vars["ActiveRegion"].set(round((ts_activeregion_end - ts_activeregion_start) * 1000, 2))

            ts_handlogic_start = time.perf_counter()
            mouse_moved_by_logic = False
            ix_cam_draw, iy_cam_draw, tx_cam_draw, ty_cam_draw, pinch_dist_draw = None, None, None, None, None
            if hand_landmarks:
                ix_cam_logic, iy_cam_logic = self.hand_tracker.get_finger_tip_coordinates(
                    frame_width, frame_height, self.hand_tracker.INDEX_FINGER_TIP)
                ix_cam_draw, iy_cam_draw = ix_cam_logic, iy_cam_logic
                if ix_cam_logic is not None:
                    clamped_ix_cam = np.clip(ix_cam_logic, ax1, ax2)
                    clamped_iy_cam = np.clip(iy_cam_logic, ay1, ay2)
                    raw_target_screen_x = np.interp(clamped_ix_cam, (ax1, ax2), (0, self.mouse_controller.screen_width))
                    raw_target_screen_y = np.interp(clamped_iy_cam, (ay1, ay2), (0, self.mouse_controller.screen_height))
                    self.raw_target_history_x.append(raw_target_screen_x)
                    self.raw_target_history_y.append(raw_target_screen_y)
                    if self.raw_target_history_x:
                         avg_target_x = sum(self.raw_target_history_x) / len(self.raw_target_history_x)
                         avg_target_y = sum(self.raw_target_history_y) / len(self.raw_target_history_y)
                    else: avg_target_x, avg_target_y = raw_target_screen_x, raw_target_screen_y
                    current_cursor_x = self.prev_cursor_x * (1 - self.smoothing_factor) + avg_target_x * self.smoothing_factor
                    current_cursor_y = self.prev_cursor_y * (1 - self.smoothing_factor) + avg_target_y * self.smoothing_factor
                    self.prev_cursor_x, self.prev_cursor_y = current_cursor_x, current_cursor_y
                    mouse_moved_by_logic = True
                _, _, tx_cam_logic, ty_cam_logic, pinch_distance_logic = self.hand_tracker.get_pinch_info(frame_width, frame_height)
                tx_cam_draw, ty_cam_draw, pinch_dist_draw = tx_cam_logic, ty_cam_logic, pinch_distance_logic
                if pinch_distance_logic < self.pinch_threshold_distance_config: is_pinching_this_frame = True
                else: is_pinching_this_frame = False
                if is_pinching_this_frame and not self.is_pinching_prev_frame:
                    ctime = time.perf_counter()
                    if (ctime - self.last_click_event_time) < self.double_click_window_sec:
                        self.mouse_controller.click(count=2) 
                        self.status_var.set("Status: Double Click!")
                        self.last_click_event_time = 0 
                    else:
                        self.mouse_controller.click(count=1) 
                        self.status_var.set("Status: Click!")
                    self.last_click_event_time = ctime
                self.is_pinching_prev_frame = is_pinching_this_frame
                if not is_pinching_this_frame and not self.status_var.get().startswith("Status: Error"):
                    if self.is_control_active: self.status_var.set("Status: Running...")
            else: 
                if self.is_control_active: self.status_var.set("Status: No Hand Detected")
                self.is_pinching_prev_frame = False
                self.raw_target_history_x.clear(); self.raw_target_history_y.clear()
            ts_handlogic_end = time.perf_counter()
            self.profile_data_vars["HandLogic"].set(round((ts_handlogic_end - ts_handlogic_start) * 1000, 2))

            ts_mousectl_start = time.perf_counter()
            if mouse_moved_by_logic: 
                final_x = int(self.prev_cursor_x); final_y = int(self.prev_cursor_y)
                if abs(final_x - self.last_mouse_move_x) > self.mouse_move_threshold or \
                   abs(final_y - self.last_mouse_move_y) > self.mouse_move_threshold:
                    self.mouse_controller.move_to(final_x, final_y) 
                    self.last_mouse_move_x, self.last_mouse_move_y = final_x, final_y
            ts_mousectl_end = time.perf_counter()
            self.profile_data_vars["MouseCtl"].set(round((ts_mousectl_end - ts_mousectl_start) * 1000, 2))

            # --- Drawing Operations on main app's processed_frame_main ---
            ts_draw_start = time.perf_counter()
            cv2.rectangle(processed_frame_main, (ax1, ay1), (ax2, ay2), (0, 255, 0), 2)
            if hand_landmarks:
                self.hand_tracker.draw_landmarks_on_frame(processed_frame_main, hand_landmarks)
                if ix_cam_draw is not None: cv2.circle(processed_frame_main, (int(ix_cam_draw), int(iy_cam_draw)), 7, (255,0,0),-1)
                if tx_cam_draw is not None: 
                    cv2.circle(processed_frame_main, (int(tx_cam_draw),int(ty_cam_draw)), 7, (0,0,255),-1)
                    if ix_cam_draw is not None: cv2.line(processed_frame_main, (int(ix_cam_draw),int(iy_cam_draw)), (int(tx_cam_draw),int(ty_cam_draw)), (255,255,0),2)
                    cv2.putText(processed_frame_main, f"PinchD: {pinch_dist_draw:.1f}", (10,frame_height-40 if frame_height>40 else 10), cv2.FONT_HERSHEY_SIMPLEX,0.6,(255,255,255),1,cv2.LINE_AA)
            
            frame_proc_end_time = time.perf_counter() 
            elapsed_ms_proc = (frame_proc_end_time - frame_overall_processing_start_time) * 1000
            current_fps_proc = 1000/elapsed_ms_proc if elapsed_ms_proc > 0 else float('inf')
            fps_text = f"FPS: {current_fps_proc:.1f}"
            cv2.putText(processed_frame_main, fps_text, (10,30), cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,0,0),2,cv2.LINE_AA)
            cv2.putText(processed_frame_main, fps_text, (10,30), cv2.FONT_HERSHEY_SIMPLEX,0.7,(255,255,255),1,cv2.LINE_AA)
            ts_draw_end = time.perf_counter()
            self.profile_data_vars["DrawOps"].set(round((ts_draw_end - ts_draw_start) * 1000, 2))

            # --- GUI Update for main app's video_label ---
            ts_gui_start = time.perf_counter()
            # Use processed_frame_main for the main display
            img_pil = Image.fromarray(cv2.cvtColor(processed_frame_main, cv2.COLOR_BGR2RGB)) 
            img_tk = ImageTk.PhotoImage(image=img_pil)
            self.video_label.imgtk = img_tk
            self.video_label.configure(image=img_tk)
            ts_gui_end = time.perf_counter()
            self.profile_data_vars["GUIUpdate"].set(round((ts_gui_end - ts_gui_start) * 1000, 2))
        
        elif not calib_active_and_wants_feed: # No control active and no calibration active
            # Clear the main video label if nothing is happening
            # Or show a placeholder. For now, do nothing to keep last frame if any.
            pass


        ts_total_end = time.perf_counter()
        self.profile_data_vars["Total"].set(round((ts_total_end - ts_total_start) * 1000, 2))
        
        time_spent_this_cycle_ms = (ts_total_end - ts_read_end) * 1000 
        actual_delay_needed_ms = max(1, self.frame_process_delay_ms - int(time_spent_this_cycle_ms))
        
        # Ensure loop continues if calibration is active, even if main control is not
        if self.is_control_active or calib_active_and_wants_feed:
            self.root.after(actual_delay_needed_ms, self.process_video_frame)
        else:
            self._processing_loop_active = False


    def on_app_close(self):
        print("Closing application...")
        self.is_control_active = False 
        if self.calibration_window_instance and self.calibration_window_instance.top.winfo_exists():
            self.calibration_window_instance.close_window() # Try to close calib window
        self.calibration_window_instance = None

        if self.video_stream: self.video_stream.stop()
        if self.hand_tracker: self.hand_tracker.close()
        
        self.config_manager.set("sensitivity", self.sensitivity_scale_var.get())
        self.config_manager.save_config()
        
        self.root.destroy()

if __name__ == '__main__':
    import cv2 
    import numpy as np 

    app_root = tk.Tk()
    controller_app = HandMouseControllerApp(app_root)
    app_root.mainloop()
