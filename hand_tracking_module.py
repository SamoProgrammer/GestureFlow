# hand_tracking_module.py
import mediapipe as mp
import math

class HandTracker:
    def __init__(self, model_complexity=0, max_num_hands=1, 
                 min_detection_confidence=0.6, min_tracking_confidence=0.5):
        self.mp_hands = mp.solutions.hands
        self.hands_detector = self.mp_hands.Hands(
            model_complexity=model_complexity,
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.results = None # To store the latest results

        # Landmark IDs
        self.INDEX_FINGER_TIP = 8
        self.THUMB_TIP = 4
        # Add other landmark IDs if needed, e.g., for other gestures
        # self.MIDDLE_FINGER_TIP = 12
        # self.WRIST = 0

    def process_frame(self, frame_rgb):
        """Processes an RGB frame to detect hand landmarks."""
        frame_rgb.flags.writeable = False # Optimization
        self.results = self.hands_detector.process(frame_rgb)
        frame_rgb.flags.writeable = True # Restore writeable flag
        return self.results # Return the raw results object

    def get_landmarks(self, hand_index=0):
        """Returns the landmarks for a specific detected hand."""
        if self.results and self.results.multi_hand_landmarks:
            if hand_index < len(self.results.multi_hand_landmarks):
                return self.results.multi_hand_landmarks[hand_index]
        return None

    def get_finger_tip_coordinates(self, frame_width, frame_height, finger_tip_id, hand_index=0):
        """
        Gets the (x, y) pixel coordinates of a specific finger tip landmark.
        Returns (None, None) if not found.
        """
        hand_landmarks = self.get_landmarks(hand_index)
        if hand_landmarks:
            try:
                landmark = hand_landmarks.landmark[finger_tip_id]
                cx, cy = int(landmark.x * frame_width), int(landmark.y * frame_height)
                return cx, cy
            except IndexError:
                print(f"Error: Landmark ID {finger_tip_id} out of range.")
                return None, None
        return None, None

    def get_pinch_info(self, frame_width, frame_height, hand_index=0):
        """
        Calculates the distance between index finger tip and thumb tip.
        Returns (ix, iy, tx, ty, distance) or (None, None, None, None, float('inf')) if not found.
        """
        ix, iy = self.get_finger_tip_coordinates(frame_width, frame_height, self.INDEX_FINGER_TIP, hand_index)
        tx, ty = self.get_finger_tip_coordinates(frame_width, frame_height, self.THUMB_TIP, hand_index)

        if ix is not None and tx is not None:
            distance = math.hypot(ix - tx, iy - ty)
            return ix, iy, tx, ty, distance
        return None, None, None, None, float('inf')


    def draw_landmarks_on_frame(self, frame, hand_landmarks):
        """Draws the detected hand landmarks and connections onto the frame."""
        if hand_landmarks:
            self.mp_drawing.draw_landmarks(
                frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)

    def close(self):
        """Releases MediaPipe Hands resources."""
        if self.hands_detector:
            self.hands_detector.close()
            print("[HandTracker] MediaPipe Hands resources released.")

if __name__ == '__main__':
    # Example Usage (requires a webcam and OpenCV for testing)
    import cv2
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Cannot open camera")
        exit()

    tracker = HandTracker()
    
    try:
        while cap.isOpened():
            success, image = cap.read()
            if not success:
                print("Ignoring empty camera frame.")
                continue

            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = tracker.process_frame(image_rgb)
            
            frame_height, frame_width, _ = image.shape

            hand_landmarks = tracker.get_landmarks()
            if hand_landmarks:
                tracker.draw_landmarks_on_frame(image, hand_landmarks)
                
                ix, iy, tx, ty, pinch_dist = tracker.get_pinch_info(frame_width, frame_height)
                if ix is not None:
                    cv2.circle(image, (ix, iy), 7, (255, 0, 0), -1) # Blue for index
                if tx is not None:
                    cv2.circle(image, (tx, ty), 7, (0, 0, 255), -1) # Red for thumb
                if ix is not None and tx is not None:
                     cv2.line(image, (ix, iy), (tx,ty), (0,255,0), 2)
                cv2.putText(image, f"PinchD: {pinch_dist:.1f}", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 1, cv2.LINE_AA)


            cv2.imshow('Hand Tracking Test', cv2.flip(image, 1))
            if cv2.waitKey(5) & 0xFF == 27: # ESC key
                break
    finally:
        tracker.close()
        cap.release()
        cv2.destroyAllWindows()
