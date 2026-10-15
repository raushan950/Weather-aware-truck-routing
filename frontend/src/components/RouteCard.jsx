import { Check, Clock3, MapPinned, ShieldAlert, Truck } from 'lucide-react'

function mins(m) {
  const h = Math.floor(m / 60), min = m % 60
  return `${h}h ${min}m`
}

export default function RouteCard({route, recommended, selected, onClick}) {
  return (
    <button className={`route-card ${selected ? 'selected' : ''}`} onClick={onClick}>
      <div className="route-card-top">
        <div>
          <div className="route-name">{route.name} {recommended && <span className="recommended"><Check size={13}/> Recommended</span>}</div>
          <div className="route-summary">{route.summary}</div>
        </div>
        <div className="route-score"><span>{route.average_risk.toFixed(2)}</span><small>avg risk</small></div>
      </div>
      <div className="route-metrics">
        <span><MapPinned size={15}/>{route.distance_miles} mi</span>
        <span><Clock3 size={15}/>{mins(route.duration_minutes)}</span>
        <span><ShieldAlert size={15}/>{route.severe_miles} severe mi</span>
        <span><Truck size={15}/>{route.high_miles} high mi</span>
      </div>
      {route.no_travel && <div className="warning-strip">No-travel condition detected on this route</div>}
    </button>
  )
}
