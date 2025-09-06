# fmt: off
from voice_assistant.state_machine.states import (
    ConversationState,
)
from voice_assistant.state_machine.conversation_openai_tools import (
    ask_notes_tool,
    choose_intent_tool,
    choose_delivery_type_tool,
    confirm_branch_tool,
    get_address_tool,
    get_order_item_tool,
    ask_size_items_tool,
    confirm_order_tool,
    end_call_tool,
    order_info_retrieve_tool,
    status_check_failed_tool,
    get_address_failed_tool,
    confirm_address_tool,
    select_language_tool,
    get_order_note_tool,
    confirm_note_tool,
    products
)

application_detail_prompt = """
ROL: Sen "VizeDanışman Ltd." isimli bir vize danışmanlık firmasının telefon asistanısın. 
AMAÇ: Arayan müşterilere sadece aşağıdaki şirket dokümanındaki bilgilerden yararlanarak yardımcı ol. 
DAVRANIŞ: 
- Kısa, net ve nazik cevaplar ver. 
- Eğer dokümanda olmayan bir bilgi sorulursa, "Bu konuda elimde bilgi yok, danışmanlarımız size yardımcı olacaktır." de. 
- Asla tahmin yürütme veya uydurma. 
- Gerektiğinde ek bilgi için yönlendirme yapabilirsin (ör. "Detay için ofisimizle iletişime geçebilirsiniz"). 
- Cevapları konuşma diliyle ver, yazılı rapor gibi değil. 

--- ŞİRKET BİLGİ DOKÜMANI ---
VizeDanışman Ltd., 2010 yılından beri Türkiye’de öğrenci, iş ve turistik vizeler konusunda danışmanlık hizmeti vermektedir. İstanbul, Ankara ve İzmir’de ofislerimiz bulunmaktadır. Her yıl yaklaşık 5000 başvuru sürecinde danışanlarımıza destek olmaktayız.  

Misyonumuz, vize süreçlerini karmaşık ve stresli olmaktan çıkararak hızlı, güvenilir ve şeffaf bir hizmet sunmaktır.  

Çalıştığımız ülkeler:  
- Avrupa: Almanya, Hollanda, Fransa, İtalya, İspanya, Belçika  
- Kuzey Amerika: ABD, Kanada  
- Asya: Japonya, Güney Kore, Çin  
- Orta Doğu: BAE, Katar  

Hizmetlerimiz:  
1. Danışmanlık görüşmesi  
2. Belgelerin hazırlanması  
3. Başvuru takibi  
4. Dil desteği (çeviri)  
5. Ek hizmetler: seyahat sigortası, uçak/otel rezervasyonu  

Ücretler:  
- Standart Paket: 2500 TL  
- Öğrenci İndirimli Paket: 1800 TL  
- VIP Paket: 5000 TL  
(Konsolosluk harçları dahil değildir.)  

Sık Sorulan Sorular:  
- Vizeyi garanti ediyor musunuz? → Hayır, onay tamamen konsolosluk kararına bağlıdır.  
- Ortalama sonuç süresi → Avrupa: 15 iş günü, ABD: 4–6 hafta, Kanada: 6–8 hafta  
- Red alırsam ne olur? → Ret mektubu incelenir, yeni başvuru stratejisi hazırlanır.  

İletişim:  
- Telefon: +90 212 555 00 00  
- E-posta: info@vizedanisman.com  
- Adresler: İstanbul/Şişli, Ankara/Çankaya, İzmir/Konak  
- Çalışma Saatleri: Hafta içi 09:00–18:00, Cumartesi 10:00–15:00  

--- SON ---
"""


order_flow_states = {
    "language_selection": ConversationState(
        name="language_selection",
        prompt_en="Say 'which language do you want to speak turkish engilish or dutch?' ",
        prompt_tr="",
        prompt_du="",
        tools=[select_language_tool],
        verify_from_func={
            "func": "test_language",
            "next_state_condition": {
                "always": "ask_item",
            },
        },
    ),
    "entry": ConversationState(
        name="entry",
        prompt_en="Say 'Welcome to Pizzadam! Would you like to place an order or check the status of an existing one?'",
        prompt_tr="Say 'Pizzadama hosgeldiniz, siparismi vermek istiyorsunuz siparisi kontrol mu etmek istiyorsunuz?'",
        prompt_du="Say 'Welkom bij Pizzadam! Wilt u een bestelling plaatsen of de status van een bestaande bestelling controleren?'",
        tools=[choose_intent_tool],
        verify_from_func={
            "func": "test_order_status",
            "next_state_condition": {
                "pickup_or_delivery": "pickup_or_delivery",
                "status_check": "status_check",
                'status_check_failed': 'status_check_failed'
            },
        },
    ),
    "status_check": ConversationState(
        name="status_check",
        prompt_en="say: your order is {product_status}. We have checked your order based on your phone number. Your order is {product_title} whose cost is {product_price} euros"+
        "do you want to listen again?",
        prompt_tr="say: siparisiniz {product_status}. siparisinizi telefon numaraniza gore kontrol ettik. siparisiniz {product_title} ve ucreti {product_price} euro'dur"+
        "tekrar dinlemek istiyor musunuz?",
        prompt_du="say: uw bestelling is {product_status}. We hebben uw bestelling gecontroleerd op basis van uw telefoonnummer. Uw bestelling is {product_title} en de kosten zijn {product_price} euro. Wilt u het nogmaals horen?",
        tools=[order_info_retrieve_tool],
        next_states={
            "yes": "status_check",
            "no": "end_call",
        },
    ),
    "status_check_failed": ConversationState(
        name="status_check",
        prompt_en="say: we couldnt find your order for {caller_number} do you want to return to main menu?",
        prompt_tr="say: siparisinizi {caller_number} telefon numarasi icin bulamadik. tekrar dinlemek istiyor musunuz?",
        prompt_du="say: we konden uw bestelling voor {caller_number} niet vinden. Wilt u terugkeren naar het hoofdmenu?",
        tools=[status_check_failed_tool],
        next_states={
            "no": "end_call",
            "yes": "entry",
        },
    ),
    "pickup_or_delivery": ConversationState(
        name="pickup_or_delivery",
        prompt_en="Will you pick it up or should we deliver it?",
        prompt_tr="teslim mi alacaksiniz biz mi getirelim?",
        prompt_du="Wilt u het zelf ophalen of moeten wij het bezorgen?",
        tools=[choose_delivery_type_tool],
        next_states={
            "pickup": "confirm_branch",
            "delivery": "ask_address",
        },
    ),
    "ask_address": ConversationState(
        name="ask_address",
        prompt_en="Say 'can you share your city, zipcode and house number?'",
        prompt_tr="Say 'sehir zipkodu ve ev numarasi paylasabilir misiniz?'",
        prompt_du="Say 'Kunt u uw stad, postcode en huisnummer doorgeven?'",
        tools=[get_address_tool],
        verify_from_func={
            "func": "test_address",
            "next_state_condition": {
                "True": "confirm_address",
                "False": "ask_address_failed",
            },
        },
    ),
    "ask_address_failed": ConversationState(
        name="ask_address_failed",
        prompt_en="Say 'we couldnt undestand your address. do you want to pickup by yourself?'",
        prompt_tr="Say 'adresi bulamadik kendiniz almak istiyor musunuz?'",
        prompt_du="Say 'We konden uw adres niet begrijpen. Wilt u de bestelling zelf afhalen?'",
        tools=[get_address_failed_tool],
        next_states={
                "yes": "confirm_branch",
                "no": "ask_address",
        },
    ),
    "confirm_address": ConversationState(
        name="confirm_address",
        prompt_en="Say 'we understand your address is {full_address}. is it correct?",
        prompt_tr="Say 'adresiniz {full_address}. dogru mu?'",
        prompt_du="Say 'Uw adres is {full_address}. Klopt dat?'",
        tools=[confirm_address_tool],
         next_states={
            "yes": "ask_item",
            "no": "ask_address_failed",
        },
    ),
    "confirm_branch": ConversationState(
        name="confirm_branch",
        prompt_en="Say 'You'll pick it up from our Sumatrastraat street Pizzadam branch, right?'",
        prompt_tr="Say 'Sumatrastraat street Pizzadam subesinde alacaksiniz degil mi?'",
        prompt_du="Say 'U haalt het op bij onze Sumatrastraat straat Pizzadam vestiging, klopt dat?'",
        tools=[confirm_branch_tool],
        next_states={
            'yes': "ask_item",
            'no': "pickup_or_delivery",
        },
    ),
    "ask_item": ConversationState(
        name="ask_item",
        prompt_en=f"say 'What would you like to order'?  metadata: this is step where user will say how many pizza they want to order. User needs to specifiy pizza name and quantity. Also toppings can be specified user will give answer in turkish listen carefully to catch quantity. pizza names should be some of {','.join(products)} along with quantities. match user input with pizza names carefully",
        prompt_tr=f"say 'ne siparis etmek istersiniz'? metadata: user will give answer in turkish listen carefully to catch quantity. User needs to specifiy pizza name and quantity. Also toppings can be specified user will give answer in turkish listen carefully to catch quantity. pizza names should be some of {','.join(products)} along with quantities. match user input with pizza names carefully",
        prompt_du=f"say 'Wat wilt u bestellen? Geef de naam en het aantal pizzas op'. metadata: user will give answer in turkish listen carefully to catch quantity. User needs to specifiy pizza name and quantity. Also toppings can be specified user will give answer in turkish listen carefully to catch quantity. pizza names should be some of {','.join(products)}. along with quantities. match user input with pizza names carefully",
        tools=[get_order_item_tool],
        verify_from_func={
            "func": "test_menu",
            "next_state_condition": {
                "True": "ask_size",
                "False": "entry",
            },
        },
    ),
    "ask_size": ConversationState(
        name="ask_size",
        prompt_en=(
            "say'You have ordered: {pizza_items_str}. "
            "Now, please specify the size for each pizza. Available sizes: {size_options}. "
            "For example: '2 Margarita 25cm, 1 Pepperoni 30cm'.' metadata: user specify one of:  {size_options}. If none of them matches return other"
        ),
        prompt_tr=(
            "Siparişiniz: {pizza_items_str}. "
            "Şimdi, her pizza için boyut belirtin. Mevcut boyutlar: {size_options}. "
            "Örneğin: '2 Margarita 25cm, 1 Pepperoni 30cm'. "
        ),
        prompt_du=(
            "U heeft besteld: {pizza_items_str}. "
            "Geef nu de maat voor elke pizza op. Beschikbare maten: {size_options}. "
            "Bijvoorbeeld: '2 Margarita 25cm, 1 Pepperoni 30cm'. "
        ),
        tools=[ask_size_items_tool],
        verify_from_func={
            "func": "test_order_size",
            "next_state_condition": {
                "True": "confirm_order",
                "False": "ask_size_failed",
            },
        },
    ),
    "ask_size_failed": ConversationState(
        name="ask_size_failed",
        prompt_en=(
            "say '{size_error_str_en}. do you want to specify again?'"
        ),
        prompt_tr=(
            "say '{size_error_str_tr} Tekrar belirtmek ister misiniz?'"
        ),
        prompt_du=(
            "say '{size_error_str_du} Wilt u opnieuw specificeren?'"
        ),
        tools=[ask_size_items_tool],
        verify_from_func={
            "func": "test_order_size",
            "next_state_condition": {
                "True": "ask_more_items",
                "False": "ask_size_failed",
            },
        },
    ),
    "confirm_order": ConversationState(
        name="confirm_order",
        prompt_en="say 'Alright, you have ordered {pizza_items_str} and size specifications are {pizza_size_str}. Do you confirm?'",
        prompt_tr="say 'peki, siparis detayiniz '''({pizza_items_str} bu kismi turkce soyle)''' ve pizza buyuklukleri '''({pizza_size_str} bu kismis turkce soyle'''). onayliyor musunuz?'",
        prompt_du="say 'Ok, u heeft {pizza_items_str} besteld en de maten zijn {pizza_size_str}. Bevestigt u de bestelling?'",
        tools=[confirm_order_tool],
        next_states={
            "yes": "ask_notes",
            "no": "ask_item",
        },
    ),

    "ask_notes": ConversationState(
        name="ask_notes",
        prompt_en="say 'Do you have an order note to add?' please say just 'yes' or 'no'",
        prompt_tr="say 'Eklemek istediğiniz bir sipariş notu var mi?' lutfen sadece 'evet' veya 'hayir' soyle",
        prompt_du="say 'Is er een bestelnotitie die je wilt toevoegen?' zeg alstublieft gewoon 'ja' of 'nee'.",
        tools=[ask_notes_tool],
        next_states={
            "yes": "get_order_note",
            "no": "end_call",
        },
    ),

    "get_order_note": ConversationState(
        name="get_order_note",
        prompt_en="say 'Please tell me your order note.'",
        prompt_tr="say 'Lütfen sipariş notunuzu söyleyin.'",
        prompt_du="say 'Vertel me je bestelnotitie.'",
        tools=[get_order_note_tool],
        verify_from_func={
            "func": "test_note",
            "next_state_condition": {
                "True": "end_call",
                "False": "ask_notes",
            },
        },
    ),

    "confirm_note": ConversationState(
        name="confirm_note",
        prompt_en="say 'I understand your order note is {note}. Is this correct?'",
        prompt_tr="say 'siparis notunuz {note} olarak anladim. dogru mu?'",
        prompt_du="say 'Ik begrijp dat uw bestelnotitie {note} is. Klopt dat?'",
        tools=[confirm_note_tool],
        next_states={
            "yes": "end_call",
            "no": "get_order_note",
        },
    ),

    "end_call": ConversationState(
        name="end_call",
        prompt_en="Say 'Thank you! Have a great day!'",
        prompt_tr="Say 'iyi gunler!'",
        prompt_du="Say 'Dank u wel! Fijne dag verder!'",
        tools=[end_call_tool],
        next_states={"no": ""},
    ),
}
