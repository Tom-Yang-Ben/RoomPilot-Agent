import * as THREE from "three";

// Builds the architectural shell, openings, circulation overlays, and room surfaces.
export function createViewerArchitecture({
  applySurfaceTint,
  architecturalPbrProfile,
  ceilingGroup,
  clearGroup,
  columnGeometryDescriptor,
  controls,
  createArchitecturalMaterial,
  createCeilingGeometry,
  createFloorMaterial,
  createWallMaterial,
  dedupeArchitecturalOpeningsFor3d,
  doorOpeningForWallTopology,
  grid,
  inferredWallThicknessCm,
  isCameraLocked,
  keyLight,
  normalizedPlanarUvs,
  openingAnchorForWallTopology,
  openingAnchorOnWall,
  openingWallInterval,
  roomGroup,
  scene,
  setViewMode,
  stabilizeWholeHouseWallAppearance,
  synchronizedFloorRegions,
  walkPositionBlocked,
  walkPositionInsideFloor,
  wallMeshes,
  wallSectionSpan,
  wallSegmentForOpening,
  windowOpeningMetrics,
}) {
  function wallSurfaceSegment(segment) {
    const startX = Number(segment?.start?.x);
    const startZ = Number(segment?.start?.z);
    const endX = Number(segment?.end?.x);
    const endZ = Number(segment?.end?.z);
    if (![startX, startZ, endX, endZ].every(Number.isFinite)) return null;
    return {
      start: { x: startX, z: startZ },
      end: { x: endX, z: endZ },
    };
  }

  function tagWallSurface(wallMesh, { segment = null, exteriorSideSign = 0 } = {}) {
    const surfaceSegment = wallSurfaceSegment(segment);
    if (surfaceSegment) {
      wallMesh.userData.roompilotWallSegment = surfaceSegment;
      wallMesh.userData.roompilotExteriorSideSign = Number(exteriorSideSign) || 0;
    }
    return wallMesh;
  }

  function registerWall(wallMesh, surfaceMetadata = {}) {
    wallMesh.castShadow = true;
    wallMesh.receiveShadow = true;
    wallMesh.userData.baseOpacity = 1;
    wallMesh.userData.fullPositionY = wallMesh.position.y;
    wallMesh.userData.fullScaleY = wallMesh.scale.y;
    tagWallSurface(wallMesh, surfaceMetadata);
    wallMeshes.push(wallMesh);
    return wallMesh;
  }

  function buildSegmentWalls(
    roomGroupRef,
    segments,
    wallMaterial,
    wallHeight,
    wallThickness,
    doorSegments = [],
    windowSegments = [],
    floorplan = null,
    surfaceCatalog = null,
    confirmedOpenings = [],
  ) {
    const renderedOpenings = new Set();
    const wallDoorSegments = doorSegments.filter((opening) => (
      opening?.topology_gap !== true && opening?.step4_skip_wall_cut !== true
    ));
    const topologyGapDoors = doorSegments.filter((opening) => opening?.topology_gap === true);
    const exteriorSegments = segments.filter((segment) => (
      isExteriorWallSegment(segment, floorplan, wallThickness)
    ));
    const protectedOpenings = [...confirmedOpenings, ...windowSegments]
      .map((opening) => opening?.wall_opening_segment || opening)
      .filter((opening) => opening?.start && opening?.end);

    function buildConfirmedWallJunctionFills() {
      const junctionToleranceCm = Math.max(36, Number(wallThickness) * 2);
      const maximumCollinearGapCm = Math.min(
        junctionToleranceCm,
        Number(wallThickness) + 4,
      );
      const endpoints = segments.flatMap((segment, segmentIndex) => (
        ["start", "end"].flatMap((key) => {
          const endpoint = wallSegmentPoint(segment, key);
          return endpoint
            ? [{
              key: `${segment.id || segmentIndex}:${key}`,
              segment,
              point: endpoint,
            }]
            : [];
        })
      ));
      const usedEndpoints = new Set();
      const bridgeTouchesProtectedOpening = (start, end) => {
        const midpoint = {
          x: (start.x + end.x) / 2,
          z: (start.z + end.z) / 2,
        };
        const toleranceCm = Math.max(Number(wallThickness) * 0.6, 7);
        return protectedOpenings.some((opening) => {
          const openingSegment = { start: opening.start, end: opening.end };
          return pointToWallSegmentDistance(midpoint, openingSegment) <= toleranceCm
            && (
              pointToWallSegmentDistance(start, openingSegment) <= toleranceCm
              || pointToWallSegmentDistance(end, openingSegment) <= toleranceCm
            );
        });
      };
      const sharesWallAxis = (left, right) => {
        const leftStart = wallSegmentPoint(left, "start");
        const leftEnd = wallSegmentPoint(left, "end");
        const rightStart = wallSegmentPoint(right, "start");
        const rightEnd = wallSegmentPoint(right, "end");
        if (!leftStart || !leftEnd || !rightStart || !rightEnd) return false;
        const leftLength = Math.hypot(leftEnd.x - leftStart.x, leftEnd.z - leftStart.z);
        const rightLength = Math.hypot(rightEnd.x - rightStart.x, rightEnd.z - rightStart.z);
        if (leftLength < 0.8 || rightLength < 0.8) return false;
        const alignment = Math.abs(
          ((leftEnd.x - leftStart.x) * (rightEnd.x - rightStart.x)
            + (leftEnd.z - leftStart.z) * (rightEnd.z - rightStart.z))
            / (leftLength * rightLength),
        );
        return alignment >= 0.995;
      };

      endpoints.forEach((endpoint, index) => {
        if (usedEndpoints.has(endpoint.key)) return;
        const neighbor = endpoints
          .slice(index + 1)
          .filter((candidate) => (
            candidate.segment !== endpoint.segment
            && !usedEndpoints.has(candidate.key)
          ))
          .map((candidate) => ({
            candidate,
            distance: Math.hypot(
              candidate.point.x - endpoint.point.x,
              candidate.point.z - endpoint.point.z,
            ),
          }))
          .filter(({ distance }) => distance > 0.8 && distance <= junctionToleranceCm)
          // Only bridge a small collinear OCR seam.  A nearby perpendicular
          // endpoint is a corner, not missing wall geometry.
          .filter(({ candidate, distance }) => (
            distance <= maximumCollinearGapCm
            && sharesWallAxis(endpoint.segment, candidate.segment)
          ))
          .sort((left, right) => left.distance - right.distance)[0];
        if (!neighbor) return;

        const start = endpoint.point;
        const end = neighbor.candidate.point;
        if (bridgeTouchesProtectedOpening(start, end)) return;
        const dx = end.x - start.x;
        const dz = end.z - start.z;
        const length = Math.hypot(dx, dz);
        if (length < 0.8) return;
        const bridgeSegment = { start, end };
        const bridgeMaterial = typeof wallMaterial === "function"
          ? (wallMaterial.faceMaterials?.(bridgeSegment, 0) || wallMaterial(bridgeSegment))
          : wallMaterial.clone();
        const bridge = new THREE.Mesh(
          new THREE.BoxGeometry(length, wallHeight, wallThickness),
          bridgeMaterial,
        );
        bridge.position.set(
          (start.x + end.x) / 2,
          wallHeight / 2,
          (start.z + end.z) / 2,
        );
        bridge.rotation.y = Math.atan2(-dz, dx);
        bridge.castShadow = true;
        bridge.receiveShadow = true;
        bridge.userData.roompilotArchitecturalDetail = "confirmed-wall-junction-fill";
        roomGroupRef.add(registerWall(bridge, { segment: bridgeSegment }));
        usedEndpoints.add(endpoint.key);
        usedEndpoints.add(neighbor.candidate.key);
      });
    }

    segments.forEach((segment) => {
      const start = segment.start;
      const end = segment.end;
      if (!start || !end) return;

      const dx = Number(end.x) - Number(start.x);
      const dz = Number(end.z) - Number(start.z);
      const length = Math.hypot(dx, dz);
      if (length < 4) return;
      const unitX = dx / length;
      const unitZ = dz / length;
      const rotationY = Math.atan2(-dz, dx);
      const exteriorWall = isExteriorWallSegment(segment, floorplan, wallThickness);
      const exteriorSideSign = exteriorWall
        ? exteriorWallOutwardSideSign(segment, floorplan, unitX, unitZ)
        : 0;
      const wallJunctionInsets = exteriorWall
        ? { start: 0, end: 0 }
        : interiorWallJunctionInsets(segment, exteriorSegments, wallThickness);
      const sectionMin = Math.min(Math.max(wallJunctionInsets.start, 0), length / 2);
      const sectionMax = Math.max(
        sectionMin,
        length - Math.min(Math.max(wallJunctionInsets.end, 0), length / 2),
      );
      if (sectionMax - sectionMin < 4) return;

      const material = typeof wallMaterial === "function"
        ? wallMaterial(segment)
        : wallMaterial;
      const openingIntervals = [...wallDoorSegments.map((opening) => ({ opening, kind: "door" })),
        ...windowSegments.map((opening) => ({ opening, kind: "window" }))]
        .map(({ opening, kind }, index) => {
          const wallInterval = openingWallInterval(
            segment,
            opening,
            wallThickness,
            kind === "door" ? 68 : 50,
          );
          if (!wallInterval) return null;
          const windowMetrics = kind === "window"
            ? windowOpeningMetrics(opening, wallHeight)
            : null;
          const from = Math.max(wallInterval.from, sectionMin);
          const to = Math.min(wallInterval.to, sectionMax);
          if (to - from < 2.5) return null;
          return {
            from,
            to,
            kind,
            id: opening.id || null,
            width: wallInterval.width,
            opening,
            windowMetrics,
            key: opening.id
              || `${kind}-${index}-${wallInterval.centerX.toFixed(2)}-${wallInterval.centerZ.toFixed(2)}`,
          };
        })
        .filter(Boolean)
        .sort((left, right) => left.from - right.from);

      const addWallSection = (from, to, bottom, height, sectionMaterial = material) => {
        if (to - from < 2.5 || height < 2.5) return;
        const span = wallSectionSpan(from, to, length);
        const sectionFrom = span.from;
        const sectionTo = span.to;
        const center = (sectionFrom + sectionTo) / 2;
        const sectionGeometry = new THREE.BoxGeometry(sectionTo - sectionFrom, height, wallThickness);
        const sectionMaterials = typeof wallMaterial.faceMaterials === "function"
          ? wallMaterial.faceMaterials(segment, exteriorSideSign)
          : sectionMaterial.clone();
        const wallMesh = new THREE.Mesh(
          sectionGeometry,
          sectionMaterials,
        );
        wallMesh.position.set(
          Number(start.x) + unitX * center,
          bottom + height / 2,
          Number(start.z) + unitZ * center,
        );
        wallMesh.rotation.y = rotationY;
        roomGroupRef.add(registerWall(wallMesh, { segment, exteriorSideSign }));
      };

      const addBaseboard = (from, to) => {
        if (to - from < 4) return;
        const center = (from + to) / 2;
        const trimMaterials = typeof wallMaterial.faceMaterials === "function"
          ? wallMaterial.faceMaterials(segment, exteriorSideSign)
          : material.clone();
        const trim = new THREE.Mesh(
          new THREE.BoxGeometry(to - from, 7.5, wallThickness + 0.2),
          trimMaterials,
        );
        trim.position.set(
          Number(start.x) + unitX * center,
          3.8,
          Number(start.z) + unitZ * center,
        );
        trim.rotation.y = rotationY;
        trim.castShadow = true;
        trim.receiveShadow = true;
        trim.userData.roompilotArchitecturalDetail = "baseboard";
        roomGroupRef.add(tagWallSurface(trim, { segment, exteriorSideSign }));
      };

      let cursor = sectionMin;
      openingIntervals.forEach((interval) => {
        addWallSection(cursor, interval.from, 0, wallHeight);
        addBaseboard(cursor, interval.from);
        const openingHeight = interval.kind === "door"
          ? Math.min(Number(interval.opening.height_cm || 210), wallHeight - 8)
          : interval.windowMetrics.headHeightCm;
        if (interval.kind === "window") {
          const sillHeight = interval.windowMetrics.sillHeightCm;
          const frameAllowanceCm = 0.6;
          addWallSection(interval.from, interval.to, 0, Math.max(0, sillHeight - frameAllowanceCm));
          addWallSection(
            interval.from,
            interval.to,
            openingHeight + frameAllowanceCm,
            Math.max(0, wallHeight - openingHeight - frameAllowanceCm),
          );
        } else {
          addWallSection(interval.from, interval.to, openingHeight, wallHeight - openingHeight);
        }
        if (!renderedOpenings.has(interval.key)) {
          buildOpeningAssembly(
            roomGroupRef,
            interval,
            {
              ...openingAnchorOnWall(segment, interval),
              rotationY,
              wallThickness,
            },
            surfaceCatalog,
          );
          renderedOpenings.add(interval.key);
        }
        cursor = Math.max(cursor, interval.to);
      });
      addWallSection(cursor, sectionMax, 0, wallHeight);
      addBaseboard(cursor, sectionMax);

      const capLength = sectionMax - sectionMin;
      const capCenter = (sectionMin + sectionMax) / 2;
      const topCapMaterials = typeof wallMaterial.faceMaterials === "function"
        ? wallMaterial.faceMaterials(segment, exteriorSideSign)
        : material.clone();
      const topCap = new THREE.Mesh(
        new THREE.BoxGeometry(capLength, 2.5, wallThickness),
        topCapMaterials,
      );
      topCap.position.set(
        Number(start.x) + unitX * capCenter,
        wallHeight + 1.25,
        Number(start.z) + unitZ * capCenter,
      );
      topCap.rotation.y = rotationY;
      topCap.castShadow = true;
      topCap.receiveShadow = true;
      tagWallSurface(topCap, { segment, exteriorSideSign });
      roomGroupRef.add(topCap);
    });

    buildConfirmedWallJunctionFills();

    // A door may have a valid closed segment but no recognised wall span yet.
    // It must still be rendered once at that closed position; otherwise a
    // confirmed Step 4 door silently disappears in Step 6.
    const missingDoors = doorSegments.filter((opening) => {
      const openingId = String(opening?.id || "").trim();
      return opening?.topology_gap === true
        || opening?.step4_skip_wall_cut === true
        || !openingId
        || !renderedOpenings.has(openingId);
    }).filter((opening) => opening?.step4_skip_wall_cut !== true);
    const missingWindows = windowSegments.filter((opening) => !segments.some(
      (segment) => openingWallInterval(segment, opening, wallThickness, 50),
    ) && opening?.step4_skip_wall_cut !== true);
    if (missingDoors.length || missingWindows.length) {
      const standaloneWallMaterial = typeof wallMaterial === "function"
        ? (opening) => {
          const hostSegment = wallSegmentForOpening(segments, opening, wallThickness);
          return wallMaterial(hostSegment || segments[0] || {});
        }
        : wallMaterial;
      buildStandaloneOpeningAssemblies(
        roomGroupRef,
        missingDoors,
        missingWindows,
        standaloneWallMaterial,
        wallHeight,
        wallThickness,
        surfaceCatalog,
      );
    }
  }

  function buildConfirmedDoorLeaves(
    roomGroupRef,
    doorSegments,
    wallMaterial,
    wallHeight,
    wallThickness,
    surfaceCatalog = null,
  ) {
    const renderedDoorIds = new Set();
    doorSegments.forEach((door, index) => {
      // The Step 4 wall gap is authoritative for every wall component; the
      // closed leaf may be shown on it, but must never define a second opening.
      // A confirmed Step 4 door must still never vanish: when its wall opening
      // can't be resolved (no persisted opening and no detectable wall gap), the
      // closed_leaf_segment is the immutable Step 4 position, so render the leaf
      // + lintel there instead of dropping the door.
      // ponytail: fall back to closed_leaf_segment; do NOT route doors through
      // buildSegmentWalls to "fix" this — that path cuts walls and double-holes.
      const headerSegment = door?.wall_opening_segment || door?.closed_leaf_segment;
      const start = headerSegment?.start;
      const end = headerSegment?.end;
      if (!start || !end) return;
      const dx = Number(end?.x) - Number(start?.x);
      const dz = Number(end?.z) - Number(start?.z);
      const width = Math.hypot(dx, dz);
      if (width < 4) return;
      const id = String(door?.id || `door-${index + 1}`);
      if (renderedDoorIds.has(id)) return;
      const doorHeight = Math.min(
        Math.max(Number(door.height_cm || door.height) || 205, 180),
        wallHeight - 8,
      );
      const headerHeight = wallHeight - doorHeight;
      if (headerHeight >= 2.5) {
        const headerMaterial = typeof wallMaterial === "function"
          ? wallMaterial({ start, end })
          : wallMaterial;
        const headerMaterials = typeof wallMaterial?.faceMaterials === "function"
          ? wallMaterial.faceMaterials({ start, end }, 0)
          : headerMaterial.clone();
        // Extend the lintel fractionally into both jambs so it becomes one
        // continuous wall assembly instead of a visibly floating thin slab.
        const headerOverlapCm = 0.8;
        const header = new THREE.Mesh(
          new THREE.BoxGeometry(
            width + headerOverlapCm,
            headerHeight,
            wallThickness + headerOverlapCm,
          ),
          headerMaterials,
        );
        header.position.set(
          (Number(start.x) + Number(end.x)) / 2,
          doorHeight + headerHeight / 2,
          (Number(start.z) + Number(end.z)) / 2,
        );
        header.rotation.y = Math.atan2(-dz, dx);
        header.castShadow = true;
        header.receiveShadow = true;
        header.userData.roompilotArchitecturalDetail = "door-header-wall";
        header.userData.roompilotArchitecturalId = id;
        roomGroupRef.add(registerWall(header, { segment: { start, end } }));
      }
      buildOpeningAssembly(
        roomGroupRef,
        {
          kind: "door",
          id,
          // The Step 4 opening span owns the physical door width.  Catalog
          // metadata may describe a wider product, but it must never extend
          // a leaf beyond the confirmed wall opening.
          width,
          opening: door,
        },
        {
          x: (Number(start.x) + Number(end.x)) / 2,
          z: (Number(start.z) + Number(end.z)) / 2,
          rotationY: Math.atan2(-dz, dx),
          wallThickness,
        },
        surfaceCatalog,
      );
      renderedDoorIds.add(id);
    });
  }

  function buildOpeningAssembly(roomGroupRef, interval, anchor, surfaceCatalog = null) {
    const isWindow = interval.kind === "window";
    const frameMaterial = createArchitecturalMaterial(
      isWindow ? "window_frame" : "door_leaf",
      surfaceCatalog,
    );
    const height = isWindow ? interval.windowMetrics?.glazingHeightCm || 120 : 205;
    const centerY = isWindow
      ? (interval.windowMetrics?.sillHeightCm || 0) + height / 2
      : height / 2;
    const assembly = new THREE.Group();
    assembly.position.set(anchor.x, 0, anchor.z);
    assembly.rotation.y = anchor.rotationY;
    assembly.userData.roompilotArchitecturalDetail = interval.kind;
    assembly.userData.roompilotArchitecturalId = String(
      interval.id || interval.opening?.id || "",
    ).trim();

    if (isWindow) {
      const frameDepth = Math.max(Number(anchor.wallThickness || 12) + 0.4, 4.2);
      const frameThickness = 4.2;
      const faceOffset = 0;
      const bottomY = centerY - height / 2;
      const topY = centerY + height / 2;
      const glass = new THREE.Mesh(
        new THREE.PlaneGeometry(Math.max(interval.width - frameThickness * 2, 12), Math.max(height - frameThickness * 2, 12)),
        new THREE.MeshPhysicalMaterial({
          color: 0xd9edf2,
          ...architecturalPbrProfile("glass"),
          side: THREE.DoubleSide,
        }),
      );
      glass.position.y = centerY;
      glass.position.z = 0;
      glass.castShadow = false;
      assembly.add(glass);
      const mullionPositions = [0];
      [
        [interval.width, frameThickness, 0, bottomY],
        [interval.width, frameThickness, 0, topY],
        [frameThickness, height, -interval.width / 2, centerY],
        [frameThickness, height, interval.width / 2, centerY],
        ...mullionPositions.map((x) => [3.2, height - frameThickness, x, centerY]),
      ].forEach(([width, frameHeight, x, y]) => {
        const frame = new THREE.Mesh(
          new THREE.BoxGeometry(width, frameHeight, frameDepth),
          frameMaterial,
        );
        frame.position.set(x, y, faceOffset);
        frame.castShadow = true;
        frame.receiveShadow = true;
        assembly.add(frame);
      });
      const sill = new THREE.Mesh(
        new THREE.BoxGeometry(interval.width + 8, 2.2, frameDepth + 4),
        frameMaterial,
      );
      sill.position.set(0, bottomY - 1.1, 0);
      sill.castShadow = true;
      sill.receiveShadow = true;
      sill.userData.roompilotArchitecturalDetail = "flush-window-sill";
      assembly.add(sill);
    } else {
      // The wall opening is the single Step 4 source of truth.  A separately
      // inferred leaf line can be slightly offset and must not pull the door
      // out of its actual opening in the Step 6 scene.
      const doorLeafInsetCm = 0.6;
      const leafWidth = Math.max(interval.width - doorLeafInsetCm, 60);
      const leafDepth = Math.max(
        Math.min(Number(anchor.wallThickness || 12) - 1.2, 5),
        2,
      );
      const leaf = new THREE.Mesh(
        new THREE.BoxGeometry(leafWidth, height, leafDepth),
        frameMaterial,
      );
      leaf.position.set(0, centerY, 0);
      leaf.castShadow = true;
      leaf.receiveShadow = true;
      leaf.userData.roompilotArchitecturalDetail = "closed-door-leaf";
      assembly.add(leaf);
    }
    roomGroupRef.add(assembly);
  }

  function buildStandaloneOpeningAssemblies(
    roomGroupRef,
    doorSegments,
    windowSegments,
    wallMaterial,
    wallHeight,
    wallThickness,
    surfaceCatalog = null,
  ) {
    [
      ...doorSegments.map((opening) => ({ opening, kind: "door" })),
      ...windowSegments.map((opening) => ({ opening, kind: "window" })),
    ].forEach(({ opening, kind }) => {
      const openingWallMaterial = typeof wallMaterial === "function"
        ? wallMaterial(opening)
        : wallMaterial;
      const openingWallMaterials = typeof wallMaterial?.faceMaterials === "function"
        ? wallMaterial.faceMaterials(opening, 0)
        : openingWallMaterial.clone();
      const start = opening.start || {};
      const end = opening.end || {};
      const dx = Number(end.x || 0) - Number(start.x || 0);
      const dz = Number(end.z || 0) - Number(start.z || 0);
      const measuredWidth = Math.hypot(dx, dz);
      if (measuredWidth < 4) return;
      // A standalone opening has no host-wall interval to clamp against, so
      // use its detected segment exactly.  This keeps the assembly coplanar
      // with the recognised wall instead of letting catalog dimensions push
      // it into a neighbouring wall or across a corner.
      const openingWidth = measuredWidth;
      const windowMetrics = kind === "window"
        ? windowOpeningMetrics(opening, wallHeight)
        : null;
      buildOpeningAssembly(
        roomGroupRef,
        {
          kind,
          id: opening.id || null,
          width: openingWidth,
          opening,
          windowMetrics,
        },
        {
          x: (Number(start.x || 0) + Number(end.x || 0)) / 2,
          z: (Number(start.z || 0) + Number(end.z || 0)) / 2,
          rotationY: Math.atan2(-dz, dx),
          wallThickness,
        },
        surfaceCatalog,
      );
      const isWindow = kind === "window";
      const openingHeight = isWindow
        ? windowMetrics.headHeightCm
        : Math.min(Number(opening.height_cm || 210), wallHeight - 8);
      const sillHeight = isWindow
        ? windowMetrics.sillHeightCm
        : 0;
      const addOpeningWallSection = (bottom, height, detail) => {
        if (height < 2.5) return;
        const section = new THREE.Mesh(
          new THREE.BoxGeometry(
            openingWidth,
            height,
            wallThickness,
          ),
          openingWallMaterials,
        );
        section.position.set(
          (Number(start.x || 0) + Number(end.x || 0)) / 2,
          bottom + height / 2,
          (Number(start.z || 0) + Number(end.z || 0)) / 2,
        );
        section.rotation.y = Math.atan2(-dz, dx);
        section.userData.roompilotArchitecturalDetail = detail;
        roomGroupRef.add(registerWall(section, { segment: { start, end } }));
      };
      if (isWindow) {
        const frameAllowanceCm = 0.6;
        addOpeningWallSection(0, Math.max(0, sillHeight - frameAllowanceCm), "window-wall-sill");
        addOpeningWallSection(
          openingHeight + frameAllowanceCm,
          Math.max(0, wallHeight - openingHeight - frameAllowanceCm),
          "window-wall-header",
        );
      } else {
        addOpeningWallSection(
          openingHeight,
          wallHeight - openingHeight,
          "door-wall-header",
        );
      }
    });
  }

  function buildStructuralMembers(roomGroupRef, floorplan, wallHeight) {
    const material = new THREE.MeshStandardMaterial({
      color: 0xb9b3aa,
      roughness: 0.88,
      metalness: 0.02,
    });
    (floorplan.beam_segments || []).forEach((segment) => {
      const start = segment.start;
      const end = segment.end;
      if (!start || !end) return;
      const dx = Number(end.x) - Number(start.x);
      const dz = Number(end.z) - Number(start.z);
      const length = Math.hypot(dx, dz);
      if (length < 4) return;
      const width = Math.max(Number(segment.width_cm || segment.thickness_cm || 30), 12);
      const height = Math.max(Number(segment.height_cm || 35), 12);
      const top = Math.min(Number(segment.top_cm || wallHeight), wallHeight);
      const beam = new THREE.Mesh(
        new THREE.BoxGeometry(length, height, width),
        material.clone(),
      );
      beam.position.set(
        (Number(start.x) + Number(end.x)) / 2,
        Math.max(height / 2, top - height / 2),
        (Number(start.z) + Number(end.z)) / 2,
      );
      beam.rotation.y = Math.atan2(-dz, dx);
      beam.castShadow = true;
      beam.receiveShadow = true;
      beam.userData.roompilotStructure = "beam";
      roomGroupRef.add(beam);
    });
    (floorplan.columns || []).forEach((column) => {
      const center = column.center;
      if (!center) return;
      const geometry = columnGeometryDescriptor(column, {
        minimumDimensionCm: 10,
        defaultHeightCm: wallHeight,
      });
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(geometry.widthCm, geometry.heightCm, geometry.depthCm),
        material.clone(),
      );
      mesh.position.set(geometry.centerX, geometry.centerHeightCm, geometry.centerZ);
      mesh.rotation.y = -THREE.MathUtils.degToRad(geometry.rotationDeg);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.userData.roompilotStructure = "column";
      roomGroupRef.add(mesh);
    });
  }

  function buildFloorPlanOverlay(roomGroupRef, segments, color, opacity = 0.55, yOffset = 2.5) {
    if (!segments?.length) return;

    const points = [];
    segments.forEach((segment) => {
      const start = segment.start;
      const end = segment.end;
      if (!start || !end) return;
      points.push(new THREE.Vector3(start.x, yOffset, start.z));
      points.push(new THREE.Vector3(end.x, yOffset, end.z));
    });

    if (!points.length) return;

    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity,
      depthWrite: false,
    });
    const lines = new THREE.LineSegments(geometry, material);
    lines.renderOrder = 20;
    roomGroupRef.add(lines);
  }

  function segmentMidpoint(segment) {
    return {
      x: (Number(segment.start?.x) + Number(segment.end?.x)) / 2,
      z: (Number(segment.start?.z) + Number(segment.end?.z)) / 2,
    };
  }

  function circulationAccessPoint(segment, reference, clearanceCm = 38) {
    const midpoint = segmentMidpoint(segment);
    const dx = Number(segment.end?.x) - Number(segment.start?.x);
    const dz = Number(segment.end?.z) - Number(segment.start?.z);
    const length = Math.hypot(dx, dz) || 1;
    const normal = { x: -dz / length, z: dx / length };
    const candidates = [1, -1].map((side) => ({
      x: midpoint.x + normal.x * clearanceCm * side,
      z: midpoint.z + normal.z * clearanceCm * side,
    })).filter(
      (point) => walkPositionInsideFloor(point) && !walkPositionBlocked(point, 17),
    );
    if (!candidates.length) return midpoint;
    return candidates.sort(
      (left, right) => Math.hypot(left.x - reference.x, left.z - reference.z)
        - Math.hypot(right.x - reference.x, right.z - reference.z),
    )[0];
  }

  function findCirculationPath(start, goal, floorplan, cellSize = 20) {
    const widthCm = Math.max(Number(floorplan.width_cm), 240);
    const depthCm = Math.max(Number(floorplan.depth_cm), 240);
    const minX = -widthCm / 2;
    const minZ = -depthCm / 2;
    const columns = Math.ceil(widthCm / cellSize) + 1;
    const rows = Math.ceil(depthCm / cellSize) + 1;
    const toCell = (point) => ({
      x: THREE.MathUtils.clamp(Math.round((point.x - minX) / cellSize), 0, columns - 1),
      z: THREE.MathUtils.clamp(Math.round((point.z - minZ) / cellSize), 0, rows - 1),
    });
    const toPoint = (cell) => ({
      x: minX + cell.x * cellSize,
      z: minZ + cell.z * cellSize,
    });
    const keyOf = (cell) => `${cell.x}:${cell.z}`;
    const isWalkable = (cell) => {
      const point = toPoint(cell);
      return walkPositionInsideFloor(point) && !walkPositionBlocked(point, 17);
    };
    const nearestWalkable = (point) => {
      const origin = toCell(point);
      if (isWalkable(origin)) return origin;
      for (let radius = 1; radius <= 5; radius += 1) {
        for (let x = -radius; x <= radius; x += 1) {
          for (let z = -radius; z <= radius; z += 1) {
            const candidate = { x: origin.x + x, z: origin.z + z };
            if (
              candidate.x >= 0 && candidate.x < columns
              && candidate.z >= 0 && candidate.z < rows
              && isWalkable(candidate)
            ) return candidate;
          }
        }
      }
      return null;
    };

    const startCell = nearestWalkable(start);
    const goalCell = nearestWalkable(goal);
    if (!startCell || !goalCell) return [];
    const goalKey = keyOf(goalCell);
    const open = [{ cell: startCell, score: 0 }];
    const cameFrom = new Map();
    const distance = new Map([[keyOf(startCell), 0]]);
    const closed = new Set();
    const directions = [
      [1, 0, 1], [-1, 0, 1], [0, 1, 1], [0, -1, 1],
      [1, 1, Math.SQRT2], [1, -1, Math.SQRT2],
      [-1, 1, Math.SQRT2], [-1, -1, Math.SQRT2],
    ];

    while (open.length) {
      open.sort((left, right) => left.score - right.score);
      const current = open.shift().cell;
      const currentKey = keyOf(current);
      if (closed.has(currentKey)) continue;
      if (currentKey === goalKey) {
        const cells = [current];
        let cursor = currentKey;
        while (cameFrom.has(cursor)) {
          const previous = cameFrom.get(cursor);
          cells.push(previous);
          cursor = keyOf(previous);
        }
        return simplifyCirculationPath(cells.reverse().map(toPoint));
      }
      closed.add(currentKey);

      directions.forEach(([stepX, stepZ, stepCost]) => {
        const next = { x: current.x + stepX, z: current.z + stepZ };
        if (
          next.x < 0 || next.x >= columns || next.z < 0 || next.z >= rows
          || !isWalkable(next)
        ) return;
        const nextKey = keyOf(next);
        const nextDistance = (distance.get(currentKey) || 0) + stepCost;
        if (nextDistance >= (distance.get(nextKey) ?? Infinity)) return;
        distance.set(nextKey, nextDistance);
        cameFrom.set(nextKey, current);
        const heuristic = Math.hypot(next.x - goalCell.x, next.z - goalCell.z);
        open.push({ cell: next, score: nextDistance + heuristic });
      });
    }
    return [];
  }

  function circulationSegmentWalkable(start, end) {
    const distance = Math.hypot(end.x - start.x, end.z - start.z);
    const steps = Math.max(Math.ceil(distance / 10), 1);
    for (let index = 0; index <= steps; index += 1) {
      const progress = index / steps;
      const point = {
        x: THREE.MathUtils.lerp(start.x, end.x, progress),
        z: THREE.MathUtils.lerp(start.z, end.z, progress),
      };
      if (!walkPositionInsideFloor(point) || walkPositionBlocked(point, 17)) return false;
    }
    return true;
  }

  function simplifyCirculationPath(points) {
    if (points.length <= 2) return points;
    const simplified = [points[0]];
    let anchor = 0;
    while (anchor < points.length - 1) {
      let next = points.length - 1;
      while (next > anchor + 1 && !circulationSegmentWalkable(points[anchor], points[next])) {
        next -= 1;
      }
      simplified.push(points[next]);
      anchor = next;
    }
    return simplified;
  }

  function addCirculationStrip(roomGroupRef, points, color = 0x2f7d64) {
    const material = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: 0.82,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    points.slice(1).forEach((point, index) => {
      const previous = points[index];
      const dx = point.x - previous.x;
      const dz = point.z - previous.z;
      const length = Math.hypot(dx, dz);
      if (length < 2) return;
      const strip = new THREE.Mesh(
        new THREE.BoxGeometry(length + 3, 1.2, 11),
        material,
      );
      strip.position.set((point.x + previous.x) / 2, 3.8, (point.z + previous.z) / 2);
      strip.rotation.y = Math.atan2(-dz, dx);
      strip.renderOrder = 24;
      strip.userData.roompilotCirculation = true;
      roomGroupRef.add(strip);
    });

    for (let index = 1; index < points.length; index += 2) {
      const previous = points[index - 1];
      const point = points[index];
      const direction = new THREE.Vector3(point.x - previous.x, 0, point.z - previous.z).normalize();
      const arrow = new THREE.Mesh(
        new THREE.ConeGeometry(11, 24, 3),
        material.clone(),
      );
      arrow.position.set(point.x, 5.2, point.z);
      arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction);
      arrow.renderOrder = 25;
      arrow.userData.roompilotCirculation = true;
      roomGroupRef.add(arrow);
    }
  }

  function createCirculationLabel(text) {
    const canvas = document.createElement("canvas");
    canvas.width = 256;
    canvas.height = 96;
    const context = canvas.getContext("2d");
    context.fillStyle = "rgba(255,255,255,0.94)";
    context.strokeStyle = "#2f7d64";
    context.lineWidth = 5;
    context.beginPath();
    context.roundRect(8, 8, 240, 80, 18);
    context.fill();
    context.stroke();
    context.fillStyle = "#214f42";
    context.font = "700 40px sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(text, 128, 50);
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
      map: new THREE.CanvasTexture(canvas),
      transparent: true,
      depthTest: false,
    }));
    sprite.scale.set(110, 42, 1);
    sprite.renderOrder = 30;
    sprite.userData.roompilotCirculation = true;
    return sprite;
  }

  function buildCirculationRoute(roomGroupRef, floorplan) {
    const doors = (floorplan.door_segments || []).filter(
      (segment) => segment.start && segment.end,
    );
    if (doors.length < 2) return;
    const widthCm = Math.max(Number(floorplan.width_cm), 240);
    const depthCm = Math.max(Number(floorplan.depth_cm), 240);
    const edgeDistance = (point) => Math.min(
      Math.abs(point.x + widthCm / 2),
      Math.abs(point.x - widthCm / 2),
      Math.abs(point.z + depthCm / 2),
      Math.abs(point.z - depthCm / 2),
    );
    const entrance = [...doors].sort((left, right) => {
      const leftMidpoint = segmentMidpoint(left);
      const rightMidpoint = segmentMidpoint(right);
      const edgeDifference = edgeDistance(leftMidpoint) - edgeDistance(rightMidpoint);
      return Math.abs(edgeDifference) > 8
        ? edgeDifference
        : rightMidpoint.z - leftMidpoint.z;
    })[0];
    const entranceMidpoint = segmentMidpoint(entrance);
    const entranceAccess = circulationAccessPoint(entrance, { x: 0, z: 0 });
    const startMarker = new THREE.Mesh(
      new THREE.CircleGeometry(23, 32),
      new THREE.MeshBasicMaterial({
        color: 0x2f7d64,
        transparent: true,
        opacity: 0.92,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
    );
    startMarker.rotation.x = -Math.PI / 2;
    startMarker.position.set(entranceAccess.x, 4, entranceAccess.z);
    startMarker.renderOrder = 26;
    startMarker.userData.roompilotCirculation = true;
    roomGroupRef.add(startMarker);
    const label = createCirculationLabel("玄關");
    label.position.set(entranceAccess.x, 42, entranceAccess.z);
    label.userData = { ...label.userData, label: "玄關" };
    roomGroupRef.add(label);

    doors.filter((door) => door !== entrance).forEach((door) => {
      const goal = circulationAccessPoint(door, entranceAccess);
      const path = findCirculationPath(entranceAccess, goal, floorplan);
      if (path.length > 1) addCirculationStrip(roomGroupRef, path);
    });
    addCirculationStrip(roomGroupRef, [entranceMidpoint, entranceAccess]);
  }

  function createMaterialBoundarySurfaces(roomGroupRef, boundary, floorMaterial, sceneData) {
    const bounds = boundary?.room_bounds_cm;
    const line = boundary?.line_cm;
    if (!bounds || !Array.isArray(line) || line.length < 2) return;
    const minX = Number(bounds.minX);
    const maxX = Number(bounds.maxX);
    const minZ = Number(bounds.minZ);
    const maxZ = Number(bounds.maxZ);
    const vertical = Math.abs(Number(line[1].x) - Number(line[0].x))
      <= Math.abs(Number(line[1].y) - Number(line[0].y));
    const split = vertical
      ? Math.max(minX, Math.min(maxX, (Number(line[0].x) + Number(line[1].x)) / 2))
      : Math.max(minZ, Math.min(maxZ, (Number(line[0].y) + Number(line[1].y)) / 2));
    const palette = sceneData.style_card?.palette_hex || sceneData.style?.palette_hex || [];
    const materials = [floorMaterial.clone(), floorMaterial.clone()];
    applySurfaceTint(materials[0], palette[1] || "#c9a77d");
    applySurfaceTint(materials[1], palette[3] || "#8b684b");
    const parts = vertical
      ? [
          { width: split - minX, depth: maxZ - minZ, x: (minX + split) / 2, z: (minZ + maxZ) / 2 },
          { width: maxX - split, depth: maxZ - minZ, x: (split + maxX) / 2, z: (minZ + maxZ) / 2 },
        ]
      : [
          { width: maxX - minX, depth: split - minZ, x: (minX + maxX) / 2, z: (minZ + split) / 2 },
          { width: maxX - minX, depth: maxZ - split, x: (minX + maxX) / 2, z: (split + maxZ) / 2 },
        ];
    parts.forEach((part, index) => {
      if (part.width < 2 || part.depth < 2) return;
      const surface = new THREE.Mesh(
        new THREE.PlaneGeometry(part.width, part.depth),
        materials[index],
      );
      surface.rotation.x = -Math.PI / 2;
      surface.position.set(part.x, 0.6 + index * 0.1, part.z);
      surface.receiveShadow = true;
      surface.userData.roompilotMaterialZone = index + 1;
      roomGroupRef.add(surface);
    });
  }

  function pointInBounds(point, bounds, padding = 0) {
    return point.x >= Number(bounds.minX) - padding
      && point.x <= Number(bounds.maxX) + padding
      && point.z >= Number(bounds.minZ) - padding
      && point.z <= Number(bounds.maxZ) + padding;
  }

  function applyNormalizedPlanarUvs(geometry) {
    const position = geometry?.getAttribute?.("position");
    if (!position?.array?.length) return geometry;
    geometry.setAttribute(
      "uv",
      new THREE.Float32BufferAttribute(normalizedPlanarUvs(position.array), 2),
    );
    return geometry;
  }

  function createRoomSurfaceOverrides(roomGroupRef, sceneData) {
    (sceneData.surface_overrides || []).forEach((override, index) => {
      const bounds = override.room_bounds_cm;
      if (!bounds) return;
      const width = Number(bounds.maxX) - Number(bounds.minX);
      const depth = Number(bounds.maxZ) - Number(bounds.minZ);
      if (width < 2 || depth < 2) return;
      const material = createFloorMaterial(
        override.floor_option || "auto",
        sceneData.surface_catalog,
        { widthCm: width, depthCm: depth },
      );
      applySurfaceTint(material, override.floor_color_hex);
      const polygon = override.room_polygon_cm || [];
      let geometry;
      if (polygon.length >= 3) {
        const shape = new THREE.Shape();
        polygon.forEach((point, pointIndex) => {
          const x = Number(point.x);
          const y = -Number(point.z);
          if (pointIndex === 0) shape.moveTo(x, y);
          else shape.lineTo(x, y);
        });
        shape.closePath();
        geometry = new THREE.ShapeGeometry(shape);
        applyNormalizedPlanarUvs(geometry);
      } else {
        geometry = new THREE.PlaneGeometry(width, depth);
      }
      const surface = new THREE.Mesh(geometry, material);
      surface.rotation.x = -Math.PI / 2;
      surface.position.y = 0.4 + index * 0.1;
      if (polygon.length < 3) {
        surface.position.x = (Number(bounds.minX) + Number(bounds.maxX)) / 2;
        surface.position.z = (Number(bounds.minZ) + Number(bounds.maxZ)) / 2;
      }
      surface.receiveShadow = true;
      surface.userData.roompilotSurfaceOverride = override.room_id;
      roomGroupRef.add(surface);
    });
  }

  function createRoomCeilingOverrides(sceneData, wallHeight) {
    const dropByStyle = {
      flat: 12,
      cove: 18,
      floating: 20,
      linear: 14,
      "no-main-light": 12,
      "wood-grid": 16,
    };
    (sceneData.surface_overrides || []).forEach((override, index) => {
      const styleId = override.ceiling_style_id || "exposed";
      const polygon = override.room_polygon_cm || [];
      if (styleId === "exposed" || polygon.length < 3) return;
      const shape = new THREE.Shape();
      polygon.forEach((point, pointIndex) => {
        const x = Number(point.x);
        const y = -Number(point.z);
        if (pointIndex === 0) shape.moveTo(x, y);
        else shape.lineTo(x, y);
      });
      shape.closePath();
      const material = new THREE.MeshStandardMaterial({
        color: new THREE.Color(override.ceiling_color_hex || "#f4f1eb"),
        roughness: override.ceiling_material_id === "wood-veneer" ? 0.72 : 0.9,
        metalness: styleId === "linear" ? 0.12 : 0,
        side: THREE.DoubleSide,
      });
      const panel = new THREE.Mesh(new THREE.ShapeGeometry(shape), material);
      panel.rotation.x = Math.PI / 2;
      panel.position.y = wallHeight - (dropByStyle[styleId] || 12) - index * 0.05;
      panel.receiveShadow = true;
      panel.userData.roompilotCeilingOverride = override.room_id;
      panel.userData.ceilingStyle = styleId;
      panel.userData.ceilingMaterial = override.ceiling_material_id || "flat-paint";
      panel.userData.lightingId = override.lighting_id || "";
      ceilingGroup.add(panel);
    });
  }

  function wallMaterialResolver(sceneData, defaultMaterial) {
    // A room can be saved more than once while the questionnaire auto-saves.
    // Only the most recent record for that room may influence the final scene.
    const canonicalOverrides = new Map();
    (sceneData.surface_overrides || []).forEach((override) => {
      const roomId = String(override?.room_id || "").trim();
      if (roomId) canonicalOverrides.set(roomId, override);
    });
    const roomOverrides = [...canonicalOverrides.values()];
    const cache = new Map();
    const firstOverride = roomOverrides[0] || null;
    const usesOneWholeHouseWall = Boolean(firstOverride) && roomOverrides.every((override) => (
      override.wall_option === firstOverride.wall_option
        && override.wall_color_hex === firstOverride.wall_color_hex
    ));
    const pointToSegmentDistance = (point, start, end) => {
      const dx = Number(end.x) - Number(start.x);
      const dz = Number(end.z) - Number(start.z);
      const lengthSquared = dx * dx + dz * dz;
      if (lengthSquared < 0.0001) {
        return Math.hypot(point.x - Number(start.x), point.z - Number(start.z));
      }
      const projection = THREE.MathUtils.clamp(
        ((point.x - Number(start.x)) * dx + (point.z - Number(start.z)) * dz)
          / lengthSquared,
        0,
        1,
      );
      return Math.hypot(
        point.x - (Number(start.x) + projection * dx),
        point.z - (Number(start.z) + projection * dz),
      );
    };
    const distanceToRoomBoundary = (point, override) => {
      const polygon = override.room_polygon_cm || [];
      if (polygon.length >= 3) {
        return polygon.reduce((nearest, current, index) => {
          const next = polygon[(index + 1) % polygon.length];
          const start = ringPointCoordinates(current);
          const end = ringPointCoordinates(next);
          return (!start || !end)
            ? nearest
            : Math.min(nearest, pointToSegmentDistance(point, start, end));
        }, Infinity);
      }
      const bounds = override.room_bounds_cm;
      if (!bounds) return Infinity;
      const nearestX = THREE.MathUtils.clamp(point.x, Number(bounds.minX), Number(bounds.maxX));
      const nearestZ = THREE.MathUtils.clamp(point.z, Number(bounds.minZ), Number(bounds.maxZ));
      return Math.hypot(point.x - nearestX, point.z - nearestZ);
    };
    function roomOverrideForInteriorPoint(point) {
      const exact = roomOverrides.filter((item) => {
        const polygon = item.room_polygon_cm || [];
        return polygon.length >= 3
          ? ringContainsPoint(point, polygon)
          : (item.room_bounds_cm && pointInBounds(point, item.room_bounds_cm, 18));
      });
      if (exact.length) return exact[0];

      // A wall face lies exactly on the room boundary.  Imperfect OCR polygons
      // can leave a few centimetres of drift, so retain the closest room rather
      // than falling back to an unrelated exterior/default finish.
      const nearest = roomOverrides
        .map((item) => ({ item, distance: distanceToRoomBoundary(point, item) }))
        .sort((left, right) => left.distance - right.distance)[0];
      return nearest?.distance <= 28 ? nearest.item : null;
    }
    const materialForOverride = (override) => {
      if (!override) return defaultMaterial;
      const cacheKey = override.room_id;
      if (!cache.has(cacheKey)) {
        let material = createWallMaterial(
          override.wall_option
            || "auto",
          sceneData.surface_catalog,
          { tintOnly: false },
        );
        applySurfaceTint(
          material,
          override.wall_color_hex,
        );
        if (usesOneWholeHouseWall) material = stabilizeWholeHouseWallAppearance(material);
        material.userData.roompilotWallSurfaceId = override.room_id;
        cache.set(cacheKey, material);
      }
      return cache.get(cacheKey);
    };
    const resolveWallMaterial = (segment) => {
      const midpoint = {
        x: (Number(segment.start?.x || 0) + Number(segment.end?.x || 0)) / 2,
        z: (Number(segment.start?.z || 0) + Number(segment.end?.z || 0)) / 2,
      };
      return materialForOverride(roomOverrideForInteriorPoint(midpoint));
    };
    resolveWallMaterial.faceMaterials = (segment, exteriorSideSign = 1) => {
      const start = segment.start || {};
      const end = segment.end || {};
      const dx = Number(end.x || 0) - Number(start.x || 0);
      const dz = Number(end.z || 0) - Number(start.z || 0);
      const length = Math.hypot(dx, dz);
      if (length < 4) return null;
      const midpoint = {
        x: (Number(start.x || 0) + Number(end.x || 0)) / 2,
        z: (Number(start.z || 0) + Number(end.z || 0)) / 2,
      };
      const normal = { x: -dz / length, z: dx / length };
      const materialForSide = (side) => {
        const sample = {
          x: midpoint.x + normal.x * side * 16,
          z: midpoint.z + normal.z * side * 16,
        };
        return materialForOverride(roomOverrideForInteriorPoint(sample));
      };
      let positiveSide = materialForSide(1);
      let negativeSide = materialForSide(-1);
      // The outside of a perimeter wall has no room polygon to sample.  It
      // therefore inherits the finish from the room on the opposite side,
      // instead of silently reverting to the generic wall material.
      if (exteriorSideSign) {
        const adjacentInteriorMaterial = materialForSide(-exteriorSideSign);
        if (exteriorSideSign > 0) positiveSide = adjacentInteriorMaterial;
        else negativeSide = adjacentInteriorMaterial;
      }
      const interior = resolveWallMaterial(segment);
      const materials = [
        interior.clone(), interior.clone(), interior.clone(),
        interior.clone(), positiveSide.clone(), negativeSide.clone(),
      ];
      return materials;
    };
    return resolveWallMaterial;
  }

  function wallSegmentPoint(segment, key) {
    const point = segment?.[key];
    const x = Number(point?.x);
    const z = Number(point?.z);
    if (!Number.isFinite(x) || !Number.isFinite(z)) return null;
    return { x, z };
  }

  function pointToWallSegmentDistance(point, segment) {
    const start = wallSegmentPoint(segment, "start");
    const end = wallSegmentPoint(segment, "end");
    if (!point || !start || !end) return Infinity;
    const dx = end.x - start.x;
    const dz = end.z - start.z;
    const lengthSquared = dx * dx + dz * dz;
    if (lengthSquared < 0.01) return Math.hypot(point.x - start.x, point.z - start.z);
    const projection = THREE.MathUtils.clamp(
      ((point.x - start.x) * dx + (point.z - start.z) * dz) / lengthSquared,
      0,
      1,
    );
    return Math.hypot(
      point.x - (start.x + projection * dx),
      point.z - (start.z + projection * dz),
    );
  }

  function wallSegmentBounds(floorplan = {}) {
    const points = (floorplan.wall_segments || [])
      .flatMap((segment) => [wallSegmentPoint(segment, "start"), wallSegmentPoint(segment, "end")])
      .filter(Boolean);
    if (!points.length) return null;
    return points.reduce((bounds, point) => ({
      minX: Math.min(bounds.minX, point.x),
      maxX: Math.max(bounds.maxX, point.x),
      minZ: Math.min(bounds.minZ, point.z),
      maxZ: Math.max(bounds.maxZ, point.z),
    }), {
      minX: Infinity,
      maxX: -Infinity,
      minZ: Infinity,
      maxZ: -Infinity,
    });
  }

  function ringPointCoordinates(point) {
    const x = Number(Array.isArray(point) ? point[0] : point?.x);
    const z = Number(Array.isArray(point) ? point[1] : point?.z ?? point?.y);
    if (!Number.isFinite(x) || !Number.isFinite(z)) return null;
    return { x, z };
  }

  function ringContainsPoint(position, ring) {
    if (!Array.isArray(ring) || ring.length < 3) return false;
    let inside = false;
    for (let current = 0, previous = ring.length - 1; current < ring.length; previous = current++) {
      const currentPoint = ringPointCoordinates(ring[current]);
      const previousPoint = ringPointCoordinates(ring[previous]);
      if (!currentPoint || !previousPoint) continue;
      const crosses = (currentPoint.z > position.z) !== (previousPoint.z > position.z);
      const edgeX = ((previousPoint.x - currentPoint.x) * (position.z - currentPoint.z))
        / ((previousPoint.z - currentPoint.z) || Number.EPSILON) + currentPoint.x;
      if (crosses && position.x < edgeX) inside = !inside;
    }
    return inside;
  }

  function floorplanRoomRegions(floorplan = {}) {
    const regions = [
      ...(Array.isArray(floorplan.room_regions) ? floorplan.room_regions : []),
      ...(Array.isArray(floorplan.rooms) ? floorplan.rooms : []),
    ];
    return regions
      .map((region) => ({
        exterior: region.exterior || region.polygon_cm || [],
        holes: region.holes || [],
      }))
      .filter((region) => Array.isArray(region.exterior) && region.exterior.length >= 3);
  }

  function pointInsideAnyFloorplanRoom(point, floorplan = {}) {
    return floorplanRoomRegions(floorplan).some((region) => (
      ringContainsPoint(point, region.exterior)
        && !(region.holes || []).some((hole) => ringContainsPoint(point, hole))
    ));
  }

  function isExplicitExteriorWallSegment(segment = {}) {
    const role = String(
      segment.boundary_side
        || segment.wall_role
        || segment.role
        || segment.wall_type
        || segment.type
        || "",
    ).toLowerCase();
    return segment.exterior === true
      || segment.is_exterior === true
      || segment.boundary === true
      || ["exterior", "outer", "perimeter", "boundary"].some((token) => role.includes(token));
  }

  function isExteriorWallSegment(segment, floorplan = {}, toleranceCm = 10) {
    if (isExplicitExteriorWallSegment(segment)) return true;
    const start = wallSegmentPoint(segment, "start");
    const end = wallSegmentPoint(segment, "end");
    if (!start || !end) return false;
    const dx = end.x - start.x;
    const dz = end.z - start.z;
    const length = Math.hypot(dx, dz);
    const roomRegions = floorplanRoomRegions(floorplan);
    if (start && end && length > 0.01 && roomRegions.length) {
      const midpoint = { x: (start.x + end.x) / 2, z: (start.z + end.z) / 2 };
      const offset = Math.max(toleranceCm, 14);
      const normal = { x: -dz / length, z: dx / length };
      const leftInside = pointInsideAnyFloorplanRoom({
        x: midpoint.x + normal.x * offset,
        z: midpoint.z + normal.z * offset,
      }, floorplan);
      const rightInside = pointInsideAnyFloorplanRoom({
        x: midpoint.x - normal.x * offset,
        z: midpoint.z - normal.z * offset,
      }, floorplan);
      if (leftInside || rightInside) return leftInside !== rightInside;
    }
    const bounds = wallSegmentBounds(floorplan);
    if (!bounds) return false;
    const onLeft = Math.abs(start.x - bounds.minX) <= toleranceCm
      && Math.abs(end.x - bounds.minX) <= toleranceCm;
    const onRight = Math.abs(start.x - bounds.maxX) <= toleranceCm
      && Math.abs(end.x - bounds.maxX) <= toleranceCm;
    const onBack = Math.abs(start.z - bounds.minZ) <= toleranceCm
      && Math.abs(end.z - bounds.minZ) <= toleranceCm;
    const onFront = Math.abs(start.z - bounds.maxZ) <= toleranceCm
      && Math.abs(end.z - bounds.maxZ) <= toleranceCm;
    return onLeft || onRight || onBack || onFront
      || wallEndpointTouchesExteriorBounds(start, bounds, toleranceCm)
      || wallEndpointTouchesExteriorBounds(end, bounds, toleranceCm);
  }

  function wallEndpointTouchesExteriorBounds(point, bounds, toleranceCm = 10) {
    return Math.abs(point.x - bounds.minX) <= toleranceCm
      || Math.abs(point.x - bounds.maxX) <= toleranceCm
      || Math.abs(point.z - bounds.minZ) <= toleranceCm
      || Math.abs(point.z - bounds.maxZ) <= toleranceCm;
  }

  function exteriorWallOutwardSideSign(segment, floorplan = {}, unitX = 1, unitZ = 0) {
    const start = wallSegmentPoint(segment, "start");
    const end = wallSegmentPoint(segment, "end");
    if (!start || !end) return 1;
    const normal = { x: -unitZ, z: unitX };
    const length = Math.hypot(end.x - start.x, end.z - start.z);
    const roomRegions = floorplanRoomRegions(floorplan);
    if (length > 0.01 && roomRegions.length) {
      const midpoint = { x: (start.x + end.x) / 2, z: (start.z + end.z) / 2 };
      const offset = 14;
      const plusInside = pointInsideAnyFloorplanRoom({
        x: midpoint.x + normal.x * offset,
        z: midpoint.z + normal.z * offset,
      }, floorplan);
      const minusInside = pointInsideAnyFloorplanRoom({
        x: midpoint.x - normal.x * offset,
        z: midpoint.z - normal.z * offset,
      }, floorplan);
      if (plusInside !== minusInside) {
        return plusInside ? -1 : 1;
      }
    }
    const side = String(segment.boundary_side || "").toLowerCase();
    const outwardBySide = {
      left: { x: -1, z: 0 },
      right: { x: 1, z: 0 },
      top: { x: 0, z: 1 },
      bottom: { x: 0, z: -1 },
    }[side];
    if (outwardBySide) {
      return (outwardBySide.x * normal.x + outwardBySide.z * normal.z) >= 0 ? 1 : -1;
    }
    const bounds = wallSegmentBounds(floorplan);
    if (bounds) {
      const midpoint = { x: (start.x + end.x) / 2, z: (start.z + end.z) / 2 };
      const distances = [
        { vector: { x: -1, z: 0 }, distance: Math.abs(midpoint.x - bounds.minX) },
        { vector: { x: 1, z: 0 }, distance: Math.abs(midpoint.x - bounds.maxX) },
        { vector: { x: 0, z: -1 }, distance: Math.abs(midpoint.z - bounds.minZ) },
        { vector: { x: 0, z: 1 }, distance: Math.abs(midpoint.z - bounds.maxZ) },
      ].sort((left, right) => left.distance - right.distance);
      const outward = distances[0]?.vector;
      if (outward) return (outward.x * normal.x + outward.z * normal.z) >= 0 ? 1 : -1;
    }
    return 1;
  }

  function interiorWallJunctionInsets(segment, exteriorSegments, wallThickness) {
    // Confirmed wall endpoints already describe the real junction.  Do not
    // retract them by half a wall thickness, or a false white slit appears
    // between otherwise continuous walls in the Step 6 model.
    const insetCm = 0;
    const toleranceCm = Math.max(Number(wallThickness) / 2 + 2, 8);
    const endpointTouchesExterior = (key) => {
      const point = wallSegmentPoint(segment, key);
      if (!point) return false;
      return exteriorSegments.some((exteriorSegment) => (
        exteriorSegment !== segment
          && pointToWallSegmentDistance(point, exteriorSegment) <= toleranceCm
      ));
    };
    return {
      start: endpointTouchesExterior("start") ? insetCm : 0,
      end: endpointTouchesExterior("end") ? insetCm : 0,
    };
  }

  function polygonShape(region = {}, includeHoles = true) {
    const exterior = region.exterior || [];
    if (exterior.length < 3) return null;
    const shape = new THREE.Shape();
    exterior.forEach((point, index) => {
      const x = Number(Array.isArray(point) ? point[0] : point.x);
      const z = Number(Array.isArray(point) ? point[1] : point.z);
      if (!Number.isFinite(x) || !Number.isFinite(z)) return;
      if (index === 0) shape.moveTo(x, -z);
      else shape.lineTo(x, -z);
    });
    shape.closePath();
    if (includeHoles) {
      (region.holes || []).forEach((ring) => {
        if (!Array.isArray(ring) || ring.length < 3) return;
        const hole = new THREE.Path();
        ring.forEach((point, index) => {
          const x = Number(Array.isArray(point) ? point[0] : point.x);
          const z = Number(Array.isArray(point) ? point[1] : point.z);
          if (!Number.isFinite(x) || !Number.isFinite(z)) return;
          if (index === 0) hole.moveTo(x, -z);
          else hole.lineTo(x, -z);
        });
        hole.closePath();
        shape.holes.push(hole);
      });
    }
    return shape;
  }

  // 文件 §5.5:多邊形牆擠出 Shape(x,-z) + ExtrudeGeometry(depth=牆高) +
  // rotateX(-90°)。polygonWalls 描述來自 SceneModel;100×100 環 → 世界 bbox
  // x[0,100]、y[0,牆高]、z[-100,0]…在本 repo 的世界對齊平面等價於 z[0,100]。
  function buildWallMass(roomGroupRef, floorplan, material, wallHeight) {
    const wallMassRegions = (floorplan?.wall_polys || []).filter(
      (region) => region?.exterior?.length >= 3,
    );
    if (!wallMassRegions.length) return false;

    wallMassRegions.forEach((region) => {
      const shape = polygonShape(region, true);
      if (!shape) return;
      const geometry = new THREE.ExtrudeGeometry(shape, {
        depth: wallHeight,
        bevelEnabled: false,
        curveSegments: 1,
      });
      geometry.computeVertexNormals();
      const wallMass = new THREE.Mesh(geometry, material.clone());
      wallMass.rotation.x = -Math.PI / 2;
      wallMass.userData.roompilotArchitecturalDetail = "continuous-wall-mass";
      wallMass.userData.roompilotWallHeightAxis = "z";
      wallMass.userData.fullScaleZ = wallMass.scale.z;
      roomGroupRef.add(registerWall(wallMass));
    });
    return true;
  }

  function buildWallMassTopCaps(roomGroupRef, floorplan, material, wallHeight) {
    const wallMassRegions = (floorplan?.wall_polys || []).filter(
      (region) => region?.exterior?.length >= 3,
    );
    wallMassRegions.forEach((region) => {
      const shape = polygonShape(region, true);
      if (!shape) return;
      const cap = new THREE.Mesh(
        new THREE.ShapeGeometry(shape),
        material.clone(),
      );
      cap.rotation.x = -Math.PI / 2;
      cap.position.y = wallHeight + 0.4;
      cap.userData.roompilotArchitecturalDetail = "continuous-wall-mass-top-cap";
      cap.castShadow = true;
      cap.receiveShadow = true;
      roomGroupRef.add(cap);
    });
  }

  function createFloorGeometry(floorplan, widthCm, depthCm) {
    const shapes = synchronizedFloorRegions(floorplan, widthCm, depthCm)
      .map((region) => polygonShape(region, true))
      .filter(Boolean);
    const geometry = new THREE.ShapeGeometry(shapes);
    geometry.computeVertexNormals();
    return geometry;
  }

  function createRoom(sceneData) {
    clearGroup(roomGroup);
    clearGroup(ceilingGroup);
    wallMeshes.length = 0;
    const catalogThumbnailMode = sceneData.design_choices?.catalog_thumbnail_mode === true;

    const widthCm = Math.max(sceneData.floorplan.width_cm, 240);
    const depthCm = Math.max(sceneData.floorplan.depth_cm, 240);
    const wallHeight = Math.max(
      Number(sceneData.floorplan.room_height_cm || 270),
      210,
    );
    const floorOption = sceneData.design_choices?.floor_option || "auto";
    const wallOption = sceneData.design_choices?.wall_option || "auto";

    const floorMaterial = createFloorMaterial(
      floorOption,
      sceneData.surface_catalog,
      { widthCm, depthCm },
    );
    const floorPbr = sceneData.style?.pbr?.floor || {};
    const floorColor = sceneData.design_choices?.floor_color_hex
      || sceneData.style_card?.palette_hex?.[1];
    applySurfaceTint(floorMaterial, floorColor);
    if (floorPbr.roughness != null) floorMaterial.roughness = floorPbr.roughness;
    if (floorPbr.metalness != null) floorMaterial.metalness = floorPbr.metalness;
    const floor = new THREE.Mesh(
      createFloorGeometry(sceneData.floorplan, widthCm, depthCm),
      floorMaterial,
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = 0;
    floor.receiveShadow = true;
    floor.userData.roompilotBaseFloor = true;
    if (!catalogThumbnailMode) roomGroup.add(floor);
    const presentationGround = new THREE.Mesh(
      new THREE.CircleGeometry(Math.max(widthCm, depthCm) * 1.15, 96),
      new THREE.MeshPhysicalMaterial({
        color: 0xe8e5df,
        roughness: 0.96,
        metalness: 0,
        envMapIntensity: 0.28,
      }),
    );
    presentationGround.rotation.x = -Math.PI / 2;
    presentationGround.position.y = -3.2;
    presentationGround.receiveShadow = true;
    presentationGround.userData.roompilotArchitecturalDetail = "shadow-ground";
    if (!catalogThumbnailMode) roomGroup.add(presentationGround);
    const shadowExtent = Math.max(widthCm, depthCm) * 0.72 + 100;
    keyLight.shadow.camera.left = -shadowExtent;
    keyLight.shadow.camera.right = shadowExtent;
    keyLight.shadow.camera.top = shadowExtent;
    keyLight.shadow.camera.bottom = -shadowExtent;
    keyLight.shadow.camera.near = 20;
    keyLight.shadow.camera.far = 3500;
    keyLight.shadow.camera.updateProjectionMatrix();
    if (!catalogThumbnailMode) {
      createRoomSurfaceOverrides(roomGroup, sceneData);
      createMaterialBoundarySurfaces(
        roomGroup,
        sceneData.material_boundary,
        floorMaterial,
        sceneData,
      );
    }

    const wallMaterial = createWallMaterial(wallOption, sceneData.surface_catalog);
    const wallPbr = sceneData.style?.pbr?.wall || {};
    const wallColor = sceneData.design_choices?.wall_color_hex
      || sceneData.style_card?.palette_hex?.[0];
    applySurfaceTint(wallMaterial, wallColor);
    if (wallPbr.roughness != null) wallMaterial.roughness = wallPbr.roughness;
    if (wallPbr.metalness != null) wallMaterial.metalness = wallPbr.metalness;
    const wallThickness = inferredWallThicknessCm(sceneData.floorplan, 12);
    const wallSegments = sceneData.floorplan?.wall_segments || [];
    const doorSegments = dedupeArchitecturalOpeningsFor3d(
      (sceneData.floorplan?.door_segments || []).map(
        (door) => doorOpeningForWallTopology(wallSegments, door, wallThickness),
      ),
      wallSegments,
      wallThickness,
    );
    const windowSegments = dedupeArchitecturalOpeningsFor3d(
      sceneData.floorplan?.window_segments || [],
      wallSegments,
      wallThickness,
    );
    const hasAccurateFloorplan = ["dxf", "user_confirmed"].includes(
      sceneData.floorplan?.source,
    );
    const singleRoomMode = sceneData.design_choices?.single_room_mode !== false;
    roomGroup.userData.roomSize = { widthCm, depthCm, wallHeight };
    roomGroup.userData.ceilingStyle = sceneData.design_choices?.ceiling_style || "exposed";

    const ceilingDropCm = Number(sceneData.design_choices?.ceiling_drop_cm) || 0;
    const ceilingHeight = wallHeight - ceilingDropCm;
    const hasRoomCeilings = (sceneData.surface_overrides || []).some(
      (override) => override.ceiling_style_id && override.ceiling_style_id !== "exposed",
    );
    if (!catalogThumbnailMode) {
      if (hasRoomCeilings) {
        createRoomCeilingOverrides(sceneData, wallHeight);
      } else {
        createCeilingGeometry(
          { widthCm, depthCm, wallHeight, ceilingHeight },
          roomGroup.userData.ceilingStyle,
          sceneData.style_card || sceneData.style || {},
          {
            color: sceneData.design_choices?.ceiling_color_hex,
            material: sceneData.design_choices?.ceiling_material,
          },
        );
      }
    }
    ceilingGroup.visible = false;

    // 12 cm 接近住宅隔間牆；原先 4 cm 會讓雙線牆與轉角看起來像中空。
    // Persisted Step 4 wall segments already contain true door gaps.  Always
    // use them for a confirmed multi-room plan so a blue open-door leaf can
    // never punch an invented opening through an otherwise continuous wall.
    const builtWallMass = !singleRoomMode && hasAccurateFloorplan && !wallSegments.length
      ? buildWallMass(
        roomGroup,
        sceneData.floorplan,
        wallMaterial,
        wallHeight,
      )
      : false;
    if (catalogThumbnailMode) {
      // Product thumbnails intentionally omit room geometry.
    } else if (builtWallMass) {
      buildWallMassTopCaps(
        roomGroup,
        sceneData.floorplan,
        wallMaterial,
        wallHeight,
      );
      buildStandaloneOpeningAssemblies(
        roomGroup,
        doorSegments,
        windowSegments,
        wallMaterial,
        wallHeight,
        wallThickness,
        sceneData.surface_catalog,
      );
    } else if (!builtWallMass && !singleRoomMode && wallSegments.length >= 2) {
      buildSegmentWalls(
        roomGroup,
        wallSegments,
        wallMaterialResolver(sceneData, wallMaterial),
        wallHeight,
        wallThickness,
        [],
        windowSegments,
        sceneData.floorplan,
        sceneData.surface_catalog,
        doorSegments,
      );
      buildConfirmedDoorLeaves(
        roomGroup,
        doorSegments,
        wallMaterialResolver(sceneData, wallMaterial),
        wallHeight,
        wallThickness,
        sceneData.surface_catalog,
      );
    } else {
      const backWall = new THREE.Mesh(new THREE.BoxGeometry(widthCm, wallHeight, wallThickness), wallMaterial.clone());
      backWall.position.set(0, wallHeight / 2, -depthCm / 2);
      roomGroup.add(registerWall(backWall, {
        segment: {
          start: { x: -widthCm / 2, z: -depthCm / 2 },
          end: { x: widthCm / 2, z: -depthCm / 2 },
        },
      }));

      const leftWall = new THREE.Mesh(new THREE.BoxGeometry(wallThickness, wallHeight, depthCm), wallMaterial.clone());
      leftWall.position.set(-widthCm / 2, wallHeight / 2, 0);
      roomGroup.add(registerWall(leftWall, {
        segment: {
          start: { x: -widthCm / 2, z: depthCm / 2 },
          end: { x: -widthCm / 2, z: -depthCm / 2 },
        },
      }));

      const rightWall = new THREE.Mesh(new THREE.BoxGeometry(wallThickness, wallHeight, depthCm), wallMaterial.clone());
      rightWall.position.set(widthCm / 2, wallHeight / 2, 0);
      roomGroup.add(registerWall(rightWall, {
        segment: {
          start: { x: widthCm / 2, z: -depthCm / 2 },
          end: { x: widthCm / 2, z: depthCm / 2 },
        },
      }));
    }

    // Keep a DOM-visible diagnostic for project-page verification. It measures
    // the assemblies actually added to this viewer, not merely input records.
    if (!catalogThumbnailMode) {
      const sourceDoorIds = (sceneData.floorplan?.door_segments || [])
        .map((door) => String(door?.id || "").trim())
        .filter(Boolean);
      const expectedDoorIds = doorSegments
        .map((door) => String(door?.id || "").trim())
        .filter(Boolean);
      const mergedDoorIds = sourceDoorIds.filter((id) => !expectedDoorIds.includes(id));
      const renderedDoors = roomGroup.children
        .filter((child) => child.userData?.roompilotArchitecturalDetail === "door")
        .map((child) => ({
          id: child.userData?.roompilotArchitecturalId || "",
          leafCount: child.children.filter(
            (mesh) => mesh.userData?.roompilotArchitecturalDetail === "closed-door-leaf",
          ).length,
          anchor: {
            x: Math.round(child.position.x * 100) / 100,
            z: Math.round(child.position.z * 100) / 100,
          },
        }))
        .filter((door) => door.id);
      const renderedDoorIds = renderedDoors.map((door) => door.id);
      const sourceDoorById = new Map(
        (sceneData.floorplan?.door_segments || []).map((door) => [String(door?.id || ""), door]),
      );
      const resolvedDoorById = new Map(
        doorSegments.map((door) => [String(door?.id || ""), door]),
      );
      const comparisons = expectedDoorIds.map((id) => {
        const source = sourceDoorById.get(id);
        const resolved = resolvedDoorById.get(id);
        const rendered = renderedDoors.find((door) => door.id === id);
        const confirmedOpening = resolved?.wall_opening_segment || resolved?.confirmed_wall_opening;
        const expectedAnchor = confirmedOpening?.start && confirmedOpening?.end
          ? {
            x: (Number(confirmedOpening.start.x) + Number(confirmedOpening.end.x)) / 2,
            z: (Number(confirmedOpening.start.z) + Number(confirmedOpening.end.z)) / 2,
          }
          : openingAnchorForWallTopology(resolved, wallSegments, wallThickness);
        const endpointDistance = source && resolved
          ? Math.min(
            Math.hypot(source.start.x - resolved.start.x, source.start.z - resolved.start.z)
              + Math.hypot(source.end.x - resolved.end.x, source.end.z - resolved.end.z),
            Math.hypot(source.start.x - resolved.end.x, source.start.z - resolved.end.z)
              + Math.hypot(source.end.x - resolved.start.x, source.end.z - resolved.start.z),
          )
          : Infinity;
        const anchorDistance = expectedAnchor && rendered
          ? Math.hypot(
            expectedAnchor.x - rendered.anchor.x,
            expectedAnchor.z - rendered.anchor.z,
          )
          : Infinity;
        return {
          id,
          source: source ? { start: source.start, end: source.end, hostWallId: source.host_wall_id || null } : null,
          resolved: resolved ? { start: resolved.start, end: resolved.end, hostWallId: resolved.host_wall_id || null } : null,
          expectedAnchor,
          anchorDistance: Number.isFinite(anchorDistance)
            ? Math.round(anchorDistance * 100) / 100
            : null,
          rendered: Boolean(rendered),
          // Recognition endpoints can be normalised in step 4. Compare the
          // rendered opening with the resolved wall anchor, not stale source coordinates.
          status: rendered && (!expectedAnchor || anchorDistance <= 1) ? "matched" : "mismatch",
        };
      });
      const doorDiagnostics = {
        expected: expectedDoorIds.length,
        recognized: sourceDoorIds.length,
        mergedDoorIds,
        resolved: doorSegments.length,
        rendered: renderedDoorIds.length,
        expectedIds: expectedDoorIds,
        renderedIds: renderedDoorIds,
        renderedDoors,
        comparisons,
      };
      container.dataset.roompilotDoorDiagnostics = JSON.stringify(doorDiagnostics);
      container.dispatchEvent(new CustomEvent("roompilot-door-diagnostics", {
        detail: doorDiagnostics,
      }));
    }

    if (!catalogThumbnailMode && hasAccurateFloorplan) {
      buildFloorPlanOverlay(roomGroup, doorSegments, 0xb9773f, 0.82, 3.8);
      buildFloorPlanOverlay(roomGroup, windowSegments, 0x6f9eb4, 0.9, 4.4);
      buildCirculationRoute(roomGroup, sceneData.floorplan);
    } else if (!catalogThumbnailMode && !builtWallMass) {
      const outline = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.BoxGeometry(widthCm, wallHeight, depthCm)),
        new THREE.LineBasicMaterial({ color: 0xb89264, transparent: true, opacity: 0.35 })
      );
      outline.position.set(0, wallHeight / 2, 0);
      roomGroup.add(outline);
    }
    if (!catalogThumbnailMode) {
      buildStructuralMembers(roomGroup, sceneData.floorplan || {}, wallHeight);
    }

    const boundary = sceneData.material_boundary?.line_cm;
    if (!catalogThumbnailMode && Array.isArray(boundary) && boundary.length >= 2) {
      buildFloorPlanOverlay(roomGroup, [{
        start: { x: Number(boundary[0].x) || 0, z: Number(boundary[0].y) || 0 },
        end: { x: Number(boundary[1].x) || 0, z: Number(boundary[1].y) || 0 },
      }], 0x7b56b3, 0.96, 5.2);
    }

    // design_choices.light_style 只餵天花衝突檢查與第 8 步生圖提示詞;3D 場景
    // 不放天花板燈具——它畫在整層平面的中心而非各房中心,會穿牆懸空,而且
    // orbit 視角天花是隱藏的,燈就吊在空中。照明由環境光組(ambient/hemi/key/
    // fill)負責,拿掉燈具不會讓場景變暗。

    if (!isCameraLocked()) {
      controls.target.set(0, 90, 0);
      setViewMode("orbit");
    }
  }

  return { createRoom };
}
