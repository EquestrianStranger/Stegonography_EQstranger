import sys, os
import numpy as np
import difflib
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, QMessageBox, QTabWidget, QPlainTextEdit, QDoubleSpinBox, QLineEdit, QGroupBox
from PyQt6.QtGui import QPixmap, QImage, QColor
from PyQt6.QtCore import Qt

END_MARKER = b"\xfe\x00\xff\xfa"

def text_to_bits_with_marker(text: str) -> list[int]:
    data = text.encode('utf-8', errors='replace')
    data_marker = data + END_MARKER
    bits = []
    for byte in data_marker:
        for i in range(8):
            bit = (byte >> (7 - i)) & 1
            bits.append(bit)
    return bits

def bits_to_text_with_marker(bits: list[int]) -> str:
    if not bits:
        return ""
    r = len(bits) % 8
    if r != 0:
        bits += [0]*(8-r)
    raw_bytes = bytearray()
    for i in range(0, len(bits), 8):
        val = 0
        for b in bits[i:i+8]:
            val = (val << 1) | b
        raw_bytes.append(val)
    idx_marker = raw_bytes.find(END_MARKER)
    if idx_marker < 0:
        payload = raw_bytes
    else:
        payload = raw_bytes[:idx_marker]
    text = payload.decode('utf-8', errors='replace')
    return text

def brightness(r, g, b):
    return 0.299*r + 0.587*g + 0.114*b

def embed_kjb(cover: QImage, bits: list[int], lam: float, seed: int):
    if cover.isNull():
        return QImage(), []
    w, h = cover.width(), cover.height()
    total_pixels = w * h
    if len(bits) > total_pixels:
        return QImage(), []
    cover = cover.convertToFormat(QImage.Format.Format_RGB888)
    result = QImage(cover)
    rng = np.random.default_rng(seed)
    all_indices = np.arange(total_pixels)
    rng.shuffle(all_indices)
    used_indices = all_indices[:len(bits)]
    for i, bit_val in enumerate(bits):
        lin = used_indices[i]
        y = lin // w
        x = lin % w
        c = result.pixelColor(x, y)
        R, G, B_ = c.red(), c.green(), c.blue()
        Y = brightness(R, G, B_)
        if bit_val == 1:
            B_new = B_ + lam * Y
        else:
            B_new = B_ - lam * Y
        if B_new < 0:
            B_new = 0
        elif B_new > 255:
            B_new = 255
        c.setBlue(int(B_new))
        result.setPixelColor(x, y, c)
    return result, used_indices

def extract_kjb(img: QImage, lam: float, seed: int) -> list[int]:
    if img.isNull():
        return []
    w, h = img.width(), img.height()
    total_pixels = w * h
    img = img.convertToFormat(QImage.Format.Format_RGB888)
    rng = np.random.default_rng(seed)
    all_indices = np.arange(total_pixels)
    rng.shuffle(all_indices)
    bits = []
    for i in range(total_pixels):
        lin = all_indices[i]
        y = lin // w
        x = lin % w
        c = img.pixelColor(x, y)
        B_val = c.blue()
        neighbors = []
        if x > 0:
            neighbors.append(img.pixelColor(x - 1, y).blue())
        if x < w - 1:
            neighbors.append(img.pixelColor(x + 1, y).blue())
        if y > 0:
            neighbors.append(img.pixelColor(x, y - 1).blue())
        if y < h - 1:
            neighbors.append(img.pixelColor(x, y + 1).blue())
        if neighbors:
            b_est = sum(neighbors) / len(neighbors)
        else:
            b_est = B_val
        bit = 1 if B_val >= b_est else 0
        bits.append(bit)
    return bits

def measure_blue_diff(original: QImage, watermarked: QImage) -> float:
    if original.isNull() or watermarked.isNull():
        return 0.0
    w1, h1 = original.width(), original.height()
    w2, h2 = watermarked.width(), watermarked.height()
    if (w1 != w2) or (h1 != h2):
        return 0.0
    orig = original.convertToFormat(QImage.Format.Format_RGB888)
    wtm = watermarked.convertToFormat(QImage.Format.Format_RGB888)
    total_pixels = w1 * h1
    diff_sum = 0
    for y in range(h1):
        for x in range(w1):
            b1 = orig.pixelColor(x, y).blue()
            b2 = wtm.pixelColor(x, y).blue()
            diff_sum += abs(b1 - b2)
    return diff_sum / total_pixels

def measure_changed_only(original: QImage, watermarked: QImage, used_indices: np.ndarray) -> float:
    if original.isNull() or watermarked.isNull() or used_indices.size == 0:
        return 0.0
    w1, h1 = original.width(), original.height()
    w2, h2 = watermarked.width(), watermarked.height()
    if (w1 != w2) or (h1 != h2):
        return 0.0
    orig = original.convertToFormat(QImage.Format.Format_RGB888)
    wtm = watermarked.convertToFormat(QImage.Format.Format_RGB888)
    diff_sum = 0
    for lin in used_indices:
        y = lin // w1
        x = lin % w1
        b1 = orig.pixelColor(x, y).blue()
        b2 = wtm.pixelColor(x, y).blue()
        diff_sum += abs(b1 - b2)
    return diff_sum / used_indices.size

class KJBApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
        QMainWindow {
            background-color: #f0f0f0;
        }
        QGroupBox {
            border: 1px solid gray;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 15px;
        }
        QPushButton {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 8px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
        """)
        self.setWindowTitle("KJB")
        self.resize(1200, 600)
        self.cover_image = QImage()
        self.watermarked_image = QImage()
        self.used_indices = np.array([], dtype=np.int64)
        self.last_text_embed = ""
        self.last_saved_file = ""
        self.init_ui()

    def init_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tab_embed = QWidget()
        self.tabs.addTab(self.tab_embed, "Встраивание")
        self.init_tab_embed()
        self.tab_extract = QWidget()
        self.tabs.addTab(self.tab_extract, "Извлечение")
        self.init_tab_extract()

    def init_tab_embed(self):
        layout = QHBoxLayout(self.tab_embed)
        panel = QWidget()
        pv = QVBoxLayout(panel)
        self.btn_load_cover = QPushButton("Загрузить оригинал")
        self.btn_load_cover.clicked.connect(self.load_cover_image)
        pv.addWidget(self.btn_load_cover)
        self.lbl_cover_path = QLabel("Файл не выбран")
        pv.addWidget(self.lbl_cover_path)
        self.txt_input = QPlainTextEdit()
        self.txt_input.setPlaceholderText("Введите сообщение")
        pv.addWidget(self.txt_input)
        group_lam = QGroupBox("λ (энергия)")
        lam_lay = QHBoxLayout(group_lam)
        self.spin_lambda = QDoubleSpinBox()
        self.spin_lambda.setRange(0.01, 10.0)
        self.spin_lambda.setSingleStep(0.01)
        self.spin_lambda.setValue(0.1)
        lam_lay.addWidget(self.spin_lambda)
        pv.addWidget(group_lam)
        group_seed = QGroupBox("Seed (псевдослучайность)")
        s_lay = QHBoxLayout(group_seed)
        self.seed_line = QLineEdit("12345")
        s_lay.addWidget(self.seed_line)
        pv.addWidget(group_seed)
        self.btn_embed = QPushButton("Встроить")
        self.btn_embed.clicked.connect(self.do_embed)
        pv.addWidget(self.btn_embed)
        self.btn_save = QPushButton("Сохранить результат")
        self.btn_save.clicked.connect(self.save_result)
        pv.addWidget(self.btn_save)
        self.lbl_diff_all = QLabel("Изменение по всем пикселям: -")
        pv.addWidget(self.lbl_diff_all)
        self.lbl_diff_changed = QLabel("Изменение только в изменённых: -")
        pv.addWidget(self.lbl_diff_changed)
        pv.addStretch(1)
        layout.addWidget(panel, 0)
        img_panel = QWidget()
        ip = QHBoxLayout(img_panel)
        self.lbl_cover_show = QLabel("Исходное")
        self.lbl_cover_show.setFixedSize(400, 400)
        self.lbl_cover_show.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ip.addWidget(self.lbl_cover_show)
        self.lbl_embed_show = QLabel("Встроенное")
        self.lbl_embed_show.setFixedSize(400, 400)
        self.lbl_embed_show.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ip.addWidget(self.lbl_embed_show)
        layout.addWidget(img_panel, 1)

    def load_cover_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите исходное изображение", "", "Images (*.png *.jpg *.jpeg *.bmp *.pgm);;All Files (*)")
        if path:
            tmp = QImage(path)
            if tmp.isNull():
                QMessageBox.warning(self, "Ошибка", "Не удалось загрузить изображение!")
                return
            self.cover_image = tmp
            self.lbl_cover_path.setText(path)
            pix = QPixmap.fromImage(tmp).scaled(self.lbl_cover_show.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.lbl_cover_show.setPixmap(pix)

    def do_embed(self):
        if self.cover_image.isNull():
            QMessageBox.warning(self, "Ошибка", "Нет исходного изображения!")
            return
        text_in = self.txt_input.toPlainText()
        if not text_in:
            QMessageBox.warning(self, "Ошибка", "Введите текст!")
            return
        lam = self.spin_lambda.value()
        try:
            seed_val = int(self.seed_line.text())
        except ValueError:
            seed_val = 12345
        bits = text_to_bits_with_marker(text_in)
        res_img, used_idx = embed_kjb(self.cover_image, bits, lam, seed_val)
        if res_img.isNull():
            QMessageBox.warning(self, "Ошибка", "Недостаточно пикселей!")
            return
        self.watermarked_image = res_img
        self.used_indices = used_idx
        self.last_text_embed = text_in
        pix1 = QPixmap.fromImage(self.cover_image).scaled(self.lbl_cover_show.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.lbl_cover_show.setPixmap(pix1)
        pix2 = QPixmap.fromImage(res_img).scaled(self.lbl_embed_show.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.lbl_embed_show.setPixmap(pix2)
        diff_all = measure_blue_diff(self.cover_image, self.watermarked_image)
        diff_changed = measure_changed_only(self.cover_image, self.watermarked_image, used_idx)
        perc_all = (diff_all / 255) * 100
        perc_changed = (diff_changed / 255) * 100
        self.lbl_diff_all.setText(f"Изменение по всем пикселям: {perc_all:.2f}%")
        self.lbl_diff_changed.setText(f"Изменение только в изменённых: {perc_changed:.2f}%")
        QMessageBox.information(self, "OK", "Сообщение встроено.")

    def save_result(self):
        if self.watermarked_image.isNull():
            QMessageBox.warning(self, "Ошибка", "Нет результата!")
            return
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if not folder:
            return
        base_name = os.path.splitext(os.path.basename(self.lbl_cover_path.text()))[0]
        lam_str = f"{self.spin_lambda.value():.2f}".replace('.', '_')
        filename = f"{base_name}_Lam{lam_str}_kjbMarker.bmp"
        path_save = os.path.join(folder, filename).replace("\\", "/")
        ok = self.watermarked_image.save(path_save, "BMP")
        if ok:
            self.last_saved_file = path_save
            QMessageBox.information(self, "OK", f"Файл сохранен: {path_save}")
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось сохранить файл!")

    def init_tab_extract(self):
        layout = QHBoxLayout(self.tab_extract)
        panel = QWidget()
        pv = QVBoxLayout(panel)
        self.btn_load_emb = QPushButton("Загрузить картинку с ЦВЗ")
        self.btn_load_emb.clicked.connect(self.load_embedded)
        pv.addWidget(self.btn_load_emb)
        self.lbl_emb_path = QLabel("Файл не выбран")
        pv.addWidget(self.lbl_emb_path)
        group_seed2 = QGroupBox("Seed (тот же)")
        s2_lay = QHBoxLayout(group_seed2)
        self.seed_line_ext = QLineEdit("12345")
        s2_lay.addWidget(self.seed_line_ext)
        pv.addWidget(group_seed2)
        self.btn_extract = QPushButton("Извлечь")
        self.btn_extract.clicked.connect(self.do_extract)
        pv.addWidget(self.btn_extract)
        self.txt_output = QPlainTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setPlaceholderText("Извлечённый текст...")
        pv.addWidget(self.txt_output)
        self.btn_measure_error = QPushButton("Измерить ошибку в процентах")
        self.btn_measure_error.clicked.connect(self.do_measure_error)
        pv.addWidget(self.btn_measure_error)
        pv.addStretch(1)
        layout.addWidget(panel, 0)
        img_panel = QWidget()
        ip_lay = QHBoxLayout(img_panel)
        self.lbl_emb_show2 = QLabel("Изображение")
        self.lbl_emb_show2.setFixedSize(400, 400)
        self.lbl_emb_show2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ip_lay.addWidget(self.lbl_emb_show2)
        layout.addWidget(img_panel, 1)

    def load_embedded(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите картинку с ЦВЗ", "", "Images (*.png *.jpg *.jpeg *.bmp *.pgm);;All Files (*)")
        if path:
            tmp = QImage(path)
            if tmp.isNull():
                QMessageBox.warning(self, "Ошибка", "Не удалось загрузить!")
                return
            self.watermarked_image = tmp
            self.lbl_emb_path.setText(path)
            pix = QPixmap.fromImage(tmp).scaled(self.lbl_emb_show2.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.lbl_emb_show2.setPixmap(pix)

    def do_extract(self):
        if self.watermarked_image.isNull():
            QMessageBox.warning(self, "Ошибка", "Нет изображения для извлечения!")
            return
        try:
            seed_val = int(self.seed_line_ext.text())
        except ValueError:
            seed_val = 12345
        raw_bits = extract_kjb(self.watermarked_image, 0, seed_val)
        text_out = bits_to_text_with_marker(raw_bits)
        self.txt_output.setPlainText(text_out)
        QMessageBox.information(self, "OK", "Сообщение извлечено.")

    def do_measure_error(self):
        if not self.last_saved_file:
            QMessageBox.warning(self, "Ошибка", "Файл с встраиванием не был сохранён!")
            return
        loaded_filename = os.path.basename(self.lbl_emb_path.text())
        last_saved_filename = os.path.basename(self.last_saved_file)
        if loaded_filename != last_saved_filename:
            QMessageBox.warning(self, "Ошибка", "Загруженный файл не совпадает с последним сохранённым!")
            return
        original_text = self.last_text_embed
        extracted_text = self.txt_output.toPlainText()
        if not original_text or not extracted_text:
            QMessageBox.warning(self, "Ошибка", "Отсутствует оригинальный или извлечённый текст!")
            return
        s = difflib.SequenceMatcher(None, original_text, extracted_text)
        ratio = s.ratio()
        error_percent = (1 - ratio) * 100
        QMessageBox.information(self, "Ошибка", f"Ошибка в извлечении: {error_percent:.2f}%")

def main():
    app = QApplication(sys.argv)
    wnd = KJBApp()
    wnd.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
