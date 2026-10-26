import json
import httpx
import h3

# Coordenadas base de tu zona de operaciones habitual (ej. centro de tu ciudad)
# Si estás en otra ciudad, puedes cambiar estos valores por tu latitud y longitud aproximadas.
BASE_LAT = -34.6037
BASE_LNG = -58.3816

def generate_radar():
    current_cell = h3.latLngToCell(BASE_LAT, BASE_LNG, 8)
    surrounding_cells = h3.grid_disk(current_cell, 2)
    
    analyzed_hexagons = []

    # Consultar API pública de tiendas cercanas
    stores_endpoint = f"https://www.rappi.com.ar/api/rocket/stores?lat={BASE_LAT}&lng={BASE_LNG}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = httpx.get(stores_endpoint, headers=headers, timeout=5.0)
        stores = response.json().get("stores", []) if response.status_code == 200 else []
    except:
        stores = []

    for cell in surrounding_cells:
        c_lat, c_lng = h3.cell_to_latlng(cell)
        
        store_score = 0
        for store in stores:
            if store.get("is_open", False):
                s_lat = store.get("lat", 0)
                s_lng = store.get("lng", 0)
                if abs(s_lat - c_lat) < 0.003 and abs(s_lng - c_lng) < 0.003:
                    store_score += store.get("average_ticket_score", 50)

        # Criterio: Si el score supera el nivel de alta demanda con baja competencia
        is_target = store_score > 150
        
        # Estilo visual: Totalmente transparente por defecto, rojo sólido si es objetivo
        color = "#ff4d4d" if is_target else "#3388ff"
        opacity = 0.55 if is_target else 0.04 

        analyzed_hexagons.append({
            "cell": cell,
            "boundary": h3.cell_to_boundary(cell),
            "color": color,
            "opacity": opacity,
            "score": store_score
        })

    output = {
        "status": "success",
        "hexagons": analyzed_hexagons
    }

    with open("radar_data.json", "w") as f:
        json.dump(output, f)

if __name__ == "__main__":
    generate_radar()
