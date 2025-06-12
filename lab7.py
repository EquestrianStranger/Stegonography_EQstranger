import sys
import numpy as np
from PIL import Image
from scipy.stats import chi2  # Добавьте этот импорт
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QTextEdit, QFileDialog, QSpinBox,
                             QTabWidget, QGroupBox, QMessageBox, QComboBox, QInputDialog)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt
from steganographer import Steganographer


class SteganographyApp(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Стеганографическая программа")
        self.setGeometry(100, 100, 800, 600)
        
        # Основные переменные
        self.original_image = None
        self.stego_image = None
        self.image_path = ""
        
        self.init_ui()

    @classmethod
    def from_image(cls, image):
        """Создает экземпляр из объекта PIL.Image"""
        import tempfile
        import os
        try:
            temp_path = "temp_image_" + str(os.getpid()) + ".png"
            image.save(temp_path)
            instance = cls(temp_path)
            return instance
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
    def init_ui(self):
        # Создаем главный виджет и layout
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        
        # Создаем вкладки
        tabs = QTabWidget()
        
        # Вкладка для встраивания сообщения
        embed_tab = QWidget()
        self.setup_embed_tab(embed_tab)
        
        # Вкладка для извлечения сообщения
        extract_tab = QWidget()
        self.setup_extract_tab(extract_tab)
        
        # Вкладка для анализа
        analyze_tab = QWidget()
        self.setup_analyze_tab(analyze_tab)
        
        # Добавляем вкладки
        tabs.addTab(embed_tab, "Встраивание")
        tabs.addTab(extract_tab, "Извлечение")
        tabs.addTab(analyze_tab, "Анализ")
        
        # Добавляем вкладки в основной layout
        main_layout.addWidget(tabs)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
    
    def setup_embed_tab(self, tab):
        layout = QVBoxLayout()
        
        # Группа для выбора изображения
        image_group = QGroupBox("Изображение-контейнер")
        image_layout = QVBoxLayout()
        
        self.image_label = QLabel("Изображение не выбрано")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFixedHeight(200)
        
        btn_load_image = QPushButton("Выбрать изображение")
        btn_load_image.clicked.connect(self.load_image)
        
        image_layout.addWidget(self.image_label)
        image_layout.addWidget(btn_load_image)
        image_group.setLayout(image_layout)

        # Группа для сравнения ёмкости
        capacity_group = QGroupBox("Сравнение ёмкости")
        capacity_layout = QVBoxLayout()

        self.capacity_label = QTextEdit()
        self.capacity_label.setReadOnly(True)

        capacity_layout.addWidget(self.capacity_label)
        capacity_group.setLayout(capacity_layout)
        
        # Группа для ввода сообщения
        message_group = QGroupBox("Сообщение для встраивания")
        message_layout = QVBoxLayout()
        
        self.message_edit = QTextEdit()
        self.message_edit.setPlaceholderText("Введите текст для встраивания...")
        
        message_layout.addWidget(self.message_edit)
        message_group.setLayout(message_layout)
        
        # Группа для параметров
        params_group = QGroupBox("Параметры встраивания")
        params_layout = QHBoxLayout()
        
        self.seed_spinbox = QSpinBox()
        self.seed_spinbox.setRange(0, 999999)
        self.seed_spinbox.setValue(12345)
        
        self.method_combo = QComboBox()
        self.method_combo.addItems(["Базовый метод", "Метод с хэшированием"])
        
        params_layout.addWidget(QLabel("Ключ (seed):"))
        params_layout.addWidget(self.seed_spinbox)
        params_layout.addWidget(QLabel("Метод:"))
        params_layout.addWidget(self.method_combo)
        params_group.setLayout(params_layout)
        
        # Кнопка встраивания
        btn_embed = QPushButton("Встроить сообщение")
        btn_embed.clicked.connect(self.embed_message)
        
        # Добавляем все группы в layout
        layout.addWidget(image_group)
        layout.addWidget(capacity_group)
        layout.addWidget(message_group)
        layout.addWidget(params_group)
        layout.addWidget(btn_embed)
        layout.addStretch()
        
        tab.setLayout(layout)
    
    def setup_extract_tab(self, tab):
        layout = QVBoxLayout()
        
        # Группа для выбора стего-изображения
        stego_group = QGroupBox("Стего-изображение")
        stego_layout = QVBoxLayout()
        
        self.stego_label = QLabel("Изображение не выбрано")
        self.stego_label.setAlignment(Qt.AlignCenter)
        self.stego_label.setFixedHeight(200)
        
        btn_load_stego = QPushButton("Выбрать стего-изображение")
        btn_load_stego.clicked.connect(self.load_stego_image)
        
        stego_layout.addWidget(self.stego_label)
        stego_layout.addWidget(btn_load_stego)
        stego_group.setLayout(stego_layout)
        
        # Группа для параметров извлечения
        extract_params_group = QGroupBox("Параметры извлечения")
        extract_params_layout = QHBoxLayout()
        
        self.extract_seed_spinbox = QSpinBox()
        self.extract_seed_spinbox.setRange(0, 999999)
        self.extract_seed_spinbox.setValue(12345)
        
        self.extract_method_combo = QComboBox()
        self.extract_method_combo.addItems(["Базовый метод", "Метод с хэшированием"])
        
        extract_params_layout.addWidget(QLabel("Ключ (seed):"))
        extract_params_layout.addWidget(self.extract_seed_spinbox)
        extract_params_layout.addWidget(QLabel("Метод:"))
        extract_params_layout.addWidget(self.extract_method_combo)
        extract_params_group.setLayout(extract_params_layout)
        
        # Кнопка извлечения
        btn_extract = QPushButton("Извлечь сообщение")
        btn_extract.clicked.connect(self.extract_message)
        
        # Поле для вывода извлеченного сообщения
        self.extracted_message = QTextEdit()
        self.extracted_message.setReadOnly(True)
        self.extracted_message.setPlaceholderText("Здесь появится извлеченное сообщение...")
        
        # Добавляем все группы в layout
        layout.addWidget(stego_group)
        layout.addWidget(extract_params_group)
        layout.addWidget(btn_extract)
        layout.addWidget(self.extracted_message)
        
        tab.setLayout(layout)
    
    def setup_analyze_tab(self, tab):
        layout = QVBoxLayout()
        
        # Группа для анализа
        analyze_group = QGroupBox("Анализ стего-изображения")
        analyze_layout = QVBoxLayout()
        
        btn_analyze = QPushButton("Проанализировать LSB")
        btn_analyze.clicked.connect(self.analyze_lsb)
        
        self.analysis_result = QTextEdit()
        self.analysis_result.setReadOnly(True)
        
        analyze_layout.addWidget(btn_analyze)
        analyze_layout.addWidget(self.analysis_result)
        analyze_group.setLayout(analyze_layout)
        
        # Группа для сравнения
        compare_group = QGroupBox("Сравнение с оригиналом")
        compare_layout = QVBoxLayout()
        
        btn_load_original = QPushButton("Выбрать оригинал")
        btn_load_original.clicked.connect(self.load_original_for_compare)
        
        btn_compare = QPushButton("Сравнить изображения")
        btn_compare.clicked.connect(self.compare_images)
        
        self.compare_result = QTextEdit()
        self.compare_result.setReadOnly(True)
        
        compare_layout.addWidget(btn_load_original)
        compare_layout.addWidget(btn_compare)
        compare_layout.addWidget(self.compare_result)
        compare_group.setLayout(compare_layout)
        
        # Добавляем группы в layout
        layout.addWidget(analyze_group)
        layout.addWidget(compare_group)
        layout.addStretch()
        
        tab.setLayout(layout)
    
    def load_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите изображение", "", "Images (*.png *.jpg *.bmp)")
        if file_path:
            self.image_path = file_path
            self.original_image = Image.open(file_path)
            
            # Показываем превью изображения
            pixmap = QPixmap(file_path)
            pixmap = pixmap.scaled(400, 200, Qt.KeepAspectRatio)
            self.image_label.setPixmap(pixmap)
    
    def load_stego_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите стего-изображение", "", "Images (*.png *.jpg *.bmp)")
        if file_path:
            self.stego_image = Image.open(file_path)
            
            # Показываем превью изображения
            pixmap = QPixmap(file_path)
            pixmap = pixmap.scaled(400, 200, Qt.KeepAspectRatio)
            self.stego_label.setPixmap(pixmap)
    
    def load_original_for_compare(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите оригинальное изображение", "", "Images (*.png *.jpg *.bmp)")
        if file_path:
            self.original_for_compare = Image.open(file_path)
            QMessageBox.information(self, "Успех", "Оригинальное изображение загружено")
    
    def embed_message(self):
        # Проверка наличия изображения
        if not hasattr(self, 'original_image') or self.original_image is None:
            QMessageBox.warning(self, "Ошибка", "Сначала выберите изображение!")
            return
        
        # Получаем текст из поля ввода (критически важная строка!)
        message = self.message_edit.toPlainText()
        
        # Проверка наличия сообщения
        if not message.strip():
            QMessageBox.warning(self, "Ошибка", "Введите сообщение для встраивания!")
            return
        
        seed = self.seed_spinbox.value()
        method = self.method_combo.currentText()

        
        temp_path = None
        try:
            # Создаём временный файл
            temp_path = f"temp_image_{os.getpid()}.png"
            self.original_image.save(temp_path)
            
            stego = Steganographer(temp_path)

            text_bytes = message.encode('utf-8')
            basic_bits = len(text_bytes) * 8
            enhanced_bits = basic_bits + (basic_bits // 64) * 16  # +16 бит хэша на каждый 64-битный блок

            # Выводим сравнение в интерфейс (добавьте QLabel в GUI)
            self.capacity_label.setText(
                f"Ёмкость:\n"
                f"• Базовый метод: {basic_bits} бит ({basic_bits//8} символов)\n"
                f"• С хэшем: {enhanced_bits} бит ({enhanced_bits//8} символов)\n"
                f"• Максимум в изображении: {stego.pixels.size} бит"
            )
            
            
            # Вычисление размера сообщения (теперь message точно определена)
            required_bits = len(message.encode('utf-8')) * 8
            
            if method == "Базовый метод":
                max_bits = stego.pixels.size
                
                if required_bits > max_bits:
                    QMessageBox.warning(
                        self, 
                        "Ошибка", 
                        f"Сообщение слишком длинное. Максимум: {max_bits//8} символов"
                    )
                    return
                    
                result_image = stego.embed_basic(message, seed)
            else:
                result_image = stego.embed_enhanced(message, seed)
            
            # Сохраняем результат
            save_path, _ = QFileDialog.getSaveFileName(
                self, 
                "Сохранить стего-изображение", 
                "", 
                "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg);;Bitmap Image (*.bmp)"
            )
            
            if save_path:
                file_format = os.path.splitext(save_path)[1][1:].upper()
                if file_format == 'JPG':
                    file_format = 'JPEG'
                result_image.save(save_path, format=file_format)
                QMessageBox.information(self, "Успех", "Сообщение успешно встроено!")
        
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка: {str(e)}")
        
        finally:
            # Гарантированно удаляем временный файл
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e:
                    print(f"Ошибка при удалении временного файла: {str(e)}")
    
    def extract_message(self):
        if not self.stego_image:
            QMessageBox.warning(self, "Ошибка", "Сначала выберите стего-изображение!")
            return
        
        seed = self.extract_seed_spinbox.value()
        method = self.extract_method_combo.currentText()
        
        try:
            stego = Steganographer.from_image(self.stego_image)
            
            if method == "Базовый метод":
                length, ok = QInputDialog.getInt(
                    self, 
                    "Длина сообщения", 
                    "Введите длину сообщения в битах:", 
                    100, 1, stego.pixels.size, 1
                )
                if not ok:
                    return
                
                extracted_text = stego.extract_basic(seed, length)
            else:
                extracted_text, error = stego.extract_enhanced(seed)
                if error:
                    QMessageBox.warning(self, "Предупреждение", 
                                    "При извлечении обнаружены ошибки в данных!")
            
            self.extracted_message.setPlainText(extracted_text)
        
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка: {str(e)}")
    
    def analyze_lsb(self):
        if not hasattr(self, 'stego_image') or self.stego_image is None:
            QMessageBox.warning(self, "Ошибка", "Сначала загрузите стего-изображение!")
            return

        try:
            # Создаем временный файл
            temp_path = f"temp_analysis_{os.getpid()}.png"
            self.stego_image.save(temp_path)
            
            # Анализируем
            stego = Steganographer(temp_path)
            
            # Получаем результаты
            lsb_dist = stego.analyze_lsb_distribution()
            chi2_result = stego.chi_square_test()
            
            # Формируем отчет
            report = (
                f"=== Анализ LSB ===\n"
                f"Среднее значение LSB: {np.mean(lsb_dist):.4f}\n"
                f"Дисперсия LSB: {np.var(lsb_dist):.4f}\n"
                f"χ² тест (p-value): {chi2_result:.4f}\n\n"
            )
            
            # Интерпретация результатов
            if chi2_result < 0.05:
                report += "ВЫВОД: Обнаружены признаки стегосообщения (p < 0.05)"
            else:
                report += "ВЫВОД: Стегосообщение не обнаружено (p ≥ 0.05)"
            
            self.analysis_result.setPlainText(report)
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка анализа: {str(e)}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        # import matplotlib.pyplot as plt
        #     plt.imshow(lsb_dist, cmap='hot', interpolation='nearest')
        #     plt.colorbar()
        #     plt.title("Распределение LSB")
        #     plt.show()
    
    def compare_images(self):
        """Сравнивает оригинальное и стего-изображение"""
        if not hasattr(self, 'original_for_compare') or self.original_for_compare is None:
            QMessageBox.warning(self, "Ошибка", "Сначала загрузите оригинальное изображение!")
            return
            
        if not hasattr(self, 'stego_image') or self.stego_image is None:
            QMessageBox.warning(self, "Ошибка", "Сначала загрузите стего-изображение!")
            return

        try:
            # Создаем временные файлы для сравнения
            original_path = f"temp_original_{os.getpid()}.png"
            stego_path = f"temp_stego_{os.getpid()}.png"
            
            self.original_for_compare.save(original_path)
            self.stego_image.save(stego_path)
            
            # Сравниваем изображения
            stego = Steganographer(stego_path)
            metrics = stego.compare_containers(original_path, stego_path)
            
            # Формируем отчет
            report = (
                "=== Результаты сравнения ===\n"
                f"MSE: {metrics['mse']:.2f}\n"
                f"PSNR: {metrics['psnr']:.2f} dB\n"
                f"Измененные пиксели: {metrics['changed_pixels']}\n"
                f"Измененные LSB: {metrics['lsb_changes']}\n"
            )
            
            self.compare_result.setPlainText(report)
            
            # Показываем визуализацию
            diff_image = stego.visualize_changes(original_path, stego_path)
            diff_image.show()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка сравнения", f"Ошибка: {str(e)}")
        finally:
            # Удаляем временные файлы
            for path in [original_path, stego_path]:
                if 'path' in locals() and os.path.exists(path):
                    os.remove(path)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SteganographyApp()
    window.show()
    sys.exit(app.exec_())