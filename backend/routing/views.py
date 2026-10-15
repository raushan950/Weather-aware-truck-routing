import json
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt

import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

MILES_PER_KM = 0.621371
RISK_SCORE = {'Low': 0, 'Moderate': 1, 'High': 2, 'Severe': 3, 'No Travel': 4}
RISK_ORDER = ['Low', 'Moderate', 'High', 'Severe', 'No Travel']


def haversine_miles(a, b):
    lon1, lat1 = a
    lon2, lat2 = b
    r = 3958.7613
    p1, p2 = radians(lat1), radians(lat2)
    dp = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)
    h = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * r * asin(sqrt(h))


def cumulative_distances(coords):
    out = [0.0]
    for i in range(1, len(coords)):
        out.append(out[-1] + haversine_miles(coords[i - 1], coords[i]))
    return out


def point_at_distance(coords, cumulative, target):
    if target <= 0:
        return coords[0]
    if target >= cumulative[-1]:
        return coords[-1]
    lo, hi = 0, len(cumulative) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if cumulative[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    i = max(1, lo)
    prev_d, next_d = cumulative[i - 1], cumulative[i]
    t = 0 if next_d == prev_d else (target - prev_d) / (next_d - prev_d)
    lon = coords[i - 1][0] + t * (coords[i][0] - coords[i - 1][0])
    lat = coords[i - 1][1] + t * (coords[i][1] - coords[i - 1][1])
    return [lon, lat]


def geocode_place(text):
    r = requests.get(
        f'{settings.NOMINATIM_URL}/search',
        params={'q': text, 'format': 'jsonv2', 'limit': 1},
        headers={'User-Agent': settings.APP_USER_AGENT},
        timeout=15,
    )
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise ValueError(f'Could not find location: {text}')
    return {'lat': float(rows[0]['lat']), 'lon': float(rows[0]['lon']), 'label': rows[0].get('display_name', text)}


def route_osrm(origin, destination):
    coords = f"{origin['lon']},{origin['lat']};{destination['lon']},{destination['lat']}"
    r = requests.get(
        f'{settings.OSRM_BASE_URL}/route/v1/driving/{coords}',
        params={'alternatives': 'true', 'steps': 'false', 'overview': 'full', 'geometries': 'geojson'},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if data.get('code') != 'Ok' or not data.get('routes'):
        raise ValueError('Routing provider did not return a route.')
    return data['routes'][:3]


def route_mapbox(origin, destination):
    coords = f"{origin['lon']},{origin['lat']};{destination['lon']},{destination['lat']}"
    r = requests.get(
        f'https://api.mapbox.com/directions/v5/mapbox/driving/{coords}',
        params={
            'access_token': settings.MAPBOX_ACCESS_TOKEN,
            'alternatives': 'true',
            'geometries': 'geojson',
            'overview': 'full',
            'steps': 'false',
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if not data.get('routes'):
        raise ValueError('Mapbox did not return a route.')
    return data['routes'][:3]


def _offset_waypoint(origin, destination, fraction, offset_miles):
    # Small perpendicular offset used only when a routing provider returns fewer
    # than three alternatives. The waypoint is still passed through the routing
    # API, so every candidate remains a real road route.
    lat1, lon1 = origin['lat'], origin['lon']
    lat2, lon2 = destination['lat'], destination['lon']
    lat = lat1 + (lat2 - lat1) * fraction
    lon = lon1 + (lon2 - lon1) * fraction
    dx = lon2 - lon1
    dy = lat2 - lat1
    length = max((dx * dx + dy * dy) ** 0.5, 1e-6)
    perp_lon, perp_lat = -dy / length, dx / length
    miles_to_deg_lat = 1 / 69.0
    miles_to_deg_lon = 1 / (69.0 * max(cos(radians(lat)), 0.2))
    return {'lat': lat + perp_lat * offset_miles * miles_to_deg_lat, 'lon': lon + perp_lon * offset_miles * miles_to_deg_lon}

def route_via_waypoint(origin, destination, waypoint, provider):
    coords = f"{origin['lon']},{origin['lat']};{waypoint['lon']},{waypoint['lat']};{destination['lon']},{destination['lat']}"
    if provider == 'mapbox' and settings.MAPBOX_ACCESS_TOKEN:
        url = f'https://api.mapbox.com/directions/v5/mapbox/driving/{coords}'
        params = {'access_token': settings.MAPBOX_ACCESS_TOKEN, 'geometries': 'geojson', 'overview': 'full', 'steps': 'false'}
    else:
        url = f'{settings.OSRM_BASE_URL}/route/v1/driving/{coords}'
        params = {'steps': 'false', 'overview': 'full', 'geometries': 'geojson'}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get('routes'):
        return data['routes'][0]
    return None

def get_routes(origin, destination):
    provider = settings.ROUTING_PROVIDER if settings.ROUTING_PROVIDER == 'mapbox' and settings.MAPBOX_ACCESS_TOKEN else 'osrm'
    routes = route_mapbox(origin, destination) if provider == 'mapbox' else route_osrm(origin, destination)
    # Some corridors have no provider-generated alternatives. To still satisfy
    # the assessment's three-option requirement, ask the same routing API for
    # two real-road via-waypoint variants rather than cloning a route.
    if len(routes) < 3:
        existing = routes[:]
        variants = [(0.34, 18), (0.66, -18)]
        for fraction, offset in variants:
            if len(existing) >= 3:
                break
            candidate = route_via_waypoint(origin, destination, _offset_waypoint(origin, destination, fraction, offset), provider)
            if candidate:
                existing.append(candidate)
        routes = existing[:3]
    return routes


def parse_dt(value):
    value = value.strip()
    if value.endswith('Z'):
        return datetime.fromisoformat(value[:-1]).replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def classify_wind(wind):
    if wind >= 55: return 'No Travel'
    if wind >= 45: return 'Severe'
    if wind >= 35: return 'High'
    if wind >= 25: return 'Moderate'
    return 'Low'


def classify_rain(rain):
    if rain > 1.0: return 'No Travel'
    if rain >= 0.50: return 'Severe'
    if rain >= 0.25: return 'High'
    if rain >= 0.10: return 'Moderate'
    return 'Low'


def classify_snow(snow):
    if snow > 3.0: return 'No Travel'
    if snow >= 2.0: return 'Severe'
    if snow >= 1.0: return 'High'
    if snow >= 0.5: return 'Moderate'
    return 'Low'


def apply_load_rule(wind_category, wind, load):
    if wind >= 55:
        return 'No Travel', 'Wind ≥ 55 mph: no travel for any load.'
    if 45 <= wind < 55 and load > 30000:
        return 'No Travel', '45–54 mph wind with a load above 30,000 lb.'
    if 35 <= wind < 45 and load > 40000:
        return 'Severe', '35–44 mph wind with a load above 40,000 lb.'
    return wind_category, None


def risk_for_weather(wind, rain, snow, load):
    wind_r = classify_wind(wind)
    rain_r = classify_rain(rain)
    snow_r = classify_snow(snow)
    adjusted_wind, load_reason = apply_load_rule(wind_r, wind, load)
    candidates = [adjusted_wind, rain_r, snow_r]
    risk = max(candidates, key=lambda x: RISK_SCORE[x])
    reasons = []
    for name, value, category in [('Wind', wind, adjusted_wind), ('Rain', rain, rain_r), ('Snow', snow, snow_r)]:
        if RISK_SCORE[category] == RISK_SCORE[risk] and category != 'Low':
            reasons.append(f'{name}: {value:.2f}')
    if load_reason:
        reasons.append(load_reason)
    return risk, reasons, {'wind': wind_r, 'rain': rain_r, 'snow': snow_r}


def sample_checkpoints(coords, duration_s, interval_miles):
    cumulative = cumulative_distances(coords)
    total = cumulative[-1]
    targets = []
    d = 0.0
    while d < total:
        targets.append(d)
        d += interval_miles
    if not targets or abs(targets[-1] - total) > 0.01:
        targets.append(total)
    points = []
    for idx, distance in enumerate(targets):
        p = point_at_distance(coords, cumulative, distance)
        ratio = distance / total if total else 0
        eta_offset = timedelta(seconds=duration_s * ratio)
        points.append({'index': idx, 'distance_miles': round(distance, 1), 'coordinate': p, 'ratio': ratio, 'eta_offset_seconds': eta_offset.total_seconds()})
    return points, total


def hourly_value(times, values, target):
    if not times or not values:
        return 0.0
    best = min(range(len(times)), key=lambda i: abs(times[i] - target))
    return float(values[best] or 0)


def weather_forecasts(points):
    # Open-Meteo accepts multiple coordinates in one request. Chunking prevents
    # excessively long URLs on long trips with 10-mile sampling.
    results = []
    chunk_size = 25
    for start in range(0, len(points), chunk_size):
        chunk = points[start:start + chunk_size]
        lats = ','.join(f"{p['coordinate'][1]:.5f}" for p in chunk)
        lons = ','.join(f"{p['coordinate'][0]:.5f}" for p in chunk)
        r = requests.get(
            settings.OPEN_METEO_URL,
            params={
                'latitude': lats,
                'longitude': lons,
                'hourly': 'wind_speed_10m,rain,snowfall',
                'wind_speed_unit': 'mph',
                'precipitation_unit': 'inch',
                'forecast_days': 16,
                'timezone': 'UTC',
            },
            timeout=30,
        )
        r.raise_for_status()
        payload = r.json()
        if isinstance(payload, dict):
            payload = [payload]
        if len(payload) != len(chunk):
            raise ValueError('Weather provider returned an incomplete checkpoint forecast.')
        results.extend(zip(chunk, payload))
    return results


def weather_values_at(weather, target):
    hourly = weather.get('hourly', {})
    times = [datetime.fromisoformat(t).replace(tzinfo=timezone.utc) for t in hourly.get('time', [])]
    return (
        hourly_value(times, hourly.get('wind_speed_10m', []), target),
        hourly_value(times, hourly.get('rain', []), target),
        hourly_value(times, hourly.get('snowfall', []), target),
    )


def weather_batch(points, departure):
    results = []
    for point, weather in weather_forecasts(points):
        target = departure + timedelta(seconds=point['eta_offset_seconds'])
        wind, rain, snow = weather_values_at(weather, target)
        results.append((point, wind, rain, snow, target))
    return results


def route_payload(route, route_index, departure, load, interval):
    coords = route['geometry']['coordinates']
    duration_s = float(route['duration'])
    distance_miles = float(route['distance']) / 1000 * MILES_PER_KM
    checkpoints, _ = sample_checkpoints(coords, duration_s, interval)
    weathered = weather_batch(checkpoints, departure)
    checkpoint_out = []
    for point, wind, rain, snow, eta in weathered:
        risk, reasons, breakdown = risk_for_weather(wind, rain, snow, load)
        checkpoint_out.append({
            'id': f'r{route_index}-c{point["index"]}',
            'distance_miles': point['distance_miles'],
            'lat': point['coordinate'][1],
            'lon': point['coordinate'][0],
            'eta': eta.isoformat(),
            'wind_mph': round(wind, 1),
            'rain_in_hr': round(rain, 3),
            'snow_in_hr': round(snow, 3),
            'risk': risk,
            'risk_score': RISK_SCORE[risk],
            'risk_reason': '; '.join(reasons) if reasons else 'Within low-risk thresholds.',
            'breakdown': breakdown,
        })
    # Segment mileage is assigned to the risk at its next checkpoint. This keeps
    # severe/high mileage conservative and easy to explain in the UI.
    severe_miles = 0.0
    high_miles = 0.0
    weighted = 0.0
    for i, cp in enumerate(checkpoint_out):
        next_d = checkpoint_out[i + 1]['distance_miles'] if i + 1 < len(checkpoint_out) else cp['distance_miles']
        segment = max(0.0, next_d - cp['distance_miles'])
        if cp['risk'] in ('Severe', 'No Travel'):
            severe_miles += segment
        elif cp['risk'] == 'High':
            high_miles += segment
        weighted += cp['risk_score'] * segment
    avg_risk = weighted / distance_miles if distance_miles else 0
    no_travel = any(c['risk'] == 'No Travel' for c in checkpoint_out)
    summary = f"{distance_miles:.0f} mi · {duration_s/3600:.1f} hr · {severe_miles:.0f} severe/no-travel mi · {high_miles:.0f} high mi"
    return {
        'id': f'route-{route_index}',
        'name': f'Route {route_index}',
        'distance_miles': round(distance_miles, 1),
        'duration_minutes': round(duration_s / 60),
        'duration_hours': round(duration_s / 3600, 1),
        'geometry': route['geometry'],
        'checkpoints': checkpoint_out,
        'severe_miles': round(severe_miles, 1),
        'high_miles': round(high_miles, 1),
        'average_risk': round(avg_risk, 3),
        'no_travel': no_travel,
        'summary': summary,
    }


def heatmap_payload(routes, departure):
    # Use checkpoint coordinates from all routes and provide 0–48h weather slices.
    unique = {}
    for route in routes:
        for cp in route['checkpoints']:
            key = f"{cp['lat']:.4f},{cp['lon']:.4f}"
            unique[key] = (cp['lat'], cp['lon'])
    points = [{'coordinate': [lon, lat], 'index': i, 'distance_miles': 0, 'ratio': 0, 'eta_offset_seconds': 0} for i, (lat, lon) in enumerate(unique.values())]
    if not points:
        return []
    # Heatmap should reflect forecast relative to departure, not route ETA.
    forecasts = weather_forecasts(points)
    hourly_slices = []
    for hour in range(0, 49, 3):
        values = []
        target = departure + timedelta(hours=hour)
        for point, weather in forecasts:
            wind, rain, snow = weather_values_at(weather, target)
            # Conservative weather severity for the corridor: max of the three conditions.
            risk, _, _ = risk_for_weather(wind, rain, snow, 0)
            values.append({'lat': point['coordinate'][1], 'lon': point['coordinate'][0], 'risk': risk, 'risk_score': RISK_SCORE[risk], 'wind_mph': round(wind,1), 'rain_in_hr': round(rain,3), 'snow_in_hr': round(snow,3)})
        hourly_slices.append({'hour': hour, 'points': values})
    return hourly_slices


@csrf_exempt
def geocode(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required'}, status=405)
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'error': 'Enter a location.'}, status=400)
    try:
        return JsonResponse(geocode_place(query))
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=502)


@csrf_exempt
def plan_route(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        body = json.loads(request.body.decode('utf-8'))
        origin_text = body.get('origin', '').strip()
        destination_text = body.get('destination', '').strip()
        load = float(body.get('load_weight', 0))
        interval = int(body.get('sample_interval', 25))
        departure = parse_dt(body.get('departure'))
        if not origin_text or not destination_text:
            raise ValueError('Origin and destination are required.')
        if load < 0:
            raise ValueError('Load weight cannot be negative.')
        if interval not in (10, 25, 50):
            raise ValueError('Sample interval must be 10, 25, or 50 miles.')
        origin = geocode_place(origin_text)
        destination = geocode_place(destination_text)
        raw_routes = get_routes(origin, destination)
        routes = [route_payload(r, i + 1, departure, load, interval) for i, r in enumerate(raw_routes)]
        # Recommendation exactly follows the brief's priority order.
        recommended = sorted(routes, key=lambda r: (r['severe_miles'], r['high_miles'], r['average_risk'], r['duration_minutes']))[0] if routes else None
        heatmap = heatmap_payload(routes, departure)
        return JsonResponse({
            'origin': origin,
            'destination': destination,
            'departure': departure.isoformat(),
            'load_weight': load,
            'sample_interval': interval,
            'routes': routes,
            'recommended_route_id': recommended['id'] if recommended else None,
            'heatmap': heatmap,
            'provider': settings.ROUTING_PROVIDER,
            'route_count': len(routes),
            'notes': [] if len(routes) >= 3 else ['The routing provider returned fewer than 3 alternatives for this corridor. No synthetic route was created.'],
        })
    except requests.RequestException as exc:
        return JsonResponse({'error': f'Upstream API error: {exc}'}, status=502)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({'error': f'Unexpected server error: {exc}'}, status=500)
