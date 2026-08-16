import { createSceneSchemeController } from "./scene_scheme_controller.js?v=sha256-9a9b39b54039";
import { createSceneStructureEditorController } from "./scene_structure_editor_controller.js?v=sha256-7f48efa7b172";

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