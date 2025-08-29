import yfinance as yf
import pandas as pd
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import QFont
import pyqtgraph as pg
from datetime import datetime, timedelta
import numpy as np
from utils import  get_eur_usd_rate, get_inflation_rate_annual


class ClickablePlotWidget(pg.PlotWidget):
    """Interactive plot widget with hover functionality"""
    def __init__(self, parent=None, date_range=None):
        super().__init__(parent)
        self.date_range = date_range
        self.plot_items = {}
        self.setup_ui()
        
    def setup_ui(self):
        self.setMouseTracking(True)
        self.scene().sigMouseMoved.connect(self.on_mouse_moved)

        self.hover_label = pg.TextItem(text="", color=(0, 0, 0))
        self.addItem(self.hover_label)
        self.hover_label.hide()
        
        self.hover_point = pg.ScatterPlotItem(
            size=10, symbol='o', brush=pg.mkBrush(color='r'), pen=pg.mkPen(color='w', width=1)
        )
        self.addItem(self.hover_point)
        self.hover_point.hide()
        
        # Styling
        for axis in ['bottom', 'left']:
            self.getAxis(axis).setTickFont(QFont("Segoe UI", 8))
            self.getAxis(axis).setPen(pg.mkPen(color='#1f2937'))
        self.getPlotItem().showGrid(x=True, y=True, alpha=0.5)

    def plot(self, *args, **kwargs):
        item = self.getPlotItem().plot(*args, **kwargs)
        self.plot_items[item] = kwargs.get('name', '')
        return item
    
    def on_mouse_moved(self, evt):
        if not self.sceneBoundingRect().contains(evt):
            return
            
        mouse_point = self.getPlotItem().vb.mapSceneToView(evt)
        x_mouse, y_mouse = mouse_point.x(), mouse_point.y()
        
        closest_point = self.find_closest_point(x_mouse, y_mouse)
        
        if closest_point:
            self.show_hover_info(closest_point)
        else:
            self.hide_hover_info()

    def find_closest_point(self, x_mouse, y_mouse):
        closest_point_data = None
        min_distance = float('inf')

        for item in self.plot_items:
            if not hasattr(item, 'xData') or not item.xData.size > 0:
                continue
            
            index = np.argmin(np.abs(item.xData - x_mouse))
            dx = item.xData[index] - x_mouse
            dy = item.yData[index] - y_mouse
            distance = np.sqrt(dx**2 + dy**2)
            
            if distance < min_distance and distance < 20:
                min_distance = distance
                closest_point_data = {
                    'x': item.xData[index],
                    'y': item.yData[index],
                    'name': self.plot_items[item],
                    'index': index
                }
        
        return closest_point_data

    def show_hover_info(self, point_data):
        if not (self.date_range is None) and point_data['index'] < len(self.date_range):
            date_str = self.date_range[point_data['index']].strftime("%Y-%m-%d")
            text = (f"<b>{point_data['name']}</b><br>"
                   f"Data: {date_str}<br>"
                   f"Valore: €{point_data['y']:.2f}")
            
            html = f"<div style='background: white; border: 1px solid black; padding: 5px; border-radius: 5px; font-size: 10px;'>{text}</div>"
            self.hover_label.setHtml(html)
            self.hover_label.setPos(point_data['x'], point_data['y'])
            self.hover_label.setAnchor((0.5, 1.5))
            self.hover_label.show()
            
            self.hover_point.setData([point_data['x']], [point_data['y']])
            self.hover_point.show()

    def hide_hover_info(self):
        self.hover_label.hide()
        self.hover_point.hide()


class PortfolioGraphWindow(QDialog):
    """Window for displaying portfolio performance graphs"""
    def __init__(self, transactions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Andamento del Portafoglio")
        self.resize(1200, 740)
        self.transactions = transactions
        self.setup_ui()
        self.plot()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)  # Add padding
        
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.verticalHeader().setDefaultSectionSize(40)  
        self.table_view.horizontalScrollBar().setStyleSheet("""
                QScrollBar:horizontal {
                    height: 0px;
                    border: 1px solid #E5E7EB;
                    background-color: #F9FAFB;
                    border-radius: 9px;
                    margin: 3px 0px 3px 0px;
                }
                QScrollBar::handle:horizontal {
                    background-color: #9CA3AF;
                    border-radius: 7px;
                    min-width: 30px;
                    margin: 2px;
                }
                QScrollBar::handle:horizontal:hover {
                    background-color: #6B7280;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    border: none;
                    background: none;
                    width: 0px;
                }
            """)
        layout.addWidget(self.table_view)
        
        layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        
        self.inflation_checkbox = QCheckBox("Mostra serie in € reali (al netto dell'inflazione)")
        self.inflation_checkbox.clicked.connect(self.plot)
        checkbox_font = QFont("Segoe UI", 14, QFont.Weight.Bold)
        self.inflation_checkbox.setFont(checkbox_font)
        self.inflation_checkbox.setStyleSheet("QCheckBox { color: #1f2937; padding: 10px; }")
        layout.addWidget(self.inflation_checkbox)
        
        plot_container = QWidget()
        plot_layout = QHBoxLayout(plot_container)
        plot_layout.setContentsMargins(80, 0, 80, 0)  # Increased left and right padding
        
        self.plot_widget = ClickablePlotWidget(self)
        plot_layout.addWidget(self.plot_widget)
        layout.addWidget(plot_container, 2)
        
        close_btn = QPushButton("Chiudi")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def get_dividend_data(self, ticker, start_date, end_date):
        """Get dividend data for a ticker between dates"""
        try:
            stock = yf.Ticker(ticker)
            # Get dividend history
            dividends = stock.dividends
            if dividends.empty:
                return pd.Series(dtype=float)
            
            # Convert timezone-aware index to timezone-naive for comparison
            dividends.index = dividends.index.tz_convert(None) if dividends.index.tz else dividends.index
            
            # Filter dividends within date range
            mask = (dividends.index >= pd.Timestamp(start_date)) & (dividends.index <= pd.Timestamp(end_date))
            filtered_dividends = dividends[mask]
            
            # Convert to EUR (assuming USD dividends)
            eurusd = get_eur_usd_rate()
            filtered_dividends_eur = filtered_dividends / max(eurusd, 1e-9)
            
            return filtered_dividends_eur
        except Exception as e:
            print(f"Dividend data error for {ticker}: {e}")
            return pd.Series(dtype=float)

    def calculate_yearly_dividends(self, tx_df):
        """Calculate yearly dividends for each ticker"""
        yearly_dividends = {}
        
        for ticker in tx_df['ticker'].unique():
            ticker_transactions = tx_df[tx_df['ticker'] == ticker]
            
            # Get dividend data for this ticker
            dividends = self.get_dividend_data(ticker, self.first_ts, self.end_ts)
            
            if dividends.empty:
                yearly_dividends[ticker] = pd.Series(0.0, index=self.annual_infl.index)
                continue
            
            # Calculate shares owned at each dividend date
            ticker_yearly_divs = []
            
            for year in self.annual_infl.index:
                year_start = pd.Timestamp(f"{year}-01-01")
                year_end = pd.Timestamp(f"{year}-12-31")
                
                # Get dividends for this year
                year_dividends = dividends[(dividends.index >= year_start) & (dividends.index <= year_end)]
                
                total_div_received = 0.0
                
                for div_date, div_amount in year_dividends.items():
                    # Calculate shares owned at dividend date
                    shares_owned = 0.0
                    for _, tx in ticker_transactions.iterrows():
                        tx_date = pd.to_datetime(tx['datetime']).tz_localize(None)
                        if tx_date <= div_date:
                            shares_owned += float(tx['shares'])
                    
                    total_div_received += div_amount * shares_owned
                
                ticker_yearly_divs.append(total_div_received)
            
            yearly_dividends[ticker] = pd.Series(ticker_yearly_divs, index=self.annual_infl.index)
        
        return yearly_dividends

    def plot(self):
        if not self.transactions:
            self.plot_widget.setTitle("Nessuna transazione per visualizzare il grafico.")
            return

        try:
            self.calculate_portfolio_data()
            self.update_table()
            self.update_plot()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.plot_widget.setTitle(f"Errore nella creazione del grafico: {e}")

    def calculate_portfolio_data(self):
        tx_df = pd.DataFrame(self.transactions)
        tx_df['datetime'] = pd.to_datetime(tx_df['datetime']).dt.tz_localize(None)

        self.first_ts = tx_df['datetime'].min().normalize()
        self.end_ts = pd.to_datetime(datetime.utcnow()).normalize()
        self.date_range = pd.date_range(start=self.first_ts, end=self.end_ts, freq='D')
        self.plot_widget.date_range = self.date_range

        self.inflation_daily_series, self.annual_infl = get_inflation_rate_annual(self.first_ts, self.end_ts)
        eurusd = get_eur_usd_rate()
        
        # Calculate yearly dividends
        self.yearly_dividends = self.calculate_yearly_dividends(tx_df)
        
        # Initialize series
        self.invest_series = pd.Series(0.0, index=self.date_range)
        self.market_series = pd.Series(0.0, index=self.date_range)
        self.real_invest_series = pd.Series(0.0, index=self.date_range)
        self.real_market_series = pd.Series(0.0, index=self.date_range)

        # Get ticker prices
        self.ticker_prices = {}
        self.ticker_yearly_values = {}
        
        tickers_list = sorted(tx_df['ticker'].unique())
        all_tickers = yf.Tickers(' '.join(tickers_list))

        for ticker in tickers_list:
            # hist = yf.Ticker(ticker).history(
            #     start=self.first_ts.date(), 
            #     end=self.end_ts.date() + timedelta(days=1)
            # )
            hist = all_tickers.tickers[ticker].history(
                start=self.first_ts.date(), 
                end=self.end_ts.date() + timedelta(days=1)
            )
            if not hist.empty:
                price_usd = hist['Close']
                price_usd.index = pd.to_datetime(price_usd.index).tz_localize(None)
                self.ticker_prices[ticker] = (price_usd / max(eurusd, 1e-9)).reindex(
                    self.date_range, method='ffill'
                ).fillna(0.0)

                yearly_value = price_usd.resample('YE').last()
                self.ticker_yearly_values[ticker] = yearly_value / max(eurusd, 1e-9)

        # Calculate daily portfolio values
        self.calculate_daily_values(tx_df)

    def calculate_daily_values(self, tx_df):
        for day_idx, day_ts in enumerate(self.date_range):
            totals = {'invest_nom': 0.0, 'market_nom': 0.0, 'invest_real': 0.0, 'market_real': 0.0}
            current_inflation = self.inflation_daily_series.loc[day_ts]
            
            for _, transaction in tx_df.iterrows():
                tx_date = pd.to_datetime(transaction['datetime']).normalize()
                if tx_date <= day_ts:
                    self.process_transaction(transaction, tx_date, day_ts, current_inflation, totals)
            
            self.invest_series.iloc[day_idx] = totals['invest_nom']
            self.market_series.iloc[day_idx] = totals['market_nom']
            self.real_invest_series.iloc[day_idx] = totals['invest_real']
            self.real_market_series.iloc[day_idx] = totals['market_real']

    def process_transaction(self, transaction, tx_date, current_date, current_inflation, totals):
        cost_nominal = float(transaction.get('price_eur', 0.0)) * float(transaction.get('shares', 0.0))
        totals['invest_nom'] += cost_nominal

        # Real cost calculation
        try:
            tx_inflation = self.inflation_daily_series.loc[tx_date]
            cost_real = cost_nominal / (current_inflation / tx_inflation)
            totals['invest_real'] += cost_real
        except KeyError:
            totals['invest_real'] += cost_nominal

        # Market value calculation
        shares = float(transaction['shares'])
        ticker = transaction['ticker'].upper()

        if ticker in self.ticker_prices:
            try:
                current_price = self.ticker_prices[ticker].loc[current_date]
                market_value_nominal = shares * current_price
                totals['market_nom'] += market_value_nominal
                
                tx_inflation = self.inflation_daily_series.loc[tx_date]
                market_value_real = market_value_nominal / (current_inflation / tx_inflation)
                totals['market_real'] += market_value_real
            except KeyError:
                pass

    def update_table(self):
        yearly_capital = self.market_series.resample('YE').last()
        yearly_real_capital = self.real_market_series.resample('YE').last()
        yearly_returns = yearly_capital.pct_change().fillna(0)

        yearly_investment = self.invest_series.resample('YE').last()
        yearly_gains = yearly_capital - yearly_investment
        yearly_gains_returns =  (yearly_gains.diff()/yearly_gains.shift().abs()).fillna(0)

        # Calculate total dividends per year
        total_yearly_dividends = pd.Series(0.0, index=self.annual_infl.index)
        for ticker, ticker_divs in self.yearly_dividends.items():
            total_yearly_dividends += ticker_divs
        
        # Get average price for display (simplified approach)
        if self.ticker_yearly_values:
            first_ticker = list(self.ticker_yearly_values.keys())[0]
            prices = self.ticker_yearly_values[first_ticker] if len(self.ticker_yearly_values) == 1 else pd.Series([0])
        else:
            prices = pd.Series([0])


        table_data = {
            'Prezzo per azione (EUR)': prices.values, 
            'Capitale nominale (EUR)': yearly_capital.values,
            'Capitale reale (EUR)': yearly_real_capital.values,
            'Rendimento %': yearly_returns.values * 100,
            'Guadagno nominale (EUR)': yearly_gains.values,
            'Guadagno annualizzato %': yearly_gains_returns.values * 100,
            'Inflazione %': self.annual_infl.values * 100,
            'Dividendi (EUR)': total_yearly_dividends.values
        }

        if len(self.ticker_yearly_values) > 1:
            del table_data['Prezzo per azione (EUR)']
        
        df_table = pd.DataFrame(table_data, index=self.annual_infl.index)
        model = PandasModel(df_table)
        self.table_view.setModel(model)
        
        # # Enhanced table styling
        # self.table_view.resizeColumnsToContents()
        # self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # Set minimum column widths and enable horizontal scrolling
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setMinimumSectionSize(150)  # Minimum width for readability
        
        # Ensure each column has a reasonable minimum width
        for column in range(model.columnCount()):
            current_width = header.sectionSize(column)
            min_width = max(150, len(str(df_table.columns[column])) * 8 + 20)  # Base on header text length
            if current_width < min_width:
                header.resizeSection(column, min_width)
        
        
        # Set fonts
        table_font = QFont("Segoe UI", 16)
        header_font = QFont("Segoe UI", 17, QFont.Weight.Bold)
        
        self.table_view.setFont(table_font)
        self.table_view.horizontalHeader().setFont(header_font)
        self.table_view.verticalHeader().setFont(header_font)
        
        # Center align all content
        for row in range(model.rowCount()):
            for col in range(model.columnCount()):
                index = model.index(row, col)
                # The centering will be handled in the PandasModel class

    def update_plot(self):
        self.plot_widget.clear()
        self.plot_widget.addLegend()
        
        # Enhanced title styling
        title_style = {'font-size': '18px', 'font-weight': 'bold', 'color': '#1f2937'}
        self.plot_widget.setTitle("Andamento del Portafoglio", **title_style)
        self.plot_widget.setLabel('bottom', "Data")
        self.plot_widget.setLabel('left', "Euro (€)")
        
        x_axis = np.arange(len(self.date_range))
        
        # Setup date axis
        date_ticks = [(i, dt.strftime("%b '%y")) for i, dt in enumerate(self.date_range) if dt.day == 1]
        self.plot_widget.getAxis('bottom').setTicks([date_ticks])
        self.plot_widget.getAxis('bottom').setStyle(tickTextAngle=45)   # diagonal ticks
        
        # Plot main series
        self.plot_widget.plot(
            x_axis, self.market_series.values, 
            pen=pg.mkPen(color='#3B82F6', width=5), 
            name='Valore di Mercato (nominale)'
        )
        self.plot_widget.plot(
            x_axis, self.invest_series.values, 
            pen=pg.mkPen(color='#EF4444', width=5, style=Qt.PenStyle.DashLine), 
            name='Capitale Investito (nominale)'
        )
        
        # Plot inflation-adjusted series if checked
        if self.inflation_checkbox.isChecked():
            self.plot_widget.plot(
                x_axis, self.real_market_series.values, 
                pen=pg.mkPen(color='#16A34A', width=5, style=Qt.PenStyle.DotLine), 
                name='Valore di Mercato (in € reali)'
            )
            self.plot_widget.plot(
                x_axis, self.real_invest_series.values, 
                pen=pg.mkPen(color='#111827', width=5, style=Qt.PenStyle.DashDotLine), 
                name='Capitale Investito (in € reali)'
            )
        
        # Auto-range and center the plot
        self.plot_widget.getViewBox().autoRange()
        self.plot_widget.getViewBox().enableAutoRange(axis='xy')


class PandasModel(QAbstractTableModel):
    """Enhanced model for displaying pandas DataFrames in QTableView with centered alignment"""
    def __init__(self, data):
        super().__init__()
        self._data = data

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid():
            if role == Qt.ItemDataRole.DisplayRole:
                value = self._data.iloc[index.row(), index.column()]
                return f"{value:.2f}" if isinstance(value, (float, np.float64)) else str(value)
            elif role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignCenter
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._data.columns[section])
            elif orientation == Qt.Orientation.Vertical:
                return str(self._data.index[section])
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        return None

