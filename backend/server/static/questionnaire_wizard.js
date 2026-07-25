export function showQuestionnaireStep(stages, requestedIndex = 0) {
  const items = [...(stages || [])];
  if (!items.length) {
    return { index: 0, total: 0, current: null };
  }
  const index = Math.min(Math.max(0, requestedIndex), items.length - 1);
  items.forEach((stage, stageIndex) => {
    stage.hidden = stageIndex !== index;
  });
  return {
    index,
    total: items.length,
    current: items[index],
  };
}

export function validateQuestionnaireStage(
  stage,
  {
    axisDatasetKey,
    usesDatasetKey,
  } = {},
) {
  if (!stage) return { ready: true, kind: "optional", label: "" };
  const label = stage.querySelector("legend")?.textContent
    || stage.querySelector("span")?.textContent
    || "目前題目";
  if (axisDatasetKey && stage.dataset[axisDatasetKey]
      && !stage.querySelector("input:checked")) {
    return { ready: false, kind: "axis", label };
  }
  if (usesDatasetKey && stage.dataset[usesDatasetKey] === "uses"
      && !stage.querySelector("input:checked")) {
    return { ready: false, kind: "uses", label };
  }
  return { ready: true, kind: "optional", label };
}

export function questionnairePlanPoint(point, floorplan = {}) {
  const scale = Number(floorplan?.scale?.cm_per_px);
  const bbox = floorplan?.plan_bbox_px;
  if (!Number.isFinite(scale) || scale <= 0 || !Array.isArray(bbox) || bbox.length < 4) {
    return { x: Number(point?.x) || 0, y: Number(point?.y) || 0 };
  }
  return {
    x: Number(bbox[0]) + (Number(point?.x) || 0) / scale,
    y: Number(bbox[3]) - (Number(point?.y) || 0) / scale,
  };
}

function pointInPolygon(point, polygon) {
  let inside = false;
  for (let index = 0, previous = polygon.length - 1; index < polygon.length; previous = index++) {
    const currentPoint = polygon[index];
    const previousPoint = polygon[previous];
    const crosses = (
      (currentPoint.y > point.y) !== (previousPoint.y > point.y)
      && point.x < (
        (previousPoint.x - currentPoint.x)
        * (point.y - currentPoint.y)
        / ((previousPoint.y - currentPoint.y) || Number.EPSILON)
        + currentPoint.x
      )
    );
    if (crosses) inside = !inside;
  }
  return inside;
}

function distanceToSegment(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = dx * dx + dy * dy;
  const ratio = lengthSquared
    ? Math.max(0, Math.min(1, (
      (point.x - start.x) * dx + (point.y - start.y) * dy
    ) / lengthSquared))
    : 0;
  return Math.hypot(
    point.x - (start.x + ratio * dx),
    point.y - (start.y + ratio * dy),
  );
}

function distanceToPolygonEdges(point, polygon) {
  return polygon.reduce((closest, start, index) => {
    const end = polygon[(index + 1) % polygon.length];
    return Math.min(closest, distanceToSegment(point, start, end));
  }, Number.POSITIVE_INFINITY);
}

export function questionnairePolygonLabelPoint(points = []) {
  const polygon = points
    .map((point) => ({ x: Number(point?.x), y: Number(point?.y) }))
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
  if (polygon.length < 3) return polygon[0] || { x: 0, y: 0 };

  let twiceArea = 0;
  let weightedX = 0;
  let weightedY = 0;
  polygon.forEach((point, index) => {
    const next = polygon[(index + 1) % polygon.length];
    const cross = point.x * next.y - next.x * point.y;
    twiceArea += cross;
    weightedX += (point.x + next.x) * cross;
    weightedY += (point.y + next.y) * cross;
  });
  const centroid = Math.abs(twiceArea) > Number.EPSILON
    ? {
      x: weightedX / (3 * twiceArea),
      y: weightedY / (3 * twiceArea),
    }
    : polygon.reduce(
      (total, point) => ({
        x: total.x + point.x / polygon.length,
        y: total.y + point.y / polygon.length,
      }),
      { x: 0, y: 0 },
    );
  if (pointInPolygon(centroid, polygon)) return centroid;

  const bounds = polygon.reduce(
    (result, point) => ({
      minX: Math.min(result.minX, point.x),
      minY: Math.min(result.minY, point.y),
      maxX: Math.max(result.maxX, point.x),
      maxY: Math.max(result.maxY, point.y),
    }),
    {
      minX: Number.POSITIVE_INFINITY,
      minY: Number.POSITIVE_INFINITY,
      maxX: Number.NEGATIVE_INFINITY,
      maxY: Number.NEGATIVE_INFINITY,
    },
  );
  let best = polygon[0];
  let bestDistance = -1;
  const sampleCount = 20;
  for (let row = 0; row < sampleCount; row += 1) {
    for (let column = 0; column < sampleCount; column += 1) {
      const candidate = {
        x: bounds.minX + (column + 0.5) * (bounds.maxX - bounds.minX) / sampleCount,
        y: bounds.minY + (row + 0.5) * (bounds.maxY - bounds.minY) / sampleCount,
      };
      if (!pointInPolygon(candidate, polygon)) continue;
      const distance = distanceToPolygonEdges(candidate, polygon);
      if (distance > bestDistance) {
        best = candidate;
        bestDistance = distance;
      }
    }
  }
  return best;
}

export function questionnaireRoomAnswerContent(answer = {}) {
  return {
    uses: answer.uses || [],
    axes: answer.axes || {},
    customNotes: answer.customNotes || {},
    stageNotes: {
      uses: answer.stageNotes?.uses || "",
      furniture: answer.stageNotes?.furniture || "",
    },
    furniture: answer.furniture || [],
    priority: answer.priority || "",
    personalNeeds: answer.personalNeeds || "",
    materialPreferences: {
      wall: answer.materialPreferences?.wall || [],
      floor: answer.materialPreferences?.floor || [],
      furniture: answer.materialPreferences?.furniture || [],
      color: answer.materialPreferences?.color || [],
      finish: answer.materialPreferences?.finish || [],
      cuts: answer.materialPreferences?.cuts || [],
    },
  };
}

export function questionnaireRoomAnswerHasDraft(answer) {
  const content = questionnaireRoomAnswerContent(answer);
  return content.uses.length > 0
    || Object.values(content.axes).some(Boolean)
    || Object.values(content.customNotes).some(Boolean)
    || Object.values(content.stageNotes).some(Boolean)
    || content.furniture.length > 0
    || Boolean(content.priority)
    || Boolean(content.personalNeeds)
    || Object.values(content.materialPreferences).some((items) => items.length > 0);
}

export function questionnaireRoomAnswerChanged(draft, existing) {
  return JSON.stringify(questionnaireRoomAnswerContent(draft))
    !== JSON.stringify(questionnaireRoomAnswerContent(existing));
}

function escapeQuestionnaireHtml(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[character],
  );
}

export function renderQuestionnaireAxisChoices({
  axisDefinition,
  inputName,
} = {}) {
  if (!axisDefinition) return "";
  const endpoints = axisDefinition.options.map((option) => {
    const comparisonVisual = option.imageStatus === "ready" && option.imageUrl
      ? `<img
          class="rp-axis-image"
          src="${escapeQuestionnaireHtml(option.imageUrl)}"
          alt="${escapeQuestionnaireHtml(option.label)}對照圖"
          width="1536"
          height="1024"
          loading="lazy"
        />`
      : `<span class="rp-axis-image-placeholder" aria-label="${escapeQuestionnaireHtml(option.label)}對照圖">
          對照圖待後續確認
        </span>`;
    return `
      <label class="rp-axis-endpoint-card" data-image-key="${escapeQuestionnaireHtml(option.imageKey)}">
        <input type="radio" name="${escapeQuestionnaireHtml(inputName)}" value="${escapeQuestionnaireHtml(option.pole)}"/>
        <span class="rp-axis-endpoint-visual">
          <span class="rp-axis-pole">選項 ${option.pole.toUpperCase()}</span>
          ${comparisonVisual}
          <strong>${escapeQuestionnaireHtml(option.label)}</strong>
        </span>
      </label>
    `;
  }).join("");
  const preferenceScale = axisDefinition.preferenceOptions.length
    ? `
      <div class="rp-axis-preference-scale" aria-label="${escapeQuestionnaireHtml(axisDefinition.label)}偏好程度">
        ${axisDefinition.preferenceOptions.map((option) => `
          <label>
            <input type="radio" name="${escapeQuestionnaireHtml(inputName)}" value="${escapeQuestionnaireHtml(option.value)}"/>
            <span>${escapeQuestionnaireHtml(option.label)}</span>
          </label>
        `).join("")}
      </div>
    `
    : '<p class="rp-axis-exclusive-note">此題為互斥條件，請直接選擇 A 或 B；不同做法可寫在「補充我的想法」。</p>';
  return `
    <div class="rp-axis-endpoints">
      ${endpoints}
    </div>
    ${preferenceScale}
  `;
}

function technicalDataAttribute(dataAttribute) {
  return [
    "data-technical-axis",
    "data-client-technical-axis",
  ].includes(dataAttribute)
    ? dataAttribute
    : "data-technical-axis";
}

export function renderQuestionnaireTechnicalChoices({
  axes = [],
  inputPrefix = "technical",
  dataAttribute = "data-technical-axis",
} = {}) {
  const safeDataAttribute = technicalDataAttribute(dataAttribute);
  return axes.map((axisDefinition) => `
    <section
      class="rp-technical-axis-block"
      ${safeDataAttribute}="${escapeQuestionnaireHtml(axisDefinition.id)}"
    >
      <h4>${escapeQuestionnaireHtml(axisDefinition.label)}</h4>
      <p>${escapeQuestionnaireHtml(axisDefinition.prompt)}</p>
      ${renderQuestionnaireAxisChoices({
        axisDefinition,
        inputName: `${inputPrefix}-${axisDefinition.id}`,
      })}
    </section>
  `).join("");
}

export function readQuestionnaireTechnicalChoices({
  container,
  axes = [],
  dataAttribute = "data-technical-axis",
} = {}) {
  const safeDataAttribute = technicalDataAttribute(dataAttribute);
  return Object.fromEntries(axes.map((axisDefinition) => {
    const host = container?.querySelector(
      `[${safeDataAttribute}="${axisDefinition.id}"]`,
    );
    return [
      axisDefinition.id,
      host?.querySelector("input:checked")?.value || "",
    ];
  }));
}

export function hydrateQuestionnaireTechnicalChoices({
  container,
  axes = [],
  values = {},
  dataAttribute = "data-technical-axis",
  normalizeChoice = (_axisDefinition, value) => value || "",
} = {}) {
  const safeDataAttribute = technicalDataAttribute(dataAttribute);
  axes.forEach((axisDefinition) => {
    const host = container?.querySelector(
      `[${safeDataAttribute}="${axisDefinition.id}"]`,
    );
    const selectedValue = normalizeChoice(
      axisDefinition,
      values?.[axisDefinition.id],
    );
    Array.from(host?.querySelectorAll('input[type="radio"]') || [])
      .forEach((input) => {
        input.checked = input.value === selectedValue;
      });
  });
}

export function validateQuestionnaireTechnicalChoices({
  container,
  dataAttribute = "data-technical-axis",
} = {}) {
  const safeDataAttribute = technicalDataAttribute(dataAttribute);
  const missing = Array.from(
    container?.querySelectorAll(`[${safeDataAttribute}]`) || [],
  ).find((host) => !host.querySelector("input:checked"));
  return {
    ready: !missing,
    missingLabel: missing?.querySelector("h4")?.textContent?.trim() || "",
  };
}

export function validateQuestionnaireTechnicalCeiling({
  container,
  axes = [],
  dataAttribute = "data-technical-axis",
  roomHeightCm,
  minimumFinishedHeightCm,
  validatePreference,
} = {}) {
  if (typeof validatePreference !== "function") {
    throw new TypeError("validatePreference must be a function");
  }
  const axisDefinition = axes.find(
    (candidate) => candidate.id === "ceiling",
  );
  const values = readQuestionnaireTechnicalChoices({
    container,
    axes: axisDefinition ? [axisDefinition] : [],
    dataAttribute,
  });
  return validatePreference({
    axisDefinition,
    value: values.ceiling || "",
    roomHeightCm,
    minimumFinishedHeightCm,
  });
}

export function renderQuestionnaireAxisCustomApproach({
  axisLabel,
  customExample,
  existingNote = "",
} = {}) {
  const hasNote = Boolean(String(existingNote || "").trim());
  return `
    <details class="rp-axis-custom-approach">
      <summary>${hasNote ? "✎ 補充我的想法（已填）" : "＋ 補充我的想法（選填）"}</summary>
      <p class="rp-axis-custom-help">可補充 A／B 未涵蓋的做法，設計師會記錄進需求。</p>
      <label class="rp-question-note">
        <span class="sr-only">${escapeQuestionnaireHtml(axisLabel)}補充我的想法</span>
        <textarea rows="2" placeholder="${escapeQuestionnaireHtml(customExample)}"></textarea>
      </label>
    </details>
  `;
}

export function updateQuestionnaireAxisCustomApproach(details) {
  const summary = details?.querySelector("summary");
  const textarea = details?.querySelector("textarea");
  if (!summary || !textarea) return;
  summary.textContent = textarea.value.trim()
    ? "✎ 補充我的想法（已填）"
    : "＋ 補充我的想法（選填）";
}
