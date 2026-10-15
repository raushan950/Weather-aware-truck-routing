import { useMemo, useState } from 'react'
import { AlertCircle, ArrowRight, CalendarClock, ChevronRight, CloudSun, Gauge, Layers3, Map, RefreshCw, Route, ShieldCheck, Truck, Wind } from 'lucide-react'
import MapView from './components/MapView'
import RouteCard from './components/RouteCard'
import CheckpointTable from './components/CheckpointTable'
import { planTrip } from './lib/api'

function localDateTimeValue(date = new Date(Date.now() + 60 * 60 * 1000)) {
  const pad = n => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const initialForm = {origin: '', destination: '', departure: localDateTimeValue(), load_weight: '30000', sample_interval: '25'}

function RiskPill({score, label}) {
  return <span className={`risk-badge ${['low','moderate','high','severe','no-travel'][score]}`}>{label}</span>
}

export default function App() {
  const [form, setForm] = useState(initialForm)
  const [result, setResult] = useState(null)
  const [activeRouteId, setActiveRouteId] = useState(null)
  const [heatHour, setHeatHour] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [checkpointsVisible, setCheckpointsVisible] = useState(true)

  const activeRoute = useMemo(() => result?.routes?.find(r => r.id === activeRouteId) || result?.routes?.find(r => r.id === result.recommended_route_id) || result?.routes?.[0], [result, activeRouteId])
  const heatmapPoints = useMemo(() => result?.heatmap?.find(h => h.hour === heatHour)?.points || [], [result, heatHour])

  async function submit(e) {
    e.preventDefault()
    setLoading(true); setError('')
    try {
      const payload = {...form, load_weight: Number(form.load_weight), sample_interval: Number(form.sample_interval), departure: new Date(form.departure).toISOString()}
      const data = await planTrip(payload)
      setResult(data)
      setActiveRouteId(data.recommended_route_id || data.routes?.[0]?.id)
      setHeatHour(0)
    } catch (err) {
      setError(err.message)
    } finally { setLoading(false) }
  }

  function update(k, v) { setForm(f => ({...f, [k]: v})) }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><div className="brand-mark"><span/><span/><span/></div><div><strong>spotter</strong><small>weather-aware routing</small></div></div>
        <div className="topbar-status"><span className="live-dot"/> Forecast engine online <span className="separator"/> OpenStreetMap + Open-Meteo</div>
      </header>

      <main>
        <section className="hero">
          <div>
            <div className="eyebrow"><ShieldCheck size={15}/> SAFETY-FIRST FREIGHT PLANNING</div>
            <h1>Route the load.<br/><em>Respect the weather.</em></h1>
            <p>Compare three driving corridors with checkpoint-level forecast risk, load-aware wind rules, ETAs and a 48-hour weather corridor.</p>
          </div>
          <div className="hero-stat"><span>Decision order</span><b>Severe → High → Avg. risk → Time</b><small>Matches the assessment recommendation priority.</small></div>
        </section>

        <section className="planner-card">
          <form onSubmit={submit}>
            <div className="form-grid">
              <label><span>Origin</span><div className="input-wrap"><Map size={17}/><input required value={form.origin} onChange={e=>update('origin',e.target.value)} placeholder="e.g. Denver, CO"/></div></label>
              <div className="direction"><ArrowRight size={18}/></div>
              <label><span>Destination</span><div className="input-wrap"><Map size={17}/><input required value={form.destination} onChange={e=>update('destination',e.target.value)} placeholder="e.g. Dallas, TX"/></div></label>
              <label><span>Departure</span><div className="input-wrap"><CalendarClock size={17}/><input type="datetime-local" required value={form.departure} onChange={e=>update('departure',e.target.value)}/></div></label>
              <label><span>Load weight <small>(lb)</small></span><div className="input-wrap"><Truck size={17}/><input type="number" min="0" step="100" required value={form.load_weight} onChange={e=>update('load_weight',e.target.value)}/></div></label>
              <label><span>Weather checkpoints</span><div className="segmented">{[10,25,50].map(n=><button type="button" key={n} className={Number(form.sample_interval)===n?'active':''} onClick={()=>update('sample_interval', String(n))}>{n} mi</button>)}</div></label>
              <button className="primary-button" disabled={loading}>{loading ? <><RefreshCw className="spin" size={18}/> Calculating</> : <><Route size={18}/> Find safest route</>}</button>
            </div>
          </form>
          {error && <div className="error-banner"><AlertCircle size={17}/>{error}</div>}
          <div className="rules-line"><Wind size={15}/> Wind ≥55 mph = no travel · 45–54 mph + &gt;30,000 lb = no travel · 35–44 mph + &gt;40,000 lb = severe</div>
        </section>

        {!result && !loading && <section className="empty-state"><div className="empty-icon"><CloudSun size={34}/></div><h2>Build a weather-aware trip plan</h2><p>Enter your corridor, departure and payload. The engine will route the trip, sample weather using checkpoint ETAs and rank the alternatives.</p><div className="empty-grid"><div><Gauge/><b>Risk engine</b><span>Wind, rain and snow thresholds + load rules</span></div><div><Layers3/><b>Corridor heatmap</b><span>Forecast snapshots from 0 to 48 hours</span></div><div><ShieldCheck/><b>Recommendation</b><span>Strict safety-first ranking</span></div></div></section>}

        {loading && <section className="loading-state"><div className="loader-ring"/><h2>Building your trip model</h2><p>Geocoding locations · finding alternatives · sampling forecast checkpoints</p></section>}

        {result && !loading && <>
          {result.notes?.map(n => <div className="info-banner" key={n}><AlertCircle size={16}/>{n}</div>)}
          <section className="results-head">
            <div><div className="eyebrow">ROUTE DECISION</div><h2>{result.origin.label.split(',').slice(0,2).join(',')} <ChevronRight size={21}/> {result.destination.label.split(',').slice(0,2).join(',')}</h2><p>{result.routes.length} provider route option{result.routes.length===1?'':'s'} · {result.sample_interval} mile weather sampling · {Number(result.load_weight).toLocaleString()} lb load</p></div>
            <div className="recommendation"><span>Safest available</span><b>{activeRoute?.name}</b><small>Prioritizes severe miles first</small></div>
          </section>

          <section className="dashboard-grid">
            <div className="map-panel">
              <div className="panel-header"><div><h3>Trip corridor</h3><span>Weather risk overlay · forecast + checkpoint ETAs</span></div><label className="toggle"><input type="checkbox" checked={checkpointsVisible} onChange={e=>setCheckpointsVisible(e.target.checked)}/><span/> Checkpoints</label></div>
              <MapView routes={result.routes} recommendedId={result.recommended_route_id} activeRouteId={activeRouteId} heatmapPoints={heatmapPoints} checkpointsVisible={checkpointsVisible}/>
              <div className="heat-controls"><div><b>Weather heatmap</b><span>Forecast hour</span></div><output>{heatHour}h</output><input type="range" min="0" max="48" step="3" value={heatHour} onChange={e=>setHeatHour(Number(e.target.value))}/><div className="heat-scale"><span>0h</span><span>12h</span><span>24h</span><span>36h</span><span>48h</span></div></div>
            </div>
            <aside className="side-panel">
              <div className="panel-header"><div><h3>Route alternatives</h3><span>Click a route to inspect checkpoints</span></div></div>
              <div className="route-list">{result.routes.map(route=><RouteCard key={route.id} route={route} recommended={route.id===result.recommended_route_id} selected={route.id===activeRoute?.id} onClick={()=>setActiveRouteId(route.id)}/>)}</div>
            </aside>
          </section>

          <section className="detail-panel">
            <div className="panel-header"><div><h3>{activeRoute?.name} · checkpoint forecast</h3><span>Weather is evaluated at the truck's estimated arrival time at each checkpoint.</span></div><div className="detail-badges"><RiskPill score={Math.max(...(activeRoute?.checkpoints||[]).map(c=>c.risk_score),0)} label="Peak route risk"/></div></div>
            <CheckpointTable route={activeRoute}/>
          </section>
        </>}
      </main>
      <footer><span>Risk rules are applied exactly as specified.</span></footer>
    </div>
  )
}
