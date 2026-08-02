import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

async function loadArtifactTool() {
  try {
    return await import("@oai/artifact-tool");
  } catch (firstError) {
    const modulesRoot = String(process.env.ROOMPILOT_ARTIFACT_TOOL_MODULES || "").trim();
    if (!modulesRoot) {
      throw new Error(
        `@oai/artifact-tool is unavailable. Install it or set ROOMPILOT_ARTIFACT_TOOL_MODULES. ${firstError.message}`,
      );
    }
    const modulePath = path.join(
      modulesRoot,
      "@oai",
      "artifact-tool",
      "dist",
      "artifact_tool.mjs",
    );
    return import(pathToFileURL(modulePath).href);
  }
}

function columnName(index) {
  let value = index + 1;
  let result = "";
  while (value > 0) {
    value -= 1;
    result = String.fromCharCode(65 + (value % 26)) + result;
    value = Math.floor(value / 26);
  }
  return result;
}

function writeRows(sheet, startRow, rows) {
  if (!rows.length) return;
  const columns = Math.max(...rows.map((row) => row.length));
  const normalized = rows.map((row) => [
    ...row,
    ...Array(Math.max(0, columns - row.length)).fill(null),
  ]);
  sheet.getRangeByIndexes(startRow - 1, 0, normalized.length, columns).values = normalized;
}

function styleTitle(sheet, lastColumn) {
  const range = sheet.getRange(`A1:${lastColumn}1`);
  range.merge();
  range.format = {
    fill: "#335F47",
    font: { bold: true, color: "#FFFFFF", size: 18 },
    verticalAlignment: "center",
  };
  range.format.rowHeight = 32;
}

function styleHeader(sheet, row, lastColumn) {
  const range = sheet.getRange(`A${row}:${lastColumn}${row}`);
  range.format = {
    fill: "#DCE9E0",
    font: { bold: true, color: "#253127" },
    wrapText: true,
    verticalAlignment: "center",
    borders: { preset: "all", style: "thin", color: "#BAC7BE" },
  };
  range.format.rowHeight = 30;
}

function setColumnWidths(sheet, endRow, widths) {
  widths.forEach((width, index) => {
    const column = columnName(index);
    sheet.getRange(`${column}1:${column}${endRow}`).format.columnWidth = width;
  });
}

const [inputPath, outputPath, ...flags] = process.argv.slice(2);
if (!inputPath || !outputPath) {
  throw new Error("usage: node workbook_builder.mjs report.json output.xlsx [--preview-dir=...] [--inspect-path=...]");
}
const previewFlag = flags.find((item) => item.startsWith("--preview-dir="));
const inspectFlag = flags.find((item) => item.startsWith("--inspect-path="));
const previewDir = previewFlag ? previewFlag.slice("--preview-dir=".length) : "";
const inspectPath = inspectFlag ? inspectFlag.slice("--inspect-path=".length) : "";
const report = JSON.parse(await fs.readFile(inputPath, "utf8"));
const { SpreadsheetFile, Workbook } = await loadArtifactTool();
const workbook = Workbook.create();

const estimate = workbook.worksheets.add("工程估價");
estimate.showGridLines = false;
const estimateHeaders = [
  "房間ID", "工種", "工項編碼", "工項名稱", "原始量", "損耗率", "計價量", "單位",
  "材料單價", "人工單價", "其他單價", "小計", "狀態", "價格地區", "價格日期", "來源", "信心",
];
writeRows(estimate, 1, [
  ["RoomPilot 初步工程估價"],
  ["專案ID", report.project_id, null, "版本", report.revision],
  ["產生時間", `UTC ${report.generated_at}`, null, "幣別", report.estimate.currency],
  ["已知小計", report.estimate.known_subtotal, null, "待詢價工項", report.estimate.pending_quote_count],
  [`重要聲明：${report.estimate.disclaimer}`],
  [],
  estimateHeaders,
]);
styleTitle(estimate, "Q");
estimate.getRange("B2:C2").merge();
estimate.getRange("B3:C3").merge();
estimate.getRange("B4:C4").merge();
estimate.getRange("A5:Q5").merge();
estimate.getRange("A5:Q5").format = {
  fill: report.demo_mode ? "#FFF0A8" : "#F3F5F2",
  font: { bold: true, color: report.demo_mode ? "#9A1F1F" : "#59635B" },
  wrapText: true,
};
estimate.getRange("A2:E4").format.wrapText = true;
estimate.getRange("A2:E4").format.rowHeight = 24;
styleHeader(estimate, 7, "Q");
const estimateStart = 8;
const estimateRows = report.estimate.lines.map((line) => [
  line.room_id, line.trade, line.work_item_code, line.name, line.raw_quantity, line.waste_rate,
  null, line.unit, line.material_unit_price, line.labor_unit_price, line.other_unit_price,
  null, line.status, line.price_region, line.price_effective_date, line.price_source, line.confidence,
]);
writeRows(estimate, estimateStart, estimateRows);
const estimateEnd = Math.max(estimateStart, estimateStart + estimateRows.length - 1);
if (estimateRows.length) {
  estimate.getRange(`G${estimateStart}`).formulas = [[`=E${estimateStart}*(1+F${estimateStart})`]];
  estimate.getRange(`G${estimateStart}:G${estimateEnd}`).fillDown();
  estimate.getRange(`L${estimateStart}`).formulas = [[
    `=IF(COUNT(I${estimateStart}:K${estimateStart})=3,G${estimateStart}*SUM(I${estimateStart}:K${estimateStart}),"")`,
  ]];
  estimate.getRange(`L${estimateStart}:L${estimateEnd}`).fillDown();
  estimate.getRange(`A${estimateStart}:Q${estimateEnd}`).format.borders = {
    preset: "all", style: "thin", color: "#E0E5E1",
  };
  estimate.getRange(`E${estimateStart}:E${estimateEnd}`).format.numberFormat = "#,##0.00";
  estimate.getRange(`F${estimateStart}:F${estimateEnd}`).format.numberFormat = "0.0%";
  estimate.getRange(`G${estimateStart}:L${estimateEnd}`).format.numberFormat = "#,##0.00";
  estimate.getRange(`M${estimateStart}:M${estimateEnd}`).conditionalFormats.add(
    "containsText",
    { text: "pending_quote", format: { fill: "#FFF0A8", font: { color: "#9A1F1F", bold: true } } },
  );
}
const estimateTotalRow = estimateEnd + 2;
writeRows(estimate, estimateTotalRow, [["公式已知小計"]]);
estimate.getRange(`L${estimateTotalRow}`).formulas = [[
  estimateRows.length ? `=SUM(L${estimateStart}:L${estimateEnd})` : "=0",
]];
estimate.getRange(`A${estimateTotalRow}:Q${estimateTotalRow}`).format = {
  fill: "#EEF3EF", font: { bold: true }, borders: { preset: "doubleBottom", style: "thin", color: "#335F47" },
};
estimate.getRange(`L${estimateTotalRow}`).format.numberFormat = "#,##0.00";
estimate.freezePanes.freezeRows(7);
setColumnWidths(estimate, estimateTotalRow, [14, 13, 21, 26, 11, 10, 11, 9, 12, 12, 12, 14, 18, 14, 14, 34, 10]);
estimate.getRange(`A1:Q${estimateTotalRow}`).format.wrapText = true;

const schedule = workbook.worksheets.add("初步排程");
schedule.showGridLines = false;
const scheduleHeaders = [
  "Task ID", "房間ID", "工項編碼", "工作", "工程量", "單位", "日產能", "工班",
  "準備日", "施工日", "等待日", "總工日", "開始日", "完成日", "前置 Task", "狀態", "來源", "信心",
];
writeRows(schedule, 1, [
  ["RoomPilot 初步工程排程"],
  ["專案ID", report.project_id, null, "版本", report.revision],
  ["預估總工期(日)", report.schedule.estimated_total_days, null, "資料不足項目", report.schedule.unknown_duration_count],
  [`重要聲明：${report.schedule.disclaimer}`],
  [],
  scheduleHeaders,
]);
styleTitle(schedule, "R");
schedule.getRange("B2:C2").merge();
schedule.getRange("B3:C3").merge();
schedule.getRange("A4:R4").merge();
schedule.getRange("A4:R4").format = {
  fill: report.demo_mode ? "#FFF0A8" : "#F3F5F2",
  font: { bold: true, color: report.demo_mode ? "#9A1F1F" : "#59635B" },
  wrapText: true,
};
schedule.getRange("A2:E3").format.wrapText = true;
schedule.getRange("A2:E3").format.rowHeight = 24;
styleHeader(schedule, 6, "R");
const scheduleStart = 7;
const scheduleRows = report.schedule.tasks.map((task) => [
  task.task_id, task.room_id, task.work_item_code, task.name, task.quantity, task.unit,
  task.daily_productivity, task.crew_count, task.preparation_days, task.construction_days,
  task.waiting_days, null, task.start_day, null, task.predecessor_task_ids.join(", "),
  task.status, task.source, task.confidence,
]);
writeRows(schedule, scheduleStart, scheduleRows);
const scheduleEnd = Math.max(scheduleStart, scheduleStart + scheduleRows.length - 1);
if (scheduleRows.length) {
  schedule.getRange(`L${scheduleStart}`).formulas = [[
    `=IF(J${scheduleStart}="","",SUM(I${scheduleStart}:K${scheduleStart}))`,
  ]];
  schedule.getRange(`L${scheduleStart}:L${scheduleEnd}`).fillDown();
  schedule.getRange(`N${scheduleStart}`).formulas = [[
    `=IF(OR(M${scheduleStart}="",L${scheduleStart}=""),"",M${scheduleStart}+L${scheduleStart}-1)`,
  ]];
  schedule.getRange(`N${scheduleStart}:N${scheduleEnd}`).fillDown();
  schedule.getRange(`A${scheduleStart}:R${scheduleEnd}`).format.borders = {
    preset: "all", style: "thin", color: "#E0E5E1",
  };
  schedule.getRange(`E${scheduleStart}:N${scheduleEnd}`).format.numberFormat = "#,##0.00";
  schedule.getRange(`P${scheduleStart}:P${scheduleEnd}`).conditionalFormats.add(
    "containsText",
    { text: "productivity_data_missing", format: { fill: "#FFF0A8", font: { color: "#9A1F1F", bold: true } } },
  );
}
schedule.freezePanes.freezeRows(6);
setColumnWidths(schedule, scheduleEnd, [31, 14, 21, 26, 11, 9, 11, 9, 10, 10, 10, 10, 10, 10, 35, 28, 38, 10]);
schedule.getRange(`A1:R${scheduleEnd}`).format.wrapText = true;

// 家具採購與工程施工費刻意分成兩張表：一個是買家具的錢，一個是施工的錢，
// 放同一張會讓屋主把兩種預算加成一個看起來很嚇人的數字。
const furnitureEstimate = report.furniture_estimate || { lines: [] };
const furniture = workbook.worksheets.add("家具採購");
furniture.showGridLines = false;
const furnitureHeaders = [
  "空間", "品項", "分類", "型錄ID", "寬(cm)", "深(cm)", "高(cm)",
  "數量", "單價(TWD)", "小計(TWD)", "狀態", "推估價", "價格來源", "信心",
];
writeRows(furniture, 1, [
  ["RoomPilot 家具採購明細"],
  ["專案ID", report.project_id, null, "版本", report.revision],
  ["已知小計", furnitureEstimate.known_subtotal_twd || 0, null, "待詢價品項", furnitureEstimate.unpriced_count || 0],
  ["型錄來源", furnitureEstimate.catalog_provider || "unknown", null, "推估價品項", furnitureEstimate.estimated_price_count || 0],
  [`重要聲明：${furnitureEstimate.disclaimer || ""}`],
  [],
  furnitureHeaders,
]);
styleTitle(furniture, "N");
furniture.getRange("B2:C2").merge();
furniture.getRange("B3:C3").merge();
furniture.getRange("B4:C4").merge();
furniture.getRange("A5:N5").merge();
furniture.getRange("A5:N5").format = {
  fill: "#F3F5F2",
  font: { bold: true, color: "#59635B" },
  wrapText: true,
};
furniture.getRange("A2:E4").format.wrapText = true;
styleHeader(furniture, 7, "N");
const furnitureStart = 8;
const furnitureRows = (furnitureEstimate.lines || []).map((line) => [
  line.room_name, line.name, line.category, line.catalog_furniture_id,
  line.width_cm, line.depth_cm, line.height_cm, line.quantity,
  line.unit_price_twd, null, line.status,
  line.price_is_estimated ? "是" : "否", line.price_source, line.confidence,
]);
writeRows(furniture, furnitureStart, furnitureRows);
const furnitureEnd = Math.max(furnitureStart, furnitureStart + furnitureRows.length - 1);
if (furnitureRows.length) {
  // 查無單價時小計留空，不能變成 0——0 會被當成「免費」而不是「未知」。
  furniture.getRange(`J${furnitureStart}`).formulas = [[
    `=IF(I${furnitureStart}="","",I${furnitureStart}*H${furnitureStart})`,
  ]];
  furniture.getRange(`J${furnitureStart}:J${furnitureEnd}`).fillDown();
  furniture.getRange(`A${furnitureStart}:N${furnitureEnd}`).format.borders = {
    preset: "all", style: "thin", color: "#E0E5E1",
  };
  furniture.getRange(`E${furnitureStart}:G${furnitureEnd}`).format.numberFormat = "#,##0";
  furniture.getRange(`I${furnitureStart}:J${furnitureEnd}`).format.numberFormat = "#,##0";
  furniture.getRange(`K${furnitureStart}:K${furnitureEnd}`).conditionalFormats.add(
    "containsText",
    { text: "price_unavailable", format: { fill: "#FFF0A8", font: { color: "#9A1F1F", bold: true } } },
  );
}
const furnitureTotalRow = furnitureEnd + 2;
writeRows(furniture, furnitureTotalRow, [["公式已知小計"]]);
furniture.getRange(`J${furnitureTotalRow}`).formulas = [[
  furnitureRows.length ? `=SUM(J${furnitureStart}:J${furnitureEnd})` : "=0",
]];
furniture.getRange(`A${furnitureTotalRow}:N${furnitureTotalRow}`).format = {
  fill: "#EEF3EF", font: { bold: true },
  borders: { preset: "doubleBottom", style: "thin", color: "#335F47" },
};
furniture.getRange(`J${furnitureTotalRow}`).format.numberFormat = "#,##0";
furniture.freezePanes.freezeRows(7);
setColumnWidths(furniture, furnitureTotalRow, [16, 32, 16, 34, 10, 10, 10, 8, 13, 14, 18, 10, 22, 10]);
furniture.getRange(`A1:N${furnitureTotalRow}`).format.wrapText = true;

const designNarrative = report.design_narrative || {};
const design = workbook.worksheets.add("設計語彙");
design.showGridLines = false;
const joinList = (items) => (Array.isArray(items) && items.length ? items.join("、") : "—");
const color = designNarrative.color || {};
const material = designNarrative.material || {};
const designRows = [
  ["RoomPilot 設計風格與語彙"],
  ["風格", designNarrative.style_name_zh || "未設定", null, "風格ID", designNarrative.style_id || "—"],
  ["判定方式", designNarrative.style_resolution_zh || "—"],
  [`可信度聲明：${designNarrative.disclaimer_zh || ""}`],
  [],
  ["項目", "內容"],
  ["風格定位", designNarrative.positioning_zh || "—"],
  ["造型語言", designNarrative.design_language_zh || "—"],
  ["代表元素", joinList(designNarrative.signature_elements_zh)],
  ["照明手法", designNarrative.lighting_approach_zh || "—"],
  ["應避免", joinList(designNarrative.avoid_zh)],
  ["色票", joinList((color.roles || []).map((role) => `${role.hex}（${role.role}）`))],
  ["色票來源", color.palette_source_detail || "—"],
  ["色溫", color.temperature_zh || "—"],
  ["明度對比", color.value_contrast_zh || "—"],
  ["本案選用材質", joinList(material.selected_materials_zh)],
  ["風格建議主材", joinList(material.primary_materials_zh)],
  ["表面處理", material.finish_rule_zh || "—"],
  ["對比邏輯", material.contrast_logic_zh || "—"],
  [],
  ["空間", "家具配置（快照事實）", "設計重點", "動線", "照明", "收納"],
];
for (const room of designNarrative.rooms || []) {
  designRows.push([
    `${room.room_name}（${room.room_name_zh || room.room_type}）`,
    room.furniture_summary_zh || "—",
    room.design_focus_zh || "—",
    room.circulation_zh || "—",
    room.lighting_zh || "—",
    room.storage_zh || "—",
  ]);
}
designRows.push([]);
designRows.push(["來源", "範圍", "信心", "備註"]);
for (const item of designNarrative.evidence || []) {
  designRows.push([item.source_id, item.scope, item.confidence, item.caveat_zh || ""]);
}
writeRows(design, 1, designRows);
styleTitle(design, "F");
design.getRange("A4:F4").merge();
design.getRange("A4:F4").format = {
  fill: "#F3F5F2", font: { bold: true, color: "#59635B" }, wrapText: true,
};
styleHeader(design, 6, "B");
const designRoomHeaderRow = 21;
styleHeader(design, designRoomHeaderRow, "F");
const designEnd = designRows.length;
setColumnWidths(design, designEnd, [26, 46, 46, 40, 40, 34]);
design.getRange(`A1:F${designEnd}`).format.wrapText = true;

if (previewDir) {
  await fs.mkdir(previewDir, { recursive: true });
  for (const sheetName of ["工程估價", "初步排程", "家具採購", "設計語彙"]) {
    const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
    const fileName = {
      "工程估價": "estimate-preview.png",
      "初步排程": "schedule-preview.png",
      "家具採購": "furniture-preview.png",
      "設計語彙": "design-preview.png",
    }[sheetName];
    await fs.writeFile(path.join(previewDir, fileName), new Uint8Array(await preview.arrayBuffer()));
  }
}

if (inspectPath) {
  const inspections = [];
  inspections.push((await workbook.inspect({ kind: "sheet", include: "id,name", maxChars: 3000 })).ndjson);
  inspections.push((await workbook.inspect({ kind: "region", sheetId: "工程估價", range: `A1:Q${Math.min(estimateTotalRow, 18)}`, maxChars: 7000 })).ndjson);
  inspections.push((await workbook.inspect({ kind: "formula", sheetId: "工程估價", range: `A1:Q${estimateTotalRow}`, maxChars: 5000 })).ndjson);
  inspections.push((await workbook.inspect({ kind: "region", sheetId: "初步排程", range: `A1:R${Math.min(scheduleEnd, 18)}`, maxChars: 7000 })).ndjson);
  inspections.push((await workbook.inspect({ kind: "formula", sheetId: "初步排程", range: `A1:R${scheduleEnd}`, maxChars: 5000 })).ndjson);
  inspections.push((await workbook.inspect({ kind: "region", sheetId: "家具採購", range: `A1:N${Math.min(furnitureTotalRow, 18)}`, maxChars: 7000 })).ndjson);
  inspections.push((await workbook.inspect({ kind: "formula", sheetId: "家具採購", range: `A1:N${furnitureTotalRow}`, maxChars: 5000 })).ndjson);
  const errorPattern = /#REF!|#DIV\/0!|#VALUE!|#NAME\?|#N\/A/g;
  const errors = inspections.flatMap((item) => String(item || "").match(errorPattern) || []);
  await fs.writeFile(inspectPath, `${inspections.join("\n")}\nFORMULA_ERRORS=${JSON.stringify(errors)}\n`, "utf8");
  if (errors.length) throw new Error(`formula errors detected: ${errors.join(", ")}`);
}

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
