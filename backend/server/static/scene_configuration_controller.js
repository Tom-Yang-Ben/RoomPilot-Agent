import { createQuestionnaireFurnitureController } from "./scene_questionnaire_furniture_controller.js?v=sha256-c4ae60f01581";
import { createSceneLayoutController } from "./scene_layout_controller.js?v=sha256-7e9d5c80e187";
import { createSceneReplacementController } from "./scene_replacement_controller.js?v=sha256-e99ec83f0e29";

export function createSceneConfigurationController(runtime) {
  let layoutController;
  let replacementController;
  const questionnaireController = createQuestionnaireFurnitureController({
    ...runtime,
    questionnaireFurniturePreviewMarkup: (...args) => layoutController.questionnaireFurniturePreviewMarkup(...args),
    replacementCandidateFitsRoom: (...args) => replacementController.replacementCandidateFitsRoom(...args),
  });
  layoutController = createSceneLayoutController({
    ...runtime,
    ...questionnaireController,
    replacementCandidateImageUrl: (...args) => replacementController.replacementCandidateImageUrl(...args),
  });
  replacementController = createSceneReplacementController({
    ...runtime,
    ...questionnaireController,
    ...layoutController,
  });
  return {
    ...questionnaireController,
    ...layoutController,
    ...replacementController,
  };
}