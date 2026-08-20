import sys
import requests
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFrame, QScrollArea, QMessageBox, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

def get_weather_condition(code):
    """Translates WMO weather codes into global descriptive conditions."""
    codes = {
        0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing Rime Fog",
        51: "Light Drizzle", 53: "Moderate Drizzle", 55: "Dense Drizzle",
        61: "Slight Rain", 63: "Moderate Rain", 65: "Heavy Rain",
        71: "Slight Snow", 73: "Moderate Snow", 75: "Heavy Snow",
        77: "Snow Grains",
        80: "Slight Rain Showers", 81: "Moderate Rain Showers", 82: "Violent Rain Showers",
        85: "Slight Snow Showers", 86: "Heavy Snow Showers",
        95: "Thunderstorm", 96: "Thunderstorm w/ Hail", 99: "Thunderstorm w/ Heavy Hail"
    }
    return codes.get(code, "Unknown")

class GlobalWeatherWorker(QThread):
    """Background thread to handle global weather data requests."""
    data_fetched = pyqtSignal(dict, dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, city_name, is_imperial):
        super().__init__()
        self.city_name = city_name
        self.is_imperial = is_imperial

    def run(self):
        try:
            # 1. Global Geocoding Search
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={self.city_name}&count=1&language=en&format=json"
            geo_res = requests.get(geo_url, timeout=10).json()

            if not geo_res.get("results"):
                self.error_occurred.emit(f"Could not find any global location named '{self.city_name}'.")
                return

            loc = geo_res["results"][0]
            location_info = {
                "name": loc.get("name"),
                "admin": loc.get("admin1", ""),
                "country": loc.get("country", ""),
                "lat": loc.get("latitude"),
                "lon": loc.get("longitude"),
                "elevation": loc.get("elevation", 0),
                "timezone": loc.get("timezone", "auto")
            }

            # 2. Fetch Multi-Model Global Forecast Data
            temp_unit = "fahrenheit" if self.is_imperial else "celsius"
            wind_unit = "mph" if self.is_imperial else "kmh"

            weather_url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": location_info["lat"],
                "longitude": location_info["lon"],
                "timezone": location_info["timezone"],
                "models": "best_match",  # Global models: ECMWF, ICON, GFS, HRRR, etc.
                "temperature_unit": temp_unit,
                "wind_speed_unit": wind_unit,
                "current": [
                    "temperature_2m", "apparent_temperature", "relative_humidity_2m",
                    "dew_point_2m", "precipitation", "weather_code", "surface_pressure",
                    "wind_speed_10m", "wind_gusts_10m"
                ],
                "hourly": [
                    "temperature_2m", "precipitation_probability", "precipitation", "weather_code"
                ],
                "forecast_days": 1
            }

            forecast_res = requests.get(weather_url, params=params, timeout=10).json()
            self.data_fetched.emit(location_info, forecast_res)

        except Exception as e:
            self.error_occurred.emit(f"Connection failed: {str(e)}")


class GlobalWeatherApp(QWidget):
    def __init__(self):
        super().__init__()
        self.is_imperial = False
        self.last_searched_city = ""
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Global Precision Weather Forecaster")
        self.setFixedSize(540, 720)
        self.setStyleSheet("""
            QWidget {
                background-color: #0B0F19;
                color: #F8FAFC;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLineEdit {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px 14px;
                color: #FFFFFF;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #38BDF8;
            }
            QPushButton {
                background-color: #0284C7;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #0369A1;
            }
            QRadioButton {
                color: #94A3B8;
                font-size: 13px;
                font-weight: bold;
            }
            QRadioButton::checked {
                color: #38BDF8;
            }
            QFrame#card {
                background-color: #1E293B;
                border-radius: 12px;
                padding: 16px;
            }
            QFrame#hourly_item {
                background-color: #334155;
                border-radius: 8px;
            }
            QScrollBar:vertical {
                border: none;
                background: #0B0F19;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #475569;
                border-radius: 3px;
            }
        """)

        # Main Layout
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(14)
        self.setLayout(self.layout)

        # Search Bar
        search_layout = QHBoxLayout()
        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("Search any city in the world (e.g. Tokyo, Paris, New York)...")
        self.city_input.returnPressed.connect(self.trigger_search)
        search_layout.addWidget(self.city_input)

        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.trigger_search)
        search_layout.addWidget(self.search_btn)
        self.layout.addLayout(search_layout)

        # Unit Selector (Metric vs Imperial)
        unit_layout = QHBoxLayout()
        unit_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        self.unit_group = QButtonGroup(self)
        self.metric_rb = QRadioButton("Metric (°C, km/h)")
        self.imperial_rb = QRadioButton("Imperial (°F, mph)")
        
        self.metric_rb.setChecked(True)
        self.unit_group.addButton(self.metric_rb)
        self.unit_group.addButton(self.imperial_rb)

        self.metric_rb.toggled.connect(self.on_unit_change)

        unit_layout.addWidget(self.metric_rb)
        unit_layout.addSpacing(16)
        unit_layout.addWidget(self.imperial_rb)
        self.layout.addLayout(unit_layout)

        # Main Content Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        self.container = QWidget()
        self.container_layout = QVBoxLayout()
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(14)
        self.container.setLayout(self.container_layout)
        
        self.scroll_area.setWidget(self.container)
        self.layout.addWidget(self.scroll_area)

        # Initial Placeholder Message
        self.placeholder = QLabel("Search any city worldwide for high-precision model forecasts.")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet("color: #64748B; font-size: 14px; margin-top: 120px;")
        self.container_layout.addWidget(self.placeholder)

    def trigger_search(self):
        city = self.city_input.text().strip()
        if not city:
            return
        self.last_searched_city = city
        self.search_weather(city)

    def on_unit_change(self):
        self.is_imperial = self.imperial_rb.isChecked()
        if self.last_searched_city:
            self.search_weather(self.last_searched_city)

    def search_weather(self, city):
        self.search_btn.setEnabled(False)
        self.search_btn.setText("Fetching...")

        self.worker = GlobalWeatherWorker(city, self.is_imperial)
        self.worker.data_fetched.connect(self.update_ui)
        self.worker.error_occurred.connect(self.handle_error)
        self.worker.start()

    def handle_error(self, message):
        self.search_btn.setEnabled(True)
        self.search_btn.setText("Search")
        QMessageBox.critical(self, "Error", message)

    def clear_container(self):
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def update_ui(self, loc, data):
        self.search_btn.setEnabled(True)
        self.search_btn.setText("Search")
        self.clear_container()

        curr = data["current"]
        t_unit = "°F" if self.is_imperial else "°C"
        w_unit = "mph" if self.is_imperial else "km/h"

        # 1. Location Card
        loc_card = QFrame()
        loc_card.setObjectName("card")
        loc_layout = QVBoxLayout(loc_card)
        
        parts = [loc['name'], loc['admin'], loc['country']]
        city_title = ", ".join([p for p in parts if p])
            
        title_lbl = QLabel(city_title)
        title_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        loc_layout.addWidget(title_lbl)

        sub_lbl = QLabel(f"Coords: {loc['lat']} N, {loc['lon']} E | Elev: {loc['elevation']}m | Timezone: {loc['timezone']}")
        sub_lbl.setStyleSheet("color: #94A3B8; font-size: 11px;")
        loc_layout.addWidget(sub_lbl)
        self.container_layout.addWidget(loc_card)

        # 2. Weather Overview
        curr_card = QFrame()
        curr_card.setObjectName("card")
        curr_layout = QVBoxLayout(curr_card)

        temp_lbl = QLabel(f"{curr['temperature_2m']}{t_unit}")
        temp_lbl.setFont(QFont("Segoe UI", 42, QFont.Weight.Bold))
        temp_lbl.setStyleSheet("color: #38BDF8;")
        curr_layout.addWidget(temp_lbl)

        cond_text = get_weather_condition(curr['weather_code'])
        feels_text = f"Feels like {curr['apparent_temperature']}{t_unit} • {cond_text}"
        cond_lbl = QLabel(feels_text)
        cond_lbl.setFont(QFont("Segoe UI", 13))
        cond_lbl.setStyleSheet("color: #E2E8F0;")
        curr_layout.addWidget(cond_lbl)

        grid_frame = QFrame()
        grid = QHBoxLayout(grid_frame)
        grid.setContentsMargins(0, 12, 0, 0)

        metrics = [
            ("Humidity", f"{curr['relative_humidity_2m']}%"),
            ("Dew Point", f"{curr['dew_point_2m']}{t_unit}"),
            ("Pressure", f"{curr['surface_pressure']} hPa"),
            ("Wind Gusts", f"{curr['wind_gusts_10m']} {w_unit}")
        ]

        for label, val in metrics:
            col = QVBoxLayout()
            v_lbl = QLabel(val)
            v_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            l_lbl = QLabel(label)
            l_lbl.setStyleSheet("color: #64748B; font-size: 11px;")
            col.addWidget(v_lbl)
            col.addWidget(l_lbl)
            grid.addLayout(col)

        curr_layout.addWidget(grid_frame)
        self.container_layout.addWidget(curr_card)

        # 3. 12-Hour Local Timeline
        hourly_title = QLabel("12-Hour Hourly Precision Timeline")
        hourly_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        hourly_title.setStyleSheet("color: #94A3B8; margin-top: 4px;")
        self.container_layout.addWidget(hourly_title)

        hourly = data["hourly"]
        times = hourly["time"]
        temps = hourly["temperature_2m"]
        precip_probs = hourly["precipitation_probability"]
        codes = hourly["weather_code"]

        start_idx = 0
        current_hour_str = datetime.now().strftime("%Y-%m-%dT%H:00")
        for idx, t in enumerate(times):
            if t >= current_hour_str:
                start_idx = idx
                break

        for i in range(start_idx, min(start_idx + 12, len(times))):
            item_frame = QFrame()
            item_frame.setObjectName("hourly_item")
            item_layout = QHBoxLayout(item_frame)
            item_layout.setContentsMargins(12, 8, 12, 8)

            t_str = times[i].split("T")[1]
            time_lbl = QLabel(t_str)
            time_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            time_lbl.setFixedWidth(50)

            c_lbl = QLabel(get_weather_condition(codes[i]))
            c_lbl.setStyleSheet("color: #CBD5E1; font-size: 12px;")

            p_lbl = QLabel(f"💧 {precip_probs[i]}%")
            p_lbl.setStyleSheet("color: #38BDF8; font-size: 12px;")
            p_lbl.setFixedWidth(60)

            temp_item_lbl = QLabel(f"{temps[i]}{t_unit}")
            temp_item_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            temp_item_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

            item_layout.addWidget(time_lbl)
            item_layout.addWidget(c_lbl, stretch=1)
            item_layout.addWidget(p_lbl)
            item_layout.addWidget(temp_item_lbl)

            self.container_layout.addWidget(item_frame)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GlobalWeatherApp()
    window.show()
    sys.exit(app.exec())