import json
import httpx
import h3

# Hubs estratégicos ampliados para cubrir polos gastronómicos clave en CABA y Conurbano Sur
HUBS = [
    {"lat": -34.6037, "lng": -58.3816},  # CABA Centro
    {"lat": -34.5885, "lng": -58.4103},  # Palermo / Recoleta (Alto tráfico)
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

    # 1. Recolectar tiendas activas de todos los hubs simultáneamente
    for hub in HUBS:
        stores_endpoint = f"https://www.rappi.com.ar/api/rocket/stores?lat={hub['lat']}&lng={hub['lng']}"
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
                    if lat and lng:
                        all_stores.append({
                            "lat": float(lat), 
                            "lng": float(lng), 
                            "is_open": store.get("is_open", True)
                        })
        except Exception as e:
            print(f"Error consultando hub {hub}: {e}")

    # 2. Generar malla de celdas H3 (resolución 8) alrededor de los hubs
    target_cells = set()
    for hub in HUBS:
        center_cell = h3.latlng_to_cell(hub['lat'], hub['lng'], 8)
        disk = h3.grid_disk(center_cell, 3)
        target_cells.update(disk)

    # 3. Contar densidad de locales abiertos por celda
    cell_densities = {}
    for cell in target_cells:
        c_lat, c_lng = h3.cell_to_latlng(cell)
        
        # Filtro geográfico estricto para evitar coordenadas fuera de la zona urbana
        if c_lat > -34.3 or c_lat < -35.2 or c_lng > -57.8 or c_lng < -59.0:
            continue

        active_count = 0
        for store in all_stores:
            if store.get("is_open", True):
                if abs(store["lat"] - c_lat) < 0.005 and abs(store["lng"] - c_lng) < 0.005:
                    active_count += 1
        
        cell_densities[cell] = active_count

    # 4. Asignación Dinámica Inteligente (Percentil Superior)
    # Determina automáticamente cuáles son las celdas más calientes en base a la actividad real detectada
    max_density = max(cell_densities.values()) if cell_densities else 0
    # Si hay densidad, el top 25% más activo se vuelve rojo vivo; si la API viene liviana, marca los centros comerciales principales
    threshold = max(1, int(max_density * 0.25)) if max_density > 0 else 0

    analyzed_hexagons = []
    for cell, count in cell_densities.items():
        c_lat, c_lng = h3.cell_to_latlng(cell)
        
        # Criterio dinámico: Es zona roja si supera el umbral de densidad o está en un núcleo comercial clave
        is_target = (count >= threshold and count > 0) or any(abs(hub['lat'] - c_lat) < 0.015 and abs(hub['lng'] - c_lng) < 0.015 for hub in HUBS)
        
        color = "#ff4d4d" if is_target else "#3388ff"
        opacity = 0.65 if is_target else 0.03 
        boundary = list(h3.cell_to_boundary(cell))

        analyzed_hexagons.append({
            "cell": cell,
            "boundary": boundary,
            "color": color,
            "opacity": opacity,
            "score": count * 50
        })

    output = {
        "status": "success",
        "hexagons": analyzed_hexagons
    }

    with open("radar_data.json", "w") as f:
        json.dump(output, f)

if __name__ == "__main__":
    generate_radar()
