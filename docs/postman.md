# Probar la API con Postman

Ejemplos para probar cada endpoint de la API en Postman, con la respuesta esperada y un
script de **Tests** que comprueba el resultado automáticamente. Los valores esperados son los
del dataset completo (1.878.525 incendios) después de correr todo el sistema.

## 0. Preparación

1. Levanta el sistema y espera a que la API esté lista (etapa 3):

   ```bash
   docker compose up --build -d
   docker compose ps api        # debe decir "(healthy)"
   ```

2. En Postman crea un **Environment** (por ejemplo `wildfires-local`) con esta variable y
   selecciónalo arriba a la derecha:

   | Variable  | Valor                   |
   |-----------|-------------------------|
   | `baseUrl` | `http://localhost:5000` |

3. Crea una **Collection** (por ejemplo `US Wildfires API`) y agrega dentro cada petición de
   esta guía. En cada petición, el script va en la pestaña **Scripts → Post-response**
   (en versiones antiguas de Postman, pestaña **Tests**).

> Desde Windows, `localhost:5000` llega a los contenedores de Docker Desktop que corren en
> WSL. Si no responde, prueba con la IP de WSL (`hostname -I` dentro de WSL).

---

## 1. Estado del servicio: `GET /health`

| Campo  | Valor                 |
|--------|-----------------------|
| Método | `GET`                 |
| URL    | `{{baseUrl}}/health`  |

Respuesta esperada (`200`):

```json
{ "status": "ok", "fires": 1878525 }
```

Tests:

```javascript
pm.test("Status 200", () => pm.response.to.have.status(200));
pm.test("MongoDB responde y tiene los incendios", () => {
    const body = pm.response.json();
    pm.expect(body.status).to.eql("ok");
    pm.expect(body.fires).to.be.above(1000000);
});
```

---

## 2. Incendios cercanos con `$near`: `GET /fires/near`

Devuelve los incendios dentro de un radio, **ordenados del más cercano al más lejano**.

| Campo  | Valor                     |
|--------|---------------------------|
| Método | `GET`                     |
| URL    | `{{baseUrl}}/fires/near`  |

En la pestaña **Params**:

| Key         | Value     | Obligatorio | Notas                          |
|-------------|-----------|-------------|--------------------------------|
| `lat`       | `34.05`   | Sí          | Latitud, −90 a 90              |
| `lon`       | `-118.25` | Sí          | Longitud, −180 a 180           |
| `radius_km` | `5`       | No          | Por defecto 10, máximo 500     |
| `limit`     | `3`       | No          | Por defecto 100, máximo 1000   |
| `cause`     | `Arson`   | No          | Filtro por causa               |
| `state`     | `CA`      | No          | Filtro por estado              |
| `year`      | `2005`    | No          | Filtro por año (1992–2015)     |

URL resultante: `{{baseUrl}}/fires/near?lat=34.05&lon=-118.25&radius_km=5&limit=3`

Respuesta esperada (`200`, recortada):

```json
{
  "type": "FeatureCollection",
  "radius_km": 5.0,
  "limit": 3,
  "returned": 3,
  "features": [
    {
      "type": "Feature",
      "id": 201642243,
      "geometry": { "type": "Point", "coordinates": [-118.24016, 34.055727] },
      "properties": { "fod_id": 201642243, "fire_year": "...", "stat_cause_descr": "...", "state": "CA", "discovery_date": "YYYY-MM-DD", "...": "..." }
    }
  ]
}
```

Tests:

```javascript
pm.test("Status 200", () => pm.response.to.have.status(200));
pm.test("Devuelve un FeatureCollection de puntos", () => {
    const body = pm.response.json();
    pm.expect(body.type).to.eql("FeatureCollection");
    body.features.forEach(f => pm.expect(f.geometry.type).to.eql("Point"));
});
pm.test("Respeta el limit", () => {
    const body = pm.response.json();
    pm.expect(body.returned).to.be.at.most(Number(pm.request.url.query.get("limit")));
});
pm.test("Responde en menos de 500 ms", () => pm.expect(pm.response.responseTime).to.be.below(500));
```

**Prueba con filtros:** agrega `cause=Arson` y sube `radius_km` a `50` y `limit` a `1000`.
Deberían volver unos 466 incendios provocados en un radio de 50 km del centro de Los Ángeles.

---

## 3. Incendios dentro de un polígono con `$geoWithin`: `POST /fires/within`

El polígono va en el **body** como GeoJSON. Se acepta una geometría `Polygon` o
`MultiPolygon`, o un `Feature` que la contenga.

| Campo  | Valor                       |
|--------|-----------------------------|
| Método | `POST`                      |
| URL    | `{{baseUrl}}/fires/within`  |
| Params | `limit=2` (opcional, también acepta `cause`, `state`, `year`) |
| Body   | **raw → JSON**              |

> GeoJSON usa el orden `[longitud, latitud]` y el anillo debe cerrarse: el primer punto se
> repite al final.

### 3a. Rectángulo que cubre California

```json
{
  "type": "Polygon",
  "coordinates": [[
    [-124.4, 32.5], [-114.1, 32.5], [-114.1, 42.0], [-124.4, 42.0], [-124.4, 32.5]
  ]]
}
```

Respuesta esperada (`200`, recortada). `total` es el número de incendios dentro del polígono
y `returned` los que se devolvieron según `limit`:

```json
{
  "type": "FeatureCollection",
  "total": 208672,
  "limit": 2,
  "returned": 2,
  "features": [ "..." ]
}
```

Tests:

```javascript
pm.test("Status 200", () => pm.response.to.have.status(200));
pm.test("Cuenta los incendios del polígono", () => {
    const body = pm.response.json();
    pm.expect(body.total).to.be.above(0);
    pm.expect(body.returned).to.be.at.most(body.total);
});
pm.test("Todos los puntos están dentro del rectángulo", () => {
    pm.response.json().features.forEach(f => {
        const [lon, lat] = f.geometry.coordinates;
        pm.expect(lon).to.be.within(-124.4, -114.1);
        pm.expect(lat).to.be.within(32.5, 42.0);
    });
});
```

### 3b. Mismo polígono como `Feature`, con filtros

URL: `{{baseUrl}}/fires/within?limit=2&cause=Lightning&year=2008`

```json
{
  "type": "Feature",
  "properties": { "name": "California" },
  "geometry": {
    "type": "Polygon",
    "coordinates": [[
      [-124.4, 32.5], [-114.1, 32.5], [-114.1, 42.0], [-124.4, 42.0], [-124.4, 32.5]
    ]]
  }
}
```

Esperado: `total` = **1348** (incendios por rayo en 2008 dentro del rectángulo).

### 3c. Polígono pequeño: área de Los Ángeles

```json
{
  "type": "Polygon",
  "coordinates": [[
    [-118.7, 33.7], [-117.9, 33.7], [-117.9, 34.4], [-118.7, 34.4], [-118.7, 33.7]
  ]]
}
```

> Para dibujar tus propios polígonos usa https://geojson.io: dibuja el área, copia la
> geometría del panel derecho y pégala como body.

---

## 4. Incendios más cercanos con distancia (`$geoNear`): `GET /fires/nearest`

Agregación con `$geoNear`. A diferencia de `$near`, devuelve la **distancia en km** de cada
incendio (`properties.distance_km`).

| Campo  | Valor                       |
|--------|-----------------------------|
| Método | `GET`                       |
| URL    | `{{baseUrl}}/fires/nearest` |

Params:

| Key      | Value     | Obligatorio | Notas                       |
|----------|-----------|-------------|-----------------------------|
| `lat`    | `37.77`   | Sí          | San Francisco               |
| `lon`    | `-122.42` | Sí          |                             |
| `max_km` | `30`      | No          | Por defecto 50, máximo 500  |
| `limit`  | `3`       | No          |                             |
| `year`   | `2015`    | No          | También `cause` y `state`   |

Tests:

```javascript
pm.test("Status 200", () => pm.response.to.have.status(200));
pm.test("Cada incendio trae su distancia en km", () => {
    pm.response.json().features.forEach(f => {
        pm.expect(f.properties).to.have.property("distance_km");
        pm.expect(f.properties.distance_km).to.be.at.most(30);
    });
});
pm.test("Ordenados del más cercano al más lejano", () => {
    const d = pm.response.json().features.map(f => f.properties.distance_km);
    pm.expect(d).to.eql([...d].sort((a, b) => a - b));
});
pm.test("Aplica el filtro de año", () => {
    pm.response.json().features.forEach(f => pm.expect(f.properties.fire_year).to.eql(2015));
});
```

---

## 5. Resultados de Spark: `GET /stats` y `GET /stats/<nombre>`

`GET {{baseUrl}}/stats` lista los resultados disponibles. Cada uno se consulta con
`GET {{baseUrl}}/stats/<nombre>`; `limit` es opcional (sin él devuelve todo).

| Petición                              | Qué devuelve                                         | Formato            |
|---------------------------------------|------------------------------------------------------|--------------------|
| `{{baseUrl}}/stats/hotspots?limit=5`  | Zonas de alta concentración, por `rank`             | GeoJSON (polígonos) |
| `{{baseUrl}}/stats/grid`              | Las 4.316 celdas de 0,5° con incendios               | GeoJSON (polígonos) |
| `{{baseUrl}}/stats/hour`              | Incendios por hora 0–23                              | JSON (`results`)   |
| `{{baseUrl}}/stats/weekday`           | Por día de la semana (1 = domingo)                   | JSON               |
| `{{baseUrl}}/stats/month`             | Por mes                                              | JSON               |
| `{{baseUrl}}/stats/year`              | Por año                                              | JSON               |
| `{{baseUrl}}/stats/state`             | Por estado, de más a menos incendios                 | JSON               |
| `{{baseUrl}}/stats/cause`             | Por causa, de más a menos incendios                  | JSON               |

Ejemplo `GET {{baseUrl}}/stats/hotspots?limit=1`: el primer hotspot es la celda `-148_81`
(Nueva York / Long Island) con 10.476 incendios.

Tests para `/stats/hotspots`:

```javascript
pm.test("Status 200", () => pm.response.to.have.status(200));
pm.test("Hotspots como polígonos ordenados por rank", () => {
    const body = pm.response.json();
    pm.expect(body.type).to.eql("FeatureCollection");
    const ranks = body.features.map(f => f.properties.rank);
    pm.expect(ranks).to.eql([...ranks].sort((a, b) => a - b));
    body.features.forEach(f => pm.expect(f.geometry.type).to.eql("Polygon"));
});
```

Tests para `/stats/month`:

```javascript
pm.test("12 meses que suman todos los incendios", () => {
    const results = pm.response.json().results;
    pm.expect(results).to.have.lengthOf(12);
    const total = results.reduce((sum, m) => sum + m.fires, 0);
    pm.expect(total).to.eql(1878525);
});
```

> Truco para la presentación: copia la respuesta de `/stats/hotspots` o de `/fires/within`
> y pégala en https://geojson.io para verla en un mapa.

---

## 6. Casos de error

La API valida los parámetros y responde con un JSON `{ "error": ..., "message": ... }`.

| Petición                                                     | Código | Mensaje (resumen)                          |
|--------------------------------------------------------------|--------|--------------------------------------------|
| `GET {{baseUrl}}/fires/near?lon=0`                           | 400    | `'lat' is required`                        |
| `GET {{baseUrl}}/fires/near?lat=95&lon=0`                    | 400    | `'lat' must be between -90 and 90, got 95` |
| `GET {{baseUrl}}/fires/near?lat=abc&lon=0`                   | 400    | `'lat' must be a number`                   |
| `GET {{baseUrl}}/fires/near?lat=0&lon=0&radius_km=10000`     | 400    | `'radius_km' must be between 0 and 500`    |
| `GET {{baseUrl}}/fires/near?lat=0&lon=0&limit=0`             | 400    | `'limit' must be between 1 and 1000`       |
| `POST {{baseUrl}}/fires/within` con body `{"type": "Point", "coordinates": [0, 0]}` | 400 | `The geometry must be a GeoJSON Polygon or MultiPolygon` |
| `POST {{baseUrl}}/fires/within` con un polígono que se cruza a sí mismo (abajo) | 400 | `Loop is not valid ...` (lo rechaza MongoDB) |
| `GET {{baseUrl}}/stats/nope`                                 | 404    | `Unknown result 'nope'. Available: ...`    |

Polígono inválido ("corbatín", sus lados se cruzan):

```json
{ "type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]] }
```

Tests para cualquier caso de error (cambia el código esperado según la fila):

```javascript
pm.test("Status 400", () => pm.response.to.have.status(400));
pm.test("Error en JSON con mensaje", () => {
    const body = pm.response.json();
    pm.expect(body).to.have.property("error");
    pm.expect(body.message).to.be.a("string").and.not.empty;
});
```

---

## 7. Correr todo de una vez

Con todas las peticiones en la Collection:

1. Clic derecho sobre la Collection → **Run collection**.
2. Selecciona el environment `wildfires-local` y pulsa **Run**.
3. Postman ejecuta cada petición en orden y muestra cuántos tests pasaron y cuáles fallaron.

Esto sirve para la sustentación: después de que Jenkins despliegue un cambio, correr la
Collection demuestra en segundos que todos los endpoints siguen funcionando.
