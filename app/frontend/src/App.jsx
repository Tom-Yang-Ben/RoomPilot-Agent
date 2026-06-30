import React, { useEffect, useState } from 'react'
import Scene from './Scene.jsx'

const DEFAULTS = { thickness: 0.18, height: 2.7 }

export default function App() {
  const [plans, setPlans] = useState([])
  const [name, setName] = useState('')
  const [upload, setUpload] = useState(null)      // File when user uploaded one
  const [scaleM, setScaleM] = useState(null)      // null = auto-guess on backend
  const [thickness, setThickness] = useState(DEFAULTS.thickness)
  const [height, setHeight] = useState(DEFAULTS.height)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [show, setShow] = useState({ walls: true, windows: true, doors: true, floor: true, xray: true })

  useEffect(() => {
    fetch('/api/plans')
      .then((r) => r.json())
      .then((d) => { setPlans(d.plans); if (d.plans[0]) setName(d.plans[0]) })
      .catch((e) => setError('無法連線後端 (/api/plans)：' + e.message))
  }, [])

  // (re)fetch geometry whenever the source or a knob changes (debounced)
  useEffect(() => {
    if (!name && !upload) return
    let cancelled = false
    const id = setTimeout(async () => {
      setLoading(true); setError(null)
      try {
        const qs = new URLSearchParams({ thickness, height })
        if (scaleM) qs.set('scale_m', scaleM)
        let res
        if (upload) {
          const fd = new FormData(); fd.append('file', upload)
          res = await fetch(`/api/upload?${qs}`, { method: 'POST', body: fd })
        } else {
          qs.set('name', name)
          res = await fetch(`/api/plan?${qs}`)
        }
        if (!res.ok) throw new Error((await res.json()).detail || res.statusText)
        const d = await res.json()
        if (!cancelled) setData(d)
      } catch (e) {
        if (!cancelled) setError(String(e.message || e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }, 250)
    return () => { cancelled = true; clearTimeout(id) }
  }, [name, upload, scaleM, thickness, height])

  const s = data?.stats
  const sliderScale = scaleM ?? data?.scale_m ?? 12

  return (
    <>
      <div className="panel">
        <h1>DXF → 3D 白模</h1>
        <div className="sub">ezdxf + shapely 解析牆/窗，R3F 即時呈現</div>

        <div className="field">
          <label>選擇平面圖</label>
          <select
            value={upload ? '' : name}
            onChange={(e) => { setUpload(null); setName(e.target.value); setScaleM(null) }}
          >
            {upload && <option value="">{`（上傳）${upload.name}`}</option>}
            {plans.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>

        <label className="filebtn">
          上傳 DXF…
          <input
            type="file"
            accept=".dxf"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) { setUpload(f); setScaleM(null) }
            }}
          />
        </label>

        <div className="field">
          <label>長邊實際尺寸 <b>{(+sliderScale).toFixed(1)} m</b></label>
          <input
            type="range" min="3" max="60" step="0.5" value={sliderScale}
            onChange={(e) => setScaleM(+e.target.value)}
          />
          <div className="hint">
            DXF 單位常不可靠，故以長邊校正比例（比例依據：{data?.scale_basis || '—'}）。
            {scaleM != null && <a style={{ cursor: 'pointer', color: '#4ea1ff' }}
              onClick={() => setScaleM(null)}> 重設為自動</a>}
          </div>
        </div>

        <div className="field">
          <label>牆厚 <b>{thickness.toFixed(2)} m</b></label>
          <input type="range" min="0.05" max="0.5" step="0.01" value={thickness}
            onChange={(e) => setThickness(+e.target.value)} />
          <div className="hint">調大可合併雙線牆。</div>
        </div>

        <div className="field">
          <label>樓高 <b>{height.toFixed(2)} m</b></label>
          <input type="range" min="2" max="4" step="0.05" value={height}
            onChange={(e) => setHeight(+e.target.value)} />
        </div>

        <div className="checks">
          {['walls', 'windows', 'doors', 'floor', 'xray'].map((k) => (
            <label key={k}>
              <input type="checkbox" checked={show[k]}
                onChange={() => setShow((v) => ({ ...v, [k]: !v[k] }))} />
              {{ walls: '牆', windows: '窗', doors: '門', floor: '地板', xray: '近景穿牆' }[k]}
            </label>
          ))}
        </div>

        {error && <div className="err">⚠ {error}</div>}
        {s && (
          <div className="stats">
            尺寸 <b>{s.width_m} × {s.depth_m} m</b>（範圍 {s.extent_area} m²）<br />
            牆段 <b>{s.wall_segments}</b> · 牆體 <b>{s.wall_polys}</b><br />
            窗 <b>{s.windows}</b> · 門 <b>{s.doors}</b><br />
            比例 <b>{data.scale_m} m</b> / {data.scale_basis}
            {data.fallback_all_walls &&
              <div className="warn">⚠ 無牆圖層，已將所有線段視為牆。</div>}
          </div>
        )}
        <div className="hint">滑鼠左鍵旋轉、右鍵平移、滾輪縮放。</div>
      </div>

      <div className="canvas-wrap">
        {loading && <div className="loading">解析中…</div>}
        <Scene data={data} show={show} />
      </div>
    </>
  )
}
