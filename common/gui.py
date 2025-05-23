from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QRadioButton,
    QButtonGroup, QFrame, QSizePolicy, QDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QObject
from PyQt6.QtGui import QFont, QTextCursor, QColor, QPalette, QMouseEvent, QIcon, QLinearGradient, QPainter, QBrush, QPixmap, QFontDatabase
import webbrowser
import re
import logging
import asyncio
import threading
import os
import sys # Import sys for stream redirection
import time # Import time for sleep
import httpx # Import httpx here
import ujson as json # Import json for config file handling
from pathlib import Path # Import Path

# Desired fonts
# Keep these names for internal reference if needed, but use 'Montserrat' in QSS
MONTSERRAT_REGULAR_NAME = 'Montserrat-Regular'
MONTSERRAT_BOLD_NAME = 'Montserrat-Bold'
MONOSPACE_FONT = 'Consolas' # Set monospace font directly (e.g., Consolas or Courier New)

# Global Stylesheet (QSS) for the dark theme
GLOBAL_QSS = """
QMainWindow, QDialog {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1f232a, stop:1 #1a1e24); /* Subtle dark gradient background */
    color: #e0e0e0; /* Brighter light grey text */
    font-family: 'Montserrat';
    font-size: 12px;
}

QWidget#centralwidget {
    background: transparent;
}

QWidget {
     background-color: transparent;
}

QLabel {
    color: #e0e0e0; /* Apply brighter text color to labels */
    background: transparent;
}

QLineEdit {
    padding: 8px;
    border: 1px solid #3e4451; /* Darker border */
    border-radius: 5px;
    background-color: #282c34; /* Slightly lighter dark for input */
    color: #abb2bf;
    selection-background-color: #61afef; /* Blue selection */
}

QLineEdit:focus {
    border: 1px solid #61afef; /* Blue accent on focus */
    background-color: #3e4451; /* Slightly lighter on focus */
}

QPushButton {
    padding: 10px 20px;
    background-color: #3e4451; /* Default button dark background */
    color: #abb2bf;
    border: none;
    border-radius: 5px;
    font-weight: normal;
    min-width: 80px;
    outline: none; /* Remove focus outline */
}

QPushButton:hover {
    background-color: #525a66; /* Lighter grey on hover */
    color: #ffffff; /* White text on hover */
}

QPushButton:pressed {
     background-color: #3e4451; /* Darker grey on pressed */
    color: #abb2bf;
}

QPushButton:disabled {
    background-color: #282c34; /* Darker background for disabled */
    color: #616161; /* Grey out text */
    border: 1px solid #3e4451;
}

/* Specific style for the primary action buttons (View, Start Unlock) */
QPushButton#view_btn,
QPushButton#start_btn {
    background-color: #61afef; /* Blue background for primary buttons */
    color: white;
    font-weight: bold;
}

QPushButton#view_btn:hover,
QPushButton#start_btn:hover {
    background-color: #67b8ff;
}

QPushButton#view_btn:pressed,
QPushButton#start_btn:pressed {
     background-color: #519cd9;
}

/* Specific style for the secondary button (Open SteamDB) */
QPushButton#open_steamdb_btn {
    background-color: #3a475e; /* Slightly darker blue-grey background */
    color: #ffffff; /* White text */
    font-weight: normal;
}

QPushButton#open_steamdb_btn:hover {
    background-color: #4a5d7b;
}

QPushButton#open_steamdb_btn:pressed {
    background-color: #3a475e;
}

QRadioButton {
    color: #abb2bf;
    spacing: 5px;
}

QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 2px solid #3e4451; /* Dark grey border */
    background-color: transparent;
}

QRadioButton::indicator:checked {
    border: 2px solid #61afef; /* Blue border when checked */
    background-color: #61afef; /* Blue fill when checked */
}

QFrame {
    background-color: transparent;
    border: none;
}

/* Style for container frames */
QFrame#input_frame,
QFrame#button_frame,
QFrame#tool_frame,
QFrame#game_info_container {
    background-color: #282c34; /* Slightly lighter dark grey background for frames */
    border-radius: 8px;
    padding: 15px;
    border: 1px solid #3e4451; /* Subtle border for frames */
}

/* Specific style for the title label */
QLabel#title_label {
    font-family: 'Montserrat';
    font-size: 30px;
    font-weight: bold;
    color: #ffffff; /* White color for title */
    qproperty-alignment: 'AlignCenter';
    margin-bottom: 15px; /* Increased space below title */
}

/* Style for status label */
QLabel#status_label {
    font-size: 11px;
    /* Color set by set_status method (which uses #4caf50 for success and #f44336 for error) */
    margin-top: 10px;
}

/* Style for game info labels (look like input fields) */
QLabel#game_name_label,
QLabel#app_id_label,
QLabel#game_developers_label,
QLabel#game_publishers_label {
    font-size: 12px;
    color: #abb2bf;
    background-color: #282c34;
    border: 1px solid #3e4451;
    border-radius: 5px;
    padding: 8px;
    margin-bottom: 8px;
    qproperty-alignment: 'AlignLeft | AlignVCenter';
}

QLabel#game_name_label::disabled,
QLabel#app_id_label::disabled,
QLabel#game_developers_label::disabled,
QLabel#game_publishers_label::disabled {
    color: #616161; /* Dim text when info is not available */
}

/* Style for the Game Info title */
QLabel#game_info_title {
     font-family: 'Montserrat';
     font-size: 20px;
     font-weight: bold;
     color: #ffffff; /* White color for title */
     qproperty-alignment: 'AlignCenter';
     margin-bottom: 10px;
}

"""

# Register custom fonts
def register_fonts():
    fonts_dir = Path(__file__).parent.parent / "fonts"
    logging.info(f"Attempting to load fonts from: {fonts_dir.resolve()}")
    if fonts_dir.exists():
        for font_file in fonts_dir.glob("*.ttf"):
            font_id = QFontDatabase.addApplicationFont(str(font_file))
            if font_id == -1:
                logging.warning(f"Failed to load font: {font_file.name}")
            else:
                font_family = QFontDatabase.applicationFontFamilies(font_id)
                if font_family:
                     logging.info(f"Successfully loaded font: {font_file.name} ({font_family[0]})")
                else:
                     logging.info(f"Successfully loaded font: {font_file.name} (Family name not available)")

    # Check if Montserrat family is available globally after loading
    available_families = QFontDatabase.families()
    if 'Montserrat' not in available_families:
        logging.warning(f"Font family 'Montserrat' not found in available fonts.")
    else:
        logging.info(f"Font family 'Montserrat' is available.")

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
        # Use a subtle dark background for the frame
        self.setStyleSheet("""
            QFrame {
                border-radius: 10px;
                background-color: #282c34; /* Match other container frames */
                border: 1px solid #3e4451; /* Subtle border */
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

        # Create httpx client within this thread's event loop
        client = httpx.AsyncClient()

        try:
            # Pass the client to the callback function
            result = loop.run_until_complete(self.callback(self.appid, self.gui, self.stage, client))
            if self.is_running:  # Only emit if thread is still running
                self.finished.emit(*result)
        except Exception as e:
            logging.error(f"Error in async worker: {e}")
            if self.is_running:
                self.finished.emit(False, None, None)
        finally:
            # Close the client when the loop finishes
            loop.run_until_complete(client.aclose())
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
        # Updated stylesheet for dark theme and monospace font
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: #21252b; /* Dark background for log */
                color: #abb2bf; /* Light grey text */
                border: 1px solid #3d3d3d; /* Darker border */
                border-radius: 5px;
                padding: 8px;
                font-family: '{MONOSPACE_FONT}'; /* Keep monospace */
                font-size: 12px;
                selection-background-color: #61afef; /* Blue selection */
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

class ConfigWindow(QDialog):
    """Window for initial configuration."""
    config_saved = pyqtSignal(dict) # Signal to emit the saved config

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration Required")
        self.setModal(True) # Make it a modal dialog
        self.setFixedSize(400, 250) # Slightly increased height for better spacing

        # Apply global stylesheet to the config window
        # self.setStyleSheet(GLOBAL_QSS)

        layout = QVBoxLayout()
        layout.setSpacing(15) # Increased spacing
        layout.setContentsMargins(20, 20, 20, 20) # Increased margins

        info_label = QLabel("Please configure the required settings:")
        # Font and style applied by QSS
        layout.addWidget(info_label)

        # GitHub Token Input
        github_layout = QVBoxLayout()
        github_label = QLabel("GitHub Token:")
        # Font and style applied by QSS
        github_layout.addWidget(github_label)
        self.github_token_input = QLineEdit()
        self.github_token_input.setPlaceholderText("Optional, but recommended")
        # Font and style applied by QSS
        github_layout.addWidget(self.github_token_input)
        layout.addLayout(github_layout)

        # Custom Steam Path Input
        steam_path_layout = QVBoxLayout()
        steam_path_label = QLabel("Steam Path:")
        # Font and style applied by QSS
        steam_path_layout.addWidget(steam_path_label)
        self.steam_path_input = QLineEdit()
        self.steam_path_input.setPlaceholderText("Leave empty for default")
        # Font and style applied by QSS
        steam_path_layout.addWidget(self.steam_path_input)
        layout.addLayout(steam_path_layout)

        # Buttons
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save")
        self.cancel_button = QPushButton("Cancel")

        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Connect signals
        self.save_button.clicked.connect(self.save_config)
        self.cancel_button.clicked.connect(self.reject)

    def save_config(self):
        """Saves the configuration to config.json."""
        config_path = Path("./config.json")

        # Start with default config and update with user input
        config_data = {
            "Github_Personal_Token": self.github_token_input.text().strip(),
            "Custom_Steam_Path": self.steam_path_input.text().strip(),
            "Debug_Mode": False,
            "Logging_Files": True,
            "Auto_Update": {
                "Enabled": True,
                "Check_Interval": 24
            },
            "Help with GitHub Personal Token": "GitHub Personal Token can be generated in GitHub Settings under Developer settings.",
            "Help with Custom Steam path": "Use \\\\ in path. For example: 'C:\\\\Program Files (x86)\\\\Steam'"
        }

        try:
            with config_path.open("w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            logging.info("config.json saved successfully.")
            self.config_saved.emit(config_data) # Emit the saved config
            self.accept() # accept closes the dialog and sets result to Accepted
        except IOError as e:
            logging.error(f"Failed to save config file: {str(e)}")
            # Optionally show a message box to the user about the error

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
        # self.setStyleSheet(GLOBAL_QSS)

        main_layout = QHBoxLayout(main_widget)
        main_layout.setSpacing(25) # Увеличил spacing между левой и правой панелями
        main_layout.setContentsMargins(25, 25, 25, 25) # Увеличил общие margins
        
        # Left panel (main functionality)
        left_panel = GradientFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(20) # Увеличил spacing внутри левой панели
        left_layout.setContentsMargins(20, 20, 20, 20) # Добавил margins к левой панели
        
        # Title
        title = QLabel("OneKeyV2")
        title.setObjectName("title_label") # Set object name for specific styling
        # Font applied by QSS
        # title.setFont(QFont(MONTSERRAT_BOLD if QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family() != MONTSERRAT_BOLD else 'Arial', 28, QFont.Weight.Bold))
        # Style applied by QSS or specific widget style
        # title.setStyleSheet("color: white; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(title)
        
        # AppID input
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.05); /* Slightly transparent dark */
                border-radius: 8px;
                padding: 15px; /* Increased padding */
            }
        """)
        input_layout = QHBoxLayout(input_frame)
        
        appid_label = QLabel("Enter AppID:")
        # Font and style applied by QSS
        # appid_label.setFont(QFont(MONTSERRAT_REGULAR if QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family() != MONTSERRAT_REGULAR else 'Arial', 12))
        # appid_label.setStyleSheet("color: white; background: transparent;");

        self.appid_input = QLineEdit()
        self.appid_input.setPlaceholderText("e.g., 730 for CS2")
        # Font and style applied by QSS
        # self.appid_input.setFont(QFont(MONTSERRAT_REGULAR if QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family() != MONTSERRAT_REGULAR else 'Arial', 12))
        # self.appid_input.setStyleSheet("""
        #     QLineEdit {
        #         padding: 8px;
        #         border: 1px solid #3d3d3d;
        #         border-radius: 5px;
        #         background-color: rgba(255, 255, 255, 0.1);
        #         color: white;
        #     }
        #     QLineEdit:focus {
        #         border: 1px solid #00a8ff;
        #     }
        # """)
        
        input_layout.addWidget(appid_label)
        input_layout.addWidget(self.appid_input)
        left_layout.addWidget(input_frame)
        
        # Action buttons
        button_frame = QFrame()
        button_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.05); /* Slightly transparent dark */
                border-radius: 8px;
                padding: 15px; /* Increased padding */
            }
        """)
        button_layout = QHBoxLayout(button_frame)
        
        self.view_btn = QPushButton("View")
        self.open_steamdb_btn = QPushButton("Open SteamDB")
        self.start_btn = QPushButton("Start Unlock")
        
        # Set object names for buttons to apply specific styles
        self.view_btn.setObjectName("view_btn")
        self.open_steamdb_btn.setObjectName("open_steamdb_btn")
        self.start_btn.setObjectName("start_btn")

        # Button styles applied by global QSS
        # Ensure disabled style is not too dominant
        # We can adjust the global QSS disabled style or apply a specific style here if needed.
        # For now, rely on global QSS.

        button_layout.addWidget(self.view_btn)
        button_layout.addWidget(self.open_steamdb_btn)
        button_layout.addWidget(self.start_btn)
        
        self.start_btn.hide()
        self.open_steamdb_btn.hide()
        
        left_layout.addWidget(button_frame)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("status_label") # Set object name
        # Font and style applied by QSS
        # self.status_label.setFont(QFont(MONTSERRAT_REGULAR if QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family() != MONTSERRAT_REGULAR else 'Arial', 10))
        # self.status_label.setStyleSheet("color: #4caf50; background: transparent;")
        left_layout.addWidget(self.status_label)
        
        # Input prompt label and buttons
        self.input_prompt_label = QLabel("Input:")
        # Font and style applied by QSS
        # self.input_prompt_label.setFont(QFont(MONTSERRAT_REGULAR if QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family() != MONTSERRAT_REGULAR else 'Arial', 10))
        # self.input_prompt_label.setStyleSheet("color: white; background: transparent;")
        self.input_prompt_label.hide()

        self.input_button_frame = QFrame()
        self.input_button_layout = QHBoxLayout(self.input_button_frame)
        self.input_yes_btn = QPushButton("Yes")
        self.input_no_btn = QPushButton("No")
        
        # Button styles applied by global QSS
        # for btn in [self.input_yes_btn, self.input_no_btn]:
        #     btn.setFont(QFont(MONTSERRAT_BOLD if QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family() != MONTSERRAT_BOLD else 'Arial', 10, QFont.Weight.Bold))
        #     btn.setStyleSheet("""
        #         QPushButton {
        #             padding: 5px 10px;
        #             background-color: #0d47a1;
        #             color: white;
        #             border: none;
        #             border-radius: 3px;
        #         }
        #         QPushButton:hover {
        #             background-color: #1565c0;
        #         }
        #         QPushButton:pressed {
        #             background-color: #0a3d91;
        #         }
        #     "")

        self.input_button_layout.addWidget(self.input_yes_btn)
        self.input_button_layout.addWidget(self.input_no_btn)
        self.input_button_frame.hide()

        left_layout.addWidget(self.input_prompt_label)
        left_layout.addWidget(self.input_button_frame)

        # Tool selection
        tool_frame = QFrame()
        tool_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.05); /* Slightly transparent dark */
                border-radius: 8px;
                padding: 15px; /* Increased padding */
            }
        """)
        tool_layout = QHBoxLayout(tool_frame)
        
        tool_label = QLabel("Select tool:")
        # Font and style applied by QSS
        # tool_label.setFont(QFont(MONTSERRAT_REGULAR if QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family() != MONTSERRAT_REGULAR else 'Arial', 12))
        # tool_label.setStyleSheet("color: white; background: transparent;")
        
        self.tool_group = QButtonGroup()
        self.steamtools_radio = QRadioButton("SteamTools")
        self.greenluma_radio = QRadioButton("GreenLuma")
        self.steamtools_radio.setChecked(True)
        self.steamtools_radio.setObjectName("steamtools_radio")
        self.greenluma_radio.setObjectName("greenluma_radio")

        self.tool_group.addButton(self.steamtools_radio)
        self.tool_group.addButton(self.greenluma_radio)

        tool_layout.addWidget(tool_label)
        tool_layout.addWidget(self.steamtools_radio)
        tool_layout.addWidget(self.greenluma_radio)
        left_layout.addWidget(tool_frame)
        
        # Right panel (game info)
        right_panel = GradientFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(15) # Увеличил spacing внутри правой панели
        right_layout.setContentsMargins(20, 20, 20, 20) # Добавил margins к правой панели
        
        # Game info title
        game_info_title = QLabel("Game Info")
        # Font and style applied by QSS
        # game_info_title.setFont(QFont(MONTSERRAT_BOLD if QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family() != MONTSERRAT_BOLD else 'Arial', 20, QFont.Weight.Bold))
        # game_info_title.setStyleSheet("color: white; background: transparent;")
        game_info_title.setObjectName("game_info_title") # Set object name
        game_info_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(game_info_title)
        
        # Game info container
        self.game_info_container = QFrame()
        self.game_info_container.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.05); /* Slightly transparent dark */
                border: 1px solid #3d3d3d; /* Darker border */
                border-radius: 8px;
                padding: 15px; /* Increased padding */
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
        self.game_name_label.setObjectName("game_name_label") # Set object name
        # Font and style applied by QSS
        # self.game_name_label.setFont(QFont(MONTSERRAT_REGULAR if QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family() != MONTSERRAT_REGULAR else 'Arial', 12))
        # self.game_name_label.setStyleSheet("color: white; background: transparent;")
        self.game_info_layout.addWidget(self.game_name_label)
        
        # App ID
        self.app_id_label = QLabel("App ID: Not specified")
        self.app_id_label.setObjectName("app_id_label") # Set object name
        # Font and style applied by QSS
        # self.app_id_label.setFont(QFont(MONTSERRAT_REGULAR if QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family() != MONTSERRAT_REGULAR else 'Arial', 12))
        # self.app_id_label.setStyleSheet("color: white; background: transparent;")
        self.game_info_layout.addWidget(self.app_id_label)
        
        # Game developers
        self.game_developers_label = QLabel("Developers: Not specified")
        self.game_developers_label.setObjectName("game_developers_label") # Set object name
        # Font and style applied by QSS
        # self.game_developers_label.setFont(QFont(MONTSERRAT_REGULAR if QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family() != MONTSERRAT_REGULAR else 'Arial', 12))
        # self.game_developers_label.setStyleSheet("color: white; background: transparent;")
        self.game_info_layout.addWidget(self.game_developers_label)
        
        # Game publishers
        self.game_publishers_label = QLabel("Publishers: Not specified")
        self.game_publishers_label.setObjectName("game_publishers_label") # Set object name
        # Font and style applied by QSS
        # self.game_publishers_label.setFont(QFont(MONTSERRAT_REGULAR if QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family() != MONTSERRAT_REGULAR else 'Arial', 12))
        # self.game_publishers_label.setStyleSheet("color: white; background: transparent;")
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
        # Disable all action buttons at the start of an operation
        self.view_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.open_steamdb_btn.setEnabled(False)

        # Hide Start Unlock and Open SteamDB buttons initially for new view
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
        # Disable all action buttons at the start of an operation
        self.view_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.open_steamdb_btn.setEnabled(False)
        
        worker = AsyncWorker(self.start_callback, appid, self, "unlock")
        self.workers.append(worker)
        worker.finished.connect(self.handle_unlock_result)
        worker.request_input.connect(self.request_worker_input)
        worker.start()
        
    def handle_view_result(self, success, appid, steamdb_url):
        # Enable View button after operation finishes
        self.view_btn.setEnabled(True)

        # Ensure buttons are re-enabled after input if it happened
        self.input_prompt_label.hide()
        self.input_button_frame.hide()

        if success:
            # If view is successful, show and enable Start Unlock and Open SteamDB buttons
            self.show_start_button()
            self.start_btn.setEnabled(True)
            if steamdb_url: # Only show and enable Open SteamDB if URL is available
                 self.steamdb_url = steamdb_url # Store URL
                 self.show_open_steamdb_button()
                 self.open_steamdb_btn.setEnabled(True)
            else:
                 self.hide_open_steamdb_button()
                 self.open_steamdb_btn.setEnabled(False)

        else:
            # If view failed, hide and disable Start Unlock and Open SteamDB buttons
            self.hide_start_button()
            self.start_btn.setEnabled(False)
            self.hide_open_steamdb_button()
            self.open_steamdb_btn.setEnabled(False)

    def handle_unlock_result(self, success, appid, steamdb_url):
        # Enable View button after operation finishes
        self.view_btn.setEnabled(True)

        # Ensure buttons are re-enabled after input if it happened
        self.input_prompt_label.hide()
        self.input_button_frame.hide()

        # After unlock, the user might want to view another game.
        # Hide Start Unlock and Open SteamDB buttons and rely on a new View operation
        # to make them visible/enabled again.
        self.hide_start_button()
        self.start_btn.setEnabled(False)
        self.hide_open_steamdb_button()
        self.open_steamdb_btn.setEnabled(False)

        # If you wanted Start Unlock to be available immediately after unlock for the *same* game:
        # self.show_start_button()
        # self.start_btn.setEnabled(True)
        # self.hide_open_steamdb_button() # Keep Open SteamDB hidden after unlock

    def set_status(self, text, error=False):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {'#f44336' if error else '#4caf50'}; background: transparent;"
        )
        
    def get_tool_choice(self):
        return 1 if self.steamtools_radio.isChecked() else 2
        
    def show_start_button(self):
        self.start_btn.show()
        
    def hide_start_button(self):
        self.start_btn.hide()

    # Return the methods for showing/hiding Open SteamDB button
    def show_open_steamdb_button(self):
        self.open_steamdb_btn.show()

    def hide_open_steamdb_button(self):
        self.open_steamdb_btn.hide()

    # Return the method for Open SteamDB button click
    def on_open_steamdb(self):
        if self.steamdb_url:
            webbrowser.open(self.steamdb_url)
        else:
            self.set_status("SteamDB URL not available!", error=True)