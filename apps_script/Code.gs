/**
 * Weekly Talent Review - report automation.
 *
 * Reads the KPI tiles off the dashboard, appends a weekly snapshot, asks a
 * language model to write the executive summary, and fills in a Google Slides
 * deck. runWeeklyReport() is the only function that needs to be called; every
 * other function is small enough to run on its own when one step misbehaves.
 *
 * Setup lives in README.md. The short version: set the Script Properties
 * LLM_API_KEY and TEMPLATE_ID, run runWeeklyReport() once to approve the OAuth
 * scopes, then run setupTrigger() once to put it on a Monday schedule.
 *
 * Everything this touches is synthetic prototype data. No real candidate or
 * company information passes through here.
 */

const PROPS = PropertiesService.getScriptProperties();

/**
 * The narrative model. Any OpenAI-compatible chat completions endpoint works,
 * so switching providers is a change to these three lines and nothing else.
 */
const LLM = {
  endpoint: 'https://api.groq.com/openai/v1/chat/completions',
  model: 'llama-3.3-70b-versatile',
  temperature: 0.4
};

/** Open requisitions older than this many days are called out in the deck. */
const AT_RISK_DAYS = 60;

/** How many at-risk requisitions to list on the slide. */
const AT_RISK_LIMIT = 8;

/**
 * Zero-based column positions in Recruiting_Data. Named rather than inlined so
 * that inserting a column upstream breaks in one obvious place instead of
 * silently shifting which field the at-risk table reports.
 */
const COL = {
  CANDIDATE_ID: 0,
  REQUISITION_ID: 1,
  TEAM: 2,
  DEPARTMENT: 3,
  REGION: 4,
  RECRUITER: 5,
  HIRING_MANAGER: 6,
  SOURCE: 7,
  CANDIDATE_TYPE: 8,
  APPLICATION_DATE: 9,
  PHONE_SCREEN_DATE: 10,
  ONSITE_DATE: 11,
  OFFER_DATE: 12,
  HIRE_DATE: 13,
  CURRENT_STAGE: 14,
  REQ_OPEN_DATE: 15,
  TIME_TO_FILL: 16,
  HEADCOUNT_STATUS: 17
};


// The whole pipeline in order. This is the only function I run by hand.
function runWeeklyReport() {
  try {
    refreshSnapshot();                           // save this week's numbers
    const metrics = getMetrics();                // read the dashboard KPIs
    const narrative = generateNarrative();       // let the model write the summary
    const url = buildSlides(metrics, narrative); // build the slide deck

    // sendReportEmail(url, narrative);  // emails the deck to leadership - off for now (see bottom)

    log_('SUCCESS: ' + url);
  } catch (e) {
    log_('FAILED: ' + e.message);
    // MailApp.sendEmail(Session.getEffectiveUser().getEmail(), 'Weekly report failed', e.stack);
  }
}


// Read the six KPI tiles off the dashboard using their named ranges.
function getMetrics() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const v = name => ss.getRangeByName(name).getValue();
  return {
    weekOf:      Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'MMM d, yyyy'),
    openReqs:    v('KPI_OpenReqs'),
    hires:       v('KPI_Hires'),
    ttf:         v('KPI_TTF'),
    offerAccept: v('KPI_OfferAccept'),
    funnelConv:  v('KPI_FunnelConv'),
    hcVsPlan:    v('KPI_HCvsPlan')
  };
}


// Add this week's numbers as a new row in Weekly_Snapshots.
// This is what lets me compare this week to last week later on.
function refreshSnapshot() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  SpreadsheetApp.flush();  // make sure the formulas finish recalculating first
  const snap = ss.getSheetByName('Weekly_Snapshots');

  // don't add a second row if I already ran it today
  const last = snap.getRange(snap.getLastRow(), 1).getValue();
  const today = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd');
  if (last && Utilities.formatDate(new Date(last), Session.getScriptTimeZone(), 'yyyy-MM-dd') === today) {
    return;
  }

  const m = getMetrics();
  snap.appendRow([new Date(), m.openReqs, m.hires, m.ttf, m.offerAccept, m.funnelConv, m.hcVsPlan]);
}


// Grab the last two snapshot rows and work out the week-over-week change.
function getWeekOverWeek() {
  const snap = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Weekly_Snapshots');
  const lastRow = snap.getLastRow();
  const cur  = snap.getRange(lastRow, 1, 1, 7).getValues()[0];
  const prev = snap.getRange(Math.max(2, lastRow - 1), 1, 1, 7).getValues()[0];  // falls back if there's only one week

  return {
    cur, prev,
    delta: {
      openReqs:    cur[1] - prev[1],
      hires:       cur[2] - prev[2],
      ttf:         cur[3] - prev[3],
      offerAccept: cur[4] - prev[4],
      funnelConv:  cur[5] - prev[5],
      hcVsPlan:    cur[6] - prev[6]
    }
  };
}


// Send the numbers to the model and get back a short written summary.
function generateNarrative() {
  const w = getWeekOverWeek();
  const cur = w.cur, d = w.delta;

  // I feed it the exact numbers and tell it not to make anything up,
  // so the summary always matches the real data.
  const prompt =
`You are a Recruiting Operations analyst writing the weekly talent review for a VP of Talent.
Use only the numbers given below. Do not make up any figures. Lead with the main takeaway.
Plain English, no markdown, no asterisks or hash symbols. Write the section labels in plain capitals.
Round numbers - days to whole numbers, percentages to one decimal.
Write about 150 words in four short sections: HEADLINE, WHAT CHANGED, RISKS, OPPORTUNITIES.

CURRENT WEEK:
Open Reqs ${cur[1]}, Hires ${cur[2]}, Avg Time-to-Fill ${cur[3]} days,
Offer Acceptance ${(cur[4]*100).toFixed(1)}%, Funnel Conversion ${(cur[5]*100).toFixed(1)}%, Headcount vs Plan ${(cur[6]*100).toFixed(1)}%.

CHANGE FROM LAST WEEK:
Open Reqs ${d.openReqs}, Hires ${d.hires}, Time-to-Fill ${d.ttf.toFixed(1)} days,
Offer Acceptance ${(d.offerAccept*100).toFixed(1)} pts, Funnel Conversion ${(d.funnelConv*100).toFixed(1)} pts, Headcount vs Plan ${(d.hcVsPlan*100).toFixed(1)} pts.`;

  const apiKey = PROPS.getProperty('LLM_API_KEY');
  if (!apiKey) throw new Error('LLM_API_KEY not set in Script Properties');

  const res = UrlFetchApp.fetch(LLM.endpoint, {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + apiKey },
    muteHttpExceptions: true,
    payload: JSON.stringify({
      model: LLM.model,
      temperature: LLM.temperature,
      max_tokens: 350,
      messages: [
        { role: 'system', content: 'You are an expert Recruiting Operations analyst.' },
        { role: 'user', content: prompt }
      ]
    })
  });

  if (res.getResponseCode() !== 200) {
    throw new Error('Narrative model error: ' + res.getContentText());
  }
  const narrative = JSON.parse(res.getContentText()).choices[0].message.content.trim();

  // keep a copy in the AI_Output tab so I can read it without opening the deck
  SpreadsheetApp.getActiveSpreadsheet().getSheetByName('AI_Output').getRange('A1').setValue(narrative);
  return narrative;
}


// Make a copy of the template deck and fill it in with this week's data.
function buildSlides(metrics, narrative) {
  const templateId = PROPS.getProperty('TEMPLATE_ID');
  if (!templateId) throw new Error('TEMPLATE_ID not set in Script Properties');

  // copy the template (into a folder if I set one, otherwise just My Drive)
  const folderId = PROPS.getProperty('REPORT_FOLDER');
  const name = 'Weekly Talent Review - ' + metrics.weekOf;
  const file = folderId
    ? DriveApp.getFileById(templateId).makeCopy(name, DriveApp.getFolderById(folderId))
    : DriveApp.getFileById(templateId).makeCopy(name);

  const deck = SlidesApp.openById(file.getId());

  // swap out the {{placeholders}} in the template for the real values
  const pct = x => (x * 100).toFixed(0) + '%';
  deck.replaceAllText('{{WEEK_OF}}',      String(metrics.weekOf));
  deck.replaceAllText('{{OPEN_REQS}}',    String(metrics.openReqs));
  deck.replaceAllText('{{HIRES}}',        String(metrics.hires));
  deck.replaceAllText('{{TTF}}',          Number(metrics.ttf).toFixed(0));
  deck.replaceAllText('{{OFFER_ACCEPT}}', pct(metrics.offerAccept));
  deck.replaceAllText('{{HC_VS_PLAN}}',   pct(metrics.hcVsPlan));
  deck.replaceAllText('{{NARRATIVE}}',    narrative);

  // pull the charts in from the Sheet (skips them if I haven't made the charts yet)
  insertSheetChart_(deck, 2, 'Time_to_Fill'); // slide 3
  insertSheetChart_(deck, 3, 'Funnel');       // slide 4

  // build the at-risk reqs table on slide 5
  buildAtRiskTable_(deck.getSlides()[4], getAtRiskReqs(AT_RISK_DAYS, AT_RISK_LIMIT));

  deck.saveAndClose();
  return file.getUrl();
}


// Drop the first chart from a given Sheet tab onto a slide.
// Wrapped in try/catch so a missing chart doesn't break the whole run.
function insertSheetChart_(deck, slideIndex, sheetName) {
  try {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(sheetName);
    const charts = sheet ? sheet.getCharts() : [];
    if (!charts.length) return;  // no chart on that tab yet, just skip it
    deck.getSlides()[slideIndex].insertSheetsChart(charts[0])
        .setLeft(60).setTop(150).setWidth(620).setHeight(300);
  } catch (e) {
    log_('chart skipped (' + sheetName + '): ' + e.message);
  }
}


// Find open reqs that have been open longer than minDays, return the worst ones.
function getAtRiskReqs(minDays, limit) {
  const data = SpreadsheetApp.getActiveSpreadsheet()
    .getSheetByName('Recruiting_Data').getDataRange().getValues();

  const seen = new Set();  // count each requisition once, not once per candidate
  const out = [];
  const now = new Date();

  for (let i = 1; i < data.length; i++) {
    const r = data[i];
    const reqId = r[COL.REQUISITION_ID];
    const dept = r[COL.DEPARTMENT];
    const region = r[COL.REGION];
    const recruiter = r[COL.RECRUITER];
    const openDate = r[COL.REQ_OPEN_DATE];
    const status = r[COL.HEADCOUNT_STATUS];

    if (status !== 'Open' || !openDate || seen.has(reqId)) continue;
    seen.add(reqId);

    const daysOpen = Math.floor((now - new Date(openDate)) / 86400000);
    if (daysOpen >= minDays) {
      out.push([reqId, dept, region || 'NA', String(daysOpen), recruiter, status]);
    }
  }

  out.sort((a, b) => Number(b[3]) - Number(a[3]));  // oldest first
  return out.slice(0, limit);
}


// Draw the at-risk table on the slide.
function buildAtRiskTable_(slide, rows) {
  const header = ['Requisition ID', 'Department', 'Region', 'Days Open', 'Recruiter', 'Status'];
  const all = [header].concat(rows.length ? rows : [['-', '-', '-', '-', '-', 'none over threshold']]);

  const table = slide.insertTable(all.length, 6, 40, 160, 660, 250);
  for (let r = 0; r < all.length; r++) {
    for (let c = 0; c < 6; c++) {
      const cell = table.getCell(r, c).getText();
      cell.setText(String(all[r][c]));
      if (r === 0) cell.getTextStyle().setBold(true);  // bold the header row
    }
  }
}


/* ---------- email step ----------
   This works, but I've left it commented out for now. With email turned on it
   asks for Gmail permission and would send the deck to a real inbox, which I
   don't need during a demo. For the real project I'd just uncomment this and
   the line in runWeeklyReport(), set REPORT_EMAIL, and it sends automatically.

function sendReportEmail(url, narrative) {
  const to = PROPS.getProperty('REPORT_EMAIL') || Session.getEffectiveUser().getEmail();
  MailApp.sendEmail({
    to: to,
    subject: 'Weekly Talent Review - ' + Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'MMM d, yyyy'),
    htmlBody:
      '<h3>This week in recruiting</h3><p>' + narrative.replace(/\n/g, '<br>') + '</p>' +
      '<p><a href="' + url + '">Open the full deck</a></p>' +
      '<hr><small>Auto-generated from synthetic prototype data. No real candidate or company data.</small>'
  });
}
*/


// Writes a line to the Logs tab so I can see what happened on each run.
function log_(msg) {
  SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Logs').appendRow([new Date(), msg]);
}


// Run this once to schedule the report every Monday morning.
function setupTrigger() {
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));  // clear old ones first
  ScriptApp.newTrigger('runWeeklyReport').timeBased()
    .onWeekDay(ScriptApp.WeekDay.MONDAY).atHour(7).create();
}