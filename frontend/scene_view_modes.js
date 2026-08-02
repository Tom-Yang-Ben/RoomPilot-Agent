export const VIEW_MODES = Object.freeze(["dollhouse", "walk", "topdown", "orbit"]);

export const VIEW_MODE_CONFIG = Object.freeze({
  dollhouse: Object.freeze({ camera: "orthographic", controller: "orbit", walls: "full" }),
  walk: Object.freeze({ camera: "perspective", controller: "first_person", walls: "full" }),
  topdown: Object.freeze({ camera: "orthographic", controller: "pan_zoom", walls: "flattened" }),
  orbit: Object.freeze({ camera: "perspective", controller: "orbit", walls: "full" }),
});

export function createViewModeState(initialMode = "dollhouse") {
  let mode = VIEW_MODES.includes(initialMode) ? initialMode : "dollhouse";
  return {
    get mode() { return mode; },
    setMode(nextMode) {
      if (!VIEW_MODES.includes(nextMode)) throw new Error(`不支援的檢視模式：${nextMode}`);
      mode = nextMode;
      return { mode, ...VIEW_MODE_CONFIG[mode] };
    },
    getConfig() { return { mode, ...VIEW_MODE_CONFIG[mode] }; },
  };
}
