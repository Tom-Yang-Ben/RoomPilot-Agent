/**
 * @oai/artifact-tool 本機相容層（backed by exceljs）。
 *
 * 真品是私有套件（公開 npm 404、所有遠端分支皆無），只存在部分隊友機器上。
 * tests/test_engineering_documents_api.py 的 XLSX 斷言已明示接受
 * 「@oai/artifact-tool 與本機相容層」兩種 writer，內容契約不綁序列化實作。
 *
 * 這裡只實作 backend/server/engineering/workbook_builder.mjs 實際用到的 API：
 * Workbook.create / worksheets.add / getRange / getRangeByIndexes /
 * freezePanes.freezeRows / showGridLines / values / formulas / fillDown /
 * merge / format（指派與逐屬性）/ conditionalFormats.add("containsText") /
 * SpreadsheetFile.exportXlsx().save。
 *
 * render() 與 inspect() 只在 --preview-dir / --inspect-path 旗標下使用，
 * DocumentService 不會傳；相容層明話拒絕而不是輸出假預覽。
 */
import ExcelJS from "exceljs";

function columnToNumber(letters) {
  let value = 0;
  for (const letter of letters) {
    value = value * 26 + (letter.charCodeAt(0) - 64);
  }
  return value;
}

function parseA1(reference) {
  const match = /^([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?$/.exec(reference.trim());
  if (!match) throw new Error(`unsupported range reference: ${reference}`);
  const r1 = Number(match[2]);
  const c1 = columnToNumber(match[1]);
  const r2 = match[4] ? Number(match[4]) : r1;
  const c2 = match[3] ? columnToNumber(match[3]) : c1;
  return { r1, c1, r2, c2 };
}

function argb(hex) {
  const clean = String(hex || "").replace("#", "").toUpperCase();
  return { argb: clean.length === 6 ? `FF${clean}` : clean };
}

function mergeView(worksheet, patch) {
  const current = (worksheet.views && worksheet.views[0]) || {};
  worksheet.views = [{ ...current, ...patch }];
}

class RangeShim {
  constructor(worksheet, bounds, reference) {
    this._ws = worksheet;
    this._b = bounds;
    this._ref = reference
      || `${this._colName(bounds.c1)}${bounds.r1}:${this._colName(bounds.c2)}${bounds.r2}`;
  }

  _colName(index) {
    let value = index;
    let result = "";
    while (value > 0) {
      value -= 1;
      result = String.fromCharCode(65 + (value % 26)) + result;
      value = Math.floor(value / 26);
    }
    return result;
  }

  _eachCell(callback) {
    for (let r = this._b.r1; r <= this._b.r2; r += 1) {
      const row = this._ws.getRow(r);
      for (let c = this._b.c1; c <= this._b.c2; c += 1) {
        callback(row.getCell(c), r, c);
      }
    }
  }

  set values(rows) {
    rows.forEach((rowValues, rowIndex) => {
      const row = this._ws.getRow(this._b.r1 + rowIndex);
      rowValues.forEach((value, colIndex) => {
        if (value === null || value === undefined) return;
        row.getCell(this._b.c1 + colIndex).value = value;
      });
    });
  }

  set formulas(rows) {
    rows.forEach((rowValues, rowIndex) => {
      const row = this._ws.getRow(this._b.r1 + rowIndex);
      rowValues.forEach((formula, colIndex) => {
        if (formula === null || formula === undefined) return;
        row.getCell(this._b.c1 + colIndex).value = {
          formula: String(formula).replace(/^=/, ""),
        };
      });
    });
  }

  fillDown() {
    for (let c = this._b.c1; c <= this._b.c2; c += 1) {
      const anchor = this._ws.getRow(this._b.r1).getCell(c).value;
      const formula = anchor && typeof anchor === "object" ? anchor.formula : null;
      if (!formula) continue;
      for (let r = this._b.r1 + 1; r <= this._b.r2; r += 1) {
        const offset = r - this._b.r1;
        const shifted = formula.replace(
          /([A-Z]{1,3})(\d+)/g,
          (whole, col, rowNumber) => `${col}${Number(rowNumber) + offset}`,
        );
        this._ws.getRow(r).getCell(c).value = { formula: shifted };
      }
    }
  }

  merge() {
    this._ws.mergeCells(this._b.r1, this._b.c1, this._b.r2, this._b.c2);
  }

  _applyFormat(props) {
    for (const [key, value] of Object.entries(props)) {
      if (value === undefined || value === null) continue;
      if (key === "rowHeight") {
        for (let r = this._b.r1; r <= this._b.r2; r += 1) {
          this._ws.getRow(r).height = value;
        }
      } else if (key === "columnWidth") {
        for (let c = this._b.c1; c <= this._b.c2; c += 1) {
          this._ws.getColumn(c).width = value;
        }
      } else if (key === "fill") {
        this._eachCell((cell) => {
          cell.fill = { type: "pattern", pattern: "solid", fgColor: argb(value) };
        });
      } else if (key === "font") {
        this._eachCell((cell) => {
          const font = { ...(cell.font || {}) };
          if (value.bold !== undefined) font.bold = value.bold;
          if (value.size !== undefined) font.size = value.size;
          if (value.color !== undefined) font.color = argb(value.color);
          cell.font = font;
        });
      } else if (key === "wrapText") {
        this._eachCell((cell) => {
          cell.alignment = { ...(cell.alignment || {}), wrapText: Boolean(value) };
        });
      } else if (key === "verticalAlignment") {
        this._eachCell((cell) => {
          cell.alignment = { ...(cell.alignment || {}), vertical: String(value) };
        });
      } else if (key === "numberFormat") {
        this._eachCell((cell) => {
          cell.numFmt = String(value);
        });
      } else if (key === "borders") {
        const edge = { style: value.style || "thin", color: argb(value.color || "#000000") };
        this._eachCell((cell) => {
          if (value.preset === "doubleBottom") {
            cell.border = { ...(cell.border || {}), bottom: { ...edge, style: "double" } };
          } else {
            cell.border = { top: edge, left: edge, bottom: edge, right: edge };
          }
        });
      }
      // 其餘屬性（builder 未使用）靜默略過會藏問題：明話丟出。
      else {
        throw new Error(`local artifact-tool compat: unsupported format key "${key}"`);
      }
    }
  }

  set format(props) {
    this._applyFormat(props);
  }

  get format() {
    const target = this;
    return new Proxy({}, {
      set(_object, property, value) {
        target._applyFormat({ [property]: value });
        return true;
      },
    });
  }

  get conditionalFormats() {
    const target = this;
    return {
      add(kind, options) {
        if (kind !== "containsText") {
          throw new Error(`local artifact-tool compat: unsupported conditional format "${kind}"`);
        }
        const style = {};
        if (options.format?.fill) {
          style.fill = { type: "pattern", pattern: "solid", bgColor: argb(options.format.fill) };
        }
        if (options.format?.font) {
          style.font = {
            ...(options.format.font.bold !== undefined ? { bold: options.format.font.bold } : {}),
            ...(options.format.font.color ? { color: argb(options.format.font.color) } : {}),
          };
        }
        target._ws.addConditionalFormatting({
          ref: target._ref,
          rules: [{
            type: "containsText",
            operator: "containsText",
            text: options.text,
            priority: (target._ws.conditionalFormattings?.length || 0) + 1,
            style,
          }],
        });
      },
    };
  }
}

class SheetShim {
  constructor(worksheet) {
    this._ws = worksheet;
  }

  set showGridLines(value) {
    mergeView(this._ws, { showGridLines: Boolean(value) });
  }

  get freezePanes() {
    const worksheet = this._ws;
    return {
      freezeRows(count) {
        mergeView(worksheet, { state: "frozen", ySplit: count });
      },
    };
  }

  getRange(reference) {
    return new RangeShim(this._ws, parseA1(reference), reference.trim());
  }

  getRangeByIndexes(rowIndex, columnIndex, rowCount, columnCount) {
    return new RangeShim(this._ws, {
      r1: rowIndex + 1,
      c1: columnIndex + 1,
      r2: rowIndex + rowCount,
      c2: columnIndex + columnCount,
    });
  }
}

class WorkbookShim {
  constructor() {
    this._wb = new ExcelJS.Workbook();
    this.worksheets = {
      add: (name) => new SheetShim(this._wb.addWorksheet(name)),
    };
  }

  async render() {
    throw new Error(
      "local artifact-tool compat layer does not support render(); "
      + "install the real @oai/artifact-tool for sheet previews",
    );
  }

  async inspect() {
    throw new Error(
      "local artifact-tool compat layer does not support inspect(); "
      + "install the real @oai/artifact-tool for workbook inspection",
    );
  }
}

export const Workbook = {
  create() {
    return new WorkbookShim();
  },
};

export const SpreadsheetFile = {
  async exportXlsx(workbook) {
    return {
      async save(outputPath) {
        await workbook._wb.xlsx.writeFile(outputPath);
      },
    };
  },
};
