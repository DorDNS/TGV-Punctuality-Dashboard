# TGV Punctuality Dashboard 🚄📊

A Streamlit dashboard for analyzing TGV punctuality, causes of delay, and severity, based on open data from SNCF.

## 🚀 Quick Setup & Run

### Prerequisites
- Python 3.10+
- `make` (standard on macOS/Linux)

### 1. Setup
This command will create a Python virtual environment (`venv`), install all dependencies from `requirements.txt`, and download the necessary raw data file (`regularite-mensuelle-tgv-aqst.csv`) into the `data/` directory.

```bash
make setup
```

### 2. Run
To launch the Streamlit application (once setup is complete):
```bash
make run
```
The application will be available at `http://localhost:8501`.

## 🛠 Makefile Commands
This project uses a `Makefile` to simplify common tasks:
* `make setup`: Runs `install` and `data`. The primary command for first-time users.
* `make install`: Creates the `venv` (if missing) and installs Python packages.
* `make data`: Downloads the raw TGV punctuality data.
* `make run`: Starts the Streamlit server.
* `make clean`: Removes the `venv`, downloaded data (`.csv`), and data cache (`.parquet`).

## 📁 Project Structure
```
.
├── Makefile          # Main commands (setup, run, clean)
├── README.md         # This file
├── app.py            # Main Streamlit app entrypoint
├── constants.py      # Configuration for filenames, seeds
├── download_data.py  # Script to fetch raw data
├── requirements.txt  # Python dependencies
├── assets/           # Static images (logo, etc.)
├── data/             # Data directory
│   └── stations.csv  # Static station coordinate data
├── pages/            # Streamlit pages (Intro, Overview, etc.)
└── utils/            # Helper Python modules (compute, prep, viz, etc.)
```

## 🌐 Deployed Application
The dashboard is deployed and accessible [here](https://tgv-punctuality-dashboard.streamlit.app/).

## 🎥 Demonstration Video
A demonstration video of the dashboard can be found [here](https://youtu.be/HSyHO0TIMgg).