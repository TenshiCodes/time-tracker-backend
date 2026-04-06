from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation
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

    header_fill = PatternFill(start_color="C6E0B4", fill_type="solid")

    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = header_fill
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    ws.freeze_panes = "A2"

    # Column widths
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
    # ✅ AUTO PROJECT NUMBER (still formula, optional)
    # -------------------------------
    for row in range(2, 500):
        ws.cell(row=row, column=3).value = f'=IFERROR(VLOOKUP(D{row},Lookup!A:B,2,FALSE),"")'

    # -------------------------------
    # ✅ FILL DATA FIRST
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

        # WRITE DATA
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
    # ✅ APPLY FORMATTING LAST (NO FORMULAS)
    # -------------------------------
    red_fill = PatternFill(start_color="FFC7CE", fill_type="solid")
    blue_fill = PatternFill(start_color="D9EAF7", fill_type="solid")

    for row in range(2, last_row + 1):
        date_cell = ws.cell(row=row, column=1)
        date_val = date_cell.value

        if not date_val:
            continue

        # Python weekday (Mon=0, Sun=6)
        is_weekend = date_val.weekday() >= 5

        # 🔵 Highlight weekend DATE only
        if is_weekend:
            date_cell.fill = blue_fill
            continue  # skip red checks for weekends

        # 🔴 Highlight missing fields (weekday only)
        for col in range(2, 7):
            cell = ws.cell(row=row, column=col)

            # IMPORTANT: keep 0.00 valid (only None or "" is missing)
            if cell.value in (None, ""):
                cell.fill = red_fill

    return wb