export async function planTrip(payload) {
  const base = import.meta.env.VITE_API_BASE_URL || ''
  const response = await fetch(`${base}/api/plan/`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  })
  const data = await response.json()
  if (!response.ok) throw new Error(data.error || 'Unable to calculate route plan.')
  return data
}
