// DOM event wiring for the scene workflow. Controllers own behavior; this module owns bindings.
export function createSceneEventBindings({
  $,
  $$,
  activateWhiteFurnitureEditing,
  activateWhiteWalkMode,
  activeQuestionnairePack,
  activeQuestionnaireRoom,
  activeRoomFinishDraft,
  activeRoomRequirement,
  activeSchemeId,
  addDroppedStructure,
  addFurnitureFromLibrary,
  addMissedRoom,
  addQuestionnaireCatalogFurniture,
  addSceneFurniture,
  allStepSixRoomSurfacesConfirmed,
  applyCalibration,
  applySelectedStructureSize,
  applySelectedWindowType,
  applyStylePackToScene,
  applyWindowType,
  autoLayoutFurniture,
  beginPlacementBusy,
  buildSpecialRequestAnswer,
  calibrationPointerDown,
  calibrationPointerMove,
  cancelStructureInteraction,
  cancelWhiteModelBeamPlacement,
  capturePendingSave,
  catalogRuntimeState,
  chooseRoomScheme,
  clearRequirementsGenerationHelp,
  closeDesignDelivery,
  closeProposalPaletteImageStage,
  closeRenderBriefDialog,
  closeRenderImageStage,
  closeRoomSchemeSelectionDialog,
  completedOpenrouterRows,
  completeRoomSchemeSelection,
  configurationFurnitureNumber,
  confirmAllRooms,
  confirmBasicQuestionnaire,
  confirmDimensionedPlan,
  confirmLayout2d,
  confirmProjectExit,
  confirmQuestionnaireFinishes,
  confirmRenderBriefAndSubmit,
  confirmRenderPalette,
  confirmRequirements,
  confirmRoom,
  confirmSpace,
  confirmStepSixRoomSurfaces,
  confirmStructure,
  confirmUpload,
  confirmWhiteModel,
  copyLivingRoomStyleToCirculation,
  createProject,
  deleteRoom,
  deleteSelectedSceneFurniture,
  deleteSelectedStructure,
  downloadDesignDeliveryJson,
  element,
  endPlacementBusy,
  ensureQuestionnaireFurnitureRecommendations,
  ensureRoomScheme3dPreviews,
  ensureRoomUsage,
  errorMessage,
  evaluateCeilingConflicts,
  finishActiveFurnitureDrag,
  finishBeamCreateDrag,
  firstUnconfirmedStepSixRoom,
  firstWorkflowBlocker,
  focusStepSixRoom,
  generateDeliveryProposal,
  generateDesignDelivery,
  goTo,
  imagePoint,
  invalidateDownstreamFrom,
  isCirculationRoom,
  layoutPointerDown,
  layoutPointerMove,
  livingRoomForCirculation,
  loadReplacementCandidates,
  loadSelectedSceneAppearance,
  lockMasterRenderView,
  lockSelectedDoorOpening,
  markRealisticSceneEdited,
  materialCatalogColor,
  materialCatalogType,
  mergeSelectedRoomNodes,
  mergeSelectedRooms,
  moveVisualQuestion,
  navigateRoomScheme3dPreview,
  openFurnitureReplacement,
  openQuestionnaireCeilingDesignStyle,
  openQuestionnaireCeilingPicker,
  openQuestionnaireFurnitureCatalog,
  openRenderBriefDialog,
  openRoomScheme3dPreview,
  openRoomSchemeSelectionDialog,
  pendingSaveCount,
  pendingSaveStorageKey,
  previewReplacementCandidate,
  previewSelectedStructureDraft,
  previewStepSixRoomSurfaces,
  prioritizeConfigurationRoomFurniture,
  projectExitConfirmed,
  proposalRuntimeState,
  proposalViewer,
  QUESTIONNAIRE_ROOM_SECTIONS,
  questionnaireFurniturePreferenceTags,
  questionnaireMaterialOptionsForPack,
  questionnaireMaterialPairCards,
  questionnaireRuntimeState,
  realisticViewer,
  reflowSingleConfigurationFurniture,
  refreshQuestionnaireFurnitureRecommendations,
  relayoutFurnitureForScheme,
  removeMaterialBoundary,
  renderCalibration,
  renderConfigurationPlan,
  renderDoorReviewList,
  renderFurnitureLibrary,
  renderLayoutFurniture,
  renderLayoutRoomFilter,
  renderQuestionnaireCatalogBatch,
  renderQuestionnaireCatalogBrowseChoices,
  renderQuestionnaireFinishes,
  renderQuestionnaireFurnitureRecommendations,
  renderQuestionnaireMaterialCatalog,
  renderQuestionnairePlan,
  renderQuestionnaireRoomSections,
  renderQuestionnaireRoomUsage,
  renderRooms,
  renderRoomSchemeSelectionDialog,
  renderSceneObjectList,
  renderSchemeControls,
  renderSelectedStructureEditor,
  renderSpaceOverlay,
  renderStructureCounts,
  renderStructureReviewList,
  renderStyleControls,
  renderVisualQuestionnaire,
  replaceSceneFurniture,
  replaceSelectedLayoutFurniture,
  rotateSelectedDoor180,
  rotateSelectedStructure,
  saveRoom,
  saveSelectedRoomView,
  saveSelectedSceneAppearance,
  saveVisualCustomAnswer,
  scheduleSave,
  searchGlbFurniture,
  selectedStructureItem,
  selectFloorplanFile,
  selectPreferenceWeight,
  selectProposalPalette,
  selectQuestionnaireCeilingDesignPack,
  selectQuestionnaireCeilingPickerItem,
  selectQuestionnaireMaterial,
  selectQuestionnaireMaterialPair,
  selectQuestionnaireStylePack,
  selectRenderRoom,
  selectRoom,
  selectStepSixCatalogMaterial,
  selectStructureForReview,
  selectVisualOption,
  selectWholeHouseStylePack,
  setActiveStructureKind,
  setFurnitureCatalogOpen,
  setReplacementDrawerOpen,
  setRoomGeometryMode,
  setRoomNodeMode,
  setSceneSidebarTab,
  setSelectedOpeningWidthCm,
  setSpaceReviewMode,
  setStatus,
  setStepSixSurfaceKind,
  setStepSixSurfaceStatus,
  setTaskDialogOpen,
  SHOW_ALL_ROOMS_BUTTONS,
  showQuestionnaireStage,
  showRenderImageEnlarged,
  showStep,
  skipQuestionnaireWithDefaults,
  spacePointerDown,
  spacePointerMove,
  state,
  stepSixSurfaceUnlockButtons,
  structureCollections,
  structurePreview,
  structureRuntimeState,
  structureSectionMeta,
  structureWallCollision,
  STYLE_PACKS,
  switchDesignScheme,
  syncAllOverlays,
  syncFurnitureInventoryAcrossSchemes,
  syncFurnitureNumberVisibility,
  syncSceneSelectionTo2dFurniture,
  syncSelected2dFurnitureToScene,
  toggleMaterialBoundary,
  toggleQuestionnaireFurniturePreferenceTag,
  unlockStepSixRoomSurfaces,
  updateAiRenderImageStage,
  updateCalibrationAction,
  updateGenerativeEquipment,
  updateGenerativeEquipmentNotes,
  updateQuestionnaireFurnitureQuantity,
  updateQuestionnaireFurnitureSelection,
  updateQuestionnaireFurnitureVariant,
  updateSelectedFurnitureDimensions,
  updateShowAllRoomsButton,
  updateUploadConfirmationState,
  whiteViewer,
  wholeHouseStylePack,
}) {
function bindEvents() {
  $("#exit-project")?.addEventListener("click", confirmProjectExit);
  element.projectForm?.addEventListener("submit", createProject);
  element.file?.addEventListener("change", () => selectFloorplanFile(element.file.files[0]));
  element.floorplanConfirmation?.addEventListener("change", updateUploadConfirmationState);
  element.confirmUpload?.addEventListener("click", confirmUpload);
  element.scaleOverlay?.addEventListener("pointerdown", calibrationPointerDown);
  element.scaleOverlay?.addEventListener("pointermove", calibrationPointerMove);
  element.scaleInput?.addEventListener("input", () => updateCalibrationAction());
  window.addEventListener("pointerup", async () => {
    if (structureRuntimeState.structureCreateDrag) finishBeamCreateDrag();
    const completedRoomDrag = structureRuntimeState.draggedRoomPointIndex != null;
    state.calibrationDragIndex = null;
    structureRuntimeState.draggedRoomPointIndex = null;
    if (structureRuntimeState.wallResizeDrag) {
      const completedWallResize = structureRuntimeState.wallResizeDrag.changed;
      const blockedWallResize = structureRuntimeState.wallResizeDrag.blocked;
      structureRuntimeState.wallResizeDrag = null;
      renderDoorReviewList();
      renderSelectedStructureEditor();
      if (completedWallResize) {
        invalidateDownstreamFrom(
          "space_confirmation",
          "牆端點已調整，請重新確認結構後再產生 2D+3D 場景。",
        );
        scheduleSave("space_confirmation");
      } else if (blockedWallResize) {
        setStatus("牆端點未變更：請避開過短牆段與附著門窗洞口。", "error");
      }
    }
    if (structureRuntimeState.structureDrag) {
      const completedStructureDrag = structureRuntimeState.structureDrag.changed;
      const blockedStructureDrag = structureRuntimeState.structureDrag.blocked;
      const draggedStructureKind = state.selectedStructure?.kind;
      const draggedStructure = selectedStructureItem();
      if (completedStructureDrag && draggedStructureKind === "door" && draggedStructure) {
        draggedStructure.confirmed = false;
      }
      structureRuntimeState.structureDrag = null;
      renderDoorReviewList();
      renderSelectedStructureEditor();
      if (completedStructureDrag) {
        invalidateDownstreamFrom(
          "space_confirmation",
          "結構位置已修改，後續需求、家具與 3D 需要重新確認。",
        );
        scheduleSave("space_confirmation");
      } else if (blockedStructureDrag) {
        setStatus("樑柱不可穿過牆體；位置未變更。", "error");
      }
    }
    if (structureRuntimeState.doorResizeDrag) {
      const resizedKind = state.selectedStructure?.kind || "door";
      const resizedLabel = structureSectionMeta[resizedKind]?.label || "開口";
      structureRuntimeState.doorResizeDrag = null;
      renderDoorReviewList();
      renderSelectedStructureEditor();
      invalidateDownstreamFrom(
        "space_confirmation",
        `${resizedLabel}寬已直接調整，後續需求、家具與 3D 需要重新確認。`,
      );
      scheduleSave("space_confirmation");
      setStatus(`${resizedLabel}寬已更新並保持吸附在牆上；請重新確認此${resizedLabel}。`);
    }
    if (structureRuntimeState.beamResizeDrag) {
      const completedBeamResize = structureRuntimeState.beamResizeDrag.changed;
      const blockedBeamResize = structureRuntimeState.beamResizeDrag.blocked;
      structureRuntimeState.beamResizeDrag = null;
      renderStructureReviewList();
      renderSelectedStructureEditor();
      if (completedBeamResize) {
        invalidateDownstreamFrom(
          "space_confirmation",
          "樑長已調整，後續需求、家具與 3D 需要重新確認。",
        );
        scheduleSave("space_confirmation");
        setStatus("樑長已更新，樑仍固定於天花板下方。");
      } else if (blockedBeamResize) {
        setStatus("樑柱不可穿過牆體；樑長未變更。", "error");
      }
    }
    if (completedRoomDrag) {
      const room = state.rooms.find((item) => item.id === state.selectedRoomId);
      if (room) room.confirmed = false;
      renderRooms();
      invalidateDownstreamFrom("space_confirmation", "房間框選已修改，後續需求、家具與 3D 需要重新確認。");
      scheduleSave("space_confirmation");
    }
    await finishActiveFurnitureDrag();
  });
  $("#reset-floorplan-calibration")?.addEventListener("click", () => {
    state.calibrationPoints = [];
    renderCalibration();
  });
  element.applyCalibration?.addEventListener("click", applyCalibration);
  element.roomList?.addEventListener("click", (event) => {
    const deleteButton = event.target.closest("[data-delete-room]");
    if (deleteButton) {
      deleteRoom(deleteButton.dataset.deleteRoom);
      return;
    }
    const confirmButton = event.target.closest("[data-confirm-room]");
    if (confirmButton) {
      confirmRoom(confirmButton.dataset.confirmRoom);
      return;
    }
    const button = event.target.closest("[data-room-id]");
    if (button) selectRoom(button.dataset.roomId);
  });
  $$("[data-room-geometry-mode]").forEach((button) => {
    button.addEventListener("click", () => setRoomGeometryMode(button.dataset.roomGeometryMode));
  });
  $("#apply-room-merge")?.addEventListener("click", mergeSelectedRooms);
  $("#cancel-room-geometry")?.addEventListener("click", () => setRoomGeometryMode(null));
  $$("[data-room-node-mode]").forEach((button) => {
    button.addEventListener("click", () => setRoomNodeMode(button.dataset.roomNodeMode));
  });
  $("#apply-node-merge")?.addEventListener("click", mergeSelectedRoomNodes);
  $("#cancel-node-edit")?.addEventListener("click", () => setRoomNodeMode(null));
  $("#add-missed-room")?.addEventListener("click", addMissedRoom);
  $("#confirm-all-rooms")?.addEventListener("click", confirmAllRooms);
  SHOW_ALL_ROOMS_BUTTONS.map((selector) => $(selector)).filter(Boolean).forEach((button) => {
    button.addEventListener("click", () => {
      if (state.rooms.length <= 1) {
        setStatus("目前只有一個空間，沒有其他框選可顯示。");
        updateShowAllRoomsButton();
        return;
      }
      state.showAllRooms = true;
      renderSpaceOverlay();
      setStatus("已顯示全部空間框選。");
    });
  });
  $("#save-room")?.addEventListener("click", saveRoom);
  element.spaceOverlay?.addEventListener("pointerdown", spacePointerDown);
  element.spaceOverlay?.addEventListener("pointermove", spacePointerMove);
  $("#apply-structure-size")?.addEventListener("click", applySelectedStructureSize);
  $("#lock-selected-door-opening")?.addEventListener("click", lockSelectedDoorOpening);
  [
    "#selected-structure-size-cm",
    "#selected-structure-depth-cm",
    "#selected-structure-height-cm",
  ].forEach((selector) => {
    $(selector).addEventListener("input", previewSelectedStructureDraft);
    $(selector).addEventListener("focus", previewSelectedStructureDraft);
  });
  $$("[data-structure-preview-view]").forEach((button) => {
    button.addEventListener("click", () => {
      structurePreview.setView(button.dataset.structurePreviewView);
      $$("[data-structure-preview-view]").forEach((candidate) => {
        candidate.classList.toggle("is-active", candidate === button);
      });
    });
  });
  $("#selected-window-type")?.addEventListener("change", applySelectedWindowType);
  element.openingWidthSlider?.addEventListener("input", () => {
    setSelectedOpeningWidthCm(element.openingWidthSlider.value, false);
  });
  element.openingWidthSlider?.addEventListener("change", () => {
    setSelectedOpeningWidthCm(element.openingWidthSlider.value, true);
  });
  $$("[data-opening-width-step]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextWidth = Number(element.openingWidthSlider.value)
        + Number(button.dataset.openingWidthStep);
      setSelectedOpeningWidthCm(nextWidth, true);
    });
  });
  $("#rotate-selected-structure-left")?.addEventListener("click", () => rotateSelectedStructure(-15));
  $("#rotate-selected-structure-right")?.addEventListener("click", () => rotateSelectedStructure(15));
  $("#rotate-selected-door-180")?.addEventListener("click", rotateSelectedDoor180);
  $("#delete-selected-structure")?.addEventListener("click", deleteSelectedStructure);
  $("#flip-selected-door")?.addEventListener("click", () => {
    const door = selectedStructureItem();
    if (!door || state.selectedStructure?.kind !== "door") return;
    door.opening_direction = door.opening_direction === "left" ? "right" : "left";
    delete door.swing_end;
    door.confirmed = false;
    renderSpaceOverlay();
    renderStructureCounts();
    renderSelectedStructureEditor();
    invalidateDownstreamFrom(
      "space_confirmation",
      "門扇方向已修改，後續需求、家具與 3D 需要重新確認。",
    );
    scheduleSave("space_confirmation");
    setStatus("已切換門扇開啟方向。");
  });
  $$("[data-space-tab]").forEach((button) => button.addEventListener("click", () => {
    $$("[data-space-tab]").forEach((item) => item.classList.toggle("is-active", item === button));
    const rooms = button.dataset.spaceTab === "rooms";
    state.spaceMode = rooms ? "rooms" : "structure";
    $("#room-confirmation-panel").hidden = !rooms;
    $("#structure-confirmation-panel").hidden = rooms;
    $("#show-all-rooms").hidden = !rooms;
    $("#plan-structure-legend").hidden = rooms;
    $("#space-plan-caption").textContent = rooms
      ? "點房間框或右側名稱可定位；紫色節點可拖曳調整範圍。"
      : "點選牆、門、窗、樑或柱後會以橘黃色標示；可直接拖曳或在右側修改。";
    if (!rooms) setActiveStructureKind(state.activeStructureKind);
    renderSpaceOverlay();
    renderStructureReviewList();
    renderSelectedStructureEditor();
  }));
  $$("[data-structure-section]").forEach((button) => {
    button.addEventListener("click", () => setActiveStructureKind(button.dataset.structureSection));
  });
  element.doorReviewList?.addEventListener("click", (event) => {
    const windowTypeButton = event.target.closest("[data-window-type]");
    if (windowTypeButton) {
      applyWindowType(
        windowTypeButton.dataset.windowId,
        windowTypeButton.dataset.windowType,
      );
      return;
    }
    const confirmButton = event.target.closest("[data-confirm-structure]");
    if (confirmButton) {
      confirmStructure(
        confirmButton.dataset.structureKind,
        confirmButton.dataset.confirmStructure,
      );
      return;
    }
    const button = event.target.closest("[data-structure-review]");
    if (button) {
      selectStructureForReview(
        button.dataset.structureKind,
        button.dataset.structureReview,
      );
    }
  });
  $("#confirm-all-visible-structures")?.addEventListener("click", () => {
    const kind = state.activeStructureKind;
    const collection = state.structures[structureCollections[kind]] || [];
    let blockedCount = 0;
    collection.forEach((item) => {
      if (structureWallCollision(item, kind)) {
        blockedCount += 1;
        item.confirmed = false;
        return;
      }
      item.confirmed = true;
      item.estimated = false;
    });
    renderStructureReviewList();
    renderStructureCounts();
    scheduleSave("space_confirmation");
    if (blockedCount) {
      const message = `樑柱不可穿過牆體；${blockedCount} 個項目尚未確認，請先移動或縮小。`;
      element.spaceError.textContent = message;
      setStatus(message, "error");
    } else {
      element.spaceError.textContent = "";
      setStatus(`已確認此頁全部 ${collection.length} 個${structureSectionMeta[kind].label}項目。`);
    }
  });
  $$("[data-structure-tool]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextTool = state.structureTool === button.dataset.structureTool
        ? null
        : button.dataset.structureTool;
      if (!nextTool) {
        cancelStructureInteraction();
        return;
      }
      state.structureTool = nextTool;
      state.structureLineStart = null;
      state.structureLinePreviewEnd = null;
      state.selectedStructure = null;
      structureRuntimeState.structureDrag = null;
      structureRuntimeState.doorResizeDrag = null;
      structureRuntimeState.beamResizeDrag = null;
      structureRuntimeState.structureCreateDrag = null;
      $$("[data-structure-tool]").forEach((item) =>
        item.classList.toggle("is-active", item.dataset.structureTool === nextTool)
      );
      renderSpaceOverlay();
      renderDoorReviewList();
      renderSelectedStructureEditor();
      const structureLabel = {
        door: "門",
        window: "窗",
        column: "柱",
      }[state.structureTool];
      setStatus(state.structureTool === "wall" || state.structureTool === "beam"
        ? `請在左圖點${state.structureTool === "wall" ? "牆" : "樑"}的起點與終點。`
        : `請在左圖點選要放置${structureLabel}的位置，系統會自動磁吸。`);
    });
    button.addEventListener("dragstart", (event) => {
      event.dataTransfer.setData("text/roompilot-structure", button.dataset.structureTool);
    });
  });
  $("#cancel-structure-interaction")?.addEventListener("click", cancelStructureInteraction);
  element.spaceStage?.addEventListener("dragover", (event) => event.preventDefault());
  element.spaceStage?.addEventListener("drop", (event) => {
    event.preventDefault();
    const tool = event.dataTransfer.getData("text/roompilot-structure");
    const point = imagePoint(event, element.spaceImage);
    if (tool && point) addDroppedStructure(tool, point);
  });
  $("#confirm-space")?.addEventListener("click", confirmSpace);
  $("#back-to-space-editor")?.addEventListener("click", () => {
    setSpaceReviewMode("editing");
    setStatus("可繼續調整房間與結構；完成後再確認尺寸標註平面圖。");
  });
  $("#recalibrate-space")?.addEventListener("click", () => {
    setSpaceReviewMode("editing");
    if (goTo("calibration")) {
      setStatus("請重新選取兩點並輸入實際尺寸；套用後會重新計算空間面積。");
    }
  });
  $("#confirm-dimensioned-plan")?.addEventListener("click", confirmDimensionedPlan);
  $("#confirm-basic-questionnaire")?.addEventListener("click", confirmBasicQuestionnaire);
  element.randomizeRequirements?.addEventListener("click", () => {
    void skipQuestionnaireWithDefaults();
  });
  $("#randomize-requirements-summary")?.addEventListener("click", () => {
    void skipQuestionnaireWithDefaults();
  });
  element.questionnaireStageNav?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-stage]");
    if (button && !button.disabled) showQuestionnaireStage(button.dataset.questionnaireStage);
  });
  element.visualSpaceNav?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-visual-room]");
    if (!button) return;
    state.roomRequirementModel.activeRoomId = button.dataset.visualRoom;
    state.selectedQuestionnaireWallId = null;
    renderVisualQuestionnaire();
  });
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-room-section]");
    if (!button) return;
    const section = button.dataset.questionnaireRuntimeState.roomSection;
    if (!QUESTIONNAIRE_ROOM_SECTIONS.some((item) => item.id === section)) return;
    questionnaireRuntimeState.roomSection = section;
    renderQuestionnaireRoomSections();
  });
  element.visualQuestionCard?.addEventListener("click", (event) => {
    const preferenceWeight = event.target.closest("[data-preference-weight]");
    if (preferenceWeight) {
      selectPreferenceWeight(preferenceWeight.dataset.preferenceWeight);
      return;
    }
    const special = event.target.closest("[data-keep-special-request]");
    if (special) {
      const label = special.dataset.keepSpecialRequest;
      const current = element.visualCustomAnswer.value.trim();
      const specialAnswer = buildSpecialRequestAnswer(
        special.dataset.specialOptionId,
        label,
        current,
      );
      element.visualCustomAnswer.value = specialAnswer.custom;
      selectVisualOption(special.dataset.specialOptionId, {
        ...specialAnswer,
      });
      element.requirementsError.textContent = "";
      return;
    }
    const option = event.target.closest("[data-visual-option]");
    if (option) selectVisualOption(option.dataset.visualOption);
  });
  element.roomPreferenceSuggestion?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-review-suggested-preferences]");
    const index = Number(button?.dataset.questionIndex);
    if (!button || !Number.isInteger(index) || index < 0) return;
    state.visualQuestionIndex = index;
    renderVisualQuestionnaire();
  });
  element.visualCustomAnswer?.addEventListener("input", () => {
    if (!saveVisualCustomAnswer()) return;
    capturePendingSave("requirements");
    clearTimeout(questionnaireRuntimeState.visualCustomSaveTimer);
    questionnaireRuntimeState.visualCustomSaveTimer = setTimeout(() => {
      questionnaireRuntimeState.visualCustomSaveTimer = null;
      scheduleSave("requirements");
    }, 450);
  });
  $("#visual-question-back")?.addEventListener("click", () => moveVisualQuestion(-1));
  $("#visual-question-next")?.addEventListener("click", () => moveVisualQuestion(1));
  $("#back-to-room-questionnaire")?.addEventListener("click", () => showQuestionnaireStage("rooms"));
  $("#questionnaire-summary-back")?.addEventListener("click", () => showQuestionnaireStage("profile"));
  element.wholeHouseStyleTabs?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-whole-house-style]");
    if (!button) return;
    const firstPack = STYLE_PACKS.find(
      (pack) => pack.styleId === button.dataset.wholeHouseStyle,
    );
    if (firstPack) selectWholeHouseStylePack(firstPack.id);
  });
  document.addEventListener("click", (event) => {
    const button = event.target.closest("#whole-house-style-grid [data-whole-house-style-pack]");
    if (!button) return;
    event.preventDefault();
    selectWholeHouseStylePack(button.dataset.wholeHouseStylePack);
  });
  element.questionnaireFurniturePreferenceTags?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-furniture-tag]");
    if (button) toggleQuestionnaireFurniturePreferenceTag(button.dataset.questionnaireFurnitureTag);
  });
  element.questionnaireStyleTabs?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-style]");
    if (!button) return;
    state.activeStyleId = button.dataset.questionnaireStyle;
    const firstPack = STYLE_PACKS.find((pack) => pack.styleId === state.activeStyleId);
    if (firstPack) selectQuestionnaireStylePack(firstPack.id);
  });
  element.questionnaireStyleGrid?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-style-pack]");
    if (button) selectQuestionnaireStylePack(button.dataset.questionnaireStylePack);
  });
  element.questionnaireRoomUsageOptions?.addEventListener("change", (event) => {
    const input = event.target.closest("[data-questionnaire-room-usage]");
    const room = activeQuestionnaireRoom();
    if (!input || !room) return;
    const requirement = state.roomRequirementModel.roomRequirements[room.id];
    const selected = new Set(ensureRoomUsage(room));
    if (input.checked) selected.add(input.dataset.questionnaireRoomUsage);
    else selected.delete(input.dataset.questionnaireRoomUsage);
    requirement.usage = [...selected];
    requirement.confirmed = false;
    activeRoomFinishDraft().confirmed = false;
    delete state.roomFurnitureRecommendations[room.id];
    renderQuestionnaireRoomUsage(room);
    renderQuestionnaireFurnitureRecommendations(room);
    renderQuestionnaireRoomSections();
    void ensureQuestionnaireFurnitureRecommendations(room, { force: true });
    invalidateDownstreamFrom(
      "requirements",
      `${room.label}的使用功能已更新，後續配置需要重新產生。`,
    );
    scheduleSave("requirements");
  });
  element.questionnaireGenerativeEquipment?.addEventListener("change", (event) => {
    if (event.target.matches("select, input[data-generative-direction], input[data-generative-exclusion]")) {
      updateGenerativeEquipment();
    }
  });
  element.questionnaireGenerationNotes?.addEventListener("input", () => updateGenerativeEquipmentNotes());
  element.questionnaireFurnitureOptions?.addEventListener("change", (event) => {
    const variant = event.target.closest("select[data-questionnaire-furniture-variant-type]");
    if (variant) {
      updateQuestionnaireFurnitureVariant(
        variant.dataset.questionnaireFurnitureVariantType,
        variant.value,
      );
      return;
    }
    const input = event.target.closest("[data-questionnaire-furniture-id]");
    if (!input) return;
    updateQuestionnaireFurnitureSelection(
      input.dataset.questionnaireFurnitureId,
      input.checked,
    );
  });
  element.questionnaireFurnitureOptions?.addEventListener("click", (event) => {
    const quantity = event.target.closest("[data-questionnaire-furniture-quantity]");
    if (quantity) {
      event.preventDefault();
      event.stopPropagation();
      updateQuestionnaireFurnitureQuantity(
        quantity.dataset.questionnaireFurnitureId,
        Number(quantity.dataset.questionnaireFurnitureQuantity),
      );
      return;
    }
    const retry = event.target.closest("[data-retry-questionnaire-furniture]");
    if (retry) {
      const room = state.rooms.find(
        (candidate) => String(candidate.id) === String(retry.dataset.retryQuestionnaireFurniture),
      );
      if (room) void ensureQuestionnaireFurnitureRecommendations(room, { force: true });
      return;
    }
  });
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-open-questionnaire-furniture-catalog]");
    const roomId = button?.dataset.openQuestionnaireFurnitureCatalog;
    if (roomId) openQuestionnaireFurnitureCatalog(roomId);
  });
  $$("#questionnaire-finishes .rp-questionnaire-furniture > .rp-action-row [data-open-questionnaire-furniture-catalog]")
    .forEach((button) => button.addEventListener("click", (event) => {
      event.preventDefault();
      openQuestionnaireFurnitureCatalog();
    }));
  element.refreshQuestionnaireFurniture?.addEventListener(
    "click",
    refreshQuestionnaireFurnitureRecommendations,
  );
  element.questionnaireMaterialPairs?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-material-pair]");
    if (!button) return;
    const pairs = questionnaireMaterialPairCards(activeQuestionnairePack());
    const pair = pairs[Number(button.dataset.questionnaireMaterialPair)];
    if (pair) selectQuestionnaireMaterialPair(pair);
  });
  [element.questionnaireWallOptions, element.questionnaireFloorOptions].forEach((host) => {
    host?.addEventListener("click", (event) => {
      const button = event.target.closest("[data-questionnaire-material]");
      if (!button) return;
      const key = button.dataset.questionnaireMaterial === "wall"
        ? "wallMaterial"
        : "floorMaterial";
      const colorKey = button.dataset.questionnaireMaterial === "wall"
        ? "wallColor"
        : "floorColor";
      const draft = activeRoomFinishDraft();
      draft[key] = button.dataset.questionnaireMaterialId;
      const pack = activeQuestionnairePack();
      const option = questionnaireMaterialOptionsForPack(
        button.dataset.questionnaireMaterial,
        pack,
      ).find((candidate) => candidate.id === button.dataset.questionnaireMaterialId);
      if (option?.color) draft[colorKey] = option.color;
      if (button.dataset.questionnaireMaterial === "wall") {
        if (state.selectedQuestionnaireWallId) {
          draft.wallOverrides[state.selectedQuestionnaireWallId] = {
            materialId: draft.wallMaterial,
            color: draft.wallColor,
          };
        } else {
          draft.defaultWallMaterial = draft.wallMaterial;
          draft.defaultWallColor = draft.wallColor;
        }
      }
      draft.confirmed = false;
      renderQuestionnaireFinishes();
      scheduleSave("requirements");
    });
  });
  [
    [element.questionnaireWallColor, "wallColor"],
    [element.questionnaireFloorColor, "floorColor"],
    [element.questionnaireCeilingMaterial, "ceilingMaterial"],
    [element.questionnaireCeilingStyle, "ceilingStyle"],
    [element.questionnaireLightStyle, "lightStyle"],
    [element.questionnaireCeilingColor, "ceilingColor"],
    [element.questionnaireAirConditioning, "airConditioning"],
  ].forEach(([control, key]) => {
    control?.addEventListener("change", () => {
      const draft = activeRoomFinishDraft();
      draft[key] = control.value;
      if (["wallColor", "floorColor"].includes(key)) {
        draft.materialSelectionMode = "custom";
        draft.styleReviewRequired = false;
      }
      if (key === "wallColor") {
        if (state.selectedQuestionnaireWallId) {
          draft.wallOverrides[state.selectedQuestionnaireWallId] = {
            materialId: draft.wallMaterial,
            color: draft.wallColor,
          };
        } else {
          draft.defaultWallColor = draft.wallColor;
        }
      }
      draft.confirmed = false;
      scheduleSave("requirements");
    });
  });
  [
    [element.questionnaireWallPreference, "wallPreference"],
    [element.questionnaireFloorPreference, "floorPreference"],
  ].forEach(([control, key]) => {
    control?.addEventListener("input", () => {
      const draft = activeRoomFinishDraft();
      draft[key] = control.value.trim();
      draft.materialSelectionMode = "custom";
      draft.styleReviewRequired = false;
      draft.confirmed = false;
      const requirement = activeRoomRequirement();
      if (requirement?.surfaces) requirement.surfaces[key] = draft[key];
      scheduleSave("requirements");
    });
  });
  element.questionnaireCeilingQuickChoices?.addEventListener("click", (event) => {
    const designStyle = event.target.closest("[data-open-questionnaire-ceiling-design-style]");
    if (designStyle) {
      openQuestionnaireCeilingDesignStyle(designStyle.dataset.openQuestionnaireCeilingDesignStyle);
      return;
    }
    const designPack = event.target.closest("[data-questionnaire-ceiling-design-pack]");
    if (designPack) {
      selectQuestionnaireCeilingDesignPack(designPack.dataset.questionnaireCeilingDesignPack);
      return;
    }
    const button = event.target.closest("[data-open-questionnaire-ceiling-picker]");
    if (!button) return;
    openQuestionnaireCeilingPicker(button.dataset.openQuestionnaireCeilingPicker);
  });
  element.questionnaireCeilingPickerOptions?.addEventListener("click", (event) => {
    const designPack = event.target.closest("[data-questionnaire-ceiling-design-pack]");
    if (designPack) {
      element.questionnaireCeilingPickerDialog.close();
      selectQuestionnaireCeilingDesignPack(designPack.dataset.questionnaireCeilingDesignPack);
      return;
    }
    const button = event.target.closest("[data-questionnaire-ceiling-picker-item]");
    if (!button) return;
    selectQuestionnaireCeilingPickerItem(button.dataset.questionnaireCeilingPickerItem);
  });
  element.closeQuestionnaireCeilingPicker?.addEventListener("click", () => {
    element.questionnaireCeilingPickerDialog?.close();
    questionnaireRuntimeState.ceilingPickerKind = null;
  });
  element.questionnaireFinishScope?.addEventListener("change", () => {
    element.questionnaireFinishRoomTargets.hidden =
      element.questionnaireFinishScope.value !== "selected";
  });
  element.enableCirculationStyleOverride?.addEventListener("click", () => {
    const room = activeQuestionnaireRoom();
    const requirement = activeRoomRequirement();
    const livingRoom = livingRoomForCirculation();
    if (!room || !requirement || !isCirculationRoom(room)) return;
    const approved = window.confirm(
      `走道目前沿用「${livingRoom?.label || "客廳"}」的風格與材質。改為獨立風格會讓動線出現視覺差異，並在第 6 步重新檢查銜接。要繼續嗎？`,
    );
    if (!approved) return;
    copyLivingRoomStyleToCirculation(room, { force: true });
    requirement.circulationStyleOverrideApproved = true;
    activeRoomFinishDraft().confirmed = false;
    renderQuestionnaireFinishes();
    invalidateDownstreamFrom("requirements", "走道已改為獨立風格，後續配置需要重新產生。");
    scheduleSave("requirements");
  });
  $("#apply-air-conditioning-all")?.addEventListener("click", () => {
    const airConditioning = element.questionnaireAirConditioning.value || "auto";
    Object.values(state.roomRequirementModel.roomRequirements || {}).forEach((requirement) => {
      requirement.climate = {
        ...(requirement.climate || {}),
        airConditioning,
      };
      const draft = state.roomFinishDrafts[requirement.roomId];
      if (draft) draft.airConditioning = airConditioning;
    });
    state.questionnaireFinishes = {
      ...state.questionnaireFinishes,
      airConditioning,
    };
    setStatus("冷氣設定已套用至全部房間；仍可在個別房間覆寫。", "success");
    scheduleSave("requirements");
  });
  element.questionnairePlanOverlay?.addEventListener("click", (event) => {
    const wall = event.target.closest("[data-questionnaire-wall]");
    if (wall) {
      state.selectedQuestionnaireWallId = wall.dataset.questionnaireWall;
      const draft = activeRoomFinishDraft();
      const override = draft.wallOverrides?.[state.selectedQuestionnaireWallId];
      draft.wallMaterial = override?.materialId || draft.defaultWallMaterial;
      draft.wallColor = override?.color || draft.defaultWallColor;
      renderQuestionnairePlan();
      renderQuestionnaireFinishes();
      return;
    }
    const room = event.target.closest("[data-questionnaire-room]");
    if (!room) return;
    state.roomRequirementModel.activeRoomId = room.dataset.questionnaireRoom;
    state.selectedQuestionnaireWallId = null;
    const draft = activeRoomFinishDraft();
    draft.wallMaterial = draft.defaultWallMaterial;
    draft.wallColor = draft.defaultWallColor;
    renderVisualQuestionnaire();
  });
  $("#confirm-questionnaire-finishes")?.addEventListener("click", confirmQuestionnaireFinishes);
  element.confirmRequirements?.addEventListener("click", confirmRequirements);
  $("#retry-configuration-catalog-check")?.addEventListener("click", () => {
    void confirmRequirements();
  });
  document.addEventListener("click", (event) => {
    const closeCatalog = event.target.closest("[data-close-material-catalog]");
    if (closeCatalog) {
      element.questionnaireMaterialCatalogDialog?.close();
      questionnaireRuntimeState.stepSixMaterialCatalogKind = null;
      return;
    }
    const openCatalog = event.target.closest("[data-open-material-catalog]");
    if (openCatalog) {
      questionnaireRuntimeState.stepSixMaterialCatalogKind = openCatalog.hasAttribute("data-step-six-material-catalog")
        ? openCatalog.dataset.openMaterialCatalog
        : null;
      questionnaireRuntimeState.materialCatalogType = "all";
      questionnaireRuntimeState.materialCatalogColor = "all";
      renderQuestionnaireMaterialCatalog(openCatalog.dataset.openMaterialCatalog, "");
      return;
    }
    const catalogMaterial = event.target.closest("[data-questionnaire-catalog-material]");
    if (!catalogMaterial) return;
    const kind = catalogMaterial.dataset.questionnaireCatalogMaterial;
    const materialId = catalogMaterial.dataset.questionnaireCatalogMaterialId;
    if (questionnaireRuntimeState.stepSixMaterialCatalogKind) selectStepSixCatalogMaterial(kind, materialId);
    else selectQuestionnaireMaterial(kind, materialId);
    element.questionnaireMaterialCatalogDialog?.close();
    questionnaireRuntimeState.stepSixMaterialCatalogKind = null;
  });
  element.questionnaireMaterialCatalogSearch?.addEventListener("input", () => {
    if (!questionnaireRuntimeState.materialCatalogKind) return;
    renderQuestionnaireMaterialCatalog(
      questionnaireRuntimeState.materialCatalogKind,
      element.questionnaireMaterialCatalogSearch.value,
    );
  });
  element.questionnaireMaterialTypeFilters?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-material-type]");
    if (!button || !questionnaireRuntimeState.materialCatalogKind) return;
    questionnaireRuntimeState.materialCatalogType = button.dataset.questionnaireMaterialType;
    renderQuestionnaireMaterialCatalog(questionnaireRuntimeState.materialCatalogKind);
  });
  element.questionnaireMaterialColorFilters?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-material-color]");
    if (!button || !questionnaireRuntimeState.materialCatalogKind) return;
    questionnaireRuntimeState.materialCatalogColor = button.dataset.questionnaireMaterialColor;
    renderQuestionnaireMaterialCatalog(questionnaireRuntimeState.materialCatalogKind);
  });
  $("#return-to-room-requirements")?.addEventListener("click", () => {
    clearRequirementsGenerationHelp();
    showQuestionnaireStage("rooms");
  });
  $$("[data-design-scheme]").forEach((button) => {
    button.addEventListener("click", () => {
      // 流程規範:方案 A/B 在第 6 步選定;第 7 步只依選定方案比較色卡、
      // 第 8 步依選定色卡逐房生圖 —— 進入第 7 步後不再切換方案。
      const currentStep = state.workflow?.currentStep;
      if (currentStep === "proposal_review" || currentStep === "ai_render") {
        setStatus("方案已於第 6 步選定；要更換 A/B 請先返回第 6 步。", "error");
        return;
      }
      if (!switchDesignScheme(button.dataset.designScheme)) return;
      setStatus(`已切換至方案 ${button.dataset.designScheme}；家具座標與 3D 場景彼此獨立。`);
    });
  });
  $("#auto-layout-furniture")?.addEventListener("click", async () => {
    element.layoutError.textContent = "";
    beginPlacementBusy("AI 正在重新擺放家具，請稍候…");
    try {
      setStatus("正在由家具引擎重新配置合法位置…");
      if (activeSchemeId() === "B" && state.designSchemes.schemes.A.furniture.length) {
        const furniture = await relayoutFurnitureForScheme(
          state.designSchemes.schemes.A.furniture,
          "B",
        );
        if (!furniture) {
          throw new Error("方案 B 無法在保留問卷家具需求下產生合法配置。");
        }
        state.furniture2d = furniture;
        const schemeB = state.designSchemes.schemes.B;
        schemeB.furniture = JSON.parse(JSON.stringify(furniture));
        schemeB.stale = false;
        schemeB.staleReason = "";
        renderLayoutRoomFilter();
        renderLayoutFurniture();
        scheduleSave("layout_2d");
      } else {
        await autoLayoutFurniture();
      }
      setStatus(`家具引擎已重新配置 ${state.furniture2d.length} 件家具。`);
    } catch (error) {
      element.layoutError.textContent = errorMessage(error);
      setStatus(errorMessage(error), "error");
    } finally {
      endPlacementBusy();
    }
  });
  element.furnitureSearch?.addEventListener("input", () => renderFurnitureLibrary(element.furnitureSearch.value));
  element.layoutRoomFilter?.addEventListener("change", () => {
    state.activeLayoutRoomId = element.layoutRoomFilter.value || "all";
    renderLayoutFurniture();
  });
  $("#add-2d-furniture-mode")?.addEventListener("click", () => {
    state.selectedFurniture2dId = null;
    renderLayoutFurniture();
    setStatus("現在是新增模式：請從右側選一個 2D 家具圖示，系統會放進目前房間。");
  });
  element.furnitureLibrary?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-add-furniture-type]");
    if (button) addFurnitureFromLibrary(button.dataset.addFurnitureType, button.dataset.addFurnitureVariant);
  });
  element.layoutLayer?.addEventListener("pointerdown", layoutPointerDown);
  element.layoutLayer?.addEventListener("pointermove", layoutPointerMove);
  element.selectedFurnitureWidth?.addEventListener("change", updateSelectedFurnitureDimensions);
  element.selectedFurnitureDepth?.addEventListener("change", updateSelectedFurnitureDimensions);
  $("#rotate-2d-furniture")?.addEventListener("click", () => {
    const item = state.furniture2d.find((candidate) => candidate.id === state.selectedFurniture2dId);
    if (item) item.rotationDeg = (item.rotationDeg + 90) % 360;
    renderLayoutFurniture();
    invalidateDownstreamFrom("layout_2d", "2D 家具旋轉已修改，3D 家具配置與即時寫實需要重新產生。");
    scheduleSave("layout_2d");
  });
  $("#delete-2d-furniture")?.addEventListener("click", () => {
    state.furniture2d = state.furniture2d.filter((item) => item.id !== state.selectedFurniture2dId);
    syncFurnitureInventoryAcrossSchemes();
    state.selectedFurniture2dId = state.furniture2d[0]?.id || null;
    renderLayoutRoomFilter();
    renderLayoutFurniture();
    invalidateDownstreamFrom("layout_2d", "2D 家具已刪除，3D 家具配置與即時寫實需要重新產生。");
    scheduleSave("layout_2d");
  });
  $("#confirm-layout-2d")?.addEventListener("click", confirmLayout2d);
  $$("[data-view-mode]").forEach((button) => button.addEventListener("click", () => {
    if (button.dataset.viewMode === "walk") {
      activateWhiteWalkMode();
      return;
    }
    $$("[data-view-mode]").forEach((item) => item.classList.toggle("is-active", item === button));
    whiteViewer.setViewMode(button.dataset.viewMode);
    $$("[data-white-interaction]").forEach((item) => {
      item.classList.toggle(
        "is-active",
        button.dataset.viewMode === "walk" && item.dataset.whiteInteraction === "walk",
      );
    });
  }));
  $$("[data-white-interaction]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.whiteInteraction === "walk") {
        activateWhiteWalkMode();
      } else {
        activateWhiteFurnitureEditing();
      }
    });
  });
  element.whiteWalkRoom?.addEventListener("change", () => {
    const roomId = element.whiteWalkRoom.value;
    state.selectedWalkRoomId = roomId;
    state.selectedRoomId = roomId;
    const sidebar = $(".rp-3d-sidebar");
    if (state.workflow?.currentStep === "realistic_3d" || sidebar?.dataset.sceneSidebarMode === "surfaces") {
      focusStepSixRoom(roomId);
    } else {
      activateWhiteWalkMode();
    }
  });
  $("#add-white-model-beam")?.addEventListener("click", () => {
    if (!goTo("space_confirmation")) return;
    showStep("space_confirmation");
    setSpaceReviewMode("editing");
    state.spaceMode = "structure";
    setActiveStructureKind("beam");
    setStatus("已返回第 4 步樑頁；修改結構後，問卷保留並重新計算家具與 3D。");
  });
  element.layoutFurnitureList?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-select-layout-furniture]");
    if (!button) return;
    state.selectedFurniture2dId = button.dataset.selectLayoutFurniture;
    renderLayoutFurniture();
    syncSelected2dFurnitureToScene({ focus: false });
  });
  const selectConfigurationFurniture = (event) => {
    const button = event.target.closest("[data-select-configuration-furniture]");
    if (!button) return;
    const fromPlan = event.currentTarget === element.configurationPlanLayer;
    const fromFurnitureList = event.currentTarget === element.configurationPlanFurnitureList;
    state.selectedFurniture2dId = button.dataset.selectConfigurationFurniture;
    if (fromFurnitureList) void openFurnitureReplacement();
    renderLayoutFurniture();
    renderConfigurationPlan();
    const focused = fromFurnitureList
      ? syncSelected2dFurnitureToScene({ focus: false })
      : syncSelected2dFurnitureToScene({ focus: true });
    if (fromPlan) {
      const item = state.furniture2d.find(
        (candidate) => candidate.id === state.selectedFurniture2dId,
      );
      setStatus(
        focused && item
          ? `已在 3D 定位家具 ${configurationFurnitureNumber(item)}「${item.label}」。`
          : "已選取家具；目前尚無可定位的 3D 模型。",
      );
    }
  };
  element.configurationPlanLayer?.addEventListener("click", selectConfigurationFurniture);
  element.configurationPlanFurnitureList?.addEventListener(
    "click",
    selectConfigurationFurniture,
  );
  element.configurationPendingList?.addEventListener("click", (event) => {
    const prioritizeButton = event.target.closest("[data-prioritize-configuration-room]");
    if (prioritizeButton) {
      void prioritizeConfigurationRoomFurniture(
        prioritizeButton.dataset.prioritizeConfigurationRoom,
      );
      return;
    }
    const replaceButton = event.target.closest("[data-replace-configuration-furniture]");
    if (replaceButton) {
      state.selectedFurniture2dId = replaceButton.dataset.replaceConfigurationFurniture;
      renderLayoutFurniture();
      renderConfigurationPlan();
      syncSelected2dFurnitureToScene({ focus: true });
      void openFurnitureReplacement();
      return;
    }
    const reflowButton = event.target.closest("[data-reflow-configuration-furniture]");
    if (reflowButton) {
      void reflowSingleConfigurationFurniture(
        reflowButton.dataset.reflowConfigurationFurniture,
      );
      return;
    }
    selectConfigurationFurniture(event);
  });
  element.configurationPlanImage?.addEventListener("load", renderConfigurationPlan);
  element.configurationPlanToggle?.addEventListener("click", () => {
    const collapsed = element.configurationPlanPanel.classList.toggle("is-collapsed");
    element.configurationPlanToggle.textContent = collapsed ? "+" : "−";
    element.configurationPlanToggle.title = collapsed ? "展開 2D 平面" : "收合 2D 平面";
    element.configurationPlanToggle.setAttribute(
      "aria-label",
      collapsed ? "展開 2D 平面" : "收合 2D 平面",
    );
    if (!collapsed) requestAnimationFrame(renderConfigurationPlan);
  });
  $("#replace-2d-furniture")?.addEventListener("click", openFurnitureReplacement);
  $("#close-furniture-replacement")?.addEventListener("click", () => {
    setReplacementDrawerOpen(false);
  });
  element.replacementSearch?.addEventListener("change", () => {
    loadReplacementCandidates().catch((error) => {
      element.replacementError.textContent = errorMessage(error);
    });
  });
  element.replacementQuery?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    loadReplacementCandidates().catch((error) => {
      element.replacementError.textContent = errorMessage(error);
    });
  });
  element.replacementResults?.addEventListener("click", (event) => {
    const preview = event.target.closest("[data-preview-replacement]");
    if (preview) {
      const candidates = JSON.parse(element.replacementResults.dataset.items || "[]");
      const candidate = candidates.find(
        (item) => item.furniture_id === preview.dataset.previewReplacement,
      );
      previewReplacementCandidate(candidate);
      return;
    }
    const confirmButton = event.target.closest("[data-confirm-replacement]");
    if (confirmButton) {
      replaceSelectedLayoutFurniture(confirmButton.dataset.confirmReplacement).catch((error) => {
        element.replacementError.textContent = errorMessage(error);
      });
    }
  });
  $("#cancel-white-model-beam")?.addEventListener("click", cancelWhiteModelBeamPlacement);
  const selectSceneObject = (event) => {
    const button = event.target.closest("[data-scene-object-index]");
    if (!button) return;
    saveSelectedSceneAppearance();
    state.selectedSceneIndex = Number(button.dataset.sceneObjectIndex);
    renderSceneObjectList();
    loadSelectedSceneAppearance();
    syncSceneSelectionTo2dFurniture(
      state.sceneData?.scene_objects?.[state.selectedSceneIndex],
    );
    if (state.workflow.currentStep === "realistic_3d") {
      realisticViewer.selectObjectByIndex(state.selectedSceneIndex);
    } else {
      whiteViewer.selectObjectByIndex(state.selectedSceneIndex);
    }
    scheduleSave(state.workflow.currentStep);
  };
  element.objectList?.addEventListener("click", selectSceneObject);
  element.realisticObjectList?.addEventListener("click", selectSceneObject);
  $("#delete-replacement-furniture")?.addEventListener("click", async () => {
    await deleteSelectedSceneFurniture();
    if (element.replacementDrawer.open) setReplacementDrawerOpen(false);
  });
  $("#delete-realistic-furniture")?.addEventListener("click", deleteSelectedSceneFurniture);
  [
    "#specified-furniture-color",
    "#specified-furniture-material",
    "#lock-specified-model",
    "#lock-specified-material",
  ].forEach((selector) => $(selector).addEventListener("change", () => {
    saveSelectedSceneAppearance();
    scheduleSave("white_model_3d");
  }));
  $("#toggle-furniture-numbers")?.addEventListener("click", () => {
    state.showFurnitureNumbers = !state.showFurnitureNumbers;
    syncFurnitureNumberVisibility();
  });
  $$('[data-scene-sidebar-tab]').forEach((button) => {
    button.addEventListener("click", () => {
      const tab = button.dataset.sceneSidebarTab;
      if (tab === "surfaces" && state.workflow?.currentStep === "white_model_3d") {
        void confirmWhiteModel().catch((error) => setStatus(errorMessage(error), "error"));
        return;
      }
      setSceneSidebarTab(tab);
      if (tab === "surfaces") focusStepSixRoom(state.selectedRoomId || state.rooms[0]?.id);
    });
  });
  $("#open-furniture-catalog")?.addEventListener("click", () => setFurnitureCatalogOpen(true));
  element.openRoomSchemeSelection?.addEventListener("click", openRoomSchemeSelectionDialog);
  $("#close-room-scheme-selection")?.addEventListener("click", closeRoomSchemeSelectionDialog);
  $("#room-scheme-cancel")?.addEventListener("click", closeRoomSchemeSelectionDialog);
  element.roomSchemeList?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-room-scheme-room]");
    if (!button) return;
    state.selectedRoomSchemeId = button.dataset.roomSchemeRoom;
    renderRoomSchemeSelectionDialog();
    void ensureRoomScheme3dPreviews();   // 換房時補拍該房的 A/B 視角
  });
  element.roomSchemeChoiceGrid?.addEventListener("click", (event) => {
    const preview = event.target.closest("[data-room-scheme-preview-3d]");
    if (preview) {
      // HTML dataset cannot expose a hyphen followed by a digit as a dot property.
      // Read the attribute directly so clicking B never falls back to the selected A.
      void openRoomScheme3dPreview(preview.getAttribute("data-room-scheme-preview-3d"));
      return;
    }
    const button = event.target.closest("[data-room-scheme-choice]");
    if (!button) return;
    chooseRoomScheme(button.dataset.roomSchemeChoice);
  });
  $("#close-room-scheme-3d-preview")?.addEventListener("click", () => {
    setTaskDialogOpen(element.roomScheme3dPreviewDialog, false);
  });
  $("#room-scheme-preview-prev")?.addEventListener("click", () => navigateRoomScheme3dPreview(-1));
  $("#room-scheme-preview-next")?.addEventListener("click", () => navigateRoomScheme3dPreview(1));
  element.roomSchemeStructureFix?.addEventListener("click", () => {
    setTaskDialogOpen(element.roomScheme3dPreviewDialog, false);
    closeRoomSchemeSelectionDialog();
    goTo("space_confirmation");
  });
  element.roomSchemeComplete?.addEventListener("click", () => {
    void completeRoomSchemeSelection();
  });
  $("#close-furniture-catalog")?.addEventListener("click", () => setFurnitureCatalogOpen(false));
  $("#search-glb-furniture")?.addEventListener("click", searchGlbFurniture);
  $("#glb-furniture-search")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      searchGlbFurniture();
    }
  });
  element.standardCatalogSearch?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      searchGlbFurniture();
    }
  });
  $("#glb-furniture-search")?.addEventListener("input", () => {
    clearTimeout(catalogRuntimeState.searchTimer);
    catalogRuntimeState.searchTimer = setTimeout(searchGlbFurniture, 180);
  });
  element.questionnaireCatalogControls?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-catalog-scope]");
    const room = state.rooms.find((item) => String(item.id) === String(catalogRuntimeState.roomId));
    if (button) {
      catalogRuntimeState.scope = button.dataset.questionnaireCatalogScope;
      catalogRuntimeState.purpose = "";
      if (catalogRuntimeState.scope === "all") catalogRuntimeState.space = "";
      element.questionnaireCatalogControls
        .querySelectorAll("[data-questionnaire-catalog-scope]")
        .forEach((item) => item.classList.toggle("is-active", item === button));
      renderQuestionnaireCatalogBrowseChoices(room);
      void searchGlbFurniture();
      return;
    }
    const spaceButton = event.target.closest("[data-questionnaire-catalog-space]");
    if (spaceButton) {
      catalogRuntimeState.space = spaceButton.dataset.questionnaireCatalogSpace;
      catalogRuntimeState.purpose = "";
      renderQuestionnaireCatalogBrowseChoices(room);
      void searchGlbFurniture();
      return;
    }
    const purposeButton = event.target.closest("[data-questionnaire-catalog-purpose]");
    if (purposeButton) {
      catalogRuntimeState.purpose = purposeButton.dataset.questionnaireCatalogPurpose;
      renderQuestionnaireCatalogBrowseChoices(room);
      void searchGlbFurniture();
    }
  });
  [
    element.questionnaireCatalogType,
    element.questionnaireCatalogColor,
    element.questionnaireCatalogMaterial,
  ].forEach((control) => control?.addEventListener("change", () => void searchGlbFurniture()));
  element.glbResults?.addEventListener("click", (event) => {
    const questionnaireAddButton = event.target.closest("[data-add-questionnaire-furniture-id]");
    if (questionnaireAddButton) {
      addQuestionnaireCatalogFurniture(questionnaireAddButton.dataset.addQuestionnaireFurnitureId);
      questionnaireAddButton.textContent = "已加入本房";
      questionnaireAddButton.disabled = true;
      return;
    }
    const replacementButton = event.target.closest("[data-replace-furniture-id]");
    if (replacementButton) {
      setFurnitureCatalogOpen(false);
      replaceSceneFurniture(replacementButton.dataset.replaceFurnitureId);
      return;
    }
    const addButton = event.target.closest("[data-add-furniture-id]");
    if (addButton) {
      setFurnitureCatalogOpen(false);
      addSceneFurniture(addButton.dataset.addFurnitureId);
    }
  });
  element.glbResults?.addEventListener("change", (event) => {
    const checkbox = event.target.closest("[data-questionnaire-catalog-select]");
    if (!checkbox) return;
    const id = String(checkbox.dataset.questionnaireCatalogSelect);
    const items = JSON.parse(element.glbResults.dataset.items || "[]");
    if (checkbox.checked) {
      catalogRuntimeState.selectedFurnitureIds.add(id);
      const item = items.find((candidate) => String(candidate.furniture_id) === id);
      if (item) catalogRuntimeState.selectedFurniture.set(id, item);
    } else {
      catalogRuntimeState.selectedFurnitureIds.delete(id);
      catalogRuntimeState.selectedFurniture.delete(id);
    }
    renderQuestionnaireCatalogBatch();
  });
  element.addSelectedQuestionnaireFurniture?.addEventListener("click", () => {
    [...catalogRuntimeState.selectedFurniture.values()].forEach((item) => addQuestionnaireCatalogFurniture(item.furniture_id, item));
    catalogRuntimeState.selectedFurnitureIds = new Set();
    catalogRuntimeState.selectedFurniture = new Map();
    renderQuestionnaireCatalogBatch();
    void searchGlbFurniture();
  });
  $("#confirm-white-model")?.addEventListener("click", async () => {
    // Confirming runs a network validation + surface re-apply + step navigation,
    // which felt dead on click.  Show the busy overlay so there is always visible
    // feedback.  The cheap validation guards inside confirmWhiteModel return
    // synchronously, so the overlay only actually paints when there is real async
    // work to wait on, and the finally guarantees it is cleared on every path.
    beginPlacementBusy("正在確認家具配置並套用材質，請稍候…");
    try {
      await confirmWhiteModel();
    } finally {
      endPlacementBusy();
    }
  });
  element.styleTabs?.addEventListener("pointerdown", (event) => {
    const button = event.target.closest("[data-style-tab]");
    if (!button) return;
    state.activeStyleId = button.dataset.styleTab;
    renderStyleControls();
  });
  element.styleGrid?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-style-pack]");
    const pack = STYLE_PACKS.find((item) => item.id === button?.dataset.stylePack);
    if (pack) {
      markRealisticSceneEdited();
      applyStylePackToScene(pack);
    }
  });
  $$("[data-real-view-mode]").forEach((button) => button.addEventListener("click", () => {
    $$("[data-real-view-mode]").forEach((item) => item.classList.toggle("is-active", item === button));
    realisticViewer.setViewMode(button.dataset.realViewMode);
    $("#lock-real-view-for-edit").textContent = "鎖定視角並編輯家具";
  }));
  $("#lock-real-view-for-edit")?.addEventListener("click", (event) => {
    const locked = realisticViewer.toggleCameraLock();
    event.currentTarget.textContent = locked ? "結束家具編輯" : "鎖定視角並編輯家具";
  });
  $$("[data-proposal-view-mode]").forEach((button) => button.addEventListener("click", () => {
    $$("[data-proposal-view-mode]").forEach((item) => item.classList.toggle("is-active", item === button));
    proposalViewer.lockRenderCamera(false);
    proposalViewer.setViewMode(button.dataset.proposalViewMode);
  }));
  $("#suggest-master-view")?.addEventListener("click", () => {
    proposalViewer.lockRenderCamera(false);
    proposalViewer.setViewMode("orbit");
    proposalViewer.setCameraPreset("corner");
    $$("[data-proposal-view-mode]").forEach((item) => {
      item.classList.toggle("is-active", item.dataset.proposalViewMode === "orbit");
    });
    element.masterViewStatus.textContent = "已套用建議透視視角；可以繼續微調。";
  });
  $("#lock-master-view")?.addEventListener("click", () => {
    try {
      lockMasterRenderView();
    } catch (error) {
      element.masterViewStatus.textContent = `無法鎖定視角：${errorMessage(error)}`;
    }
  });
  $("#return-to-realistic")?.addEventListener("click", () => goTo("realistic_3d"));
  element.proposalPaletteGrid?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-proposal-style-card]");
    if (button) selectProposalPalette(button.dataset.proposalStyleCard);
  });
  $("#request-palette-renders")?.addEventListener("click", () => openRenderBriefDialog("palette_comparison"));
  element.confirmRenderPalette?.addEventListener("click", confirmRenderPalette);
  element.renderRoomList?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-render-room]");
    if (button) selectRenderRoom(button.dataset.renderRoom);
  });
  $("#save-room-view")?.addEventListener("click", saveSelectedRoomView);
  $("#submit-room-renders")?.addEventListener("click", () => openRenderBriefDialog("room_final"));
  const galleryTileFrom = (target) => {
    const tile = target?.closest?.("[data-gallery-room]");
    if (!tile) return null;
    return completedOpenrouterRows().find(
      (item) => String(item.room_id) === String(tile.dataset.galleryRoom),
    ) || null;
  };
  element.aiRenderImageStage?.addEventListener("click", (event) => {
    if (event.target?.closest?.("#ai-render-stage-close")) return; // 由關閉鈕自己處理
    const row = galleryTileFrom(event.target);
    if (row) { showRenderImageEnlarged(row.image_data_url, row.room_label || row.room_id); return; }
    closeRenderImageStage();
  });
  element.aiRenderImageStage?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " " && event.key !== "Escape") return;
    event.preventDefault();
    const row = event.key === "Escape" ? null : galleryTileFrom(event.target);
    if (row) showRenderImageEnlarged(row.image_data_url, row.room_label || row.room_id);
    else closeRenderImageStage();
  });
  element.aiRenderStageClose?.addEventListener("click", (event) => {
    event.stopPropagation();
    closeRenderImageStage();
  });
  element.aiRenderImageToggle?.addEventListener("click", () => {
    proposalRuntimeState.renderStageView = null;
    proposalRuntimeState.aiRenderImageVisible = true;
    updateAiRenderImageStage();
  });
  // 第 7 步色卡疊層:點任一處(含關閉鈕)切回 3D;鍵盤 Enter/Space/Esc 亦可關。
  element.proposalReviewImageStage?.addEventListener("click", () => closeProposalPaletteImageStage());
  element.proposalReviewImageStage?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " " || event.key === "Escape") {
      event.preventDefault();
      closeProposalPaletteImageStage();
    }
  });
  // 色卡三張(第 7 步)點縮圖 → 放大到左側 3D 區,標示是哪張色卡。
  element.paletteRenderResults?.addEventListener("click", (event) => {
    const img = event.target?.closest?.("img");
    if (!img?.getAttribute("src")) return;
    const label = (img.getAttribute("alt") || "").replace(/\s*色卡渲染$/, "").trim();
    showRenderImageEnlarged(img.src, label || "色卡");
  });
  element.deliveryProposalGenerate?.addEventListener("click", generateDeliveryProposal);
  $("#design-delivery-generate")?.addEventListener("click", () => {
    void generateDesignDelivery();
  });
  $("#close-design-delivery")?.addEventListener("click", closeDesignDelivery);
  $("#design-delivery-done")?.addEventListener("click", closeDesignDelivery);
  $("#download-design-delivery-json")?.addEventListener("click", downloadDesignDeliveryJson);
  $("#close-render-brief")?.addEventListener("click", closeRenderBriefDialog);
  $("#render-brief-cancel")?.addEventListener("click", closeRenderBriefDialog);
  $("#render-brief-confirm")?.addEventListener("click", () => {
    void confirmRenderBriefAndSubmit();
  });
  $$('[data-step-six-surface-kind]').forEach((button) => {
    button.addEventListener("click", () => setStepSixSurfaceKind(button.dataset.stepSixSurfaceKind));
  });
  $("#white-model-surface-entry")?.addEventListener("click", (event) => {
    const swatch = event.target.closest("[data-surface-color-swatch]");
    if (!swatch) return;
    const kind = swatch.dataset.surfaceColorKind;
    const color = $("#" + kind + "-color");
    if (!color) return;
    color.value = swatch.dataset.surfaceColorValue;
    state.stepSixSurfaceKind = kind;
    void previewStepSixRoomSurfaces({ userInitiated: true });
  });
  [element.wallMaterialGrouped, element.floorMaterialGrouped].forEach((host) => {
    host?.addEventListener("click", async (event) => {
      const button = event.target.closest("[data-surface-material]");
      if (!button) return;
      const kind = button.dataset.surfaceKind;
      const select = $(`#${kind}-material`);
      const color = $(`#${kind}-color`);
      const materialId = button.dataset.surfaceMaterial;
      if (select) select.value = materialId;
      if (!select || select.value !== materialId) {
        element.realisticStatus.textContent = "材質選項尚未載入完成，請重新選擇。";
        return;
      }
      if (color && button.dataset.surfaceColor) color.value = button.dataset.surfaceColor;
      state.stepSixSurfaceKind = kind;
      markRealisticSceneEdited();
      await previewStepSixRoomSurfaces({ userInitiated: true });
    });
  });
  ["wall-color", "floor-color", "wall-material", "floor-material"].forEach((id) => {
    $(`#${id}`)?.addEventListener("change", async () => {
      state.stepSixSurfaceKind = id.startsWith("floor") ? "floor" : "wall";
      markRealisticSceneEdited();
      await previewStepSixRoomSurfaces({ userInitiated: true });
    });
  });
  element.confirmRoomSurfaces?.addEventListener("click", () => {
    void confirmStepSixRoomSurfaces().catch((error) => setStatus(errorMessage(error), "error"));
  });
  stepSixSurfaceUnlockButtons().forEach((button) => {
    button.addEventListener("click", unlockStepSixRoomSurfaces);
  });
  $("#draw-material-boundary")?.addEventListener("click", toggleMaterialBoundary);
  $("#remove-material-boundary")?.addEventListener("click", removeMaterialBoundary);
  $("#material-boundary-position")?.addEventListener("input", () => {
    if (state.materialBoundary) toggleMaterialBoundary();
  });
  $("#material-boundary-direction")?.addEventListener("change", () => {
    if (state.materialBoundary) toggleMaterialBoundary();
  });
  element.boundarySecondaryFloor?.addEventListener("change", () => {
    if (state.materialBoundary) toggleMaterialBoundary();
  });
  element.ceilingStyle?.addEventListener("change", () => {
    markRealisticSceneEdited();
    evaluateCeilingConflicts();
  });
  element.lightStyle?.addEventListener("change", () => {
    markRealisticSceneEdited();
    evaluateCeilingConflicts();
  });
  element.lightingFixtureSelect?.addEventListener("change", () => {
    markRealisticSceneEdited();
    evaluateCeilingConflicts();
  });
  $("#undo-style-change")?.addEventListener("click", async () => {
    const previous = state.styleHistory.pop();
    if (!previous) return;
    state.surfaceState = previous.surfaceState;
    const pack = STYLE_PACKS.find((item) => item.id === previous.packId);
    if (pack) {
      state.activeStylePackId = null;
      await applyStylePackToScene(pack);
    }
  });
  $("#save-realistic-scene")?.addEventListener("click", () => {
    if (!allStepSixRoomSurfacesConfirmed()) {
      const firstUnconfirmed = firstUnconfirmedStepSixRoom();
      if (firstUnconfirmed) focusStepSixRoom(firstUnconfirmed.id);
      setStepSixSurfaceStatus(
        `請先確認「${firstUnconfirmed?.label || "所有房間"}」的材質，再前往第 7 步。`,
      );
      return;
    }
    const completed = state.workflow.complete("realistic_3d", { confirmed: true });
    if (!completed) return;
    scheduleSave("realistic_3d");
    setStatus("第 6 步配置已保存；接著逐房確認生圖視角。");
    goTo("proposal_review");
  });
  $$(".rp-progress button").forEach((button) => button.addEventListener("click", () => {
    const step = button.dataset.step;
    if (step === "recognition" && state.workflow?.canEnter("recognition")) {
      goTo(state.workflow.completed.includes("calibration") ? "calibration" : "recognition");
      return;
    }
    if (step === "layout_2d") {
      const stepSixTarget = state.workflow?.canEnter("realistic_3d")
        ? "realistic_3d"
        : (state.workflow?.canEnter("white_model_3d") ? "white_model_3d" : "layout_2d");
      if (state.workflow?.canEnter(stepSixTarget)) goTo(stepSixTarget);
      else setStatus(firstWorkflowBlocker(stepSixTarget), "error");
      return;
    }
    if (state.workflow?.canEnter(step)) goTo(step);
    else setStatus(firstWorkflowBlocker(step), "error");
  }));
  $("#reset-project")?.addEventListener("click", () => {
    if (!confirm("要重新開始此專案嗎？目前頁面的本機流程狀態會清除。")) return;
    state.workflow?.reset();
    history.replaceState({}, "", "/scene");
    location.reload();
  });
  window.addEventListener("resize", syncAllOverlays);
  window.addEventListener("beforeunload", (event) => {
    if (projectExitConfirmed) return;
    if (pendingSaveCount === 0 && !localStorage.getItem(pendingSaveStorageKey())) return;
    event.preventDefault();
    event.returnValue = "";
  });
}

  return bindEvents;
}
