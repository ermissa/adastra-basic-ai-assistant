import requests

import xml.etree.ElementTree as ET
import io
from datetime import datetime, timedelta
from typing import List, Dict
client_id = 3517
api_key = '564ff05d0a9c61d030431330952a56c0'
url = (
        f"https://api.foodticket.net/1/orders?client_id={client_id}"
    )


headers = {"X-OrderBuddy-Reseller-Key": api_key}

response = requests.get(url, headers=headers)

xml_stream = io.BytesIO(response.content)
flat_orders = []
for event, elem in ET.iterparse(xml_stream, events=("end",)):
    if elem.tag == "order":
        base_order = {
            "order_id": elem.findtext("id"),
            "client_id": elem.findtext("client_id"),
            "order_date": (elem.findtext("date") or "").split(" ")[0],
            "order_time": (elem.findtext("date") or "").split(" ")[1]
            if " " in (elem.findtext("date") or "") else "",
            "firstname": elem.findtext("firstname") or "",
            "lastname": elem.findtext("lastname") or "",
            "phone": elem.findtext("tel") or "",
            "email": elem.findtext("email") or "",
            "address": elem.findtext("address") or "",
            "status": elem.findtext("status"),
            "tip": elem.findtext("tip"),
            "delivery_cost": elem.findtext("delivery_costs"),
            "total_price": elem.findtext("total"),
        }
        for orderline in elem.findall("orderline"):
            flat_orders.append({
                **base_order,
                "product_title": orderline.findtext("title"),
                "product_category": orderline.findtext("category_title"),
                "product_extras": orderline.findtext("extras"),
                "product_price": orderline.findtext("price"),
            })

from collections import defaultdict
extras = defaultdict(set)
for product in flat_orders:
    extras[product['product_title']].add(product['product_extras'])



url = f"https://api.foodticket.net/1/products?client_id={client_id}"

response = requests.get(url, headers=headers)
xml_stream = io.BytesIO(response.content)
root = ET.parse(xml_stream).getroot()

products = []
for row in root.findall("row"):
    product = {
        "title": row.findtext("title"),
        "description": row.findtext("description"),
        "description_extras": row.findtext("description_extras"),
        "price": row.findtext("price"),
        "delivery": row.findtext("delivery"),
        "vegan": row.findtext("vegan"),
        'row': row
    }
    products.append(product)

product_extras = defaultdict(set)
for product in products:
    product_extras[product['title']].add(product['description_extras'])

from collections import Counter

extras_counter = Counter([i for key,values in product_extras.items() for i in values])
for extra, c in extras_counter.items():
    print(f"{extra} ========================>>    passing {c} times")


extras

extras_counter1 = Counter([i for key,values in extras.items() for i in values])
for extra, c in extras_counter1.items():
    print(f"{extra} ========================>>    passing {c} times")


product_descriptions =  defaultdict(set)
for product in products:
    product_descriptions[product['title']].add(product['description'])

for title, description in product_descriptions.items():
    print(f"extras of the {title} {'are' if len(list(description)[0])>0 else 'has no ingradients'} {','.join(description)}")


for title, description in extras.items():
    print(f"extras of the {title}:  {','.join(description)}")