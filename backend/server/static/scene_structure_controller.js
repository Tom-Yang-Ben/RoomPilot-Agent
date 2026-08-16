import { createSceneSchemeController } from "./scene_scheme_controller.js?v=sha256-9874fc53a6c7";
import { createSceneStructureEditorController } from "./scene_structure_editor_controller.js?v=sha256-c72f02e08639";

export function createSceneStructureController(runtime) {
  let editorController;
  const schemeController = createSceneSchemeController({
    ...runtime,
    nearestPointOnSegment: (...args) => editorController.nearestPointOnSegment(...args),
    openingHostWall: (...args) => editorController.openingHostWall(...args),
    renderStructureCounts: (...args) => editorController.renderStructureCounts(...args),
    renderStructureSvg: (...args) => editorController.renderStructureSvg(...args),
    repairLoadedStructureWallCollisions: (...args) => editorController.repairLoadedStructureWallCollisions(...args),
  });
  editorController = createSceneStructureEditorController({
    ...runtime,
    ...schemeController,
  });
  return { ...schemeController, ...editorController };
}