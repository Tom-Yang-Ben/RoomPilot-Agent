// Shared reload contract for catalog edits that rebuild a Three.js scene.
export async function reloadViewerPreservingState(
  viewer,
  sceneData,
  { interactionMode = null } = {},
) {
  const cameraState = viewer.getCameraState?.() || null;
  await viewer.loadScene(sceneData);
  if (cameraState) viewer.setCameraState?.(cameraState);
  if (interactionMode) viewer.setInteractionMode?.(interactionMode);
  return cameraState;
}
