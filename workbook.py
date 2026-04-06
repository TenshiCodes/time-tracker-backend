from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
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
    headers = ["Date", "Time (hh:mm)", "Project Number", "Customer", "Labor Type", "Description"]
    ws.append(headers)

    # Header style
    header_fill = PatternFill(start_color="C6E0B4", fill_type="solid")

    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = header_fill
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    ws.freeze_panes = "A2"

    # Column widths (FIXES YOUR HEADER ISSUE)
    column_widths = [14, 18, 24, 30, 22, 40]
    for i, width in enumerate(column_widths, start=1):
        ws.column_dimensions[chr(64 + i)].width = width

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
    dv_customer.add("D2:D500")

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
    dv_labor.add("E2:E500")

    # -------------------------------
    # ✅ AUTO PROJECT NUMBER
    # -------------------------------
    for row in range(2, 500):
        ws.cell(row=row, column=3).value = f'=IFERROR(VLOOKUP(D{row},Lookup!A:B,2,FALSE),"")'

    # -------------------------------
    # ✅ FILL DATA
    # -------------------------------
    row_index = 2
    project_map = {p["code"]: p["name"] for p in projects}

    for row in time_entries:
        start = row["clock_in"]
        end = row["clock_out"]
        job_code = row["job_code"]

        if not start:
            continue

        start_dt = start.astimezone(ZoneInfo(tz)).replace(tzinfo=None)

        duration_hours = None

        if end:
            end_dt = end.astimezone(ZoneInfo(tz)).replace(tzinfo=None)

            if end_dt < start_dt:
                diff_hours = (start_dt - end_dt).total_seconds() / 3600
                if diff_hours <= 12:
                    end_dt += timedelta(hours=12)
                else:
                    end_dt += timedelta(days=1)

            diff = end_dt - start_dt
            duration_hours = round(diff.total_seconds() / 3600, 2)

        # Write values
        ws.cell(row=row_index, column=1, value=start_dt)
        ws.cell(row=row_index, column=1).number_format = "m/d/yyyy"

        ws.cell(row=row_index, column=2, value=duration_hours)
        ws.cell(row=row_index, column=2).number_format = "0.00"

        ws.cell(row=row_index, column=3, value=job_code)

        customer_name = project_map.get(job_code, "")
        ws.cell(row=row_index, column=4, value=customer_name)

        row_index += 1

    last_row = row_index - 1

    # -------------------------------
    # ✅ CONDITIONAL FORMATTING (FIXED)
    # -------------------------------
    red_fill = PatternFill(start_color="FFC7CE", fill_type="solid")
    blue_fill = PatternFill(start_color="D9EAF7", fill_type="solid")

    rules = {
        "B": '=AND(ISNUMBER($A2), WEEKDAY($A2,2)<6, B2="")',
        "C": '=AND(ISNUMBER($A2), WEEKDAY($A2,2)<6, C2="")',
        "D": '=AND(ISNUMBER($A2), WEEKDAY($A2,2)<6, D2="")',
        "E": '=AND(ISNUMBER($A2), WEEKDAY($A2,2)<6, E2="")',
        "F": '=AND(ISNUMBER($A2), WEEKDAY($A2,2)<6, F2="")',
    }

    for col, formula in rules.items():
        ws.conditional_formatting.add(
            f"{col}2:{col}{last_row}",
            FormulaRule(formula=[formula], fill=red_fill)
        )

    ws.conditional_formatting.add(
        f"A2:A{last_row}",
        FormulaRule(
            formula=['=AND(ISNUMBER(A2), WEEKDAY(A2,2)>=6)'],
            fill=blue_fill
        )
    )

    # -------------------------------
    # ✅ BORDERS + ALIGNMENT (VISUAL FIX)
    # -------------------------------
    thin = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin")
    )

    for row in ws.iter_rows(min_row=1, max_row=last_row, min_col=1, max_col=6):
        for cell in row:
            cell.border = thin

    for row in range(2, last_row + 1):
        ws.cell(row=row, column=1).alignment = Alignment(horizontal="center")
        ws.cell(row=row, column=2).alignment = Alignment(horizontal="center")
        ws.cell(row=row, column=3).alignment = Alignment(horizontal="center")

    # Autofilter
    ws.auto_filter.ref = f"A1:F{last_row}"

    return wb