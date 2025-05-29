import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QTextEdit, 
                            QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class SteganographyApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Текстовая стеганография")
        self.setGeometry(100, 100, 800, 600)
        
        self.init_ui()
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        # Верхняя панель - загрузка и сохранение файлов
        top_layout = QHBoxLayout()
        
        self.load_file_btn = QPushButton("Загрузить файл")
        self.load_file_btn.clicked.connect(self.load_file)
        
        self.save_file_btn = QPushButton("Сохранить файл")
        self.save_file_btn.clicked.connect(self.save_file)
        
        top_layout.addWidget(self.load_file_btn)
        top_layout.addWidget(self.save_file_btn)
        
        main_layout.addLayout(top_layout)
        
        # Средняя панель - исходный текст и секретное сообщение
        mid_layout = QHBoxLayout()
        
        # Левая часть - исходный текст
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Исходный текст:"))
        self.source_text = QTextEdit()
        left_layout.addWidget(self.source_text)
        
        # Правая часть - секретное сообщение
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Секретное сообщение:"))
        self.secret_message = QTextEdit()
        right_layout.addWidget(self.secret_message)
        
        mid_layout.addLayout(left_layout)
        mid_layout.addLayout(right_layout)
        
        main_layout.addLayout(mid_layout)
        
        # Нижняя панель - кнопки для встраивания и извлечения
        bottom_layout = QHBoxLayout()
        
        self.embed_btn = QPushButton("Встроить сообщение")
        self.embed_btn.clicked.connect(self.embed_message)
        
        self.extract_btn = QPushButton("Извлечь сообщение")
        self.extract_btn.clicked.connect(self.extract_message)
        
        bottom_layout.addWidget(self.embed_btn)
        bottom_layout.addWidget(self.extract_btn)
        
        main_layout.addLayout(bottom_layout)
        
        # Результат операции
        main_layout.addWidget(QLabel("Результат:"))
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        main_layout.addWidget(self.result_text)
    
    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Открыть текстовый файл", "", "Text Files (*.txt);;All Files (*)")
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    self.source_text.setText(content)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл: {str(e)}")
    
    def save_file(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить файл", "", "Text Files (*.txt);;All Files (*)")
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(self.result_text.toPlainText())
                QMessageBox.information(self, "Успех", "Файл успешно сохранен")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл: {str(e)}")
    
    def embed_message(self):
        cover_text = self.source_text.toPlainText()
        secret_msg = self.secret_message.toPlainText()
        
        if not cover_text or not secret_msg:
            QMessageBox.warning(self, "Предупреждение", "Необходимо заполнить оба текстовых поля")
            return
        
        # Конвертируем сообщение в двоичный код
        binary_message = ''.join(format(ord(char), '08b') for char in secret_msg)
        
        # Добавляем маркер конца сообщения (8 бит '1')
        binary_message += '11111111'
        
        # Разбиваем текст на слова
        words = cover_text.split()
        
        if len(binary_message) > len(words) - 1:
            QMessageBox.critical(self, "Ошибка", "Текст слишком короткий для встраивания сообщения")
            return
        
        # Встраиваем сообщение, изменяя количество пробелов между словами
        stego_text = words[0]
        for i in range(len(binary_message)):
            if binary_message[i] == '0':
                stego_text += ' ' + words[i + 1]  # Один пробел для бита '0'
            else:
                stego_text += '  ' + words[i + 1]  # Два пробела для бита '1'
        
        # Добавляем оставшиеся слова, если они есть
        if len(binary_message) < len(words) - 1:
            stego_text += ' ' + ' '.join(words[len(binary_message) + 1:])
        
        self.result_text.setText(stego_text)
        QMessageBox.information(self, "Успех", "Сообщение успешно встроено в текст")
    def extract_message(self):
        stego_text = self.source_text.toPlainText()
        
        if not stego_text:
            QMessageBox.warning(self, "Предупреждение", "Необходимо загрузить стегонограмму")
            return
        
        # Извлекаем биты из пробелов между словами
        binary_message = ''
        i = 0
        while i < len(stego_text):
            if stego_text[i] == ' ':
                # Проверяем, сколько пробелов подряд
                space_count = 0
                while i < len(stego_text) and stego_text[i] == ' ':
                    space_count += 1
                    i += 1
                
                if space_count == 1:
                    binary_message += '0'
                elif space_count == 2:
                    binary_message += '1'
            else:
                i += 1
        
        # Ищем маркер конца сообщения (8 бит '1')
        end_marker = '11111111'
        end_marker_index = binary_message.find(end_marker)
        
        if end_marker_index == -1:
            QMessageBox.warning(self, "Предупреждение", "Маркер конца сообщения не найден")
            return
        
        # Извлекаем только полезную часть сообщения (до маркера)
        binary_message = binary_message[:end_marker_index]
        
        # Преобразуем биты обратно в текст
        extracted_message = ''
        for i in range(0, len(binary_message), 8):
            if i + 8 <= len(binary_message):
                byte = binary_message[i:i+8]
                extracted_message += chr(int(byte, 2))
        
        self.secret_message.clear()
        self.result_text.setText(extracted_message)
        QMessageBox.information(self, "Успех", "Сообщение успешно извлечено")

def main():
    app = QApplication(sys.argv)
    window = SteganographyApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
