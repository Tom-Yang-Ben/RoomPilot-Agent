import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  clientPointToLayout,
  layoutView,
  moveLayoutObject,
  polygonPath,
  rotateLayoutObject,
} from './layout2d.js'

const ROOM_LABELS = {
  living_room: '客廳', dining_room: '餐廳', bedroom: '臥室', study: '書房',
  kitchen: '廚房', bathroom: '浴室', toilet: '廁所', entry: '玄關',
  corridor: '走廊', balcony: '陽台／露台', storage: '儲藏室', laundry: '洗衣間', other: '其他空間',
}

function roomLabel(room) {
  return room.label_zh || ROOM_LABELS[room.room_type] || room.room_id
}

function segmentLine(segment) {
  return {
    x1: Number(segment.x1), z1: Number(segment.z1),
    x2: Number(segment.x2), z2: Number(segment.z2),
  }
}

export default function Layout2DReview({
  floorplan,
  busy = false,
  onAnalyze,
  onValidate,
  onConfirm,
  onBack,
}) {
  const rooms = floorplan?.room_regions || []
  const view = useMemo(() => layoutView(floorplan), [floorplan])
  const [allowOpenrouter, setAllowOpenrouter] = useState(false)
  const [proposal, setProposal] = useState(null)
  const [objects, setObjects] = useState([])
  const [selectedRoomId, setSelectedRoomId] = useState(rooms[0]?.room_id || '')
  const [selectedId, setSelectedId] = useState(null)
  const [reviewed, setReviewed] = useState(false)
  const [notice, setNotice] = useState('先產生一版配置；所有家具座標都會由幾何引擎計算。')
  const [localBusy, setLocalBusy] = useState(false)
  const objectsRef = useRef(objects)
  const dragRef = useRef(null)
  objectsRef.current = objects

  useEffect(() => {
    if (!rooms.some((room) => room.room_id === selectedRoomId)) {
      setSelectedRoomId(rooms[0]?.room_id || '')
    }
  }, [rooms, selectedRoomId])

  const selected = objects.find((item) => item.instance_id === selectedId)
  const visibleObjects = objects.filter((item) => item.placement_room_id === selectedRoomId)
  const failedCount = objects.filter((item) => item.placement_failed).length

  const analyze = async () => {
    setLocalBusy(true)
    setNotice('正在依逐房需求選件並計算合法位置…')
    try {
      const next = await onAnalyze(allowOpenrouter)
      setProposal(next)
      setObjects(next.scene_objects || [])
      setReviewed(false)
      setSelectedId(null)
      setNotice(next.summary_zh || '配置已產生，請逐房確認。')
    } catch (error) {
      setNotice(`配置未產生：${error.message}`)
    } finally {
      setLocalBusy(false)
    }
  }

  const validateChange = async (before, candidate, instanceId, successMessage) => {
    setLocalBusy(true)
    try {
      const result = await onValidate(candidate, instanceId)
      if (!result.ok) {
        setObjects(before)
        setNotice(`位置未套用：${result.reason || '未通過碰撞與淨空檢查'}`)
        return false
      }
      setObjects(candidate.map((item) => item.instance_id === instanceId
        ? { ...item, placement_failed: false, placement_reason: null }
        : item))
      setReviewed(false)
      setNotice(successMessage)
      return true
    } catch (error) {
      setObjects(before)
      setNotice(`位置未套用：${error.message}`)
      return false
    } finally {
      setLocalBusy(false)
    }
  }

  const beginDrag = (event, item) => {
    if (busy || localBusy) return
    event.preventDefault()
    event.stopPropagation()
    event.currentTarget.setPointerCapture?.(event.pointerId)
    setSelectedId(item.instance_id)
    dragRef.current = {
      instanceId: item.instance_id,
      before: objectsRef.current,
      pointerId: event.pointerId,
      captureTarget: event.currentTarget,
      latest: objectsRef.current,
    }
  }

  const moveDrag = (event) => {
    const drag = dragRef.current
    if (!drag || !view) return
    const svg = event.currentTarget.ownerSVGElement || event.currentTarget
    const point = clientPointToLayout(
      { x: event.clientX, y: event.clientY },
      svg.getBoundingClientRect(),
      view,
    )
    if (!point) return
    const next = moveLayoutObject(objectsRef.current, drag.instanceId, point)
    drag.latest = next
    setObjects(next)
  }

  const finishDrag = async (event) => {
    const drag = dragRef.current
    if (!drag) return
    drag.captureTarget?.releasePointerCapture?.(drag.pointerId)
    dragRef.current = null
    await validateChange(drag.before, drag.latest, drag.instanceId, '家具位置已通過房間、碰撞、門口與淨空檢查。')
  }

  const rotateSelected = async () => {
    if (!selected) return
    const before = objectsRef.current
    const next = rotateLayoutObject(before, selected.instance_id)
    setObjects(next)
    await validateChange(before, next, selected.instance_id, '家具已旋轉 90° 並通過配置檢查。')
  }

  const removeSelected = () => {
    if (!selected || selected.user_required) return
    setObjects((current) => current.filter((item) => item.instance_id !== selected.instance_id))
    setSelectedId(null)
    setReviewed(false)
    setNotice('已移除這件建議家具；指定型號家具不會允許移除。')
  }

  const confirm = async () => {
    if (!proposal || !reviewed || failedCount) return
    setLocalBusy(true)
    try {
      await onConfirm(proposal, objects)
    } catch (error) {
      setNotice(`配置尚未確認：${error.message}`)
    } finally {
      setLocalBusy(false)
    }
  }

  if (!view) return <div className="layout-empty">沒有可用的平面圖範圍，請返回空間確認。</div>

  const activeRoom = rooms.find((room) => room.room_id === selectedRoomId)
  const status = proposal?.openrouter
  const aiStatus = status?.sent
    ? status.status === 'suggested'
      ? `已採用 OpenRouter 選件／語意建議${status.model ? `（${status.model}）` : ''}`
      : '已嘗試 OpenRouter；未取得合法回應，已自動改用本地規則。'
    : '本次未將配置資料送到 OpenRouter。'

  return (
    <main className="layout-shell">
      <header className="layout-header">
        <div>
          <p className="eyebrow">ROOMPILOT · 05</p>
          <h2>AI 自動配置 2D 家具</h2>
          <p>一次只產生一版。AI 可選型號與提供擺位意圖；實際公分座標由家具引擎計算，確認後才進入 3D。</p>
        </div>
        <button type="button" className="review-back" onClick={onBack} disabled={busy || localBusy}>返回需求問卷</button>
      </header>

      {!proposal && (
        <section className="layout-generate-card">
          <h3>產生配置建議</h3>
          <p>問卷中指定的家具型號會鎖定保留；系統再依房型補齊核心搭配家具。</p>
          <label className="ai-consent">
            <span>
              <input
                type="checkbox"
                checked={allowOpenrouter}
                disabled={busy || localBusy}
                onChange={(event) => setAllowOpenrouter(event.target.checked)}
              />
              允許將房型、需求限制與候選家具 ID 送到 OpenRouter取得配置建議
            </span>
            <small>不傳平面圖原檔，也不接受 AI 產生座標或型錄外家具；未勾選仍可用本地規則完成。</small>
          </label>
          <button type="button" className="layout-primary" onClick={analyze} disabled={busy || localBusy}>
            {localBusy ? '配置中…' : '產生一版 2D 配置'}
          </button>
        </section>
      )}

      {proposal && (
        <>
          <section className="layout-status-row">
            <div><strong>{proposal.summary_zh}</strong><small>{aiStatus}</small></div>
            <button type="button" onClick={analyze} disabled={busy || localBusy}>重新產生</button>
          </section>
          <nav className="layout-room-tabs" aria-label="選擇配置空間">
            {rooms.map((room) => {
              const count = objects.filter((item) => item.placement_room_id === room.room_id).length
              return (
                <button
                  type="button"
                  key={room.room_id}
                  className={selectedRoomId === room.room_id ? 'active' : ''}
                  onClick={() => { setSelectedRoomId(room.room_id); setSelectedId(null) }}
                >
                  {roomLabel(room)} <span>{count}</span>
                </button>
              )
            })}
          </nav>

          <section className="layout-workspace">
            <div className="layout-plan-card">
              <svg
                className="layout-map"
                viewBox={`${view.minx} ${view.minz} ${view.width} ${view.depth}`}
                role="img"
                aria-label={`${activeRoom ? roomLabel(activeRoom) : '空間'} 2D 家具配置`}
                preserveAspectRatio="xMidYMid meet"
                onPointerMove={moveDrag}
                onPointerUp={finishDrag}
                onPointerCancel={finishDrag}
              >
                {rooms.map((room) => (
                  <path
                    key={room.room_id}
                    d={polygonPath(room)}
                    className={room.room_id === selectedRoomId ? 'layout-room active' : 'layout-room'}
                    fillRule="evenodd"
                  />
                ))}
                {(floorplan.windows || []).map((raw, index) => {
                  const segment = segmentLine(raw)
                  return <line key={`window-${index}`} x1={segment.x1} y1={segment.z1} x2={segment.x2} y2={segment.z2} className="layout-window" />
                })}
                {(floorplan.doors || []).map((raw, index) => {
                  const segment = segmentLine(raw)
                  return <line key={`door-${index}`} x1={segment.x1} y1={segment.z1} x2={segment.x2} y2={segment.z2} className="layout-door" />
                })}
                {visibleObjects.map((item) => {
                  const size = item.size_cm || {}
                  const x = Number(item.position_cm?.x || 0) / 100
                  const z = Number(item.position_cm?.z || 0) / 100
                  const width = Number(size.width || 60) / 100
                  const depth = Number(size.depth || 60) / 100
                  const chosen = item.instance_id === selectedId
                  return (
                    <g
                      key={item.instance_id}
                      className={`layout-furniture${chosen ? ' selected' : ''}${item.placement_failed ? ' failed' : ''}`}
                      transform={`rotate(${Number(item.rotation_y_deg || 0)} ${x} ${z})`}
                      onPointerDown={(event) => beginDrag(event, item)}
                      onClick={(event) => { event.stopPropagation(); setSelectedId(item.instance_id) }}
                    >
                      <rect x={x - width / 2} y={z - depth / 2} width={width} height={depth} rx="0.04" />
                      <text
                        x={x}
                        y={z}
                        transform={`rotate(${-Number(item.rotation_y_deg || 0)} ${x} ${z})`}
                      >
                        {String(item.name_zh_raw || item.normalized_type || '家具').slice(0, 9)}
                      </text>
                      {item.user_required && <circle cx={x + width / 2 - 0.08} cy={z - depth / 2 + 0.08} r="0.07" />}
                    </g>
                  )
                })}
              </svg>
              <div className="layout-legend"><span className="required-dot" />問卷指定 <span className="door-dot" />門口 <span className="window-dot" />窗</div>
            </div>

            <aside className="layout-inspector">
              <h3>{activeRoom ? roomLabel(activeRoom) : '家具'}配置</h3>
              {!visibleObjects.length && <p className="layout-empty-room">此空間目前不需要自動配置核心家具。</p>}
              {visibleObjects.map((item) => (
                <button
                  type="button"
                  key={item.instance_id}
                  className={item.instance_id === selectedId ? 'layout-item active' : 'layout-item'}
                  onClick={() => setSelectedId(item.instance_id)}
                >
                  <strong>{item.name_zh_raw || item.normalized_type}</strong>
                  <small>{Math.round(item.size_cm.width)} × {Math.round(item.size_cm.depth)} cm · {item.user_required ? '指定型號' : '搭配建議'}</small>
                  {item.placement_failed && <em>{item.placement_reason || '尚無合法位置'}</em>}
                </button>
              ))}
              {selected && (
                <div className="layout-actions">
                  <button type="button" onClick={rotateSelected} disabled={busy || localBusy}>旋轉 90°</button>
                  <button type="button" onClick={removeSelected} disabled={busy || localBusy || selected.user_required}>移除</button>
                  <small>{selected.user_required ? '問卷指定型號不可移除，但可拖曳或旋轉。' : '拖曳放開後，後端會重新驗證房間、碰撞、門口與淨空。'}</small>
                </div>
              )}
            </aside>
          </section>

          {(proposal.warnings || []).map((warning, index) => <div className="layout-warning" key={index}>{warning}</div>)}
          <div className="layout-notice" role="status" aria-live="polite">{notice}</div>
          <section className="layout-confirm-card">
            <label>
              <input type="checkbox" checked={reviewed} disabled={busy || localBusy || failedCount > 0} onChange={(event) => setReviewed(event.target.checked)} />
              我已逐房檢查家具型號、位置與動線，確認採用這一版配置
            </label>
            {failedCount > 0 && <small>仍有 {failedCount} 件家具無合法位置，請移動、移除搭配家具，或返回問卷調整指定型號。</small>}
            <button type="button" className="layout-primary" onClick={confirm} disabled={busy || localBusy || !reviewed || failedCount > 0}>
              {localBusy ? '驗證並儲存中…' : '確認配置並進入 3D 白模'}
            </button>
          </section>
        </>
      )}

      {!proposal && <div className="layout-notice" role="status" aria-live="polite">{notice}</div>}
    </main>
  )
}
