import React, { useMemo, useEffect } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, Bounds, Grid } from '@react-three/drei'
import * as THREE from 'three'

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

function Walls({ polys, height, color, xray, span }) {
  const geos = useMemo(
    () =>
      polys.map(({ exterior, holes }) => {
        const shape = new THREE.Shape()
        exterior.forEach(([x, z], i) => (i ? shape.lineTo(x, z) : shape.moveTo(x, z)))
        holes.forEach((h) => {
          const path = new THREE.Path()
          h.forEach(([x, z], i) => (i ? path.lineTo(x, z) : path.moveTo(x, z)))
          shape.holes.push(path)
        })
        return new THREE.ExtrudeGeometry(shape, { depth: height, bevelEnabled: false })
      }),
    [polys, height]
  )

  const mat = useMemo(() => makeWallMaterial(color), [color])
  // Dispose on different cadences: the shared material only on color change /
  // unmount, the geometries whenever they're rebuilt. Coupling them would
  // dispose the still-in-use material on every slider tweak — a shader recompile
  // that resets the uniforms and flashes the x-ray fade back on.
  useEffect(() => () => mat.dispose(), [mat])
  useEffect(() => () => geos.forEach((g) => g.dispose()), [geos])

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
    <group rotation={[-Math.PI / 2, 0, 0]}>
      {geos.map((g, i) => (
        // renderOrder -1: draw the wall before the transparent windows/doors so
        // they composite over it correctly.
        <mesh key={i} geometry={g} material={mat} renderOrder={-1} castShadow receiveShadow />
      ))}
    </group>
  )
}

// boxes laid along each segment (windows, doors)
function SegBoxes({ segs, h, y, depth, color, opacity = 1 }) {
  return (
    <group>
      {segs.map((s, i) => {
        const dx = s.x2 - s.x1, dz = s.z2 - s.z1
        const len = Math.hypot(dx, dz)
        if (len < 1e-3) return null
        return (
          <mesh
            key={i}
            position={[(s.x1 + s.x2) / 2, y, -(s.z1 + s.z2) / 2]}
            rotation={[0, Math.atan2(dz, dx), 0]}
          >
            <boxGeometry args={[len, h, depth]} />
            <meshStandardMaterial
              color={color}
              transparent={opacity < 1}
              opacity={opacity}
              roughness={0.2}
            />
          </mesh>
        )
      })}
    </group>
  )
}

function Floor({ bbox }) {
  const w = bbox.maxx - bbox.minx
  const d = bbox.maxz - bbox.minz
  const cx = (bbox.minx + bbox.maxx) / 2
  const cz = (bbox.minz + bbox.maxz) / 2
  const pad = 0.6
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[cx, -0.01, -cz]} receiveShadow>
      <planeGeometry args={[w + pad, d + pad]} />
      <meshStandardMaterial color="#e9e6df" roughness={1} />
    </mesh>
  )
}

export default function Scene({ data, show }) {
  const H = data?.wall_height ?? 2.7
  const t = data?.wall_thickness ?? 0.18
  const winH = Math.min(1.3, Math.max(0.6, H - 1.1))
  const sill = Math.min(0.9, H - winH - 0.1)
  // plan diagonal (m): scales the x-ray zoom thresholds to the model's size
  const span = data
    ? Math.hypot(data.bbox.maxx - data.bbox.minx, data.bbox.maxz - data.bbox.minz) || 10
    : 10

  return (
    <Canvas shadows camera={{ position: [10, 12, 14], fov: 45, near: 0.05, far: 2000 }}>
      <color attach="background" args={['#dfe6ee']} />
      <hemisphereLight args={['#ffffff', '#9aa6b2', 0.7]} />
      <ambientLight intensity={0.35} />
      <directionalLight
        position={[12, 22, 8]}
        intensity={1.1}
        castShadow
        shadow-mapSize={[2048, 2048]}
      />
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
      {data && (
        <Bounds key={data.name} fit clip observe margin={1.25}>
          {show.floor && <Floor bbox={data.bbox} />}
          {show.walls && (
            <Walls
              polys={data.wall_polys}
              height={H}
              color="#f3f1ec"
              xray={show.xray}
              span={span}
            />
          )}
          {show.windows && (
            <SegBoxes
              segs={data.windows}
              h={winH}
              y={sill + winH / 2}
              depth={t * 1.4}
              color="#6fb3ff"
              opacity={0.4}
            />
          )}
          {show.doors && (
            <SegBoxes
              segs={data.doors}
              h={0.08}
              y={0.05}
              depth={t * 1.1}
              color="#c2884a"
              opacity={0.95}
            />
          )}
        </Bounds>
      )}
      <OrbitControls makeDefault enableDamping target={[0, 1, 0]} />
    </Canvas>
  )
}
