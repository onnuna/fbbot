# -*- coding: utf-8 -*-
# cd C:\Users\Weronika\Desktop\Anna\bot\project\Bot Ardex\ArdexHelpBot
# python -m venv venv
# .\venv\Scripts\activate
# python fbbot.py

# -*- coding: utf-8 -*-
import logging
import os
from flask import Flask, request
import requests
import pandas as pd
import pdfplumber
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Dane Messengera
PAGE_ACCESS_TOKEN = "EAAI62sv9ZAlwBOZBWNS1Iels0Jsp5KfV4yERwAjnKyFqKiLMHdXAeKvZB4UpuJEqZCmLZCSHZA5AFZBfdZBKNo09KwxNKstC3WTrFUZAepKNwEhDCbjRQGXjQCPMPelk9yZALAdBo76ByNZAEmyI4ScON43IkXt2PT1vtvLvEdUB1rCQymWYcsZCdnNa4B7t6Pkyek7J"
VERIFY_TOKEN = "ardexbot123"


# Ścieżki
current_dir = os.path.dirname(os.path.abspath(__file__))
pdf_path = os.path.join(current_dir, "katalog_ardex.pdf")
csv_path = os.path.join(current_dir, "extracted_products.csv")

# Funkcja wczytująca dane z PDF
def extract_data_from_pdf(pdf_path):
    try:
        products = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    # Zakładam, że każda sekcja zaczyna się od "ARDEX" i zawiera opis
                    lines = text.split('\n')
                    product_name = None
                    description = []
                    for line in lines:
                        if line.startswith("ARDEX"):
                            if product_name and description:
                                products.append({
                                    'product': product_name,
                                    'description': ' '.join(description)
                                })
                            product_name = line.split('Opis:')[0].strip()
                            description = [line]
                        elif product_name:
                            description.append(line)
                    if product_name and description:
                        products.append({
                            'product': product_name,
                            'description': ' '.join(description)
                        })
        df = pd.DataFrame(products)
        df.to_csv(csv_path, index=False, encoding='utf-8')
        logger.info(f"Extracted {len(df)} products from PDF and saved to CSV")
        return df
    except Exception as e:
        logger.error(f"Error extracting data from PDF: {e}")
        return pd.DataFrame(columns=['product', 'description'])

# Funkcja wczytująca produkty
def load_products():
    try:
        if os.path.exists(csv_path):
            logger.info("Loading products from CSV...")
            df_products = pd.read_csv(csv_path, encoding='utf-8')
            if not df_products.empty:
                logger.info(f"Loaded {len(df_products)} products successfully")
                return df_products
        
        logger.warning("CSV not found or empty, attempting to parse PDF...")
        return extract_data_from_pdf(pdf_path)
    
    except Exception as e:
        logger.error(f"Error loading products: {e}")
        return pd.DataFrame(columns=['product', 'description'])

# Inicjalizacja wyszukiwania
def initialize_search():
    global model, index, df_products
    try:
        model = SentenceTransformer("all-MiniLM-L6-v2")
        df_products = load_products()
        
        if df_products.empty:
            raise ValueError("No products loaded")
            
        descriptions = df_products['description'].tolist()
        embeddings = model.encode(descriptions)
        
        d = embeddings.shape[1]
        index = faiss.IndexFlatL2(d)
        index.add(np.array(embeddings, dtype=np.float32))
        
        logger.info("Search initialization completed successfully")
        return df_products, index
    
    except Exception as e:
        logger.error(f"Error initializing search: {e}")
        raise

# Funkcja czyszcząca tekst
def cleanup_text(text):
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s+([.,;:])', r'\1', text)
    return text.strip()

# Funkcja formatująca odpowiedź
def format_product_section(product_name, description):
    try:
        formatted_text = f"*{product_name}*\n\n"
        if "Do stosowania:" in description:
            parts = description.split("Do stosowania:", 1)
            main_desc = cleanup_text(parts[0])
            tech_details = "Do stosowania:" + parts[1] if len(parts) > 1 else ""
        else:
            main_desc = cleanup_text(description)
            tech_details = ""
        
        formatted_text += f"{main_desc}\n\n"
        if tech_details:
            formatted_text += f"{cleanup_text(tech_details)}\n"
        
        return formatted_text.strip()
    except Exception as e:
        logger.error(f"Error formatting product section: {e}")
        return f"*{product_name}*\n\n{description}"

# Funkcja wyszukiwania produktu
def find_best_product(query):
    query_vector = model.encode([query])
    distances, idx = index.search(query_vector, k=5)
    
    seen_products = set()
    responses = []
    
    for i in idx[0]:
        row = df_products.iloc[i]
        product_name = row['product']
        
        if product_name not in seen_products:
            seen_products.add(product_name)
            formatted_response = format_product_section(product_name, row['description'])
            responses.append(formatted_response)
    
    return responses

# Funkcja wysyłania wiadomości
def send_message(sender_id, message):
    url = f"https://graph.facebook.com/v20.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": sender_id},
        "message": {"text": message[:2000]}  # Messenger ma limit 2000 znaków
    }
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        logger.error(f"Error sending message: {response.text}")

# Health check endpoint
@app.route('/')
def health_check():
    return "Ardex Bot is running! 🚀", 200

# Status endpoint
@app.route('/status')
def status():
    try:
        products_count = len(df_products) if 'df_products' in globals() else 0
        return {
            "status": "running",
            "products_loaded": products_count,
            "model_loaded": 'model' in globals()
        }, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

# Weryfikacja webhooka
@app.route('/webhook', methods=['GET'])
def verify():
    if request.args.get('hub.verify_token') == VERIFY_TOKEN:
        return request.args.get('hub.challenge')
    return "Verification failed", 403

# Obsługa wiadomości
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if data['object'] == 'page':
        for entry in data['entry']:
            for event in entry['messaging']:
                if 'message' in event and 'text' in event['message']:
                    sender_id = event['sender']['id']
                    message_text = event['message']['text']
                    
                    if message_text.lower() in ["/start", "start"]:
                        send_message(sender_id, "👋 Cześć! Opisz Swój problem, a podpowiem najlepsze rozwiązania ARDEX!")
                    else:
                        try:
                            responses = find_best_product(message_text)
                            for response in responses:
                                send_message(sender_id, response)
                        except Exception as e:
                            logger.error(f"Error handling message: {e}")
                            send_message(sender_id, "Przepraszam, wystąpił błąd. Spróbuj ponownie.")
    return "OK", 200

if __name__ == "__main__":
    try:
        df_products, index = initialize_search()
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
if __name__ == "__main__":
    df_products, index = initialize_search()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
