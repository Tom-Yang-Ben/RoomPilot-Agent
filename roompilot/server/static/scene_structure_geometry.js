function segmentLength(item) {
  if (!item?.start || !item?.end) return 0;
  return Math.hypot(
    Number(item.end.x || 0) - Number(item.start.x || 0),
    Number(item.end.y || 0) - Number(item.start.y || 0),
  );
}

function segmentRotation(item) {
  if (!item?.start || !item?.end) return Number(item?.rotation_deg || 0);
  return Math.atan2(
    Number(item.end.y || 0) - Number(item.start.y || 0),
    Number(item.end.x || 0) - Number(item.start.x || 0),
  ) * 180 / Math.PI;
}

export function validateColumnDimensionsCm({
  widthCm,
  depthCm,
  heightCm,
  maxWidthCm = Number.POSITIVE_INFINITY,
  maxDepthCm = Number.POSITIVE_INFINITY,
  maxHeightCm = Number.POSITIVE_INFINITY,
  centerXcm = null,
  centerYcm = null,
  rotationDeg = 0,
}) {
  if ([widthCm, depthCm, heightCm].some((value) => value === "" || value === null || value === undefined)) {
    return { valid: false, message: "請完整輸入柱寬、深度與高度。" };
  }
  const values = {
    widthCm: Number(widthCm),
    depthCm: Number(depthCm),
    heightCm: Number(heightCm),
  };
  if (Object.values(values).some((value) => !Number.isFinite(value))) {
    return { valid: false, message: "請完整輸入柱寬、深度與高度。" };
  }
  if (values.widthCm < 10 || values.depthCm < 10 || values.heightCm < 30) {
    return { valid: false, message: "柱寬與深度至少 10 公分，高度至少 30 公分。" };
  }
  const limits = {
    maxWidthCm: Number(maxWidthCm),
    maxDepthCm: Number(maxDepthCm),
    maxHeightCm: Number(maxHeightCm),
  };
  const centerX = Number(centerXcm);
  const centerY = Number(centerYcm);
  const hasFootprintContext = centerXcm !== null
    && centerYcm !== null
    && Number.isFinite(centerX)
    && Number.isFinite(centerY)
    && Number.isFinite(limits.maxWidthCm)
    && Number.isFinite(limits.maxDepthCm);
  if (
    values.heightCm > limits.maxHeightCm
    || (!hasFootprintContext && (
      values.widthCm > limits.maxWidthCm
      || values.depthCm > limits.maxDepthCm
    ))
  ) {
    return {
      valid: false,
      message: `柱寬不可超過 ${Math.round(limits.maxWidthCm)} 公分、深度不可超過 ${Math.round(limits.maxDepthCm)} 公分、高度不可超過 ${Math.round(limits.maxHeightCm)} 公分。`,
    };
  }
  if (hasFootprintContext) {
    const angle = Number(rotationDeg || 0) * Math.PI / 180;
    const cos = Math.abs(Math.cos(angle));
    const sin = Math.abs(Math.sin(angle));
    const halfExtentX = (values.widthCm * cos + values.depthCm * sin) / 2;
    const halfExtentY = (values.widthCm * sin + values.depthCm * cos) / 2;
    const epsilonCm = 1e-6;
    const outside = centerX - halfExtentX < -epsilonCm
      || centerX + halfExtentX > limits.maxWidthCm + epsilonCm
      || centerY - halfExtentY < -epsilonCm
      || centerY + halfExtentY > limits.maxDepthCm + epsilonCm;
    if (outside) {
      return {
        valid: false,
        message: "旋轉後柱體超出平面圖範圍，請縮小尺寸、調整方向或移動位置。",
      };
    }
  }
  return { valid: true, values };
}

export function columnGeometryDescriptor(
  item,
  { minimumDimensionM = 0.1, defaultHeightM = 2.7 } = {},
) {
  const widthM = Math.max(
    minimumDimensionM,
    Number(item?.size_m) || 0.35,
  );
  const depthM = Math.max(
    minimumDimensionM,
    Number(item?.depth_m) || Number(item?.size_m) || 0.35,
  );
  const heightM = Math.max(
    minimumDimensionM,
    Number(item?.height_m) || Number(defaultHeightM) || 2.7,
  );
  return {
    widthM,
    depthM,
    heightM,
    centerX: Number(item?.center?.x || 0),
    centerZ: Number(item?.center?.z ?? item?.center?.y ?? 0),
    centerHeightM: heightM / 2,
    rotationDeg: Number(item?.rotation_deg) || 0,
  };
}

export function structurePreviewDescriptor(
  item,
  kind,
  { ceilingHeightM = 2.7, planWidthM = 0, planDepthM = 0 } = {},
) {
  const safeCeilingHeight = Math.max(2.1, Number(ceilingHeightM) || 2.7);
  const centerX = kind === "column"
    ? Number(item?.center?.x || 0) - Number(planWidthM || 0) / 2
    : (Number(item?.start?.x || 0) + Number(item?.end?.x || 0)) / 2
      - Number(planWidthM || 0) / 2;
  const centerZ = kind === "column"
    ? Number(item?.center?.y ?? item?.center?.z ?? 0) - Number(planDepthM || 0) / 2
    : (Number(item?.start?.y ?? item?.start?.z ?? 0)
      + Number(item?.end?.y ?? item?.end?.z ?? 0)) / 2
      - Number(planDepthM || 0) / 2;
  if (kind === "beam") {
    const heightM = Math.max(0.1, Number(item?.height_m) || 0.35);
    return {
      kind,
      lengthM: Math.max(0.3, segmentLength(item)),
      widthM: Math.max(0.1, Number(item?.thickness_m) || 0.3),
      heightM,
      centerHeightM: safeCeilingHeight - heightM / 2,
      centerX,
      centerZ,
      rotationDeg: segmentRotation(item),
    };
  }
  if (kind === "column") {
    const column = columnGeometryDescriptor({
      ...item,
      center: { x: centerX, z: centerZ },
    }, {
      minimumDimensionM: 0.1,
      defaultHeightM: safeCeilingHeight,
    });
    return {
      kind,
      lengthM: column.widthM,
      widthM: column.depthM,
      heightM: column.heightM,
      centerHeightM: column.centerHeightM,
      centerX: column.centerX,
      centerZ: column.centerZ,
      rotationDeg: column.rotationDeg,
    };
  }
  return null;
}
