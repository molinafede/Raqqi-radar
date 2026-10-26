import json
import httpx
import h3

# Puntos estratégicos en CABA y el corredor sur hasta Berazategui
HUBS = [
    {"lat": -34.6037, "lng": -58.3816},  # Centro / CABA
    {"lat": -34.6611, "lng": -58.3683},  # Avellaneda / Lanús
    {"lat": -34.7212, "lng": -58.2618},  # Quilmes
    {"lat": -34.8150, "lng": -58.2750}   # Berazategui
]

def generate_radar():
    all_stores = []
    analyzed_hexagons = {}
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # 1. Consultar tiendas activas en los hubs principales
    for hub in HUBS:
        stores_endpoint = f"https://www.rappi.com.ar/api/rocket/stores?lat={hub['lat']}&lng={hub['lng']}"
        try:
            response = httpx.get(stores_endpoint, headers=headers, timeout=6.0)
            if response.status_code == 200:
                data = response.json()
                stores = data.get("stores", [])
                all_stores.extend(stores)
        except Exception as e:
            print(f"Aviso en hub {hub}: {e}")

    # 2. Generar malla de celdas H3 usando los nombres correctos de la librería (v4+)
    target_cells = set()
    for hub in HUBS:
        center_cell = h3.latlng_to_cell(hub['lat'], hub['lng'], 8)
        disk = h3.grid_disk(center_cell, 3)
        target_cells.update(disk)

    # 3. Evaluar densidad y marcar objetivos tácticos (hexágonos rojos)
    for cell in target_cells:
        c_lat, c_lng = h3.cell_to_latlng(cell)
        
        store_score = 0
        for store in all_stores:
            if store.get("is_open", False):
                s_lat = store.get("lat", 0)
                s_lng = store.get("lng", 0)
                if abs(s_lat - c_lat) < 0.008 and abs(s_lng - c_lng) < 0.008:
                    store_score += store.get("average_ticket_score", 60)

        # Criterio táctico: Asegurar visualización de zonas calientes en centros comerciales y alta actividad
        is_target = store_score > 30 or any(abs(hub['lat'] - c_lat) < 0.025 and abs(hub['lng'] - c_lng) < 0.025 for hub in HUBS)
        
        color = "#ff4d4d" if is_target else "#3388ff"
        opacity = 0.65 if is_target else 0.03 

        boundary = list(h3.cell_to_boundary(cell))

        analyzed_hexagons[cell] = {
            "cell": cell,
            "boundary": boundary,
            "color": color,
            "opacity": opacity,
            "score": store_score
        }

    output = {
        "status": "success",
        "hexagons": list(analyzed_hexagons.values())
    }

    with open("radar_data.json", "w") as f:
        json.dump(output, f)

if __name__ == "__main__":
    generate_radar()
