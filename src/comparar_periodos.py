import json
import requests
import re
import os
from datetime import datetime
from collections import defaultdict

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'datasets.json')
BASE_API_URL = "https://catalogodatos.gub.uy/api/3/action/package_show?id={}"

def parse_date(date_str):
    formats = [
        ("%Y", "%Y"),
        ("%Y-%m", "%Y-%m"),
        ("%Y-%m-%d", "%Y-%m-%d"),
        ("%m/%Y", "%m/%Y"),
        ("%d/%m/%Y", "%d/%m/%Y"),
    ]
    for fmt_in, fmt_out in formats:
        try:
            return datetime.strptime(date_str, fmt_in)
        except ValueError:
            pass
    return None

def extract_date_range(name):
    name_lower = name.lower()
    
    month_year = re.findall(r'(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)[_\- ](\d{4})', name_lower)
    if month_year:
        months = {"ene":"01","feb":"02","mar":"03","abr":"04","may":"05","jun":"06",
                  "jul":"07","ago":"08","sep":"09","oct":"10","nov":"11","dic":"12"}
        dates = []
        for m, y in month_year:
            try:
                dates.append(datetime.strptime(f"{y}-{months[m]}", "%Y-%m"))
            except:
                pass
        if len(dates) == 1:
            return dates[0], dates[0]
        elif len(dates) == 2:
            return min(dates), max(dates)
    
    year_range = re.findall(r'(\d{4})', name)
    if year_range:
        years = [int(y) for y in year_range]
        if len(years) == 1:
            return datetime(years[0], 1, 1), datetime(years[0], 12, 31)
        elif len(years) >= 2:
            return datetime(min(years), 1, 1), datetime(max(years), 12, 31)
    
    dates_found = re.findall(r'(\d{4}-\d{2}-\d{2})|(\d{4}-\d{2})|(\d{4})', name)
    dates = []
    for df, dm, dy in dates_found:
        d = parse_date(df or dm or dy)
        if d:
            dates.append(d)
    if len(dates) == 1:
        return dates[0], dates[0]
    elif len(dates) >= 2:
        return min(dates), max(dates)
    
    return None, None

def main():
    try:
        with open(CONFIG_FILE) as f:
            datasets = json.load(f)
    except Exception as e:
        print(f"Error al leer {CONFIG_FILE}: {e}")
        return

    print(f"Consultando {len(datasets)} datasets...\n")

    dataset_periods = {}

    for dataset in datasets:
        title = dataset['title']
        dataset_id = dataset['dataset_id']
        
        print(f"Consultando: {title}...")
        try:
            response = requests.get(BASE_API_URL.format(dataset_id), timeout=10)
            response.raise_for_status()
            dataset_info = response.json()
        except Exception as e:
            print(f"  Error: {e}")
            continue

        recursos = dataset_info['result']['resources']
        
        dataset_periods[title] = {}
        for r in recursos:
            name = r.get('name', '')
            start, end = extract_date_range(name)
            if start:
                dataset_periods[title][name] = (start, end)

    print("\n" + "="*60)
    print("PERIODOS DETECTADOS POR DATASET")
    print("="*60)

    for title, resources in dataset_periods.items():
        if not resources:
            print(f"\n{title}: No se detectaron periodos")
            continue
        
        all_dates = []
        for name, (start, end) in resources.items():
            all_dates.append((start, end))
        
        if all_dates:
            overall_start = min(d[0] for d in all_dates)
            overall_end = max(d[1] for d in all_dates)
            print(f"\n{title}:")
            print(f"  Periodo total: {overall_start.strftime('%Y-%m')} a {overall_end.strftime('%Y-%m')}")
            print(f"  Archivos con fechas detectadas: {len(resources)}")

    titles = list(dataset_periods.keys())
    print("\n" + "="*60)
    print("ANALISIS DE SOLAPAMIENTOS")
    print("="*60)

    for i in range(len(titles)):
        for j in range(i + 1, len(titles)):
            title_a, title_b = titles[i], titles[j]
            periods_a = dataset_periods[title_a]
            periods_b = dataset_periods[title_b]
            
            if not periods_a or not periods_b:
                continue
            
            overlaps = []
            for name_a, (start_a, end_a) in periods_a.items():
                for name_b, (start_b, end_b) in periods_b.items():
                    overlap_start = max(start_a, start_b)
                    overlap_end = min(end_a, end_b)
                    if overlap_start <= overlap_end:
                        overlaps.append((overlap_start, overlap_end, name_a, name_b))
            
            if overlaps:
                print(f"\n{title_a} <-> {title_b}:")
                print(f"  {len(overlaps)} archivos con periodo en comun")
                unique_overlaps = {}
                for start, end, name_a, name_b in overlaps:
                    key = (start.strftime("%Y-%m"), end.strftime("%Y-%m"))
                    if key not in unique_overlaps:
                        unique_overlaps[key] = []
                    unique_overlaps[key].append((name_a, name_b))
                
                for period, pairs in unique_overlaps.items():
                    print(f"  {period[0]} a {period[1]} ({len(pairs)} archivos)")
            else:
                overall_a_start = min(d[0] for d in periods_a.values())
                overall_a_end = max(d[1] for d in periods_a.values())
                overall_b_start = min(d[0] for d in periods_b.values())
                overall_b_end = max(d[1] for d in periods_b.values())
                
                if overall_a_end < overall_b_start or overall_b_end < overall_a_start:
                    print(f"\n{title_a} <-> {title_b}:")
                    print(f"  Sin solapamiento")
                else:
                    overlap_start = max(overall_a_start, overall_b_start)
                    overlap_end = min(overall_a_end, overall_b_end)
                    print(f"\n{title_a} <-> {title_b}:")
                    print(f"  Solapamiento de periods generales: {overlap_start.strftime('%Y-%m')} a {overlap_end.strftime('%Y-%m')}")

if __name__ == "__main__":
    main()
