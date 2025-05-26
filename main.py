# main_app.py
# Version 0.3.4: Reduced mouse move threshold for smoother movement with pynput.

import cv2
import mediapipe as mp
from pynput.mouse import Button, Controller as MouseController # For mouse control
import pyautogui # Still used for pyautogui.size() and potentially initial position
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import numpy as np
import time
import math
import collections
import threading # For threaded video capture
import queue     # For passing frames between threads


class WebcamVideoStream:
    """
    A class to handle video capturing in a separate thread to improve FPS.
    """
    def __init__(self, src=0, width=480, height=360):
        self.stream = cv2.VideoCapture(src)
        if not self.stream.isOpened():
            print(f"[WebcamVideoStream] Error: Cannot open video source {src}")
            raise ValueError("Webcam not accessible")

        self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.actual_width = int(self.stream.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.actual_height = int(self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[WebcamVideoStream] Requested Res: {width}x{height}, Actual Res: {self.actual_width}x{self.actual_height}")

        self.grabbed, initial_frame = self.stream.read()
        if not self.grabbed or initial_frame is None:
            print(f"[WebcamVideoStream] Error: Failed to grab initial frame from source {src}")
            self.stream.release()
            raise ValueError("Failed to grab initial frame")
        
        self.frame_for_read = initial_frame 
        self.stopped = False
        self.frame_queue = queue.Queue(maxsize=5) # Buffer a few frames
        self.frame_queue.put(initial_frame) # Put the first frame in queue

        self.thread = threading.Thread(target=self.update, args=())
        self.thread.daemon = True 

    def start(self):
        self.stopped = False
        self.thread.start()
        print("[WebcamVideoStream] Thread started.")
        return self

    def update(self):
        """The target function for the reading thread."""
        while not self.stopped:
            if not self.frame_queue.full():
                grabbed, frame = self.stream.read()
                if not grabbed or frame is None:
                    # This can happen if the camera is disconnected or the video ends
                    print("[WebcamVideoStream] Warning: Failed to grab frame in thread. Attempting to stop stream.")
                    self.stop() 
                    return
                self.frame_queue.put(frame)
            else:
                time.sleep(0.001) # Queue is full, wait briefly to avoid busy-waiting

        # Release resources when stopped
        if self.stream.isOpened():
            self.stream.release()
        print("[WebcamVideoStream] Stream released.")

    def read(self):
        """Return the latest frame from the queue."""
        try:
            # Get frame from queue, non-blocking with timeout
            return self.frame_queue.get(timeout=0.033) # Timeout after ~1 frame time at 30fps target
        except queue.Empty:
            # This is expected if processing is faster than frame arrival
            return None

    def stop(self):
        """Signal the thread to stop."""
        if self.stopped: # Already stopping/stopped
            return
        print("[WebcamVideoStream] Stopping thread...")
        self.stopped = True
        if self.thread.is_alive():
             self.thread.join(timeout=1.0) # Wait for the thread to finish
        if self.thread.is_alive(): # Check if join timed out
            print("[WebcamVideoStream] Warning: Read thread did not terminate gracefully.")
        
        # Clear the queue after stopping to ensure clean state for potential restart
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break
        print("[WebcamVideoStream] Thread stopped and queue cleared.")


class HandMouseController:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("Hand Gesture Mouse Control v0.3.4 (Smoother Mouse)")

        # --- Mouse Controller (pynput) ---
        self.mouse = MouseController()

        # --- Configuration ---
        self.SCREEN_WIDTH, self.SCREEN_HEIGHT = pyautogui.size() # pyautogui still good for this
        self.CAM_REQUESTED_WIDTH, self.CAM_REQUESTED_HEIGHT = 480, 360
        self.CAM_ACTUAL_WIDTH, self.CAM_ACTUAL_HEIGHT = self.CAM_REQUESTED_WIDTH, self.CAM_REQUESTED_HEIGHT

        self.TARGET_FPS = 60 # Let's aim for higher if processing allows
        self.FRAME_PROCESS_DELAY_MS = int(1000 / self.TARGET_FPS)

        # Smoothing
        self.SMOOTHING_FACTOR = 0.20 # Slightly increased smoothing for more frequent updates
        self.RAW_TARGET_BUFFER_SIZE = 5 # Slightly increased buffer for more frequent updates
        self.raw_target_history_x = collections.deque(maxlen=self.RAW_TARGET_BUFFER_SIZE)
        self.raw_target_history_y = collections.deque(maxlen=self.RAW_TARGET_BUFFER_SIZE)

        # Mouse movement optimization
        self.last_pynput_x = -1 
        self.last_pynput_y = -1
        self.MOUSE_MOVE_THRESHOLD = 1 # Min pixel change to trigger mouse move (was 7)

        # Active region base percentages
        self.BASE_ACTIVE_X_MIN_PERCENT = 0.15
        self.BASE_ACTIVE_X_MAX_PERCENT = 0.85
        self.BASE_ACTIVE_Y_MIN_PERCENT = 0.15
        self.BASE_ACTIVE_Y_MAX_PERCENT = 0.85

        # Click detection
        self.INDEX_FINGER_TIP = 8
        self.THUMB_TIP = 4
        self.PINCH_THRESHOLD_DISTANCE = 25 
        self.is_pinching_prev_frame = False
        self.last_click_event_time = 0
        self.DOUBLE_CLICK_WINDOW_SEC = 0.4

        # --- MediaPipe Hands Setup ---
        self.mp_hands = mp.solutions.hands
        self.hands_detector = self.mp_hands.Hands(
            model_complexity=0, 
            max_num_hands=1,
            min_detection_confidence=0.6, 
            min_tracking_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils

        # --- Tkinter GUI Elements ---
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
        self.sensitivity_scale = ttk.Scale(self.controls_frame, from_=0.5, to=3.0, orient=tk.HORIZONTAL, length=150)
        self.sensitivity_scale.set(1.5)
        self.sensitivity_scale.grid(row=0, column=2, padx=5, pady=5)

        self.status_var = tk.StringVar(value="Status: Idle")
        self.status_label = ttk.Label(self.controls_frame, textvariable=self.status_var, anchor=tk.W)
        self.status_label.grid(row=0, column=3, padx=10, pady=5, sticky=(tk.W, tk.E))
        self.controls_frame.columnconfigure(3, weight=1)

        self.profiling_frame = ttk.LabelFrame(self.main_frame, text="Profiling (ms)", padding="5")
        self.profiling_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        self.profile_data = {
            "Total": tk.DoubleVar(value=0.0), "Read": tk.DoubleVar(value=0.0),
            "PreProc": tk.DoubleVar(value=0.0), "MediaPipe": tk.DoubleVar(value=0.0),
            "ActiveRegion": tk.DoubleVar(value=0.0), "HandLogic": tk.DoubleVar(value=0.0),
            "MouseCtl": tk.DoubleVar(value=0.0), "DrawOps": tk.DoubleVar(value=0.0),
            "GUIUpdate": tk.DoubleVar(value=0.0)
        }
        row_idx, col_idx = 0, 0
        for name, var in self.profile_data.items():
            ttk.Label(self.profiling_frame, text=f"{name}:").grid(row=row_idx, column=col_idx, padx=2, sticky=tk.W)
            ttk.Label(self.profiling_frame, textvariable=var).grid(row=row_idx, column=col_idx+1, padx=(0,10), sticky=tk.W)
            col_idx += 2
            if col_idx >= 6: 
                col_idx = 0
                row_idx += 1
        
        self.is_control_active = False
        self.video_stream = None 
        self.root.protocol("WM_DELETE_WINDOW", self.on_app_close)
        print(f"Screen dimensions: {self.SCREEN_WIDTH}x{self.SCREEN_HEIGHT}")
        print(f"Target webcam resolution: {self.CAM_REQUESTED_WIDTH}x{self.CAM_REQUESTED_HEIGHT}")


    def toggle_control_state(self):
        if self.is_control_active:
            self.stop_hand_control()
        else:
            self.start_hand_control()

    def start_hand_control(self):
        try:
            self.video_stream = WebcamVideoStream(src=0, width=self.CAM_REQUESTED_WIDTH, height=self.CAM_REQUESTED_HEIGHT).start()
            self.CAM_ACTUAL_WIDTH = self.video_stream.actual_width
            self.CAM_ACTUAL_HEIGHT = self.video_stream.actual_height
            if self.CAM_ACTUAL_WIDTH == 0 or self.CAM_ACTUAL_HEIGHT == 0 : # Basic check
                 raise ValueError("Webcam stream started with invalid dimensions.")
            print(f"Hand control using actual cam resolution: {self.CAM_ACTUAL_WIDTH}x{self.CAM_ACTUAL_HEIGHT}")
        except ValueError as e:
            self.status_var.set(f"Status: Error - {e}")
            print(f"Error starting webcam: {e}")
            if self.video_stream: self.video_stream.stop() # Ensure stream is stopped if partially started
            self.video_stream = None
            return

        self.is_control_active = True
        self.start_stop_button.config(text="Stop Control")
        self.status_var.set("Status: Running...")
        print("Hand control started.")
        
        try:
            self.prev_cursor_x, self.prev_cursor_y = self.mouse.position 
            self.last_pynput_x, self.last_pynput_y = self.mouse.position
        except Exception as e: # pynput can sometimes fail on certain systems initially
            print(f"Warning: Could not get initial mouse position with pynput: {e}")
            # Fallback to screen center if pynput fails for initial position
            self.prev_cursor_x, self.prev_cursor_y = self.SCREEN_WIDTH // 2, self.SCREEN_HEIGHT // 2
            self.last_pynput_x, self.last_pynput_y = self.SCREEN_WIDTH // 2, self.SCREEN_HEIGHT // 2


        self.raw_target_history_x.clear()
        self.raw_target_history_y.clear()
        self.process_video_frame()

    def stop_hand_control(self):
        self.is_control_active = False 
        if self.video_stream:
            self.video_stream.stop() 
            self.video_stream = None
        self.start_stop_button.config(text="Start Control")
        self.status_var.set("Status: Stopped.")
        print("Hand control stopped.")
        for var in self.profile_data.values(): var.set(0.0)

    def process_video_frame(self):
        if not self.is_control_active or not self.video_stream:
            return

        ts_total_start = time.perf_counter()
        
        ts_read_start = time.perf_counter()
        frame = self.video_stream.read()
        ts_read_end = time.perf_counter()
        self.profile_data["Read"].set(round((ts_read_end - ts_read_start) * 1000, 2))

        if frame is None: # Queue might be empty if processing is faster than camera
            self.root.after(5, self.process_video_frame) # Try again sooner if aiming for high FPS
            return

        frame_overall_processing_start_time = time.perf_counter()

        ts_preproc_start = time.perf_counter()
        frame = cv2.flip(frame, 1)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # Use actual frame dimensions from the frame itself, in case CAM_ACTUAL_WIDTH/HEIGHT wasn't updated correctly
        # or if the stream provides frames of varying sizes (less common for webcams)
        frame_height, frame_width, _ = frame.shape 
        ts_preproc_end = time.perf_counter()
        self.profile_data["PreProc"].set(round((ts_preproc_end - ts_preproc_start) * 1000, 2))

        ts_mp_start = time.perf_counter()
        frame_rgb.flags.writeable = False
        results = self.hands_detector.process(frame_rgb)
        frame_rgb.flags.writeable = True
        ts_mp_end = time.perf_counter()
        self.profile_data["MediaPipe"].set(round((ts_mp_end - ts_mp_start) * 1000, 2))
        
        ts_activeregion_start = time.perf_counter()
        sensitivity = self.sensitivity_scale.get()
        center_x_cam_percent = (self.BASE_ACTIVE_X_MIN_PERCENT + self.BASE_ACTIVE_X_MAX_PERCENT) / 2
        center_y_cam_percent = (self.BASE_ACTIVE_Y_MIN_PERCENT + self.BASE_ACTIVE_Y_MAX_PERCENT) / 2
        base_active_width_percent = self.BASE_ACTIVE_X_MAX_PERCENT - self.BASE_ACTIVE_X_MIN_PERCENT
        base_active_height_percent = self.BASE_ACTIVE_Y_MAX_PERCENT - self.BASE_ACTIVE_Y_MIN_PERCENT
        effective_active_width_percent = base_active_width_percent / sensitivity
        effective_active_height_percent = base_active_height_percent / sensitivity
        current_active_x_min_percent = np.clip(center_x_cam_percent - effective_active_width_percent / 2, 0.0, 1.0)
        current_active_x_max_percent = np.clip(center_x_cam_percent + effective_active_width_percent / 2, 0.0, 1.0)
        current_active_y_min_percent = np.clip(center_y_cam_percent - effective_active_height_percent / 2, 0.0, 1.0)
        current_active_y_max_percent = np.clip(center_y_cam_percent + effective_active_height_percent / 2, 0.0, 1.0)
        if current_active_x_min_percent >= current_active_x_max_percent: current_active_x_max_percent = current_active_x_min_percent + 0.01
        if current_active_y_min_percent >= current_active_y_max_percent: current_active_y_max_percent = current_active_y_min_percent + 0.01
        ax1 = int(current_active_x_min_percent * frame_width)
        ay1 = int(current_active_y_min_percent * frame_height)
        ax2 = int(current_active_x_max_percent * frame_width)
        ay2 = int(current_active_y_max_percent * frame_height)
        ts_activeregion_end = time.perf_counter()
        self.profile_data["ActiveRegion"].set(round((ts_activeregion_end - ts_activeregion_start) * 1000, 2))

        ts_handlogic_start = time.perf_counter()
        mouse_moved_by_logic = False
        ix_cam_logic, iy_cam_logic, tx_cam_logic, ty_cam_logic, pinch_distance_logic = None, None, None, None, None

        if results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]
            index_tip_landmark = hand_landmarks.landmark[self.INDEX_FINGER_TIP]
            ix_cam_logic = index_tip_landmark.x * frame_width
            iy_cam_logic = index_tip_landmark.y * frame_height
            clamped_ix_cam = np.clip(ix_cam_logic, ax1, ax2)
            clamped_iy_cam = np.clip(iy_cam_logic, ay1, ay2)
            raw_target_screen_x = np.interp(clamped_ix_cam, (ax1, ax2), (0, self.SCREEN_WIDTH))
            raw_target_screen_y = np.interp(clamped_iy_cam, (ay1, ay2), (0, self.SCREEN_HEIGHT))
            self.raw_target_history_x.append(raw_target_screen_x)
            self.raw_target_history_y.append(raw_target_screen_y)
            if self.raw_target_history_x: # Check if deque is populated
                 averaged_target_screen_x = sum(self.raw_target_history_x) / len(self.raw_target_history_x)
                 averaged_target_screen_y = sum(self.raw_target_history_y) / len(self.raw_target_history_y)
            else: # Fallback if buffer is empty
                 averaged_target_screen_x = raw_target_screen_x
                 averaged_target_screen_y = raw_target_screen_y

            current_cursor_x = self.prev_cursor_x*(1-self.SMOOTHING_FACTOR) + averaged_target_screen_x*self.SMOOTHING_FACTOR
            current_cursor_y = self.prev_cursor_y*(1-self.SMOOTHING_FACTOR) + averaged_target_screen_y*self.SMOOTHING_FACTOR
            
            self.prev_cursor_x, self.prev_cursor_y = current_cursor_x, current_cursor_y
            mouse_moved_by_logic = True 

            thumb_tip_landmark = hand_landmarks.landmark[self.THUMB_TIP]
            tx_cam_logic = thumb_tip_landmark.x * frame_width
            ty_cam_logic = thumb_tip_landmark.y * frame_height
            pinch_distance_logic = math.hypot(ix_cam_logic - tx_cam_logic, iy_cam_logic - ty_cam_logic)
            is_pinching_this_frame = pinch_distance_logic < self.PINCH_THRESHOLD_DISTANCE
            
            if is_pinching_this_frame and not self.is_pinching_prev_frame:
                current_time = time.perf_counter()
                if (current_time - self.last_click_event_time) < self.DOUBLE_CLICK_WINDOW_SEC:
                    self.mouse.click(Button.left, 2) 
                    self.status_var.set("Status: Double Click!")
                    self.last_click_event_time = 0 
                else:
                    self.mouse.click(Button.left, 1) 
                    self.status_var.set("Status: Click!")
                self.last_click_event_time = current_time
            self.is_pinching_prev_frame = is_pinching_this_frame
            if not is_pinching_this_frame and not self.status_var.get().startswith("Status: Error"):
                if self.is_control_active: self.status_var.set("Status: Running...")
        else: 
            if self.is_control_active: self.status_var.set("Status: No Hand Detected")
            self.is_pinching_prev_frame = False
            self.raw_target_history_x.clear()
            self.raw_target_history_y.clear()
        ts_handlogic_end = time.perf_counter()
        self.profile_data["HandLogic"].set(round((ts_handlogic_end - ts_handlogic_start) * 1000, 2))

        ts_mousectl_start = time.perf_counter()
        if mouse_moved_by_logic: 
            final_cursor_x_int = int(self.prev_cursor_x) 
            final_cursor_y_int = int(self.prev_cursor_y)
            final_cursor_x_int = max(0, min(final_cursor_x_int, self.SCREEN_WIDTH -1))
            final_cursor_y_int = max(0, min(final_cursor_y_int, self.SCREEN_HEIGHT -1))

            if abs(final_cursor_x_int - self.last_pynput_x) > self.MOUSE_MOVE_THRESHOLD or \
               abs(final_cursor_y_int - self.last_pynput_y) > self.MOUSE_MOVE_THRESHOLD:
                self.mouse.position = (final_cursor_x_int, final_cursor_y_int) 
                self.last_pynput_x = final_cursor_x_int
                self.last_pynput_y = final_cursor_y_int
        ts_mousectl_end = time.perf_counter()
        self.profile_data["MouseCtl"].set(round((ts_mousectl_end - ts_mousectl_start) * 1000, 2))

        ts_draw_start = time.perf_counter()
        cv2.rectangle(frame, (ax1, ay1), (ax2, ay2), (0, 255, 0), 2) 
        if results.multi_hand_landmarks and ix_cam_logic is not None: 
            hand_landmarks_for_draw = results.multi_hand_landmarks[0] 
            self.mp_drawing.draw_landmarks(frame, hand_landmarks_for_draw, self.mp_hands.HAND_CONNECTIONS)
            cv2.circle(frame, (int(ix_cam_logic), int(iy_cam_logic)), 7, (255, 0, 0), -1)
            if tx_cam_logic is not None: 
                cv2.circle(frame, (int(tx_cam_logic), int(ty_cam_logic)), 7, (0, 0, 255), -1)
                cv2.line(frame, (int(ix_cam_logic), int(iy_cam_logic)), (int(tx_cam_logic), int(ty_cam_logic)), (255,255,0), 2)
                cv2.putText(frame, f"PinchD: {pinch_distance_logic:.1f}", (10, frame_height - 40 if frame_height > 40 else 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1, cv2.LINE_AA)
        
        frame_proc_end_time = time.perf_counter() 
        elapsed_time_ms_proc = (frame_proc_end_time - frame_overall_processing_start_time) * 1000
        current_fps_proc = 1000 / elapsed_time_ms_proc if elapsed_time_ms_proc > 0 else float('inf')
        fps_text = f"FPS: {current_fps_proc:.1f}"
        cv2.putText(frame, fps_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,0), 2, cv2.LINE_AA)
        cv2.putText(frame, fps_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 1, cv2.LINE_AA)
        ts_draw_end = time.perf_counter()
        self.profile_data["DrawOps"].set(round((ts_draw_end - ts_draw_start) * 1000, 2))

        ts_gui_start = time.perf_counter()
        img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        img_tk = ImageTk.PhotoImage(image=img_pil)
        self.video_label.imgtk = img_tk
        self.video_label.configure(image=img_tk)
        ts_gui_end = time.perf_counter()
        self.profile_data["GUIUpdate"].set(round((ts_gui_end - ts_gui_start) * 1000, 2))

        ts_total_end = time.perf_counter()
        self.profile_data["Total"].set(round((ts_total_end - ts_total_start) * 1000, 2))
        
        time_spent_this_cycle_ms = (ts_total_end - ts_read_end) * 1000 
        actual_delay_needed_ms = max(1, self.FRAME_PROCESS_DELAY_MS - int(time_spent_this_cycle_ms))
        self.root.after(actual_delay_needed_ms, self.process_video_frame)

    def on_app_close(self):
        print("Closing application...")
        self.is_control_active = False 
        if self.video_stream: self.video_stream.stop()
        if self.hands_detector: self.hands_detector.close()
        self.root.destroy()

if __name__ == '__main__':
    app_root = tk.Tk()
    controller_app = HandMouseController(app_root)
    app_root.mainloop()
