import os
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4  # Или ваш размер

# Глобальные размеры (оставляем как было)
BARCODE_HEIGHT = 22.85 * mm
BARCODE_EXTRA_HEIGHT = 1.65 * mm
DIGIT_HEIGHT = 2.75 * mm
TOP_MARGIN = 0.165 * mm
BAR_WIDTH_BASE = 0.15 * mm
SPACE_BETWEEN_BARS = 0.2 * mm
ZERO_WIDTH = 1.35 * mm
GUARD_BAR_WIDTH = 0.15 * mm

# Пути для сохранения
PDF_DIR = "barcodes\pdf"
os.makedirs(PDF_DIR, exist_ok=True)


def generate_barcode_pdf(barcode_data):
    """Создает PDF со штрих-кодом (без PNG)."""
    pdf_filename = os.path.join(PDF_DIR, f"barcode{barcode_data[:4]}.pdf")

    # Настройка PDF (70x40 мм как в вашем коде)
    c = canvas.Canvas(pdf_filename, pagesize=(70 * mm, 40 * mm))

    # Рассчет ширины штрих-кода (как раньше)
    total_width = 3.63 * mm + 2.31 * mm  # Отступы
    for section in (barcode_data[4:10], barcode_data[10:]):
        total_width += 2 * GUARD_BAR_WIDTH + SPACE_BETWEEN_BARS
        total_width += sum((ZERO_WIDTH if d == "0" else BAR_WIDTH_BASE * int(d)) + SPACE_BETWEEN_BARS
                           for d in section)
    total_width += 2 * GUARD_BAR_WIDTH

    # Коэффициент растяжения (чтобы заполнить ширину)
    target_width = 65 * mm - 3.63 * mm - 2.31 * mm
    scale_factor = target_width / (total_width - 3.63 * mm - 2.31 * mm)

    # Рисуем штрих-код
    x = 3.63 * mm
    y = 10 * mm  # Отступ сверху

    def draw_guard_bars(extended=True):
        nonlocal x
        y_offset = BARCODE_EXTRA_HEIGHT if extended else 0  # Смещаем вниз
        for _ in range(2):
            c.rect(x, y - y_offset, GUARD_BAR_WIDTH * scale_factor, BARCODE_HEIGHT + y_offset, fill=1)
            x += (GUARD_BAR_WIDTH + SPACE_BETWEEN_BARS) * scale_factor

    # Ограничители (удлиненные)
    draw_guard_bars(extended=True)

    # Основные штрихи
    for section in (barcode_data[4:10], barcode_data[10:]):
        for digit in section:
            if digit == "0":
                x += (ZERO_WIDTH + SPACE_BETWEEN_BARS) * scale_factor
            else:
                width = BAR_WIDTH_BASE * int(digit) * scale_factor
                c.rect(x, y, width, BARCODE_HEIGHT, fill=1)
                x += (BAR_WIDTH_BASE * int(digit) + SPACE_BETWEEN_BARS) * scale_factor
        draw_guard_bars(extended=True)

    # Текст
    c.setFont("Helvetica", 11)
    text = f"{barcode_data[:4]} {barcode_data[4:10]} {barcode_data[10:]}"
    text_width = c.stringWidth(text, "Helvetica", 11)
    c.drawString((70 * mm - text_width) / 2, 4 * mm, text)

    c.save()
    print(f"✅ PDF со штрих-кодом сохранен в {pdf_filename}")
    return pdf_filename