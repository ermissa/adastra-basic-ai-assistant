import requests
import xml.etree.ElementTree as ET
import io
from typing import Dict, Union


def get_zipcode_info(postcode: str, client_id: int = 3517, api_key: str = "564ff05d0a9c61d030431330952a56c0") -> Union[Dict, str]:
    url = f"https://api.foodticket.net/1/zipcodes?client_id={client_id}"
    headers = {"X-OrderBuddy-Reseller-Key": api_key}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"API request failed. Status code: {response.status_code}")

    xml_stream = io.BytesIO(response.content)
    root = ET.parse(xml_stream).getroot()

    for row in root.findall("row"):
        zip_code = row.findtext("start")
        if zip_code == postcode[:4]:
            return {
                "postcode": zip_code,
                "costs": row.findtext("costs"),
                "min_order": row.findtext("min"),
                "available": row.findtext("available") == "1",
                "free_delivery": row.findtext("free") == "1",
            }

    return f"❌ Postcode {postcode} is out of our delivery options."


# Example usage
if __name__ == "__main__":
    result = get_zipcode_info("1018")
    print(result)
