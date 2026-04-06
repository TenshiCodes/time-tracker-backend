from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from datetime import timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict


def build_timesheet_wb(projects, time_entries, tz="UTC"):
    daily_totals = defaultdict(float)

    wb = Workbook()
    ws = wb.active
    ws.title = "Timesheet"

    # -----------------------------------
    # ✅ HEADERS FIRST
    # -----------------------------------
    headers = ["Date", "Time {hh:mm}", "Project Number", "Customer", "Labor Type", "Description"]
    ws.append(headers)
    # -----------------------------------
    # ✅ LOOKUP SHEET (for Customer dropdown)
    # -----------------------------------
    ws_lookup = wb.create_sheet(title="Lookup")

    for i, p in enumerate(projects, start=1):
        ws_lookup.cell(row=i, column=1, value=p["name"])  # Customer
        ws_lookup.cell(row=i, column=2, value=p["code"])  # Project Number

    ws_lookup.sheet_state = "hidden"
    max_row_lookup = len(projects)
    # -----------------------------------
    # ✅ PROJECT MAP (code → name)
    # -----------------------------------
    project_map = {p["code"]: p["name"] for p in projects}

    # -----------------------------------
    # ✅ WRITE DATA
    # -----------------------------------
    row_index = 2
    time_entries.sort(key=lambda x: x["clock_in"] or "")
    for row in time_entries:
        start = row["clock_in"]
        end = row["clock_out"]
        job_code = row["job_code"]

        if not start:
            continue

        start_dt = start.astimezone(ZoneInfo(tz)).replace(tzinfo=None)
        entry_date = start_dt.date()

        hours = 0

        if end:
            end_dt = end.astimezone(ZoneInfo(tz)).replace(tzinfo=None)

            if end_dt < start_dt:
                diff_hours = (start_dt - end_dt).total_seconds() / 3600
                if diff_hours <= 12:
                    end_dt += timedelta(hours=12)
                else:
                    end_dt += timedelta(days=1)

            diff = end_dt - start_dt
            hours = round(diff.total_seconds() / 3600, 2)

        # -----------------------------------
        # ✅ CHECK DAILY LIMIT (8 HOURS)
        # -----------------------------------
        current_total = daily_totals[entry_date]

        if current_total >= 8:
            # ✅ Already full → everything is overflow
            write_hours = 0
            overflow = hours

        elif current_total + hours <= 8:
            # ✅ Normal case
            write_hours = hours
            overflow = 0

        else:
            # ✅ Split case
            write_hours = 8 - current_total
            overflow = hours - write_hours

        # -----------------------------------
        # ✅ WRITE MAIN ROW
        # -----------------------------------
        customer_name = project_map.get(job_code, "")
        if write_hours > 0:
            ws.cell(row=row_index, column=1, value=start_dt)
            ws.cell(row=row_index, column=1).number_format = "m/d/yyyy"

            ws.cell(row=row_index, column=2, value=write_hours / 24)
            ws.cell(row=row_index, column=2).number_format = "[h]:mm"

            ws.cell(row=row_index, column=3, value=job_code)
            ws.cell(row=row_index, column=4, value=customer_name)

            row_index += 1

        # -----------------------------------
        # ✅ WRITE OVERFLOW ROW (if needed)
        # -----------------------------------
        if overflow > 0:
            ws.cell(row=row_index, column=1, value=start_dt)
            ws.cell(row=row_index, column=1).number_format = "m/d/yyyy"

            ws.cell(row=row_index, column=2, value=overflow / 24)
            ws.cell(row=row_index, column=2).number_format = "[h]:mm"

            ws.cell(row=row_index, column=3, value=job_code)
            ws.cell(row=row_index, column=4, value=customer_name)

            row_index += 1

        # -----------------------------------
        # ✅ UPDATE TOTAL
        # -----------------------------------
        daily_totals[entry_date] += hours

    # -----------------------------------
    # ✅ CONDITIONAL FORMATTING (EXACT ORIGINAL)
    # -----------------------------------
    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

    rows = 200

    rules = {
        "B": '=AND($A2<>"", OR(WEEKDAY($A2,2)<6, AND(WEEKDAY($A2,2)>=6, $B2<>"")), B2="")',
        "C": '=AND($A2<>"", OR(WEEKDAY($A2,2)<6, AND(WEEKDAY($A2,2)>=6, $B2<>"")), C2="")',
        "D": '=AND($A2<>"", OR(WEEKDAY($A2,2)<6, AND(WEEKDAY($A2,2)>=6, $B2<>"")), D2="")',
        "E": '=AND($A2<>"", OR(WEEKDAY($A2,2)<6, AND(WEEKDAY($A2,2)>=6, $B2<>"")), E2="")',
        "F": '=AND($A2<>"", OR(WEEKDAY($A2,2)<6, AND(WEEKDAY($A2,2)>=6, $B2<>"")), F2="")',
    }

    for col, formula in rules.items():
        ws.conditional_formatting.add(
            f"{col}2:{col}{rows}",
            FormulaRule(formula=[formula], fill=red_fill)
        )

    blue_fill = PatternFill(start_color="D9EAF7", end_color="D9EAF7", fill_type="solid")

    ws.conditional_formatting.add(
        "A2:A200",
        FormulaRule(
            formula=['=AND(A2<>"", WEEKDAY(A2,2)>=6)'],
            fill=blue_fill
        )
    )

    # -----------------------------------
    # ✅ HEADER STYLING
    # -----------------------------------
    header_fill = PatternFill(start_color="C6E0B4", end_color="C6E0B4", fill_type="solid")
    header_font = Font(bold=True)
    center_align = Alignment(horizontal="center", vertical="center")

    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin")
    )

    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = thin_border

    # Column widths
    column_widths = [12, 14, 20, 25, 22, 40]
    for i, width in enumerate(column_widths, start=1):
        ws.column_dimensions[chr(64 + i)].width = width

    ws.row_dimensions[1].height = 25

    # Freeze
    ws.freeze_panes = "A2"

    # -----------------------------------
    # ✅ LABOR DROPDOWN
    # -----------------------------------
    labor_options = [
        "Labor",
        "Labor 1 X (Flex Time)",
        "Labor 1 X (Bonus OT)",
        "Labor 1.5 X (Flex Time)",
        "Labor 1.5 X (Bonus OT)",
        "Labor 2 X (Flex Time)",
        "Labor 2 X (Bonus OT)",
        "Personal Vehicle Ground Travel",
        "Air Travel",
        "PTO (Gusto)",
        "PTO (Embedded Contract)",
        "PTO (Sabbatical)",
        "PTO (Flex Time)",
        "Disability",
        "Company Holiday"
    ]

    dv = DataValidation(
        type="list",
        formula1=f'"{",".join(labor_options)}"',
        allow_blank=True
    )
    # -----------------------------------
    # ✅ CUSTOMER DROPDOWN
    # -----------------------------------
    dv_customer = DataValidation(
        type="list",
        formula1=f'=Lookup!$A$1:$A${max_row_lookup}',
        allow_blank=True
    )

    ws.add_data_validation(dv_customer)
    dv_customer.add("D2:D200")

    ws.add_data_validation(dv)
    dv.add("E2:E200")

    return wb