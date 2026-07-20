import React, { useMemo, useState } from 'react'
import {
  addDraftSegment,
  clientPointToViewBox,
  removeDraftSegment,
  snapPointToWall,
  updateDraftRoomType,
  wallSnapSegments,
} from './floorplanReview.js'

const SOURCE_LABELS = {
  dxf_text: 'DXF 文字',
  ai_suggestion: 'OpenRouter 建議',
  geometry: '離線幾何',
  user_confirmation: '使用者確認',
}

function polygonPath(region) {
  const rings = [region.exterior, ...(region.holes || [])]
  return rings
    .filter((ring) => ring?.length)
    .map((ring) => `M ${ring.map(([x, z]) => `${x} ${z}`).join(' L ')} Z`)
    .join(' ')
}

function sourceLabel(source) {
  return SOURCE_LABELS[source] || '辨識建議'
}

export default function FloorplanReview({
  draft,
  onChange,
  onConfirm,
  busy = false,
  openrouter = null,
  calibration = null,
  onCalibrate,
  calibrationBusy = false,
}) {
  const [drawMode, setDrawMode] = useState(null)
  const [pendingPoint, setPendingPoint] = useState(null)
  const [selectedSegment, setSelectedSegment] = useState(null)
  const [scaleLine, setScaleLine] = useState(null)
  const [actualLengthCm, setActualLengthCm] = useState('')
  const [draggingScaleEndpoint, setDraggingScaleEndpoint] = useState(null)
  const [scaleNotice, setScaleNotice] = useState('比例線端點只會吸附在已辨識的牆線上。')
  const bbox = draft?.bbox
  const snapSegments = useMemo(() => wallSnapSegments(draft || {}), [draft])
  const view = useMemo(() => {
    if (!bbox) return null
    const width = Math.max(0.1, bbox.maxx - bbox.minx)
    const depth = Math.max(0.1, bbox.maxz - bbox.minz)
    const padding = Math.max(width, depth) * 0.05
    return {
      minx: bbox.minx - padding,
      minz: bbox.minz - padding,
      width: width + padding * 2,
      depth: depth + padding * 2,
      stroke: Math.max(width, depth) * 0.018,
    }
  }, [bbox])

  if (!draft || !view) {
    return <div className="review-empty">沒有可供確認的平面幾何，請重新辨識。</div>
  }

  const svgPoint = (event) => {
    const rect = event.currentTarget.getBoundingClientRect()
    return clientPointToViewBox(
      { x: event.clientX, y: event.clientY },
      rect,
      view,
    )
  }

  const drawSegment = (event) => {
    if (!drawMode || busy) return
    const rawPoint = svgPoint(event)
    const snapped = drawMode === 'scale'
      ? snapPointToWall(
        draft,
        rawPoint,
        Math.max(0.08, Math.max(view.width, view.depth) * 0.04),
        pendingPoint?.wall_index ?? null,
      )
      : null
    if (drawMode === 'scale' && !snapped) {
      setScaleNotice('沒有吸附到牆線，請靠近已辨識的牆再點一次。')
      return
    }
    const point = snapped
      ? { x: snapped.x, z: snapped.z, wall_index: snapped.wall_index }
      : rawPoint
    if (!pendingPoint) {
      setPendingPoint(point)
      if (drawMode === 'scale') setScaleNotice('起點已吸附牆線，請沿同一面牆選擇終點。')
      return
    }
    if (drawMode === 'scale') {
      if (Math.hypot(point.x - pendingPoint.x, point.z - pendingPoint.z) < 0.05) {
        setScaleNotice('比例線至少需要 5 公分，請把終點拉得更遠。')
        return
      }
      setScaleLine({ start: pendingPoint, end: point, wall_index: pendingPoint.wall_index })
      setPendingPoint(null)
      setDrawMode(null)
      setScaleNotice('兩端已吸附牆線；可拖曳紅色端點微調，再輸入實際公分。')
      return
    }
    onChange(addDraftSegment(draft, drawMode, pendingPoint, point))
    setPendingPoint(null)
    setSelectedSegment({ feature: drawMode, index: draft[drawMode].length })
  }

  const chooseDrawMode = (mode) => {
    setDrawMode((current) => current === mode ? null : mode)
    setPendingPoint(null)
    setSelectedSegment(null)
    if (mode === 'scale') setScaleNotice('請沿已辨識的牆線點選起點與終點。')
  }

  const removeSelected = () => {
    if (!selectedSegment) return
    onChange(removeDraftSegment(draft, selectedSegment.feature, selectedSegment.index))
    setSelectedSegment(null)
  }

  const applyCalibration = async () => {
    if (!scaleLine || !(Number(actualLengthCm) > 0) || !onCalibrate) return
    const applied = await onCalibrate(scaleLine, Number(actualLengthCm))
    if (applied !== false) {
      setScaleLine(null)
      setActualLengthCm('')
    }
  }

  const beginScaleEndpointDrag = (event, endpoint) => {
    event.preventDefault()
    event.stopPropagation()
    event.currentTarget.ownerSVGElement?.setPointerCapture?.(event.pointerId)
    setDraggingScaleEndpoint(endpoint)
    setScaleNotice('拖曳中：端點只會留在這一面已選定的牆上。')
  }

  const dragScaleEndpoint = (event) => {
    if (!scaleLine || draggingScaleEndpoint == null) return
    const snapped = snapPointToWall(
      draft,
      svgPoint(event),
      Math.max(0.12, Math.max(view.width, view.depth) * 0.07),
      scaleLine.wall_index,
    )
    if (!snapped) return
    const point = { x: snapped.x, z: snapped.z, wall_index: snapped.wall_index }
    setScaleLine((current) => draggingScaleEndpoint === 'start'
      ? { ...current, start: point }
      : { ...current, end: point })
  }

  const finishScaleEndpointDrag = (event) => {
    if (draggingScaleEndpoint == null) return
    event.currentTarget.releasePointerCapture?.(event.pointerId)
    setDraggingScaleEndpoint(null)
    setScaleNotice('端點已吸附牆線；確認紅線位置後輸入實際公分。')
  }

  const measuredScaleLengthCm = scaleLine
    ? Math.hypot(
      scaleLine.end.x - scaleLine.start.x,
      scaleLine.end.z - scaleLine.start.z,
    ) * 100
    : null
  const calibrationReady = calibration?.status === 'confirmed'
  const calibratedLongEdgeCm = Number(
    calibration?.scale_cm ?? Number(calibration?.scale_m || 0) * 100,
  )

  const aiStatus = openrouter?.status === 'suggested'
    ? `已取得 OpenRouter 建議${openrouter.model ? `（${openrouter.model}）` : ''}`
    : openrouter?.requested
      ? '已允許 OpenRouter，但本次未取得可用建議；可依離線幾何手動確認。'
      : '本次未傳送至 OpenRouter，使用離線幾何與 DXF 文字建議。'

  return (
    <main className="review-shell">
      <header className="review-header">
        <div>
          <p className="eyebrow">ROOMPILOT · 02</p>
          <h2>辨識結果與真實比例確認</h2>
          <p>先檢查牆壁、門窗與空間分區，再選定一面牆完成比例校正；沒有完成校尺就不能跳到問卷。</p>
        </div>
        <div className={`ai-review-status ${openrouter?.status || 'offline'}`}>{aiStatus}</div>
      </header>

      <section className="recognition-summary" aria-label="辨識結果摘要">
        <article><small>封閉空間</small><strong>{draft.rooms.length}</strong><span>等待逐房確認</span></article>
        <article><small>辨識門</small><strong>{draft.doors.length}</strong><span>可補畫或刪除</span></article>
        <article><small>辨識窗</small><strong>{draft.windows.length}</strong><span>將形成真實窗洞</span></article>
        <article className={calibrationReady ? 'complete' : ''}><small>真實比例</small><strong>{calibrationReady ? '已設定' : '待校尺'}</strong><span>端點限同一面牆</span></article>
      </section>

      <section className="review-layout">
        <div className="review-plan-card">
          <div className="review-toolbar">
            <button type="button" className={drawMode === 'scale' ? 'active' : ''} onClick={() => chooseDrawMode('scale')}>
              ↔ 沿牆拉比例
            </button>
            <button type="button" className={drawMode === 'doors' ? 'active' : ''} onClick={() => chooseDrawMode('doors')}>
              ＋ 補畫門
            </button>
            <button type="button" className={drawMode === 'windows' ? 'active' : ''} onClick={() => chooseDrawMode('windows')}>
              ＋ 補畫窗
            </button>
            <button type="button" disabled={!selectedSegment} onClick={removeSelected}>刪除選取線段</button>
          </div>
          <p className="review-instruction">
            {drawMode
              ? `請在圖上點兩下設定${drawMode === 'scale' ? '已知牆寬' : drawMode === 'doors' ? '門' : '窗'}的兩個端點${pendingPoint ? '（已選第一點）' : ''}。`
              : '先沿辨識後牆線拉出一段已知牆寬；門窗可補畫、選取及刪除。'}
            {drawMode === 'scale' || scaleLine ? ` ${scaleNotice}` : ''}
          </p>
          <div className={`calibration-card ${calibrationReady ? 'confirmed' : ''}`}>
            <div>
              <strong>{scaleLine ? '正在設定比例' : calibrationReady ? '比例已確認' : '尚未設定實際比例'}</strong>
              <small>
                {scaleLine
                  ? `目前辨識牆線長 ${measuredScaleLengthCm.toFixed(1)} cm，請輸入這段牆的實際公分。`
                  : calibrationReady
                  ? calibration.legacy
                    ? `既有專案沿用已確認比例 · 長邊 ${calibratedLongEdgeCm.toFixed(1)} cm`
                    : `長邊 ${calibratedLongEdgeCm.toFixed(1)} cm · 參考牆寬 ${Number(calibration.actual_length_cm).toFixed(1)} cm`
                  : '請點「沿牆拉比例」，在辨識後牆線上選擇一段已知牆寬。'}
              </small>
            </div>
            <label>
              實際長度（公分）
              <input
                type="number"
                min="1"
                max="50000"
                step="0.1"
                inputMode="decimal"
                value={actualLengthCm}
                disabled={calibrationBusy}
                placeholder="例如 300"
                onChange={(event) => setActualLengthCm(event.target.value)}
              />
            </label>
            <button
              type="button"
              disabled={calibrationBusy || !scaleLine || !(Number(actualLengthCm) > 0)}
              onClick={applyCalibration}
            >
              {calibrationBusy ? '重新換算中…' : '套用比例'}
            </button>
          </div>
          <svg
            className={`review-svg${drawMode ? ' drawing' : ''}`}
            viewBox={`${view.minx} ${view.minz} ${view.width} ${view.depth}`}
            role="img"
            aria-label="平面圖辨識確認畫面"
            onClick={drawSegment}
            onPointerMove={dragScaleEndpoint}
            onPointerUp={finishScaleEndpointDrag}
            onPointerCancel={finishScaleEndpointDrag}
          >
            <rect x={bbox.minx} y={bbox.minz} width={bbox.maxx - bbox.minx} height={bbox.maxz - bbox.minz} className="review-floor" />
            {draft.rooms.map((room, index) => (
              <path
                key={room.room_id}
                d={polygonPath(room)}
                className={`review-room room-${index % 6}`}
                fillRule="evenodd"
              />
            ))}
            {draft.wall_polys.map((wall, index) => (
              <path key={`wall-${index}`} d={polygonPath(wall)} className="review-wall" fillRule="evenodd" />
            ))}
            {snapSegments.map((segment, index) => (
              <line
                key={`wall-snap-${index}`}
                data-wall-snap-index={index}
                aria-hidden="true"
                x1={segment.x1}
                y1={segment.z1}
                x2={segment.x2}
                y2={segment.z2}
                style={{ strokeWidth: view.stroke * 3.4 }}
                className={`review-wall-hit${(pendingPoint?.wall_index ?? scaleLine?.wall_index) === index ? ' selected' : ''}`}
              />
            ))}
            {draft.windows.map((segment, index) => (
              <line
                key={`window-${index}`}
                x1={segment.x1}
                y1={segment.z1}
                x2={segment.x2}
                y2={segment.z2}
                style={{ strokeWidth: view.stroke }}
                className={selectedSegment?.feature === 'windows' && selectedSegment.index === index ? 'review-window selected' : 'review-window'}
                onClick={(event) => { event.stopPropagation(); setSelectedSegment({ feature: 'windows', index }) }}
              />
            ))}
            {draft.doors.map((segment, index) => (
              <line
                key={`door-${index}`}
                x1={segment.x1}
                y1={segment.z1}
                x2={segment.x2}
                y2={segment.z2}
                style={{ strokeWidth: view.stroke }}
                className={selectedSegment?.feature === 'doors' && selectedSegment.index === index ? 'review-door selected' : 'review-door'}
                onClick={(event) => { event.stopPropagation(); setSelectedSegment({ feature: 'doors', index }) }}
              />
            ))}
            {scaleLine && (
              <g className="review-scale-line">
                <line
                  x1={scaleLine.start.x}
                  y1={scaleLine.start.z}
                  x2={scaleLine.end.x}
                  y2={scaleLine.end.z}
                  style={{ strokeWidth: view.stroke * 0.65 }}
                />
                <circle
                  data-scale-endpoint="start"
                  aria-label="比例線起點"
                  cx={scaleLine.start.x}
                  cy={scaleLine.start.z}
                  r={view.stroke * 0.85}
                  onPointerDown={(event) => beginScaleEndpointDrag(event, 'start')}
                  onClick={(event) => event.stopPropagation()}
                />
                <circle
                  data-scale-endpoint="end"
                  aria-label="比例線終點"
                  cx={scaleLine.end.x}
                  cy={scaleLine.end.z}
                  r={view.stroke * 0.85}
                  onPointerDown={(event) => beginScaleEndpointDrag(event, 'end')}
                  onClick={(event) => event.stopPropagation()}
                />
              </g>
            )}
            {draft.rooms.map((room) => (
              <text key={`label-${room.room_id}`} x={room.centroid?.x} y={room.centroid?.z} className="review-map-label">
                {draft.room_type_options.find((option) => option.value === room.room_type)?.label_zh || '其他空間'}
              </text>
            ))}
            {pendingPoint && <circle cx={pendingPoint.x} cy={pendingPoint.z} r={view.stroke * 0.75} className="review-pending" />}
          </svg>
          <div className="review-legend"><span className="door-dot" />門 {draft.doors.length}<span className="window-dot" />窗 {draft.windows.length}<span className="room-dot" />空間 {draft.rooms.length}<span className="scale-dot" />比例端點吸附牆線</div>
        </div>

        <aside className="review-room-list" aria-label="空間屬性確認">
          <h3>空間屬性</h3>
          {draft.rooms.length === 0 && <div className="review-warning">沒有辨識到封閉空間，暫時不能完成確認。</div>}
          {draft.rooms.map((room, index) => (
            <label className="review-room-row" key={room.room_id}>
              <span className={`room-swatch room-${index % 6}`} />
              <span className="room-meta">
                <strong>{room.label_zh || room.label || '未分類空間'}</strong>
                <small>{sourceLabel(room.label_source)} · {room.area_m2 ?? '—'} m² · 信心 {Math.round((room.confidence || 0) * 100)}%</small>
              </span>
              <select
                value={room.room_type}
                disabled={busy}
                aria-label={`${room.label_zh || room.label || room.room_id}房型`}
                onChange={(event) => onChange(updateDraftRoomType(draft, room.room_id, event.target.value))}
              >
                {draft.room_type_options.map((option) => (
                  <option key={option.value} value={option.value}>{option.label_zh}</option>
                ))}
              </select>
            </label>
          ))}
          <button
            className="review-confirm"
            type="button"
            disabled={busy || calibrationBusy || draft.rooms.length === 0 || !calibrationReady}
            onClick={onConfirm}
          >
            {busy ? '正在儲存確認結果…' : calibrationReady ? '確認空間，進入需求問卷 →' : '請先沿牆拉線設定比例'}
          </button>
          <p className="review-privacy">送出後，人工確認版本才會成為後續流程的正式資料；原始 AI 建議仍保留供稽核。</p>
        </aside>
      </section>
    </main>
  )
}
