"""Print the operation cells with the same layout for paper and PDF."""

from dataclasses import dataclass
from html import escape
from math import floor

from PySide6.QtCore import QMarginsF, QRectF, Qt
from PySide6.QtGui import QFont, QFontMetricsF, QPageLayout, QPageSize, QPainter, QTextDocument, QTextOption
from PySide6.QtPrintSupport import QAbstractPrintDialog, QPrintDialog, QPrinter
from PySide6.QtWidgets import QDialog


@dataclass(frozen=True)
class PrintColumn:
    heading: str
    width: int
    numeric: bool = False


def _overview_markup(overview, column_count):
    span, extra = divmod(column_count, len(overview))
    cells = "".join(
        f'<td colspan="{span + (index < extra)}" bgcolor="#f3f5f7">'
        f'{escape(label)}&nbsp;&nbsp;<b>{escape(value)}</b></td>'
        for index, (label, value) in enumerate(overview)
    )
    return f"<tr>{cells}</tr>"


def _table_markup(columns, rows, overview, page_width):
    total_width = sum(column.width for column in columns)
    font = QFont("Arial")
    font.setPixelSize(9)
    metrics = QFontMetricsF(font)
    widths = [max(page_width * column.width / total_width, metrics.horizontalAdvance(column.heading) + 12)
              for column in columns]
    for row in rows:
        for index, lines in enumerate(row):
            for value in lines[:2]:
                widths[index] = max(widths[index], 17 + metrics.horizontalAdvance(value))
    total_width = sum(widths)
    widths = [page_width * width / total_width for width in widths]
    headings = "".join(
        f'<th width="{100 * width / page_width:.4f}%" bgcolor="#ebeff3" '
        f'align="{"right" if column.numeric else "left"}">{escape(column.heading)}</th>'
        for column, width in zip(columns, widths)
    )
    body = []
    for row in rows:
        cells = []
        for column, width, lines in zip(columns, widths, row):
            available = width - 17
            compact = []
            for value in lines[:2]:
                if not value:
                    continue
                measured = max(metrics.horizontalAdvance(value), 1)
                size = max(1, min(9, floor(9 * available / measured)))
                compact.append(f'<nobr><span style="font-size:{size}px">{escape(value)}</span></nobr>')
            if len(lines) > 2 and lines[2]:
                note = escape(lines[2], quote=False).replace("\n", "<br/>")
                compact.append(f'<span style="font-size:8px">{note}</span>')
            content = "<br/>".join(compact)
            cells.append(f'<td align="{"right" if column.numeric else "left"}">{content}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    header = ('<body style="font-family:Arial,sans-serif;font-size:9px;color:#18212a;">'
              '<table border="1" cellspacing="0" cellpadding="2" width="100%" style="border-color:#a4aeb8;">'
              f"<thead>{_overview_markup(overview, len(columns))}<tr>{headings}</tr></thead><tbody>")
    return header, body


def _printer():
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPageLayout(QPageLayout(
        QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Landscape,
        QMarginsF(10, 10, 10, 10), QPageLayout.Unit.Millimeter,
    ))
    return printer


def _document(width, header, rows):
    document = QTextDocument()
    document.setDocumentMargin(0)
    option = document.defaultTextOption()
    option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    document.setDefaultTextOption(option)
    document.setHtml(header + "".join(rows) + "</tbody></table></body>")
    document.setTextWidth(width)
    return document


def _pages(size, header, rows):
    first = 0
    while first < len(rows):
        low = first + 1
        high = min(len(rows), first + max(1, int(size.height() / 12)))
        fit = None
        while low <= high:
            end = (low + high) // 2
            document = _document(size.width(), header, rows[first:end])
            if document.size().height() <= size.height():
                fit = (end, document)
                low = end + 1
            else:
                high = end - 1
        if fit is not None:
            first, document = fit
            yield document, 0
        else:
            # A single operation can contain a note longer than a page.
            document = _document(size.width(), header, rows[first:first + 1])
            document.setPageSize(size)
            for index in range(document.pageCount()):
                yield document, index * size.height()
            first += 1


def _print_table(printer, columns, rows, overview):
    size = printer.pageRect(QPrinter.Unit.Point).size()
    if size.isEmpty():
        raise OSError("Избраният принтер няма достъпна област за печат.")
    header, body = _table_markup(columns, rows, overview, size.width())
    painter = QPainter()
    if not painter.begin(printer):
        raise OSError("Таблицата не можа да се отпечата.")
    try:
        scale = printer.resolution() / 72
        for index, (document, offset) in enumerate(_pages(size, header, body)):
            if index and not printer.newPage():
                raise OSError("Следващата страница не можа да се отпечата.")
            painter.save()
            painter.scale(scale, scale)
            painter.translate(0, -offset)
            document.drawContents(painter, QRectF(0, offset, size.width(), size.height()))
            painter.restore()
    finally:
        painter.end()
    if printer.printerState() in (QPrinter.PrinterState.Error, QPrinter.PrinterState.Aborted):
        raise OSError("Таблицата не можа да се отпечата.")


def print_table(columns, rows, overview) -> bool:
    printer = _printer()
    dialog = QPrintDialog(printer)
    dialog.setOption(QAbstractPrintDialog.PrintDialogOption.PrintPageRange, False)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    _print_table(printer, columns, rows, overview)
    return True
