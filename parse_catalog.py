# python parse_catalog.py

import logging
import pdfplumber
import re
import pandas as pd
import os
import time

logging.basicConfig(
    level=logging.DEBUG,  # Zmienione na DEBUG dla większej ilości szczegółów
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def extract_data_from_pdf(pdf_path):
    data = []
    current_item = None
    description = []
    
    try:
        logging.debug("Rozpoczynam otwieranie pliku PDF...")
        with pdfplumber.open(pdf_path) as pdf:
            logging.info(f"Otwarto PDF, liczba stron: {len(pdf.pages)}")
            
            for page_num, page in enumerate(pdf.pages, 1):
                logging.debug(f"Przetwarzanie strony {page_num}...")
                start_time = time.time()
                
                text = page.extract_text()
                logging.debug(f"Czas ekstrakcji tekstu ze strony {page_num}: {time.time() - start_time:.2f} sekund")
                
                if text:
                    logging.debug(f"Długość tekstu na stronie {page_num}: {len(text)} znaków")
                    lines = text.split("\n")
                    logging.debug(f"Liczba linii na stronie {page_num}: {len(lines)}")
                    
                    for line_num, line in enumerate(lines, 1):
                        line = line.strip()
                        if line.startswith('ARDEX '):
                            logging.debug(f"Znaleziono produkt na stronie {page_num}, linia {line_num}: {line}")
                            if current_item:
                                full_description = " ".join(description).strip()
                                if full_description:
                                    data.append({
                                        "product": current_item,
                                        "description": full_description,
                                        "page": page_num
                                    })
                                    logging.debug(f"Dodano produkt: {current_item}")
                            current_item = line
                            description = []
                        elif current_item and line:
                            description.append(line)
                else:
                    logging.warning(f"Nie znaleziono tekstu na stronie {page_num}")
                
                if page_num % 10 == 0:  # Status co 10 stron
                    logging.info(f"Przetworzono {page_num} stron...")
        
        # Dodanie ostatniego produktu
        if current_item:
            full_description = " ".join(description).strip()
            if full_description:
                data.append({
                    "product": current_item,
                    "description": full_description,
                    "page": len(pdf.pages)
                })
                logging.debug("Dodano ostatni produkt")
        
        df = pd.DataFrame(data)
        
        if not df.empty:
            logging.info(f"Znaleziono {len(df)} produktów")
            df.to_csv("extracted_products.csv", index=False, encoding='utf-8')
            logging.info("Zapisano dane do 'extracted_products.csv'")
            print("\nPierwsze znalezione produkty:")
            print(df[['product', 'page']].head())
        else:
            logging.error("Nie znaleziono produktów")
            
        return df
    
    except Exception as e:
        logging.exception(f"Błąd podczas przetwarzania PDF: {str(e)}")
        return pd.DataFrame(columns=['product', 'description', 'page'])

if __name__ == "__main__":
    pdf_path = r"C:\Users\Weronika\Desktop\Anna\bot\project\Bot Ardex\ArdexHelpBot\katalog_ardex.pdf"
    logging.info("Rozpoczynam proces ekstrakcji danych...")
    df_data = extract_data_from_pdf(pdf_path)
    logging.info("Zakończono proces ekstrakcji danych.")