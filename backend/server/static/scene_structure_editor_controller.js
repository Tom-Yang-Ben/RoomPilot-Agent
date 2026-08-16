// Step 4 room and architectural structure editing workflow.
export function createSceneStructureEditorController({
  $,
  $$,
  activePanelName,
  activeScheme,
  activeSchemeId,
  addMissedRoom,
  addRoomReviewReason,
  allRoomsHaveSchemeSelections,
  allStepSixRoomSurfacesConfirmed,
  analysisReviewItems,
  applyAttachedOpeningUpdates,
  applyCanonicalRoomLabels,
  applyDjangoZoneRoomLabels,
  applyUnavailableRoomSchemeDefaults,
  applyWindowTypePreset,
  attachedOpenings,
  attachedOpeningUpdates,
  beamDragGeometry,
  buildDimensionedPlanAnnotations,
  buildRoomSchemePreviewScene,
  CANONICAL_ROOM_LABELS,
  captureConfirmedStructureSnapshot,
  chooseRoomScheme,
  CIRCLED_ROOM_ORDINALS,
  clipPolygonByLine,
  closeRoomSchemeSelectionDialog,
  cmToPixel,
  completeRoomSchemeSelection,
  composeSelectedRoomFurniture,
  configurationSnapshot,
  confirmAllRooms,
  confirmedFloorplanEditor,
  confirmedRoomHeightCm,
  confirmedStepSixSurfaceCount,
  confirmedWallGapForDoor,
  confirmedWallOpeningForSnapshot,
  confirmRoom,
  convexHull,
  deactivateWhiteInteractionMode,
  dedupeDoorCandidates,
  dedupeWindowCandidates,
  deleteRoom,
  element,
  ensureRoomScheme3dPreviews,
  ensureRoomSchemeAlternative,
  ensureSchemeB,
  errorMessage,
  escapeHtml,
  findStructureWallCollision,
  focusStepSixRoom,
  genericPendingRoomLabel,
  glbThumbnailQueue,
  glbThumbnailViewer,
  goTo,
  hasStepFourConfirmedOpening,
  hydrateConfirmedStructureSnapshot,
  hydrateSceneWallMass,
  ICON_INFERENCE_MAX_ROOM_AREA_M2,
  imagePoint,
  initializeRoomsAndStructures,
  insertRoomNodeAt,
  instructions,
  invalidateDownstreamFrom,
  isDismissedAutoRoom,
  isStructuralSnapshotPoint,
  lockedConfigurationSnapshot,
  materialOptionsForStyle,
  mergeSelectedRoomNodes,
  mergeSelectedRooms,
  navigateRoomScheme3dPreview,
  nearestPointOnRoomEdge,
  normalizedWindowType,
  normalizeIconInferredRoomReview,
  openRoomScheme3dPreview,
  openRoomSchemeSelectionDialog,
  pendingRoomBaseLabel,
  pixelToCm,
  planGeometry,
  pointInPolygonCm,
  polygonArea,
  populateStepSixRoomSelectors,
  preparedAutoRoomLabels,
  prepareRoomSchemePreviewViewer,
  previewStepSixRoomSurfaces,
  promptRoomSchemeSelection,
  recognitionReviewSuffix,
  refreshConfigurationSnapshot,
  renderRooms,
  renderRoomSchemeGate,
  renderRoomSchemeSelectionDialog,
  renderSchemeControls,
  renderSpaceOverlay,
  renderStepSixSurfaceProgress,
  renderStyleControls,
  renderWhiteWalkRoomSelector,
  renderWholeHouseQuestionnaire,
  repairLoadedRoomPolygon,
  resolveStructureWallCollisions,
  resolveSurfaceOption,
  reviewItemsFromAnalysis,
  ROOM_NAME_OPTIONS,
  roomDimensions,
  roomFinishDraftFor,
  roomHasComparableSchemeB,
  roomIconCentroidCm,
  roomNameOptionFor,
  roomPolygonsDiffer,
  roomPolygonSvg,
  roomQuestionnaireSummary,
  roomReviewHint,
  roomSchemeFurnitureLabel,
  roomSchemeFurnitureLegend,
  roomSchemeGateBlocking,
  roomSchemePlanMarkup,
  roomSchemePreviewCache,
  roomSchemePreviewFloorplan,
  roomSchemePreviewKey,
  roomSchemePreviewViewer,
  roomSchemeRuntimeState,
  roomSchemeSelectionRequired,
  scheduleSave,
  schemeFurnitureForRoom,
  schemeFurnitureSceneFromShell,
  schemeStructureMarkup,
  segmentSvg,
  selectedSchemeForRoom,
  selectedSchemeMismatchNotice,
  selectedStepSixRoom,
  selectSchemeForRoom,
  setRoomGeometryMode,
  setRoomNodeMode,
  setRoomSchemeWorkbenchLocked,
  setStatus,
  setStepSixSurfaceKind,
  setStepSixSurfaceStatus,
  setTaskDialogOpen,
  SHOW_ALL_ROOMS_BUTTONS,
  showStep,
  snapshotCopy,
  snapshotFurniture,
  splitImplausibleIconRoomsByInteriorWalls,
  splitSelectedRoom,
  state,
  stepSixRoomSurfaceConfirmed,
  stepSixSurfacesFinalLocked,
  stepSixSurfaceUnlockButtons,
  STORAGE_INFERENCE_MAX_AREA_CM2,
  structuralSnapshotPoint,
  structureCollections,
  structurePreview,
  structureRuntimeState,
  structureSectionMeta,
  structuresForScheme,
  STYLE_MATERIAL_OPTIONS,
  syncConfigurationConfirmButton,
  syncOverlayToImage,
  unresolvedReviewRooms,
  updateRoomGeometryControls,
  updateRoomNodeControls,
  updateShowAllRoomsButton,
  userFacingMaterialLabel,
  validateColumnDimensionsCm,
  waitForRoomSchemePreviewFrames,
  whiteViewer,
  WINDOW_TYPES,
  windowsOverlap,
}) {
function structureGroup(item, kind, markup) {
  const active = state.selectedStructure?.id === item.id
    && state.selectedStructure?.kind === kind;
  return `<g data-structure-id="${escapeHtml(item.id)}" data-structure-kind="${kind}"
    class="${active ? "is-selected-structure" : ""}">${markup}</g>`;
}

function beamBandSvg(item, { selected = false, draft = false } = {}) {
  const start = cmToPixel(item.start);
  const end = cmToPixel(item.end);
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const length = Math.hypot(dx, dy);
  if (length < 50) return "";
  const halfWidth = Math.max(7, Number(item.thickness_cm || 30) / planGeometry().scale / 2);
  const nx = -dy / length * halfWidth;
  const ny = dx / length * halfWidth;
  const points = [
    `${start.x + nx},${start.y + ny}`,
    `${end.x + nx},${end.y + ny}`,
    `${end.x - nx},${end.y - ny}`,
    `${start.x - nx},${start.y - ny}`,
  ].join(" ");
  const color = selected || draft ? "#ef9f19" : "#6b4d8a";
  return `<polygon points="${points}" fill="${color}" fill-opacity="${draft ? 0.28 : 0.42}"
    stroke="${color}" stroke-width="${selected ? 5 : 3}" ${draft ? 'stroke-dasharray="14 9"' : ""}
    style="cursor:${draft ? "crosshair" : "move"}"/>`;
}

function beamSnapCandidates(excludeId = null) {
  return [
    ...state.structures.walls
      .filter((item) => item.id !== excludeId)
      .flatMap((item) => [item.start, item.end]),
    ...state.structures.beams
      .filter((item) => item.id !== excludeId)
      .flatMap((item) => [item.start, item.end]),
    ...state.structures.columns.map((item) => item.center),
  ].filter(Boolean);
}

function wallEndpointSnapCandidates(excludeId = null) {
  return [
    ...beamSnapCandidates(excludeId),
    ...state.structures.doors.flatMap((item) => [item.start, item.end]),
    ...state.structures.windows.flatMap((item) => [item.start, item.end]),
  ].filter(Boolean);
}

function structureNumberMarkerSvg(kind, index, point, {
  selected = false,
  moveHandle = "",
} = {}) {
  const colors = {
    wall: "#343434",
    door: "#bd5c36",
    window: "#2f8ba1",
    beam: "#6b4d8a",
    column: "#8e3e23",
  };
  return `<g data-structure-number-kind="${kind}" data-structure-number="${index + 1}"
    ${moveHandle} style="cursor:${selected ? "grab" : "pointer"}">
    <circle cx="${point.x}" cy="${point.y}" r="18" fill="#fff"
      stroke="${selected ? "#ef9f19" : colors[kind]}" stroke-width="6"/>
    <text x="${point.x}" y="${point.y + 7}" text-anchor="middle"
      fill="${colors[kind]}" font-size="20" font-weight="800"
      pointer-events="none">${index + 1}</text>
    <title>${structureSectionMeta[kind].label} ${index + 1}${selected ? "，拖曳可移動" : ""}</title>
  </g>`;
}

function renderStructureSvg() {
  const walls = state.activeStructureKind === "wall" ? state.structures.walls.map((item, index) => {
    const start = cmToPixel(item.start);
    const end = cmToPixel(item.end);
    const midpoint = { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 };
    const selected = state.selectedStructure?.kind === "wall"
      && state.selectedStructure?.id === item.id;
    return structureGroup(
      item,
      "wall",
      `${segmentSvg(
        item,
        "#343434",
        Math.max(4, Number(item.thickness_cm || 12) / planGeometry().scale),
      )}
      ${structureNumberMarkerSvg("wall", index, midpoint, { selected })}
      ${selected ? `<circle data-wall-handle="start" cx="${start.x}" cy="${start.y}" r="17"
        fill="#fff" stroke="#bd5c36" stroke-width="6" style="cursor:crosshair"><title>拖曳微調牆起點</title></circle>
      <circle data-wall-handle="end" cx="${end.x}" cy="${end.y}" r="17"
        fill="#fff" stroke="#ef9f19" stroke-width="6" style="cursor:crosshair"><title>拖曳微調牆終點</title></circle>` : ""}`,
    );
  }).join("") : "";
  const windows = state.activeStructureKind === "window" ? state.structures.windows.map((item, index) => {
    const start = cmToPixel(item.start);
    const end = cmToPixel(item.end);
    const selected = state.selectedStructure?.kind === "window"
      && state.selectedStructure?.id === item.id;
    const midpoint = {
      x: (start.x + end.x) / 2,
      y: (start.y + end.y) / 2,
    };
    const dragTarget = `<line x1="${start.x}" y1="${start.y}" x2="${end.x}" y2="${end.y}"
      stroke="transparent" stroke-width="34" pointer-events="stroke"/>`;
    const marker = structureNumberMarkerSvg("window", index, midpoint, {
      selected,
      moveHandle: selected ? 'data-opening-move-handle="true"' : "",
    }).replace(`data-structure-number="${index + 1}"`, `data-structure-number="${index + 1}" data-window-number="${index + 1}"`);
    const handles = selected
      ? `<circle data-opening-handle="start" cx="${start.x}" cy="${start.y}" r="18"
          fill="#fff" stroke="#2f8ba1" stroke-width="7" style="cursor:ew-resize">
          <title>拖曳此端調整窗寬</title>
        </circle>
        <circle data-opening-handle="end" cx="${end.x}" cy="${end.y}" r="18"
          fill="#fff" stroke="#7755a6" stroke-width="7" style="cursor:ew-resize">
          <title>拖曳此端調整窗寬</title>
        </circle>`
      : "";
    return structureGroup(
      item,
      "window",
      `${dragTarget}${segmentSvg(item, "#2f8ba1", 7)}${marker}${handles}`,
    );
  }).join("") : "";
  const doors = state.activeStructureKind === "door" ? state.structures.doors.map((item, index) => {
    const line = segmentSvg(item, "#bd5c36", 7);
    const hinge = cmToPixel(item.start);
    const end = cmToPixel(item.end);
    const radius = Math.hypot(end.x - hinge.x, end.y - hinge.y);
    const swingEnd = item.swing_end ? cmToPixel(item.swing_end) : {
      x: hinge.x + (end.y - hinge.y),
      y: hinge.y - (end.x - hinge.x),
    };
    const swingCross = (end.x - hinge.x) * (swingEnd.y - hinge.y)
      - (end.y - hinge.y) * (swingEnd.x - hinge.x);
    const sweep = item.swing_end
      ? (swingCross >= 0 ? 1 : 0)
      : (item.opening_direction === "left" ? 0 : 1);
    const selected = state.selectedStructure?.kind === "door"
      && state.selectedStructure?.id === item.id;
    const midpoint = {
      x: (hinge.x + end.x) / 2,
      y: (hinge.y + end.y) / 2,
    };
    const dragTarget = `<line x1="${hinge.x}" y1="${hinge.y}" x2="${end.x}" y2="${end.y}"
      stroke="transparent" stroke-width="34" pointer-events="stroke"/>`;
    const marker = structureNumberMarkerSvg("door", index, midpoint, {
      selected,
      moveHandle: selected ? 'data-door-move-handle="true"' : "",
    });
    const handles = selected
      ? `<circle data-door-handle="start" cx="${hinge.x}" cy="${hinge.y}" r="18"
          fill="#fff" stroke="#bd5c36" stroke-width="7" style="cursor:ew-resize">
          <title>拖曳此端調整門寬</title>
        </circle>
        <circle data-door-handle="end" cx="${end.x}" cy="${end.y}" r="18"
          fill="#fff" stroke="#7755a6" stroke-width="7" style="cursor:ew-resize">
          <title>拖曳此端調整門寬</title>
        </circle>`
      : "";
    // Blue is the Step 4 open leaf. Green is the Step 6 closed leaf, both sharing one hinge.
    const openLeafLine = `<line x1="${hinge.x}" y1="${hinge.y}" x2="${end.x}" y2="${end.y}"
      stroke="#1598dc" stroke-width="5" stroke-linecap="round" pointer-events="none"/>`;
    const closedLeafLine = item.swing_end ? `<line x1="${hinge.x}" y1="${hinge.y}" x2="${swingEnd.x}" y2="${swingEnd.y}"
      stroke="#258b45" stroke-width="5" stroke-linecap="round" pointer-events="none"/>` : "";
    return structureGroup(
      item,
      "door",
      `${dragTarget}${line}${openLeafLine}${closedLeafLine}<path d="M ${end.x} ${end.y} A ${radius} ${radius} 0 0 ${sweep} ${swingEnd.x} ${swingEnd.y}" fill="none" stroke="#bd5c36" stroke-width="3"/>${marker}${handles}`,
    );
  }).join("") : "";
  const beams = state.activeStructureKind === "beam" ? state.structures.beams.map((item, index) => {
    const displayItem = structureRuntimeState.structureSizeDraft?.kind === "beam"
      && structureRuntimeState.structureSizeDraft.id === item.id
      ? structureRuntimeState.structureSizeDraft.item
      : item;
    const start = cmToPixel(displayItem.start);
    const end = cmToPixel(displayItem.end);
    const midpoint = { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 };
    const selected = state.selectedStructure?.kind === "beam"
      && state.selectedStructure?.id === item.id;
    return structureGroup(
      item,
      "beam",
      `${beamBandSvg(displayItem, { selected })}
      ${structureNumberMarkerSvg("beam", index, midpoint, { selected })}
      ${selected ? `<circle data-beam-handle="start" cx="${start.x}" cy="${start.y}" r="17"
        fill="#fff" stroke="#6b4d8a" stroke-width="6" style="cursor:crosshair"/>
      <circle data-beam-handle="end" cx="${end.x}" cy="${end.y}" r="17"
        fill="#fff" stroke="#ef9f19" stroke-width="6" style="cursor:crosshair"/>` : ""}`,
    );
  }).join("") : "";
  const columns = state.activeStructureKind === "column" ? state.structures.columns.map((item, index) => {
    const displayItem = structureRuntimeState.structureSizeDraft?.kind === "column"
      && structureRuntimeState.structureSizeDraft.id === item.id
      ? structureRuntimeState.structureSizeDraft.item
      : item;
    const pixel = cmToPixel(displayItem.center);
    const width = Number(displayItem.size_cm || 35) / planGeometry().scale;
    const depth = Number(displayItem.depth_cm || displayItem.size_cm || 35) / planGeometry().scale;
    const selected = state.selectedStructure?.kind === "column"
      && state.selectedStructure?.id === item.id;
    return structureGroup(
      item,
      "column",
      `<rect x="${pixel.x - width / 2}" y="${pixel.y - depth / 2}" width="${width}" height="${depth}"
        transform="rotate(${Number(displayItem.rotation_deg || 0)} ${pixel.x} ${pixel.y})"
        fill="rgba(189,92,54,.32)" stroke="#8e3e23" stroke-width="4"/>
      ${structureNumberMarkerSvg("column", index, pixel, { selected })}`,
    );
  }).join("") : "";
  const beamDraft = state.activeStructureKind === "beam" && structureRuntimeState.structureCreateDrag
    ? beamBandSvg({
      start: structureRuntimeState.structureCreateDrag.geometry.start,
      end: structureRuntimeState.structureCreateDrag.geometry.end,
      thickness_cm: structureRuntimeState.structureCreateDrag.thicknessCm,
    }, { selected: true, draft: true })
    : "";
  const wallDraft = state.activeStructureKind === "wall" && state.structureTool === "wall"
    && state.structureLineStart
    ? (() => {
      const start = cmToPixel(state.structureLineStart);
      const previewEnd = state.structureLinePreviewEnd
        ? cmToPixel(state.structureLinePreviewEnd)
        : null;
      const previewLine = previewEnd
        ? `<line x1="${start.x}" y1="${start.y}" x2="${previewEnd.x}" y2="${previewEnd.y}"
            stroke="#bd5c36" stroke-width="8" stroke-linecap="round" stroke-dasharray="14 10"/>`
        : "";
      return `<g class="rp-wall-draft" pointer-events="none">
        ${previewLine}
        <circle cx="${start.x}" cy="${start.y}" r="12" fill="#fff" stroke="#bd5c36" stroke-width="6"/>
        <circle cx="${start.x}" cy="${start.y}" r="4" fill="#bd5c36"/>
        <text x="${start.x + 16}" y="${start.y - 14}" fill="#8e3e23" font-size="16" font-weight="700">起點已設定，請點終點</text>
      </g>`;
    })()
    : "";
  return `<g>${walls}${windows}${doors}${beams}${columns}${beamDraft}${wallDraft}</g>`;
}

function snapPoint(point, candidates = [], toleranceCm = 16) {
  const nearest = candidates
    .filter(Boolean)
    .map((candidate) => ({
      candidate,
      distance: Math.hypot(point.x - candidate.x, point.y - candidate.y),
    }))
    .sort((left, right) => left.distance - right.distance)[0];
  return nearest && nearest.distance <= toleranceCm
    ? { x: nearest.candidate.x, y: nearest.candidate.y }
    : point;
}










function cancelStructureInteraction() {
  state.structureTool = null;
  state.structureLineStart = null;
  state.structureLinePreviewEnd = null;
  state.pendingWallDeleteId = null;
  state.selectedStructure = null;
  structureRuntimeState.structureDrag = null;
  structureRuntimeState.wallResizeDrag = null;
  structureRuntimeState.doorResizeDrag = null;
  structureRuntimeState.beamResizeDrag = null;
  structureRuntimeState.structureCreateDrag = null;
  $$("[data-structure-tool]").forEach((button) => button.classList.remove("is-active"));
  renderSpaceOverlay();
  renderDoorReviewList();
  renderSelectedStructureEditor();
  setStatus("已取消目前操作與結構選取。");
}

function structureWallCollision(item, kind) {
  if (!["beam", "column"].includes(kind)) return null;
  return findStructureWallCollision(item, kind, state.structures.walls);
}

function structurePreferredPoint() {
  const floorplan = confirmedFloorplanEditor();
  return {
    x: Number(floorplan.width_cm || 0) / 2,
    y: Number(floorplan.depth_cm || 0) / 2,
  };
}

function resolveStructureSizeDraft(item, kind) {
  if (!["beam", "column"].includes(kind)) {
    return { item, resolved: true, moved: false, totalShiftCm: 0 };
  }
  return resolveStructureWallCollisions(item, kind, state.structures.walls, {
    preferredPoint: structurePreferredPoint(),
    maxAutoShiftCm: 75,
  });
}

function repairLoadedStructureWallCollisions() {
  const preferredPoint = structurePreferredPoint();
  let moved = 0;
  let unresolved = 0;
  for (const [kind, collection] of [["beam", "beams"], ["column", "columns"]]) {
    state.structures[collection] = (state.structures[collection] || []).map((item) => {
      const normalizedItem = kind === "column"
        ? { ...item, height_cm: confirmedRoomHeightCm() }
        : item;
      const result = resolveStructureWallCollisions(
        normalizedItem,
        kind,
        state.structures.walls,
        { preferredPoint, maxAutoShiftCm: 75 },
      );
      if (result.resolved && result.moved) {
        moved += 1;
        return {
          ...result.item,
          confirmed: false,
          estimated: false,
          wall_collision_repaired: true,
        };
      }
      if (!result.resolved) {
        unresolved += 1;
        return { ...normalizedItem, confirmed: false };
      }
      return normalizedItem;
    });
  }
  state.structureCollisionRepairs = { moved, unresolved };
  return state.structureCollisionRepairs;
}

function structureWallCollisionMessage(kind) {
  const label = kind === "beam" ? "樑" : "柱";
  return `樑柱不可穿過牆體；請移動或縮小${label}，也可以貼齊牆面。`;
}

function rejectStructureWallCollision(item, kind) {
  const collision = structureWallCollision(item, kind);
  if (!collision) {
    element.spaceError.textContent = "";
    $("#structure-wall-collision-error").textContent = "";
    return false;
  }
  const message = structureWallCollisionMessage(kind);
  element.spaceError.textContent = message;
  $("#structure-wall-collision-error").textContent = message;
  setStatus(message, "error");
  return true;
}

function finishBeamCreateDrag() {
  if (!structureRuntimeState.structureCreateDrag) return false;
  const draft = structureRuntimeState.structureCreateDrag;
  structureRuntimeState.structureCreateDrag = null;
  if (!draft.geometry.valid) {
    renderSpaceOverlay();
    setStatus("樑長至少需要 25 公分，請重新拖曳起點與終點。", "error");
    return false;
  }
  const item = {
    id: `beam-manual-${Date.now()}`,
    start: draft.geometry.start,
    end: draft.geometry.end,
    thickness_cm: draft.thicknessCm,
    height_cm: draft.heightCm,
    top_cm: Number(state.sceneData?.floorplan?.room_height_cm || 270),
    confirmed: false,
    estimated: true,
    source: "manual",
  };
  if (rejectStructureWallCollision(item, "beam")) {
    renderSpaceOverlay();
    return false;
  }
  state.structures.beams.push(item);
  state.selectedStructure = { id: item.id, kind: "beam" };
  state.structureTool = null;
  $$('[data-structure-tool]').forEach((button) => button.classList.remove("is-active"));
  renderSpaceOverlay();
  renderStructureCounts();
  renderStructureReviewList();
  renderSelectedStructureEditor();
  invalidateDownstreamFrom(
    "space_confirmation",
    "已新增樑，後續需求、家具與 3D 需要重新確認。",
  );
  scheduleSave("space_confirmation");
  setStatus(`已新增樑 ${state.structures.beams.length}，長度 ${Math.round(draft.geometry.lengthCm)} 公分。`);
  return true;
}

function spacePointerDown(event) {
  if (state.spaceMode === "rooms" && state.roomGeometryMode === "split") {
    const point = imagePoint(event, element.spaceImage);
    if (!point) return;
    state.splitPoints.push(pixelToCm(point));
    updateRoomGeometryControls();
    renderSpaceOverlay();
    if (state.splitPoints.length === 2) {
      splitSelectedRoom(state.splitPoints[0], state.splitPoints[1]);
    }
    return;
  }
  if (state.spaceMode === "rooms" && state.roomNodeMode === "split") {
    const point = imagePoint(event, element.spaceImage);
    if (point) insertRoomNodeAt(pixelToCm(point));
    return;
  }
  if (
    state.spaceMode === "structure"
    && ["door", "window", "column"].includes(state.structureTool)
  ) {
    const point = imagePoint(event, element.spaceImage);
    if (point) addDroppedStructure(state.structureTool, point);
    return;
  }
  if (state.spaceMode === "structure" && state.structureTool === "beam") {
    const point = imagePoint(event, element.spaceImage);
    if (!point) return;
    const meter = pixelToCm(point);
    structureRuntimeState.structureCreateDrag = {
      geometry: beamDragGeometry(meter, meter, beamSnapCandidates()),
      thicknessCm: 30,
      heightCm: 35,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
    renderSpaceOverlay();
    setStatus("按住並拖曳到樑的終點；系統會自動對齊水平、垂直並磁吸牆柱端點。");
    return;
  }
  if (state.structureTool === "wall") {
    const point = imagePoint(event, element.spaceImage);
    if (!point) return;
    const meter = pixelToCm(point);
    if (!state.structureLineStart) {
      state.structureLineStart = meter;
      state.structureLinePreviewEnd = null;
      renderSpaceOverlay();
      setStatus(`已設定${state.structureTool === "wall" ? "牆" : "樑"}起點，請再點終點。`);
    } else {
      const kind = state.structureTool;
      const collection = kind === "wall" ? "walls" : "beams";
      const item = {
        id: `${kind}-manual-${Date.now()}`,
        start: state.structureLineStart,
        end: meter,
        thickness_cm: kind === "wall" ? 12 : 30,
        height_cm: kind === "wall" ? 270 : 35,
        confirmed: false,
        estimated: true,
        source: "manual",
      };
      const lengthCm = Math.hypot(item.end.x - item.start.x, item.end.y - item.start.y);
      if (lengthCm < 25) {
        renderSpaceOverlay();
        setStatus("牆長至少需 25 公分。起點已保留，請重新點選終點。", "error");
        return;
      }
      state.structures[collection].push(item);
      state.selectedStructure = { id: item.id, kind };
      state.structureLineStart = null;
      state.structureLinePreviewEnd = null;
      state.structureTool = null;
      $$("[data-structure-tool]").forEach((button) => button.classList.remove("is-active"));
      renderSpaceOverlay();
      renderStructureCounts();
      renderStructureReviewList();
      renderSelectedStructureEditor();
      invalidateDownstreamFrom(
        "space_confirmation",
        "已新增牆，後續需求、家具與 3D 需要重新確認。",
      );
      scheduleSave("space_confirmation");
      setStatus(`已新增${structureSectionMeta[kind].label} ${state.structures[collection].length}，可拖曳、調整尺寸、刪除或確認。`);
    }
    return;
  }
  const wallHandle = event.target.closest("[data-wall-handle]");
  if (wallHandle) {
    const structureNode = wallHandle.closest("[data-structure-id]");
    state.selectedStructure = { id: structureNode.dataset.structureId, kind: "wall" };
    structureRuntimeState.wallResizeDrag = {
      handle: wallHandle.dataset.wallHandle,
      snapshot: JSON.parse(JSON.stringify(selectedStructureItem())),
      attachedOpenings: JSON.parse(JSON.stringify(attachedOpenings(
        state.structures,
        structureNode.dataset.structureId,
      ))),
      changed: false,
      blocked: false,
    };
    renderSelectedStructureEditor();
    return;
  }
  const beamHandle = event.target.closest("[data-beam-handle]");
  if (beamHandle) {
    const structureNode = beamHandle.closest("[data-structure-id]");
    state.selectedStructure = {
      id: structureNode.dataset.structureId,
      kind: "beam",
    };
    structureRuntimeState.beamResizeDrag = {
      handle: beamHandle.dataset.beamHandle,
      snapshot: JSON.parse(JSON.stringify(selectedStructureItem())),
      changed: false,
      blocked: false,
    };
    renderStructureReviewList();
    renderSelectedStructureEditor();
    return;
  }
  const openingHandle = event.target.closest("[data-door-handle], [data-opening-handle]");
  if (openingHandle) {
    const structureNode = openingHandle.closest("[data-structure-id]");
    state.selectedStructure = {
      id: structureNode.dataset.structureId,
      kind: structureNode.dataset.structureKind,
    };
    structureRuntimeState.doorResizeDrag = {
      handle: openingHandle.dataset.doorHandle || openingHandle.dataset.openingHandle,
      snapshot: JSON.parse(JSON.stringify(selectedStructureItem())),
    };
    renderDoorReviewList();
    renderSelectedStructureEditor();
    return;
  }
  const structureNode = event.target.closest("[data-structure-id]");
  if (structureNode) {
    state.selectedStructure = {
      id: structureNode.dataset.structureId,
      kind: structureNode.dataset.structureKind,
    };
    const point = imagePoint(event, element.spaceImage);
    if (point) {
      structureRuntimeState.structureDrag = {
        start: pixelToCm(point),
        snapshot: JSON.parse(JSON.stringify(selectedStructureItem())),
        attachedOpenings: state.selectedStructure.kind === "wall"
          ? JSON.parse(JSON.stringify(attachedOpenings(
              state.structures,
              state.selectedStructure.id,
            )))
          : [],
        changed: false,
        blocked: false,
      };
    }
    renderSpaceOverlay();
    renderDoorReviewList();
    renderSelectedStructureEditor();
    return;
  }
  if (state.spaceMode === "structure" && !state.structureTool) {
    if (state.selectedStructure) {
      state.selectedStructure = null;
      renderSpaceOverlay();
      renderDoorReviewList();
      renderSelectedStructureEditor();
      setStatus("已取消結構選取。");
    }
    return;
  }
  const node = event.target.closest("[data-room-point]");
  if (node) {
    if (state.roomNodeMode === "merge") {
      const index = Number(node.dataset.roomPoint);
      state.selectedRoomNodeIndices = state.selectedRoomNodeIndices.includes(index)
        ? state.selectedRoomNodeIndices.filter((item) => item !== index)
        : [...state.selectedRoomNodeIndices.slice(-1), index];
      element.spaceError.textContent = "";
      updateRoomNodeControls();
      renderSpaceOverlay();
      return;
    }
    structureRuntimeState.draggedRoomPointIndex = Number(node.dataset.roomPoint);
    return;
  }
  const roomShape = event.target.closest("[data-room-shape]");
  if (roomShape) {
    selectRoom(roomShape.dataset.roomShape);
    return;
  }
}

function spacePointerMove(event) {
  if (state.structureTool === "wall" && state.structureLineStart) {
    const point = imagePoint(event, element.spaceImage);
    if (!point) return;
    state.structureLinePreviewEnd = pixelToCm(point);
    renderSpaceOverlay();
    return;
  }
  if (structureRuntimeState.structureCreateDrag) {
    const point = imagePoint(event, element.spaceImage);
    if (!point) return;
    structureRuntimeState.structureCreateDrag.geometry = beamDragGeometry(
      structureRuntimeState.structureCreateDrag.geometry.start,
      pixelToCm(point),
      beamSnapCandidates(),
    );
    renderSpaceOverlay();
    return;
  }
  if (structureRuntimeState.beamResizeDrag) {
    const point = imagePoint(event, element.spaceImage);
    const item = selectedStructureItem();
    if (!point || !item) return;
    const fixed = structureRuntimeState.beamResizeDrag.handle === "start"
      ? structureRuntimeState.beamResizeDrag.snapshot.end
      : structureRuntimeState.beamResizeDrag.snapshot.start;
    const geometry = beamDragGeometry(
      fixed,
      pixelToCm(point),
      beamSnapCandidates(item.id),
    );
    const candidate = {
      ...item,
      start: structureRuntimeState.beamResizeDrag.handle === "start" ? geometry.end : fixed,
      end: structureRuntimeState.beamResizeDrag.handle === "start" ? fixed : geometry.end,
    };
    if (rejectStructureWallCollision(candidate, "beam")) {
      structureRuntimeState.beamResizeDrag.blocked = true;
      return;
    }
    if (structureRuntimeState.beamResizeDrag.handle === "start") {
      item.start = geometry.end;
      item.end = fixed;
    } else {
      item.start = fixed;
      item.end = geometry.end;
    }
    structureRuntimeState.beamResizeDrag.changed = true;
    structureRuntimeState.beamResizeDrag.blocked = false;
    item.confirmed = false;
    renderSpaceOverlay();
    return;
  }
  if (structureRuntimeState.doorResizeDrag) {
    resizeOpeningFromPointer(event);
    return;
  }
  if (structureRuntimeState.wallResizeDrag) {
    const point = imagePoint(event, element.spaceImage);
    const item = selectedStructureItem();
    if (!point || !item) return;
    const endpoint = snapPoint(pixelToCm(point), wallEndpointSnapCandidates(item.id), 16);
    const candidate = {
      ...item,
      start: structureRuntimeState.wallResizeDrag.handle === "start" ? endpoint : structureRuntimeState.wallResizeDrag.snapshot.start,
      end: structureRuntimeState.wallResizeDrag.handle === "end" ? endpoint : structureRuntimeState.wallResizeDrag.snapshot.end,
    };
    const lengthCm = Math.hypot(
      candidate.end.x - candidate.start.x,
      candidate.end.y - candidate.start.y,
    );
    if (lengthCm < 25) {
      structureRuntimeState.wallResizeDrag.blocked = true;
      element.spaceError.textContent = "牆長至少需 25 公分。";
      return;
    }
    const attachedUpdates = attachedOpeningUpdates(
      structureRuntimeState.wallResizeDrag.snapshot,
      candidate,
      structureRuntimeState.wallResizeDrag.attachedOpenings,
    );
    if (attachedUpdates == null) {
      structureRuntimeState.wallResizeDrag.blocked = true;
      element.spaceError.textContent = "調整會讓附著的門窗離開牆面或與洞口衝突。";
      return;
    }
    item.start = candidate.start;
    item.end = candidate.end;
    item.confirmed = false;
    applyAttachedOpeningUpdates(attachedUpdates);
    structureRuntimeState.wallResizeDrag.changed = true;
    structureRuntimeState.wallResizeDrag.blocked = false;
    element.spaceError.textContent = "";
    renderSpaceOverlay();
    return;
  }
  if (structureRuntimeState.structureDrag && state.selectedStructure) {
    const point = imagePoint(event, element.spaceImage);
    const item = selectedStructureItem();
    if (!point || !item) return;
    const current = pixelToCm(point);
    const dx = current.x - structureRuntimeState.structureDrag.start.x;
    const dy = current.y - structureRuntimeState.structureDrag.start.y;
    if (state.selectedStructure.kind === "column") {
      const candidate = {
        ...item,
        center: {
          x: structureRuntimeState.structureDrag.snapshot.center.x + dx,
          y: structureRuntimeState.structureDrag.snapshot.center.y + dy,
        },
      };
      if (rejectStructureWallCollision(candidate, "column")) {
        structureRuntimeState.structureDrag.blocked = true;
        return;
      }
      item.center = candidate.center;
      structureRuntimeState.structureDrag.changed = true;
      structureRuntimeState.structureDrag.blocked = false;
    } else if (["door", "window"].includes(state.selectedStructure.kind)) {
      const snapshotCenter = {
        x: (structureRuntimeState.structureDrag.snapshot.start.x + structureRuntimeState.structureDrag.snapshot.end.x) / 2,
        y: (structureRuntimeState.structureDrag.snapshot.start.y + structureRuntimeState.structureDrag.snapshot.end.y) / 2,
      };
      item.start = { ...structureRuntimeState.structureDrag.snapshot.start };
      item.end = { ...structureRuntimeState.structureDrag.snapshot.end };
      item.width_cm = Number(
        structureRuntimeState.structureDrag.snapshot.width_cm
        || Math.hypot(
          structureRuntimeState.structureDrag.snapshot.end.x - structureRuntimeState.structureDrag.snapshot.start.x,
          structureRuntimeState.structureDrag.snapshot.end.y - structureRuntimeState.structureDrag.snapshot.start.y,
        ),
      );
      snapOpeningToHostWall(item, {
        x: snapshotCenter.x + dx,
        y: snapshotCenter.y + dy,
      });
      structureRuntimeState.structureDrag.changed = true;
      item.confirmed = false;
    } else {
      const candidate = {
        ...item,
        start: {
          x: structureRuntimeState.structureDrag.snapshot.start.x + dx,
          y: structureRuntimeState.structureDrag.snapshot.start.y + dy,
        },
        end: {
          x: structureRuntimeState.structureDrag.snapshot.end.x + dx,
          y: structureRuntimeState.structureDrag.snapshot.end.y + dy,
        },
      };
      if (state.selectedStructure.kind === "beam"
        && rejectStructureWallCollision(candidate, "beam")) {
        structureRuntimeState.structureDrag.blocked = true;
        return;
      }
      const attachedUpdates = state.selectedStructure.kind === "wall"
        ? attachedOpeningUpdates(
            structureRuntimeState.structureDrag.snapshot,
            candidate,
            structureRuntimeState.structureDrag.attachedOpenings,
          )
        : [];
      if (state.selectedStructure.kind === "wall" && attachedUpdates == null) {
        structureRuntimeState.structureDrag.blocked = true;
        element.spaceError.textContent =
          "牆長不足以容納附著的門窗，已保留修改前尺寸。請先調整或刪除門窗。";
        return;
      }
      item.start = candidate.start;
      item.end = candidate.end;
      applyAttachedOpeningUpdates(attachedUpdates);
      structureRuntimeState.structureDrag.changed = true;
      structureRuntimeState.structureDrag.blocked = false;
    }
    item.confirmed = false;
    renderSpaceOverlay();
    return;
  }
  if (structureRuntimeState.draggedRoomPointIndex == null) return;
  const room = state.rooms.find((item) => item.id === state.selectedRoomId);
  const point = imagePoint(event, element.spaceImage);
  if (!room || !point) return;
  room.polygon_cm[structureRuntimeState.draggedRoomPointIndex] = pixelToCm(point);
  renderSpaceOverlay();
  renderRooms();
}

function selectedStructureItem() {
  if (!state.selectedStructure) return null;
  const collection = structureCollections[state.selectedStructure.kind];
  return state.structures[collection]?.find(
    (item) => item.id === state.selectedStructure.id,
  ) || null;
}

function selectedStructureIndex() {
  if (!state.selectedStructure) return -1;
  const collection = structureCollections[state.selectedStructure.kind];
  return state.structures[collection]?.findIndex(
    (item) => item.id === state.selectedStructure.id,
  ) ?? -1;
}

function selectedStructurePreviewContext() {
  const floorplan = confirmedFloorplanEditor();
  return {
    walls: state.structures.walls,
    planWidthCm: floorplan.width_cm,
    planDepthCm: floorplan.depth_cm,
    ceilingHeightCm: floorplan.room_height_cm,
  };
}

function renderStructurePreview(item, kind, index, { draft = false } = {}) {
  structurePreview.render(item, kind, index, selectedStructurePreviewContext());
  if (kind === "beam") {
    const lengthCm = Math.hypot(
      Number(item.end?.x || 0) - Number(item.start?.x || 0),
      Number(item.end?.y || 0) - Number(item.start?.y || 0),
    );
    $("#structure-3d-preview-status").textContent =
      `紫色樑位於天花板下方；長 ${Math.round(lengthCm)} cm、寬 ${Math.round(Number(item.thickness_cm || 30))} cm、下垂 ${Math.round(Number(item.height_cm || 35))} cm${draft ? "（尚未套用）" : "。"}`;
    return;
  }
  $("#structure-3d-preview-status").textContent =
    `棕色柱從地板立起；寬 ${Math.round(Number(item.size_cm || 35))} cm、深 ${Math.round(Number(item.depth_cm || item.size_cm || 35))} cm、高 ${Math.round(Number(item.height_cm || 270))} cm${draft ? "（尚未套用）" : "。"}`;
}

function updateStructureDimensionHint(inputId, kind, valueCm, shiftCm = 0) {
  const hint = $("#structure-preview-dimension-hint");
  const definitions = {
    beam: {
      "selected-structure-size-cm": {
        dimension: "width",
        label: "目前調整：樑寬",
        direction: "前後方向",
        axis: "↔",
      },
      "selected-structure-height-cm": {
        dimension: "height",
        label: "目前調整：下垂深度",
        direction: "上下方向",
        axis: "↕",
      },
    },
    column: {
      "selected-structure-size-cm": {
        dimension: "length",
        label: "目前調整：柱寬",
        direction: "左右方向",
        axis: "↔",
      },
      "selected-structure-depth-cm": {
        dimension: "width",
        label: "目前調整：柱深",
        direction: "前後方向",
        axis: "↔",
      },
    },
  };
  const definition = definitions[kind]?.[inputId];
  if (!definition) return;
  hint.hidden = false;
  $("#structure-preview-dimension-axis").textContent = definition.axis;
  $("#structure-preview-dimension-label").textContent = definition.label;
  $("#structure-preview-dimension-value").textContent =
    `${definition.direction} · ${Math.round(valueCm)} cm${shiftCm > 0 ? ` · 避牆位移 ${Math.round(shiftCm)} cm` : ""}`;
  structurePreview.setActiveDimension(definition.dimension);
}

function previewSelectedStructureDraft(event) {
  const item = selectedStructureItem();
  const kind = state.selectedStructure?.kind;
  if (!item || !["beam", "column"].includes(kind)) return;
  const sizeCm = Number($("#selected-structure-size-cm").value);
  const depthCm = Number($("#selected-structure-depth-cm").value);
  const heightCm = kind === "column"
    ? confirmedRoomHeightCm()
    : Number($("#selected-structure-height-cm").value);
  if (!Number.isFinite(sizeCm) || sizeCm <= 0 || !Number.isFinite(heightCm) || heightCm <= 0) {
    return;
  }
  if (kind === "column" && (!Number.isFinite(depthCm) || depthCm <= 0)) return;
  const draft = {
    ...item,
    height_cm: heightCm,
    ...(kind === "beam"
      ? { thickness_cm: sizeCm }
      : { size_cm: sizeCm, depth_cm: depthCm }),
  };
  const resolution = resolveStructureSizeDraft(draft, kind);
  const inputId = event?.target?.id || "selected-structure-size-cm";
  const inputValue = Number(event?.target?.value) || sizeCm;
  if (!resolution.resolved) {
    structureRuntimeState.structureSizeDraft = null;
    $("#structure-wall-collision-error").textContent = structureWallCollisionMessage(kind);
    updateStructureDimensionHint(inputId, kind, inputValue);
    renderSpaceOverlay();
    renderStructurePreview(item, kind, selectedStructureIndex());
    return;
  }
  structureRuntimeState.structureSizeDraft = {
    id: item.id,
    kind,
    item: resolution.item,
  };
  $("#structure-wall-collision-error").textContent = "";
  updateStructureDimensionHint(
    inputId,
    kind,
    inputValue,
    resolution.totalShiftCm,
  );
  renderSpaceOverlay();
  renderStructurePreview(
    resolution.item,
    kind,
    selectedStructureIndex(),
    { draft: true },
  );
}

function renderSelectedStructureEditor() {
  const item = selectedStructureItem();
  element.structureEditor.hidden = !item;
  if (!item) {
    structureRuntimeState.structureSizeDraft = null;
    structureRuntimeState.lastEditorKey = null;
    $("#structure-preview-dimension-hint").hidden = true;
    structurePreview.setActiveDimension(null);
    $("#delete-selected-structure").textContent = "刪除此結構";
    return;
  }
  const editorKey = `${state.selectedStructure.kind}:${item.id}`;
  if (structureRuntimeState.lastEditorKey !== editorKey) {
    state.pendingWallDeleteId = null;
    structureRuntimeState.structureSizeDraft = null;
    structureRuntimeState.lastEditorKey = editorKey;
    $("#structure-preview-dimension-hint").hidden = true;
    structurePreview.setActiveDimension(null);
  }
  const labels = {
    wall: "牆",
    door: "門",
    window: "窗",
    beam: "樑",
    column: "柱",
  };
  const selectedIndex = selectedStructureIndex();
  const isLineWidth = ["door", "window"].includes(state.selectedStructure.kind);
  const isDoor = state.selectedStructure.kind === "door";
  const isWindow = state.selectedStructure.kind === "window";
  const windowType = isWindow ? normalizedWindowType(item.window_type) : WINDOW_TYPES.standard;
  const isFloorToCeilingWindow = windowType === WINDOW_TYPES.floorToCeiling;
  const isBeam = state.selectedStructure.kind === "beam";
  const isColumn = state.selectedStructure.kind === "column";
  const deleteButton = $("#delete-selected-structure");
  deleteButton.textContent = state.selectedStructure.kind === "wall"
    && state.pendingWallDeleteId === item.id
    ? "再次點擊確認刪除牆"
    : "刪除此結構";
  const heightInput = $("#selected-structure-height-cm");
  $("#structure-wall-collision-error").textContent =
    structureWallCollision(item, state.selectedStructure.kind)
      ? structureWallCollisionMessage(state.selectedStructure.kind)
      : "";
  const hasLength = ["wall", "beam"].includes(state.selectedStructure.kind);
  $("#selected-structure-title").textContent =
    `選取${isFloorToCeilingWindow ? "落地窗" : labels[state.selectedStructure.kind] || "結構"} ${selectedIndex + 1}`;
  $("#selected-structure-length-cm").readOnly = isBeam;
  $("#selected-structure-size-label").textContent = isLineWidth
    ? "開口寬度（公分）"
    : isColumn
      ? "柱寬（公分）"
      : isBeam
        ? "樑寬（公分）"
      : "厚度（公分）";
  const length = item.start && item.end
    ? Math.hypot(item.end.x - item.start.x, item.end.y - item.start.y)
    : 0;
  $("#selected-structure-size-cm").value = Math.round(
    Number(
      isLineWidth
        ? item.width_cm || length
        : state.selectedStructure.kind === "column"
          ? item.size_cm
          : item.thickness_cm,
    ),
  );
  heightInput.value = isColumn
    ? String(Math.round(confirmedRoomHeightCm()))
    : String(Math.round(
      Number(item.height_cm || (isWindow ? 120 : isBeam ? 35 : 270)),
    ));
  heightInput.readOnly = isColumn;
  $("#selected-structure-length-field").hidden = !hasLength;
  $("#selected-structure-depth-field").hidden = !isColumn;
  if (hasLength) {
    $("#selected-structure-length-cm").value = Math.round(length);
    $("#selected-structure-length-label").textContent =
      isBeam ? "樑長（公分）" : "牆長（公分）";
  }
  if (isColumn) {
    $("#selected-structure-depth-cm").value =
      Math.round(Number(item.depth_cm || item.size_cm || 35));
  }
  $("#selected-structure-size-cm").min = isColumn ? "10" : "1";
  $("#selected-structure-depth-cm").min = isColumn ? "10" : "1";
  heightInput.min = isColumn ? String(Math.round(confirmedRoomHeightCm())) : "1";
  if (isColumn) {
    const columnLimits = confirmedFloorplanEditor();
    $("#selected-structure-size-cm").max = String(Math.round(columnLimits.width_cm));
    $("#selected-structure-depth-cm").max = String(Math.round(columnLimits.depth_cm));
    heightInput.max = String(Math.round(columnLimits.room_height_cm));
  } else {
    $("#selected-structure-size-cm").removeAttribute("max");
    $("#selected-structure-depth-cm").removeAttribute("max");
    heightInput.removeAttribute("max");
  }
  $("#selected-structure-height-label").textContent =
    isBeam ? "下垂深度（公分）" : isColumn ? "柱高（依樓高，公分）" : "高度（公分）";
  $("#window-type-field").hidden = !isWindow;
  $("#selected-window-type").value = windowType;
  $("#selected-structure-size-field").hidden = isLineWidth;
  $("#opening-width-controls").hidden = !isLineWidth;
  $("#window-sill-height-field").hidden = !isWindow;
  $("#window-type-preview").hidden = !isFloorToCeilingWindow;
  $("#window-sill-height-cm").disabled = isFloorToCeilingWindow;
  if (isWindow) {
    $("#window-sill-height-cm").value = isFloorToCeilingWindow
      ? "0"
      : String(Math.round(Number(item.sill_height_cm ?? 90)));
  }
  $("#apply-structure-size").textContent = isDoor ? "套用高度" : "套用尺寸";
  if (isLineWidth) {
    const widthCm = Math.round(Number(item.width_cm || length || (isDoor ? 90 : 120)));
    $("#opening-width-label").textContent = isDoor ? "門寬" : "窗寬";
    element.openingWidthSlider.value = String(widthCm);
    element.openingWidthValue.textContent = `${widthCm} cm`;
  }
  $("#flip-selected-door").hidden = !isDoor;
  $("#rotate-selected-door-180").hidden = !isDoor;
  $("#lock-selected-door-opening").hidden = !isDoor;
  $("#lock-selected-door-opening").textContent = item.host_wall_confirmed === true
    ? "已鎖定門洞"
    : "鎖定目前門洞";
  const canRotateStructure = ["door", "window", "wall"].includes(state.selectedStructure.kind);
  $("#rotate-selected-structure-left").hidden = !canRotateStructure;
  $("#rotate-selected-structure-right").hidden = !canRotateStructure;
  $("#structure-editor-guidance").textContent = isDoor
    ? "拖曳左圖門弧可沿牆移動；可調整門寬、門高、開門側與鉸鏈端。"
    : isWindow
      ? "拖曳左圖藍色窗線可移動；可調整窗寬、窗高與窗台離地高度。"
      : isBeam
        ? "拖曳左圖樑帶可移動；拖曳兩端圓點可改變長度，並在下方調整樑寬與下垂深度。"
        : isColumn
          ? "左圖調整柱的位置；下方室內 3D 預覽顯示柱從地板到天花板的寬、深與高度。"
      : "可直接在左圖拖曳移動，並在下方調整尺寸。";
  const showStructurePreview = isBeam || isColumn;
  $("#structure-3d-preview-panel").hidden = !showStructurePreview;
  if (showStructurePreview) {
    const index = selectedIndex;
    renderStructurePreview(item, state.selectedStructure.kind, index);
    $("#structure-3d-preview-title").textContent =
      `${labels[state.selectedStructure.kind]} ${index + 1} · 室內 3D 預覽`;
  }
  $("#structure-editor-hint").textContent =
    `修改${labels[state.selectedStructure.kind]}的位置或尺寸後，會回到待確認狀態。`;
}

function structureMeasurement(item, kind) {
  if (kind === "door" || kind === "window") {
    const widthCm = Number(
      item.width_cm
      || Math.hypot(item.end?.x - item.start?.x, item.end?.y - item.start?.y)
      || (kind === "door" ? 90 : 120),
    );
    const heightCm = Number(item.height_cm || (kind === "door" ? 210 : 120));
    const typeLabel = kind === "window"
      && normalizedWindowType(item.window_type) === WINDOW_TYPES.floorToCeiling
      ? "落地窗 · "
      : "";
    return `${typeLabel}寬 ${Math.round(widthCm)} × 高 ${Math.round(heightCm)} cm`;
  }
  if (kind === "column") {
    return `寬 ${Math.round(Number(item.size_cm || 35))} × 深 ${Math.round(Number(item.depth_cm || item.size_cm || 35))} × 高 ${Math.round(Number(item.height_cm || 270))} cm`;
  }
  const lengthCm = Math.hypot(
    Number(item.end?.x || 0) - Number(item.start?.x || 0),
    Number(item.end?.y || 0) - Number(item.start?.y || 0),
  );
  const widthCm = Number(item.thickness_cm || (kind === "beam" ? 30 : 12));
  const heightCm = Number(item.height_cm || (kind === "beam" ? 35 : 270));
  return `長 ${Math.round(lengthCm)} × ${kind === "beam" ? "寬" : "厚"} ${Math.round(widthCm)} × 高 ${Math.round(heightCm)} cm`;
}

function renderStructureReviewList() {
  if (!element.doorReviewList) return;
  const kind = state.activeStructureKind;
  const meta = structureSectionMeta[kind];
  const collection = state.structures[structureCollections[kind]] || [];
  const confirmedCount = collection.filter((item) => item.confirmed === true).length;
  $("#structure-review-title").textContent = meta.listTitle;
  const reviewGuidance = $("#structure-review-guidance");
  reviewGuidance.textContent = meta.guidance;
  reviewGuidance.hidden = kind === "beam" && state.structureTool !== "beam";
  $("#structure-review-progress").textContent =
    `已確認 ${confirmedCount} / ${collection.length} ${meta.unit}`;
  const confirmAllButton = $("#confirm-all-visible-structures");
  const allConfirmed = collection.length > 0 && confirmedCount === collection.length;
  confirmAllButton.disabled = !collection.length || allConfirmed;
  confirmAllButton.textContent = allConfirmed
    ? `此頁${meta.label}已全部確認`
    : `一鍵確認全部${meta.label}`;
  const addButton = $("#add-active-structure");
  addButton.dataset.structureTool = kind;
  addButton.textContent = meta.addLabel;
  if (!collection.length) {
    element.doorReviewList.innerHTML =
      `<p class="rp-control-hint">尚未辨識到${meta.label}。請按「${meta.addLabel}」，再到左側圖面指定位置。</p>`;
    return;
  }
  element.doorReviewList.innerHTML = collection.map((item, index) => {
    const selected = state.selectedStructure?.kind === kind
      && state.selectedStructure?.id === item.id;
    const windowType = kind === "window"
      ? normalizedWindowType(item.window_type)
      : null;
    const windowTypeToggle = kind === "window"
      ? `<div class="rp-window-type-toggle" role="group" aria-label="窗 ${index + 1} 類型">
          <button type="button" class="${windowType === WINDOW_TYPES.standard ? "is-active" : ""}"
            aria-pressed="${windowType === WINDOW_TYPES.standard}"
            data-window-type="${WINDOW_TYPES.standard}" data-window-id="${escapeHtml(item.id)}">一般窗</button>
          <button type="button" class="${windowType === WINDOW_TYPES.floorToCeiling ? "is-active" : ""}"
            aria-pressed="${windowType === WINDOW_TYPES.floorToCeiling}"
            data-window-type="${WINDOW_TYPES.floorToCeiling}" data-window-id="${escapeHtml(item.id)}">落地窗</button>
        </div>`
      : "";
    return `<article class="rp-door-review-item ${selected ? "is-active" : ""}">
      <button type="button" class="rp-door-review-select"
        data-structure-review="${escapeHtml(item.id)}" data-structure-kind="${kind}">
        <strong>${kind === "window" && normalizedWindowType(item.window_type) === WINDOW_TYPES.floorToCeiling ? "落地窗" : meta.label} ${index + 1}</strong>
        <span>${structureMeasurement(item, kind)} · ${item.confirmed ? "已確認" : "待人工確認"}</span>
      </button>
      <button type="button" class="rp-door-confirm ${item.confirmed ? "is-confirmed" : ""}"
        data-confirm-structure="${escapeHtml(item.id)}" data-structure-kind="${kind}">${item.confirmed ? "已確認" : "確認"}</button>
      ${windowTypeToggle}
    </article>`;
  }).join("");
}

function renderDoorReviewList() {
  renderStructureReviewList();
}

function confirmStructure(kind, structureId) {
  const collection = state.structures[structureCollections[kind]] || [];
  const item = collection.find((candidate) => candidate.id === structureId);
  if (!item) return;
  if (rejectStructureWallCollision(item, kind)) {
    state.selectedStructure = { id: item.id, kind };
    renderSelectedStructureEditor();
    return;
  }
  item.confirmed = true;
  item.estimated = false;
  state.selectedStructure = { id: item.id, kind };
  element.spaceError.textContent = "";
  renderSpaceOverlay();
  renderStructureReviewList();
  renderSelectedStructureEditor();
  renderStructureCounts();
  scheduleSave("space_confirmation");
  setStatus(`此${structureSectionMeta[kind].label}的位置與尺寸已確認。`);
}


function lockSelectedDoorOpening() {
  const item = selectedStructureItem();
  if (!item || state.selectedStructure?.kind !== "door") return;
  const center = {
    x: (Number(item.start?.x || 0) + Number(item.end?.x || 0)) / 2,
    y: (Number(item.start?.y || 0) + Number(item.end?.y || 0)) / 2,
  };
  if (!snapOpeningToHostWall(item, center)) {
    const message = "找不到可對應的牆體，請先確認門洞位置。";
    element.spaceError.textContent = message;
    setStatus(message, "error");
    return;
  }
  item.confirmed = true;
  item.estimated = false;
  item.opening_source = "manual_confirmed";
  element.spaceError.textContent = "";
  renderSpaceOverlay();
  renderStructureReviewList();
  renderSelectedStructureEditor();
  invalidateDownstreamFrom(
    "space_confirmation",
    "門洞位置已鎖定，請重新生成第 6 步的 2D+3D 場景。",
  );
  scheduleSave("space_confirmation");
  setStatus("門洞已鎖定為關門位置，後續 3D 會以這個洞口生成。");
}

function applySelectedStructureSize() {
  const item = selectedStructureItem();
  if (!item) return;
  const kind = state.selectedStructure.kind;
  const columnLimits = kind === "column" ? confirmedFloorplanEditor() : null;
  const columnDimensions = kind === "column"
    ? validateColumnDimensionsCm({
      widthCm: $("#selected-structure-size-cm").value,
      depthCm: $("#selected-structure-depth-cm").value,
      heightCm: confirmedRoomHeightCm(),
      maxWidthCm: columnLimits.width_cm,
      maxDepthCm: columnLimits.depth_cm,
      maxHeightCm: columnLimits.room_height_cm,
      centerXcm: Number(item.center?.x || 0),
      centerYcm: Number(item.center?.y ?? item.center?.z ?? 0),
      rotationDeg: Number(item.rotation_deg || 0),
    })
    : null;
  if (columnDimensions && !columnDimensions.valid) {
    element.spaceError.textContent = columnDimensions.message;
    setStatus(columnDimensions.message);
    return;
  }
  element.spaceError.textContent = "";
  const sizeCm = columnDimensions
    ? columnDimensions.values.widthCm
    : Math.max(1, Number($("#selected-structure-size-cm").value));
  const heightCm = columnDimensions
    ? confirmedRoomHeightCm()
    : Math.max(1, Number($("#selected-structure-height-cm").value));
  const lengthCm = Math.max(10, Number($("#selected-structure-length-cm").value));
  const depthCm = columnDimensions
    ? columnDimensions.values.depthCm
    : Math.max(10, Number($("#selected-structure-depth-cm").value));
  const floorToCeiling = kind === "window"
    && normalizedWindowType(item.window_type) === WINDOW_TYPES.floorToCeiling;
  const sillHeightCm = floorToCeiling
    ? 0
    : Math.max(0, Number($("#window-sill-height-cm").value));
  const nextItem = { ...item };
  if (kind === "window") {
    const cx = (item.start.x + item.end.x) / 2;
    const cy = (item.start.y + item.end.y) / 2;
    const angle = Math.atan2(item.end.y - item.start.y, item.end.x - item.start.x);
    nextItem.start = { x: cx - Math.cos(angle) * sizeCm / 2, y: cy - Math.sin(angle) * sizeCm / 2 };
    nextItem.end = { x: cx + Math.cos(angle) * sizeCm / 2, y: cy + Math.sin(angle) * sizeCm / 2 };
    nextItem.width_cm = sizeCm;
    nextItem.sill_height_cm = sillHeightCm;
    nextItem.height_cm = heightCm;
    nextItem.head_height_cm = sillHeightCm + heightCm;
  } else if (kind === "door") {
    nextItem.height_cm = heightCm;
  } else if (kind === "column") {
    nextItem.size_cm = sizeCm;
    nextItem.depth_cm = depthCm;
    nextItem.height_cm = heightCm;
  } else {
    nextItem.thickness_cm = sizeCm;
    nextItem.height_cm = heightCm;
    if (item.start && item.end) {
      const center = {
        x: (item.start.x + item.end.x) / 2,
        y: (item.start.y + item.end.y) / 2,
      };
      const angle = Math.atan2(item.end.y - item.start.y, item.end.x - item.start.x);
      nextItem.start = {
        x: center.x - Math.cos(angle) * lengthCm / 2,
        y: center.y - Math.sin(angle) * lengthCm / 2,
      };
      nextItem.end = {
        x: center.x + Math.cos(angle) * lengthCm / 2,
        y: center.y + Math.sin(angle) * lengthCm / 2,
      };
    }
  }
  const resolution = resolveStructureSizeDraft(nextItem, kind);
  if (!resolution.resolved) {
    rejectStructureWallCollision(nextItem, kind);
    return;
  }
  const attachedUpdates = kind === "wall"
    ? attachedOpeningUpdates(
        item,
        resolution.item,
        JSON.parse(JSON.stringify(attachedOpenings(state.structures, item.id))),
      )
    : [];
  if (kind === "wall" && attachedUpdates == null) {
    const message = "牆長不足以容納附著門窗，尺寸未套用。請先調整或刪除門窗。";
    element.spaceError.textContent = message;
    setStatus(message, "error");
    return;
  }
  Object.assign(item, resolution.item);
  applyAttachedOpeningUpdates(attachedUpdates);
  structureRuntimeState.structureSizeDraft = null;
  item.confirmed = false;
  item.estimated = false;
  renderSpaceOverlay();
  renderDoorReviewList();
  renderSelectedStructureEditor();
  invalidateDownstreamFrom(
    "space_confirmation",
    "結構尺寸已修改，後續需求、家具與 3D 需要重新確認。",
  );
  scheduleSave("space_confirmation");
  const shiftNote = resolution.moved
    ? `，並向室內避牆位移 ${Math.round(resolution.totalShiftCm)} 公分`
    : "";
  setStatus(kind === "column"
    ? `柱寬深已更新為 ${Math.round(sizeCm)} × ${Math.round(depthCm)} 公分，柱高依樓高固定為 ${Math.round(heightCm)} 公分${shiftNote}。`
    : `${structureSectionMeta[kind].label}尺寸已更新${shiftNote}。`);
}

function applyWindowType(windowId, type) {
  const item = state.structures.windows.find((candidate) => candidate.id === windowId);
  if (!item) return;
  const nextType = normalizedWindowType(type);
  if (normalizedWindowType(item.window_type) === nextType) return;
  const ceilingHeightCm = confirmedFloorplanEditor().room_height_cm;
  Object.assign(
    item,
    applyWindowTypePreset(item, nextType, ceilingHeightCm),
  );
  item.confirmed = false;
  item.estimated = false;
  state.selectedStructure = { id: item.id, kind: "window" };
  renderSpaceOverlay();
  renderStructureReviewList();
  renderSelectedStructureEditor();
  invalidateDownstreamFrom(
    "space_confirmation",
    "窗戶類型已修改，後續需求、家具與 3D 需要重新確認。",
  );
  scheduleSave("space_confirmation");
  setStatus(item.window_type === WINDOW_TYPES.floorToCeiling
    ? "已改為落地窗，窗台設為 0 cm，3D 會依樓高生成玻璃與框架。"
    : "已改為一般窗，請確認窗高與窗台高度。");
}

function applySelectedWindowType() {
  const item = selectedStructureItem();
  if (!item || state.selectedStructure?.kind !== "window") return;
  applyWindowType(item.id, $("#selected-window-type").value);
}

function setSelectedOpeningWidthCm(requestedWidthCm, persist = false) {
  const item = selectedStructureItem();
  if (!item || !["door", "window"].includes(state.selectedStructure?.kind)) return;
  const kind = state.selectedStructure.kind;
  const widthCm = Math.max(30, Math.min(400, Number(requestedWidthCm)));
  const hostWall = openingHostWall(item);
  const hostLengthCm = hostWall
    ? Math.hypot(
        hostWall.end.x - hostWall.start.x,
        hostWall.end.y - hostWall.start.y,
      )
    : Infinity;
  if (widthCm > hostLengthCm - 10) {
    const message = `${structureSectionMeta[kind].label}寬不可超過附著牆長；請縮小開口或先調整附著牆。`;
    element.spaceError.textContent = message;
    setStatus(message, "error");
    return;
  }
  const dx = item.end.x - item.start.x;
  const dy = item.end.y - item.start.y;
  const length = Math.hypot(dx, dy) || 1;
  item.end = {
    x: item.start.x + dx / length * widthCm,
    y: item.start.y + dy / length * widthCm,
  };
  if (kind === "door") delete item.swing_end;
  item.width_cm = widthCm;
  item.confirmed = false;
  item.estimated = false;
  element.openingWidthSlider.value = String(Math.round(widthCm));
  element.openingWidthValue.textContent = `${Math.round(widthCm)} cm`;
  renderSpaceOverlay();
  renderDoorReviewList();
  renderSelectedStructureEditor();
  if (persist) {
    const label = structureSectionMeta[kind].label;
    invalidateDownstreamFrom(
      "space_confirmation",
      `${label}寬已調整，後續需求、家具與 3D 需要重新確認。`,
    );
    scheduleSave("space_confirmation");
    setStatus(`${label}寬已調整為 ${Math.round(widthCm)} cm；請重新確認此${label}。`);
  }
}



function rotateSelectedStructure(deltaDeg) {
  const item = selectedStructureItem();
  if (!item) return;
  if (state.selectedStructure?.kind === "column") {
    const candidate = {
      ...item,
      rotation_deg: (Number(item.rotation_deg) || 0) + deltaDeg,
    };
    if (rejectStructureWallCollision(candidate, "column")) return;
    item.rotation_deg = candidate.rotation_deg;
    item.confirmed = false;
    item.estimated = false;
    renderSpaceOverlay();
    renderStructureReviewList();
    renderSelectedStructureEditor();
    invalidateDownstreamFrom("space_confirmation", "柱的方向已微調，後續需求、家具與 3D 需要重新確認。");
    scheduleSave("space_confirmation");
    return;
  }
  if (!item.start || !item.end) return;
  const snapshot = JSON.parse(JSON.stringify(item));
  const angle = Math.atan2(item.end.y - item.start.y, item.end.x - item.start.x)
    + (Math.PI / 180) * deltaDeg;
  const length = Math.hypot(item.end.x - item.start.x, item.end.y - item.start.y);
  const center = {
    x: (item.start.x + item.end.x) / 2,
    y: (item.start.y + item.end.y) / 2,
  };
  const nextWall = {
    ...item,
    start: {
    x: center.x - Math.cos(angle) * length / 2,
    y: center.y - Math.sin(angle) * length / 2,
    },
    end: {
    x: center.x + Math.cos(angle) * length / 2,
    y: center.y + Math.sin(angle) * length / 2,
    },
  };
  const attachedUpdates = state.selectedStructure?.kind === "wall"
    ? attachedOpeningUpdates(
        snapshot,
        nextWall,
        JSON.parse(JSON.stringify(attachedOpenings(state.structures, item.id))),
      )
    : [];
  if (state.selectedStructure?.kind === "wall" && attachedUpdates == null) {
    element.spaceError.textContent =
      "旋轉後牆長不足以容納附著門窗，已取消這次修改。";
    return;
  }
  item.start = nextWall.start;
  item.end = nextWall.end;
  applyAttachedOpeningUpdates(attachedUpdates);
  if (state.selectedStructure?.kind === "door") delete item.swing_end;
  item.confirmed = false;
  item.estimated = false;
  renderSpaceOverlay();
  renderDoorReviewList();
  renderDoorReviewList();
  renderSelectedStructureEditor();
  invalidateDownstreamFrom(
    "space_confirmation",
    "結構方向已微調，後續需求、家具與 3D 需要重新確認。",
  );
  scheduleSave("space_confirmation");
}

function deleteSelectedStructure() {
  if (!state.selectedStructure) return;
  const deletedKind = state.selectedStructure.kind;
  const collection = structureCollections[state.selectedStructure.kind];
  const selected = selectedStructureItem();
  if (deletedKind === "wall" && state.pendingWallDeleteId !== selected?.id) {
    const children = attachedOpenings(state.structures, selected?.id || "");
    state.pendingWallDeleteId = selected?.id || null;
    renderSelectedStructureEditor();
    setStatus(
      children.length
        ? `再次點擊「確認刪除牆」會一併刪除這面牆與附著的 ${children.length} 個門窗；刪除牆時會一併刪除附著門窗。`
        : "請再次點擊「確認刪除牆」完成刪除；切換選取或取消操作可放棄。",
      "error",
    );
    return;
  }
  if (deletedKind === "wall" && selected) {
    const children = attachedOpenings(state.structures, selected.id);
    children.forEach(({ collection: childCollection, item }) => {
      state.structures[childCollection] = state.structures[childCollection].filter(
        (candidate) => candidate.id !== item.id,
      );
    });
  }
  state.structures[collection] = state.structures[collection].filter(
    (item) => item.id !== state.selectedStructure.id,
  );
  const nextItem = state.structures[collection][0] || null;
  state.pendingWallDeleteId = null;
  state.selectedStructure = nextItem ? { id: nextItem.id, kind: deletedKind } : null;
  renderSpaceOverlay();
  renderStructureCounts();
  renderSelectedStructureEditor();
  invalidateDownstreamFrom(
    "space_confirmation",
    "結構已刪除，後續需求、家具與 3D 需要重新確認。",
  );
  scheduleSave("space_confirmation");
}

function selectRoom(roomId) {
  if (state.selectedRoomId !== roomId) {
    state.roomNodeMode = null;
    state.selectedRoomNodeIndices = [];
    updateRoomNodeControls();
  }
  state.selectedRoomId = roomId;
  if (state.roomGeometryMode === "merge") {
    state.showAllRooms = true;
    state.mergeRoomIds = state.mergeRoomIds.includes(roomId)
      ? state.mergeRoomIds.filter((id) => id !== roomId)
      : [...state.mergeRoomIds.slice(-1), roomId];
    updateRoomGeometryControls();
  } else {
    state.showAllRooms = false;
    if (state.roomGeometryMode === "split") {
      state.splitPoints = [];
      updateRoomGeometryControls();
    }
  }
  renderRooms();
  renderSpaceOverlay();
}

function saveRoom() {
  const room = state.rooms.find((item) => item.id === state.selectedRoomId);
  if (!room) return;
  const option = ROOM_NAME_OPTIONS.find((item) => item.id === element.roomName.value);
  if (!option) {
    element.spaceError.textContent = "請選擇空間名稱。";
    element.roomName.focus();
    return;
  }
  room.label = option.label;
  room.type = option.type;
  room.room_type = option.type;
  room.visual_space_type = option.id;
  room.confirmed = false;
  room.source = "manual_confirmation";
  room.confidence = 1;
  applyCanonicalRoomLabels(state.rooms);
  element.spaceError.textContent = "";
  renderRooms();
  renderSpaceOverlay();
  invalidateDownstreamFrom("space_confirmation", "房間資料已修改，後續需求、家具與 3D 需要重新確認。");
  scheduleSave("space_confirmation");
}

function nearestPointOnSegment(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = dx * dx + dy * dy || 1;
  const t = Math.max(0, Math.min(1, ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSquared));
  return { x: start.x + t * dx, y: start.y + t * dy, t };
}

function nearestPointOnLine(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = dx * dx + dy * dy || 1;
  const t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSquared;
  return { x: start.x + t * dx, y: start.y + t * dy, t };
}

function openingHostWall(item) {
  const center = {
    x: (item.start.x + item.end.x) / 2,
    y: (item.start.y + item.end.y) / 2,
  };
  const doorDx = item.end.x - item.start.x;
  const doorDy = item.end.y - item.start.y;
  const doorLength = Math.hypot(doorDx, doorDy) || 1;
  return state.structures.walls
    .map((wall) => {
      const wallDx = wall.end.x - wall.start.x;
      const wallDy = wall.end.y - wall.start.y;
      const wallLength = Math.hypot(wallDx, wallDy) || 1;
      const alignment = Math.abs(
        (doorDx / doorLength) * (wallDx / wallLength)
        + (doorDy / doorLength) * (wallDy / wallLength),
      );
      const projected = nearestPointOnLine(center, wall.start, wall.end);
      const segmentProjection = nearestPointOnSegment(center, wall.start, wall.end);
      const perpendicularDistance = Math.hypot(projected.x - center.x, projected.y - center.y);
      const extensionDistance = Math.hypot(
        projected.x - segmentProjection.x,
        projected.y - segmentProjection.y,
      );
      const recognizedHostBonus = wall.id === item.host_wall_id && alignment > 0.92 ? -8 : 0;
      return {
        wall,
        score: perpendicularDistance
          + (1 - alignment) * 300
          + extensionDistance * 0.12
          + recognizedHostBonus,
      };
    })
    .sort((a, b) => a.score - b.score)[0]?.wall || null;
}

function snapOpeningToHostWall(item, targetCenter) {
  const wall = openingHostWall(item);
  if (!wall) return false;
  const center = nearestPointOnLine(targetCenter, wall.start, wall.end);
  const wallDx = wall.end.x - wall.start.x;
  const wallDy = wall.end.y - wall.start.y;
  const wallLength = Math.hypot(wallDx, wallDy) || 1;
  const axis = { x: wallDx / wallLength, y: wallDy / wallLength };
  const currentDx = item.end.x - item.start.x;
  const currentDy = item.end.y - item.start.y;
  const direction = currentDx * axis.x + currentDy * axis.y < 0 ? -1 : 1;
  const halfWidth = Math.max(
    20,
    Number(item.width_cm || Math.hypot(currentDx, currentDy) || 90) / 2,
  );
  item.start = {
    x: center.x - axis.x * halfWidth * direction,
    y: center.y - axis.y * halfWidth * direction,
  };
  item.end = {
    x: center.x + axis.x * halfWidth * direction,
    y: center.y + axis.y * halfWidth * direction,
  };
  delete item.swing_end;
  item.host_wall_id = wall.id;
  return true;
}

function resizeOpeningFromPointer(event) {
  const item = selectedStructureItem();
  const point = imagePoint(event, element.spaceImage);
  if (!item || !point || !["door", "window"].includes(state.selectedStructure?.kind)) return;
  const requested = pixelToCm(point);
  const wall = openingHostWall(item);
  const projected = nearestPointOnLine(requested, item.start, item.end);
  const movingKey = structureRuntimeState.doorResizeDrag.handle;
  const fixedKey = movingKey === "start" ? "end" : "start";
  const fixed = item[fixedKey];
  const snapshotMoving = structureRuntimeState.doorResizeDrag.snapshot[movingKey];
  let dx = projected.x - fixed.x;
  let dy = projected.y - fixed.y;
  let length = Math.hypot(dx, dy);
  if (length < 0.1) {
    dx = snapshotMoving.x - fixed.x;
    dy = snapshotMoving.y - fixed.y;
    length = Math.hypot(dx, dy) || 1;
  }
  const width = Math.max(30, Math.min(400, length));
  item[movingKey] = {
    x: fixed.x + dx / length * width,
    y: fixed.y + dy / length * width,
  };
  if (state.selectedStructure?.kind === "door") delete item.swing_end;
  item.width_cm = Math.hypot(
    item.end.x - item.start.x,
    item.end.y - item.start.y,
  );
  item.host_wall_id = wall?.id || item.host_wall_id;
  item.confirmed = false;
  item.estimated = false;
  renderSpaceOverlay();
  renderDoorReviewList();
  renderSelectedStructureEditor();
}

function addDroppedStructure(tool, point) {
  state.activeStructureKind = tool;
  const meter = pixelToCm(point);
  let item = null;
  if (tool === "column") {
    item = {
      id: `column-manual-${Date.now()}`,
      center: meter,
      size_cm: 35,
      depth_cm: 35,
      height_cm: confirmedRoomHeightCm(),
      confirmed: false,
      estimated: true,
      source: "manual",
    };
    if (rejectStructureWallCollision(item, "column")) return;
    state.structures.columns.push(item);
  } else if (tool === "door" || tool === "window") {
    const candidates = state.structures.walls.map((wall) => ({
      wall,
      projected: nearestPointOnSegment(meter, wall.start, wall.end),
    }));
    candidates.sort((a, b) => {
      const da = Math.hypot(a.projected.x - meter.x, a.projected.y - meter.y);
      const db = Math.hypot(b.projected.x - meter.x, b.projected.y - meter.y);
      return da - db;
    });
    const host = candidates[0];
    const widthCm = tool === "door" ? 90 : 120;
    const wallStart = host?.wall.start || { x: meter.x - 100, y: meter.y };
    const wallEnd = host?.wall.end || { x: meter.x + 100, y: meter.y };
    const angle = Math.atan2(wallEnd.y - wallStart.y, wallEnd.x - wallStart.x);
    const center = host?.projected || meter;
    item = {
      id: `${tool}-manual-${Date.now()}`,
      start: { x: center.x - Math.cos(angle) * widthCm / 2, y: center.y - Math.sin(angle) * widthCm / 2 },
      end: { x: center.x + Math.cos(angle) * widthCm / 2, y: center.y + Math.sin(angle) * widthCm / 2 },
      width_cm: widthCm,
      height_cm: tool === "window" ? 120 : 210,
      sill_height_cm: tool === "window" ? 90 : 0,
      window_type: tool === "window" ? WINDOW_TYPES.standard : undefined,
      host_wall_id: host?.wall.id,
      source: "manual",
      opening_direction: "right",
      confirmed: false,
      estimated: true,
    };
    if (tool === "window") {
      const duplicate = state.structures.windows.find((candidate) => windowsOverlap(candidate, item));
      if (duplicate) {
        state.selectedStructure = { id: duplicate.id, kind: "window" };
        state.structureTool = null;
        $$("[data-structure-tool]").forEach((button) => button.classList.remove("is-active"));
        renderSpaceOverlay();
        renderStructureReviewList();
        renderSelectedStructureEditor();
        setStatus("此位置已有窗，已選取既有窗，不重複新增。");
        return;
      }
    }
    state.structures[tool === "door" ? "doors" : "windows"].push(item);
  }
  if (item) state.selectedStructure = { id: item.id, kind: tool };
  state.structureTool = null;
  $$("[data-structure-tool]").forEach((button) => button.classList.remove("is-active"));
  renderSpaceOverlay();
  renderStructureCounts();
  renderStructureReviewList();
  renderSelectedStructureEditor();
  invalidateDownstreamFrom(
    "space_confirmation",
    "已新增結構，後續需求、家具與 3D 需要重新確認。",
  );
  scheduleSave("space_confirmation");
  setStatus(`已新增${tool === "door" ? "門" : tool === "window" ? "窗" : "柱"}，可在右側繼續修改。`);
}

function setActiveStructureKind(kind) {
  if (!structureCollections[kind]) return;
  state.activeStructureKind = kind;
  state.structureTool = null;
  state.structureLineStart = null;
  state.structureLinePreviewEnd = null;
  structureRuntimeState.structureDrag = null;
  structureRuntimeState.doorResizeDrag = null;
  const firstItem = state.structures[structureCollections[kind]]?.[0] || null;
  state.selectedStructure = firstItem ? { id: firstItem.id, kind } : null;
  $$("[data-structure-section]").forEach((button) => {
    const active = button.dataset.structureSection === kind;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });
  $$("[data-structure-tool]").forEach((button) => button.classList.remove("is-active"));
  renderSpaceOverlay();
  renderStructureReviewList();
  renderSelectedStructureEditor();
  setStatus(`已切換到${structureSectionMeta[kind].label}頁；左圖只顯示此類結構的可編輯標記。`);
}

function selectStructureForReview(kind, structureId) {
  const item = state.structures[structureCollections[kind]]?.find(
    (candidate) => candidate.id === structureId,
  );
  if (!item) return;
  state.activeStructureKind = kind;
  state.selectedStructure = { id: item.id, kind };
  renderSpaceOverlay();
  renderStructureReviewList();
  renderSelectedStructureEditor();
  setStatus(`已選取${structureSectionMeta[kind].label}，可拖曳、修改尺寸、旋轉或刪除。`);
}


function rotateSelectedDoor180() {
  const item = selectedStructureItem();
  if (!item || state.selectedStructure?.kind !== "door") return;
  [item.start, item.end] = [item.end, item.start];
  delete item.swing_end;
  item.confirmed = false;
  item.estimated = false;
  element.spaceError.textContent = "";
  renderSpaceOverlay();
  renderDoorReviewList();
  renderSelectedStructureEditor();
  renderStructureCounts();
  invalidateDownstreamFrom(
    "space_confirmation",
    "門的鉸鏈端已翻轉，後續需求、家具與 3D 需要重新確認。",
  );
  scheduleSave("space_confirmation");
  setStatus("已將鉸鏈端翻轉 180°；請檢查門弧後重新確認此扇門。");
}

function renderStructureCounts() {
  const s = state.structures;
  const pendingSummary = Object.entries(structureCollections)
    .map(([kind, collection]) => ({
      label: structureSectionMeta[kind].label,
      count: s[collection].filter((item) => item.confirmed !== true).length,
    }))
    .filter((item) => item.count > 0)
    .map((item) => `${item.label} ${item.count}`)
    .join("、");
  const review = pendingSummary
    ? `；待確認：${pendingSummary}`
    : "；所有結構皆已確認";
  element.structureCounts.textContent =
    `辨識＋人工修正：牆 ${s.walls.length}、門 ${s.doors.length}、窗 ${s.windows.length}、樑 ${s.beams.length}、柱 ${s.columns.length}${review}`;
  renderDoorReviewList();
}

function confirmSpace() {
  element.spaceError.textContent = "";
  if (!state.rooms.every((room) => room.confirmed === true)) {
    const pendingCount = state.rooms.filter((room) => !room.confirmed).length;
    element.spaceError.textContent =
      `尚有 ${pendingCount} 個房間未確認，請逐一按右側房間的「確認」鍵。`;
    element.roomList.querySelector("[data-confirm-room]:not(.is-confirmed)")?.focus();
    return;
  }
  const pendingStructureKind = Object.keys(structureCollections).find((kind) => {
    const collection = state.structures[structureCollections[kind]];
    return collection.some((item) => item.confirmed !== true);
  });
  if (pendingStructureKind) {
    const collection = state.structures[structureCollections[pendingStructureKind]];
    const pendingCount = collection.filter((item) => item.confirmed !== true).length;
    const meta = structureSectionMeta[pendingStructureKind];
    element.spaceError.textContent =
      `尚有 ${pendingCount} 個${meta.label}項目未確認，已為你切到「${meta.label}」頁。請逐項確認或按「確認此頁全部項目」。`;
    $("[data-space-tab='structure']").click();
    setActiveStructureKind(pendingStructureKind);
    $("#structure-review-list [data-confirm-structure]")?.focus();
    return;
  }
  if (!$("#structure-confirmed").checked) {
    element.spaceError.textContent = "請切到「牆門窗樑柱」並確認結構。";
    $("[data-space-tab='structure']").focus();
    return;
  }
  if (!$("#estimated-size-ack").checked) {
    element.spaceError.textContent = "請確認已了解圖面估計尺寸可能與現場不同。";
    $("#estimated-size-ack").focus();
    return;
  }
  showDimensionedPlanReview();
}

function dimensionedPlanRoomInputs() {
  return state.rooms.map((room) => ({
    id: room.id,
    label: room.label || "未命名空間",
    polygonPx: room.polygon_cm.map(cmToPixel),
    ...roomDimensions(room),
  }));
}

function renderDimensionedPlanReview() {
  const { imageWidth, imageHeight } = planGeometry();
  const annotation = buildDimensionedPlanAnnotations(
    dimensionedPlanRoomInputs(),
    { imageWidth, imageHeight },
  );
  element.dimensionTotalArea.textContent = `${annotation.totalAreaM2.toFixed(2)} m²`;
  element.dimensionRoomCount.textContent = `${annotation.roomCount} 個`;
  const distanceCm = Number(state.workflow?.data?.calibration?.distanceCm);
  element.dimensionCalibrationState.textContent = distanceCm > 0
    ? `已用 ${Math.round(distanceCm)} cm 已知尺寸校正`
    : "已套用比例尺校正";
  element.dimensionPlanOverlay.setAttribute("viewBox", `0 0 ${imageWidth} ${imageHeight}`);
  element.dimensionPlanOverlay.innerHTML = annotation.svg;
  element.dimensionPlanLegend.innerHTML = annotation.rooms.map((room) => `
    <span><i style="background:${room.color}"></i><strong>${escapeHtml(room.label)}</strong>
      ${Math.round(room.widthCm)} × ${Math.round(room.depthCm)} cm</span>
  `).join("");
  const source = element.spaceImage.currentSrc || element.spaceImage.src;
  if (source && element.dimensionPlanImage.src !== source) {
    element.dimensionPlanImage.src = source;
    element.dimensionPlanImage?.addEventListener("load", () => {
      syncOverlayToImage(
        element.dimensionPlanStage,
        element.dimensionPlanImage,
        element.dimensionPlanOverlay,
      );
    }, { once: true });
  }
  requestAnimationFrame(() => syncOverlayToImage(
    element.dimensionPlanStage,
    element.dimensionPlanImage,
    element.dimensionPlanOverlay,
  ));
}

function setSpaceReviewMode(mode) {
  state.spaceReviewMode = ["dimensions", "proportion"].includes(mode) ? "dimensions" : "editing";
  const reviewing = state.spaceReviewMode === "dimensions";
  element.spaceEditorWorkspace.hidden = reviewing;
  element.spaceDimensionReview.hidden = !reviewing;
  if (activePanelName(state.workflow?.currentStep) === "space") {
    element.instruction.textContent = reviewing
      ? "最後確認平面圖上的房間輪廓、長寬尺寸與估算面積"
      : instructions.space_confirmation[1];
  }
  if (reviewing) renderDimensionedPlanReview();
}

function showDimensionedPlanReview() {
  element.dimensionReviewError.textContent = "";
  setSpaceReviewMode("dimensions");
  element.spaceDimensionReview.scrollIntoView({ behavior: "smooth", block: "start" });
  $("#back-to-space-editor").focus({ preventScroll: true });
  setStatus("請確認平面圖上的彩色房間輪廓、水平寬度與垂直長度標註。");
}

function confirmDimensionedPlan() {
  const { imageWidth, imageHeight } = planGeometry();
  const annotation = buildDimensionedPlanAnnotations(
    dimensionedPlanRoomInputs(),
    { imageWidth, imageHeight },
  );
  if (!annotation.roomCount || annotation.totalAreaM2 <= 0) {
    element.dimensionReviewError.textContent = "目前沒有可確認的空間尺寸，請返回調整空間或重新校正比例尺。";
    return;
  }
  state.confirmedStructureSnapshot = captureConfirmedStructureSnapshot();
  state.workflow.complete("space_confirmation", {
    roomsConfirmed: true,
    structureConfirmed: true,
    proportionsConfirmed: true,
    dimensionedPlanConfirmed: true,
    totalAreaM2: annotation.totalAreaM2,
  });
  renderWholeHouseQuestionnaire();
  setStatus("尺寸標註平面圖與結構均已確認。現在開始基本問卷。");
  goTo("requirements");
}

  return {
    addDroppedStructure,
    applySelectedStructureSize,
    applySelectedWindowType,
    applyWindowType,
    beamBandSvg,
    beamSnapCandidates,
    cancelStructureInteraction,
    confirmDimensionedPlan,
    confirmSpace,
    confirmStructure,
    deleteSelectedStructure,
    dimensionedPlanRoomInputs,
    finishBeamCreateDrag,
    lockSelectedDoorOpening,
    nearestPointOnLine,
    nearestPointOnSegment,
    openingHostWall,
    previewSelectedStructureDraft,
    rejectStructureWallCollision,
    renderDimensionedPlanReview,
    renderDoorReviewList,
    renderSelectedStructureEditor,
    renderStructureCounts,
    renderStructurePreview,
    renderStructureReviewList,
    renderStructureSvg,
    repairLoadedStructureWallCollisions,
    resizeOpeningFromPointer,
    resolveStructureSizeDraft,
    rotateSelectedDoor180,
    rotateSelectedStructure,
    saveRoom,
    selectedStructureIndex,
    selectedStructureItem,
    selectedStructurePreviewContext,
    selectRoom,
    selectStructureForReview,
    setActiveStructureKind,
    setSelectedOpeningWidthCm,
    setSpaceReviewMode,
    showDimensionedPlanReview,
    snapOpeningToHostWall,
    snapPoint,
    spacePointerDown,
    spacePointerMove,
    structureGroup,
    structureMeasurement,
    structureNumberMarkerSvg,
    structurePreferredPoint,
    structureWallCollision,
    structureWallCollisionMessage,
    updateStructureDimensionHint,
    wallEndpointSnapCandidates,
  };
}
