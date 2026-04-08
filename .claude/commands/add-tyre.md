# Add a tyre to the catalogue

Add a new tyre entry to `app/data/tyres.json`. Follow the schema exactly.

## Schema for a tyre entry

```json
{
  "id": "BRAND-MODEL-SIZE",
  "brand": "Michelin",
  "model": "Primacy 4",
  "size": "205/55R16",
  "load_index": 91,
  "speed_rating": "V",
  "season": "all-season",
  "terrain": "highway",
  "price": 189.99,
  "member_price": 169.99,
  "tread_life_km": 80000,
  "wet_grip": "A",
  "noise_db": 68,
  "rating": 4.8,
  "review_count": 1240,
  "warranty_years": 5,
  "compatible_vehicles": ["Toyota Camry 2018-2023", "Honda Accord 2017-2022"],
  "stock": {"warehouse_id": "W001", "qty": 24},
  "active_promotion": "Save $20 on set of 4"
}
```

## Steps to add

1. Open `app/data/tyres.json`
2. Add the new entry to the JSON array
3. Ensure `id` is unique (format: `BRAND_ABBREV-MODEL_ABBREV-SIZE_NODASH`)
4. Restart the server — services reload data on startup

## Valid field values

- `season`: `"all-season"` | `"winter"` | `"summer"`
- `terrain`: `"highway"` | `"city"` | `"all-terrain"`
- `speed_rating`: `"H"` | `"V"` | `"W"` | `"Y"`
- `wet_grip`: `"A"` | `"B"` | `"C"`
- `stock.warehouse_id`: `"W001"` (Seattle) | `"W002"` (Portland) | `"W003"` (San Francisco) | `"W004"` (Los Angeles) | `"W005"` (Phoenix)
