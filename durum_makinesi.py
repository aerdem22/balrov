import time

class Durum:
    BAŞLA         = 0
    DERİNLİĞE_İN  = 1
    STABİLİZE_OL  = 2
    HAT_TAKİP     = 3
    MINI_ROV_BIRAK = 4
    İPUCU_BEKLE   = 5
    GÖREV_TAMAM   = 6

# Sahte sensör verileri
derinlik = 0.0
hat_var = False
ipucu_goruldu = False
stabil_baslangic = None

durum = Durum.BAŞLA

print("BALROV Görev Başlıyor...")
print("-" * 40)

for adim in range(100):
    time.sleep(0.2)

    # Sahte fizik simülasyonu
    if durum == Durum.DERİNLİĞE_İN:
        derinlik += 0.2  # ROV alçalıyor
    if durum == Durum.HAT_TAKİP and adim > 40:
        hat_var = False  # Tahtanın sonu geldi
    if durum == Durum.İPUCU_BEKLE and adim > 60:
        ipucu_goruldu = True

    # Durum makinesi
    if durum == Durum.BAŞLA:
        print(f"[{adim:3d}] BAŞLA → Arme ediliyor...")
        durum = Durum.DERİNLİĞE_İN

    elif durum == Durum.DERİNLİĞE_İN:
        print(f"[{adim:3d}] DERİNLİĞE_İN → Derinlik: {derinlik:.1f}m")
        if derinlik >= 2.0:
            stabil_baslangic = adim
            durum = Durum.STABİLİZE_OL

    elif durum == Durum.STABİLİZE_OL:
        print(f"[{adim:3d}] STABİLİZE_OL → Bekleniyor...")
        if adim - stabil_baslangic >= 3:
            hat_var = True
            durum = Durum.HAT_TAKİP

    elif durum == Durum.HAT_TAKİP:
        print(f"[{adim:3d}] HAT_TAKİP → Şerit takip ediliyor...")
        if not hat_var:
            durum = Durum.MINI_ROV_BIRAK

    elif durum == Durum.MINI_ROV_BIRAK:
        print(f"[{adim:3d}] MINI_ROV_BIRAK → Mini ROV serbest bırakıldı!")
        durum = Durum.İPUCU_BEKLE

    elif durum == Durum.İPUCU_BEKLE:
        print(f"[{adim:3d}] İPUCU_BEKLE → Kamera tarıyor...")
        if ipucu_goruldu:
            durum = Durum.GÖREV_TAMAM

    elif durum == Durum.GÖREV_TAMAM:
        print(f"[{adim:3d}] GÖREV_TAMAM → Görev başarıyla tamamlandı! 🎉")
        break
