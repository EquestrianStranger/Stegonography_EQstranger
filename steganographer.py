import numpy as np
from PIL import Image
import os

class Steganographer:
    def __init__(self, image_path):
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Файл {image_path} не найден")
        self.image = Image.open(image_path)
        self.pixels = np.array(self.image)
        
        if self.pixels.dtype != np.uint8:
            self.pixels = self.pixels.astype(np.uint8)
    
    @classmethod
    def from_image(cls, image):
        """Создает экземпляр из объекта PIL.Image"""
        import tempfile
        temp_path = "temp_stego_image.png"
        image.save(temp_path)
        instance = cls(temp_path)
        os.remove(temp_path)
        if instance.pixels.dtype != np.uint8:
            instance.pixels = instance.pixels.astype(np.uint8)
        return instance
    
    def text_to_bits(self, text):
        byte_array = text.encode('utf-8')
        return np.unpackbits(np.frombuffer(byte_array, dtype=np.uint8))
    
    def generate_key(self, seed, length):
        np.random.seed(seed)
        return np.random.randint(0, 2, length)
    
    def embed_basic(self, text, seed):
        bits = self.text_to_bits(text)
        key = self.generate_key(seed, len(bits))
        encoded = np.bitwise_xor(bits, key)
        
        flat_pixels = self.pixels.flatten().astype(np.int32)
        
        for i in range(len(encoded)):
            if i < len(flat_pixels):
                new_value = (flat_pixels[i] & 0xFE) | encoded[i]  # 0xFE = 11111110
                flat_pixels[i] = np.clip(new_value, 0, 255)
        
        new_pixels = flat_pixels.reshape(self.pixels.shape).astype(np.uint8)
        return Image.fromarray(new_pixels)
    
    def linear_hash(self, data_block, a=101, b=103, p=2**16+1):
        return (a * int.from_bytes(data_block, 'big') + b) % p
    
    def embed_enhanced(self, text, seed):
        text_bits = np.unpackbits(np.frombuffer(text.encode('utf-8'), dtype=np.uint8))
        length_bits = np.array([int(bit) for bit in f"{len(text_bits):032b}"], dtype=np.uint8)
        
        all_bits = np.concatenate([length_bits, text_bits])
        key_text = self.generate_key(seed, len(all_bits))
        print("Биты", all_bits)
        print("Встроенная длинна", len(text_bits))
        encoded_text = np.bitwise_xor(all_bits, key_text)
        
        block_size = 64
        blocks = [encoded_text[i:i+block_size] for i in range(0, len(encoded_text), block_size)]
        enhanced_data = []
        
        for block in blocks:
            block_bytes = np.packbits(block).tobytes()
            block_hash = self.linear_hash(block_bytes)
            hash_bits = np.array([(block_hash >> i) & 1 for i in range(16)], dtype=np.uint8)
            enhanced_data.extend(block)
            enhanced_data.extend(hash_bits)
        
        key_full = self.generate_key(seed, len(enhanced_data))
        
        final_bits = np.bitwise_xor(enhanced_data, key_full)
        
        flat_pixels = self.pixels.flatten()
        for i in range(len(final_bits)):
            if i < len(flat_pixels):
                flat_pixels[i] = (flat_pixels[i] & 0xFE) | final_bits[i]
        
        return Image.fromarray(self.pixels)

    def calculate_capacity(self, text, method="enhanced"):
        """Вычисляет требуемое количество бит для встраивания текста"""
        text_bits = len(text.encode('utf-8')) * 8
        
        if method == "basic":
            return text_bits
        else:
            blocks = (text_bits + 63) // 64  
            return text_bits + blocks * 16
    
    def extract_basic(self, seed, length_bits):
        flat_pixels = self.pixels.flatten()
        extracted_bits = [pixel & 1 for pixel in flat_pixels[:length_bits]]
        
        key = self.generate_key(seed, len(extracted_bits))
        decoded_bits = np.bitwise_xor(extracted_bits, key)
        
        bytes_array = np.packbits(decoded_bits).tobytes()
        try:
            return bytes_array.decode('utf-8')
        except UnicodeDecodeError:
            return "Ошибка декодирования"

    def extract_enhanced(self, seed):
        length_bits = (self.pixels.flatten()[:32] & 1).astype(np.uint8)
        msg_length = int(''.join(map(str, length_bits)), 2)
        key = self.generate_key(seed, 32 + msg_length)
        print("Биты длинна", length_bits)
        print("Извлечённая длинна", msg_length)
        extracted_bits = (self.pixels.flatten()[:32 + msg_length] & 1)
        decoded_bits = np.bitwise_xor(extracted_bits, key)[32:]
               
        block_size = 64
        hash_size = 16
        result = bytearray()
        error_count = 0 
        
        for i in range(0, len(decoded_bits), block_size + hash_size):
            if i + block_size > len(decoded_bits):
                break
            
            data_bits = decoded_bits[i:i+block_size]
            
            if i + block_size + hash_size <= len(decoded_bits):
                hash_bits = decoded_bits[i+block_size:i+block_size+hash_size]
                extracted_hash = sum(bit << j for j, bit in enumerate(hash_bits))
                
                data_bytes = np.packbits(data_bits).tobytes()
                computed_hash = self.linear_hash(data_bytes)
                
                if computed_hash != extracted_hash:
                    error_count += 1
            
            key_text = self.generate_key(seed, block_size)
            clean_bits = np.bitwise_xor(data_bits, key_text)
            result.extend(np.packbits(clean_bits).tobytes())
        
        try:
            decoded_text = result.decode('utf-8')
        except UnicodeDecodeError:
            decoded_text = result.decode('utf-8', errors='replace')
        
        return decoded_text, error_count

    def compare_containers(self, original_image_path, stego_image_path):
        """Сравнивает оригинальное и стего-изображение с автоматической конвертацией форматов"""
        original = np.array(Image.open(original_image_path))
        stego = np.array(Image.open(stego_image_path))
        
        if len(original.shape) != len(stego.shape):
            if len(original.shape) == 3:
                stego = np.stack((stego,)*3, axis=-1)
            else:
                original = np.stack((original,)*3, axis=-1)
        
        if original.shape != stego.shape:
            raise ValueError(f"Размеры изображений не совпадают: {original.shape} vs {stego.shape}")
        
        original_int = original.astype(np.int32)
        stego_int = stego.astype(np.int32)
        
        diff = original_int - stego_int
        
        metrics = {
            'mse': np.mean(diff**2),
            'psnr': 10 * np.log10(255**2 / np.mean(diff**2)),
            'changed_pixels': np.sum(diff != 0),
            'lsb_changes': np.sum((original & 1) != (stego & 1))
        }
        
        return metrics

    def visualize_changes(self, original_image_path, stego_image_path):
        """Визуализирует различия с автоматической конвертацией форматов"""
        original = np.array(Image.open(original_image_path))
        stego = np.array(Image.open(stego_image_path))
        
        if len(original.shape) != len(stego.shape):
            if len(original.shape) == 3:
                stego = np.stack((stego,)*3, axis=-1)
            else:
                original = np.stack((original,)*3, axis=-1)
        
        changes = ((original & 1) != (stego & 1)).any(axis=-1 if len(original.shape) == 3 else None).astype(np.uint8) * 255
        
        highlight = np.zeros_like(original) if len(original.shape) == 3 else np.zeros((*original.shape, 3))
        highlight[..., 0] = changes
        if len(original.shape) == 3:
            highlight[..., 1] = original[..., 1] // 2
            highlight[..., 2] = original[..., 2] // 2
        else:
            highlight[..., 1] = original // 2
            highlight[..., 2] = original // 2
        
        return Image.fromarray(highlight.astype(np.uint8))

    def analyze_lsb_distribution(self, block_size=8):
        """Анализирует распределение LSB в блоках изображения"""
        if len(self.pixels.shape) == 3:
            lsb = self.pixels[:, :, 0] & 1
        else:
            lsb = self.pixels & 1
        
        height, width = lsb.shape[:2]
        prob_matrix = np.zeros((height // block_size, width // block_size))
        
        for i in range(0, height, block_size):
            for j in range(0, width, block_size):
                block = lsb[i:i+block_size, j:j+block_size]
                prob_matrix[i//block_size, j//block_size] = np.mean(block)
        
        return prob_matrix  

    def chi_square_test(self, block_size=64):
        """
        Выполняет χ²-тест для обнаружения стегосообщений
        :param block_size: размер анализируемого блока (по умолчанию 64 бита)
        :return: p-value - вероятность естественного распределения LSB
        """
        if len(self.pixels.shape) == 3:
            lsb = self.pixels[:, :, 0].flatten() & 1
        else:
            lsb = self.pixels.flatten() & 1
        
        lsb = lsb[:block_size]
        
        pairs = [(lsb[i], lsb[i+1]) for i in range(0, len(lsb)-1, 2)]
        
        freq = {
            (0, 0): 0,
            (0, 1): 0,
            (1, 0): 0,
            (1, 1): 0
        }
        
        for pair in pairs:
            freq[pair] += 1
        
        total_pairs = len(pairs)
        if total_pairs == 0:
            return 1.0 
        
        exp_freq = {
            (0, 0): (freq[(0,0)] + freq[(0,1)]) * (freq[(0,0)] + freq[(1,0)]) / total_pairs,
            (0, 1): (freq[(0,0)] + freq[(0,1)]) * (freq[(0,1)] + freq[(1,1)]) / total_pairs,
            (1, 0): (freq[(1,0)] + freq[(1,1)]) * (freq[(0,0)] + freq[(1,0)]) / total_pairs,
            (1, 1): (freq[(1,0)] + freq[(1,1)]) * (freq[(0,1)] + freq[(1,1)]) / total_pairs
        }
        
        chi_sq = 0
        for key in freq:
            if exp_freq[key] != 0:
                chi_sq += (freq[key] - exp_freq[key])**2 / exp_freq[key]
        
        from scipy.stats import chi2
        p_value = 1 - chi2.cdf(chi_sq, df=1)
        
        return p_value

    def advanced_analysis(self):
        """Расширенный анализ с несколькими тестами"""
        results = {
            'chi_square': self.chi_square_test(),
            'lsb_mean': np.mean(self.pixels & 1),
            'lsb_variance': np.var(self.pixels & 1)
        }
        
        if len(self.pixels.shape) == 3:
            for i, channel in enumerate(['Red', 'Green', 'Blue']):
                lsb = self.pixels[:, :, i] & 1
                results[f'{channel}_mean'] = np.mean(lsb)
        
        return results
