import json
import httpx
import h3

# Polos gastronómicos estratégicos en CABA y Conurbano Sur
HUBS = [
    {"lat": -34.6037, "lng": -58.3816},  # CABA Centro
    {"lat": -34.5885, "lng": -58.4103},  # Palermo / Recoleta
    {"lat": -34.6611, "lng": -58.3683},  # Avellaneda
    {"lat": -34.7212, "lng": -58.2618},  # Quilmes Centro
    {"lat": -34.8150, "lng": -58.2750}   # Berazategui Centro
]

def generate_radar():
    all_stores = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    # 1. Consultar la API de tiendas en tiempo real en cada hub
    for hub in HUBS:
        stores_endpoint = f"https://www.argentina.rappi.com/api/rocket/stores?lat={hub['lat']}&lng={hub['lng']}"
        try:
            response = httpx.get(stores_endpoint, headers=headers, timeout=8.0)
            if response.status_code == 200:
                data = response.json()
                stores = []
                if isinstance(data, list):
                    stores = data
                elif isinstance(data, dict):
                    stores = data.get("stores", data.get("data", data.get("results", [])))
                
                for store in stores:
                    lat = store.get("lat") or store.get("latitude") or store.get("location", {}).get("lat")
                    lng = store.get("lng") or store.get("longitude") or store.get("location", {}).get("lng")
                    
                    # Extraer métricas operativas en vivo (como el tiempo estimado de entrega / ETA)
                    delivery_time = store.get("delivery_time", 30)
                    is_open = store.get("is_open", True)
                    
                    if lat and lng:
                        all_stores.append({
                            "lat": float(lat), 
                            "lng": float(lng), 
                            "is_open": is_open,
                            "delivery_time": int(delivery_time) if isinstance(delivery_time, (int, float)) else 30
                        })
        except Exception as e:
            print(f"Error consultando hub {hub}: {e}")

    # 2. Generar malla de celdas H3 (resolución 8)
    target_cells = set()
    for hub in HUBS:
        center_cell = h3.latlng_to_cell(hub['lat'], hub['lng'], 8)
        disk = h3.grid_disk(center_cell, 3)
        target_cells.update(disk)

    # 3. Calcular el puntaje de presión operativa por celda
    cell_metrics = {}
    for cell in target_cells:
        c_lat, c_lng = h3.cell_to_latlng(cell)
        
        # Filtro geográfico estricto para evitar coordenadas fuera del área urbana
        if c_lat > -34.3 or c_lat < -35.2 or c_lng > -57.8 or c_lng < -59.0:
            continue

        active_count = 0
        total_eta_pressure = 0
        
        for store in all_stores:
            if store["is_open"]:
                if abs(store["lat"] - c_lat) < 0.005 and abs(store["lng"] - c_lng) < 0.005:
                    active_count += 1
                    total_eta_pressure += store["delivery_time"]
        
        # Fórmula de estrés: combina volumen de locales abiertos + aumento en el tiempo de entrega (ETA)
        avg_eta = (total_eta_pressure / active_count) if active_count > 0 else 0
        operational_score = (active_count * 12) + (avg_eta * 2.0)
        
        cell_metrics[cell] = {
            "count": active_count,
            "score": operational_score
        }

    # 4. Asignación Dinámica por Percentil Superior de Estrés Operativo
    if cell_metrics:
        scores = [m["score"] for m in cell_metrics.values()]
        max_score = max(scores) if scores else 0
        # El top 30% con mayor presión y demora operativa se convierte en Zona Roja
        threshold = max_score * 0.30 if max_score > 0 else 0
    else:
        threshold = 0

    analyzed_hexagons = []
    for cell, metrics in cell_metrics.items():
        c_lat, c_lng = h3.cell_to_latlng(cell)
        
        is_target = metrics["score"] >= threshold and metrics["count"] > 0
        
        color = "#ff4d4d" if is_target else "#3388ff"
        opacity = 0.70 if is_target else 0.03 
        boundary = list(h3.cell_to_boundary(cell))

        analyzed_hexagons.append({
            "cell": cell,
            "boundary": boundary,
            "color": color,
            "opacity": opacity,
            "score": metrics["score"]
        })

    output = {
        "status": "success",
        "hexagons": analyzed_hexagons
    }

    with open("radar_data.json", "w") as f:
        json.dump(output, f)

if __name__ == "__main__":
    generate_radar()
