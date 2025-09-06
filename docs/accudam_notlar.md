AKÜCÜ AKIŞ:

1. /incoming-call'a istek geldi, bu controller twilio'ya
    1.1. /media-stream websocket URL'i
    1.2. firstMessage
    1.3. CallerNUmber'i response'a ekleyip döndü.
2. /media-stream socket URL'ine Twilio bağlandı.
3. OpenAI Websocket'i açıldı.
4. Twilio'nun bağlantı request'inden gelen call_sid ile aramaya ait bir session oluşturuldu. (Bu session bir obje olsun)
5. Twilio'nun bağlantı request'inden gelen firstMessage'ın instructions'a yazıldığı ilk session.update OpenAI'a gönderildi. Bu mesajda kullanıcıya dil tercihi soruldu.

NOT: İlk session.update'te sadece set_language fonksiyonu olmali. Ki kullanıcı dil seçmeden diğer fonksiyonlara düşemesin.

6. İDEAL SENARYO: Kullanıcı tercih ettiği dili söyledi, o dilin promptu db'den çekilip **session.update** yapılarak context oluşması için OpenAI'a gönderildi. Bu 2. session.update içinde diğer fonksiyonlarımız da (varsa) olacak. 

NOT: session.update kendi başına bir cevap üretmez. Şimdi yeni instructions yani prompt'a göre yeni bir cevap üretmesi için **response.create** event'i gönderilir.

NOT-2:
```python
await openai_ws.send(json.dumps({
    "type": "response.create",
    "response": {
        "modalities": ["text", "audio"]
    }
}))
```

Buradaki modalities kısmı, openai'ın göndereceği cevabın ne tipte veya tiplerde olması gerektiğini belirtiyor. audio almak istiyorsan kesinlikle gönderilmeli.

IDEAL OLMAYAN SENARYODA: Kullanıcı dili seçse bile fonksiyonumuza düşmedi diyelim... Bu durumda default dil ingilizce olmalı. userLanguageResponse şeklinde bir flag ayarlanıp True'ye dönmediği durumda kodun set_language'e girmesi sağlanabilir. Bu sayede ilk cevaptan sonra kesinlikle dil set edilmiş olacaktır. 

7. İkinci session.update ile güncelleme yapıldıktan sonra kullanıcı tools'da verdiğimiz fonksiyonlara düşebilir.