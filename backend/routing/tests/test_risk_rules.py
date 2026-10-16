import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase

from routing.views import heatmap_payload, plan_route, risk_for_weather, weather_forecasts


class RiskRuleTests(SimpleTestCase):
    @patch('routing.views.requests.get')
    def test_weather_forecasts_reuses_cached_coordinate_batch(self, mock_get):
        cache.clear()
        self.addCleanup(cache.clear)
        response = Mock()
        response.json.return_value = [{'hourly': {}}, {'hourly': {}}]
        mock_get.return_value = response
        points = [
            {'coordinate': [-104.0, 39.0]},
            {'coordinate': [-105.0, 40.0]},
        ]

        first = weather_forecasts(points)
        second = weather_forecasts(points)

        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(len(first), 2)
        self.assertEqual(len(second), 2)

    @patch('routing.views.time.sleep')
    @patch('routing.views.requests.get')
    def test_weather_forecasts_retries_rate_limited_request(self, mock_get, mock_sleep):
        cache.clear()
        self.addCleanup(cache.clear)
        rate_limited = Mock(status_code=429, headers={'Retry-After': '0'})
        response = Mock(status_code=200)
        response.json.return_value = [{'hourly': {}}]
        mock_get.side_effect = [rate_limited, response]

        forecasts = weather_forecasts([{'coordinate': [-104.12345, 39.12345]}])

        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(0)
        self.assertEqual(len(forecasts), 1)

    def test_plan_route_shares_weather_forecasts_across_routes_and_heatmap(self):
        departure = '2026-01-01T00:00:00Z'
        raw_routes = [
            {
                'geometry': {'coordinates': [[-104.0, 39.0], [-103.5, 39.5]]},
                'duration': 3600,
                'distance': 80000,
            },
            {
                'geometry': {'coordinates': [[-104.0, 39.0], [-103.5, 39.5]]},
                'duration': 3600,
                'distance': 80000,
            },
        ]
        request = RequestFactory().post(
            '/api/plan/',
            data='{"origin":"A","destination":"B","departure":"%s","load_weight":10000,"sample_interval":25}' % departure,
            content_type='application/json',
        )
        with (
            patch('routing.views.geocode_place', side_effect=[{'lat': 39, 'lon': -104}, {'lat': 40, 'lon': -103}]),
            patch('routing.views.get_routes', return_value=raw_routes),
            patch(
                'routing.views.weather_forecasts',
                side_effect=lambda points: [(point, {'hourly': {}}) for point in points],
            ) as mock_forecasts,
        ):
            response = plan_route(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_forecasts.call_count, 1)
        self.assertEqual(json.loads(response.content)['route_count'], 2)

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
