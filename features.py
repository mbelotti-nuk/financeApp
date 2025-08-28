import json
import sys
import yfinance as yf
import os
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import QFont, QIcon
import dateutil.parser
from datetime import datetime
from dialogs import TransactionDialog
from models import PortfolioGraphWindow
from utils import get_eur_usd_rate, ROME_TZ, INFLATION_RATE_ANNUAL



class TransactionCard(QFrame):
    """Card widget for displaying transaction information"""
    def __init__(self, html_content=""):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background:#FFFFFF; border:none; border-radius:12px;")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        self.label = QLabel(html_content)
        layout.addWidget(self.label)

class SummaryCard(QFrame):
    """Summary card for portfolio information"""
    def __init__(self, html):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background:#F8FAFC; border:none; border-radius:12px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        self.label = QLabel(html)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

class SlidingWindow(QWidget):
    """Sliding window for detailed transaction view"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setVisible(False)
        self.setup_ui()

    def setup_ui(self):
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, -1)
        shadow.setColor(Qt.GlobalColor.black)
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 6)

        # Horizontal container for summary and transactions
        horizontal_layout = QHBoxLayout()
        horizontal_layout.setSpacing(10)

        self.summary_card = SummaryCard("")
        horizontal_layout.addWidget(self.summary_card, 1)

        # Transactions scroll area
        self.transactions_scroll = QScrollArea()
        self.transactions_scroll.setWidgetResizable(True)
        self.transactions_scroll.setStyleSheet("QScrollArea{border:none;}")
        
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("transactions_list_widget")
        self.list_widget.setStyleSheet("QListWidget{border:none;background:#FFFFFF;}")
        self.transactions_scroll.setWidget(self.list_widget)
        
        horizontal_layout.addWidget(self.transactions_scroll, 1)
        layout.addLayout(horizontal_layout)
        layout.addSpacing(10)

        # Graph button
        self.graph_button = QPushButton("Mostra Grafico Rendimento")
        self.graph_button.clicked.connect(self.show_graph)
        layout.addWidget(self.graph_button)

    def update_info(self, ticker, transactions):
        """Update the sliding window with ticker information"""
        self.ticker = ticker
        self.transactions = transactions
        self.list_widget.clear()

        if not transactions:
            self.summary_card.label.setText(f"<h3>Nessuna transazione per {ticker}</h3>")
            return

        # Calculate summary statistics
        cost_basis, total_shares, cost_basis_real = self.calculate_portfolio_stats(transactions)
        avg_price = (cost_basis / total_shares) if total_shares > 0 else 0.0

        # Get current market data and update summary
        self.update_summary_card(ticker, total_shares, cost_basis, cost_basis_real)
        
        # Populate transaction list
        self.populate_transaction_list(transactions)

    def calculate_portfolio_stats(self, transactions):
        """Calculate portfolio statistics using actual purchase prices"""
        cost_basis = sum(float(t.get('price_eur', 0.0)) * float(t['shares']) for t in transactions)
        total_shares = sum(float(t['shares']) for t in transactions)
        
        # Calculate inflation-adjusted cost basis using actual purchase prices
        cost_basis_real = 0.0
        end_date = datetime.utcnow().date()
        inflation_rate_daily = (1 + INFLATION_RATE_ANNUAL)**(1/365) - 1
        
        for transaction in transactions:
            try:
                tx_date = dateutil.parser.parse(transaction['datetime']).date()
                cost_nominal = float(transaction.get('price_eur', 0.0)) * float(transaction['shares'])
                days_since = (end_date - tx_date).days
                cost_basis_real += cost_nominal * (1 + inflation_rate_daily)**days_since
            except Exception as e:
                print(f"Inflation calculation error: {e}")
                cost_basis_real += float(transaction.get('price_eur', 0.0)) * float(transaction['shares'])
        
        return cost_basis, total_shares, cost_basis_real

    def update_summary_card(self, ticker, total_shares, cost_basis, cost_basis_real):
        """Update the summary card with current market data"""
        try:
            data = yf.Ticker(ticker).history(period='5d')
            if not data.empty:
                eurusd = get_eur_usd_rate()
                current_price_eur = float(data.iloc[-1]['Close']) / max(eurusd, 1e-9)
                current_value = current_price_eur * total_shares
                
                # Calculate gains/losses based on actual purchase prices
                pl_nominal = current_value - cost_basis
                pl_pct_nominal = (pl_nominal / cost_basis * 100.0) if cost_basis > 0 else 0.0
                
                pl_real = current_value - cost_basis_real
                pl_pct_real = (pl_real / cost_basis_real * 100.0) if cost_basis_real > 0 else 0.0

                # Calculate average purchase price
                avg_purchase_price = (cost_basis / total_shares) if total_shares > 0 else 0.0

                # Format colors and signs
                color_nom = "#16A34A" if pl_nominal >= 0 else "#DC2626"
                sign_nom = "+" if pl_nominal >= 0 else ""
                color_real = "#16A34A" if pl_real >= 0 else "#DC2626"
                sign_real = "+" if pl_real >= 0 else ""

                html_content = f"""
                <h2 style='margin:0;color:#111827;'>{ticker}</h2>
                <p style='font-size:14px;'><b>Quantità Totale:</b> {total_shares:.4f}</p>
                <p style='font-size:14px;'><b>Prezzo Medio di Acquisto:</b> €{avg_purchase_price:.4f}</p>
                <p style='font-size:14px;'><b>Prezzo Corrente:</b> €{current_price_eur:.4f}</p>
                <p style='font-size:14px;'><b>Valore Corrente:</b> €{current_value:.2f}</p>
                <p style='font-size:14px;'><b>Capitale Investito:</b> €{cost_basis:.2f}</p>
                <p style='font-size:17px;'><b>Guadagno/Perdita (Nominale):</b> 
                <span style='color:{color_nom};font-weight:700;'>{sign_nom}{pl_nominal:.2f}€ ({sign_nom}{pl_pct_nominal:.1f}%)</span></p>
                <p style='font-size:17px;'><b>Guadagno/Perdita (Reale):</b> 
                <span style='color:{color_real};font-weight:700;'>{sign_real}{pl_real:.2f}€ ({sign_real}{pl_pct_real:.1f}%)</span></p>
                """
                self.summary_card.label.setText(html_content)
            else:
                self.summary_card.label.setText(f"<h2>{ticker}</h2><p>Dati di mercato non disponibili</p>")
        except Exception as e:
            print(f"Market data error: {e}")
            self.summary_card.label.setText(f"<h2>{ticker}</h2><p>Impossibile recuperare i dati di mercato</p>")

    def populate_transaction_list(self, transactions):
        """Populate the transaction list with individual transactions"""
        for i, transaction in enumerate(transactions):
            try:
                dt = dateutil.parser.parse(transaction['datetime']).astimezone(ROME_TZ)
                date_str = dt.strftime("%d/%m/%Y")
                qty = float(transaction['shares'])
                price = float(transaction.get('price_eur', 0.0))
                
                # Create transaction item widget
                item_widget = QWidget()
                item_layout = QHBoxLayout(item_widget)
                item_layout.setContentsMargins(6, 15, 6, 15)

                label_text = f"<b>Data:</b> {date_str} | <b>Quantità:</b> {int(qty)} | <b>Prezzo:</b> €{price:.4f}"
                label = QLabel(label_text)
                item_layout.addWidget(label)
                item_layout.addStretch()

                # Delete button
                delete_btn = QPushButton("Elimina")
                delete_btn.setObjectName("delete_button")
                delete_btn.clicked.connect(lambda _, idx=i: self.delete_transaction(idx))
                item_layout.addWidget(delete_btn)

                # Add to list
                list_item = QListWidgetItem()
                list_item.setSizeHint(item_widget.sizeHint())
                self.list_widget.addItem(list_item)
                self.list_widget.setItemWidget(list_item, item_widget)

            except Exception as e:
                print(f"Transaction card error {i}: {e}")

    def delete_transaction(self, idx):
        """Delete a transaction and update the parent"""
        if 0 <= idx < len(self.transactions):
            # Find the transaction in the parent's transaction list
            tx_to_delete = self.transactions[idx]
            if hasattr(self, 'parent_window') and self.parent_window:
                # Remove from parent's transaction list
                for i, tx in enumerate(self.parent_window.transactions):
                    if (tx.get('ticker') == tx_to_delete.get('ticker') and
                        tx.get('datetime') == tx_to_delete.get('datetime') and
                        tx.get('shares') == tx_to_delete.get('shares')):
                        del self.parent_window.transactions[i]
                        break
                
                self.parent_window.save_transactions()
                self.parent_window.update_ui()
                
                # Update this sliding window
                updated_transactions = [t for t in self.parent_window.transactions 
                                      if t.get('ticker', '').upper() == self.ticker.upper()]
                self.update_info(self.ticker, updated_transactions)

    def show_graph(self):
        """Show graph for current ticker"""
        if hasattr(self, 'ticker') and self.transactions:
            ticker_transactions = [t for t in self.transactions if t['ticker'].upper() == self.ticker.upper()]
            PortfolioGraphWindow(ticker_transactions, self).exec()
        else:
            QMessageBox.warning(self, "Errore", "Nessun dato disponibile per il grafico.")

class PortfolioItemCard(QFrame):
    """Card widget for portfolio items in the main list"""
    def __init__(self, ticker, total_shares, current_value_eur, gain_loss_eur, gain_loss_percent, avg_purchase_price):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background:#FFFFFF; border:none; border-radius:12px;")
        self.setup_ui(ticker, total_shares, current_value_eur, gain_loss_eur, gain_loss_percent, avg_purchase_price)

    def setup_ui(self, ticker, total_shares, current_value, gain_loss, gain_loss_pct, avg_purchase_price):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(15)

        # Left side - basic info with improved layout
        left_layout = QVBoxLayout()
        left_layout.setSpacing(4)
        
        # Ticker label with larger font
        ticker_label = QLabel(f"<b style='font-size:18px;'>{ticker}</b>")
        ticker_label.setWordWrap(True)
        ticker_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        # Quantity label with wrapping
        quantity_label = QLabel(f"Quantità: <b>{total_shares:.4f}</b>")
        quantity_label.setWordWrap(True)
        quantity_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        # Average purchase price
        avg_price_label = QLabel(f"Prezzo Medio: <b>€{avg_purchase_price:.4f}</b>")
        avg_price_label.setWordWrap(True)
        avg_price_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        # Value label with wrapping  
        value_label = QLabel(f"Valore: <b>€{current_value:.2f}</b>")
        value_label.setWordWrap(True)
        value_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        left_layout.addWidget(ticker_label)
        left_layout.addWidget(quantity_label)
        left_layout.addWidget(avg_price_label)
        left_layout.addWidget(value_label)
        left_layout.addStretch()

        # Right side - performance with fixed width
        right_layout = QVBoxLayout()
        performance_label = QLabel()
        performance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        performance_label.setWordWrap(True)
        performance_label.setMinimumWidth(120)
        performance_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        
        if gain_loss >= 0:
            content = f"""
            <div style='text-align:center;'>
                <span style='color:#16A34A;font-size:16px;'><b>+€{gain_loss:.2f}</b></span><br>
                <span style='color:#16A34A;'><b>(+{gain_loss_pct:.1f}%)</b></span>
            </div>
            """
        else:
            content = f"""
            <div style='text-align:center;'>
                <span style='color:#DC2626;font-size:16px;'><b>€{gain_loss:.2f}</b></span><br>
                <span style='color:#DC2626;'><b>({gain_loss_pct:.1f}%)</b></span>
            </div>
            """
        performance_label.setText(content)
        right_layout.addWidget(performance_label)
        right_layout.addStretch()

        # Adjust layout proportions
        layout.addLayout(left_layout, 7)
        layout.addLayout(right_layout, 3)
        
        # Set minimum height for the card
        self.setMinimumHeight(110)

class PortfolioManager(QWidget):
    """Main application window"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gestore Portafoglio d'Investimenti")
        self.resize(1080, 720)
        
        # Setup file path
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))
            
        self.portfolio_file = os.path.join(app_dir, 'transactions.json')
        
        # Load data and initialize
        self.transactions = self.load_transactions()
        self.last_selected_item = None
        
        self.setup_ui()
        self.update_ui()
        
        # Set icon if available
        icon_path = os.path.join(app_dir, 'app_icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def setup_ui(self):
        """Initialize the user interface"""
        main_layout = QHBoxLayout(self)

        # Sidebar
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar)

        # Main content stack
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, 1)

        # Create views
        self.create_actions_view()
        self.create_portfolio_view()

        # Add views to stack
        self.stack.addWidget(self.actions_view)
        self.stack.addWidget(self.portfolio_view)

        # Setup animations
        self.setup_animations()
        
        # Show default view
        self.show_actions_view()

    def create_sidebar(self):
        """Create the sidebar with navigation buttons"""
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 14, 10, 14)
        
        # Title
        title = QLabel("GestorePortafoglio")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        layout.addWidget(title)
        layout.addSpacing(10)

        # Navigation buttons
        self.btn_actions = QPushButton("Azioni")
        self.btn_actions.clicked.connect(self.show_actions_view)
        
        self.btn_graph = QPushButton("Grafico Portafoglio")
        self.btn_graph.clicked.connect(self.show_portfolio_view)
        
        self.btn_add = QPushButton("Aggiungi Transazione")
        self.btn_add.clicked.connect(self.add_transaction)

        layout.addWidget(self.btn_actions)
        layout.addWidget(self.btn_graph)
        layout.addSpacing(6)
        layout.addWidget(self.btn_add)
        layout.addStretch()
        
        return sidebar

    def create_actions_view(self):
        """Create the actions view with transaction list"""
        self.actions_view = QWidget()
        layout = QVBoxLayout(self.actions_view)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        
        # Transaction list
        self.list = QListWidget()
        self.list.setStyleSheet("QListWidget{background:#FFFFFF;border:none;}")
        self.list.itemClicked.connect(self.toggle_sliding_window)
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Sliding window
        self.slide = SlidingWindow(self)
        self.slide.setMaximumHeight(0)
        
        layout.addWidget(self.list)
        layout.addSpacing(6)
        layout.addWidget(self.slide)

    def create_portfolio_view(self):
        """Create the portfolio overview view"""
        self.portfolio_view = QWidget()
        layout = QVBoxLayout(self.portfolio_view)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        
        self.lab_empty_state = QLabel("Aggiungi transazioni per vedere il grafico del portafoglio.")
        self.lab_empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lab_empty_state)

    def setup_animations(self):
        """Setup sliding window animations"""
        self.anim = QPropertyAnimation(self.slide, b"maximumHeight")
        self.anim.setDuration(250)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._closing = False
        self.anim.finished.connect(self._on_anim_finished)

    def _on_anim_finished(self):
        """Handle animation finish"""
        if self._closing:
            self.slide.setVisible(False)
            self.slide.setMaximumHeight(0)
        self._closing = False

    def show_actions_view(self):
        """Show the actions view"""
        self.stack.setCurrentWidget(self.actions_view)
        self.close_sliding_window_immediate()

    def show_portfolio_view(self):
        """Show the portfolio view"""
        self.stack.setCurrentWidget(self.portfolio_view)
        self.close_sliding_window_immediate()
        
        if not self.transactions:
            self.lab_empty_state.show()
        else:
            self.lab_empty_state.hide()
            PortfolioGraphWindow(self.transactions, self).exec()

    def load_transactions(self):
        """Load transactions from file"""
        try:
            with open(self.portfolio_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Load error: {e}")
            return []

    def save_transactions(self):
        """Save transactions to file"""
        try:
            with open(self.portfolio_file, 'w', encoding='utf-8') as f:
                json.dump(self.transactions, f, indent=4, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Errore nel salvataggio: {e}")

    def add_transaction(self):
        """Add a new transaction"""
        dialog = TransactionDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                data = dialog.get_transaction_data()
                if data['ticker'] and data['shares'] > 0 and data['price_eur'] > 0:
                    self.transactions.append(data)
                    self.save_transactions()
                    self.update_ui()
                    QMessageBox.information(self, "Successo", "Transazione aggiunta e salvata!")
                else:
                    QMessageBox.warning(self, "Errore", "Dati transazione non validi.")
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Errore nell'aggiunta della transazione: {e}")

    def update_ui(self):
        """Update the user interface with current data"""
        self.list.clear()
        
        if not self.transactions:
            self.list.addItem(QListWidgetItem("Nessuna transazione disponibile"))
            return

        # Group transactions by ticker
        summary = {}
        for transaction in self.transactions:
            ticker = transaction.get('ticker', '').upper()
            if not ticker:
                continue
                
            if ticker not in summary:
                summary[ticker] = {'shares': 0.0, 'transactions': []}
            
            summary[ticker]['shares'] += float(transaction.get('shares', 0.0))
            summary[ticker]['transactions'].append(transaction)

        # Create portfolio items
        eurusd = get_eur_usd_rate()
        for ticker, data in summary.items():
            self.create_portfolio_item(ticker, data, eurusd)

    def create_portfolio_item(self, ticker, data, eurusd):
        """Create a portfolio item card using actual purchase prices"""
        total_shares = float(data['shares'])
        
        # Calculate cost basis using actual purchase prices
        cost_basis = sum(
            float(tx.get('price_eur', 0.0)) * float(tx.get('shares', 0.0)) 
            for tx in data['transactions']
        )
        
        # Calculate average purchase price
        avg_purchase_price = (cost_basis / total_shares) if total_shares > 0 else 0.0
        
        # Get current market value
        current_value = cost_basis
        profit_loss = 0.0
        profit_loss_pct = 0.0
        
        try:
            hist = yf.Ticker(ticker).history(period='5d')
            if not hist.empty:
                last_price_usd = float(hist.iloc[-1]['Close'])
                last_price_eur = last_price_usd / max(eurusd, 1e-9)
                current_value = last_price_eur * total_shares
                profit_loss = current_value - cost_basis
                profit_loss_pct = (profit_loss / cost_basis * 100.0) if cost_basis > 0 else 0.0
        except Exception as e:
            print(f"Price error for {ticker}: {e}")

        # Create and add card with average purchase price
        card = PortfolioItemCard(ticker, total_shares, current_value, profit_loss, profit_loss_pct, avg_purchase_price)
        list_item = QListWidgetItem()

        # Increase spacing between items
        card_size = card.sizeHint()
        list_item.setSizeHint(QSize(card_size.width(), card_size.height() + 20))
        list_item.setData(Qt.ItemDataRole.UserRole, ticker)
        
        self.list.addItem(list_item)
        self.list.setItemWidget(list_item, card)

    def toggle_sliding_window(self, item):
        """Toggle the sliding window for a selected item"""
        ticker = item.data(Qt.ItemDataRole.UserRole)
        if not ticker:
            return
            
        transactions = [t for t in self.transactions if t.get('ticker', '').upper() == ticker]

        if (self.last_selected_item == item and 
            self.slide.isVisible() and 
            self.slide.maximumHeight() > 0):
            self.close_sliding_window()
            return

        self.slide.update_info(ticker, transactions)
        self.open_sliding_window()
        self.last_selected_item = item

    def open_sliding_window(self):
        """Open the sliding window with animation"""
        self.slide.setVisible(True)
        self.anim.stop()
        self._closing = False
        self.anim.setStartValue(self.slide.maximumHeight())
        self.anim.setEndValue(380)
        self.anim.start()

    def close_sliding_window(self):
        """Close the sliding window with animation"""
        if not self.slide.isVisible() and self.slide.maximumHeight() == 0:
            return
            
        self.anim.stop()
        self._closing = True
        self.anim.setStartValue(self.slide.maximumHeight())
        self.anim.setEndValue(0)
        self.anim.start()
        self.last_selected_item = None

    def close_sliding_window_immediate(self):
        """Close the sliding window immediately without animation"""
        self.anim.stop()
        self._closing = False
        self.slide.setVisible(False)
        self.slide.setMaximumHeight(0)
        self.last_selected_item = None
