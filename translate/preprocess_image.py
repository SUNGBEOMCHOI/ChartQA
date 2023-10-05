import os
import re
import time

import tqdm
import pytesseract
import pandas as pd
from googletrans import Translator, LANGUAGES
from PIL import Image, ImageDraw, ImageFont
import easyocr

class ImageTranslator:
    def __init__(self, image_path, translator, reader, font_path, method="tesseract", debug_mode=False):
        self.image_path = image_path
        self.font_path = font_path
        self.img = Image.open(self.image_path).copy()  # 원본 이미지 복사
        self.debug_img = self.img.copy() if debug_mode else None  # 디버그 이미지 생성
        self.translator = translator
        self.reader = reader
        self.data = None
        self.lines = []
        self.debug_mode = debug_mode
        self.method = method  # tesseract or easyocr

    def translate_to_korean(self, text):
        if text.strip() == '':
            return text
        for _ in range(3):  # 최대 3회 시도
            try:
                translated = self.translator.translate(text, src='en', dest='ko')
                return translated.text
            except Exception as e:  # 예외 발생 시
                print(f"Error encountered: {e}. Retrying...")
                time.sleep(1)  # 1초 대기
        # 3회 시도 후에도 실패할 경우 에러 메시지 반환
        print("Translation failed after multiple attempts.")
        return text

    def merge_boxes(self, boxes):
        if not boxes:
            return None
        x_min = min(box[0] for box in boxes)
        y_min = min(box[1] for box in boxes)
        x_max = max(box[2] for box in boxes)
        y_max = max(box[3] for box in boxes)
        return x_min, y_min, x_max, y_max

    def extract_text_with_tesseract(self):
        d = self.reader(self.img, output_type=pytesseract.Output.DICT)
        self.data = d
        draw = ImageDraw.Draw(self.img)
        
        current_line = []
        previous_x_mid = d['left'][0] + (d['width'][0] / 2)
        previous_y_mid = d['top'][0] + (d['height'][0] / 2)
        threshold_x_mid_difference = 20
        threshold_y_mid_difference = 20

        for i in range(len(d['text'])):
            if d['text'][i].strip() != "":
                x, y, w, h = d['left'][i], d['top'][i], d['width'][i], d['height'][i]
                x_mid = x + (w / 2)
                y_mid = y + (h / 2)

                if self.debug_mode:
                    draw.rectangle([x, y, x+w, y+h], outline="red")

                if (abs(x_mid - previous_x_mid) > threshold_x_mid_difference or
                    abs(y_mid - previous_y_mid) > threshold_y_mid_difference):
                    self.lines.append(self.merge_boxes(current_line))
                    current_line = []

                current_line.append((x, y, x + w, y + h))
                previous_x_mid = x_mid
                previous_y_mid = y_mid

        if current_line:
            self.lines.append(self.merge_boxes(current_line))

        # debug_mode일 때 병합된 바운딩 박스 그리기
        if self.debug_mode:
            for line in self.lines:
                if line:
                    draw.rectangle(line, outline="blue")

    def extract_text_with_easyocr(self):        
        self.ocr_results = self.reader.readtext(self.image_path)
        draw = ImageDraw.Draw(self.debug_img if self.debug_mode else self.img)
        
        current_line = []
        previous_width = self.ocr_results[0][0][1][0] - self.ocr_results[0][0][0][0]
        previous_mid_x = self.ocr_results[0][0][0][0] + previous_width / 2
        previous_height = self.ocr_results[0][0][3][1] - self.ocr_results[0][0][0][1]
        previous_mid_y = self.ocr_results[0][0][0][1] + previous_height / 2
        
        threshold_x_distance = 10  # y축 거리 임계값 추가
        threshold_y_distance = 6  # y축 거리 임계값 추가
        threshold_height_difference = 8

        for entry in self.ocr_results:
            box = entry[0]
            text = entry[1]
            x_start, y_start = box[0]
            x_end, y_end = box[2]
            w = x_end - x_start
            h = y_end - y_start
            mid_x = x_start + w / 2
            mid_y = y_start + h / 2

            if self.debug_mode:
                draw.rectangle([x_start, y_start, x_end, y_end], outline="red")

            if (abs(h - previous_height) > threshold_height_difference or 
                abs(mid_x - previous_mid_x) - ((w + previous_width) / 2) >  threshold_x_distance or 
                abs(mid_y - previous_mid_y) - ((h + previous_height) / 2) > threshold_y_distance):
                merged_box = self.merge_boxes(current_line)
                if merged_box:
                    self.lines.append(merged_box)
                current_line = []

            current_line.append((x_start, y_start, x_end, y_end))
            previous_width = w
            previous_mid_x = mid_x
            previous_height = h
            previous_mid_y = mid_y

        # Add the last line if it exists
        merged_box = self.merge_boxes(current_line)
        if merged_box:
            self.lines.append(merged_box)

        if self.debug_mode:
            for line in self.lines:
                if line:
                    draw.rectangle(line, outline="blue")


    def extract_text_boxes(self):
        if self.method == "tesseract":
            self.extract_text_with_tesseract()
        elif self.method == "easyocr":
            self.extract_text_with_easyocr()


    def merge_texts_inside_box(self, box):
        x_min, y_min, x_max, y_max = box
        texts_in_box = [self.data['text'][i] for i in range(len(self.data['text']))
                        if (self.data['left'][i] >= x_min and self.data['top'][i] >= y_min
                            and (self.data['left'][i] + self.data['width'][i]) <= x_max
                            and (self.data['top'][i] + self.data['height'][i]) <= y_max)]
        
        avg_font_size = sum([self.data['height'][i] for i in range(len(self.data['text']))
                             if (self.data['left'][i] >= x_min and self.data['top'][i] >= y_min
                                 and (self.data['left'][i] + self.data['width'][i]) <= x_max
                                 and (self.data['top'][i] + self.data['height'][i]) <= y_max)]) / len(texts_in_box)
        
        merged_text = ' '.join(texts_in_box)
        return merged_text, avg_font_size
    
    def merge_texts_inside_box_easyocr(self, box):
        x_min, y_min, x_max, y_max = box
        texts_in_box = []
        total_height = 0
        count = 0
        for entry in self.ocr_results:
            text_box = entry[0]
            text = entry[1]
            tx_min, ty_min = text_box[0]
            tx_max, ty_max = text_box[2]
            if x_min <= tx_min and y_min <= ty_min and x_max >= tx_max and y_max >= ty_max:
                texts_in_box.append(text)
                total_height += (ty_max - ty_min)
                count += 1

        avg_font_size = total_height / count if count else 0  # 텍스트가 없는 경우를 대비한 분모가 0이 되는 경우 방지
        merged_text = ' '.join(texts_in_box)
        return merged_text, avg_font_size


    def draw_merged_text(self, draw, text, box, font):
        
        try:
            text_width, text_height = font.getbbox(text)[2:4]
        except:
            print('text', text)
            return 
        x = box[2] - text_width  # Start drawing from here for right-aligned text

        # If text width exceeds box width, break it into multiple lines
        if text_width > (box[2] - box[0]):
            lines = text.split()
            new_text = ''
            while lines:
                line = ''
                prev_line = None
                while lines:
                    word = lines[0]
                    if draw.textbbox((0, 0), line + word, font=font)[2] <= (box[2] - box[0]):
                        prev_line = line
                        line += (lines.pop(0) + ' ')
                    else:
                        if line:
                            break
                        line += (lines.pop(0) + ' ')
                        break
                if line == prev_line and not lines:
                    break
                new_text += line + '\n'
            try:
                draw.text((box[0], box[1]), new_text, font=font, fill="black")
            except:
                pass
        else:
            draw.text((x, box[1]), text, font=font, fill="black")

    def is_numeric_or_percentage(self, text):
        return bool(re.fullmatch(r'^[0-9\s.%]+$', text))

    def draw_translated_text(self):
        draw = ImageDraw.Draw(self.img)
        for box in self.lines:
            if box:
                if self.method == "tesseract":
                    merged_text, estimated_font_size = self.merge_texts_inside_box(box)
                elif self.method == "easyocr":
                    merged_text, estimated_font_size = self.merge_texts_inside_box_easyocr(box)

                if self.is_numeric_or_percentage(merged_text):
                    # If the text is numeric or a percentage, skip the translation and drawing
                    continue

                x0, y0, x1, y1 = box
                sanitized_box = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

                draw.rectangle(sanitized_box, fill="white")
                translated_text = self.translate_to_korean(merged_text)
                font = ImageFont.truetype(self.font_path, int(estimated_font_size*0.7))
                self.draw_merged_text(draw, translated_text, box, font)

    def save_image(self, path):
        # Save the translated image
        self.img.save(path)
        # If debug mode is on, save the debug image
        if self.debug_mode:
            # Extract just the filename without the path
            filename = os.path.basename(path)
            debug_filename = "debug_" + filename
            debug_path = os.path.join(os.path.dirname(path), debug_filename)
            self.debug_img.save(debug_path)

    def show_image(self):
        if self.debug_mode:
            self.debug_img.show()  # 디버그 이미지 출력
        self.img.show()

def translate_and_save_all_images_in_folder(source_folder, target_root_folder, font_path, method="tesseract", debug_mode=False):
    """
    Translate all images in a source folder and save them to a target root folder.

    Args:
    - source_folder: The path of the folder containing the images to translate.
    - target_root_folder: The root folder where the translated images will be saved.
    - font_path: The path to the font file to be used.
    - method: Either "tesseract" or "easyocr" to specify which OCR tool to use.
    - debug_mode: Whether to activate debug mode or not.
    """
    image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff']

    google_translator = Translator()
    if method == "tesseract":
        reader = pytesseract.image_to_data
    elif method == "easyocr":
        reader = easyocr.Reader(['en'])
    else:
        raise ValueError("method must be either 'tesseract' or 'easyocr'.")

    # Ensure the target root folder exists
    if not os.path.exists(target_root_folder):
        os.makedirs(target_root_folder)

    # List all files in the source folder
    for filename in tqdm.tqdm(os.listdir(source_folder)):
        if os.path.splitext(filename)[1].lower() in image_extensions:
            source_image_path = os.path.join(source_folder, filename)
            target_image_path = os.path.join(target_root_folder, filename)
            
            # Check if the translated image already exists in the target folder
            if os.path.exists(target_image_path):
                continue  # If it does, skip this image

            # Translate the image
            image_translator = ImageTranslator(source_image_path, google_translator, reader, font_path, method=method, debug_mode=debug_mode)
            image_translator.extract_text_boxes()
            image_translator.draw_translated_text()
            image_translator.save_image(target_image_path)

if __name__ == "__main__":
    source_folder = "../ChartQA Dataset/train/png"
    target_root_folder = "../ChartQA Dataset/translate_train/png"
    font_path = "./font/휴먼명조.ttf"
    translate_and_save_all_images_in_folder(source_folder, target_root_folder, font_path, method="easyocr", debug_mode=False)
