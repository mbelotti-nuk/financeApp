import sys
import os
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import  QPixmap
import pyqtgraph as pg
from features import PortfolioManager
from utils import apply_stylesheet, SplashScreen

# Configuration
pg.setConfigOption('background', '#FFFFFF')
pg.setConfigOption('foreground', '#1f2937')


def main():
    """Main application entry point"""
    try:
        app = QApplication(sys.argv)
        
        # Get application directory
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Show splash screen if image exists
        splash_path = os.path.join(app_dir, 'splash.png')
        if os.path.exists(splash_path):
            splash = SplashScreen(QPixmap(splash_path))
            splash.show()
            splash.show_message("Applicazione stili...")
        else:
            splash = None
        
        # Apply styles
        apply_stylesheet(app)
        
        if splash:
            splash.show_message("Caricamento dati...")
        
        # Create main window
        window = PortfolioManager()
        
        if splash:
            splash.finish(window)
        
        window.show()
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"Application startup error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

