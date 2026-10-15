import { AlertTriangle, CloudRain, Snowflake, Wind } from 'lucide-react'

function fmtTime(iso) {
  return new Date(iso).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})
}

export default function CheckpointTable({route}) {
  if (!route) return null
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>Checkpoint</th><th>ETA</th><th>Wind</th><th>Rain</th><th>Snow</th><th>Risk</th></tr></thead>
        <tbody>
          {route.checkpoints.map(cp => (
            <tr key={cp.id}>
              <td className="checkpoint"><b>{Math.round(cp.distance_miles)} mi</b><span>{cp.lat.toFixed(2)}, {cp.lon.toFixed(2)}</span></td>
              <td>{fmtTime(cp.eta)}</td>
              <td><Wind size={14}/>{cp.wind_mph} mph</td>
              <td><CloudRain size={14}/>{cp.rain_in_hr} in/hr</td>
              <td><Snowflake size={14}/>{cp.snow_in_hr} in/hr</td>
              <td><span className={`risk-badge ${['low','moderate','high','severe','no-travel'][cp.risk_score]}`}>{cp.risk}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
