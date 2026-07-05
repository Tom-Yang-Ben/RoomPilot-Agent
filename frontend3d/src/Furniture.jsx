import React, { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useThree } from '@react-three/fiber'
import { useGLTF } from '@react-three/drei'
import * as THREE from 'three'
import { snapPlacement, wallSegments } from './snap.js'

export const furnitureUrl = (file) => `/api/furniture/${encodeURIComponent(file)}`

let SEQ = 1 // placed-item ids, unique for the page's lifetime

// The bundled GLBs come from trimesh, which exports Z-up geometry with no
// correcting node — stand them upright, centre XZ on the origin and rest the
// bottom on y=0, so a placed item is just position[x,0,z] + rotation.y.
function useFurnitureNode(file) {
  const { scene } = useGLTF(furnitureUrl(file))
  return useMemo(() => {
    const obj = scene.clone(true)
    obj.rotation.x = -Math.PI / 2
    const root = new THREE.Group()
    root.add(obj)
    const box = new THREE.Box3().setFromObject(root)
    const c = box.getCenter(new THREE.Vector3())
    obj.position.set(-c.x, -box.min.y, -c.z)
    const size = box.getSize(new THREE.Vector3())
    root.traverse((m) => {
      if (m.isMesh) { m.castShadow = true; m.receiveShadow = true }
    })
    return { node: root, size }
  }, [scene])
}

const Item = React.memo(function Item({ it, selected, onDown, onClick, onHover, reportSize }) {
  const { node, size } = useFurnitureNode(it.file)
  useEffect(() => reportSize(it.file, size), [it.file, size, reportSize])
  return (
    <group
      position={[it.x, 0, it.z]}
      rotation={[0, it.yaw, 0]}
      onPointerDown={(e) => onDown(e, it.id)}
      onClick={(e) => onClick(e, it.id)}
      onPointerOver={(e) => onHover(e, true)}
      onPointerOut={(e) => onHover(e, false)}
    >
      <primitive object={node} />
      {selected && (
        <mesh rotation-x={-Math.PI / 2} position-y={0.02}>
          <planeGeometry args={[size.x + 0.15, size.z + 0.15]} />
          <meshBasicMaterial color="#4ea1ff" transparent opacity={0.35} depthWrite={false} />
        </mesh>
      )}
    </group>
  )
})

const GHOST_FREE = new THREE.MeshStandardMaterial({
  color: '#6db4ff', transparent: true, opacity: 0.55, depthWrite: false,
})
const GHOST_SNAP = new THREE.MeshStandardMaterial({
  color: '#7fe0a0', transparent: true, opacity: 0.6, depthWrite: false,
})

function Ghost({ file, ghost, reportSize }) {
  const { node, size } = useFurnitureNode(file)
  useEffect(() => reportSize(file, size), [file, size, reportSize])
  const snapped = ghost.kind === 'wall' || ghost.kind === 'corner' || ghost.kind === 'edge'
  const mat = snapped ? GHOST_SNAP : GHOST_FREE
  useEffect(() => {
    node.traverse((m) => {
      if (m.isMesh) { m.material = mat; m.castShadow = false; m.receiveShadow = false }
    })
  }, [node, mat])
  return (
    <group position={[ghost.x, 0, ghost.z]} rotation={[0, ghost.yaw, 0]}>
      <primitive object={node} />
    </group>
  )
}

// All placed furniture + the placement ghost + the interaction logic.
// Placing: the ghost follows the cursor with snapping; click commits
// (shift-click keeps placing). Items: pointer-drag moves with snapping,
// R rotates 90°, Del removes, Esc cancels/deselects.
export default function FurnitureLayer({
  data, items, setItems, placing, setPlacing, selectedId, setSelectedId, snapOn,
}) {
  const camera = useThree((s) => s.camera)
  const gl = useThree((s) => s.gl)
  const controls = useThree((s) => s.controls)

  const walls = useMemo(() => wallSegments(data), [data])

  const sizes = useRef(new Map())
  const reportSize = useCallback((file, size) => { sizes.current.set(file, size) }, [])

  const [ghost, setGhost] = useState(null) // {x,z,yaw,kind} cursor-follow while placing
  const [drag, setDrag] = useState(null)   // {id,x,z,yaw,kind} live position while dragging

  // refs so the native event handlers (bound once) always see current state
  const itemsRef = useRef(items); itemsRef.current = items
  const placingRef = useRef(placing); placingRef.current = placing
  const selectedRef = useRef(selectedId); selectedRef.current = selectedId
  const ghostRef = useRef(ghost); ghostRef.current = ghost
  const controlsRef = useRef(controls); controlsRef.current = controls
  const snapRef = useRef(snapOn); snapRef.current = snapOn
  const wallsRef = useRef(walls); wallsRef.current = walls
  const dragGesture = useRef(null) // {id,file,userYaw,moved}
  const dragLive = useRef(null)
  const userYaw = useRef(0)        // intended yaw while placing (R rotates it)
  const lastPt = useRef(null)      // last cursor point on the floor plane

  const computeSnap = useCallback((pt, yaw, file, excludeId) => {
    const others = itemsRef.current
      .filter((it) => it.id !== excludeId)
      .map((it) => ({ x: it.x, z: it.z, yaw: it.yaw, size: sizes.current.get(it.file) }))
    return snapPlacement({
      x: pt.x, z: pt.z, yaw,
      size: sizes.current.get(file),
      walls: wallsRef.current, others,
      enabled: snapRef.current,
    })
  }, [])

  const refreshGhost = useCallback(() => {
    if (!placingRef.current || !lastPt.current) return
    const s = computeSnap(lastPt.current, userYaw.current, placingRef.current, null)
    setGhost(s)
  }, [computeSnap])

  const refreshDrag = useCallback(() => {
    const g = dragGesture.current
    if (!g || !lastPt.current) return
    g.moved = true
    const s = computeSnap(lastPt.current, g.userYaw, g.file, g.id)
    dragLive.current = { id: g.id, ...s }
    setDrag(dragLive.current)
  }, [computeSnap])

  // pointer → floor plane, via a manual raycast so nothing can occlude the move
  useEffect(() => {
    const el = gl.domElement
    const ray = new THREE.Raycaster()
    const ndc = new THREE.Vector2()
    const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0)
    const hit = new THREE.Vector3()
    const floorPoint = (e) => {
      const r = el.getBoundingClientRect()
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
      ray.setFromCamera(ndc, camera)
      return ray.ray.intersectPlane(plane, hit) ? { x: hit.x, z: hit.z } : null
    }
    const onMove = (e) => {
      if (!placingRef.current && !dragGesture.current) return
      const pt = floorPoint(e)
      if (!pt) return
      lastPt.current = pt
      if (placingRef.current) refreshGhost()
      else refreshDrag()
    }
    const onUp = () => {
      if (!dragGesture.current) return
      const g = dragGesture.current
      dragGesture.current = null
      if (controlsRef.current) controlsRef.current.enabled = true
      const live = dragLive.current
      dragLive.current = null
      setDrag(null)
      if (g.moved && live) {
        setItems((arr) => arr.map((it) =>
          it.id === live.id ? { ...it, x: live.x, z: live.z, yaw: live.yaw } : it))
      }
    }
    el.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    return () => {
      el.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
  }, [gl, camera, setItems, refreshGhost, refreshDrag])

  useEffect(() => {
    const onKey = (e) => {
      if (/INPUT|SELECT|TEXTAREA/.test(e.target?.tagName ?? '')) return
      if (e.key === 'Escape') {
        if (placingRef.current) setPlacing(null)
        else setSelectedId(null)
      } else if (e.key === 'r' || e.key === 'R') {
        if (placingRef.current) {
          userYaw.current += Math.PI / 2
          refreshGhost()
        } else if (dragGesture.current) {
          dragGesture.current.userYaw += Math.PI / 2
          refreshDrag()
        } else if (selectedRef.current != null) {
          const id = selectedRef.current
          setItems((arr) => arr.map((it) =>
            it.id === id ? { ...it, yaw: it.yaw + Math.PI / 2 } : it))
        }
      } else if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedRef.current != null) {
          const id = selectedRef.current
          setItems((arr) => arr.filter((it) => it.id !== id))
          setSelectedId(null)
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setItems, setPlacing, setSelectedId, refreshGhost, refreshDrag])

  // entering/leaving placement mode: reset the ghost and show a crosshair
  useEffect(() => {
    userYaw.current = 0
    setGhost(null)
    gl.domElement.style.cursor = placing ? 'crosshair' : ''
  }, [placing, gl])

  const onItemDown = useCallback((e, id) => {
    if (placingRef.current || e.button !== 0) return
    e.stopPropagation()
    setSelectedId(id)
    const it = itemsRef.current.find((i) => i.id === id)
    if (!it) return
    dragGesture.current = { id, file: it.file, userYaw: it.yaw, moved: false }
    dragLive.current = null
    if (controlsRef.current) controlsRef.current.enabled = false
  }, [setSelectedId])

  const onItemClick = useCallback((e, id) => {
    if (placingRef.current) return // let the click fall through to the pick plane
    e.stopPropagation()
  }, [])

  const onItemHover = useCallback((e, over) => {
    if (placingRef.current) return
    e.stopPropagation()
    gl.domElement.style.cursor = over ? 'move' : ''
  }, [gl])

  const onPlaneClick = useCallback((e) => {
    if (e.delta > 4) return // an orbit/pan gesture, not a click
    if (placingRef.current) {
      e.stopPropagation()
      const g = ghostRef.current
      if (!g) return
      const id = SEQ++
      const file = placingRef.current
      setItems((arr) => [...arr, { id, file, x: g.x, z: g.z, yaw: g.yaw }])
      setSelectedId(id)
      if (!e.shiftKey) setPlacing(null)
      else refreshGhost()
    } else {
      setSelectedId(null)
    }
  }, [setItems, setPlacing, setSelectedId, refreshGhost])

  // pick plane: catches placement clicks and empty-ground deselects; invisible
  // but raycastable (colorWrite off draws nothing)
  const bbox = data?.bbox
  const planeCx = bbox ? (bbox.minx + bbox.maxx) / 2 : 0
  const planeCz = bbox ? -(bbox.minz + bbox.maxz) / 2 : 0
  const planeW = bbox ? (bbox.maxx - bbox.minx) + 60 : 200
  const planeD = bbox ? (bbox.maxz - bbox.minz) + 60 : 200

  return (
    <group>
      <mesh
        rotation-x={-Math.PI / 2}
        position={[planeCx, -0.005, planeCz]}
        onClick={onPlaneClick}
      >
        <planeGeometry args={[planeW, planeD]} />
        <meshBasicMaterial transparent opacity={0} colorWrite={false} depthWrite={false} />
      </mesh>

      {items.map((it) => {
        const live = drag && drag.id === it.id
          ? { ...it, x: drag.x, z: drag.z, yaw: drag.yaw }
          : it
        return (
          <Suspense key={it.id} fallback={null}>
            <Item
              it={live}
              selected={it.id === selectedId}
              onDown={onItemDown}
              onClick={onItemClick}
              onHover={onItemHover}
              reportSize={reportSize}
            />
          </Suspense>
        )
      })}

      {placing && ghost && (
        <Suspense fallback={null}>
          <Ghost key={placing} file={placing} ghost={ghost} reportSize={reportSize} />
        </Suspense>
      )}
    </group>
  )
}
