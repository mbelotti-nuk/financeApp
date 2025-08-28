import yfinance as yf
import pandas as pd
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from datetime import datetime, timedelta
from ecbdata import ecbdata
import pytz

ROME_TZ = pytz.timezone('Europe/Rome')
INFLATION_RATE_ANNUAL = 0.02

def apply_stylesheet(app):
    """Apply consistent styling across the application with larger text"""
    app.setStyleSheet("""
        QWidget { 
            background-color: #FFFFFF; 
            color: #1f2937; 
            font-family: 'Segoe UI', Arial, sans-serif; 
            font-size: 15px; 
        }
        QLineEdit, QSpinBox, QDateTimeEdit, QDoubleSpinBox {
            background-color: #FFFFFF; 
            border: 1px solid #E5E7EB; 
            border-radius: 10px; 
            padding: 10px 12px; 
            font-size: 15px; 
            min-height: 20px;
        }
        QLineEdit:focus, QSpinBox:focus, QDateTimeEdit:focus, QDoubleSpinBox:focus { 
            border: 1px solid #3B82F6; 
        }
        QPushButton { 
            background-color: #3B82F6; 
            color: #FFFFFF; 
            border: none; 
            border-radius: 10px; 
            padding: 12px 16px; 
            font-weight: 600; 
            font-size: 15px; 
            min-height: 15px;
        }
        QPushButton:hover { background-color: #2563EB; }
        QPushButton:pressed { background-color: #1D4ED8; }
        QPushButton[objectName="delete_button"] {
            background-color: #EF4444;
            border-radius: 6px;
            font-size: 14px;
            min-width: 90px;
            min-height: 35px;
            padding: 0px 0px;
        }
        QPushButton[objectName="delete_button"]:hover { background-color: #DC2626; }
        QWidget[objectName="sidebar"] { 
            background-color: #F3F4F6; 
            border-right: 1px solid #E5E7EB; 
        }
        QWidget[objectName="sidebar"] QPushButton { 
            background: transparent; 
            color: #111827; 
            text-align: left; 
            padding: 14px 16px; 
            border-radius: 10px; 
            font-weight: 600; 
            font-size: 15px;
            min-height: 25px;
        }
        QWidget[objectName="sidebar"] QPushButton:hover { background: #E0E7FF; }
        QListWidget { 
            background: #FFFFFF; 
            border: none; 
            padding: 8px; 
            font-size: 15px;
        }
        QListWidget[objectName="transactions_list_widget"] {
            border-radius: 12px;
            border: 1px solid #E5E7EB;
        }
        QListWidget::item { 
            outline: none; 
            padding: 8px;
            min-height: 30px;
        }
        QListWidget::item:selected { 
            background-color: #E0E7FF; 
            border-radius: 12px; 
        }
        QTableView {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 10px;
            gridline-color: #E5E7EB;
            padding: 12px; 
            font-size: 15px;
        }
        QHeaderView::section {
            background-color: #F9FAFB;
            color: #1f2937;
            padding: 12px;
            border-bottom: 1px solid #E5E7EB;
            font-size: 15px;
            font-weight: bold;
            min-height: 25px;
        }
        QLabel {
            font-size: 15px;
        }
        QCheckBox {
            font-size: 17px;
            spacing: 8px;
        }
        QCheckBox::indicator {
            width: 20px;
            height: 20px;
        }
    """)

class SplashScreen(QSplashScreen):
    """Splash screen for application startup"""
    def __init__(self, pixmap):
        super().__init__(pixmap)
        self.message_label = QLabel("Caricamento in corso...")
        self.message_label.setStyleSheet(
            "color: white; font-size: 16px; font-weight: bold; background: transparent;"
        )
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(self.message_label)
        layout.addSpacing(20)

    def show_message(self, message):
        self.message_label.setText(message)
        QCoreApplication.processEvents()

def get_eur_usd_rate():
    """Get current EUR/USD exchange rate"""
    try:
        data = yf.Ticker("EURUSD=X").history(period="5d")
        return float(data.iloc[-1]['Close']) if not data.empty else 1.1
    except Exception as e:
        print(f"EURUSD error: {e}")
        return 1.1

def infer_price_eur_if_missing(ticker: str, when_dt_utc: datetime) -> float:
    """Infer EUR price for a stock if missing"""
    try:
        when = when_dt_utc.date()
        hist = yf.Ticker(ticker).history(
            start=when - timedelta(days=3), 
            end=when + timedelta(days=4)
        )
        if hist.empty:
            hist = yf.Ticker(ticker).history(period="5d")
        
        if not hist.empty:
            eurusd = get_eur_usd_rate()
            return float(hist.iloc[-1]['Close']) / max(eurusd, 1e-9)
    except Exception as e:
        print(f"Infer price error: {e}")
    return 0.0

def get_inflation_rate_annual(start_date, end_date):
    """Get inflation data from ECB"""
    try:
        inflation_code = 'ICP.M.U2.N.000000.4.ANR'
        infl_df = ecbdata.get_series(
            inflation_code,
            start=start_date.strftime('%Y-%m'),
            end=end_date.strftime('%Y-%m'),
        )
        
        infl_df["TIME_PERIOD"] = pd.to_datetime(infl_df["TIME_PERIOD"])
        infl_df["YEAR"] = infl_df["TIME_PERIOD"].dt.year
        annual_infl = infl_df.groupby("YEAR")["OBS_VALUE"].mean() / 100.0
        
        infl_df_daily = pd.Series(100.0, index=pd.date_range(start_date, end_date, freq='D'))
        inflation_rate_daily = (1 + annual_infl)**(1/365) - 1
        
        for i in range(1, len(infl_df_daily)):
            rate = inflation_rate_daily[infl_df_daily.index[i].year]
            infl_df_daily.iloc[i] = infl_df_daily.iloc[i-1] * (1 + rate)
        
        return infl_df_daily, annual_infl
        
    except Exception as e:
        print(f"Inflation data error: {e}")
        # Fallback with fixed inflation
        rate_daily = (1 + INFLATION_RATE_ANNUAL)**(1/365) - 1
        infl_df_daily = pd.Series(100.0, index=pd.date_range(start_date, end_date, freq='D'))
        for i in range(1, len(infl_df_daily)):
            infl_df_daily.iloc[i] = infl_df_daily.iloc[i-1] * (1 + rate_daily)
        return infl_df_daily, pd.Series([INFLATION_RATE_ANNUAL])
