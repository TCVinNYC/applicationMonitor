# monitor.py

import time
import platform
import logging
import numpy as np
from mss import mss
from PySide6.QtCore import QThread, Signal
import cv2

from detector import PersonDetector

if platform.system() == 'Windows':
    import win32gui
elif platform.system() == 'Darwin':
    from AppKit import NSWorkspace

import pyautogui

class ScreenMonitor(QThread):
    """
    Monitors a selected region of the screen for person detection.
    Emits frames with detections for display.
    """
    frame_updated = Signal(np.ndarray)
    monitoring_paused = Signal()
    monitoring_resumed = Signal()
    log_event = Signal(str)  # Signal for logging events

    def __init__(self, region, target_app_name=None):
        super().__init__()
        self.region = region  # {'top': y, 'left': x, 'width': w, 'height': h}
        self.detector = PersonDetector('MobileNetSSD_deploy.prototxt',
                                       'MobileNetSSD_deploy.caffemodel')
        self.is_paused = False
        self.target_app_name = target_app_name or 'Wirecast'
        self.macro_keys = []
        self.is_running = False
        self.sct = mss()
        self.delay = 0.1  # Adjust as needed
        self.out_of_focus_time = None  # Timestamp when application lost focus or monitoring started
        self.focus_delay = 5  # Delay in seconds before pausing monitoring
        self.user_paused = False  # Track if monitoring was paused by the user or macro command

    def set_macro_keys(self, macro_keys):
        self.macro_keys = macro_keys

    def get_active_window_title(self):
        """
        Returns the title of the currently active window.
        """
        try:
            if platform.system() == 'Windows':
                window = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(window)
                return title
            elif platform.system() == 'Darwin':
                active_app = NSWorkspace.sharedWorkspace().activeApplication()
                title = active_app['NSApplicationName']
                return title
            else:
                return None
        except Exception as e:
            logging.error(f"Error getting active window title: {e}")
            return None

    def run(self):
        logging.info("Monitoring started.")
        self.log_event.emit("Monitoring started.")
        no_person_time = None
        self.is_running = True
        self.out_of_focus_time = None  # Start with None
        while not self.isInterruptionRequested():
            if self.is_paused:
                time.sleep(self.delay)
                continue

            active_window = self.get_active_window_title()
            if active_window and self.target_app_name.lower() in active_window.lower():
                # Target application is in focus
                if self.out_of_focus_time is not None:
                    self.out_of_focus_time = None  # Reset the out-of-focus timer

                if self.is_paused and not self.user_paused:
                    self.resume()
                    resume_message = f"Monitoring resumed. '{self.target_app_name}' is in focus."
                    logging.info(resume_message)
                    self.log_event.emit(resume_message)

                # Proceed with person detection
                frame = self.capture_screen(self.region)
                boxes = self.detector.detect(frame)

                # Draw detections
                for box in boxes:
                    x1, y1, x2, y2 = box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                self.frame_updated.emit(frame)

                if boxes:
                    no_person_time = None
                else:
                    if no_person_time is None:
                        no_person_time = time.time()
                    elif time.time() - no_person_time >= 1:
                        self.switch_to_safe_camera()
                        no_person_message = f"No person detected at {time.strftime('%H:%M:%S')}"
                        logging.info(no_person_message)
                        self.log_event.emit(no_person_message)
                        no_person_time = None

            else:
                # Target application is not in focus
                if self.is_paused:
                    # Already paused, do nothing
                    pass
                else:
                    if self.out_of_focus_time is None:
                        self.out_of_focus_time = time.time()  # Start the out-of-focus timer
                    elif time.time() - self.out_of_focus_time >= self.focus_delay:
                        self.pause()
                        pause_message = f"Monitoring paused after {self.focus_delay} seconds. '{self.target_app_name}' is not in focus."
                        logging.info(pause_message)
                        self.log_event.emit(pause_message)
                        self.out_of_focus_time = None  # Reset out_of_focus_time after pausing

                # Do not proceed with person detection when application is not in focus

            time.sleep(self.delay)

    def capture_screen(self, region):
        img = np.array(self.sct.grab(region))
        frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return frame

    def stop(self):
        self.requestInterruption()
        self.wait()

    def pause(self, user_initiated=False):
        self.is_paused = True
        if user_initiated:
            self.user_paused = True
        self.monitoring_paused.emit()

    def resume(self):
        self.is_paused = False
        self.user_paused = False
        self.monitoring_resumed.emit()

    def switch_to_safe_camera(self):
        try:
            pyautogui.hotkey(*self.macro_keys)
            event = f"Switched to safe camera using macro: {' + '.join(self.macro_keys).title()}"
            logging.info(event)
            self.log_event.emit(event)
            # Pause monitoring and set user_paused to True
            self.pause(user_initiated=True)
        except Exception as e:
            event = f"Error sending macro keys: {e}"
            logging.error(event)
            self.log_event.emit(event)
