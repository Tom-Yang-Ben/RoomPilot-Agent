import { createSceneSchemeController } from "./scene_scheme_controller.js?v=sha256-569a5c9d029c";
import { createSceneStructureEditorController } from "./scene_structure_editor_controller.js?v=sha256-8cb7e968d492";

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