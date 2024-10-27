# gui.py

import sys
import platform
import logging
import cv2
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout,
    QInputDialog, QMessageBox, QSizePolicy, QTextEdit
)
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QPen
from PySide6.QtCore import Qt, QTimer, QRect, Signal, Slot
import numpy as np
import psutil
from mss import mss
from datetime import datetime

from monitor import ScreenMonitor

class AppGUI(QWidget):
    """
    Manages the graphical user interface using PySide6.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Application Monitor")
        self.region = None
        self.monitor = None
        self.target_app_name = ''  # Default target application
        self.macro_keys = ['5'] if platform.system() == 'Windows' else ['5']
        self.monitoring_state = 'stopped'  # 'stopped', 'running', 'paused'
        self.border_color = QColor(255, 0, 0)  # Red for monitoring, blue for paused
        self.is_selecting = False
        self.selection_rect = QRect()
        self.history_log = []  # Initialize history log

        self.sct = mss()
        self.screen = QApplication.primaryScreen()
        self.screen_size = self.screen.size()
        self.screen_width = self.screen_size.width()
        self.screen_height = self.screen_size.height()

        self.init_ui()

    def init_ui(self):
        # Status Label
        self.status_label = QLabel("Status: Not Monitoring")
        # Target Application
        self.app_name_label = QLabel(f"Target Application: {self.target_app_name}")
        self.change_app_button = QPushButton("Change Target Application")
        self.change_app_button.clicked.connect(self.change_target_app)
        # Macro Keys
        self.macro_label = QLabel(f"Macro Keys: {self.format_macro_keys()}")
        self.change_macro_button = QPushButton("Change Macro Keys")
        self.change_macro_button.clicked.connect(self.change_macro_keys)
        # Monitor Button
        self.monitor_button = QPushButton("Start Monitoring")
        self.monitor_button.clicked.connect(self.toggle_monitoring)
        # Live Feed Label
        self.feed_label = QLabel()
        self.feed_label.setAlignment(Qt.AlignCenter)
        self.feed_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.feed_label.setMinimumSize(800, 600)
        # Quit Button
        self.quit_button = QPushButton("Quit")
        self.quit_button.clicked.connect(self.quit_application)
        # Reset Selection Button
        self.reset_button = QPushButton("Reset Selection")
        self.reset_button.clicked.connect(self.reset_selection)
        self.reset_button.setEnabled(False)  # Disabled initially
        # History Button
        self.history_button = QPushButton("Show History")
        self.history_button.clicked.connect(self.show_history)

        # Layouts
        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.app_name_label)
        hbox1.addWidget(self.change_app_button)
        hbox2 = QHBoxLayout()
        hbox2.addWidget(self.macro_label)
        hbox2.addWidget(self.change_macro_button)
        hbox3 = QHBoxLayout()
        hbox3.addWidget(self.monitor_button)
        hbox3.addWidget(self.reset_button)
        hbox3.addWidget(self.history_button)

        vbox = QVBoxLayout()
        vbox.addWidget(self.status_label)
        vbox.addLayout(hbox1)
        vbox.addLayout(hbox2)
        vbox.addLayout(hbox3)
        vbox.addWidget(self.feed_label)
        vbox.addWidget(self.quit_button)

        self.setLayout(vbox)

        # Mouse Events for Region Selection
        self.feed_label.mousePressEvent = self.on_mouse_press
        self.feed_label.mouseMoveEvent = self.on_mouse_move
        self.feed_label.mouseReleaseEvent = self.on_mouse_release

        # Timer for updating the feed
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_feed)
        self.timer.start(100)  # Update every 100 ms

    def format_macro_keys(self):
        return ' + '.join([key.title() for key in self.macro_keys])

    def change_target_app(self):
        app_names = []
        if platform.system() == 'Darwin':
            # macOS
            from AppKit import NSWorkspace, NSApplicationActivationPolicyRegular
            running_apps = NSWorkspace.sharedWorkspace().runningApplications()
            app_names = [app.localizedName() for app in running_apps if
                         app.activationPolicy() == NSApplicationActivationPolicyRegular]
            app_names = sorted(set(app_names))
        elif platform.system() == 'Windows':
            # Windows
            import win32gui
            def enum_windows(hwnd, result):
                if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                    result.append(win32gui.GetWindowText(hwnd))

            window_titles = []
            win32gui.EnumWindows(enum_windows, window_titles)
            app_names = list(set(window_titles))  # Remove duplicates
            app_names = sorted(app_names)
        else:
            # Fallback to psutil
            app_names = []
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name']:
                        app_names.append(proc.info['name'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            app_names = sorted(set(app_names))

        if not app_names:
            QMessageBox.warning(self, "No Applications Found", "No running applications were found.")
            return

        # Create a dialog to select application
        app_name, ok = QInputDialog.getItem(self, "Select Application", "Choose the application to monitor:", app_names,
                                            editable=False)
        if ok and app_name:
            self.target_app_name = app_name
            self.app_name_label.setText(f"Target Application: {self.target_app_name}")
            if self.monitor:
                self.monitor.target_app_name = self.target_app_name

    def change_macro_keys(self):
        keys, ok = QInputDialog.getText(self, "Macro Keys", "Enter the keys to press (comma-separated):", text=', '.join(self.macro_keys))
        if ok and keys:
            self.macro_keys = [key.strip() for key in keys.split(',')]
            self.macro_label.setText(f"Macro Keys: {self.format_macro_keys()}")
            if self.monitor:
                self.monitor.set_macro_keys(self.macro_keys)

    def toggle_monitoring(self):
        if self.monitoring_state == 'stopped':
            self.start_monitoring()
        elif self.monitoring_state == 'running':
            self.pause_monitoring()
        elif self.monitoring_state == 'paused':
            self.resume_monitoring()

    def start_monitoring(self):
        if not self.region:
            QMessageBox.warning(self, "Region Not Set",
                                "Please select a region by drawing a rectangle on the live feed.")
            return

        if self.monitor and self.monitor.isRunning():
            QMessageBox.warning(self, "Already Monitoring", "Monitoring is already running.")
            return

        self.monitor = ScreenMonitor(self.region, self.target_app_name)
        self.monitor.set_macro_keys(self.macro_keys)
        self.monitor.frame_updated.connect(self.display_frame)
        self.monitor.monitoring_paused.connect(self.on_monitoring_paused)
        self.monitor.monitoring_resumed.connect(self.on_monitoring_resumed)
        self.monitor.start()
        self.monitoring_state = 'running'
        self.status_label.setText("Status: Monitoring")
        self.monitor_button.setText("Pause Monitoring")
        self.border_color = QColor(255, 0, 0)  # Red
        logging.info("Monitoring started.")
        self.monitor.log_event.connect(self.on_log_event)
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.history_log.append(f"{timestamp} - Monitoring started.")

    def pause_monitoring(self):
        if self.monitor and not self.monitor.is_paused:
            self.monitor.pause(user_initiated=True)
            # The GUI updates will be handled in the on_monitoring_paused slot

    def resume_monitoring(self):
        if self.monitor and self.monitor.is_paused:
            self.monitor.resume()
            # The GUI updates will be handled in the on_monitoring_resumed slot

    @Slot()
    def on_monitoring_paused(self):
        self.monitoring_state = 'paused'
        self.status_label.setText("Status: Paused")
        self.monitor_button.setText("Resume Monitoring")
        self.border_color = QColor(0, 0, 255)  # Blue
        if self.monitor.is_paused and self.monitor.user_paused:
            # Monitoring paused due to user action or macro command execution
            logging.info("Monitoring paused by user or after command execution.")
            self.history_log.append(
                f"{datetime.now().strftime('%H:%M:%S')} - Monitoring paused by user or after command execution.")
        else:
            logging.info("Monitoring paused due to application focus.")
            self.history_log.append(
                f"{datetime.now().strftime('%H:%M:%S')} - Monitoring paused due to application focus.")

    @Slot()
    def on_monitoring_resumed(self):
        self.monitoring_state = 'running'
        self.status_label.setText("Status: Monitoring")
        self.monitor_button.setText("Pause Monitoring")
        self.border_color = QColor(255, 0, 0)  # Red
        logging.info("Monitoring resumed due to application focus.")

    def update_feed(self):
        if self.monitoring_state == 'stopped':
            # Always capture the full desktop
            monitor = self.sct.monitors[0]
            img = np.array(self.sct.grab(monitor))
            frame = img[:, :, :3]  # Remove alpha channel
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            height, width, _ = frame.shape

            # Convert to QImage
            bytes_per_line = 3 * width
            q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(q_img)
            # Scale pixmap to fit label while maintaining aspect ratio
            pixmap = pixmap.scaled(self.feed_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)

            # Draw selection rectangle if any
            if not self.selection_rect.isNull():
                painter = QPainter(pixmap)
                pen = QPen(self.border_color, 2)
                painter.setPen(pen)
                # Adjust rectangle to scaled pixmap
                scale_x = pixmap.width() / self.feed_label.width()
                scale_y = pixmap.height() / self.feed_label.height()
                scaled_rect = QRect(
                    self.selection_rect.left() * scale_x,
                    self.selection_rect.top() * scale_y,
                    self.selection_rect.width() * scale_x,
                    self.selection_rect.height() * scale_y
                )
                painter.drawRect(scaled_rect)
                painter.end()

            self.feed_label.setPixmap(pixmap)

    @Slot(np.ndarray)
    def display_frame(self, frame):
        # Similar adjustments as in update_feed
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_BGR888)
        pixmap = QPixmap.fromImage(q_img)
        # Scale pixmap to fit label while maintaining aspect ratio
        pixmap = pixmap.scaled(self.feed_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.feed_label.setPixmap(pixmap)

    def on_mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            self.is_selecting = True
            self.selection_rect.setTopLeft(event.pos())
            self.selection_rect.setBottomRight(event.pos())

    def on_mouse_move(self, event):
        if self.is_selecting:
            self.selection_rect.setBottomRight(event.pos())

    def on_mouse_release(self, event):
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.is_selecting = False
            # Map the selection rectangle to screen coordinates
            label_width = self.feed_label.width()
            label_height = self.feed_label.height()
            pixmap = self.feed_label.pixmap()
            if pixmap:
                pixmap_width = pixmap.width()
                pixmap_height = pixmap.height()
                scale_x = self.screen_width / pixmap_width
                scale_y = self.screen_height / pixmap_height
                x = int(self.selection_rect.left() * scale_x)
                y = int(self.selection_rect.top() * scale_y)
                w = int(self.selection_rect.width() * scale_x)
                h = int(self.selection_rect.height() * scale_y)
                self.region = {'top': y, 'left': x, 'width': w, 'height': h}
                logging.info(f"Region selected: {self.region}")
                self.reset_button.setEnabled(True)

    def reset_selection(self):
        self.region = None
        self.selection_rect = QRect()
        self.reset_button.setEnabled(False)
        if self.monitor and self.monitor.isRunning():
            self.monitor.stop()
            self.monitor.wait()
        self.monitor = None  # Reset monitor
        self.monitoring_state = 'stopped'
        self.monitor_button.setText("Start Monitoring")
        self.status_label.setText("Status: Not Monitoring")
        logging.info("Selection reset. Monitoring stopped.")
        self.history_log.append("Selection reset. Monitoring stopped.")

    def show_history(self):
        history_window = QWidget()
        history_window.setWindowTitle("History")
        history_text = QTextEdit()
        history_text.setReadOnly(True)
        history_text.setText('\n'.join(self.history_log))
        layout = QVBoxLayout()
        layout.addWidget(history_text)
        history_window.setLayout(layout)
        history_window.resize(600, 400)
        history_window.show()
        self.history_window = history_window  # Keep a reference to prevent garbage collection

    @Slot(str)
    def on_log_event(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"{timestamp} - {message}"
        self.history_log.append(log_entry)

    def quit_application(self):
        if self.monitor and self.monitor.isRunning():
            self.monitor.stop()
            self.monitor.wait()
        logging.info("Application quit.")
        self.close()