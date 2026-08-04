**Source Visual Truth**

- Path: `C:\Users\ADMINI~1\AppData\Local\Temp\codex-clipboard-eb666f8e-d0d5-472d-99f3-e77ff48dbac9.png`
- Pixels: 1165 x 1717.
- State: Step 4, room confirmation tab, right review rail at the top of a seven-room queue.

**Rendered Implementation**

- Top-state screenshot: `C:\Users\Administrator\RoomPilot-Agent\.tmp\product-design\step4-fixed-top.png`
- Scrolled-state screenshot: `C:\Users\Administrator\RoomPilot-Agent\.tmp\product-design\step4-fixed-scrolled.png`
- Full-view comparison: `C:\Users\Administrator\RoomPilot-Agent\.tmp\product-design\step4-source-vs-fixed.png`
- Scroll-behavior comparison: `C:\Users\Administrator\RoomPilot-Agent\.tmp\product-design\step4-scroll-behavior.png`
- Pixels and CSS viewport: 1165 x 768 at device pixel ratio 1. No density normalization was required. The source was cropped to its top 768 pixels for the equal-size full-view comparison.
- State: Step 4, room confirmation tab, right review rail at the top and after a 560 px rail-only scroll. The available QA project contains nine rooms, so room names and counts differ from the source while the interaction state and layout are equivalent.

**Findings**

- No actionable P0, P1, or P2 findings remain for the requested scrolling behavior.
- Fonts and typography: unchanged from the source RoomPilot implementation; no new type styles or wrapping behavior were introduced.
- Spacing and layout rhythm: the desktop two-column workspace now fits the 768 px viewport. The page scroll height equals the viewport height, the left plan remains at y=231 through the rail scroll, and the completion bar remains visible.
- Colors and visual tokens: unchanged; the existing ivory, espresso, sage, border, radius, and shadow tokens are preserved.
- Image quality and asset fidelity: the existing floor-plan image and overlays are reused without raster replacement, cropping changes, or generated substitutes.
- Copy and content: unchanged. The source has seven rooms and the QA project has nine; this is test-data variance rather than design drift.

**Comparison History**

- Initial P1: the right rail declared `overflow-y: auto` but had no constrained height, so its content expanded the grid and the document scrolled. The cached stylesheet also retained the old behavior.
- Fix: constrain the desktop Step 4 shell to the available dynamic viewport height, use `minmax(0, 1fr)` for the workspace row, allow the plan stage to shrink, make the review rail the vertical scroll container, keep the completion bar in the fixed grid row, and update the shared CSS cache key.
- Post-fix evidence: at 1165 x 768, document `scrollHeight` and `clientHeight` are both 768; document `scrollTop` remains 0; the review rail changes from `scrollTop` 0 to 560; the plan remains y=231..642; the completion bar remains y=648..732.

**Focused Region Comparison**

- `step4-scroll-behavior.png` places the rail's top and scrolled states together. The plan, workspace frame, and completion bar remain aligned while only the right-rail content and scrollbar thumb move.

**Primary Interactions Tested**

- Opened an existing completed project and navigated from Step 8 to Step 4.
- Scrolled 560 px with the pointer positioned inside the right review rail.
- Verified that the document did not scroll and the left plan did not move.
- Checked browser console errors: none.

**Implementation Checklist**

- [x] Constrain Step 4 to the desktop viewport.
- [x] Make the right review rail independently scrollable.
- [x] Keep the left plan and bottom completion action visible.
- [x] Preserve the existing single-column behavior below 1025 px.
- [x] Add a regression contract and refresh the shared CSS cache key.

**Follow-up Polish**

- None required for this focused interaction change.

final result: passed

# Step 7 Guided Proposal-Lock Sidebar

**Source Visual Truth**

- Path: `C:\Users\Administrator\.codex\generated_images\019fcafc-8770-7db1-9262-400e7caae8b4\exec-0eb13599-8c96-4c73-aa08-e08b755f3382.png`
- Pixels: 1043 x 1508.
- State: the user-selected second design direction, with a compact proposal summary, expanded palette stage, selected low-saturation card, and visible view-lock actions.

**Rendered Implementation**

- Top-state screenshot: `C:\Users\Administrator\RoomPilot-Agent\.tmp\product-design\step7-sidebar-top.png`
- Interaction/action-state screenshot: `C:\Users\Administrator\RoomPilot-Agent\.tmp\product-design\step7-sidebar-actions.png`
- Side-by-side comparison: `C:\Users\Administrator\RoomPilot-Agent\.tmp\product-design\step7-source-vs-after.png`
- Pixels and CSS viewport: implementation captures are 832 x 720 at device pixel ratio 1; the production right rail is 460 CSS px. The comparison crops the implementation to that 460 px rail and scales both evidence regions for a single 832 px comparison viewport. No density normalization was required.
- State: Step 7, summary complete, low-saturation palette selected, view stage active, and content confirmation checked in the action-state capture.

**Findings**

- No actionable P0, P1, or P2 findings remain.
- Fonts and typography: the existing RoomPilot system font stack is retained. The hierarchy follows the selected direction with 20 px screen title, 16 px stage headings, compact 12–13 px explanatory copy, and no character-by-character wrapping.
- Spacing and layout rhythm: the 460 px rail uses three vertically ordered cards with 12 px stage gaps, 16 px internal padding, compact 34 px numbered headers, and a two-column summary grid. The final action area is grouped inside stage 3 instead of scattering buttons between unrelated cards.
- Colors and visual tokens: the existing ivory, warm gray, white, and `#27715d` brand green map directly to the source direction. Green is reserved for active/completed stage semantics and the primary lock action.
- Image quality and asset fidelity: all three production style-card raster images are reused with correct 4:3 source crops and no generated placeholders, CSS drawings, or custom SVG substitutions.
- Copy and content: the three stages use action-led titles (`檢查完整方案`, `選擇同風格色卡`, `鎖定比較視角`) and preserve every existing workflow action. Furniture/style cues are populated from the production style-pack data rather than hard-coded in the application.
- Accessibility and interactions: the palette is a named radiogroup with radio semantics and selected state; the confirmation control keeps a native label and checkbox; state text is not color-only; focus styling is inherited from the established workflow controls.
- Responsiveness: the rail remains independently scrollable at desktop width; the summary and palette-card media tracks collapse at the existing narrow breakpoints without hiding the primary action.

**Comparison History**

- Initial P1: the original production sidebar presented the summary, three large style cards, a large confirmation block, and five actions as equally weighted sections, producing a long and difficult-to-scan rail.
- Fix: reorganize the content into a numbered three-stage flow, use compact summary rows, turn palette choices into horizontal radio cards, and group confirmation plus primary/secondary actions inside the final stage.
- Initial P2: selection progress and the next required action were only described in body copy.
- Fix: add explicit `待選擇`, `已選擇`, `尚未鎖定`, and `已鎖定` stage states synchronized with the existing application data.
- Post-fix evidence: the combined comparison shows the same three-stage hierarchy and selected palette direction as the source. Browser interaction changed the palette stage to complete, checked the confirmation control, scrolled to stage 3, and reported zero console errors.

**Focused Region Comparison**

- `step7-source-vs-after.png` places the full selected direction beside two readable implementation crops: the summary/palette header region and the palette/action region. Separate focused crops were necessary because the full 1508 px source makes 12 px rail text too small to judge at the desktop QA viewport.

**Primary Interactions Tested**

- Selected a different palette radio card and verified the palette stage changed to `已選擇`.
- Checked the content-confirmation control and verified stage 3 received its confirmed visual state.
- Verified the view suggestion, primary lock, PNG download, project save, and Step 6 return actions remained present and reachable.
- Checked browser console errors: none.

**Implementation Checklist**

- [x] Replace the flat Step 7 rail with a three-stage guided flow.
- [x] Keep summary data compact and readable at 460 px.
- [x] Use real style-card assets with radio semantics and visible selected state.
- [x] Group confirmation, view status, primary CTA, and secondary actions.
- [x] Preserve the post-lock per-room view panel inside stage 3.
- [x] Add regression coverage and refresh CSS/JavaScript cache keys.

**Follow-up Polish**

- P3: when per-room view locking is reached, consider collapsing stages 1 and 2 to headers so more of the room-view candidate list is visible without scrolling.

final result: passed

---

# Step 6 Surface Material Panel Redesign

**Source Visual Truth**

- Path: `C:\Users\ADMINI~1\AppData\Local\Temp\codex-clipboard-a65d6318-620b-4bd5-8fae-d050e7784b97.png`
- Pixels: 1167 x 1702.
- State: Step 6 realistic-material workspace with the wall and floor material controls visible in the right rail.

**Rendered Implementation**

- Production-markup QA render: `C:\Users\Administrator\RoomPilot-Agent\.tmp\product-design\step6-material-panel-after-full.jpg`
- Side-by-side comparison: `C:\Users\Administrator\RoomPilot-Agent\.tmp\product-design\step6-material-source-vs-after.jpg`
- Pixels: implementation 1264 x 1064; comparison 1264 x 1115.
- CSS viewport: 1280 px desktop viewport at device pixel ratio 1. The comparison crops both right-rail regions to 460 px and aligns them at the top; no density normalization was required.
- State: wall and floor colors visible, wall and floor option groups expanded, one active option in each group, advanced material-boundary controls collapsed.

**Findings**

- No actionable P0, P1, or P2 findings remain for the requested material-panel redesign.
- Fonts and typography: the existing RoomPilot font stack and weights are preserved. Material names remain horizontal at 13 px with 1.35 line height; explanations use an intentional three-line clamp instead of collapsing to one character per line.
- Spacing and layout rhythm: wall and floor are separate full-width groups. The 460 px rail produces 171 px two-column cards; the 340 px breakpoint switches headers, color controls, and card grids to one column.
- Colors and visual tokens: the existing ivory, warm gray, espresso, and `--rp-green` palette is retained. Active states use the existing green token with a pale-green surface rather than a new competing color system.
- Image quality and asset fidelity: production surface texture assets are used directly at 62 x 82 px with cover positioning. No generated placeholders, CSS drawings, or substituted icons are present.
- Copy and content: controls now distinguish color from material, explain each surface's role, and separate `目前選取` from `風格推薦`. Existing material reasons remain the source of card copy.
- Accessibility: material buttons expose `aria-pressed`; hover and keyboard focus states are distinct; advanced boundary controls remain reachable inside a native details element.

**Comparison History**

- Initial P1: the outer two-column field container placed each material grid in half of the right rail, while the grid itself divided that width again. Cards became extremely narrow and Chinese text rendered one character per line.
- Fix: remove the nested half-width layout, give wall and floor their own full-width sections, and use an auto-fit card grid with a 164 px minimum.
- Initial P2: color, material selection, recommendation copy, and boundary controls had equal visual weight, making the main selection task difficult to scan.
- Fix: promote color summaries, group material choices, add compact active/recommended badges, strengthen the lock action, and move boundary controls into a collapsed advanced section.
- Post-fix evidence: at the desktop viewport, every material name reads horizontally, cards measure 171 px, the sidebar has no horizontal overflow, and the browser console reports zero errors.

**Focused Region Comparison**

- `step6-material-source-vs-after.jpg` places the original and revised right rails together. The crop shows the original character-by-character wrapping and the revised horizontal card hierarchy at equivalent rail width.

**Primary Interactions Tested**

- Loaded the production stylesheet and the production material-panel markup with real surface texture assets.
- Selected a different wall material card and verified its `aria-pressed` state changed to `true` while the previous card changed to `false`.
- Verified semantic labels for color controls, selects, material cards, lock action, and advanced boundary section.
- Checked browser console errors: none.

**Implementation Checklist**

- [x] Separate wall and floor material groups from the generic two-column field layout.
- [x] Keep material thumbnails, names, reasons, and state badges readable at desktop rail width.
- [x] Add responsive one-column behavior for the 340 px rail breakpoint.
- [x] Preserve existing IDs, events, material data, and real asset paths.
- [x] Add regression coverage and refresh CSS and scene-module cache keys.

**Follow-up Polish**

- P3: if future material catalogs grow beyond roughly eight options per surface, add a search or category filter rather than making the rail taller.

final result: passed

---

# Step 6 Furniture Workspace Polish

**Source Visual Truth**

- Path: `C:\Users\ADMINI~1\AppData\Local\Temp\codex-clipboard-3a0c1241-f7a6-48f9-bbf5-cf1f91a1dcb2.png`
- Pixels: 1176 x 1654.
- State: Step 6 white-model workspace, synchronized-plan tab active, furniture 2 selected.

**Rendered Implementation**

- Full isolated sidebar render: `C:\Users\Administrator\RoomPilot-Agent\.tmp\product-design\step6-sidebar-fixed.png`
- Desktop viewport render: `C:\Users\Administrator\RoomPilot-Agent\.tmp\product-design\step6-sidebar-fixed-top.png`
- Source comparison: `C:\Users\Administrator\RoomPilot-Agent\.tmp\product-design\step6-source-vs-fixed.png`
- The isolated render uses the production Step 6 markup and stylesheet at a 1176 px desktop viewport. The source project lost its temporary browser session after reload, so the comparison uses representative, non-persistent fixture data rather than mutating or recreating the user's project.

**Findings**

- No actionable P0, P1, or P2 findings remain for the requested scope.
- Furniture annotations: the Step 6 viewer keeps numbered sprites for 2D/3D cross-reference but no longer creates a name sprite for every furniture item. Names remain available in the synchronized list and selected-furniture editor.
- Right header alignment: tabs, the `2D 配置與問題家具` heading, and the collapse control now share one 460 px rail, consistent horizontal insets, and a fixed two-column header grid.
- Lower controls: related actions are grouped into consistent white work sections with a small semantic accent, restrained shadow, unified button height, and a stronger final confirmation action.
- Scope protection: all new sidebar styles are nested under `#white-model-3d-step`, so the Step 7 proposal sidebar is unaffected.
- Typography and tokens: existing RoomPilot typefaces and green, ivory, violet, and blue state colors are preserved; no new decorative assets or gradients were introduced in production.

**Comparison History**

- Initial P1: furniture name plates obscured objects and made the 3D view noisy.
- Fix: add a viewer-level `showFurnitureNames` option and disable only names for the Step 6 white-model viewer while keeping number markers.
- Initial P1: the top tabs, plan heading, and collapse control read as separate, slightly offset blocks.
- Fix: normalize the sidebar padding and give the plan surface a fixed `minmax(0, 1fr) 34px` header grid.
- Initial P2: lower-right actions were visually flat and difficult to scan.
- Fix: apply a shared work-section hierarchy, consistent spacing, button treatment, and a clearer final CTA.

**Implementation Checklist**

- [x] Keep furniture numbers while removing in-scene furniture names.
- [x] Align the right-side tabs, plan heading, and collapse action.
- [x] Improve lower-right information hierarchy without changing workflow semantics.
- [x] Scope Step 6 styles away from the proposal review sidebar.
- [x] Add regression coverage and refresh static asset cache keys.

**Follow-up Polish**

- None required for this focused pass.

final result: passed

---

# Step 8 AI Rendering Workbench

**Source Visual Truth**

- Path: `C:\Users\Administrator\.codex\generated_images\019fcafc-8770-7db1-9262-400e7caae8b4\exec-692f0ae8-092e-4a01-ac61-71eea013828a.png`
- Pixels: 1035 x 1519.
- State: the user-selected second design direction, with the palette workspace active, compact rendering settings, segmented workflow navigation, and summarized room/result actions.

**Rendered Implementation**

- Screenshot: unavailable.
- Intended viewport: the existing production desktop scene route with the 460 CSS px right rail, matched to the source's tall desktop state.
- Density normalization: unavailable because the implementation could not be captured.
- State: implementation and contract tests completed, but visual state could not be opened for comparison.

**Findings**

- [P1] Browser-rendered evidence is unavailable.
  Location: Step 8 production route in the in-app browser.
  Evidence: the source design opened successfully, but the local production route was rejected by the in-app browser URL policy after the backend was restarted.
  Impact: typography, spacing, wrapping, color balance, and responsive behavior cannot be visually compared against the selected source.
  Fix: reopen the production scene route in the in-app browser, capture the Step 8 palette state at the intended desktop viewport, combine it side by side with the source, and repeat this QA pass.

**Required Fidelity Surfaces**

- Fonts and typography: blocked pending a browser-rendered capture.
- Spacing and layout rhythm: blocked pending a browser-rendered capture.
- Colors and visual tokens: blocked pending a browser-rendered capture.
- Image quality and asset fidelity: the selected direction contains no new raster assets in the redesigned rail; final visible rendering remains blocked pending capture.
- Copy and content: static contract coverage confirms the existing actions and Traditional Chinese labels remain present, but visible wrapping and truncation cannot be judged without the rendered capture.

**Full-view Comparison Evidence**

- Blocked: no implementation screenshot was available, so no combined comparison image was created.

**Focused Region Comparison Evidence**

- Blocked for the same reason; the palette cards, segmented navigation, and compact phase summaries require browser-rendered evidence.

**Comparison History**

- Initial blocker: the existing app tab first showed `ERR_CONNECTION_REFUSED` because the local backend was not listening.
- Recovery completed: the local FastAPI service was restarted and `/api/health` returned ready.
- Remaining blocker: the in-app browser URL policy rejected reloading the local production route, so the implementation could not be recaptured or visually iterated.

**Primary Interactions Tested**

- Static interaction contracts passed for segmented workflow navigation, stage-state synchronization, palette multi-select behavior, and all existing Step 8 action IDs.
- Browser interaction testing was blocked before the page could be rendered.
- Console errors could not be checked for the rendered Step 8 state.

**Implementation Checklist**

- [x] Preserve all six rendering-preference controls.
- [x] Preserve palette, room-rendering, download, and project-save actions.
- [x] Add the selected compact workbench structure and interactive segmented navigation.
- [x] Add focused regression coverage and refresh static asset cache keys.
- [ ] Capture the implementation in the in-app browser and complete side-by-side visual QA.

**Follow-up Polish**

- Deferred until the production route can be rendered and inspected.

final result: blocked
