from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from routing.views import heatmap_payload, risk_for_weather


class RiskRuleTests(SimpleTestCase):
    def test_wind_thresholds(self):
        cases = [
            (24.9, 'Low'),
            (25, 'Moderate'),
            (35, 'High'),
            (45, 'Severe'),
            (55, 'No Travel'),
        ]
        for wind, expected in cases:
            with self.subTest(wind=wind):
                self.assertEqual(risk_for_weather(wind, 0, 0, 1)[0], expected)

    def test_rain_thresholds(self):
        cases = [
            (0.099, 'Low'),
            (0.10, 'Moderate'),
            (0.25, 'High'),
            (0.50, 'Severe'),
            (1.00, 'Severe'),
            (1.01, 'No Travel'),
        ]
        for rain, expected in cases:
            with self.subTest(rain=rain):
                self.assertEqual(risk_for_weather(0, rain, 0, 1)[0], expected)

    def test_snow_thresholds(self):
        cases = [
            (0.49, 'Low'),
            (0.5, 'Moderate'),
            (1.0, 'High'),
            (2.0, 'Severe'),
            (3.0, 'Severe'),
            (3.01, 'No Travel'),
        ]
        for snow, expected in cases:
            with self.subTest(snow=snow):
                self.assertEqual(risk_for_weather(0, 0, snow, 1)[0], expected)

    def test_wind_no_travel_any_load(self):
        self.assertEqual(risk_for_weather(55, 0, 0, 1)[0], 'No Travel')

    def test_heavy_load_45_54_no_travel(self):
        self.assertEqual(risk_for_weather(50, 0, 0, 30001)[0], 'No Travel')

    def test_very_heavy_load_35_44_severe(self):
        self.assertEqual(risk_for_weather(40, 0, 0, 40001)[0], 'Severe')

    def test_load_limits_are_strictly_greater_than(self):
        self.assertEqual(risk_for_weather(50, 0, 0, 30000)[0], 'Severe')
        self.assertEqual(risk_for_weather(40, 0, 0, 40000)[0], 'High')

    def test_low_weather(self):
        self.assertEqual(risk_for_weather(10, 0.05, 0.1, 10000)[0], 'Low')

    @patch('routing.views.requests.get')
    def test_heatmap_reuses_one_forecast_for_all_slider_hours(self, mock_get):
        departure = datetime(2026, 1, 1, tzinfo=timezone.utc)
        times = [(departure + timedelta(hours=hour)).isoformat() for hour in range(49)]
        forecast = {
            'hourly': {
                'time': times,
                'wind_speed_10m': list(range(49)),
                'rain': [0] * 49,
                'snowfall': [0] * 49,
            },
        }
        response = Mock()
        response.json.return_value = [forecast, forecast]
        mock_get.return_value = response
        routes = [{'checkpoints': [
            {'lat': 39.0, 'lon': -104.0},
            {'lat': 40.0, 'lon': -105.0},
        ]}]

        slices = heatmap_payload(routes, departure)

        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(len(slices), 17)
        self.assertEqual(slices[0]['points'][0]['wind_mph'], 0)
        self.assertEqual(slices[-1]['points'][0]['wind_mph'], 48)
