# Makefile for tgv-punctuality-dashboard

.PHONY: install setup data clean run help

VENV_DIR = venv

help:
	@echo "Available commands:"
	@echo "  make setup    : Create venv, install dependencies, and download data."
	@echo "  make install  : Install Python dependencies from requirements.txt."
	@echo "  make data     : Download the raw data file using download_data.py."
	@echo "  make clean    : Remove venv, parquet cache, and downloaded CSV."
	@echo "  make run      : Run the Streamlit application."

# Creates venv if it doesn't exist
$(VENV_DIR):
	@echo "Creating virtual environment at $(VENV_DIR)..."
	python3 -m venv $(VENV_DIR)

install: $(VENV_DIR)
	@echo "Installing dependencies..."
	@$(VENV_DIR)/bin/pip install -r requirements.txt

data: $(VENV_DIR)
	@echo "Downloading raw data..."
	@$(VENV_DIR)/bin/python download_data.py

setup: install data
	@echo "Setup complete. Use 'make run' to launch the dashboard."

run: $(VENV_DIR)
	@echo "Starting Streamlit dashboard..."
	@$(VENV_DIR)/bin/streamlit run app.py

clean:
	@echo "Cleaning up generated files..."
	rm -rf $(VENV_DIR)
	rm -f data/*.parquet
	rm -f data/regularite-mensuelle-tgv-aqst.csv