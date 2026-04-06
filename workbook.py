from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from datetime import timedelta
from zoneinfo import ZoneInfo


def build_timesheet_wb(projects, time_entries, tz="UTC"):
    wb = Workbook()
    ws = wb.active
    ws.title = "Timesheet"

    # -------------------------------
    # ✅ HEADERS
    # -------------------------------
    headers = ["Date", "Time {hh:mm}", "Project Number", "Customer", "Labor Type", "Description"]
    ws.append(headers)

    # Style header
    header_fill = PatternFill(start_color="C6E0B4", fill_type="solid")
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = header_fill
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    ws.freeze_panes = "A2"

    # -------------------------------
    # ✅ LOOKUP SHEET
    # -------------------------------
    ws_lookup = wb.create_sheet(title="Lookup")

    for i, p in enumerate(projects, start=1):
        ws_lookup.cell(row=i, column=1, value=p["name"])
        ws_lookup.cell(row=i, column=2, value=p["code"])

    ws_lookup.sheet_state = "hidden"

    max_row_lookup = len(projects)

    # -------------------------------
    # ✅ DROPDOWNS
    # -------------------------------
    dv_customer = DataValidation(
        type="list",
        formula1=f'=Lookup!$A$1:$A${max_row_lookup}'
    )
    ws.add_data_validation(dv_customer)
    dv_customer.add("D2:D200")

    labor_options = [
        "Labor", "Labor 1 X (Flex Time)", "Labor 1 X (Bonus OT)",
        "Labor 1.5 X (Flex Time)", "Labor 1.5 X (Bonus OT)",
        "Labor 2 X (Flex Time)", "Labor 2 X (Bonus OT)",
        "Personal Vehicle Ground Travel", "Air Travel",
        "PTO (Gusto)", "PTO (Embedded Contract)",
        "PTO (Sabbatical)", "PTO (Flex Time)",
        "Disability", "Company Holiday"
    ]

    dv_labor = DataValidation(type="list", formula1=f'"{",".join(labor_options)}"')
    ws.add_data_validation(dv_labor)
    dv_labor.add("E2:E200")

    # -------------------------------
    # ✅ AUTO PROJECT NUMBER
    # -------------------------------
    for row in range(2, 200):
        ws.cell(row=row, column=3).value = f'=IFERROR(VLOOKUP(D{row},Lookup!A:B,2,FALSE),"")'

    # -------------------------------
    # ✅ CONDITIONAL FORMATTING
    # -------------------------------
    red_fill = PatternFill(start_color="FFC7CE", fill_type="solid")
    blue_fill = PatternFill(start_color="D9EAF7", fill_type="solid")

    rules = {
        "B": '=AND($A2<>"", WEEKDAY($A2,2)<6, B2="")',
        "C": '=AND($A2<>"", WEEKDAY($A2,2)<6, C2="")',
        "D": '=AND($A2<>"", WEEKDAY($A2,2)<6, D2="")',
        "E": '=AND($A2<>"", WEEKDAY($A2,2)<6, E2="")',
        "F": '=AND($A2<>"", WEEKDAY($A2,2)<6, F2="")',
    }

    for col, formula in rules.items():
        ws.conditional_formatting.add(
            f"{col}2:{col}200",
            FormulaRule(formula=[formula], fill=red_fill)
        )

    ws.conditional_formatting.add(
        "A2:A200",
        FormulaRule(
            formula=['=AND(A2<>"", WEEKDAY(A2,2)>=6)'],
            fill=blue_fill
        )
    )

    # -------------------------------
    # ✅ FILL DATA FROM time_entries
    # -------------------------------
    row_index = 2

    for row in time_entries:
        start = row["clock_in"]
        end = row["clock_out"]

        if start and end:
            start_dt = start.astimezone(ZoneInfo(tz))
            end_dt = end.astimezone(ZoneInfo(tz))

            if end_dt < start_dt:
                diff_hours = (start_dt - end_dt).total_seconds() / 3600
                if diff_hours <= 12:
                    end_dt += timedelta(hours=12)
                else:
                    end_dt += timedelta(days=1)

            # Fill sheet
            ws.cell(row=row_index, column=1, value=start_dt.date())
            ws.cell(row=row_index, column=2, value=start_dt.strftime("%H:%M"))
            ws.cell(row=row_index, column=6, value=f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}")

        # Project number from DB
        ws.cell(row=row_index, column=3, value=row["job_code"])

        row_index += 1

    return wb
