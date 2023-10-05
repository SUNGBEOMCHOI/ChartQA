import os
import time

import tqdm
import pandas as pd
from googletrans import Translator

class CSVTranslator:
    def __init__(self, csv_path, translator):
        self.csv_path = csv_path
        self.data = pd.read_csv(csv_path)
        self.translator = translator

    def translate_column(self, column_name):
        if column_name not in self.data.columns:
            print(f"Column '{column_name}' not found in the CSV!")
            return
        self.data[column_name] = self.data[column_name].apply(self.translate_to_korean)
    
    def translate_headers(self):
        # Translate column names
        new_columns = {}
        for column_name in self.data.columns:
            translated_name = self.translate_to_korean(column_name)
            new_columns[column_name] = translated_name
        self.data.rename(columns=new_columns, inplace=True)

    def translate_to_korean(self, text):
        # First, handle the case where the input is a pandas Series
        if isinstance(text, pd.Series):
            return text.apply(self.translate_to_korean)  # This will apply the function to each element in the series

        # Now, we handle the single-value cases
        if pd.isna(text):
            return text

        if not isinstance(text, str):
            return text

        if not text.strip():
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


    def save(self, path=None):
        if path is None:
            path = self.csv_path
        self.data.to_csv(path, index=False)


def translate_and_save_all_csvs_in_folder(source_folder, target_root_folder):
    """
    Translate all CSVs in a source folder and save them to a target root folder.

    Args:
    - source_folder: The path of the folder containing the CSVs to translate.
    - target_root_folder: The root folder where the translated CSVs will be saved.
    """
    csv_extension = '.csv'
    google_translator = Translator()

    # Ensure the target root folder exists
    if not os.path.exists(target_root_folder):
        os.makedirs(target_root_folder)

    # List all files in the source folder
    for filename in tqdm.tqdm(os.listdir(source_folder)):
        if os.path.splitext(filename)[1].lower() == csv_extension:
            source_csv_path = os.path.join(source_folder, filename)
            target_csv_path = os.path.join(target_root_folder, filename)

            # Check if the translated image already exists in the target folder
            if os.path.exists(target_csv_path):
                continue  # If it does, skip this image

            # Translate the CSV
            csv_translator = CSVTranslator(source_csv_path, translator=google_translator)
            csv_translator.translate_headers()
            for column in csv_translator.data.columns:
                csv_translator.translate_column(column)
            csv_translator.save(target_csv_path)
            # print(f"{filename} translated and saved.")

# Example usage:
if __name__ == "__main__":
    source_folder = "../ChartQA Dataset/train/tables"
    target_root_folder = "../ChartQA Dataset/translate_train/tables"
    os.makedirs(target_root_folder, exist_ok=True)
    translate_and_save_all_csvs_in_folder(source_folder, target_root_folder)
