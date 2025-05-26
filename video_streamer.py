# video_streamer.py
import cv2
import threading
import queue
import time

class WebcamVideoStream:
    """
    A class to handle video capturing in a separate thread to improve FPS.
    Includes more robust resolution handling.
    """
    def __init__(self, src=0, width=480, height=360):
        self.src = src
        self.requested_width = width  # User's preferred width from config
        self.requested_height = height # User's preferred height from config
        self.stream = None
        self.actual_width = 0
        self.actual_height = 0
        self.grabbed = False
        # self.frame = None # Not needed as instance var, handled by queue
        self.stopped = True 
        self.frame_queue = queue.Queue(maxsize=5) 
        self.thread = None
        print(f"[WebcamVideoStream] Initialized for src {self.src} with target requested res {self.requested_width}x{self.requested_height}")

    def _initialize_stream(self):
        """Internal method to open and configure the camera stream robustly."""
        print(f"[WebcamVideoStream] Attempting to open stream source: {self.src}")
        self.stream = cv2.VideoCapture(self.src)
        if not self.stream.isOpened():
            print(f"[WebcamVideoStream] Error: Cannot open video source {self.src}")
            self.stream = None
            return False

        # 1. Get camera's initial default resolution
        initial_default_width = int(self.stream.get(cv2.CAP_PROP_FRAME_WIDTH))
        initial_default_height = int(self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[WebcamVideoStream] Camera's initial default resolution: {initial_default_width}x{initial_default_height}")

        # 2. Attempt to set the requested resolution (from config via main_app)
        final_width_to_set = self.requested_width
        final_height_to_set = self.requested_height

        if not (self.requested_width > 0 and self.requested_height > 0):
            print(f"[WebcamVideoStream] Invalid requested resolution ({self.requested_width}x{self.requested_height}). "
                  f"Will use camera's initial default: {initial_default_width}x{initial_default_height}")
            final_width_to_set = initial_default_width
            final_height_to_set = initial_default_height

        if final_width_to_set > 0 and final_height_to_set > 0:
            print(f"[WebcamVideoStream] Attempting to set resolution to: {final_width_to_set}x{final_height_to_set}")
            self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, final_width_to_set)
            self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, final_height_to_set)
        
        # 3. Get the actual resolution after attempting to set
        current_actual_width = int(self.stream.get(cv2.CAP_PROP_FRAME_WIDTH))
        current_actual_height = int(self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[WebcamVideoStream] Resolution after attempt: {current_actual_width}x{current_actual_height}")

        # 4. Validate and potentially fall back
        # If setting failed (0x0) or is drastically different from a valid request,
        # and also different from the initial default (if initial default was valid), try initial default.
        valid_request = (self.requested_width > 0 and self.requested_height > 0)
        significantly_different_from_request = (
            valid_request and
            (abs(current_actual_width - self.requested_width) > self.requested_width * 0.5 or \
             abs(current_actual_height - self.requested_height) > self.requested_height * 0.5)
        ) # Heuristic: more than 50% different

        if current_actual_width == 0 or current_actual_height == 0 or significantly_different_from_request:
            print(f"[WebcamVideoStream] Current resolution {current_actual_width}x{current_actual_height} is invalid or "
                  f"far from requested {self.requested_width}x{self.requested_height}.")
            if initial_default_width > 0 and initial_default_height > 0:
                print(f"[WebcamVideoStream] Falling back to camera's initial default: {initial_default_width}x{initial_default_height}")
                self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, initial_default_width)
                self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, initial_default_height)
                self.actual_width = int(self.stream.get(cv2.CAP_PROP_FRAME_WIDTH))
                self.actual_height = int(self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT))
            else: # Initial default was also bad
                self.actual_width = current_actual_width # Keep what we got if initial default is also bad
                self.actual_height = current_actual_height
                if self.actual_width == 0 or self.actual_height == 0:
                     print(f"[WebcamVideoStream] Error: Could not establish any valid camera resolution.")
                     if self.stream.isOpened(): self.stream.release()
                     self.stream = None
                     return False
        else: # The resolution set (either requested or initial default if request was invalid) is acceptable
            self.actual_width = current_actual_width
            self.actual_height = current_actual_height
        
        print(f"[WebcamVideoStream] Final operational resolution: {self.actual_width}x{self.actual_height}")

        # Grab the first frame with the final resolution
        self.grabbed, initial_frame = self.stream.read()
        if not self.grabbed or initial_frame is None:
            print(f"[WebcamVideoStream] Error: Failed to grab initial frame with final resolution {self.actual_width}x{self.actual_height} from source {self.src}")
            if self.stream.isOpened(): self.stream.release()
            self.stream = None
            return False
        
        # Clear previous queue if any (e.g. on restart)
        while not self.frame_queue.empty():
            try: self.frame_queue.get_nowait()
            except queue.Empty: break
        self.frame_queue.put(initial_frame)
        return True

    def start(self):
        if not self.stopped:
            print("[WebcamVideoStream] Stream already started.")
            return self
        
        if not self._initialize_stream():
            raise ValueError(f"Failed to initialize webcam stream source {self.src}")

        self.stopped = False
        self.thread = threading.Thread(target=self.update, args=())
        self.thread.daemon = True 
        self.thread.start()
        print("[WebcamVideoStream] Thread started.")
        return self

    def update(self):
        while not self.stopped:
            if self.stream and self.stream.isOpened():
                if not self.frame_queue.full():
                    grabbed, frame = self.stream.read()
                    if not grabbed or frame is None:
                        print("[WebcamVideoStream] Warning: Failed to grab frame in thread. Stream might have ended or camera disconnected.")
                        time.sleep(0.1) 
                        continue 
                    self.frame_queue.put(frame)
                else:
                    time.sleep(0.001) 
            else:
                print("[WebcamVideoStream] Error: Stream not available in update loop. Stopping.")
                self.stopped = True 

        if self.stream and self.stream.isOpened():
            self.stream.release()
            print("[WebcamVideoStream] Stream released in update loop exit.")
        self.stream = None

    def read(self):
        if self.stopped and self.frame_queue.empty():
            return None 
        try:
            return self.frame_queue.get(timeout=0.05) 
        except queue.Empty:
            return None

    def stop(self):
        if self.stopped: 
            return
        print("[WebcamVideoStream] Stopping thread...")
        self.stopped = True 

        if self.thread is not None and self.thread.is_alive():
             self.thread.join(timeout=1.0) 
        if self.thread is not None and self.thread.is_alive(): 
            print("[WebcamVideoStream] Warning: Read thread did not terminate gracefully.")
        
        if self.stream and self.stream.isOpened(): # Ensure release if not done by thread
            self.stream.release()
            print("[WebcamVideoStream] Stream explicitly released in stop method.")
        self.stream = None
        
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break
        print("[WebcamVideoStream] Thread stopped and queue cleared.")
        self.thread = None 
