import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = new URL("../", import.meta.url).pathname;
const dataPath = `${root}analysis/data/metro-head-office-2004-2024.csv`;
const resultsPath = `${root}analysis/data/metro-head-office-20y-results.json`;
const outputDir = `${root}outputs/metro-debt-20y-20260817`;
const outputPath = `${outputDir}/metro-debt-head-office-2004-2024-audit.xlsx`;

const csvText = await fs.readFile(dataPath, "utf8");
const results = JSON.parse(await fs.readFile(resultsPath, "utf8"));
const lines = csvText.trim().split(/\r?\n/);
const headers = lines[0].split(",");
const records = lines.slice(1).map((line) => {
  const fields = line.split(",");
  return Object.fromEntries(headers.map((header, index) => [header, fields[index]]));
});

const workbook = Workbook.create();
const summary = workbook.worksheets.add("요약");
const raw = workbook.worksheets.add("원자료");
const calc = workbook.worksheets.add("계산");
const models = workbook.worksheets.add("모형결과");
const sources = workbook.worksheets.add("출처·검증");

const colors = {
  navy: "#17324D",
  blue: "#2563EB",
  green: "#0F766E",
  orange: "#D97706",
  gray: "#F3F4F6",
  midGray: "#D1D5DB",
  darkGray: "#4B5563",
  white: "#FFFFFF",
  paleBlue: "#EAF2F8",
  paleGreen: "#E8F5F0",
  paleOrange: "#FFF3E6",
};

function title(sheet, range, text) {
  const cellRange = sheet.getRange(range);
  cellRange.merge();
  cellRange.values = [[text]];
  cellRange.format = {
    fill: colors.navy,
    font: { bold: true, color: colors.white, size: 18 },
    verticalAlignment: "center",
  };
  cellRange.format.rowHeight = 34;
}

function section(sheet, range, text) {
  const cellRange = sheet.getRange(range);
  cellRange.merge();
  cellRange.values = [[text]];
  cellRange.format = {
    fill: colors.paleBlue,
    font: { bold: true, color: colors.navy },
    borders: { preset: "bottom", style: "medium", color: colors.navy },
  };
  cellRange.format.rowHeight = 24;
}

function headerStyle(range) {
  range.format = {
    fill: colors.navy,
    font: { bold: true, color: colors.white },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "bottom", style: "medium", color: colors.navy },
  };
  range.format.rowHeight = 30;
}

function lightBorders(range) {
  range.format.borders = { preset: "inside", style: "thin", color: colors.midGray };
}

// Summary sheet.
summary.showGridLines = false;
title(summary, "A1:H1", "7개 광역단체 본청 지방채 20년 분석");
summary.getRange("A2:H2").merge();
summary.getRange("A2:H2").values = [[
  "2004~2024년 결산 · 2005~2024년 증가율 · 행정안전부 지방재정365 공개 API",
]];
summary.getRange("A2:H2").format = {
  font: { color: colors.darkGray, italic: true },
  wrapText: true,
};

section(summary, "A4:H4", "핵심 추정치 — 명목 지방채 증가율 변화");
summary.getRange("A5:E5").values = [["요인", "추정치(%p)", "95% 하한", "95% 상한", "해석 단위"]];
headerStyle(summary.getRange("A5:E5"));
const driverLabels = [
  ["코로나 대응기", "covid", "2020~2021년"],
  ["금융위기 대응기", "gfc", "2009~2010년"],
  ["지방세 증가율 하락", "tax_slowdown_z", "1표준편차(7.9%p)"],
  ["민주계 재임", "democratic", "보수계 대비"],
  ["자본지출 비중 상승", "capital_share_z", "1표준편차(7.6%p)"],
];
summary.getRange("A6:A10").values = driverLabels.map(([label]) => [label]);
summary.getRange("E6:E10").values = driverLabels.map(([, , unit]) => [unit]);
summary.getRange("B6:D10").formulas = driverLabels.map(([, key], index) => {
  const row = 5 + index;
  return [`='모형결과'!B${row}`, `='모형결과'!C${row}`, `='모형결과'!D${row}`];
});
summary.getRange("B6:D10").format.font = { color: "#008000" };
summary.getRange("B6:D10").format.numberFormat = "+0.0;-0.0;0.0";
summary.getRange("A6:E10").format.rowHeight = 24;
lightBorders(summary.getRange("A6:E10"));
summary.getRange("A6:E6").format.fill = colors.paleGreen;
summary.getRange("A7:E7").format.fill = colors.paleOrange;

section(summary, "A12:H12", "단순 평균과 진영 추정치");
summary.getRange("A13:D13").values = [["비교", "민주계", "보수계", "격차(민주-보수)"]];
headerStyle(summary.getRange("A13:D13"));
const desc = results.descriptive;
summary.getRange("A14:D16").values = [
  ["2005~2024 당해 연도 귀속", desc.party_current.democratic_mean, desc.party_current.conservative_mean, desc.party_current.gap_democratic_minus_conservative],
  ["2005~2014 당해 연도 귀속", desc.first_decade_current.democratic_mean, desc.first_decade_current.conservative_mean, desc.first_decade_current.gap_democratic_minus_conservative],
  ["2015~2024 당해 연도 귀속", desc.second_decade_current.democratic_mean, desc.second_decade_current.conservative_mean, desc.second_decade_current.gap_democratic_minus_conservative],
];
summary.getRange("B14:D16").format.numberFormat = "0.0";
lightBorders(summary.getRange("A14:D16"));
summary.getRange("F13:H13").values = [["지역·연도 통제", "추정치(%p)", "95% 범위"]];
headerStyle(summary.getRange("F13:H13"));
summary.getRange("F14:F15").values = [["당해 연도 귀속"], ["1년 시차 귀속"]];
summary.getRange("G14:G15").formulas = [["='모형결과'!B22"], ["='모형결과'!B23"]];
summary.getRange("H14:H15").values = [
  [`${results.models.party_year_fe_current.estimates.democratic.ci95_t6[0].toFixed(1)} ~ ${results.models.party_year_fe_current.estimates.democratic.ci95_t6[1].toFixed(1)}`],
  [`${results.models.party_year_fe_lagged.estimates.democratic.ci95_t6[0].toFixed(1)} ~ ${results.models.party_year_fe_lagged.estimates.democratic.ci95_t6[1].toFixed(1)}`],
];
summary.getRange("G14:G15").format.font = { color: "#008000" };
summary.getRange("G14:G15").format.numberFormat = "+0.0;-0.0;0.0";
lightBorders(summary.getRange("F14:H15"));

section(summary, "A18:H18", "읽는 법");
summary.getRange("A19:H22").merge();
summary.getRange("A19:H22").values = [[
  "위기·세수·자본지출·진영을 한 모형에 넣고 지역 고정효과와 선형 추세를 통제했습니다. " +
  "추정치는 인과효과가 아니라 조건부 연관성입니다. 7개 지역뿐이므로 신뢰구간은 지역 군집 표준오차와 자유도 6의 t 임계값으로 계산했습니다. " +
  "초록색 숫자는 다른 시트의 계산 결과를 참조합니다.",
]];
summary.getRange("A19:H22").format = { wrapText: true, verticalAlignment: "top", fill: colors.gray };
summary.getRange("A19:H22").format.rowHeight = 24;
summary.getRange("A1:H24").format.font.name = "Arial";
summary.getRange("A1:A24").format.columnWidth = 28;
summary.getRange("B1:D24").format.columnWidth = 16;
summary.getRange("E1:E24").format.columnWidth = 22;
summary.getRange("F1:F24").format.columnWidth = 22;
summary.getRange("G1:G24").format.columnWidth = 15;
summary.getRange("H1:H24").format.columnWidth = 22;
summary.freezePanes.freezeRows(2);

// Raw source sheet.
raw.showGridLines = false;
const rawHeaders = [
  "지역", "단체코드", "연도", "일반회계 지방채(원)", "기타특별회계(원)",
  "공기업특별회계(원)", "기금회계(원)", "지방채 합계(원)", "순계 세입(원)",
  "지방세 수입(원)", "성질별 분류 세출(원)", "자본지출(원)",
  "채무/세입(%)", "자본지출 비중(%)", "출처",
];
raw.getRange(`A1:O1`).values = [rawHeaders];
headerStyle(raw.getRange("A1:O1"));
const rawValues = records.map((record) => [
  record.city,
  record.laf_cd,
  Number(record.year),
  Number(record.debt_general_won),
  Number(record.debt_other_special_won),
  Number(record.debt_public_enterprise_won),
  Number(record.debt_fund_won),
  Number(record.debt_total_won),
  Number(record.revenue_net_won),
  Number(record.local_tax_won),
  Number(record.classified_expenditure_won),
  Number(record.capital_outlay_won),
  Number(record.debt_to_revenue_pct),
  Number(record.capital_share_pct),
  "LOFIN ACCAM/FIACRV/SDSCF",
]);
raw.getRange(`A2:O${rawValues.length + 1}`).values = rawValues;
raw.getRange(`A2:O${rawValues.length + 1}`).format.font = { color: colors.blue };
raw.getRange(`D2:L${rawValues.length + 1}`).format.numberFormat = "#,##0";
raw.getRange(`M2:N${rawValues.length + 1}`).format.numberFormat = "0.00";
raw.getRange(`A2:O${rawValues.length + 1}`).format.borders = { preset: "bottom", style: "hair", color: colors.midGray };
raw.getRange("A1:O1").format.autofitColumns();
raw.getRange("A1:A148").format.columnWidth = 10;
raw.getRange("B1:B148").format.columnWidth = 13;
raw.getRange("C1:C148").format.columnWidth = 9;
raw.getRange("D1:L148").format.columnWidth = 20;
raw.getRange("M1:N148").format.columnWidth = 16;
raw.getRange("O1:O148").format.columnWidth = 28;
raw.freezePanes.freezeRows(1);
raw.freezePanes.freezeColumns(3);

// Formula-driven calculation sheet.
calc.showGridLines = false;
const calcHeaders = [
  "지역", "연도", "지방채(억원)", "채무 증가율(%)", "지방세 증가율(%)",
  "자본지출 비중(%)", "채무/세입(%)", "부담비율 변화(%p)",
  "당해 진영", "전년 진영", "금융위기", "코로나",
];
calc.getRange("A1:L1").values = [calcHeaders];
headerStyle(calc.getRange("A1:L1"));
const calcRows = [];
const calcFormulas = [];
for (let index = 0; index < records.length; index += 1) {
  const record = records[index];
  if (Number(record.year) === 2004) continue;
  const rawRow = index + 2;
  const priorRawRow = rawRow - 1;
  const city = record.city;
  const year = Number(record.year);
  const partyNow = (() => {
    if (city === "서울") return year <= 2010 || year >= 2021 ? "보수" : "민주";
    if (city === "경기") return year <= 2017 ? "보수" : "민주";
    if (city === "부산") return year <= 2017 || year >= 2021 ? "보수" : year <= 2019 ? "민주" : "모호";
    if (city === "대구") return "보수";
    if (city === "광주") return "민주";
    if (city === "대전") return year === 2005 ? "모호" : year <= 2013 || year >= 2022 ? "보수" : "민주";
    return year <= 2017 || year >= 2022 ? "보수" : "민주";
  })();
  const previousYear = year - 1;
  const partyLag = (() => {
    if (city === "서울") return previousYear <= 2010 || previousYear >= 2021 ? "보수" : "민주";
    if (city === "경기") return previousYear <= 2017 ? "보수" : "민주";
    if (city === "부산") return previousYear <= 2017 || previousYear >= 2021 ? "보수" : previousYear <= 2019 ? "민주" : "모호";
    if (city === "대구") return "보수";
    if (city === "광주") return "민주";
    if (city === "대전") return previousYear === 2005 ? "모호" : previousYear <= 2013 || previousYear >= 2022 ? "보수" : "민주";
    return previousYear <= 2017 || previousYear >= 2022 ? "보수" : "민주";
  })();
  calcRows.push([city, year, null, null, null, null, null, null, partyNow, partyLag, [2009, 2010].includes(year) ? 1 : 0, [2020, 2021].includes(year) ? 1 : 0]);
  calcFormulas.push([
    `='원자료'!H${rawRow}/100000000`,
    `=('원자료'!H${rawRow}/'원자료'!H${priorRawRow}-1)*100`,
    `=('원자료'!J${rawRow}/'원자료'!J${priorRawRow}-1)*100`,
    `='원자료'!L${rawRow}/'원자료'!K${rawRow}*100`,
    `='원자료'!H${rawRow}/'원자료'!I${rawRow}*100`,
    `=('원자료'!H${rawRow}/'원자료'!I${rawRow}-'원자료'!H${priorRawRow}/'원자료'!I${priorRawRow})*100`,
  ]);
}
calc.getRange(`A2:L${calcRows.length + 1}`).values = calcRows;
calc.getRange(`C2:H${calcRows.length + 1}`).formulas = calcFormulas;
calc.getRange(`C2:H${calcRows.length + 1}`).format.font = { color: "#008000" };
calc.getRange(`C2:H${calcRows.length + 1}`).format.numberFormat = "0.00";
calc.getRange(`K2:L${calcRows.length + 1}`).format.numberFormat = "0";
calc.getRange(`A2:L${calcRows.length + 1}`).format.borders = { preset: "bottom", style: "hair", color: colors.midGray };
calc.getRange("A1:L1").format.autofitColumns();
calc.getRange("A1:A141").format.columnWidth = 10;
calc.getRange("B1:B141").format.columnWidth = 9;
calc.getRange("C1:H141").format.columnWidth = 18;
calc.getRange("I1:J141").format.columnWidth = 12;
calc.getRange("K1:L141").format.columnWidth = 11;
calc.freezePanes.freezeRows(1);
calc.freezePanes.freezeColumns(2);

// Statistical model output sheet.
models.showGridLines = false;
title(models, "A1:G1", "회귀모형 결과");
models.getRange("A2:G2").merge();
models.getRange("A2:G2").values = [["지역 고정효과 + 선형 추세, 지역 군집 표준오차 · 단위: %p"]];
models.getRange("A2:G2").format.font = { color: colors.darkGray, italic: true };
models.getRange("A4:E4").values = [["요인", "추정치", "95% 하한", "95% 상한", "군집 표준오차"]];
headerStyle(models.getRange("A4:E4"));
const driverModel = results.models.drivers_current.estimates;
models.getRange("A5:E9").values = driverLabels.map(([label, key]) => [
  label,
  driverModel[key].estimate,
  driverModel[key].ci95_t6[0],
  driverModel[key].ci95_t6[1],
  driverModel[key].cluster_se,
]);
models.getRange("B5:E9").format.numberFormat = "+0.00;-0.00;0.00";
lightBorders(models.getRange("A5:E9"));
models.getRange("A5:E5").format.fill = colors.paleGreen;
models.getRange("A6:E6").format.fill = colors.paleOrange;

section(models, "A11:G11", "재정부담 지표 — 지방채/순계 세입 비율의 전년 대비 변화");
models.getRange("A12:E12").values = [["요인", "추정치", "95% 하한", "95% 상한", "군집 표준오차"]];
headerStyle(models.getRange("A12:E12"));
const burdenModel = results.models.burden_change_current.estimates;
models.getRange("A13:E17").values = driverLabels.map(([label, key]) => [
  label,
  burdenModel[key].estimate,
  burdenModel[key].ci95_t6[0],
  burdenModel[key].ci95_t6[1],
  burdenModel[key].cluster_se,
]);
models.getRange("B13:E17").format.numberFormat = "+0.00;-0.00;0.00";
lightBorders(models.getRange("A13:E17"));

section(models, "A19:G19", "진영 민감도");
models.getRange("A20:D20").values = [["모형", "진영 추정치", "95% 하한", "95% 상한"]];
headerStyle(models.getRange("A20:D20"));
const partyCurrent = results.models.party_year_fe_current.estimates.democratic;
const partyLagged = results.models.party_year_fe_lagged.estimates.democratic;
models.getRange("A21:D23").values = [
  ["지역·연도 통제 · 당해 연도", partyCurrent.estimate, partyCurrent.ci95_t6[0], partyCurrent.ci95_t6[1]],
  ["요약 연결용 · 당해 연도", partyCurrent.estimate, partyCurrent.ci95_t6[0], partyCurrent.ci95_t6[1]],
  ["요약 연결용 · 1년 시차", partyLagged.estimate, partyLagged.ci95_t6[0], partyLagged.ci95_t6[1]],
];
models.getRange("B21:D23").format.numberFormat = "+0.00;-0.00;0.00";
lightBorders(models.getRange("A21:D23"));

section(models, "A25:G25", "모형 주석");
models.getRange("A26:G30").merge();
models.getRange("A26:G30").values = [[
  "표본은 정당 귀속이 모호한 관측을 제외한 138개 단체·연도입니다. 금융위기는 2009~2010년, 코로나는 2020~2021년입니다. " +
  "세수와 자본지출 계수는 각각 표본 1표준편차 변화 기준입니다. 95% 범위는 지역 7개 군집과 자유도 6의 t 임계값을 사용했습니다. " +
  "모형은 관측상의 연관성을 보여주며 인과효과를 식별하지 않습니다.",
]];
models.getRange("A26:G30").format = { wrapText: true, verticalAlignment: "top", fill: colors.gray };
models.getRange("A1:G30").format.font.name = "Arial";
models.getRange("A1:A30").format.columnWidth = 34;
models.getRange("B1:E30").format.columnWidth = 16;
models.getRange("F1:G30").format.columnWidth = 18;
models.freezePanes.freezeRows(2);

// Sources and checks.
sources.showGridLines = false;
title(sources, "A1:F1", "출처와 검증");
section(sources, "A3:F3", "공식 원자료");
sources.getRange("A4:C4").values = [["데이터", "제공 범위", "URL"]];
headerStyle(sources.getRange("A4:C4"));
sources.getRange("A5:C7").values = [
  ["회계별 지방채 잔액", "2000~2024", "https://www.data.go.kr/data/15058459/openapi.do"],
  ["재원별 회계별 세입결산", "2002~2024", "https://www.data.go.kr/data/15056937/openapi.do"],
  ["성질별 단체별 세출결산", "2002~2024", "https://www.data.go.kr/data/15057187/openapi.do"],
];
sources.getRange("A5:C7").format.font = { color: colors.blue };
lightBorders(sources.getRange("A5:C7"));

section(sources, "A9:F9", "자동 검증");
sources.getRange("A10:D10").values = [["검증 항목", "계산값", "기대값", "판정"]];
headerStyle(sources.getRange("A10:D10"));
sources.getRange("A11:A15").values = [
  ["원자료 행 수"], ["계산 행 수"], ["최초 연도"], ["최종 연도"], ["지방채 계정 합계 일치"],
];
sources.getRange("B11:B15").formulas = [
  ["=COUNTA('원자료'!A2:A148)"],
  ["=COUNTA('계산'!A2:A141)"],
  ["=MIN('원자료'!C2:C148)"],
  ["=MAX('원자료'!C2:C148)"],
  ["=SUM('원자료'!H2:H148)-SUM('원자료'!D2:G148)"],
];
sources.getRange("C11:C15").values = [[147], [140], [2004], [2024], [0]];
sources.getRange("D11:D15").formulas = [
  ["=IF(B11=C11,\"통과\",\"확인\")"],
  ["=IF(B12=C12,\"통과\",\"확인\")"],
  ["=IF(B13=C13,\"통과\",\"확인\")"],
  ["=IF(B14=C14,\"통과\",\"확인\")"],
  ["=IF(ABS(B15-C15)<1,\"통과\",\"확인\")"],
];
sources.getRange("B11:B15").format.font = { color: "#008000" };
sources.getRange("D11:D15").format.font = { bold: true, color: colors.green };
sources.getRange("B11:C15").format.numberFormat = "#,##0";
lightBorders(sources.getRange("A11:D15"));

section(sources, "A17:F17", "정의와 재현");
sources.getRange("A18:F23").merge();
sources.getRange("A18:F23").values = [[
  "수집 스크립트: analysis/collect_lofin_20y.py\n" +
  "분석 스크립트: analysis/metro_head_office_20y.py\n" +
  "본청 채무 = 일반회계 + 기타특별회계 + 공기업특별회계 + 기금회계 지방채 잔액.\n" +
  "재정부담 지표 = 지방채 잔액 / 순계 세입 결산액. 공식 관리채무비율과 다릅니다.\n" +
  "자본지출 = 성질별 세출결산의 4xxxx 항목 합계. 원 API 응답은 analysis/data/metro-head-office-2004-2024-raw.json에 보존했습니다.",
]];
sources.getRange("A18:F23").format = { wrapText: true, verticalAlignment: "top", fill: colors.gray };
sources.getRange("A1:F23").format.font.name = "Arial";
sources.getRange("A1:A23").format.columnWidth = 32;
sources.getRange("B1:B23").format.columnWidth = 16;
sources.getRange("C1:C23").format.columnWidth = 56;
sources.getRange("D1:F23").format.columnWidth = 16;
sources.freezePanes.freezeRows(3);

// Compact verification before export.
const overview = await workbook.inspect({
  kind: "workbook,sheet",
  include: "id,name",
  maxChars: 5000,
});
console.log(overview.ndjson);
const keyCheck = await workbook.inspect({
  kind: "table",
  range: "요약!A1:H22",
  include: "values,formulas",
  tableMaxRows: 24,
  tableMaxCols: 8,
  maxChars: 10000,
});
console.log(keyCheck.ndjson);
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

await fs.mkdir(outputDir, { recursive: true });
for (const sheetName of ["요약", "원자료", "계산", "모형결과", "출처·검증"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(
    `${outputDir}/preview-${sheetName.replace("·", "-")}.png`,
    new Uint8Array(await preview.arrayBuffer()),
  );
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(`exported ${outputPath}`);
