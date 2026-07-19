import React, { useState } from 'react'
import {
  MATERIAL_OPTIONS,
  ROOM_USE_OPTIONS,
  STYLE_OPTIONS,
  makeRequirementsDraft,
  toggleValue,
  updateRequirementRoom,
  validateRequirementsDraft,
} from './requirements.js'

function CountField({ id, label, value, onChange, disabled }) {
  return (
    <label className="requirements-count" htmlFor={id}>
      <span>{label}</span>
      <input
        id={id}
        type="number"
        min="0"
        max="30"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}

function ChoicePills({ options, values, onChange, disabled }) {
  return (
    <div className="requirements-pills">
      {options.map(([value, label]) => (
        <label key={value}>
          <input
            type="checkbox"
            checked={values.includes(value)}
            disabled={disabled}
            onChange={() => onChange(toggleValue(values, value))}
          />
          <span>{label}</span>
        </label>
      ))}
    </div>
  )
}

export default function RequirementsQuestionnaire({
  rooms,
  initial,
  styles = STYLE_OPTIONS,
  catalogItems = [],
  busy = false,
  onAnalyze,
  onConfirm,
  onBack,
}) {
  const [draft, setDraft] = useState(() => makeRequirementsDraft(rooms, initial))
  const [suggestion, setSuggestion] = useState(null)
  const [reviewed, setReviewed] = useState(false)
  const [localError, setLocalError] = useState(null)

  const changeDraft = (next) => {
    setDraft(next)
    setSuggestion(null)
    setReviewed(false)
    setLocalError(null)
  }

  const analyze = async () => {
    const validation = validateRequirementsDraft(draft)
    if (validation) {
      setLocalError(validation)
      return
    }
    setLocalError(null)
    try {
      const result = await onAnalyze(draft)
      setSuggestion(result)
      setReviewed(false)
    } catch (reason) {
      setLocalError(reason.message || String(reason))
    }
  }

  const confirm = async () => {
    if (!suggestion || !reviewed) return
    setLocalError(null)
    try {
      await onConfirm(draft, suggestion)
    } catch (reason) {
      setLocalError(reason.message || String(reason))
    }
  }

  const roomLabels = new Map(draft.room_requirements.map((room) => [room.room_id, room.label_zh]))
  const advanced = draft.customization_mode === 'advanced'
  const openrouter = suggestion?.openrouter || {}

  return (
    <main className="requirements-shell">
      <header className="requirements-header">
        <div>
          <p className="eyebrow">ROOMPILOT · 02</p>
          <h2>針對性需求問卷</h2>
          <p>先填必需的居住資訊，再決定是否展開逐房客製。AI 只整理自由文字，最後一定由你確認。</p>
        </div>
        <div className="requirements-progress">空間已確認<br /><strong>{rooms.length} 個房間</strong></div>
      </header>

      <div className="requirements-layout">
        <section className="requirements-form-card" aria-label="需求問卷">
          <div className="requirements-section-heading">
            <span>01</span><div><h3>基礎必填</h3><p>這些欄位直接轉成 JSON，不會送到 LLM。</p></div>
          </div>

          <fieldset className="requirements-fieldset" disabled={busy}>
            <legend>風格方向 *</legend>
            <div className="style-choice-grid">
              {styles.map((style) => (
                <label key={style.style_id} className={draft.style_id === style.style_id ? 'selected' : ''}>
                  <input
                    type="radio"
                    name="style-id"
                    value={style.style_id}
                    checked={draft.style_id === style.style_id}
                    onChange={() => changeDraft({ ...draft, style_id: style.style_id })}
                  />
                  <strong>{style.style_name_zh}</strong>
                  <small>{(style.keywords_zh || []).slice(0, 3).join(' · ') || '風格偏好'}</small>
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset className="requirements-fieldset" disabled={busy}>
            <legend>居住成員 *</legend>
            <div className="requirements-count-grid">
              {[
                ['adults', '成人'], ['children', '兒童'], ['elderly', '長者'], ['pets', '寵物'],
              ].map(([key, label]) => (
                <CountField
                  key={key}
                  id={`occupants-${key}`}
                  label={label}
                  value={draft.occupants[key]}
                  disabled={busy}
                  onChange={(value) => changeDraft({
                    ...draft,
                    occupants: { ...draft.occupants, [key]: value },
                  })}
                />
              ))}
            </div>
          </fieldset>

          <div className="requirements-section-heading requirements-second">
            <span>02</span><div><h3>客製深度</h3><p>一般案採用房型預設值；有特殊材質、機能或指定型號時再展開。</p></div>
          </div>
          <div className="customization-choice" role="radiogroup" aria-label="客製深度">
            <label className={!advanced ? 'selected' : ''}>
              <input
                type="radio"
                name="customization-mode"
                checked={!advanced}
                disabled={busy}
                onChange={() => changeDraft({ ...draft, customization_mode: 'default', allow_openrouter: false })}
              />
              <strong>套用房型預設值</strong>
              <small>快速完成，隱藏進階欄位</small>
            </label>
            <label className={advanced ? 'selected' : ''}>
              <input
                type="radio"
                name="customization-mode"
                checked={advanced}
                disabled={busy}
                onChange={() => changeDraft({ ...draft, customization_mode: 'advanced' })}
              />
              <strong>展開進階探討</strong>
              <small>逐房設定機能、材質與指定家具</small>
            </label>
          </div>

          {!advanced && (
            <div className="requirements-default-note">
              已依 {draft.room_requirements.length} 個房型帶入主要機能；隱藏的進階欄位不會送出。
            </div>
          )}

          {advanced && (
            <div className="room-requirements-list">
              {draft.room_requirements.map((room, index) => (
                <article key={room.room_id} className="room-requirement-card">
                  <header><span>{String(index + 1).padStart(2, '0')}</span><div><h4>{room.label_zh}</h4><small>{room.room_id}</small></div></header>
                  <div className="requirements-control">
                    <strong>主要使用方式</strong>
                    <ChoicePills
                      options={ROOM_USE_OPTIONS[room.room_type] || ROOM_USE_OPTIONS.other}
                      values={room.uses}
                      disabled={busy}
                      onChange={(uses) => changeDraft(updateRequirementRoom(draft, room.room_id, { uses }))}
                    />
                  </div>
                  <div className="requirements-control">
                    <strong>特殊材質條件</strong>
                    <ChoicePills
                      options={MATERIAL_OPTIONS}
                      values={room.special_materials}
                      disabled={busy}
                      onChange={(special_materials) => changeDraft(
                        updateRequirementRoom(draft, room.room_id, { special_materials }),
                      )}
                    />
                  </div>
                  <label className="requirements-control">
                    <strong>指定家具型號（選填）</strong>
                    <select
                      multiple
                      value={room.required_furniture_ids}
                      disabled={busy || !catalogItems.length}
                      onChange={(event) => changeDraft(updateRequirementRoom(draft, room.room_id, {
                        required_furniture_ids: [...event.target.selectedOptions].map((option) => option.value),
                      }))}
                    >
                      {catalogItems.map((item) => (
                        <option key={item.furniture_id} value={item.furniture_id}>
                          {item.name_zh || item.name_en || item.furniture_id}
                        </option>
                      ))}
                    </select>
                    <small>只列出目前有 GLB 的型錄品項；按 Ctrl／⌘ 可複選。</small>
                  </label>
                  <label className="requirements-control">
                    <strong>此空間的特殊說明</strong>
                    <textarea
                      rows="2"
                      maxLength="1000"
                      value={room.special_notes}
                      disabled={busy}
                      placeholder="例如：書桌需要容納雙螢幕，輪椅需能靠近床側"
                      onChange={(event) => changeDraft(updateRequirementRoom(draft, room.room_id, {
                        special_notes: event.target.value,
                      }))}
                    />
                  </label>
                </article>
              ))}

              <label className="requirements-control whole-house-notes">
                <strong>全屋特殊需求</strong>
                <textarea
                  rows="4"
                  maxLength="4000"
                  value={draft.special_notes}
                  disabled={busy}
                  placeholder="例如：孩子對粉塵過敏、長者使用助行器、貓咪需要耐抓材質"
                  onChange={(event) => changeDraft({ ...draft, special_notes: event.target.value })}
                />
              </label>
              <label className="requirements-ai-consent">
                <input
                  type="checkbox"
                  checked={draft.allow_openrouter}
                  disabled={busy}
                  onChange={(event) => changeDraft({ ...draft, allow_openrouter: event.target.checked })}
                />
                <span><strong>允許將上述自由文字送到 OpenRouter 整理成 JSON</strong><small>勾選項、居住人數與指定型號不需要 LLM；未勾選時使用本機規則。</small></span>
              </label>
            </div>
          )}

          {localError && <div className="requirements-error" role="alert">{localError}</div>}
          <div className="requirements-actions">
            <button type="button" onClick={onBack} disabled={busy}>返回空間確認</button>
            <button className="requirements-analyze" type="button" onClick={analyze} disabled={busy}>
              {busy ? '整理中…' : '整理需求建議'}
            </button>
          </div>
        </section>

        <aside className="requirements-review-card" aria-live="polite">
          <div className="requirements-section-heading"><span>03</span><div><h3>確認後才完成</h3><p>修改任何答案後，都必須重新整理與確認。</p></div></div>
          {!suggestion ? (
            <div className="requirements-review-empty">完成左側問卷後，點「整理需求建議」。</div>
          ) : (
            <>
              <div className={`requirements-source ${suggestion.source}`}>
                {suggestion.source === 'openrouter' ? 'OpenRouter 建議' : '本機規則建議'}
                {suggestion.model && <small>{suggestion.model}</small>}
              </div>
              <p className="requirements-summary">{suggestion.summary_zh}</p>
              {openrouter.requested && openrouter.status !== 'suggested' && (
                <div className="requirements-ai-fallback">
                  {openrouter.status === 'skipped_no_text'
                    ? '沒有自由文字，本次不需外送 OpenRouter。'
                    : 'OpenRouter 本次未回傳可用結果，已降級為本機規則。'}
                </div>
              )}
              <div className="constraint-list">
                {suggestion.constraints.length ? suggestion.constraints.map((constraint, index) => (
                  <div key={`${constraint.type}-${constraint.room_id || 'all'}-${index}`} className={`constraint-item ${constraint.priority}`}>
                    <strong>{constraint.description_zh}</strong>
                    <small>
                      {constraint.room_id ? roomLabels.get(constraint.room_id) || constraint.room_id : '全屋'}
                      {' · '}{constraint.priority === 'high' ? '高優先' : constraint.priority === 'low' ? '低優先' : '一般'}
                    </small>
                  </div>
                )) : <div className="constraint-empty">無額外限制，將採用房型預設機能。</div>}
              </div>
              <label className="requirements-final-check">
                <input type="checkbox" checked={reviewed} disabled={busy} onChange={(event) => setReviewed(event.target.checked)} />
                我已檢查居住人數、逐房需求與特殊限制，確認內容正確。
              </label>
              <button
                className="requirements-confirm"
                type="button"
                disabled={busy || !reviewed}
                onClick={confirm}
              >
                {busy ? '儲存中…' : '確認需求並進入佈局'}
              </button>
            </>
          )}
        </aside>
      </div>
    </main>
  )
}
