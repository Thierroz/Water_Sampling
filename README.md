# 💧 Water Sampler

Swiss water & air temperature monitoring tool. Fetches live data from **BAFU/FOEN** (hydrology) and **MeteoSwiss SwissMetNet** (weather) via the [existenz.ch API](https://api.existenz.ch).

---

## 📱 Web App (PWA)

Open `app/index.html` in a browser, or serve it:

```bash
cd app
python3 -m http.server 8765
# → open http://localhost:8765
```

**Add to phone home screen:**
- **iPhone**: Safari → Share → Add to Home Screen
- **Android**: Chrome → ⋮ → Add to Home Screen

### Features
- 🔍 Search 83+ active Swiss hydrology stations
- 💧 Live water temperature (BAFU/FOEN)
- 🌡 Air temperature from nearest MeteoSwiss station
- 💾 Save readings as timestamped `.txt` files

---

## 🐍 Python CLI

```bash
pip install requests

# Interactive mode (shows full list)
python water_temp.py

# Search by river / location
python water_temp.py --place "Sihl"
python water_temp.py --place "Zürich"
```

Output is saved as `YYYY-MM-DD_HH-MM-SS_StationName.txt`.

---

## Data Sources

| Source | Data |
|--------|------|
| [BAFU/FOEN](https://www.bafu.admin.ch) | Water temperature |
| [MeteoSwiss SwissMetNet](https://www.meteoswiss.admin.ch) | Air temperature |
| [existenz.ch API](https://api.existenz.ch) | API wrapper |
