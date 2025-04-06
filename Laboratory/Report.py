from PyQt6.QtWidgets import QMainWindow, QMessageBox, QVBoxLayout, QTableWidget, QTableWidgetItem, QFileDialog, QStackedWidget, QButtonGroup
from PyQt6.QtCore import QDate
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from отчет import Ui_MainWindow
from PyQt6.QtGui import QPixmap


class ReportApp(QMainWindow):
    """Класс для генерации отчетов"""
    def __init__(self, db_connection, user_text, image_path, auth_window, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Установка фиксированного размера окна
        self.setFixedSize(596, 376)

        self.db_connection = db_connection
        self.auth_window = auth_window
        self.image_path = image_path

        # Инициализация интерфейса
        self.setup_ui(user_text)

        # Настройка кнопок
        self.setup_buttons()

        # Инициализация графиков и таблиц
        self.figure = plt.figure()
        self.canvas = FigureCanvas(self.figure)
        self.table_widget = QTableWidget()
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.canvas)
        self.stacked_widget.addWidget(self.table_widget)

        layout = QVBoxLayout()
        layout.addWidget(self.stacked_widget)
        self.ui.widget.setLayout(layout)

        self.ui.radioButton_2.setChecked(True)
        self.toggle_view()

    def setup_ui(self, user_text):
        """Настройка UI компонента."""
        self.ui.comboBox.addItems(["Контроль качества", "Отчет по услугам"])
        self.ui.dateEdit.setDate(QDate.currentDate().addMonths(-1))
        self.ui.dateEdit_2.setDate(QDate.currentDate())
        self.ui.label_2.setText(user_text)
        self.load_user_image()

    def load_user_image(self):
        """Загрузка изображения пользователя."""
        try:
            pixmap = QPixmap(self.image_path)
            if pixmap.isNull():
                raise FileNotFoundError(f"Изображение {self.image_path} не найдено.")
            self.ui.label.setPixmap(pixmap)
            self.ui.label.setScaledContents(True)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить изображение: {e}")

    def setup_buttons(self):
        """Настройка кнопок и сигналов."""
        self.ui.pushButton_4.clicked.connect(self.go_back)
        self.ui.pushButton_3.clicked.connect(self.go_to_auth)
        self.ui.pushButton_5.clicked.connect(self.generate_report)
        self.ui.pushButton_6.clicked.connect(self.export_to_pdf)

        self.button_group = QButtonGroup()
        self.button_group.addButton(self.ui.radioButton)
        self.button_group.addButton(self.ui.radioButton_2)
        self.button_group.buttonToggled.connect(self.toggle_view)

    def go_back(self):
        """Возврат к предыдущему окну."""
        self.parent().show()
        self.close()

    def go_to_auth(self):
        """Возврат к окну аутентификации."""
        self.auth_window.show()
        self.close()

    def toggle_view(self):
        """Переключение между графиком и таблицей."""
        if self.ui.radioButton.isChecked():
            self.stacked_widget.setCurrentIndex(0)
        else:
            self.stacked_widget.setCurrentIndex(1)

    def generate_report(self):
        """Генерация отчета на основе выбранных параметров."""
        report_type = self.ui.comboBox.currentText()
        start_date = self.ui.dateEdit.date().toString("yyyy-MM-dd")
        end_date = self.ui.dateEdit_2.date().toString("yyyy-MM-dd")

        if report_type == "Контроль качества":
            self.generate_quality_control_report(start_date, end_date)
        elif report_type == "Отчет по услугам":
            self.generate_service_report(start_date, end_date)

        self.save_report_log(report_type, start_date, end_date)

    def save_report_log(self, report_type, start_date, end_date):
        """Сохранение записи о сгенерированном отчете в БД."""
        try:
            cursor = self.db_connection.cursor()
            query = """
                INSERT INTO report_logs (report_type, start_date, end_date)
                VALUES (%s, %s, %s)
            """
            cursor.execute(query, (report_type, start_date, end_date))
            self.db_connection.commit()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при записи отчета в БД: {e}")
            self.db_connection.rollback()
        finally:
            cursor.close()

    def generate_quality_control_report(self, start_date, end_date):
        """Генерация отчета по контролю качества."""
        try:
            cursor = self.db_connection.cursor()
            query = """
                SELECT result, date FROM quality_control 
                WHERE date BETWEEN %s AND %s
            """
            cursor.execute(query, (start_date, end_date))
            results = cursor.fetchall()

            # Обработка полученных данных
            data = np.array([r[0] for r in results if r[0] is not None])
            if len(data) == 0:
                QMessageBox.warning(self, "Предупреждение", "Нет данных для выбранного периода.")
                return

            mean = np.mean(data)
            std_dev = np.std(data)
            cv = (std_dev / mean) * 100 if mean != 0 else 0
            limits = {
                '+1S': mean + std_dev,
                '+2S': mean + 2 * std_dev,
                '+3S': mean + 3 * std_dev,
                '-1S': mean - std_dev,
                '-2S': mean - 2 * std_dev,
                '-3S': mean - 3 * std_dev,
            }

            if self.ui.radioButton.isChecked():
                self.plot_quality_control_results(data, limits)
            else:
                self.populate_quality_table(mean, std_dev, limits, cv)
                self.stacked_widget.setCurrentIndex(1)

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при получении данных из базы данных: {e}")
        finally:
            cursor.close()

    def plot_quality_control_results(self, data, limits):
        """Отображение графика результатов контроля качества."""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(data, marker='o', color=(118 / 255, 227 / 255, 131 / 255), label="Результаты исследований")

        for limit_name, limit_value in limits.items():
            ax.axhline(limit_value, linestyle='--', color='grey', label=f'{limit_name} ({limit_value:.2f})')

        ax.set_xlabel("Номер исследования")
        ax.set_ylabel("Результат")
        ax.set_xlim(left=0, right=len(data) - 1)
        ax.set_ylim(bottom=min(data) - 1, top=max(data) + 1)

        self.figure.tight_layout()
        self.canvas.draw()
        self.stacked_widget.setCurrentIndex(0)

    def generate_service_report(self, start_date, end_date):
        """Генерация отчета по услугам."""
        try:
            cursor = self.db_connection.cursor()
            query = """
                SELECT COUNT(*) AS total_services,
                       COUNT(DISTINCT b.id_patient) AS total_patients
                FROM orders o
                JOIN biomaterial b ON o.id_biomaterial = b.id
                WHERE o.date_create BETWEEN %s AND %s;
            """
            cursor.execute(query, (start_date, end_date))
            result = cursor.fetchone()

            if result:
                total_services, total_patients = result
                if self.ui.radioButton.isChecked():
                    self.plot_service_report(total_services, total_patients)
                else:
                    self.populate_service_table(total_services, total_patients)
                    self.stacked_widget.setCurrentIndex(1)
            else:
                QMessageBox.warning(self, "Предупреждение", "Нет данных для выбранного периода.")

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при получении данных из базы данных: {e}")
        finally:
            cursor.close()

    def plot_service_report(self, total_services, total_patients):
        """Отображение графика отчета по услугам."""
        self.figure.clear()
        self.figure.set_size_inches(5, 2)
        ax = self.figure.add_subplot(111)
        ax.bar(['Общее количество услуг', 'Общее количество пациентов'],
               [total_services, total_patients],
               color=(118 / 255, 227 / 255, 131 / 255))
        ax.set_xlabel("Параметры")
        ax.set_ylabel("Количество")
        ax.set_ylim(0, max(total_services, total_patients) + 20)

        self.figure.tight_layout()
        self.canvas.draw()
        self.stacked_widget.setCurrentIndex(0)

    def populate_quality_table(self, mean, std_dev, limits, cv):
        """Заполнение таблицы результатов контроля качества."""
        self.table_widget.clear()
        self.table_widget.setRowCount(7)
        self.table_widget.setColumnCount(2)
        self.table_widget.setHorizontalHeaderLabels(["Параметр", "Значение"])

        self.table_widget.setItem(0, 0, QTableWidgetItem("Среднее значение"))
        self.table_widget.setItem(0, 1, QTableWidgetItem(str(mean)))
        self.table_widget.setItem(1, 0, QTableWidgetItem("Стандартное отклонение"))
        self.table_widget.setItem(1, 1, QTableWidgetItem(str(std_dev)))
        self.table_widget.setItem(2, 0, QTableWidgetItem("Коэффициент вариации (%)"))
        self.table_widget.setItem(2, 1, QTableWidgetItem(str(cv)))

        limits_list = list(limits.items())
        for i in range(min(5, len(limits_list))):
            self.table_widget.setItem(i + 3, 0, QTableWidgetItem(limits_list[i][0]))
            self.table_widget.setItem(i + 3, 1, QTableWidgetItem(str(limits_list[i][1])))

        self.table_widget.setColumnWidth(0, 200)
        self.table_widget.setColumnWidth(1, 285)

    def populate_service_table(self, total_services, total_patients):
        """Заполнение таблицы отчета по услугам."""
        self.table_widget.clear()
        self.table_widget.setRowCount(2)
        self.table_widget.setColumnCount(2)
        self.table_widget.setHorizontalHeaderLabels(["Параметр", "Значение"])

        self.table_widget.setItem(0, 0, QTableWidgetItem("Общее количество услуг"))
        self.table_widget.setItem(0, 1, QTableWidgetItem(str(total_services)))
        self.table_widget.setItem(1, 0, QTableWidgetItem("Общее количество пациентов"))
        self.table_widget.setItem(1, 1, QTableWidgetItem(str(total_patients)))

        self.table_widget.setColumnWidth(0, 240)
        self.table_widget.setColumnWidth(1, 245)

    def export_to_pdf(self):
        """Экспорт результата в PDF файл."""
        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить отчет", "", "PDF Files (*.pdf)")

        if file_path:
            try:
                pdf_canvas = canvas.Canvas(file_path, pagesize=A4)

                pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
                pdf_canvas.setFont("DejaVuSans", 12)

                pdf_canvas.drawString(100, 800, "Отчет лаборатории")
                pdf_canvas.drawString(100, 780, f"Тип отчета: {self.ui.comboBox.currentText()}")

                if self.ui.radioButton.isChecked():
                    self.figure.savefig("temp_graph.png", dpi=300)
                    pdf_canvas.drawImage("temp_graph.png", 100, 500, width=400, height=250)
                else:
                    self.export_table_to_pdf(pdf_canvas)

                pdf_canvas.save()
                QMessageBox.information(self, "Успех", "Отчет успешно сохранен.")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Произошла ошибка при создании PDF: {e}")

    def export_table_to_pdf(self, pdf_canvas):
        """Экспорт данных из таблицы в PDF файл."""
        table_data = []
        for row in range(self.table_widget.rowCount()):
            row_data = []
            for col in range(self.table_widget.columnCount()):
                item = self.table_widget.item(row, col)
                if item is not None:
                    row_data.append(item.text())
            table_data.append(row_data)

        x = 100
        y = 500
        for row in table_data:
            for col, text in enumerate(row):
                pdf_canvas.drawString(x + col * 100, y, text)
            y -= 20