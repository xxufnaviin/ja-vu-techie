from transform import main as transform_and_save
from extract import main as extract_pdfs



if __name__ == "__main__":
    extract_pdfs()
    transform_and_save("pipeline/data/ocr") # transforms text data to neptune graph data

