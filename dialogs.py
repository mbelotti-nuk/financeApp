import yfinance as yf
import requests
import urllib.parse
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
import pytz
from datetime import timedelta
from utils import ROME_TZ, get_eur_usd_rate, infer_price_eur_if_missing


class TransactionDialog(QDialog):
    """Dialog for adding new transactions"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aggiungi Transazione")
        self.resize(450, 400)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QGridLayout()
        
        # Form fields
        self.ticker_input = QLineEdit()
        self.shares_input = QSpinBox()
        self.shares_input.setRange(1, 1_000_000)
        self.shares_input.setValue(1)
        
        self.time_input = QDateTimeEdit()
        self.time_input.setCalendarPopup(True)
        self.time_input.setDateTime(QDateTime.currentDateTime())
        
        # Market price display (read-only)
        self.market_price_label = QLabel("Prezzo di Mercato (EUR): €0.00")
        self.market_price_label.setStyleSheet("color: #6B7280; font-style: italic;")
        
        # Custom price input
        self.custom_price_input = QDoubleSpinBox()
        self.custom_price_input.setRange(0.0001, 999999.99)
        self.custom_price_input.setDecimals(4)
        self.custom_price_input.setSingleStep(0.1)
        self.custom_price_input.setValue(0.000)
        self.custom_price_input.setSpecialValueText("Usa prezzo di mercato")
        
        self.search_button = QPushButton("Cerca Titolo")
        self.submit_button = QPushButton("Aggiungi")
        
        # Layout with improved spacing
        row = 0
        form_layout.addWidget(QLabel("Simbolo Azione:"), row, 0, Qt.AlignmentFlag.AlignRight)
        form_layout.addWidget(self.ticker_input, row, 1)
        
        row += 1
        form_layout.addWidget(QLabel("Quantità:"), row, 0, Qt.AlignmentFlag.AlignRight)
        form_layout.addWidget(self.shares_input, row, 1)
        
        row += 1
        form_layout.addWidget(QLabel("Data e Ora:"), row, 0, Qt.AlignmentFlag.AlignRight)
        form_layout.addWidget(self.time_input, row, 1)
        
        row += 1
        form_layout.addWidget(self.market_price_label, row, 0, 1, 2, Qt.AlignmentFlag.AlignCenter)
        
        row += 1
        form_layout.addWidget(QLabel("Prezzo Personalizzato (EUR):"), row, 0, Qt.AlignmentFlag.AlignRight)
        form_layout.addWidget(self.custom_price_input, row, 1)
        
        # Add help text
        # help_label = QLabel("Personalizza prezzo per tuo acquisto")
        # help_label.setStyleSheet("color: #6B7280; font-size: 13px; font-style: italic;")
        # help_label.setWordWrap(True)
        
        layout.addLayout(form_layout)
        #layout.addWidget(help_label)
        layout.addSpacing(10)
        layout.addWidget(self.search_button)
        layout.addWidget(self.submit_button)
        
        # Connections
        self.time_input.dateTimeChanged.connect(self.update_market_price)
        self.ticker_input.textChanged.connect(self.update_market_price)
        self.search_button.clicked.connect(self.open_search_dialog)
        self.submit_button.clicked.connect(self.accept)
        
        self.update_market_price()

    def open_search_dialog(self):
        dialog = SearchStockDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_ticker:
            self.ticker_input.setText(dialog.selected_ticker)
            self.update_market_price()

    def update_market_price(self):
        """Update market price display and optionally the custom price input"""
        ticker = self.ticker_input.text().upper().strip()
        if not ticker:
            self.market_price_label.setText("Prezzo di Mercato (EUR): €0.00")
            return
            
        try:
            date = self.time_input.dateTime().toPyDateTime().date()
            hist = yf.Ticker(ticker).history(
                start=date - timedelta(days=3), 
                end=date + timedelta(days=4)
            )
            if hist.empty:
                hist = yf.Ticker(ticker).history(period="5d")
                
            if not hist.empty:
                eurusd = get_eur_usd_rate()
                price_eur = float(hist.iloc[-1]['Close']) / max(eurusd, 1e-9)
                self.market_price_label.setText(f"Prezzo di Mercato (EUR): €{price_eur:.4f}")
                
                # If custom price is 0 (default/special value), update it with market price
                #if self.custom_price_input.value() <= 0.0001:
                self.custom_price_input.setValue(price_eur)
                    
            else:
                self.market_price_label.setText("Prezzo di mercato non trovato per questo simbolo.")
        except Exception as e:
            print(f"Update market price error: {e}")
            self.market_price_label.setText("Errore nel recupero del prezzo di mercato.")

    def get_transaction_data(self):
        dt_local = self.time_input.dateTime().toPyDateTime()
        rome_dt = ROME_TZ.localize(dt_local.replace(tzinfo=None))
        utc_dt = rome_dt.astimezone(pytz.utc)

        ticker = self.ticker_input.text().upper().strip()
        
        # Use custom price if provided, otherwise get market price
        custom_price = self.custom_price_input.value()
        if custom_price > 0:
            final_price = custom_price
        else:
            # Extract market price from label or fetch it
            market_price_text = self.market_price_label.text()
            try:
                final_price = float(market_price_text.split('€')[1].strip())
            except Exception:
                final_price = infer_price_eur_if_missing(ticker, utc_dt) if ticker else 0.0

        return {
            "ticker": ticker,
            "shares": float(self.shares_input.value()),
            "datetime": utc_dt.isoformat(),
            "price_eur": float(final_price)
        }

class SearchStockDialog(QDialog):
    """Dialog for searching stock symbols"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cerca Titolo")
        self.resize(480, 360)
        self.selected_ticker = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Cerca per nome o simbolo (es. Apple, AAPL)")
        self.result_list = QListWidget()
        
        layout.addWidget(QLabel("Digita il nome o il simbolo di un'azienda:"))
        layout.addWidget(self.search_input)
        layout.addWidget(self.result_list)
        
        self.search_input.textChanged.connect(self.search_stock)
        self.result_list.itemDoubleClicked.connect(self.select_stock)

    def search_stock(self, query):
        query = query.strip()
        self.result_list.clear()
        if len(query) < 2:
            return
            
        try:
            url = f"https://query1.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(query)}"
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'quotes' in data and data['quotes']:
                for item in data['quotes'][:15]:
                    if 'symbol' in item:
                        longname = item.get('longname', item.get('shortname', 'N/A'))
                        text = f"{item['symbol']} - {longname}"
                        list_item = QListWidgetItem(text)
                        list_item.setData(Qt.ItemDataRole.UserRole, item['symbol'])
                        self.result_list.addItem(list_item)
            else:
                self.result_list.addItem(QListWidgetItem("Nessun risultato trovato."))
        except Exception as e:
            print(f"Search error: {e}")
            QMessageBox.warning(self, "Errore di ricerca", str(e))

    def select_stock(self, item):
        symbol = item.data(Qt.ItemDataRole.UserRole)
        if symbol:
            self.selected_ticker = symbol
            self.accept()
