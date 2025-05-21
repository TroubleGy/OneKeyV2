from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QRadioButton,
    QButtonGroup, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QObject
from PyQt6.QtGui import QFont, QTextCursor, QColor, QPalette, QMouseEvent, QIcon, QLinearGradient, QPainter, QBrush, QPixmap
import webbrowser
import re
import logging
import asyncio
import threading
import os
import sys # Import sys for stream redirection
import time # Import time for sleep

# Desired fonts (will use system default if not available)
MONTSERRAT_FONT = 'Arial' # Set Montserrat to Arial or another common font
MONOSPACE_FONT = 'Consolas' # Set monospace font directly (e.g., Consolas or Courier New)

class StreamToLog(QObject):
    """Redirects console output to the GUI log area"""
    text_written = pyqtSignal(str)

    def write(self, text):
        self.text_written.emit(str(text))

    def flush(self):
        pass # Needed for file-like object

class GradientFrame(QFrame):
    """Custom frame with gradient background"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                border-radius: 10px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a237e, stop:0.5 #0d47a1, stop:1 #01579b);
            }
        """)

class AsyncWorker(QThread):
    """Worker thread for async operations"""
    finished = pyqtSignal(bool, str, str)  # success, appid, steamdb_url
    request_input = pyqtSignal(str) # Signal to request input from GUI
    input_received = pyqtSignal(str) # Signal to send input back to worker

    def __init__(self, callback, appid, gui, stage):
        super().__init__()
        self.callback = callback
        self.appid = appid
        self.gui = gui
        self.stage = stage
        self.is_running = True
        self._input_response = None
        self._waiting_for_input = threading.Event()
        
        # Connect input_received signal from GUI to worker's handler
        self.input_received.connect(self._handle_input_response)

    def _handle_input_response(self, response):
        self._input_response = response
        self._waiting_for_input.set() # Release the block

    # Override the built-in input function for this thread
    def _blocking_input(self, prompt):
        self.request_input.emit(prompt) # Request input from GUI
        self._waiting_for_input.wait() # Block until GUI provides input
        response = self._input_response
        self._input_response = None # Clear response for next time
        self._waiting_for_input.clear()
        return response

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Temporarily replace built-in input for this thread
        original_input = __builtins__['input']
        __builtins__['input'] = self._blocking_input

        try:
            result = loop.run_until_complete(self.callback(self.appid, self.gui, self.stage))
            if self.is_running:  # Only emit if thread is still running
                self.finished.emit(*result)
        except Exception as e:
            logging.error(f"Error in async worker: {e}")
            if self.is_running:
                self.finished.emit(False, None, None)
        finally:
            loop.close()
            # Restore built-in input
            __builtins__['input'] = original_input

    def stop(self):
        self.is_running = False
        self._waiting_for_input.set() # Release any potential block if stopping
        self.wait()

class ClickableTextEdit(QTextEdit):
    """Custom text edit with clickable links and monospace font"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1a1a1a;
                color: #ffffff;
                border: 1px solid #2d2d2d;
                border-radius: 5px;
                padding: 8px;
                font-family: '{MONOSPACE_FONT}';
                font-size: 12px;
            }}
        """)
        self.setAcceptRichText(True)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse clicks on links"""
        if event.button() == Qt.MouseButton.LeftButton:
            cursor = self.cursorForPosition(event.pos())
            format = cursor.charFormat()
            if format.isAnchor():
                url = format.anchorHref()
                if url:
                    webbrowser.open(url)
        super().mousePressEvent(event)

    def append_html(self, html):
        """Append HTML text"""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(html)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def append_plain_text(self, text):
        """Append plain text"""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

class OneKeyGUI(QMainWindow):
    def __init__(self, start_callback, version):
        super().__init__()
        self.version = version
        self.start_callback = start_callback
        self.steamdb_url = None
        self.workers = []  # Keep track of workers
        
        # Redirect stdout and stderr
        sys.stdout = StreamToLog(self)
        sys.stderr = StreamToLog(self)
        sys.stdout.text_written.connect(self.append_log)
        sys.stderr.text_written.connect(self.append_log_error)

        # Set window icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.setWindowTitle(f"OneKeyV2 v{self.version}")
        self.setMinimumSize(1000, 600)
        self.setup_ui()
        
    def setup_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # Set main window background to transparent
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("QMainWindow { background: transparent; }")

        main_layout = QHBoxLayout(main_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Left panel (main functionality)
        left_panel = GradientFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(15)
        
        # Title
        title = QLabel("OneKeyV2")
        title.setFont(QFont(MONTSERRAT_FONT, 28, QFont.Weight.Bold))
        title.setStyleSheet("color: white; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(title)
        
        # AppID input
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 10px;
            }
        """)
        input_layout = QHBoxLayout(input_frame)
        
        appid_label = QLabel("Enter AppID:")
        appid_label.setFont(QFont(MONTSERRAT_FONT, 12))
        appid_label.setStyleSheet("color: white; background: transparent;")
        self.appid_input = QLineEdit()
        self.appid_input.setPlaceholderText("e.g., 730 for CS2")
        self.appid_input.setFont(QFont(MONTSERRAT_FONT, 12))
        self.appid_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #3d3d3d;
                border-radius: 5px;
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
            }
            QLineEdit:focus {
                border: 1px solid #00a8ff;
            }
        """)
        
        input_layout.addWidget(appid_label)
        input_layout.addWidget(self.appid_input)
        left_layout.addWidget(input_frame)
        
        # Action buttons
        button_frame = QFrame()
        button_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 10px;
            }
        """)
        button_layout = QHBoxLayout(button_frame)
        
        self.view_btn = QPushButton("View")
        self.open_steamdb_btn = QPushButton("Open SteamDB")
        self.start_btn = QPushButton("Start Unlock")
        
        for btn in [self.view_btn, self.open_steamdb_btn, self.start_btn]:
            btn.setFont(QFont(MONTSERRAT_FONT, 12, QFont.Weight.Bold))
            btn.setStyleSheet("""
                QPushButton {
                    padding: 10px 20px;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #0d47a1, stop:1 #01579b);
                    color: white;
                    border: none;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #1565c0, stop:1 #0277bd);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #0a3d91, stop:1 #01579b);
                }
                QPushButton:disabled {
                    background: #424242;
                }
            """)
        
        button_layout.addWidget(self.view_btn)
        button_layout.addWidget(self.open_steamdb_btn)
        button_layout.addWidget(self.start_btn)
        
        self.open_steamdb_btn.hide()
        self.start_btn.hide()
        
        left_layout.addWidget(button_frame)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setFont(QFont(MONTSERRAT_FONT, 10))
        self.status_label.setStyleSheet("color: #4caf50; background: transparent;")
        left_layout.addWidget(self.status_label)
        
        # Input prompt label and buttons
        self.input_prompt_label = QLabel("Input:")
        self.input_prompt_label.setFont(QFont(MONTSERRAT_FONT, 10))
        self.input_prompt_label.setStyleSheet("color: white; background: transparent;")
        self.input_prompt_label.hide()

        self.input_button_frame = QFrame()
        self.input_button_layout = QHBoxLayout(self.input_button_frame)
        self.input_yes_btn = QPushButton("Yes")
        self.input_no_btn = QPushButton("No")
        
        for btn in [self.input_yes_btn, self.input_no_btn]:
            btn.setFont(QFont(MONTSERRAT_FONT, 10, QFont.Weight.Bold))
            btn.setStyleSheet("""
                QPushButton {
                    padding: 5px 10px;
                    background-color: #0d47a1;
                    color: white;
                    border: none;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #1565c0;
                }
                QPushButton:pressed {
                    background-color: #0a3d91;
                }
            """)

        self.input_button_layout.addWidget(self.input_yes_btn)
        self.input_button_layout.addWidget(self.input_no_btn)
        self.input_button_frame.hide()

        left_layout.addWidget(self.input_prompt_label)
        left_layout.addWidget(self.input_button_frame)

        # Log area
        self.log_area = ClickableTextEdit()
        left_layout.addWidget(self.log_area)
        
        # Tool selection
        tool_frame = QFrame()
        tool_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 10px;
            }
        """)
        tool_layout = QHBoxLayout(tool_frame)
        
        tool_label = QLabel("Select tool:")
        tool_label.setFont(QFont(MONTSERRAT_FONT, 12))
        tool_label.setStyleSheet("color: white; background: transparent;")
        
        self.tool_group = QButtonGroup()
        self.steamtools_radio = QRadioButton("SteamTools")
        self.greenluma_radio = QRadioButton("GreenLuma")
        self.steamtools_radio.setChecked(True)
        
        for radio in [self.steamtools_radio, self.greenluma_radio]:
            radio.setFont(QFont(MONTSERRAT_FONT, 12))
            radio.setStyleSheet("""
                QRadioButton {
                    color: white;
                    background: transparent;
                }
                QRadioButton::indicator {
                    width: 18px;
                    height: 18px;
                }
                QRadioButton::indicator:unchecked {
                    border: 2px solid #3d3d3d;
                    border-radius: 9px;
                    background-color: transparent;
                }
                QRadioButton::indicator:checked {
                    border: 2px solid #00a8ff;
                    border-radius: 9px;
                    background-color: #00a8ff;
                }
            """)
            self.tool_group.addButton(radio)
        
        tool_layout.addWidget(tool_label)
        tool_layout.addWidget(self.steamtools_radio)
        tool_layout.addWidget(self.greenluma_radio)
        left_layout.addWidget(tool_frame)
        
        # Right panel (game info)
        right_panel = GradientFrame()
        right_layout = QVBoxLayout(right_panel)
        
        # Game info title
        game_info_title = QLabel("Game Info")
        game_info_title.setFont(QFont(MONTSERRAT_FONT, 20, QFont.Weight.Bold))
        game_info_title.setStyleSheet("color: white; background: transparent;")
        game_info_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(game_info_title)
        
        # Game info container
        self.game_info_container = QFrame()
        self.game_info_container.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid #2d2d2d;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        self.game_info_layout = QVBoxLayout(self.game_info_container)

        self.game_icon_label = QLabel()
        self.game_icon_label.setFixedSize(350, 200)
        self.game_icon_label.setStyleSheet("border-radius: 5px;")
        self.game_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.game_info_layout.addWidget(self.game_icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Game name
        self.game_name_label = QLabel("Game Name: Not specified")
        self.game_name_label.setFont(QFont(MONTSERRAT_FONT, 12))
        self.game_name_label.setStyleSheet("color: white; background: transparent;")
        self.game_info_layout.addWidget(self.game_name_label)
        
        # App ID
        self.app_id_label = QLabel("App ID: Not specified")
        self.app_id_label.setFont(QFont(MONTSERRAT_FONT, 12))
        self.app_id_label.setStyleSheet("color: white; background: transparent;")
        self.game_info_layout.addWidget(self.app_id_label)
        
        # Game developers
        self.game_developers_label = QLabel("Developers: Not specified")
        self.game_developers_label.setFont(QFont(MONTSERRAT_FONT, 12))
        self.game_developers_label.setStyleSheet("color: white; background: transparent;")
        self.game_info_layout.addWidget(self.game_developers_label)
        
        # Game publishers
        self.game_publishers_label = QLabel("Publishers: Not specified")
        self.game_publishers_label.setFont(QFont(MONTSERRAT_FONT, 12))
        self.game_publishers_label.setStyleSheet("color: white; background: transparent;")
        self.game_info_layout.addWidget(self.game_publishers_label)
        
        right_layout.addWidget(self.game_info_container)
        right_layout.addStretch()
        
        # Add panels to main layout
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 1)
        
        # Connect signals
        self.view_btn.clicked.connect(self.on_view)
        self.open_steamdb_btn.clicked.connect(self.on_open_steamdb)
        self.start_btn.clicked.connect(self.on_start_unlock)

        # Connect input buttons
        self.input_yes_btn.clicked.connect(lambda: self.send_input('y'))
        self.input_no_btn.clicked.connect(lambda: self.send_input('n'))

    def append_log(self, text):
        """Append text to the log area"""
        self.log_area.append_plain_text(text)

    def append_log_error(self, text):
        """Append error text to the log area (optional: color differently)"""
        self.log_area.append_plain_text(text) # For now, same as normal log

    def request_worker_input(self, prompt):
        """Show input prompt and buttons for the worker"""
        self.input_prompt_label.setText(prompt)
        self.input_prompt_label.show()
        self.input_button_frame.show()
        # You might want to disable other buttons here
        self.view_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.open_steamdb_btn.setEnabled(False)

    def send_input(self, response):
        """Send input from GUI back to the worker"""
        # Find the worker that requested input (assuming only one at a time)
        worker_to_notify = next((w for w in self.workers if w.isRunning()), None)
        if worker_to_notify:
            worker_to_notify.input_received.emit(response)

        # Hide input prompt and buttons
        self.input_prompt_label.hide()
        self.input_button_frame.hide()

        # Re-enable buttons as appropriate (depends on the stage/state)
        # This logic might need refinement based on context after input
        self.view_btn.setEnabled(True)
        # Start and Open SteamDB buttons state depend on handle_view_result/handle_unlock_result
        # so we don't re-enable them here directly

    def closeEvent(self, event):
        """Handle window close event"""
        # Restore stdout and stderr
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

        # Stop all running workers
        for worker in self.workers:
            worker.stop()
        event.accept()

    def set_game_info(self, info: dict):
        """Update game information in the right panel"""
        if "Game Name" in info:
            self.game_name_label.setText(f"Game Name: {info['Game Name']}")
        if "App ID" in info:
            self.app_id_label.setText(f"App ID: {info['App ID']}")
        if "Developers" in info:
            # Join the list of developers into a single string
            developers_str = ", ".join(info['Developers'])
            self.game_developers_label.setText(f"Developers: {developers_str}")
        if "Publishers" in info:
            # Join the list of publishers into a single string
            publishers_str = ", ".join(info['Publishers'])
            self.game_publishers_label.setText(f"Publishers: {publishers_str}")
            
        # Set game icon
        if "IconData" in info and info["IconData"]:
            pixmap = QPixmap()
            if pixmap.loadFromData(info["IconData"]):
                # Масштабируем иконку, чтобы заполнить весь прямоугольник
                self.game_icon_label.setPixmap(pixmap.scaled(self.game_icon_label.size(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                self.game_icon_label.clear() # Clear if loading fails
        else:
            self.game_icon_label.clear() # Clear if no icon data

    def clear_game_info(self):
        """Clear game information"""
        self.game_name_label.setText("Game Name: Not specified")
        self.app_id_label.setText("App ID: Not specified")
        self.game_developers_label.setText("Developers: Not specified")
        self.game_publishers_label.setText("Publishers: Not specified")
        
    def on_view(self):
        appid = self.appid_input.text().strip()
        if not appid:
            self.set_status("Please enter AppID!", error=True)
            return
            
        self.set_status("Fetching game info...", error=False)
        self.log_area.clear()
        self.view_btn.setEnabled(False)
        self.hide_start_button()
        self.hide_open_steamdb_button()
        
        worker = AsyncWorker(self.start_callback, appid, self, "view")
        self.workers.append(worker)  # Add to workers list
        worker.finished.connect(self.handle_view_result)
        # Connect worker's input request to GUI slot
        worker.request_input.connect(self.request_worker_input)
        worker.start()
        
    def on_start_unlock(self):
        appid = self.appid_input.text().strip()
        if not appid:
            self.set_status("Please enter AppID!", error=True)
            return
            
        self.set_status("Starting unlock process...", error=False)
        self.start_btn.setEnabled(False)
        self.view_btn.setEnabled(False)
        self.hide_open_steamdb_button()
        
        worker = AsyncWorker(self.start_callback, appid, self, "unlock")
        self.workers.append(worker)  # Add to workers list
        worker.finished.connect(self.handle_unlock_result)
        # Connect worker's input request to GUI slot
        worker.request_input.connect(self.request_worker_input)
        worker.start()
        
    def on_open_steamdb(self):
        if self.steamdb_url:
            webbrowser.open(self.steamdb_url)
        else:
            self.set_status("SteamDB URL not available!", error=True)
            
    def handle_view_result(self, success, appid, steamdb_url):
        self.view_btn.setEnabled(True)
        # Ensure buttons are re-enabled after input if it happened
        self.input_prompt_label.hide()
        self.input_button_frame.hide()

        if success:
            self.show_start_button()
            if steamdb_url:
                self.steamdb_url = steamdb_url
                self.show_open_steamdb_button()
            else:
                self.hide_open_steamdb_button()
        else:
            self.hide_start_button()
            self.hide_open_steamdb_button()
            
    def handle_unlock_result(self, success, appid, steamdb_url):
        self.view_btn.setEnabled(True)
        # Ensure buttons are re-enabled after input if it happened
        self.input_prompt_label.hide()
        self.input_button_frame.hide()

        self.hide_start_button()
        self.hide_open_steamdb_button()
        
    def set_status(self, text, error=False):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {'#f44336' if error else '#4caf50'}; background: transparent;"
        )
        
    # This log method is no longer used for writing to the log_area directly
    # The StreamToLog class and append_log methods handle writing now.
    # Keeping it here for compatibility with GuiLogger, but it will effectively do nothing.
    def log(self, text):
        # The GuiLogger will call this, but the actual appending is done by StreamToLog
        pass

    def get_tool_choice(self):
        return 1 if self.steamtools_radio.isChecked() else 2
        
    def show_start_button(self):
        self.start_btn.show()
        
    def hide_start_button(self):
        self.start_btn.hide()
        
    def show_open_steamdb_button(self):
        self.open_steamdb_btn.show()
        
    def hide_open_steamdb_button(self):
        self.open_steamdb_btn.hide()