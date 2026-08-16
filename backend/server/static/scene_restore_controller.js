// Saved-project restoration and deterministic recovery workflow.
export function createSceneRestoreController({
  $,
  activeScheme,
  activeSchemeId,
  api,
  applyCanonicalRoomLabels,
  applyStyleCardHandoff,
  applyWholeHouseSurfaceConsistency,
  configureDxfPreview,
  confirmedFloorplanEditor,
  dedupeDoorCandidates,
  dedupeWindowCandidates,
  element,
  errorMessage,
  floorplanExtension,
  furniture2dDefaultsForSceneObject,
  generateWhiteModelFromRequirements,
  hydrateConfirmedStructureSnapshot,
  hydrateSceneWallMass,
  normalizeDesignSchemes,
  normalizeIconInferredRoomReview,
  normalizeRoomRequirements,
  normalizeSavedSceneData,
  normalizeSavedSceneWallSurfaces,
  normalizeSavedSpaceConfirmation,
  normalizeSceneDoorSegments,
  pendingSaveStorageKey,
  persistActiveScheme,
  preparedAutoRoomLabels,
  pruneRetiredAppliances,
  recognitionReviewSuffix,
  renderRestoredStep,
  repairFurnitureRoomPlacements,
  repairLoadedRoomPolygon,
  repairLoadedStructureWallCollisions,
  resolvedVisualPreferences,
  restoreDoorSwingEndpointsFromConfirmedStructures,
  restoreWorkflow,
  roomPolygonsDiffer,
  roomSurfaceAssignments,
  scheduleSave,
  setPlanImages,
  setStatus,
  shouldReplayPendingSave,
  showStep,
  showUploadedPreview,
  state,
  STYLE_PACKS,
  toSceneFurniture,
  upsertFurniture2dFromSceneObject,
}) {
async function recoverSceneDataFromSavedLayout() {
  const sceneSteps = new Set([
    "white_model_3d",
    "realistic_3d",
    "proposal_review",
    "ai_render",
  ]);
  if (
    state.sceneData
    || !sceneSteps.has(state.workflow?.currentStep)
  ) return false;
  const layout = await api("/api/scene/layout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      floorplan_editor: confirmedFloorplanEditor(),
      placement_variant: activeSchemeId(),
      scene_objects: state.furniture2d.map((item) => toSceneFurniture(item)),
    }),
  });
  const roomSurfaces = roomSurfaceAssignments();
  state.sceneData = {
    scene_id: `${state.projectId}-restored-${activeSchemeId()}`,
    floorplan: layout.floorplan,
    scene_objects: layout.scene_objects || [],
    questionnaire: {
      catalog_version: state.visualCatalogVersion,
      basic: state.basicAnswers,
      visual_preferences: resolvedVisualPreferences(),
      finishes: state.questionnaireFinishes,
      room_requirements: state.roomRequirementModel.roomRequirements,
    },
    room_requirements: state.roomRequirementModel.roomRequirements,
    surface_overrides: roomSurfaces.map((surface) => ({
      ...surface,
      wall_option: surface.wall_material_id || "auto",
      floor_option: surface.floor_material_id || "auto",
    })),
    design_choices: {
      single_room_mode: false,
      wall_option: state.questionnaireFinishes.wallMaterial || "auto",
      wall_color_hex: state.questionnaireFinishes.wallColor || "#f2f0ec",
      floor_option: state.questionnaireFinishes.floorMaterial || "auto",
      floor_color_hex: state.questionnaireFinishes.floorColor || "#b99b78",
      ceiling_material: state.questionnaireFinishes.ceilingMaterial || "flat-paint",
      ceiling_style: state.questionnaireFinishes.ceilingStyle || "exposed",
      ceiling_color_hex: state.questionnaireFinishes.ceilingColor || "#f4f1eb",
      exterior_wall_option: "auto",
      exterior_wall_color_hex: "#e7e3dc",
    },
    style: {
      style_id: "white_model",
      palette_hex: ["#f4f1ec", "#e9e6e1", "#d8d3cc", "#bcb4aa"],
    },
    placement_resolution_report: [],
  };
  state.sceneData.scene_objects.forEach((item) => {
    state.furniture2d = upsertFurniture2dFromSceneObject(
      state.furniture2d,
      item,
      furniture2dDefaultsForSceneObject(item),
    );
  });
  persistActiveScheme(state.designSchemes, {
    furniture: state.furniture2d,
    sceneData: state.sceneData,
  });
  return true;
}

async function restoreProject() {
  if (!state.projectId) {
    state.workflow = null;
    showStep("project");
    return;
  }
  try {
    let sceneRecoveryError = null;
    let furnitureRoomRepairError = null;
    let restoredFurnitureRoomRepairs = 0;
    let result = await api(`/api/projects/${state.projectId}`);
    const pendingSave = localStorage.getItem(pendingSaveStorageKey());
    let pendingSaveDiscarded = false;
    if (pendingSave) {
      let removePendingSave = false;
      if (shouldReplayPendingSave(pendingSave, result.project)) {
        const replayPayload = {
          ...JSON.parse(pendingSave),
          replay_pending: true,
        };
        try {
          result = await api(`/api/projects/${state.projectId}/workflow`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(replayPayload),
          });
          removePendingSave = true;
        } catch (error) {
          if (error.status !== 409) throw error;
          pendingSaveDiscarded = true;
          removePendingSave = true;
          result = await api(`/api/projects/${state.projectId}`);
        }
      } else {
        pendingSaveDiscarded = true;
        removePendingSave = true;
      }
      if (removePendingSave) localStorage.removeItem(pendingSaveStorageKey());
    }
    state.project = result.project;
    const serverState = state.project.workflow || {};
    if (Number(serverState.project_schema_version) !== 3) {
      throw new Error("project_schema_upgrade_required");
    }
    state.workflow = restoreWorkflow({
      projectId: state.projectId,
      snapshot: serverState._flow || null,
    });
    element.projectName.value = state.project.name;
    element.projectNotes.value = state.project.notes || "";
    element.saveStatus.textContent = `已載入 · ${state.project.name}`;
    state.analysis = serverState.recognition || state.workflow.data.recognition || null;
    state.confirmedFloorplan = serverState.confirmed_floorplan || null;
    const savedCalibration = serverState.calibration || state.workflow.data.calibration || null;
    const calibrationGeometry = savedCalibration?.calibration || savedCalibration;
    if (Array.isArray(calibrationGeometry?.start_px) && Array.isArray(calibrationGeometry?.end_px)) {
      state.calibrationPoints = [
        { x: Number(calibrationGeometry.start_px[0]), y: Number(calibrationGeometry.start_px[1]) },
        { x: Number(calibrationGeometry.end_px[0]), y: Number(calibrationGeometry.end_px[1]) },
      ];
    } else {
      const scaleEvidence = (state.analysis?.evidence || []).find(
        (item) => Array.isArray(item.start_px) && Array.isArray(item.end_px),
      );
      if (scaleEvidence) {
        state.calibrationPoints = [
          { x: Number(scaleEvidence.start_px[0]), y: Number(scaleEvidence.start_px[1]) },
          { x: Number(scaleEvidence.end_px[0]), y: Number(scaleEvidence.end_px[1]) },
        ];
      }
    }
    if (Number(savedCalibration?.distanceCm) > 0) {
      element.scaleInput.value = Number(savedCalibration.distanceCm);
    } else if (Number(state.analysis?.scale?.distance_cm) > 0) {
      element.scaleInput.value = Number(state.analysis.scale.distance_cm);
    }
    if (state.analysis) {
      element.recognitionSummary.textContent = `辨識結果：牆 ${state.analysis.walls?.length || state.analysis.floorplan?.wall_count || 0}、門 ${state.analysis.doors?.length || state.analysis.floorplan?.door_count || 0}、窗 ${state.analysis.windows?.length || state.analysis.floorplan?.window_count || 0}${recognitionReviewSuffix()}`;
      element.uploadFileState.textContent =
        state.analysis.filename || state.workflow.data.upload?.filename || "已上傳平面圖";
    }
    const savedSpace = normalizeSavedSpaceConfirmation(serverState.space_confirmation || {});
    state.dismissedAutoRoomIds = Array.isArray(savedSpace.dismissed_auto_room_ids)
      ? savedSpace.dismissed_auto_room_ids
      : [];
    state.rooms = savedSpace.rooms.map((room, index) => {
      const polygon = room.polygon_cm || [];
      const shouldRepair = (
        room.polygon_source === "cody_wall_enclosure"
        && room.confirmed !== true
      );
      const repairedPolygon = shouldRepair
        ? repairLoadedRoomPolygon(polygon)
        : polygon;
      const geometryRepaired = roomPolygonsDiffer(repairedPolygon, polygon);
      const normalizedRoom = normalizeIconInferredRoomReview(room, repairedPolygon, index);
      return {
        ...normalizedRoom,
        confirmed: geometryRepaired ? false : normalizedRoom.confirmed === true,
        geometry_repaired: geometryRepaired || room.geometry_repaired === true,
        polygon_cm: repairedPolygon,
      };
    });
    state.structures = serverState.space_confirmation
      ? savedSpace.structures
      : state.structures;
    state.confirmedStructureSnapshot = hydrateConfirmedStructureSnapshot(
      serverState.space_confirmation?.confirmed_structure_snapshot || null,
      state.structures,
    );
    state.rooms = applyCanonicalRoomLabels(preparedAutoRoomLabels(state.rooms, state.structures.walls || []));
    repairLoadedStructureWallCollisions();
    const normalizedDoors = dedupeDoorCandidates(state.structures.doors || []);
    state.structures.doors = normalizedDoors.doors;
    state.doorNormalizationRemoved = normalizedDoors.removed;
    const normalizedWindows = dedupeWindowCandidates(state.structures.windows || []);
    state.structures.windows = normalizedWindows.windows;
    state.windowNormalizationRemoved = normalizedWindows.removed;
    state.basicAnswers = serverState.requirements?.basic || {};
    state.basicConfirmed = serverState.requirements?.basicConfirmed === true;
    const savedQuestionnaireStage = serverState.requirements?.questionnaireStage;
    state.questionnaireStage = (savedQuestionnaireStage === "visual"
      ? "rooms"
      : savedQuestionnaireStage) || (
      "profile"
    );
    state.visualCatalogVersion =
      serverState.requirements?.visualCatalogVersion || null;
    state.visualAnswers = serverState.requirements?.visualAnswers || {};
    state.skippedVisualSpaceTypes =
      serverState.requirements?.skippedVisualSpaceTypes || [];
    state.questionnaireFinishes = {
      ...state.questionnaireFinishes,
      ...(serverState.requirements?.finishes || {}),
    };
    if (!serverState.requirements?.finishes?.stylePackId) {
      applyStyleCardHandoff();
    }
    state.roomRequirementModel = normalizeRoomRequirements(
      serverState.requirements?.roomRequirementModel || {},
      state.rooms,
      {
        basic: state.basicAnswers,
        basicConfirmed: state.basicConfirmed,
        finishes: state.questionnaireFinishes,
      },
    );
    state.roomFinishDrafts = serverState.realistic_3d?.roomSurfaceDrafts
      || serverState.requirements?.roomFinishDrafts
      || {};
    const questionnairePack = STYLE_PACKS.find(
      (pack) => pack.id === state.questionnaireFinishes.stylePackId,
    );
    if (questionnairePack) state.activeStyleId = questionnairePack.styleId;
    state.designSchemes = normalizeDesignSchemes(
      serverState.configuration || { schema_version: 3 },
    );
    Object.values(state.designSchemes.schemes).forEach((scheme) => {
      scheme.sceneData = normalizeSavedSceneData(scheme.sceneData);
    });
    const restoredScheme = activeScheme();
    state.furniture2d = restoredScheme?.furniture || [];
    state.sceneData = restoredScheme?.sceneData || null;
    applyWholeHouseSurfaceConsistency();
    const restoredWallSurfaceRepairs = Object.values(state.designSchemes.schemes || {})
      .reduce(
        (total, scheme) => total + normalizeSavedSceneWallSurfaces(scheme?.sceneData),
        0,
      ) + normalizeSavedSceneWallSurfaces(state.sceneData);
    const restoredRetiredAppliancesRemoved = pruneRetiredAppliances({ notify: true });
    const restoredSceneDoorsRemoved = normalizeSceneDoorSegments(state.sceneData);
    const restoredDoorSwingEndpoints = restoreDoorSwingEndpointsFromConfirmedStructures(
      state.sceneData,
    );
    state.doorNormalizationRemoved += restoredSceneDoorsRemoved;
    state.activeStylePackId = serverState.realistic_3d?.activeStylePackId
      || state.questionnaireFinishes.stylePackId
      || state.activeStylePackId
      || null;
    state.surfaceState = serverState.realistic_3d?.surfaceState || state.surfaceState;
    state.materialBoundary = serverState.realistic_3d?.materialBoundary || null;
    state.dismissedDecorRoles = serverState.realistic_3d?.dismissedDecorRoles || {};
    const savedProposal = serverState.proposal_review
      || state.workflow.data.proposal_review
      || {};
    state.proposalReview = {
      masterView: savedProposal.masterView || null,
      confirmedStyleCardId: savedProposal.confirmedStyleCardId || null,
      roomViews: savedProposal.roomViews || {},
      jobs: savedProposal.jobs || [],
      renderBriefs: savedProposal.renderBriefs || [],
      // 「只生一次」以後端 palette_render.generated 為準(前端 save 不會覆寫它)。
      paletteGenerated: Boolean(serverState.palette_render?.generated),
    };
    state.paletteRenderImages = {};
    state.sourceExtension = floorplanExtension({
      name: state.analysis?.filename || state.workflow.data.upload?.filename || "",
    });
    await recoverConfirmedFloorplan();
    let sceneRecoveredFromLayout = false;
    try {
      sceneRecoveredFromLayout = await recoverSceneDataFromSavedLayout();
    } catch (error) {
      sceneRecoveryError = error;
      console.warn("Unable to rebuild saved 3D scene from layout.", error);
    }
    try {
      restoredFurnitureRoomRepairs = await repairFurnitureRoomPlacements();
    } catch (error) {
      furnitureRoomRepairError = error;
      console.warn("Unable to repair furniture assigned outside its room.", error);
    }
    hydrateSceneWallMass();
    state.sourceUrl = state.sourceExtension === ".dxf"
      ? configureDxfPreview(state.analysis)
      : `/api/projects/${state.projectId}/floorplan/source?v=${Date.now()}`;
    if (state.workflow.completed.includes("upload")) {
      setPlanImages(state.sourceUrl);
      showUploadedPreview(state.sourceUrl, state.sourceExtension);
    }
    showStep(state.workflow.currentStep || "project");
    await renderRestoredStep();
    if (
      state.workflow.currentStep === "layout_2d"
      && state.workflow.completed.includes("requirements")
      && !state.sceneData
    ) {
      await generateWhiteModelFromRequirements({ returnToRequirementsOnFailure: true });
    }
    if (state.confirmedFloorplan && !serverState.confirmed_floorplan) {
      scheduleSave(state.workflow.currentStep);
    }
    if (
      sceneRecoveredFromLayout
      || restoredFurnitureRoomRepairs > 0
      || restoredRetiredAppliancesRemoved > 0
      || restoredWallSurfaceRepairs > 0
      || restoredDoorSwingEndpoints > 0
    ) {
      scheduleSave(state.workflow.currentStep);
    }
    if (state.structureCollisionRepairs?.moved > 0) {
      scheduleSave("space_confirmation");
      setStatus(
        `已將 ${state.structureCollisionRepairs.moved} 個貼牆的樑柱自動移至牆體內側，請重新確認。`,
      );
    }
    if (state.windowNormalizationRemoved > 0) {
      scheduleSave(state.workflow.currentStep);
    }
    if (sceneRecoveryError) {
      setStatus(
        `已恢復專案「${state.project.name}」，但 3D 場景暫時無法重建：${errorMessage(sceneRecoveryError)}`,
        "error",
      );
    } else if (furnitureRoomRepairError) {
      setStatus(
        `已恢復專案「${state.project.name}」，但部分家具無法回到指定房間：${errorMessage(furnitureRoomRepairError)}`,
        "warning",
      );
    } else if (restoredFurnitureRoomRepairs > 0) {
      setStatus(
        `已恢復專案「${state.project.name}」，並修正 ${restoredFurnitureRoomRepairs} 件跨房間家具的位置。`,
        "success",
      );
    } else {
      setStatus(pendingSaveDiscarded
        ? `已恢復專案「${state.project.name}」；較舊的離線暫存未覆蓋目前版本。`
        : `已恢復專案「${state.project.name}」。`);
    }
  } catch (error) {
    if (state.project && state.workflow) {
      showStep(state.workflow.currentStep || state.project.current_step || "project");
      setStatus(`專案資料已載入，但畫面還原失敗：${errorMessage(error)}`, "error");
      return;
    }
    state.projectId = null;
    state.workflow = null;
    history.replaceState({}, "", "/scene");
    showStep("project");
    setStatus(`原網址的專案無法載入：${errorMessage(error)}`, "error");
  }
}

async function recoverConfirmedFloorplan() {
  if (state.confirmedFloorplan || !state.analysis) return state.confirmedFloorplan;
  state.confirmedFloorplan = {
    floorplan: state.analysis.floorplan || state.analysis,
    dxf_text: null,
    confirmation_status: state.workflow?.completed.includes("space_confirmation")
      ? "space_reviewed"
      : "room_review_pending",
  };
  return state.confirmedFloorplan;
}

  return {
    recoverSceneDataFromSavedLayout,
    restoreProject,
    recoverConfirmedFloorplan,
  };
}
