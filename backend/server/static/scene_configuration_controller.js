import { createQuestionnaireFurnitureController } from "./scene_questionnaire_furniture_controller.js?v=sha256-eaeb7785b9a6";
import { createSceneLayoutController } from "./scene_layout_controller.js?v=sha256-b05318e0f0a6";
import { createSceneReplacementController } from "./scene_replacement_controller.js?v=sha256-4194e5b50b56";

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