import requests
import os
from pathlib import Path

# URL de l'API Open Data SNCF (fichier AQST TGV)
DATA_URL = "https://ressources.data.sncf.com/explore/dataset/regularite-mensuelle-tgv-aqst/download/?format=csv&timezone=Europe/Berlin&lang=fr&use_labels_for_header=true&csv_separator=%3B"

# Chemin local
OUTPUT_PATH = Path("data/regularite-mensuelle-tgv-aqst.csv")

def download_and_save(url: str, output_path: Path):
    """Downloads data from a URL and saves it to a file."""
    print(f"-> Downloading data from {url.split('//')[1].split('/')[0]}...")

    # Ensure the data directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Use stream=True to handle large files
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status() # Check for HTTP errors

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        print(f"-> Success: Data saved to {output_path.resolve()}")

    except requests.exceptions.RequestException as e:
        print(f"!! ERROR during download: {e}")

if __name__ == "__main__":
    download_and_save(DATA_URL, OUTPUT_PATH)