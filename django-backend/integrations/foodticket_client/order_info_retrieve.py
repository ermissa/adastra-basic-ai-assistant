import requests
import xml.etree.ElementTree as ET
import io
from datetime import datetime, timedelta
from typing import List, Dict


def fetch_flat_orders_by_phone_last_3_days(
    phone: int,
    client_id: int = 3517,
    api_key: str = "564ff05d0a9c61d030431330952a56c0"
) -> List[Dict]:
    url = (
        f"https://api.foodticket.net/1/orders?client_id={client_id}"
        f"&stel={phone}&"
        f"page=0&perpage=1"
    )
    headers = {"X-OrderBuddy-Reseller-Key": api_key}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"API request failed. Status code: {response.status_code}")

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

    if len(flat_orders) > 0:
        return flat_orders[0]
    return 'not found'


# Example usage
if __name__ == "__main__":
    phone_number = 31615373364
    flat_result = fetch_flat_orders_by_phone_last_3_days(31615373364)
    print(flat_result)
