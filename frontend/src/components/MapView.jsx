import { useEffect, useMemo } from 'react'
import { MapContainer, TileLayer, Polyline, CircleMarker, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet.heat'

const routeLineStyles = [
  {weight: 6, opacity: .95, dashArray: null},
  {weight: 5, opacity: .7, dashArray: '10 8'},
  {weight: 5, opacity: .65, dashArray: '4 10'},
]

function HeatLayer({points}) {
  const map = useMap()
  useEffect(() => {
    if (!map || !points?.length) return undefined
    const max = Math.max(...points.map(p => p.risk_score), 1)
    const layer = L.heatLayer(points.map(p => [p.lat, p.lon, Math.max(.15, p.risk_score / max)]), {
      radius: 28,
      blur: 24,
      maxZoom: 8,
      minOpacity: .28,
      gradient: {0.15: '#5bd6a3', 0.35: '#f4c95d', 0.6: '#f08a5d', 0.8: '#e85d75', 1: '#8b5cf6'},
    }).addTo(map)
    return () => map.removeLayer(layer)
  }, [map, points])
  return null
}

function FitBounds({routes, selectedRoute}) {
  const map = useMap()
  const geometry = selectedRoute?.geometry || routes?.[0]?.geometry
  useEffect(() => {
    if (!map || !geometry?.coordinates?.length) return
    const bounds = L.latLngBounds(geometry.coordinates.map(([lon, lat]) => [lat, lon]))
    map.fitBounds(bounds.pad(.12), {duration: .8})
  }, [map, geometry])
  return null
}

function riskClass(score) {
  return ['low', 'moderate', 'high', 'severe', 'no-travel'][score] || 'low'
}

export default function MapView({routes, recommendedId, activeRouteId, heatmapPoints, checkpointsVisible}) {
  const selected = routes?.find(r => r.id === activeRouteId) || routes?.find(r => r.id === recommendedId) || routes?.[0]
  const center = useMemo(() => {
    const c = selected?.geometry?.coordinates?.[0]
    return c ? [c[1], c[0]] : [39.5, -98.35]
  }, [selected])

  return (
    <div className="map-shell">
      <MapContainer center={center} zoom={5} scrollWheelZoom className="map">
        <TileLayer
          attribution='&copy; OpenStreetMap contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds routes={routes} selectedRoute={selected} />
        <HeatLayer points={heatmapPoints} />
        {routes?.map((route, idx) => {
          const active = route.id === selected?.id
          const positions = route.geometry.coordinates.map(([lon, lat]) => [lat, lon])
          return <Polyline key={route.id} positions={positions} pathOptions={{...routeLineStyles[idx] || routeLineStyles[2], color: active ? '#0f172a' : '#64748b', opacity: active ? 1 : .48, weight: active ? 7 : 4}} />
        })}
        {checkpointsVisible && selected?.checkpoints?.map(cp => (
          <CircleMarker key={cp.id} center={[cp.lat, cp.lon]} radius={6} pathOptions={{color: '#fff', weight: 2, fillColor: ['#36c98f','#f3bd3d','#f08a5d','#e85d75','#7c3aed'][cp.risk_score], fillOpacity: 1}}>
          </CircleMarker>
        ))}
      </MapContainer>
      <div className="map-legend">
        <span><i className="dot low"/> Low</span><span><i className="dot moderate"/> Moderate</span><span><i className="dot high"/> High</span><span><i className="dot severe"/> Severe</span><span><i className="dot no-travel"/> No travel</span>
      </div>
    </div>
  )
}
