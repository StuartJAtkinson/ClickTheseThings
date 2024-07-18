import sys
import subprocess
import importlib
import urllib.request
import os

def download_file(url, filename):
    urllib.request.urlretrieve(url, filename)

def install_pip():
    pip_url = "https://bootstrap.pypa.io/get-pip.py"
    pip_installer = "get-pip.py"
    
    print("Downloading pip installer...")
    download_file(pip_url, pip_installer)
    
    print("Installing pip...")
    subprocess.check_call([sys.executable, pip_installer])
    
    print("Cleaning up...")
    os.remove(pip_installer)
    
    print("pip has been installed successfully.")

def check_pip():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "--version"])
        return True
    except subprocess.CalledProcessError:
        return False

def install(package):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    except subprocess.CalledProcessError:
        print(f"Failed to install {package}. Please install it manually.")
        print(f"Run: pip install {package}")
        return False
    return True

# Check if pip is available, if not, install it
if not check_pip():
    print("pip is not available. Installing pip...")
    install_pip()
    if not check_pip():
        print("Failed to install pip. Please install it manually and run the script again.")
        sys.exit(1)

# List of required packages
required_packages = ['pywin32', 'PySide6', 'pyautogui', 'numpy', 'Pillow', 'mss', 'screeninfo', 'opencv-python']

# Check and install missing packages
all_packages_installed = True
for package in required_packages:
    try:
        importlib.import_module(package.split('==')[0])
    except ImportError:
        print(f"Installing {package}...")
        if not install(package):
            all_packages_installed = False

if not all_packages_installed:
    print("Some packages could not be installed. Please install them manually and run the script again.")
    sys.exit(1)

# Now that all packages are installed, we can import them
import time
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, QThread, Signal
import pyautogui
import numpy as np
from PIL import Image
import io
from PySide6.QtCore import QBuffer
import ctypes
import ctypes.wintypes
import mss
from screeninfo import get_monitors
import win32api
import win32con

class ClickerThread(QThread):
    update_signal = Signal(str)
    finished_signal = Signal()  # New signal to indicate thread completion

    def __init__(self, image):
        super().__init__()
        self.image = image
        self.is_running = True

    def run(self):
        while self.is_running:
            self.click_target()
            time.sleep(10)  # Wait for 10 seconds before next click
        self.finished_signal.emit()  # Emit signal when thread is done

    def get_all_screens_screenshot(self):
        with mss.mss() as sct:
            monitors = get_monitors()
            total_width = sum(m.width for m in monitors)
            max_height = max(m.height for m in monitors)
            
            full_screenshot = Image.new('RGB', (total_width, max_height))
            
            offset_x = 0
            for monitor in sct.monitors[1:]:  # Skip the first monitor as it represents the "All in One" virtual screen
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                full_screenshot.paste(img, (offset_x, 0))
                offset_x += monitor['width']
            
            return full_screenshot

    def click_target(self):
        current_x, current_y = pyautogui.position()
        
        self.update_signal.emit("Taking screenshot of all screens...")
        screen = self.get_all_screens_screenshot()

        self.update_signal.emit("Searching for target image...")
        result = pyautogui.locate(self.image, screen)

        if result:
            monitors = get_monitors()
            target_x = result.left
            target_y = result.top
            
            for monitor in monitors:
                if target_x >= monitor.x and target_x < monitor.x + monitor.width and \
                   target_y >= monitor.y and target_y < monitor.y + monitor.height:
                    center_x = monitor.x + (result.left - monitor.x) + result.width // 2
                    center_y = monitor.y + (result.top - monitor.y) + result.height // 2
                    break
            else:
                self.update_signal.emit("Target found but couldn't map to screen coordinates")
                return

            self.update_signal.emit(f"Target found at ({center_x}, {center_y}). Moving and clicking...")
            
            pyautogui.moveTo(center_x, center_y)
            pyautogui.click()
            
            self.update_signal.emit(f"Clicked at ({center_x}, {center_y})")
            
            pyautogui.moveTo(current_x, current_y)
            
            self.update_signal.emit("Restored original cursor position")
        else:
            self.update_signal.emit("Target image not found on screen")
        
        if self.is_running:
            self.update_signal.emit("Waiting for next iteration...")
        else:
            self.update_signal.emit("Stopping...")

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.clicker_thread = None
        self.target_image = None

    def initUI(self):
        self.setWindowTitle('Diablo IV Clicker')
        self.setGeometry(100, 100, 400, 300)

        layout = QVBoxLayout()

        self.image_label = QLabel('Paste image here')
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(200, 200)
        self.image_label.setStyleSheet("border: 2px dashed gray;")
        layout.addWidget(self.image_label)

        button_layout = QHBoxLayout()
        self.toggle_button = QPushButton('Start')
        self.toggle_button.clicked.connect(self.toggle_clicker)
        button_layout.addWidget(self.toggle_button)

        layout.addLayout(button_layout)

        self.status_label = QLabel('Status: Idle')
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def toggle_clicker(self):
        if self.clicker_thread is None or not self.clicker_thread.is_running:
            if self.target_image is None:
                self.status_label.setText('Status: No image pasted')
                return
            self.clicker_thread = ClickerThread(self.target_image)
            self.clicker_thread.update_signal.connect(self.update_status)
            self.clicker_thread.finished_signal.connect(self.on_thread_finish)
            self.clicker_thread.start()
            self.toggle_button.setText('Stop')
            self.status_label.setText('Status: Running')
        else:
            self.clicker_thread.is_running = False
            self.toggle_button.setText('Start')
            self.status_label.setText('Status: Stopping...')

    def on_thread_finish(self):
        self.clicker_thread = None
        self.toggle_button.setText('Start')
        self.status_label.setText('Status: Stopped')

    def closeEvent(self, event):
        if self.clicker_thread and self.clicker_thread.is_running:
            self.clicker_thread.is_running = False
            self.clicker_thread.wait()
        event.accept()

    def update_status(self, message):
        self.status_label.setText(f'Status: {message}')

    def paste_image(self):
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()

        if mime_data.hasImage():
            image = QImage(mime_data.imageData())
            pixmap = QPixmap.fromImage(image)
            self.image_label.setPixmap(pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio))
            
            # Convert QImage to PIL Image
            buffer = QBuffer()
            buffer.open(QBuffer.OpenModeFlag.ReadWrite)
            image.save(buffer, "PNG")
            pil_img = Image.open(io.BytesIO(buffer.data()))
            self.target_image = pil_img
            
            self.status_label.setText('Status: Image pasted')
        else:
            self.status_label.setText('Status: No image in clipboard')

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_V and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.paste_image()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())