/**
 * CRM Automation Project
 * 
 * Demo Google Apps Script used for a portfolio project.
 * The script automates basic CRM reporting tasks in Google Sheets:
 * - highlights rows based on lead status,
 * - adds close dates for closed deals,
 * - creates a custom CRM Tools menu,
 * - refreshes the dashboard,
 * - generates a simple CRM report,
 * - sends an email report to the active user.
 *
 * Dataset: fictional / demo data.
 */
function helloWorld() {
  Logger.log("CRM Dashboard Project");
}

function showMessage() {
  SpreadsheetApp.getUi().alert("Witaj w CRM Dashboard!");
}

function onEdit(e) {

  const sheet = e.range.getSheet();
  const row = e.range.getRow();
  const column = e.range.getColumn();

  const STATUS_COLUMN = 7;      // G
  const CLOSE_DATE_COLUMN = 10; // J

  if (row == 1) return;

  if (column != STATUS_COLUMN) return;

  const status = e.range.getValue().toString().trim().toUpperCase();

  const rowRange = sheet.getRange(row,1,1,sheet.getLastColumn());

  // Wyczyść poprzedni kolor
  rowRange.setBackground(null);

  if(status == "NEW"){
    rowRange.setBackground("#CFE2F3");
  }

  if(status == "CONTACTED"){
    rowRange.setBackground("#FFF2CC");
  }

  if(status == "CLOSED"){

    rowRange.setBackground("#D9EAD3");

    const closeDate = sheet.getRange(row,CLOSE_DATE_COLUMN);

    if(closeDate.getValue()==""){
      closeDate.setValue(new Date());
    }

  }

  if(status == "UNKNOWN"){
    rowRange.setBackground("#F4CCCC");
  }

}
function processExistingData() {

  const sheet = SpreadsheetApp
    .getActiveSpreadsheet()
    .getSheetByName("CLEAN_DATA");

  const STATUS_COLUMN = 7;      // G
  const CLOSE_DATE_COLUMN = 10; // J

  const lastRow = sheet.getLastRow();Logger.log(lastRow);
  const lastColumn = sheet.getLastColumn();

  for (let row = 2; row <= lastRow; row++) {

    const status = sheet
      .getRange(row, STATUS_COLUMN)
      .getValue()
      .toString()
      .trim()
      .toUpperCase();

    const rowRange = sheet.getRange(row, 1, 1, lastColumn);

    rowRange.setBackground(null);

    if (status === "NEW") rowRange.setBackground("#CFE2F3");

    if (status === "CONTACTED") rowRange.setBackground("#FFF2CC");

    if (status === "UNKNOWN") rowRange.setBackground("#F4CCCC");

    if (status === "CLOSED") {
      rowRange.setBackground("#D9EAD3");

      const closeDate = sheet.getRange(row, CLOSE_DATE_COLUMN);

      if (closeDate.getValue() === "") {
        closeDate.setValue(new Date());
      }
    }
  }
}
function onOpen() {

  SpreadsheetApp.getUi()

    .createMenu("CRM Tools")

    .addItem("Refresh Dashboard","refreshDashboard")

    .addItem("Color Existing Data","processExistingData")

    .addItem("Generate Sales Report","generateReport")

    .addItem("Send Email Report", "sendEmailReport")

    .addItem("Welcome","showMessage")

    .addToUi();

}
function refreshDashboard(){

  SpreadsheetApp.flush();

  SpreadsheetApp.getUi().alert("Dashboard has been refreshed.");

}
function generateReport(){

  const ss = SpreadsheetApp.getActiveSpreadsheet();

  const source = ss.getSheetByName("CLEAN_DATA");

  const report = ss.getSheetByName("REPORT");

  report.clear();

  report.getRange("A1").setValue("CRM SALES REPORT");

  report.getRange("A3").setValue("Generated:");

  report.getRange("B3").setValue(new Date());

  report.getRange("A5").setValue("Total Records");

  report.getRange("B5").setValue(source.getLastRow()-1);

  SpreadsheetApp.getUi().alert("Report generated successfully!");

}
function sendEmailReport() {

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const report = ss.getSheetByName("REPORT");

  const email = Session.getActiveUser().getEmail();

  const totalRecords = report.getRange("B5").getValue();
  const generatedDate = report.getRange("B3").getValue();

  const subject = "CRM Sales Report";

  const body =
    "Hello,\n\n" +
    "CRM Sales Report has been generated.\n\n" +
    "Generated: " + generatedDate + "\n" +
    "Total Records: " + totalRecords + "\n\n" +
    "Best regards,\n" +
    "CRM Automation System";

  GmailApp.sendEmail(email, subject, body);

  SpreadsheetApp.getUi().alert("Email report sent successfully.");
