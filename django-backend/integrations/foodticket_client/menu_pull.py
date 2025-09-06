import requests
import xml.etree.ElementTree as ET
import io
import json
import os
import pandas as pd
from difflib import get_close_matches

def parse_xml_to_dataframe(xml_content: str) -> pd.DataFrame:
    # Parse XML
    root = ET.fromstring(xml_content)

    # Prepare data lists
    row_data = []
    item_data = []

    # Loop through each <row>
    for row in root.findall("row"):
        row_dict = {child.tag: child.text for child in row if child.tag != "items"}
        row_data.append(row_dict)

        items = row.find("items")
        if items is not None:
            for item in items.findall("item"):
                item_dict = {child.tag: child.text for child in item}
                item_dict["extra_id"] = row.find("id").text  # Link item to row
                item_data.append(item_dict)

    # Convert to DataFrames
    df_rows = pd.DataFrame(row_data)
    df_items = pd.DataFrame(item_data)

    # Filter necessary columns
    df_rows = df_rows[['product_ids', 'mandatory', 'id', 'items_str',
                       'products_n', 'title', 'selectable', 'categories_n']]

    df_items = df_items[['id', 'pack_costs', 'extra_id', 'prio', 'price', 'title']]

    # Merge and clean
    result = pd.merge(df_rows, df_items, left_on='id', right_on='extra_id', how='inner')
    result = result.drop(columns=['id_x'])  # Drop duplicate column

    # Rename columns
    result = result.rename(columns={
        'title_x': 'group_name',
        'extra_id':'group_id',
        'title_y':'product_name',
        'items_str': 'item_list',
        'id_y': 'product_id'
    })

    return result

def fetch_extras_info(client_id, api_key):
    if os.path.exists("extras_api_data.json"):
        with open("extras_api_data.json", "r", encoding="utf-8") as f:
            loaded_data = json.load(f)
            return loaded_data
    
    url = f"https://api.foodticket.net/1/extras?client_id={client_id}"
    headers = {
        "X-OrderBuddy-Reseller-Key": api_key
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"API request failed. Status code: {response.status_code}")

    final_df = parse_xml_to_dataframe(response.text)
    final_df['product_ids'] = final_df['product_ids'].str.split(',')
    final_df = final_df.explode('product_ids')
    filtered_df = final_df[final_df.product_ids=='2649158']
    grouped_dict = filtered_df.groupby('group_name')['product_name'].apply(list).to_dict()
    with open("extras_api_data.json", "w", encoding="utf-8") as f:
        json.dump(grouped_dict, f, indent=4)

    return grouped_dict

def get_extras_info(product_id, client_id, api_key):
    grouped_dict = fetch_extras_info(client_id, api_key) 
    return {
        'toppings': grouped_dict['Toppings'],
        'size': grouped_dict['Bodem'],
        'drinks': grouped_dict['Wil je er drankje of taartje bij?'],
        'edge': grouped_dict['Heerlijke zaadjes voor de rand van je pizza']
    }

def fetch_products(client_id: int = 3517, api_key: str = "564ff05d0a9c61d030431330952a56c0"):
    if os.path.exists("product_api_data.json"):
        with open("product_api_data.json", "r", encoding="utf-8") as f:
            loaded_data = json.load(f)
            return loaded_data
    # Fetch products
    url = f"https://api.foodticket.net/1/products?client_id={client_id}"
    headers = {"X-OrderBuddy-Reseller-Key": api_key}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"API request failed. Status code: {response.status_code}")

    xml_stream = io.BytesIO(response.content)
    root = ET.parse(xml_stream).getroot()

    products = []
    for row in root.findall("row"):
        product = {
            "id": row.findtext("id"),
            "title": row.findtext("title"),
            "description": row.findtext("description"),
            "description_extras": row.findtext("description_extras"),
            "price": row.findtext("price"),
            "delivery": row.findtext("delivery"),
            "vegan": row.findtext("vegan"),
        }
        products.append(product)
    
    with open("product_api_data.json", "w", encoding="utf-8") as f:
        json.dump(products, f, indent=4)
    
    return products


def find_product_by_name(product_name: str, client_id: int = 3517, api_key: str = "564ff05d0a9c61d030431330952a56c0") -> None:
    """
    Fetches products from the Foodticket API, finds the closest match for the given product name,
    and prints the matched product details.
    """
    products = fetch_products()
    # Fuzzy match
    titles = [p["title"] for p in products if p.get("title")]
    matches = get_close_matches(product_name, titles, n=1, cutoff=0.5)
    match = matches[0] if matches else None

    if not match:
        print("Product not found.")
        return

    for product in products:
        if product["title"].lower() == match.lower():
            print("Matched Product Details:")
            for key, value in product.items():
                print(f"{key.capitalize()}: {value}")
            
            product['extras'] = get_extras_info(product['id'], client_id, api_key)
            return product

    print("Matched title not found in product list.")


# Example usage:
if __name__ == "__main__":
    find_product_by_name("margarita pizza")
