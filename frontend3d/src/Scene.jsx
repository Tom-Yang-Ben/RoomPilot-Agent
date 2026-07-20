import React, { useMemo, useEffect, useImperativeHandle } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, Bounds, Grid } from '@react-three/drei'
import * as THREE from 'three'
import FurnitureLayer, { WhiteFurnitureLayer } from './Furniture.jsx'

// Mapping plan(x,z) -> world: worldX = x, worldZ = -z, height = world Y (up).
// Walls get -z for free from the [-PI/2, 0, 0] extrude rotation; segment meshes
// negate z explicitly so everything lines up.

// --- X-ray walls -----------------------------------------------------------
// When the camera zooms in, fade the wall *surfaces* that sit between the camera
// and the focus point, so you can see into the rooms. This is done per-fragment
// in the shader (not per-mesh opacity) because the backend unions every wall
// into one big mesh (with the rooms as holes) — the near and far walls share a
// single mesh, so only a per-fragment test can single out the near side.
const _camPos = new THREE.Vector3()
const _viewDir = new THREE.Vector3()
const _target = new THREE.Vector3()
const _DEFAULT_TARGET = new THREE.Vector3(0, 1, 0)

function makeWallMaterial(color) {
  const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.9, metalness: 0 })
  mat.transparent = true // queued in the transparent pass; alpha stays 1 until faded
  mat.onBeforeCompile = (shader) => {
    shader.uniforms.uCamPos = { value: new THREE.Vector3() }
    shader.uniforms.uViewDir = { value: new THREE.Vector3(0, 0, -1) }
    shader.uniforms.uCamDist = { value: 1e9 }
    shader.uniforms.uFade = { value: 0 } // 0 = off (zoomed out), 1 = zoomed in
    shader.uniforms.uMargin = { value: 0.3 } // keep walls at/behind the focus opaque
    shader.uniforms.uBand = { value: 1.0 } // softness of the fade boundary
    shader.uniforms.uMinAlpha = { value: 0.4 } // faded walls stay a clear ghost, not invisible
    shader.vertexShader =
      'varying vec3 vWorldPos;\n' +
      shader.vertexShader.replace(
        '#include <begin_vertex>',
        '#include <begin_vertex>\n\tvWorldPos = (modelMatrix * vec4(transformed, 1.0)).xyz;'
      )
    shader.fragmentShader =
      'varying vec3 vWorldPos;\n' +
      'uniform vec3 uCamPos; uniform vec3 uViewDir; uniform float uCamDist;\n' +
      'uniform float uFade; uniform float uMargin; uniform float uBand; uniform float uMinAlpha;\n' +
      shader.fragmentShader.replace(
        '#include <dithering_fragment>',
        '#include <dithering_fragment>\n' +
          '\tfloat proj = dot(vWorldPos - uCamPos, uViewDir);\n' + // distance along view ray
          '\tfloat front = 1.0 - smoothstep(uCamDist - uMargin - uBand, uCamDist - uMargin, proj);\n' +
          '\tgl_FragColor.a *= mix(1.0, uMinAlpha, uFade * front);'
      )
    mat.userData.shader = shader
  }
  return mat
}

function Walls({ polys = [], solids = [], height, color, xray, span }) {
  const layers = useMemo(
    () => (solids.length ? solids : [{ base_y: 0, height, polys }]),
    [solids, polys, height],
  )
  const geos = useMemo(
    () =>
      layers.flatMap((layer, layerIndex) =>
        (layer.polys || []).map(({ exterior, holes = [] }, polyIndex) => {
          const shape = new THREE.Shape()
          exterior.forEach(([x, z], i) => (i ? shape.lineTo(x, z) : shape.moveTo(x, z)))
          holes.forEach((h) => {
            const path = new THREE.Path()
            h.forEach(([x, z], i) => (i ? path.lineTo(x, z) : path.moveTo(x, z)))
            shape.holes.push(path)
          })
          return {
            key: `${layerIndex}-${polyIndex}`,
            baseY: Number(layer.base_y || 0),
            geometry: new THREE.ExtrudeGeometry(shape, {
              depth: Number(layer.height || height),
              bevelEnabled: false,
            }),
          }
        }),
      ),
    [layers, height]
  )

  const mat = useMemo(() => makeWallMaterial(color), [color])
  // Dispose on different cadences: the shared material only on color change /
  // unmount, the geometries whenever they're rebuilt. Coupling them would
  // dispose the still-in-use material on every slider tweak — a shader recompile
  // that resets the uniforms and flashes the x-ray fade back on.
  useEffect(() => () => mat.dispose(), [mat])
  useEffect(() => () => geos.forEach((entry) => entry.geometry.dispose()), [geos])

  const camera = useThree((s) => s.camera)
  const controls = useThree((s) => s.controls)

  useFrame((_, dt) => {
    const shader = mat.userData.shader
    if (!shader) return // not compiled yet
    const u = shader.uniforms
    const near = Math.max(2, span * 0.45) // fully faded once this close to focus
    const far = Math.max(near + 1, span * 1.05) // only engages once you zoom past this
    _camPos.copy(camera.position)
    _target.copy(controls?.target ?? _DEFAULT_TARGET)
    _viewDir.copy(_target).sub(_camPos)
    const dist = _viewDir.length() || 1
    _viewDir.divideScalar(dist) // unit view direction
    let want = xray ? 1 - THREE.MathUtils.smoothstep(dist, near, far) : 0
    // Near top-down the proj test degenerates to a height test (near vs far
    // walls become indistinguishable) and the effect isn't needed — you already
    // see into the rooms from above — so fade it out as the view turns vertical.
    want *= Math.min(1, Math.hypot(_viewDir.x, _viewDir.z) / 0.35)
    if (want < 0.12) want = 0 // deadzone: the whole-plan view stays exactly opaque
    u.uFade.value = THREE.MathUtils.damp(u.uFade.value, want, 6, dt) // ease in/out
    u.uCamPos.value.copy(_camPos)
    u.uViewDir.value.copy(_viewDir)
    u.uCamDist.value = dist
    u.uMargin.value = Math.max(0.15, span * 0.04)
    u.uBand.value = Math.max(0.5, span * 0.16)
    // depthWrite stays ON. The walls are one big self-overlapping mesh, so
    // turning depth off to "see the far wall through the near one" made its faces
    // (and its shadow) blend in submission order and shimmer as the camera moved.
    // With depth on, a faded near wall simply blends its uMinAlpha over the room
    // interior (floor/furniture, drawn opaque first) — stable, and enough to see in.
  })

  return (
    <group>
      {geos.map((entry) => (
        // renderOrder -1: draw the wall before the transparent windows/doors so
        // they composite over it correctly.
        <mesh
          key={entry.key}
          position={[0, entry.baseY, 0]}
          rotation={[-Math.PI / 2, 0, 0]}
          geometry={entry.geometry}
          material={mat}
          renderOrder={-1}
          castShadow
          receiveShadow
        />
      ))}
    </group>
  )
}

function WindowAssemblies({ segs = [], sill, height, depth, wallColor, showWallBelow = true }) {
  const frame = Math.max(0.035, Math.min(0.065, depth * 0.28))
  return (
    <group name="window-assemblies">
      {segs.map((segment, index) => {
        const dx = segment.x2 - segment.x1
        const dz = segment.z2 - segment.z1
        const length = Math.hypot(dx, dz)
        if (length < 1e-3) return null
        const localSill = Math.max(0, Number(segment.sill_m ?? sill))
        const localHeight = Math.max(0.1, Number(segment.height_m ?? height))
        return (
          <group
            key={index}
            position={[(segment.x1 + segment.x2) / 2, 0, -(segment.z1 + segment.z2) / 2]}
            rotation={[0, Math.atan2(dz, dx), 0]}
          >
            {/* 明確補出窗台下的實牆，避免白模只剩懸空玻璃的錯覺。 */}
            {showWallBelow && localSill > 0.02 && (
              <mesh position={[0, localSill / 2, 0]} castShadow receiveShadow>
                <boxGeometry args={[length + frame * 2, localSill, depth * 0.94]} />
                <meshStandardMaterial color={wallColor} roughness={0.94} />
              </mesh>
            )}
            <mesh position={[0, localSill + localHeight / 2, 0]} renderOrder={1}>
              <boxGeometry args={[Math.max(0.02, length - frame * 2), Math.max(0.04, localHeight - frame * 2), frame * 0.42]} />
              <meshPhysicalMaterial color="#bcd9df" transparent opacity={0.42} roughness={0.08} transmission={0.18} />
            </mesh>
            {[-1, 1].map((side) => (
              <mesh key={side} position={[side * (length / 2 - frame / 2), localSill + localHeight / 2, 0]} castShadow>
                <boxGeometry args={[frame, localHeight + frame, depth * 1.08]} />
                <meshStandardMaterial color="#8a8277" roughness={0.58} metalness={0.08} />
              </mesh>
            ))}
            {[localSill, localSill + localHeight].map((y) => (
              <mesh key={y} position={[0, y, 0]} castShadow>
                <boxGeometry args={[length, frame, depth * 1.08]} />
                <meshStandardMaterial color="#8a8277" roughness={0.58} metalness={0.08} />
              </mesh>
            ))}
            <mesh position={[0, localSill + localHeight / 2, 0]} castShadow>
              <boxGeometry args={[frame * 0.72, localHeight - frame, depth * 1.02]} />
              <meshStandardMaterial color="#8a8277" roughness={0.58} metalness={0.08} />
            </mesh>
          </group>
        )
      })}
    </group>
  )
}

function DoorAssemblies({ segs = [], height, depth, whiteModel = false }) {
  const frame = Math.max(0.045, Math.min(0.08, depth * 0.34))
  const panelColor = whiteModel ? '#d9cbbb' : '#8b6244'
  return (
    <group name="door-assemblies">
      {segs.map((segment, index) => {
        const dx = segment.x2 - segment.x1
        const dz = segment.z2 - segment.z1
        const length = Math.hypot(dx, dz)
        if (length < 1e-3) return null
        const doorHeight = Math.max(0.4, Number(segment.height_m ?? height))
        return (
          <group
            key={index}
            position={[(segment.x1 + segment.x2) / 2, 0, -(segment.z1 + segment.z2) / 2]}
            rotation={[0, Math.atan2(dz, dx), 0]}
          >
            <mesh position={[0, doorHeight / 2, 0]} castShadow receiveShadow>
              <boxGeometry args={[Math.max(0.1, length - frame * 1.8), doorHeight - frame, Math.max(0.035, depth * 0.24)]} />
              <meshStandardMaterial color={panelColor} roughness={0.76} />
            </mesh>
            {[-1, 1].map((side) => (
              <mesh key={side} position={[side * (length / 2 - frame / 2), doorHeight / 2, 0]} castShadow>
                <boxGeometry args={[frame, doorHeight + frame, depth * 1.12]} />
                <meshStandardMaterial color="#6e5542" roughness={0.72} />
              </mesh>
            ))}
            <mesh position={[0, doorHeight, 0]} castShadow>
              <boxGeometry args={[length, frame, depth * 1.12]} />
              <meshStandardMaterial color="#6e5542" roughness={0.72} />
            </mesh>
            <mesh position={[length * 0.3, doorHeight * 0.52, depth * 0.17]} castShadow>
              <sphereGeometry args={[Math.max(0.025, frame * 0.42), 14, 10]} />
              <meshStandardMaterial color="#c7a56c" roughness={0.3} metalness={0.58} />
            </mesh>
          </group>
        )
      })}
    </group>
  )
}

function Floor({ bbox, color = '#e9e6df' }) {
  const w = bbox.maxx - bbox.minx
  const d = bbox.maxz - bbox.minz
  const cx = (bbox.minx + bbox.maxx) / 2
  const cz = (bbox.minz + bbox.maxz) / 2
  const pad = 0.6
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[cx, -0.01, -cz]} receiveShadow>
      <planeGeometry args={[w + pad, d + pad]} />
      <meshStandardMaterial color={color} roughness={1} />
    </mesh>
  )
}

function CameraBridge({ viewerRef, controlsRef, locked }) {
  const { camera, gl, scene } = useThree()

  useEffect(() => {
    if (controlsRef.current) controlsRef.current.enabled = !locked
  }, [controlsRef, locked])

  useImperativeHandle(viewerRef, () => ({
    getViewpoint() {
      const target = controlsRef.current?.target || _DEFAULT_TARGET
      return {
        projection: 'perspective',
        position_cm: {
          x: camera.position.x * 100,
          y: camera.position.y * 100,
          z: camera.position.z * 100,
        },
        target_cm: { x: target.x * 100, y: target.y * 100, z: target.z * 100 },
        fov_deg: Number(camera.fov || 45),
      }
    },
    applyViewpoint(viewpoint) {
      if (!viewpoint?.position_cm || !viewpoint?.target_cm) return false
      camera.position.set(
        Number(viewpoint.position_cm.x) / 100,
        Number(viewpoint.position_cm.y) / 100,
        Number(viewpoint.position_cm.z) / 100,
      )
      controlsRef.current?.target.set(
        Number(viewpoint.target_cm.x) / 100,
        Number(viewpoint.target_cm.y) / 100,
        Number(viewpoint.target_cm.z) / 100,
      )
      camera.fov = Number(viewpoint.fov_deg || 45)
      camera.updateProjectionMatrix()
      controlsRef.current?.update()
      return true
    },
    capturePng() {
      gl.render(scene, camera)
      return new Promise((resolve, reject) => {
        gl.domElement.toBlob((blob) => {
          if (blob) {
            // Chromium 讀取 WebGL buffer 後可能把畫面留在已清空狀態；再畫一次，
            // 避免使用者按下輸出後右側預覽突然變成空白。
            gl.render(scene, camera)
            resolve(blob)
          }
          else reject(new Error('瀏覽器未能產生 PNG。'))
        }, 'image/png')
      })
    },
  }), [camera, controlsRef, gl, scene])
  return null
}

const Scene = React.forwardRef(function Scene(
  {
    data,
    show,
    furniture,
    whiteModel = false,
    onWhiteModelDiagnostics,
    cameraLocked = false,
    renderIntent = null,
  },
  viewerRef,
) {
  const controlsRef = React.useRef(null)
  const H = data?.wall_height ?? 2.7
  const t = data?.wall_thickness ?? 0.18
  const openingGeometry = data?.opening_geometry || {}
  const sill = Math.max(0, Number(openingGeometry.window_sill_m ?? 0.9))
  const winH = Math.max(0.1, Number(openingGeometry.window_height_m ?? Math.min(1.3, H - sill)))
  const doorH = Math.max(0.4, Number(openingGeometry.door_height_m ?? Math.min(2.1, H)))
  // plan diagonal (m): scales the x-ray zoom thresholds to the model's size
  const span = data
    ? Math.hypot(data.bbox.maxx - data.bbox.minx, data.bbox.maxz - data.bbox.minz) || 10
    : 10
  const surfaces = renderIntent?.surfaces || {}
  const wallColor = whiteModel ? '#f3f1ec' : (surfaces.wall_hex || '#f3f1ec')
  const floorColor = whiteModel ? '#e9e6df' : (surfaces.floor_hex || '#e9e6df')
  const backgroundColor = renderIntent ? '#f4f0e8' : '#dfe6ee'

  return (
    <Canvas
      shadows
      gl={{ antialias: true, preserveDrawingBuffer: true }}
      camera={{ position: [10, 12, 14], fov: 45, near: 0.05, far: 2000 }}
    >
      <color attach="background" args={[backgroundColor]} />
      <hemisphereLight args={['#ffffff', '#9aa6b2', 0.7]} />
      <ambientLight intensity={0.35} />
      <directionalLight
        position={[12, 22, 8]}
        intensity={1.1}
        castShadow
        shadow-mapSize={[2048, 2048]}
      />
      {!renderIntent && (
        <Grid
          infiniteGrid
          cellSize={1}
          cellThickness={0.5}
          sectionSize={5}
          sectionColor="#9fb0c2"
          cellColor="#c4cfda"
          fadeDistance={60}
          fadeStrength={1.5}
          position={[0, -0.02, 0]}
        />
      )}
      {data && (
        <Bounds key={data.name} fit clip observe margin={1.25}>
          {show.floor && <Floor bbox={data.bbox} color={floorColor} />}
          {show.walls && (
            <Walls
              polys={data.wall_polys}
              solids={data.wall_solids || []}
              height={H}
              color={wallColor}
              xray={show.xray}
              span={span}
            />
          )}
          {show.windows && (
            <WindowAssemblies
              segs={data.windows}
              height={winH}
              sill={sill}
              depth={t}
              wallColor={wallColor}
              showWallBelow={show.walls}
            />
          )}
          {show.doors && (
            <DoorAssemblies
              segs={data.doors}
              height={doorH}
              depth={t}
              whiteModel={whiteModel}
            />
          )}
        </Bounds>
      )}
      {/* outside <Bounds> so placing furniture never refits the camera */}
      {data && whiteModel && (
        <WhiteFurnitureLayer
          items={furniture?.items || []}
          onDiagnostics={onWhiteModelDiagnostics}
        />
      )}
      {data && !whiteModel && <FurnitureLayer data={data} {...furniture} />}
      <OrbitControls ref={controlsRef} makeDefault enableDamping target={[0, 1, 0]} enabled={!cameraLocked} />
      <CameraBridge viewerRef={viewerRef} controlsRef={controlsRef} locked={cameraLocked} />
    </Canvas>
  )
})

export default Scene
