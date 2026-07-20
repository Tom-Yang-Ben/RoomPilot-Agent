import React, { useCallback, useEffect, useRef, useState } from 'react'
import FloorplanReview from './FloorplanReview.jsx'
import RequirementsQuestionnaire from './RequirementsQuestionnaire.jsx'
import Layout2DReview from './Layout2DReview.jsx'
import {
  calibrationPayload,
  confirmationPayload,
  makeFloorplanReviewDraft,
} from './floorplanReview.js'
import {
  requirementsAnalyzePayload,
  requirementsConfirmationPayload,
} from './requirements.js'
import {
  layoutConfirmationPayload,
  layoutObjectsToThreeItems,
  layoutValidationPayload,
} from './layout2d.js'
import {
  whiteModelConfirmationPayload,
  whiteModelDiagnostics,
} from './whiteModel.js'
import {
  ProjectApiError,
  applyServerStyleCard,
  analyzeServerLayout,
  analyzeServerRequirements,
  analyzeServerFloorplan,
  cacheProject,
  calibrateServerFloorplan,
  confirmServerFloorplan,
  confirmServerRequirements,
  confirmServerLayout,
  confirmServerWhiteModel,
  confirmServerViewpoint,
  createServerProject,
  createServerRender,
  loadLastProjectId,
  loadProjectCache,
  loadServerProject,
  listServerRenders,
  projectIdFromLocation,
  rememberProjectId,
  saveServerWorkflow,
  setProjectInLocation,
  uploadServerFloorplan,
  validateServerLayout,
} from './project.js'
import { flattenStyleCards, viewpointConfirmationPayload } from './proposal.js'

const Scene = React.lazy(() => import('./Scene.jsx'))

const DEFAULTS = { thickness: 0.18, height: 2.7 }
const SHOW_DEFAULTS = { walls: true, windows: true, doors: true, floor: true, xray: true }
const P0_FLOORPLAN_EXTENSIONS = ['.dxf', '.png']
const MAX_FLOORPLAN_BYTES = 20 * 1024 * 1024

const WORKFLOW_STEPS = [
  { key: 'project', number: '01', label: '建立專案' },
  { key: 'floorplan', number: '02', label: '辨識與比例' },
  { key: 'requirements', number: '03', label: '需求問卷' },
  { key: 'layout', number: '04', label: '2D 配置' },
  { key: 'white', number: '05', label: '3D 白模' },
  { key: 'viewpoint', number: '06', label: '微調與視角' },
  { key: 'proposal', number: '07', label: '風格提案' },
]

function ProductHeader({ project = null, saveStatus = null, onNew = null }) {
  return (
    <header className="studio-topbar">
      <a className="studio-brand" href="/" aria-label="RoomPilot 首頁">
        <span className="studio-brand-mark" aria-hidden="true" />
        <span>RoomPilot</span>
      </a>
      <nav className="studio-nav" aria-label="主要導覽">
        <a href="/">探索功能</a>
        <a href="/styles">風格類型</a>
        <a href="/library">家具資料庫</a>
        <a className="active" href="/scene">3D 場景展示</a>
      </nav>
      {project ? (
        <div className="studio-project-pill" aria-label="目前專案">
          <span><small>目前專案</small><strong>{project.name}</strong></span>
          <i>{saveStatus}</i>
          <button type="button" onClick={onNew}>＋ 新專案</button>
        </div>
      ) : (
        <a className="studio-topbar-cta" href="#project-title">建立新專案</a>
      )}
    </header>
  )
}

function WorkflowProgress({ current }) {
  const currentIndex = Math.max(0, WORKFLOW_STEPS.findIndex((step) => step.key === current))
  return (
    <nav className="workflow-progress" aria-label="RoomPilot 使用者流程">
      <ol>
        {WORKFLOW_STEPS.map((step, index) => (
          <li
            key={step.key}
            className={index < currentIndex ? 'complete' : index === currentIndex ? 'current' : ''}
            aria-current={index === currentIndex ? 'step' : undefined}
          >
            <span>{index < currentIndex ? '✓' : step.number}</span>
            <strong>{step.label}</strong>
          </li>
        ))}
      </ol>
    </nav>
  )
}

function UploadWorkspace({
  uploadStage,
  uploadStatus,
  uploadBusy,
  storedUploadName,
  openrouterConsent,
  setOpenrouterConsent,
  thickness,
  setThickness,
  height,
  setHeight,
  onUpload,
  error,
}) {
  const recognitionActive = uploadStage === 'uploading' || uploadStage === 'analyzing'
  const sourceSaved = ['analyzing', 'review', 'ready'].includes(uploadStage)
  const milestones = [
    { label: '保存原始檔', detail: storedUploadName || '等待 DXF／PNG', state: sourceSaved ? 'done' : uploadStage === 'uploading' ? 'active' : 'pending' },
    { label: '解析牆體', detail: '建立可編輯的牆線與空間邊界', state: uploadStage === 'analyzing' ? 'active' : ['review', 'ready'].includes(uploadStage) ? 'done' : 'pending' },
    { label: '辨識門窗', detail: '標記開口並保留人工修正', state: uploadStage === 'analyzing' ? 'active' : ['review', 'ready'].includes(uploadStage) ? 'done' : 'pending' },
    { label: '空間分區', detail: '提出房型與空間屬性建議', state: uploadStage === 'analyzing' ? 'active' : ['review', 'ready'].includes(uploadStage) ? 'done' : 'pending' },
  ]

  return (
    <main className="upload-shell">
      <header className="stage-intro">
        <div>
          <p className="eyebrow">ROOMPILOT · FLOOR PLAN INTAKE</p>
          <h1>先讓空間被正確理解，<br />再開始設計。</h1>
        </div>
        <p>上傳後會清楚呈現辨識結果；你必須沿著一面已辨識的牆拉線並輸入真實距離，確認後才會進入需求問卷。</p>
      </header>

      <section className="upload-workspace">
        <div className="upload-drop-card">
          <div className="upload-card-heading">
            <span className="upload-icon" aria-hidden="true">⌁</span>
            <div><small>STEP 02</small><h2>上傳平面圖</h2></div>
          </div>
          <p>支援 DXF 與 PNG，單檔上限 20 MB。原始檔會綁定目前專案，重新開啟網址仍可續作。</p>
          <label className={`upload-dropzone${uploadBusy ? ' disabled' : ''}`}>
            <input
              type="file"
              accept=".dxf,.png,image/png,application/dxf"
              disabled={uploadBusy}
              onChange={(event) => {
                const file = event.target.files?.[0]
                event.target.value = ''
                onUpload(file)
              }}
            />
            <span className="upload-drop-graphic" aria-hidden="true"><i /><i /><i /></span>
            <strong>{uploadBusy ? '正在處理平面圖…' : '選擇 DXF 或 PNG 平面圖'}</strong>
            <small>{storedUploadName || '點擊選擇檔案，辨識完成前不會跳過任何確認步驟'}</small>
          </label>

          <label className="upload-ai-consent">
            <input
              type="checkbox"
              checked={openrouterConsent}
              disabled={uploadBusy}
              onChange={(event) => setOpenrouterConsent(event.target.checked)}
            />
            <span><strong>允許 PNG 房型辨識使用 OpenRouter</strong><small>DXF 不會外送；AI 只提建議，牆、門、窗與房型仍由你確認。</small></span>
          </label>

          <details className="upload-advanced">
            <summary>進階建模設定</summary>
            <label>預估牆厚 <b>{Math.round(thickness * 100)} cm</b>
              <input disabled={uploadBusy} type="range" min="5" max="50" step="1" value={thickness * 100}
                onChange={(event) => setThickness(+event.target.value / 100)} />
            </label>
            <label>樓高 <b>{Math.round(height * 100)} cm</b>
              <input disabled={uploadBusy} type="range" min="200" max="400" step="5" value={height * 100}
                onChange={(event) => setHeight(+event.target.value / 100)} />
            </label>
          </details>
          {error && <div className="stage-error" role="alert">{error}</div>}
        </div>

        <div className={`recognition-board${recognitionActive ? ' is-scanning' : ''}`} aria-live="polite">
          <div className="recognition-visual" aria-hidden="true">
            <div className="blueprint-room room-a" />
            <div className="blueprint-room room-b" />
            <div className="blueprint-room room-c" />
            <div className="blueprint-door" />
            <div className="blueprint-window" />
            <div className="scan-line" />
            <span>WALL</span><span>WINDOW</span><span>ROOM</span>
          </div>
          <div className="recognition-copy">
            <small>辨識流程</small>
            <h2>{recognitionActive ? '正在讀懂你的空間' : '辨識過程會顯示在這裡'}</h2>
            <p>{uploadStatus}</p>
          </div>
          <ol className="recognition-milestones">
            {milestones.map((milestone) => (
              <li key={milestone.label} className={milestone.state}>
                <span>{milestone.state === 'done' ? '✓' : ''}</span>
                <div><strong>{milestone.label}</strong><small>{milestone.detail}</small></div>
              </li>
            ))}
          </ol>
        </div>
      </section>
    </main>
  )
}

function floorplanExtension(file) {
  const filename = String(file?.name || '').toLowerCase()
  return P0_FLOORPLAN_EXTENSIONS.find((extension) => filename.endsWith(extension)) || ''
}

function ProjectSetup({ busy, error, onCreate, onCancel }) {
  const [name, setName] = useState('')
  const [notes, setNotes] = useState('')

  const submit = (event) => {
    event.preventDefault()
    onCreate({ name, notes })
  }

  return (
    <div className="studio-app project-mode">
      <ProductHeader />
      <WorkflowProgress current="project" />
      <main className="project-start">
        <section className="project-card" aria-labelledby="project-title">
          <div className="project-form-side">
            <div className="project-mark">RP</div>
            <p className="eyebrow">ROOMPILOT · 01</p>
            <h1 id="project-title">為下一個空間<br />建立設計專案</h1>
            <p className="project-lead">每一份平面圖、需求、配置與提案版本都會留在同一個專案網址，不再分散到另一個網頁。</p>
            <form onSubmit={submit}>
              <label htmlFor="project-name">專案名稱 *</label>
              <input
                id="project-name"
                autoFocus
                maxLength={120}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="例如：王小姐住宅提案"
                disabled={busy}
              />
              <label htmlFor="project-notes">提案備註</label>
              <textarea
                id="project-notes"
                maxLength={2000}
                rows={3}
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="例如：三房兩廳，希望保留明亮木質調"
                disabled={busy}
              />
              {error && <div className="project-error" role="alert">{error}</div>}
              <button className="project-primary" type="submit" disabled={busy || !name.trim()}>
                {busy ? '正在建立專案…' : '建立專案，下一步上傳平面圖 →'}
              </button>
              {onCancel && (
                <button className="project-secondary" type="button" onClick={onCancel} disabled={busy}>
                  返回目前專案
                </button>
              )}
            </form>
          </div>
          <aside className="project-visual-side" aria-hidden="true">
            <img src="/static/style_images/scandinavian.png" alt="" />
            <div className="project-visual-overlay" />
            <div className="project-visual-copy"><span>ROOMPILOT STUDIO</span><strong>從一條牆線，<br />走到完整提案。</strong></div>
            <ol><li>辨識與比例確認</li><li>AI 2D 合法配置</li><li>3D 白模與風格提案</li></ol>
          </aside>
        </section>
      </main>
    </div>
  )
}

function projectSnapshot({ name, upload, storedUploadName, scaleM, thickness, height, show, items }) {
  return {
    schemaVersion: 1,
    source: upload || storedUploadName
      ? { kind: 'upload', fileName: upload?.name || storedUploadName }
      : { kind: 'sample', planName: name },
    scaleM,
    thickness,
    height,
    show,
    furnitureItems: items,
  }
}

export default function App() {
  const plans = []
  const [name, setName] = useState('')
  const [upload, setUpload] = useState(null)
  const [storedUploadName, setStoredUploadName] = useState(null)
  const [scaleM, setScaleM] = useState(null)
  const [thickness, setThickness] = useState(DEFAULTS.thickness)
  const [height, setHeight] = useState(DEFAULTS.height)
  const [data, setData] = useState(null)
  const [recognizedDxfText, setRecognizedDxfText] = useState(null)
  const [uploadStage, setUploadStage] = useState('idle')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [show, setShow] = useState(SHOW_DEFAULTS)
  const [reviewDraft, setReviewDraft] = useState(null)
  const [reviewing, setReviewing] = useState(false)
  const [reviewBusy, setReviewBusy] = useState(false)
  const [openrouterConsent, setOpenrouterConsent] = useState(true)
  const [recognitionOpenRouter, setRecognitionOpenRouter] = useState(null)
  const [calibrationInfo, setCalibrationInfo] = useState(null)
  const [calibrationBusy, setCalibrationBusy] = useState(false)
  const [requirementsEditing, setRequirementsEditing] = useState(false)
  const [requirementsBusy, setRequirementsBusy] = useState(false)
  const [layoutEditing, setLayoutEditing] = useState(false)
  const [layoutBusy, setLayoutBusy] = useState(false)
  const [whiteModelBusy, setWhiteModelBusy] = useState(false)
  const [viewpointBusy, setViewpointBusy] = useState(false)
  const [cameraEditing, setCameraEditing] = useState(true)
  const [styleBusy, setStyleBusy] = useState(false)
  const [renderBusy, setRenderBusy] = useState(false)
  const [whiteModelRender, setWhiteModelRender] = useState({ visibleInstanceIds: [] })
  const [requirementStyles, setRequirementStyles] = useState([])
  const [taiwanStyleCards, setTaiwanStyleCards] = useState([])
  const [renderHistory, setRenderHistory] = useState([])
  const [catalogItems, setCatalogItems] = useState([])

  const [furn, setFurn] = useState([])
  const [items, setItems] = useState([])
  const [placing, setPlacing] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [snapOn, setSnapOn] = useState(true)

  const [project, setProject] = useState(null)
  const [pausedProject, setPausedProject] = useState(null)
  const [projectLoading, setProjectLoading] = useState(true)
  const [projectReady, setProjectReady] = useState(false)
  const [projectBusy, setProjectBusy] = useState(false)
  const [projectError, setProjectError] = useState(null)
  const [projectSaveStatus, setProjectSaveStatus] = useState('saved')
  const projectRef = useRef(null)
  const saveTimer = useRef(null)
  const lastSavedSnapshot = useRef(null)
  const projectOperationRef = useRef(false)
  const viewerRef = useRef(null)

  useEffect(() => {
    projectRef.current = project
  }, [project])

  useEffect(() => {
    const viewpoint = project?.workflow?.data?.viewpoint
    if (viewpoint?.status !== 'locked' || cameraEditing) return undefined
    const frame = window.requestAnimationFrame(() => viewerRef.current?.applyViewpoint(viewpoint))
    return () => window.cancelAnimationFrame(frame)
  }, [project?.project_id, project?.workflow?.data?.viewpoint?.version, cameraEditing])

  const handleWhiteModelDiagnostics = useCallback((diagnostics) => {
    const next = diagnostics?.visibleInstanceIds || []
    setWhiteModelRender((current) => (
      current.visibleInstanceIds.join('|') === next.join('|')
        ? current
        : { visibleInstanceIds: next }
    ))
  }, [])

  useEffect(() => {
    fetch('/api/furniture?has_model=true&page_size=80')
      .then((response) => response.json())
      .then((payload) => {
        setFurn(payload.furniture || [])
        setCatalogItems(payload.items || [])
      })
      .catch(() => {})
    fetch('/api/styles')
      .then((response) => response.json())
      .then((payload) => {
        setRequirementStyles(payload.styles || [])
        setTaiwanStyleCards(payload.taiwan_style_cards || [])
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    let cancelled = false

    const restore = async () => {
      const projectId = projectIdFromLocation() || loadLastProjectId()
      if (!projectId) {
        setProjectLoading(false)
        return
      }

      const cached = loadProjectCache(projectId)
      let restoredProject
      try {
        restoredProject = (await loadServerProject(projectId)).project
        setProjectSaveStatus('saved')
      } catch (reason) {
        if (reason instanceof ProjectApiError && reason.status === 0 && cached?.project) {
          restoredProject = cached.project
          setProjectSaveStatus('offline')
        } else {
          if (reason instanceof ProjectApiError && reason.status === 404) {
            rememberProjectId(null)
            setProjectInLocation(null)
            if (!cancelled) {
              setProjectError(null)
              setProjectLoading(false)
            }
            return
          }
          if (!cancelled) {
            setProjectError(reason.message)
            setProjectLoading(false)
          }
          return
        }
      }
      if (cancelled) return

      const snapshot = restoredProject.workflow?.frontend3d || cached?.snapshot || {}
      lastSavedSnapshot.current = JSON.stringify(snapshot)
      projectRef.current = restoredProject
      setProject(restoredProject)
      rememberProjectId(restoredProject.project_id)
      setProjectInLocation(restoredProject.project_id)
      if (Number(snapshot.thickness) > 0) setThickness(Number(snapshot.thickness))
      if (Number(snapshot.height) > 0) setHeight(Number(snapshot.height))
      if (snapshot.scaleM == null || Number(snapshot.scaleM) > 0) setScaleM(snapshot.scaleM ?? null)
      if (snapshot.show && typeof snapshot.show === 'object') {
        setShow({ ...SHOW_DEFAULTS, ...snapshot.show })
      }
      if (Array.isArray(snapshot.furnitureItems)) setItems(snapshot.furnitureItems)
      const restoredRecognition = restoredProject.workflow?.data?.recognition
      const restoredConfirmation = restoredProject.workflow?.data?.space_confirmation
      const restoredCalibration = restoredProject.workflow?.data?.calibration
      const restoredRequirements = restoredProject.workflow?.data?.requirements
      const restoredLayout = restoredProject.workflow?.data?.layout_2d
      const restoredViewpoint = restoredProject.workflow?.data?.viewpoint
      const restoredStyleRender = restoredProject.workflow?.data?.style_render
      if (restoredRecognition?.openrouter?.requested != null) {
        setOpenrouterConsent(Boolean(restoredRecognition.openrouter.requested))
      }
      setRecognitionOpenRouter(restoredRecognition?.openrouter || null)
      if (restoredConfirmation?.status === 'confirmed' && restoredConfirmation.floorplan) {
        setCalibrationInfo(restoredCalibration || {
          status: 'confirmed',
          legacy: true,
          scale_cm: Number(restoredConfirmation.floorplan.scale_m || 0) * 100,
        })
        setData(restoredConfirmation.floorplan)
        setReviewDraft(makeFloorplanReviewDraft(restoredConfirmation.floorplan))
        setReviewing(false)
        setRequirementsEditing(restoredRequirements?.status !== 'confirmed')
        setLayoutEditing(false)
        if (restoredStyleRender?.status === 'configured') {
          setItems(layoutObjectsToThreeItems(restoredStyleRender.scene_objects || []))
        } else if (restoredLayout?.status === 'confirmed') {
          setItems(layoutObjectsToThreeItems(restoredLayout.scene_objects || []))
        }
        setCameraEditing(restoredViewpoint?.status !== 'locked')
        setUploadStage('ready')
      } else if (restoredRecognition?.floorplan) {
        setCalibrationInfo(restoredCalibration || null)
        setData(restoredRecognition.floorplan)
        setReviewDraft(makeFloorplanReviewDraft(restoredRecognition.floorplan))
        setReviewing(true)
        setUploadStage('review')
      }

      if (snapshot.source?.kind === 'upload' && snapshot.source.fileName) {
        setStoredUploadName(snapshot.source.fileName)
        try {
          const response = await fetch(
            `/api/projects/${encodeURIComponent(restoredProject.project_id)}/floorplan/source`,
          )
          if (!response.ok) throw new Error('找不到已上傳的平面圖原檔。')
          const blob = await response.blob()
          if (!cancelled) {
            setUpload(new File([blob], snapshot.source.fileName, { type: blob.type }))
            if (snapshot.source.fileName.toLowerCase().endsWith('.dxf')) {
              setRecognizedDxfText(await blob.text())
            }
            setName('')
          }
        } catch (reason) {
          if (!cancelled) setError(`專案已載入，但平面圖無法還原：${reason.message}`)
        }
      } else if (snapshot.source?.planName) {
        setStoredUploadName(null)
        setUpload(null)
        setRecognizedDxfText(null)
        setUploadStage('idle')
        setName(snapshot.source.planName)
      }
      if (!cancelled) {
        try {
          const history = await listServerRenders(restoredProject.project_id)
          if (!cancelled) setRenderHistory(history.renders || [])
        } catch {
          // PNG 歷史是非阻斷資訊；專案主資料仍可正常還原。
        }
        setProjectReady(true)
        setProjectLoading(false)
      }
    }

    restore()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (
      !projectReady
      || !project
      || upload
      || !name
      || project.workflow?.data?.space_confirmation?.status === 'confirmed'
    ) return
    let cancelled = false
    const timer = setTimeout(async () => {
      setLoading(true)
      setError(null)
      try {
        const query = new URLSearchParams({ thickness, height })
        if (scaleM) query.set('scale_m', scaleM)
        query.set('name', name)
        const response = await fetch(`/api/plan?${query}`)
        if (!response.ok) {
          const payload = await response.json()
          throw new Error(payload.detail || response.statusText)
        }
        const payload = await response.json()
        if (!cancelled) setData(payload)
      } catch (reason) {
        if (!cancelled) setError(String(reason.message || reason))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }, 250)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [projectReady, project?.project_id, name, upload, scaleM, thickness, height])

  useEffect(() => {
    if (
      !projectReady
      || !upload
      || !recognizedDxfText
      || uploadStage !== 'ready'
      || projectOperationRef.current
      || project?.workflow?.data?.space_confirmation?.status === 'confirmed'
    ) return
    let cancelled = false
    const timer = window.setTimeout(async () => {
      setLoading(true)
      try {
        const query = new URLSearchParams({ thickness, height })
        if (scaleM) query.set('scale_m', scaleM)
        const body = new FormData()
        body.append('file', new File([recognizedDxfText], 'recognized.dxf', { type: 'application/dxf' }))
        const response = await fetch(`/api/upload?${query}`, { method: 'POST', body })
        if (!response.ok) {
          const payload = await response.json()
          throw new Error(payload.detail || response.statusText)
        }
        const payload = await response.json()
        if (!cancelled) setData(payload)
      } catch (reason) {
        if (!cancelled) setError(`尺寸調整解析失敗：${reason.message || reason}`)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }, 250)
    return () => { cancelled = true; window.clearTimeout(timer) }
  }, [projectReady, project?.revision, upload, recognizedDxfText, uploadStage, scaleM, thickness, height])

  useEffect(() => {
    if (!projectReady || !project?.project_id || projectOperationRef.current) return
    const snapshot = projectSnapshot({ name, upload, storedUploadName, scaleM, thickness, height, show, items })
    const serializedSnapshot = JSON.stringify(snapshot)
    cacheProject(project, snapshot)
    window.clearTimeout(saveTimer.current)
    if (serializedSnapshot === lastSavedSnapshot.current) {
      setProjectSaveStatus((current) => current === 'offline' ? current : 'saved')
      return
    }
    setProjectSaveStatus('saving')
    saveTimer.current = window.setTimeout(async () => {
      const active = projectRef.current
      if (!active?.project_id) return
      const update = {
        expected_revision: active.revision,
        current_step: null,
        workflow: { schema_version: 1, frontend3d: snapshot },
      }
      try {
        const response = await saveServerWorkflow(active.project_id, update)
        projectRef.current = response.project
        setProject(response.project)
        cacheProject(response.project, snapshot)
        lastSavedSnapshot.current = serializedSnapshot
        setProjectSaveStatus('saved')
      } catch (reason) {
        if (reason instanceof ProjectApiError && reason.status === 409) {
          try {
            const latest = (await loadServerProject(active.project_id)).project
            const retried = await saveServerWorkflow(active.project_id, {
              ...update,
              expected_revision: latest.revision,
            })
            projectRef.current = retried.project
            setProject(retried.project)
            cacheProject(retried.project, snapshot)
            lastSavedSnapshot.current = serializedSnapshot
            setProjectSaveStatus('saved-after-conflict')
            return
          } catch {
            setProjectSaveStatus('conflict')
            return
          }
        }
        setProjectSaveStatus('offline')
      }
    }, 500)
    return () => window.clearTimeout(saveTimer.current)
  }, [projectReady, project?.project_id, project?.revision, name, upload?.name, storedUploadName, uploadStage, scaleM, thickness, height, show, items])

  const createProject = async ({ name: projectName, notes }) => {
    setProjectBusy(true)
    setProjectError(null)
    try {
      const created = (await createServerProject({ name: projectName, notes })).project
      lastSavedSnapshot.current = null
      setUpload(null)
      setStoredUploadName(null)
      // 新專案一律先停在上傳站，不偷偷載入示範圖跳過使用者流程。
      setName('')
      setScaleM(null)
      setThickness(DEFAULTS.thickness)
      setHeight(DEFAULTS.height)
      setData(null)
      setRecognizedDxfText(null)
      setUploadStage('idle')
      setReviewDraft(null)
      setReviewing(false)
      setRecognitionOpenRouter(null)
      setCalibrationInfo(null)
      setRequirementsEditing(false)
      setLayoutEditing(false)
      setCameraEditing(true)
      setRenderHistory([])
      setShow(SHOW_DEFAULTS)
      setItems([])
      setPlacing(null)
      setSelectedId(null)
      projectRef.current = created
      setProject(created)
      setPausedProject(null)
      setProjectReady(true)
      setProjectSaveStatus('saved')
      rememberProjectId(created.project_id)
      setProjectInLocation(created.project_id)
    } catch (reason) {
      setProjectError(reason.message)
    } finally {
      setProjectBusy(false)
      setProjectLoading(false)
    }
  }

  const startNewProject = () => {
    lastSavedSnapshot.current = null
    setPausedProject(project)
    setProject(null)
    setProjectReady(false)
    setProjectError(null)
    setProjectInLocation(null)
  }

  const cancelNewProject = () => {
    if (!pausedProject) return
    projectRef.current = pausedProject
    lastSavedSnapshot.current = JSON.stringify(
      pausedProject.workflow?.frontend3d
      || projectSnapshot({ name, upload, storedUploadName, scaleM, thickness, height, show, items }),
    )
    setProject(pausedProject)
    setProjectReady(true)
    rememberProjectId(pausedProject.project_id)
    setProjectInLocation(pausedProject.project_id)
    setPausedProject(null)
  }

  const choosePlan = (planName) => {
    setUpload(null)
    setStoredUploadName(null)
    setRecognizedDxfText(null)
    setUploadStage('idle')
    setReviewDraft(null)
    setReviewing(false)
    setRecognitionOpenRouter(null)
    setCalibrationInfo(null)
    setRequirementsEditing(false)
    setLayoutEditing(false)
    setCameraEditing(true)
    setRenderHistory([])
    setName(planName)
    setScaleM(null)
    setData(null)
    setItems([])
    setSelectedId(null)
    setPlacing(null)
  }

  const chooseUpload = async (file) => {
    if (!file) return
    const preservedUploadStage = ['ready', 'review'].includes(uploadStage) && storedUploadName
      ? uploadStage
      : 'error'
    const extension = floorplanExtension(file)
    if (!extension) {
      setUploadStage(preservedUploadStage)
      setError('格式不支援：P0 只接受 DXF 或 PNG 平面圖。')
      return
    }
    if (!file.size) {
      setUploadStage(preservedUploadStage)
      setError('平面圖是空檔案，請重新選擇。')
      return
    }
    if (file.size > MAX_FLOORPLAN_BYTES) {
      setUploadStage(preservedUploadStage)
      setError('平面圖檔案不可超過 20 MB。')
      return
    }

    const active = projectRef.current
    if (!active) return
    window.clearTimeout(saveTimer.current)
    projectOperationRef.current = true
    setUpload(file)
    setStoredUploadName(file.name)
    setRecognizedDxfText(null)
    setUploadStage('uploading')
    setName('')
    setScaleM(null)
    setData(null)
    setReviewDraft(null)
    setReviewing(false)
    setRecognitionOpenRouter(null)
    setCalibrationInfo(null)
    setRequirementsEditing(false)
    setLayoutEditing(false)
    setCameraEditing(true)
    setRenderHistory([])
    setError(null)
    setItems([])
    setSelectedId(null)
    setPlacing(null)
    setProjectSaveStatus('uploading')
    setLoading(true)
    let uploadedProject = null
    try {
      const uploaded = await uploadServerFloorplan(
        active.project_id,
        file,
        active.revision,
      )
      uploadedProject = uploaded.project
      projectRef.current = uploadedProject
      setProject(uploadedProject)
      setUploadStage('analyzing')
      setProjectSaveStatus('analyzing')

      const analyzed = await analyzeServerFloorplan(active.project_id, {
        expected_revision: uploadedProject.revision,
        scale_m: null,
        thickness,
        height,
        allow_openrouter: openrouterConsent,
      })
      setData(analyzed.analysis.floorplan)
      setReviewDraft(makeFloorplanReviewDraft(analyzed.analysis.floorplan))
      setReviewing(true)
      setRecognitionOpenRouter(analyzed.analysis.openrouter || null)
      setCalibrationInfo(null)
      setRequirementsEditing(false)
    setLayoutEditing(false)
    setCameraEditing(true)
    setRenderHistory([])
      setRecognizedDxfText(analyzed.analysis.dxf_text || null)
      setUploadStage('review')
      projectOperationRef.current = false
      projectRef.current = analyzed.project
      setProject(analyzed.project)
      setProjectSaveStatus('saved')
    } catch (reason) {
      projectOperationRef.current = false
      setUploadStage('error')
      if (uploadedProject) {
        projectRef.current = uploadedProject
        setProject({ ...uploadedProject })
        setProjectSaveStatus('recognition-error')
        setError(`原檔已保存，但辨識失敗：${reason.message}`)
      } else {
        setUpload(null)
        setStoredUploadName(null)
        setProjectSaveStatus('upload-error')
        setError(`平面圖未儲存：${reason.message}`)
      }
    } finally {
      setLoading(false)
    }
  }

  const confirmFloorplan = async () => {
    const active = projectRef.current
    if (!active || !reviewDraft) return
    if (calibrationInfo?.status !== 'confirmed') {
      setError('請先在 2D 圖上拉參考線並輸入實際公分數。')
      return
    }
    window.clearTimeout(saveTimer.current)
    projectOperationRef.current = true
    setReviewBusy(true)
    setError(null)
    setProjectSaveStatus('confirming')
    try {
      const response = await confirmServerFloorplan(
        active.project_id,
        confirmationPayload(reviewDraft, active.revision),
      )
      projectRef.current = response.project
      setProject(response.project)
      setData(response.confirmation.floorplan)
      setReviewDraft(makeFloorplanReviewDraft(response.confirmation.floorplan))
      setReviewing(false)
      setRequirementsEditing(true)
      setLayoutEditing(false)
      setUploadStage('ready')
      setProjectSaveStatus('saved')
    } catch (reason) {
      if (reason instanceof ProjectApiError && reason.status === 409) {
        setProjectSaveStatus('conflict')
      } else {
        setProjectSaveStatus('confirmation-error')
      }
      setError(`確認結果未儲存：${reason.message}`)
    } finally {
      projectOperationRef.current = false
      setReviewBusy(false)
    }
  }

  const calibrateFloorplan = async (reference, actualLengthCm) => {
    const active = projectRef.current
    if (!active) return false
    window.clearTimeout(saveTimer.current)
    projectOperationRef.current = true
    setCalibrationBusy(true)
    setError(null)
    setProjectSaveStatus('calibrating')
    try {
      const response = await calibrateServerFloorplan(
        active.project_id,
        calibrationPayload(reference, actualLengthCm, active.revision),
      )
      projectRef.current = response.project
      setProject(response.project)
      setData(response.analysis.floorplan)
      setReviewDraft(makeFloorplanReviewDraft(response.analysis.floorplan))
      setRecognizedDxfText(response.analysis.dxf_text || recognizedDxfText)
      setRecognitionOpenRouter(response.analysis.openrouter || recognitionOpenRouter)
      setCalibrationInfo(response.calibration)
      setProjectSaveStatus('saved')
      return true
    } catch (reason) {
      setProjectSaveStatus(reason instanceof ProjectApiError && reason.status === 409
        ? 'conflict'
        : 'calibration-error')
      setError(`比例尚未套用：${reason.message}`)
      return false
    } finally {
      projectOperationRef.current = false
      setCalibrationBusy(false)
    }
  }

  const analyzeRequirements = async (draft) => {
    const active = projectRef.current
    if (!active) throw new Error('找不到目前專案。')
    window.clearTimeout(saveTimer.current)
    setRequirementsBusy(true)
    setError(null)
    setProjectSaveStatus('requirements-analyzing')
    try {
      const response = await analyzeServerRequirements(
        active.project_id,
        requirementsAnalyzePayload(draft, active.revision),
      )
      setProjectSaveStatus('saved')
      return response.suggestion
    } catch (reason) {
      setProjectSaveStatus(reason instanceof ProjectApiError && reason.status === 409
        ? 'conflict'
        : 'requirements-error')
      throw reason
    } finally {
      setRequirementsBusy(false)
    }
  }

  const confirmRequirements = async (draft, suggestion) => {
    const active = projectRef.current
    if (!active) throw new Error('找不到目前專案。')
    window.clearTimeout(saveTimer.current)
    projectOperationRef.current = true
    setRequirementsBusy(true)
    setError(null)
    setProjectSaveStatus('requirements-confirming')
    try {
      const response = await confirmServerRequirements(
        active.project_id,
        requirementsConfirmationPayload(draft, active.revision, suggestion),
      )
      projectRef.current = response.project
      setProject(response.project)
      setRequirementsEditing(false)
      setProjectSaveStatus('saved')
      return response.requirements
    } catch (reason) {
      setProjectSaveStatus(reason instanceof ProjectApiError && reason.status === 409
        ? 'conflict'
        : 'requirements-error')
      throw reason
    } finally {
      projectOperationRef.current = false
      setRequirementsBusy(false)
    }
  }

  const analyzeLayout = async (allowOpenrouter) => {
    const active = projectRef.current
    if (!active) throw new Error('找不到目前專案。')
    window.clearTimeout(saveTimer.current)
    setLayoutBusy(true)
    setError(null)
    setProjectSaveStatus('layout-analyzing')
    try {
      const response = await analyzeServerLayout(active.project_id, {
        expected_revision: active.revision,
        allow_openrouter: Boolean(allowOpenrouter),
      })
      setProjectSaveStatus('saved')
      return response.proposal
    } catch (reason) {
      setProjectSaveStatus(reason instanceof ProjectApiError && reason.status === 409
        ? 'conflict'
        : 'layout-error')
      throw reason
    } finally {
      setLayoutBusy(false)
    }
  }

  const validateLayout = async (objects, instanceId) => {
    const active = projectRef.current
    if (!active) throw new Error('找不到目前專案。')
    return validateServerLayout(
      active.project_id,
      layoutValidationPayload(objects, instanceId, active.revision),
    )
  }

  const confirmLayout = async (proposal, objects) => {
    const active = projectRef.current
    if (!active) throw new Error('找不到目前專案。')
    window.clearTimeout(saveTimer.current)
    projectOperationRef.current = true
    setLayoutBusy(true)
    setError(null)
    setProjectSaveStatus('layout-confirming')
    try {
      const response = await confirmServerLayout(
        active.project_id,
        layoutConfirmationPayload(proposal, objects, active.revision),
      )
      projectRef.current = response.project
      setProject(response.project)
      setItems(layoutObjectsToThreeItems(response.layout.scene_objects || []))
      setLayoutEditing(false)
      setProjectSaveStatus('saved')
      return response.layout
    } catch (reason) {
      setProjectSaveStatus(reason instanceof ProjectApiError && reason.status === 409
        ? 'conflict'
        : 'layout-error')
      throw reason
    } finally {
      projectOperationRef.current = false
      setLayoutBusy(false)
    }
  }

  const confirmWhiteModel = async () => {
    const active = projectRef.current
    if (!active) throw new Error('找不到目前專案。')
    const diagnostics = whiteModelDiagnostics(items, whiteModelRender.visibleInstanceIds)
    window.clearTimeout(saveTimer.current)
    projectOperationRef.current = true
    setWhiteModelBusy(true)
    setError(null)
    setProjectSaveStatus('white-model-confirming')
    try {
      const response = await confirmServerWhiteModel(
        active.project_id,
        whiteModelConfirmationPayload(diagnostics, active.revision),
      )
      projectRef.current = response.project
      setProject(response.project)
      setProjectSaveStatus('saved')
      return response.white_model
    } catch (reason) {
      setProjectSaveStatus(reason instanceof ProjectApiError && reason.status === 409
        ? 'conflict'
        : 'white-model-error')
      setError(`3D 白模尚未完成確認：${reason.message}`)
      return null
    } finally {
      projectOperationRef.current = false
      setWhiteModelBusy(false)
    }
  }

  const confirmViewpoint = async () => {
    const active = projectRef.current
    const viewpoint = viewerRef.current?.getViewpoint()
    if (!active || !viewpoint) {
      setError('3D 場景尚未準備完成，請稍後再鎖定視角。')
      return null
    }
    window.clearTimeout(saveTimer.current)
    projectOperationRef.current = true
    setViewpointBusy(true)
    setError(null)
    setProjectSaveStatus('viewpoint-confirming')
    try {
      const response = await confirmServerViewpoint(
        active.project_id,
        viewpointConfirmationPayload(viewpoint, active.revision),
      )
      projectRef.current = response.project
      setProject(response.project)
      setItems(layoutObjectsToThreeItems(
        response.project.workflow?.data?.layout_2d?.scene_objects || [],
      ))
      setCameraEditing(false)
      setProjectSaveStatus('saved')
      return response.viewpoint
    } catch (reason) {
      setProjectSaveStatus(reason instanceof ProjectApiError && reason.status === 409
        ? 'conflict'
        : 'viewpoint-error')
      setError(`攝影機視角尚未鎖定：${reason.message}`)
      return null
    } finally {
      projectOperationRef.current = false
      setViewpointBusy(false)
    }
  }

  const applyStyleCard = async (cardId) => {
    const active = projectRef.current
    if (!active || cameraEditing) return null
    window.clearTimeout(saveTimer.current)
    projectOperationRef.current = true
    setStyleBusy(true)
    setError(null)
    setProjectSaveStatus('style-applying')
    try {
      const response = await applyServerStyleCard(active.project_id, {
        expected_revision: active.revision,
        card_id: cardId,
      })
      projectRef.current = response.project
      setProject(response.project)
      setItems(layoutObjectsToThreeItems(response.style_render.scene_objects || []))
      setSelectedId(null)
      setProjectSaveStatus('saved')
      return response.style_render
    } catch (reason) {
      setProjectSaveStatus(reason instanceof ProjectApiError && reason.status === 409
        ? 'conflict'
        : 'style-error')
      setError(`色卡尚未套用：${reason.message}`)
      return null
    } finally {
      projectOperationRef.current = false
      setStyleBusy(false)
    }
  }

  const createFinalPng = async () => {
    const active = projectRef.current
    if (!active || !viewerRef.current) return null
    window.clearTimeout(saveTimer.current)
    projectOperationRef.current = true
    setRenderBusy(true)
    setError(null)
    setProjectSaveStatus('rendering-png')
    try {
      setSelectedId(null)
      await new Promise((resolve) => window.requestAnimationFrame(() => window.requestAnimationFrame(resolve)))
      const blob = await viewerRef.current.capturePng()
      const response = await createServerRender(active.project_id, blob, active.revision)
      projectRef.current = response.project
      setProject(response.project)
      setRenderHistory((current) => [response.render, ...current])
      setProjectSaveStatus('saved')
      return response.render
    } catch (reason) {
      setProjectSaveStatus(reason instanceof ProjectApiError && reason.status === 409
        ? 'conflict'
        : 'render-error')
      setError(`最終 PNG 尚未儲存：${reason.message}`)
      return null
    } finally {
      projectOperationRef.current = false
      setRenderBusy(false)
    }
  }

  if (projectLoading) {
    return (
      <div className="studio-app project-mode">
        <ProductHeader />
        <main className="project-start"><div className="project-loading">正在載入專案…</div></main>
      </div>
    )
  }
  if (!project) {
    return (
      <ProjectSetup
        busy={projectBusy}
        error={projectError}
        onCreate={createProject}
        onCancel={pausedProject ? cancelNewProject : null}
      />
    )
  }

  const saveStatus = {
    saving: '正在儲存…',
    uploading: '正在保存原始平面圖…',
    analyzing: '原檔已保存，正在辨識牆、門、窗…',
    calibrating: '正在依參考線重新換算比例…',
    confirming: '正在儲存人工確認結果…',
    'requirements-analyzing': '正在整理需求建議…',
    'requirements-confirming': '正在儲存需求確認…',
    'layout-analyzing': '正在產生 2D 家具配置…',
    'layout-confirming': '正在驗證並儲存 2D 配置…',
    'white-model-confirming': '正在驗證並儲存 3D 白模…',
    'viewpoint-confirming': '正在鎖定攝影機視角…',
    'style-applying': '正在換選家具並套用色卡…',
    'rendering-png': '正在產生並儲存最終 PNG…',
    saved: '已儲存至專案',
    'saved-after-conflict': '已套用最新版本並儲存',
    'recognition-error': '原檔已保存，辨識需要重試',
    'upload-error': '上傳失敗，專案未變更',
    'confirmation-error': '人工確認結果尚未儲存',
    'calibration-error': '比例校正尚未儲存',
    'requirements-error': '需求尚未完成確認',
    'layout-error': '2D 家具配置尚未完成確認',
    'white-model-error': '3D 白模尚未完成確認',
    'viewpoint-error': '攝影機視角尚未鎖定',
    'style-error': '色卡尚未套用',
    'render-error': '最終 PNG 尚未儲存',
    offline: '伺服器未連線，本次變更暫存在瀏覽器',
    conflict: '另一分頁有更新，請重新整理',
  }[projectSaveStatus]
  const uploadBusy = uploadStage === 'uploading' || uploadStage === 'analyzing' || reviewBusy || calibrationBusy || requirementsBusy || layoutBusy || whiteModelBusy || viewpointBusy || styleBusy || renderBusy
  const uploadStatus = {
    idle: '支援 DXF、PNG，檔案上限 20 MB。',
    uploading: '正在保存原始平面圖…',
    analyzing: '正在辨識牆、門、窗並建立 2D 幾何…',
    review: `等待人工確認${storedUploadName ? `：${storedUploadName}` : ''}`,
    ready: `辨識完成${storedUploadName ? `：${storedUploadName}` : ''}`,
    error: '上傳或辨識未完成，請依錯誤訊息修正後重試。',
  }[uploadStage]
  const stats = data?.stats
  const sliderScale = scaleM ?? data?.scale_m ?? 12
  const selectedItem = items.find((item) => item.id === selectedId)
  const short = (file) => decodeURIComponent(String(file || '').split('/').filter(Boolean).at(-1) || '家具').replace(/\.glb$/i, '')
  const spaceConfirmation = project.workflow?.data?.space_confirmation
  const requirementsRecord = project.workflow?.data?.requirements
  const layoutRecord = project.workflow?.data?.layout_2d
  const whiteModelRecord = project.workflow?.data?.white_model_3d
  const viewpointRecord = project.workflow?.data?.viewpoint
  const styleRenderRecord = project.workflow?.data?.style_render
  const styleCards = flattenStyleCards(taiwanStyleCards)
  const requirementsVisible = !reviewing
    && spaceConfirmation?.status === 'confirmed'
    && (requirementsEditing || requirementsRecord?.status !== 'confirmed')
  const layoutVisible = !reviewing
    && !requirementsVisible
    && requirementsRecord?.status === 'confirmed'
    && (layoutEditing || layoutRecord?.status !== 'confirmed')
  const whiteModelActive = !reviewing
    && !requirementsVisible
    && !layoutVisible
    && layoutRecord?.status === 'confirmed'
    && whiteModelRecord?.status !== 'confirmed'
  const viewpointActive = !reviewing
    && !requirementsVisible
    && !layoutVisible
    && whiteModelRecord?.status === 'confirmed'
    && (viewpointRecord?.status !== 'locked' || cameraEditing)
  const styleRenderActive = !reviewing
    && !requirementsVisible
    && !layoutVisible
    && whiteModelRecord?.status === 'confirmed'
    && viewpointRecord?.status === 'locked'
    && !cameraEditing
  const floorplanVisible = !reviewing && spaceConfirmation?.status !== 'confirmed'
  const currentStage = floorplanVisible || reviewing
    ? 'floorplan'
    : requirementsVisible
      ? 'requirements'
      : layoutVisible
        ? 'layout'
        : whiteModelActive
          ? 'white'
          : viewpointActive
            ? 'viewpoint'
            : 'proposal'
  const sceneTitle = whiteModelActive
    ? '確認空間升維與家具白模'
    : viewpointActive
      ? '在場景裡微調家具，鎖定提案視角'
      : '選擇風格色卡，完成提案畫面'
  const sceneDescription = whiteModelActive
    ? '牆、窗洞、實體門與家具比例都來自已確認資料；這一步只驗收幾何，不用材質掩飾問題。'
    : viewpointActive
      ? '直接拖曳家具做最後微調；左鍵旋轉視角、右鍵平移、滾輪縮放，滿意後鎖定。'
      : '色卡與風格在 3D 畫面下方選擇，不離開目前專案，也不再開第二個網站。'
  const whiteDiagnostics = whiteModelDiagnostics(items, whiteModelRender.visibleInstanceIds)
  const expectedWindows = data?.windows?.length || 0
  const matchedWindows = Number(data?.opening_geometry?.window_opening_count || 0)
  const windowOpeningsReady = Boolean(data?.wall_solids?.length)
    && matchedWindows === expectedWindows
  const whiteGeometryVisible = show.walls && (expectedWindows === 0 || show.windows)
  const whiteModelReady = whiteDiagnostics.ready && windowOpeningsReady && whiteGeometryVisible

  return (
    <div className={`studio-app stage-${currentStage}`}>
      <ProductHeader project={project} saveStatus={saveStatus} onNew={startNewProject} />
      <WorkflowProgress current={currentStage} />
      <div className="studio-workarea">
      {false && (
      <div className="panel legacy-panel" aria-hidden="true">
        <section className="active-project" aria-label="目前專案">
          <div><span>目前專案</span><strong>{project.name}</strong><small>{saveStatus}</small></div>
          <button type="button" onClick={startNewProject}>建立新專案</button>
        </section>
        <h1>{reviewing ? 'AI 辨識 → 使用者確認' : requirementsVisible ? '需求問卷 → 使用者確認' : layoutVisible ? 'AI 配置 2D 家具 → 使用者確認' : whiteModelActive ? '生成 3D 白模 → 使用者確認' : viewpointActive ? '調整並鎖定攝影機' : styleRenderActive ? '選擇色卡 → 最終 PNG' : '3D 場景'}</h1>
        <div className="sub">
          {whiteModelActive
            ? '家具只以實際公分尺寸呈現中性幾何；牆體切出真實窗洞，確認後鎖定本版白模。'
            : viewpointActive
              ? '用滑鼠調整提案角度；鎖定後，PNG 與色卡版本都會綁定這個視角。'
              : styleRenderActive
                ? '問卷指定型號保持不變；其餘家具依色卡換選，並重新通過擺放引擎驗證。'
                : 'AI 只提供選件與擺位意圖；合法座標由引擎計算，使用者確認後才進入 3D'}
        </div>

        <div className="field">
          <label>選擇示範平面圖</label>
          <select disabled={uploadBusy} value={upload ? '' : name} onChange={(event) => choosePlan(event.target.value)}>
            {upload && <option value="">{`（上傳）${upload.name}`}</option>}
            {plans.map((plan) => <option key={plan} value={plan}>{plan}</option>)}
          </select>
        </div>

        <label className={`filebtn${uploadBusy ? ' disabled' : ''}`} aria-busy={uploadBusy}>
          {uploadBusy ? '處理平面圖中…' : '上傳 DXF / PNG…'}
          <input
            type="file"
            accept=".dxf,.png,image/png,application/dxf"
            disabled={uploadBusy}
            onChange={(event) => {
              const file = event.target.files?.[0]
              event.target.value = ''
              chooseUpload(file)
            }}
          />
        </label>
        <div className={`upload-status ${uploadStage}`} role="status" aria-live="polite">
          {uploadStatus}
        </div>

        <div className="ai-consent">
          <label>
            <input
              type="checkbox"
              checked={openrouterConsent}
              disabled={uploadBusy || ['review', 'ready'].includes(uploadStage)}
              onChange={(event) => setOpenrouterConsent(event.target.checked)}
            />
            允許辨識 PNG 時將平面圖送到 OpenRouter，取得房型與空間屬性建議
          </label>
          <small>DXF 不會送出；AI 建議不會直接定稿，仍須在 2D 畫面逐房確認。</small>
        </div>

        {!reviewing && spaceConfirmation?.status === 'confirmed' && (
          <button className="review-back" type="button" onClick={() => { setRequirementsEditing(false); setReviewing(true) }}>
            返回 2D 修正房型／門窗
          </button>
        )}

        {!reviewing && !requirementsVisible && requirementsRecord?.status === 'confirmed' && (
          <button className="review-back" type="button" onClick={() => setRequirementsEditing(true)}>
            修改需求問卷
          </button>
        )}

        {!reviewing && !requirementsVisible && !layoutVisible && layoutRecord?.status === 'confirmed' && (
          <button className="review-back" type="button" onClick={() => setLayoutEditing(true)}>
            返回 2D 家具配置
          </button>
        )}

        {!upload && (
          <div className="field">
            <label>示範圖除錯長邊 <b>{Math.round((+sliderScale) * 100)} cm</b></label>
            <input disabled={uploadBusy} type="range" min="300" max="6000" step="50" value={sliderScale * 100}
              onChange={(event) => setScaleM(+event.target.value / 100)} />
            <div className="hint">
              僅供內建示範 DXF 除錯；上傳主流程必須在辨識後牆線拉比例。
              {scaleM != null && <button className="text-action" type="button" onClick={() => setScaleM(null)}>重設為自動</button>}
            </div>
          </div>
        )}

        <div className="field">
          <label>牆厚 <b>{Math.round(thickness * 100)} cm</b></label>
          <input disabled={uploadBusy} type="range" min="5" max="50" step="1" value={thickness * 100}
            onChange={(event) => setThickness(+event.target.value / 100)} />
          <div className="hint">調大可合併雙線牆。</div>
        </div>

        <div className="field">
          <label>樓高 <b>{Math.round(height * 100)} cm</b></label>
          <input disabled={uploadBusy} type="range" min="200" max="400" step="5" value={height * 100}
            onChange={(event) => setHeight(+event.target.value / 100)} />
        </div>

        <div className="checks">
          {['walls', 'windows', 'doors', 'floor', 'xray'].map((key) => (
            <label key={key}>
              <input type="checkbox" checked={show[key]}
                onChange={() => setShow((value) => ({ ...value, [key]: !value[key] }))} />
              {{ walls: '牆', windows: '窗', doors: '門', floor: '地板', xray: '近景穿牆' }[key]}
            </label>
          ))}
        </div>

        {!requirementsVisible && !layoutVisible && !whiteModelActive && !viewpointActive && !styleRenderActive && layoutRecord?.status === 'confirmed' && furn.length > 0 && (
          <div className="field">
            <label>家具庫{items.length > 0 && <b>已放 {items.length} 件</b>}</label>
            <div className="furn-list">
              {furn.map((file) => (
                <button key={file} className={placing === file ? 'active' : ''}
                  onClick={() => setPlacing(placing === file ? null : file)}>
                  {short(file)}
                </button>
              ))}
            </div>
            <label className="snaprow">
              <input type="checkbox" checked={snapOn} onChange={() => setSnapOn((value) => !value)} />
              吸附（牆面／家具／格點）
            </label>
            <div className="hint">
              {placing
                ? `在 3D 地面點擊放置「${short(placing)}」；R 旋轉、Shift+點擊連續放置、Esc 取消。`
                : '點選家具後移到 3D 地面放置；拖曳移動、R 旋轉、Del 刪除。'}
            </div>
          </div>
        )}

        {!requirementsVisible && !layoutVisible && !whiteModelActive && !viewpointActive && !styleRenderActive && selectedItem && (
          <div className="field">
            <label>選取中 <b>{short(selectedItem.file)}</b></label>
            <div className="row2">
              <button onClick={() => setItems((current) => current.map((item) =>
                item.id === selectedId ? { ...item, yaw: item.yaw + Math.PI / 2 } : item))}>
                旋轉 90°
              </button>
              <button disabled={selectedItem.userRequired} onClick={() => {
                if (selectedItem.userRequired) return
                setItems((current) => current.filter((item) => item.id !== selectedId))
                setSelectedId(null)
              }}>
                刪除
              </button>
            </div>
            {selectedItem.userRequired && <div className="hint">問卷指定型號不可刪除。</div>}
          </div>
        )}

        {whiteModelActive && (
          <div className="field white-model-check" aria-live="polite">
            <label>
              3D 白模驗收
              <b>{whiteDiagnostics.visibleFurnitureCount}/{whiteDiagnostics.expectedFurnitureCount} 件家具</b>
            </label>
            <div className={whiteDiagnostics.ready ? 'white-model-pass' : 'white-model-warn'}>
              {whiteDiagnostics.ready
                ? '家具已全部以實際公分尺寸生成中性白模。'
                : `仍有 ${whiteDiagnostics.missingInstanceIds.length} 件家具未形成可見白模。`}
            </div>
            <div className={windowOpeningsReady ? 'white-model-pass' : 'white-model-warn'}>
              {windowOpeningsReady
                ? `${matchedWindows} 扇窗已從牆體形成真實開口。`
                : `只有 ${matchedWindows}/${expectedWindows} 扇窗形成牆體開口，請返回空間確認修正。`}
            </div>
            {!whiteGeometryVisible && (
              <div className="white-model-warn">請開啟牆與窗圖層後再確認白模。</div>
            )}
            {whiteModelRecord?.status === 'confirmed' ? (
              <div className="white-model-confirmed">已由使用者確認，白模比例與窗洞已鎖定。</div>
            ) : (
              <button
                className="review-confirm"
                type="button"
                disabled={!whiteModelReady || whiteModelBusy}
                onClick={confirmWhiteModel}
              >
                {whiteModelBusy ? '正在確認…' : '確認 3D 白模比例與窗洞'}
              </button>
            )}
          </div>
        )}

        {viewpointActive && (
          <div className="field proposal-stage" aria-live="polite">
            <label>提案攝影機 <b>公分座標契約</b></label>
            <div className="hint">左鍵旋轉、右鍵平移、滾輪縮放。請把畫面調到最後提案角度，再鎖定視角。</div>
            <button
              className="review-confirm"
              type="button"
              disabled={viewpointBusy}
              onClick={confirmViewpoint}
            >
              {viewpointBusy ? '正在鎖定…' : viewpointRecord?.status === 'locked' ? '以目前畫面重新鎖定' : '鎖定目前攝影機視角'}
            </button>
            {viewpointRecord?.status === 'locked' && (
              <button
                className="project-secondary"
                type="button"
                disabled={viewpointBusy}
                onClick={() => {
                  viewerRef.current?.applyViewpoint(viewpointRecord)
                  setCameraEditing(false)
                }}
              >
                取消調整，回到已鎖定視角
              </button>
            )}
          </div>
        )}

        {styleRenderActive && (
          <div className="field proposal-stage" aria-live="polite">
            <div className="proposal-heading">
              <label>色卡與家具版本</label>
              <button className="text-action" type="button" onClick={() => setCameraEditing(true)}>
                重新調整視角
              </button>
            </div>
            <div className="hint">
              有指定型號的家具會鎖定；未指定者換成相同類型的新風格家具，位置由後端引擎重算。
            </div>
            <div className="style-card-grid">
              {styleCards.map((card) => (
                <button
                  key={card.card_id}
                  type="button"
                  className={styleRenderRecord?.card_id === card.card_id ? 'style-card active' : 'style-card'}
                  aria-pressed={styleRenderRecord?.card_id === card.card_id}
                  disabled={styleBusy}
                  onClick={() => applyStyleCard(card.card_id)}
                >
                  {card.image_url && <img src={card.image_url} alt="" />}
                  <span>{card.style_name_zh}</span>
                  <strong>{card.name_zh}</strong>
                  <i aria-label={`色票 ${card.palette_hex?.join('、') || ''}`}>
                    {(card.palette_hex || []).map((color) => (
                      <em key={color} style={{ backgroundColor: color }} />
                    ))}
                  </i>
                </button>
              ))}
            </div>
            {styleBusy && <div className="white-model-warn">正在重新選型並驗證合法擺位…</div>}
            {styleRenderRecord?.status === 'configured' && (
              <>
                <div className="white-model-pass">
                  已套用「{styleRenderRecord.render_intent?.style_name_zh} · {styleRenderRecord.render_intent?.card_name_zh}」；
                  保留 {styleRenderRecord.protected_instance_ids?.length || 0} 件指定家具，
                  更換 {styleRenderRecord.replacements?.length || 0} 件未指定家具。
                </div>
                {(styleRenderRecord.warnings || []).map((warning) => (
                  <div className="white-model-warn" key={warning}>{warning}</div>
                ))}
                <button
                  className="review-confirm"
                  type="button"
                  disabled={renderBusy || styleBusy}
                  onClick={createFinalPng}
                >
                  {renderBusy ? '正在產生 PNG…' : '產生並儲存最終 PNG'}
                </button>
              </>
            )}
            <div className="hint">P0 僅輸出最終 PNG；PDF 提案報告列入 P1，本次不產生。</div>
            {renderHistory.length > 0 && (
              <div className="render-history">
                <label>PNG 歷史版本 <b>{renderHistory.length}</b></label>
                {renderHistory.slice(0, 6).map((render) => (
                  <a key={render.render_id} href={render.download_url} download={render.filename}>
                    {new Date(render.created_at).toLocaleString('zh-TW')} · {render.style_card_id}
                  </a>
                ))}
              </div>
            )}
          </div>
        )}

        {error && <div className="err">⚠ {error}</div>}
        {stats && (
          <div className="stats">
            尺寸 <b>{Math.round(Number(stats.width_m) * 100)} × {Math.round(Number(stats.depth_m) * 100)} cm</b>（範圍 {stats.extent_area} m²）<br />
            牆段 <b>{stats.wall_segments}</b> · 牆體 <b>{stats.wall_polys}</b><br />
            窗 <b>{reviewing ? reviewDraft?.windows?.length ?? 0 : stats.windows}</b>
            {' '}· 門 <b>{reviewing ? reviewDraft?.doors?.length ?? 0 : stats.doors}</b><br />
            比例 <b>{Math.round(Number(data.scale_m) * 100)} cm</b> / {data.scale_basis}
            {data.fallback_all_walls && <div className="warn">⚠ 無牆圖層，已將所有線段視為牆。</div>}
          </div>
        )}
        <div className="hint">滑鼠左鍵旋轉、右鍵平移、滾輪縮放。</div>
      </div>
      )}

      <div className="canvas-wrap">
        {loading && <div className="loading">{uploadBusy ? uploadStatus : '解析中…'}</div>}
        {floorplanVisible ? (
          <UploadWorkspace
            uploadStage={uploadStage}
            uploadStatus={uploadStatus}
            uploadBusy={uploadBusy}
            storedUploadName={storedUploadName}
            openrouterConsent={openrouterConsent}
            setOpenrouterConsent={setOpenrouterConsent}
            thickness={thickness}
            setThickness={setThickness}
            height={height}
            setHeight={setHeight}
            onUpload={chooseUpload}
            error={error}
          />
        ) : reviewing ? (
          <FloorplanReview
            draft={reviewDraft}
            onChange={setReviewDraft}
            onConfirm={confirmFloorplan}
            busy={reviewBusy}
            openrouter={recognitionOpenRouter}
            calibration={calibrationInfo}
            onCalibrate={calibrateFloorplan}
            calibrationBusy={calibrationBusy}
          />
        ) : requirementsVisible ? (
          <RequirementsQuestionnaire
            key={`${project.project_id}:${(spaceConfirmation.floorplan?.room_regions || []).map((room) => `${room.room_id}-${room.room_type}`).join('|')}`}
            rooms={spaceConfirmation.floorplan?.room_regions || []}
            initial={requirementsRecord}
            styles={requirementStyles.length ? requirementStyles : undefined}
            catalogItems={catalogItems}
            busy={requirementsBusy}
            onAnalyze={analyzeRequirements}
            onConfirm={confirmRequirements}
            onBack={() => { setRequirementsEditing(false); setReviewing(true) }}
          />
        ) : layoutVisible ? (
          <Layout2DReview
            key={`${project.project_id}:${requirementsRecord?.style_id}:${layoutRecord?.status || 'new'}`}
            floorplan={spaceConfirmation.floorplan}
            busy={layoutBusy}
            onAnalyze={analyzeLayout}
            onValidate={validateLayout}
            onConfirm={confirmLayout}
            onBack={() => { setLayoutEditing(false); setRequirementsEditing(true) }}
          />
        ) : (
          <main className="scene-workspace">
            <div className="scene-viewport">
              <React.Suspense fallback={<div className="scene-module-loading">正在準備 3D 場景…</div>}>
                <Scene
                  ref={viewerRef}
                  data={data}
                  show={styleRenderActive ? { ...show, xray: false } : show}
                  whiteModel={whiteModelActive}
                  onWhiteModelDiagnostics={handleWhiteModelDiagnostics}
                  cameraLocked={styleRenderActive}
                  renderIntent={styleRenderRecord?.status === 'configured'
                    ? styleRenderRecord.render_intent
                    : null}
                  furniture={{ items, setItems, placing, setPlacing, selectedId, setSelectedId, snapOn }}
                />
              </React.Suspense>

              <header className="scene-overlay-heading">
                <p>ROOMPILOT · {whiteModelActive ? '3D WHITE MODEL' : viewpointActive ? 'SCENE EDITOR' : 'PROPOSAL'}</p>
                <h1>{sceneTitle}</h1>
                <span>{sceneDescription}</span>
              </header>

              <div className="scene-metrics" aria-label="場景資料摘要">
                <span><small>空間</small><b>{data?.room_regions?.length || 0}</b></span>
                <span><small>家具</small><b>{items.length}</b></span>
                <span><small>門／窗</small><b>{data?.doors?.length || 0}／{data?.windows?.length || 0}</b></span>
                {stats && <span><small>範圍</small><b>{Math.round(Number(stats.width_m) * 100)} × {Math.round(Number(stats.depth_m) * 100)} cm</b></span>}
              </div>

              <div className="scene-layer-controls" aria-label="場景圖層">
                {['walls', 'windows', 'doors', 'floor', 'xray'].map((key) => (
                  <label key={key} className={show[key] ? 'active' : ''}>
                    <input
                      type="checkbox"
                      checked={key === 'xray' && styleRenderActive ? false : show[key]}
                      disabled={key === 'xray' && styleRenderActive}
                      onChange={() => setShow((value) => ({ ...value, [key]: !value[key] }))}
                    />
                    {{ walls: '牆體', windows: '窗', doors: '實體門', floor: '地板', xray: '近景穿牆' }[key]}
                  </label>
                ))}
              </div>

              {whiteModelActive && (
                <aside className="scene-action-card white-model-action" aria-live="polite">
                  <div className="scene-action-number">05</div>
                  <div><small>幾何驗收</small><h2>3D 白模</h2></div>
                  <ul>
                    <li className={whiteDiagnostics.ready ? 'pass' : 'warn'}>
                      <span>{whiteDiagnostics.ready ? '✓' : '!'}</span>
                      家具白模 {whiteDiagnostics.visibleFurnitureCount}/{whiteDiagnostics.expectedFurnitureCount}
                    </li>
                    <li className={windowOpeningsReady ? 'pass' : 'warn'}>
                      <span>{windowOpeningsReady ? '✓' : '!'}</span>
                      真實窗洞 {matchedWindows}/{expectedWindows}
                    </li>
                    <li className={show.doors ? 'pass' : 'warn'}>
                      <span>{show.doors ? '✓' : '!'}</span>
                      門片與門框已顯示
                    </li>
                  </ul>
                  <button
                    className="studio-primary-action"
                    type="button"
                    disabled={!whiteModelReady || whiteModelBusy}
                    onClick={confirmWhiteModel}
                  >
                    {whiteModelBusy ? '正在確認白模…' : '確認白模，進入場景微調 →'}
                  </button>
                  <button className="studio-link-action" type="button" onClick={() => setLayoutEditing(true)}>返回 2D 配置</button>
                </aside>
              )}

              {viewpointActive && (
                <aside className="scene-action-card viewpoint-action" aria-live="polite">
                  <div className="scene-action-number">06</div>
                  <div><small>場景編輯</small><h2>微調家具與視角</h2></div>
                  <p>拖曳家具後再調整鏡頭。家具座標會沿用引擎配置；問卷指定型號不可刪除。</p>
                  <label className="scene-snap-toggle">
                    <input type="checkbox" checked={snapOn} onChange={() => setSnapOn((value) => !value)} />
                    家具吸附牆面、家具與格點
                  </label>
                  {selectedItem && (
                    <div className="scene-selected-item">
                      <span>選取中<strong>{selectedItem.name || short(selectedItem.file)}</strong></span>
                      <button type="button" onClick={() => setItems((current) => current.map((item) =>
                        item.id === selectedId ? { ...item, yaw: item.yaw + Math.PI / 2 } : item))}>旋轉 90°</button>
                      <button type="button" disabled={selectedItem.userRequired} onClick={() => {
                        if (selectedItem.userRequired) return
                        setItems((current) => current.filter((item) => item.id !== selectedId))
                        setSelectedId(null)
                      }}>移除</button>
                    </div>
                  )}
                  <details className="scene-furniture-drawer">
                    <summary>需要時才展開家具庫（{furn.length}）</summary>
                    <div>
                      {furn.slice(0, 80).map((file) => (
                        <button key={file} type="button" className={placing === file ? 'active' : ''}
                          onClick={() => setPlacing(placing === file ? null : file)}>{short(file)}</button>
                      ))}
                    </div>
                  </details>
                  <button className="studio-primary-action" type="button" disabled={viewpointBusy} onClick={confirmViewpoint}>
                    {viewpointBusy ? '正在鎖定視角…' : viewpointRecord?.status === 'locked' ? '重新鎖定目前視角' : '完成微調並鎖定視角 →'}
                  </button>
                  <button className="studio-link-action" type="button" onClick={() => setLayoutEditing(true)}>返回 2D 配置</button>
                </aside>
              )}

              {styleRenderActive && (
                <section className="proposal-tray" aria-live="polite">
                  <header>
                    <div><small>STEP 07 · STYLE &amp; DELIVERY</small><h2>讓空間長出最後的氣質</h2></div>
                    <div className="proposal-tray-actions">
                      <button type="button" onClick={() => setCameraEditing(true)}>重新調整視角</button>
                      <button
                        className="studio-primary-action"
                        type="button"
                        disabled={renderBusy || styleBusy || styleRenderRecord?.status !== 'configured'}
                        onClick={createFinalPng}
                      >{renderBusy ? '正在產生 PNG…' : '儲存最終 PNG'}</button>
                    </div>
                  </header>
                  <div className="proposal-style-scroll">
                    {styleCards.map((card) => (
                      <button
                        key={card.card_id}
                        type="button"
                        className={styleRenderRecord?.card_id === card.card_id ? 'proposal-style-card active' : 'proposal-style-card'}
                        aria-pressed={styleRenderRecord?.card_id === card.card_id}
                        disabled={styleBusy}
                        onClick={() => applyStyleCard(card.card_id)}
                      >
                        <span className="proposal-style-image">
                          {card.image_url ? <img src={card.image_url} alt="" /> : <i />}
                          <em>{card.style_name_zh}</em>
                        </span>
                        <strong>{card.name_zh}</strong>
                        <i className="proposal-palette">
                          {(card.palette_hex || []).map((color) => <b key={color} style={{ backgroundColor: color }} />)}
                        </i>
                      </button>
                    ))}
                  </div>
                  {styleBusy && <p className="proposal-status">正在重新選型，並由後端引擎驗證合法位置…</p>}
                  {styleRenderRecord?.status === 'configured' && (
                    <p className="proposal-status pass">已套用「{styleRenderRecord.render_intent?.style_name_zh} · {styleRenderRecord.render_intent?.card_name_zh}」；指定家具仍保持鎖定。</p>
                  )}
                  {renderHistory.length > 0 && (
                    <details className="proposal-history">
                      <summary>已儲存的 PNG 版本（{renderHistory.length}）</summary>
                      <div>{renderHistory.slice(0, 6).map((render) => (
                        <a key={render.render_id} href={render.download_url} download={render.filename}>
                          {new Date(render.created_at).toLocaleString('zh-TW')} · {render.style_card_id}
                        </a>
                      ))}</div>
                    </details>
                  )}
                </section>
              )}
            </div>
          </main>
        )}
        {error && !floorplanVisible && <button className="stage-error-toast" type="button" onClick={() => setError(null)}>⚠ {error}<span>關閉</span></button>}
      </div>
      </div>
    </div>
  )
}
