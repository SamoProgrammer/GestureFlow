<p align="center">
  <img src="https://placehold.co/1500x350/1A1A2E/F5F5F5/png?text=GestureFlow&font=montserrat&font_size=80&bg_opacity=0.1&padding=50&border_radius=25&text_shadow_offset_x=2&text_shadow_offset_y=2&text_shadow_blur_radius=5&text_shadow_color=00000033" alt="GestureFlow - Control Your PC with Hand Gestures" style="border-radius: 25px; max-width: 900px;">
</p>

<h1 align="center">GestureFlow: Hand Gesture Mouse Control</h1>

<p align="center">
  <strong>Navigate your computer using simple hand movements captured by your webcam!</strong>
  <br />
  <a href="#features">Features</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#requirements">Requirements</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#calibration">Calibration</a> •
  <a href="#troubleshooting">Troubleshooting</a>
  </p>

---

## 👋 Introduction

GestureFlow is an innovative desktop application that transforms your webcam into a futuristic input device. Say goodbye to constant mouse clicking and scrolling for simple tasks! With GestureFlow, you can control your mouse cursor, perform clicks, and double-clicks using intuitive hand gestures. It's designed to be easy to use, even for non-technical users, bringing a touch of magic to your daily computer interactions.

Whether you're looking for a more ergonomic way to interact with your PC, want to impress your friends, or simply explore the possibilities of computer vision, GestureFlow offers a unique and engaging experience.

## ✨ Features

* **Intuitive Gesture Control:**
    * **Cursor Movement:** Guide your mouse cursor by moving your index finger.
    * **Single Click:** Perform a quick pinch gesture with your thumb and index finger.
    * **Double Click:** Perform two quick pinch gestures.
* **Webcam-Based:** Uses your existing webcam – no special hardware required!
* **User-Friendly Interface:** Simple GUI to start/stop control and adjust settings.
* **Real-time Visual Feedback:** See your hand and detected landmarks directly in the app.
* **Sensitivity Adjustment:** Fine-tune how responsive the cursor is to your hand movements.
* **Calibration System:** Personalize the active movement area and pinch gesture sensitivity for optimal comfort and accuracy.
* **Cross-Platform (Python-based):** Designed to run on various operating systems where Python and the required libraries are supported.
* **Performance Optimized:** Strives for smooth operation and responsiveness.

## 🤔 How It Works (Simplified)

1.  **Camera Access:** GestureFlow uses your webcam to see your hand.
2.  **Hand Detection:** Specialized computer vision technology (Google's MediaPipe) identifies your hand and key points on your fingers (like your index fingertip and thumb tip) in real-time.
3.  **Gesture Recognition:** The application continuously analyzes the position and relationship of these key points:
    * The position of your index fingertip is mapped to the mouse cursor's position on your screen.
    * When your index finger and thumb come close together (a pinch), it's recognized as a click.
4.  **Mouse Control:** Based on the recognized gestures, GestureFlow then tells your operating system to move the mouse or perform a click, just as if you were using a physical mouse.

All of this happens many times per second to create a fluid experience!

## 📋 Requirements

Before you begin, ensure you have the following installed on your system:

1.  **Python:** Version 3.7 or newer is recommended. You can download it from [python.org](https://www.python.org/downloads/).
    * When installing Python on Windows, make sure to check the box that says **"Add Python to PATH"**.
2.  **Webcam:** A standard USB webcam or your laptop's built-in camera.

## 🚀 Installation

Setting up GestureFlow is straightforward. Follow these steps:

1.  **Download the Project:**
    * Go to the [GestureFlow GitHub repository page](https://github.com/your-username/gestureflow) (replace with your actual link).
    * Click the green "Code" button and then "Download ZIP".
    * Extract the downloaded ZIP file to a folder on your computer (e.g., `C:\GestureFlow` or `~/GestureFlow`).

2.  **Open a Terminal or Command Prompt:**
    * **Windows:** Search for "cmd" or "PowerShell".
    * **macOS:** Search for "Terminal".
    * **Linux:** Usually Ctrl+Alt+T or search for "Terminal".

3.  **Navigate to the Project Folder:**
    Use the `cd` (change directory) command to go into the folder where you extracted the project files. For example:
    ```bash
    cd C:\GestureFlow\GestureFlow-main 
    # Or for macOS/Linux:
    # cd ~/GestureFlow/GestureFlow-main
    ```
    (The folder name might vary slightly depending on the ZIP extraction).

4.  **Install Required Packages:**
    While in the project folder in your terminal, run the following command to install all the necessary software libraries GestureFlow depends on:
    ```bash
    pip install opencv-python mediapipe pynput pyautogui Pillow numpy
    ```
    This command tells Python's package installer (`pip`) to download and set up these libraries. Wait for the installation to complete. You should see messages indicating successful installation.

That's it! GestureFlow is now ready to use.

## 💻 Usage

1.  **Run the Application:**
    * Make sure you are still in the project folder in your terminal/command prompt.
    * Execute the main application file using Python:
        ```bash
        python main_app.py
        ```
    * The GestureFlow application window should appear.

2.  **Using GestureFlow:**
    * **Start Control:** Click the "Start Control" button in the application window. The webcam feed should appear, showing your hand.
    * **Position Your Hand:** Place your hand in front of the webcam so it's clearly visible within the camera view.
    * **Move Cursor:** Move your index finger; the mouse cursor on your screen should follow.
    * **Single Click:** Make a quick pinch gesture with your index finger and thumb.
    * **Double Click:** Make two quick pinch gestures in succession.
    * **Sensitivity:** Adjust the "Sensitivity" slider if the cursor moves too fast or too slow for your liking.
    * **Stop Control:** Click the "Stop Control" button to pause gesture control and use your physical mouse normally.

3.  **Exiting the Application:**
    * Simply close the GestureFlow application window.

## 🛠️ Calibration (Important for Best Experience!)

For GestureFlow to work best for *you* and *your setup* (your hand size, distance from camera, lighting), **calibration is highly recommended!**

1.  **Open Calibration:**
    * Start the GestureFlow application (`python main_app.py`).
    * Click the "Start Control" button to activate the camera.
    * Then, click the "Calibrate" button. A new window will open.

2.  **Active Region Calibration:**
    * This lets you define the area your hand will move in to control the entire screen.
    * Follow the on-screen instructions in the "Active Region" tab to capture your comfortable top-left and bottom-right hand positions.
    * A small camera preview in the calibration window will help guide you.

3.  **Pinch Gesture Calibration:**
    * This helps the app learn how *you* make a pinch for clicking.
    * Go to the "Pinch Gesture" tab.
    * Follow the instructions to first show the app your "open hand" (no click) and then your "pinched hand" (click).

4.  **Apply & Save:**
    * Once you've completed the calibration steps you want, click "Apply & Save All" in the calibration window.
    * Your personalized settings will be saved and used the next time you start GestureFlow.

You can also "Reset Calibrations" to go back to the default settings.

## ⚠️ Troubleshooting

* **Application doesn't start / "Module not found" errors:**
    * Ensure you have run the `pip install ...` command (Step 4 in Installation) successfully from within the correct project folder.
    * Make sure Python is installed correctly and added to your system's PATH.
* **Webcam doesn't turn on / "Cannot open webcam" error:**
    * Ensure your webcam is properly connected and not being used by another application (e.g., Zoom, Skype).
    * Try restarting the application.
    * On some systems, you might need to grant permission for Python or the terminal application to access the camera.
* **Hand not detected or tracking is poor:**
    * Ensure good, consistent lighting on your hand. Avoid very dark rooms or strong backlighting.
    * Keep your hand clearly visible to the camera, without obstructions.
    * Try moving your hand a bit slower, especially initially.
* **Mouse movement is jumpy or clicks are unreliable:**
    * **Run the Calibration!** This is the most common solution for these issues. Calibrating the Active Region and Pinch Gesture makes a huge difference.
    * Adjust the "Sensitivity" slider in the main window.

## 🤝 Contributing (Optional)

This project is open source! If you're a developer and interested in contributing, please feel free to:
* Fork the repository.
* Create a new branch for your feature or bug fix.
* Submit a pull request with a clear description of your changes.

(You can add more specific contribution guidelines here if you wish, like coding standards, issue templates, etc.)

## 📜 License

This project is licensed under the MIT License - see the `LICENSE.txt` file for details (you'll need to create this file and add the MIT license text if you choose this license).

## 🙏 Acknowledgements

GestureFlow is made possible by the amazing work of the open-source community and these incredible libraries:

* **OpenCV:** For robust computer vision and webcam access.
* **MediaPipe (by Google):** For cutting-edge hand landmark detection.
* **pynput:** For cross-platform mouse control.
* **PyAutoGUI:** For utility functions like getting screen size.
* **Pillow (PIL Fork):** For image manipulation.
* **NumPy:** For efficient numerical operations.
* **Tkinter:** For the graphical user interface.

And a big thank you to all users and contributors!