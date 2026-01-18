import streamlit as st
from ortools.sat.python import cp_model
from datetime import datetime, timedelta
import pandas as pd
import io

st.set_page_config(page_title="Doktor Nöbet Robotu", layout="wide")

st.title("🏥 Doktor Nöbet Planlayıcı")
st.markdown("Tatil günleri, kotalar ve tercihler dahil pratik çizelgeleme sistemi.")

# --- SIDEBAR: TEMEL AYARLAR ---
with st.sidebar:
    st.header("📅 Takvim Ayarları")
    yil = st.number_input("Yıl", min_value=2024, max_value=2030, value=2025)
    ay = st.number_input("Ay (1-12)", min_value=1, max_value=12, value=12)
    
    st.header("🏝️ Tatil Günleri")
    st.caption("Resmi tatil veya idari izin günlerini girin. Bu günlere asla nöbet yazılmaz.")
    tatil_input = st.text_input("Örn: 29 (Tek gün) veya 15-17 (Aralık)")

    doktorlar = ["Ben", "Cem", "Cer", "Fe", "Ha", "Ki", "Le", "Mü", "Oy", "Yı", "Ser", "Bek"]
    #doktorlar = ["DR.B", "DR.C", "UZ.C", "DR.F", "DR.H", "DR.K", "DR.L", "DR.M", "DR.O", "UZ.Y", "DR.S", "DR.B"]
    
    st.header("📊 Bireysel Kotalar")
    kotalar = {}
    for d in doktorlar:
        kota = st.text_input(f"{d} Nöbet Sayısı", key=f"kota_{d}")
        if kota.isdigit():
            kotalar[doktorlar.index(d)] = int(kota)

# --- TAKVİM HESAPLAMA (TATİLLERİ ÇIKARARAK) ---

# --- TAKVİM HESAPLAMA (GELİŞTİRİLMİŞ TATİL AYRIŞTIRICI) ---
is_gunleri = []
tatil_gunleri_listesi = []

if tatil_input:
    try:
        # Girdiyi virgüllere göre parçala (Örn: "2, 8, 20-24" -> ["2", " 8", " 20-24"])
        parcalar = [p.strip() for p in tatil_input.split(',')]
        
        for parca in parcalar:
            if "-" in parca:
                # Aralık varsa (Örn: "20-24")
                t_bas, t_son = map(int, parca.split("-"))
                tatil_gunleri_listesi.extend(list(range(t_bas, t_son + 1)))
            else:
                # Tek günse (Örn: "2")
                tatil_gunleri_listesi.append(int(parca))
        
        # Mükerrer kayıtları temizle (Set kullanarak)
        tatil_gunleri_listesi = sorted(list(set(tatil_gunleri_listesi)))
        
    except ValueError:
        st.sidebar.error("Tatil formatı hatalı! Lütfen sayı ve tire (-) kullanın. Örn: 2, 8, 20-24")

# Takvimi oluştururken bu listeyi kullan
curr = datetime(int(yil), int(ay), 1)
while curr.month == int(ay):
    # Hafta içi mi VE tatil listesinde yok mu?
    if curr.weekday() < 5 and curr.day not in tatil_gunleri_listesi:
        is_gunleri.append(curr)
    curr += timedelta(days=1)

# is_gunleri = []
# tatil_gunleri_listesi = []

# # Tatil günlerini parse et (Aralık veya tek gün)
# if tatil_input:
    # try:
        # if "-" in tatil_input:
            # t_bas, t_son = map(int, tatil_input.split("-"))
            # tatil_gunleri_listesi = list(range(t_bas, t_son + 1))
        # else:
            # tatil_gunleri_listesi = [int(tatil_input)]
    # except:
        # st.sidebar.error("Tatil formatı hatalı!")

# curr = datetime(int(yil), int(ay), 1)
# while curr.month == int(ay):
    # # Eğer hafta içiyse VE tatil günleri listesinde DEĞİLSE nöbet günü kabul et
    # if curr.weekday() < 5 and curr.day not in tatil_gunleri_listesi:
        # is_gunleri.append(curr)
    # curr += timedelta(days=1)

gun_sayisi = len(is_gunleri)

# --- ANA PANEL ---
if not is_gunleri:
    st.warning("Seçilen ayda veya kriterlerde nöbet tutulacak gün bulunamadı.")
else:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📍 Sabit Nöbetçiler")
        st.info(f"Bu ay toplam **{gun_sayisi}** gün nöbet tutulacak.")
        
        ilk_gun_etiket = f"{is_gunleri[0].strftime('%d.%m.%Y')} (İlk Nöbet Günü)"
        ilk_gun = st.multiselect(f"{ilk_gun_etiket} Nöbetçileri (3 Kişi)", doktorlar)
        
        st.write("---")
        cuma_sabitleme = {}
        for g_idx, tarih in enumerate(is_gunleri):
            if tarih.weekday() == 4: # Cuma
                secilen = st.selectbox(f"{tarih.strftime('%d.%m.%Y')} (Cuma)", ["Seçiniz..."] + doktorlar, key=f"cuma_{g_idx}")
                if secilen != "Seçiniz...":
                    cuma_sabitleme[g_idx] = doktorlar.index(secilen)

    with col2:
        st.subheader("📝 İzinler ve Tercihler")
        st.caption("0: İzinli, 1: İstiyor, 2: İstemiyor. Örn: `Yı, 10-12, 0` veya `Ha, 5, 1`")
        izin_metni = st.text_area("Tercihleri girin:", height=600)

    # --- HESAPLAMA VE ÇÖZÜCÜ ---
    if st.button("🚀 Nöbet Listesini Oluştur"):
        model = cp_model.CpModel()
        doktor_sayisi = len(doktorlar)
        nobet = {(d, g): model.NewBoolVar(f'n_{d}_{g}') for d in range(doktor_sayisi) for g in range(gun_sayisi)}

        # 1. Kısıt: Her gün 3 kişi
        for g in range(gun_sayisi):
            model.Add(sum(nobet[(d, g)] for d in range(doktor_sayisi)) == 3)

        # 2. Sabit Nöbetçiler (İlk gün ve Cumalar)
        for isim in ilk_gun:
            model.Add(nobet[(doktorlar.index(isim), 0)] == 1)
        for g_idx, d_idx in cuma_sabitleme.items():
            model.Add(nobet[(d_idx, g_idx)] == 1)

        # 3. Tercihler ve İzinler
        # --- GRUP TANIMLARI (İndis bazlı) ---
        g0_tayfasi = [0, 1]          # Ben, Cem
        g1_tayfasi = [2, 10, 11]     # Cer, Ser, Bek
        g2_tayfasi = [3, 7, 9]       # Fe, Mü, Yı
        tum_gruplar = [g0_tayfasi, g1_tayfasi, g2_tayfasi]

        # 3. Tercihler ve İzinler (GELİŞTİRİLMİŞ)
        tercih_puanlari = []
        if izin_metni:
            for line in izin_metni.split('\n'):
                if ',' in line:
                    try:
                        p = line.split(',')
                        d_idx = doktorlar.index(p[0].strip().capitalize())
                        g_verisi = p[1].strip()
                        durum = int(p[2].strip())
                        
                        # Gün listesini oluştur (Örn: 19-22 -> [19, 20, 21, 22])
                        g_list = list(range(int(g_verisi.split("-")[0]), int(g_verisi.split("-")[-1]) + 1)) if "-" in g_verisi else [int(g_verisi)]
                        
                        for gn in g_list:
                            g_idx = next((i for i, t in enumerate(is_gunleri) if t.day == gn), None)
                            if g_idx is not None:
                                # Kişinin kendi tercihi
                                if durum == 0: 
                                    model.Add(nobet[(d_idx, g_idx)] == 0)
                                    
                                    # YENİ KISIT: Grup arkadaşlarına yasak (Son gün hariç)
                                    # Eğer gn listenin son elemanı değilse grup arkadaşlarına yasak koy
                                    if gn != g_list[-1]:
                                        # Bu doktor hangi grupta?
                                        for grup in tum_gruplar:
                                            if d_idx in grup:
                                                for arkadas_idx in grup:
                                                    if arkadas_idx != d_idx:
                                                        model.Add(nobet[(arkadas_idx, g_idx)] == 0)
                                
                                elif durum == 1: tercih_puanlari.append(nobet[(d_idx, g_idx)] * 10)
                                elif durum == 2: tercih_puanlari.append(nobet[(d_idx, g_idx)] * -10)
                    except: pass
        # tercih_puanlari = []
        # if izin_metni:
            # for line in izin_metni.split('\n'):
                # if ',' in line:
                    # try:
                        # p = line.split(',')
                        # d_idx = doktorlar.index(p[0].strip().capitalize())
                        # g_verisi = p[1].strip()
                        # durum = int(p[2].strip())
                        
                        # g_list = list(range(int(g_verisi.split("-")[0]), int(g_verisi.split("-")[-1]) + 1)) if "-" in g_verisi else [int(g_verisi)]
                        # for gn in g_list:
                            # g_idx = next((i for i, t in enumerate(is_gunleri) if t.day == gn), None)
                            # if g_idx is not None:
                                # if durum == 0: model.Add(nobet[(d_idx, g_idx)] == 0)
                                # elif durum == 1: tercih_puanlari.append(nobet[(d_idx, g_idx)] * 10)
                                # elif durum == 2: tercih_puanlari.append(nobet[(d_idx, g_idx)] * -10)
                    # except: pass

        # 4. Kurallar (Grup, Üst Üste vb.)
        g1, g2 = [2, 10, 11], [3, 7, 9] # Grup kısıtları
        for g in range(gun_sayisi):
            model.Add(nobet[(0, g)] + nobet[(1, g)] <= 1) # Bendigar & Cemalettin
            model.Add(sum(nobet[(d, g)] for d in g1) <= 1)
            model.Add(sum(nobet[(d, g)] for d in g2) <= 1)

            # ÜST ÜSTE NÖBET YASAĞI (DÜZELTİLDİ)
            # Arada hafta sonu veya tatil olsa bile, listenin bir sonraki gününde nöbet yazılamaz.
            for d in range(doktor_sayisi):
                if g < gun_sayisi - 1:
                    for d in range(doktor_sayisi):
                        model.Add(nobet[(d, g)] + nobet[(d, g+1)] <= 1)

        # 5. Kota ve Adalet
        toplam_nobetler = [sum(nobet[(d, g)] for g in range(gun_sayisi)) for d in range(doktor_sayisi)]
        for d_idx, h in kotalar.items():
            model.Add(toplam_nobetler[d_idx] == h)

        kotasizlar = [i for i in range(doktor_sayisi) if i not in kotalar]
        fark_puan = 0
        if kotasizlar:
            max_n, min_n = model.NewIntVar(0, gun_sayisi, 'max'), model.NewIntVar(0, gun_sayisi, 'min')
            for d in kotasizlar:
                model.Add(max_n >= toplam_nobetler[d])
                model.Add(min_n <= toplam_nobetler[d])
            fark = model.NewIntVar(0, gun_sayisi, 'fark')
            model.Add(fark == max_n - min_n)
            fark_puan = fark * -50

        model.Maximize(sum(tercih_puanlari) + fark_puan)
        
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            res_data = []
            for g, t in enumerate(is_gunleri):
                secili_d = [doktorlar[d] for d in range(doktor_sayisi) if solver.Value(nobet[(d, g)]) == 1]
                res_data.append({"Tarih": t.strftime('%d.%m.%Y'), "Gün": t.strftime('%A'), "Nöbetçiler": ", ".join(secili_d)})
            
            st.success("✅ Liste Oluşturuldu!")
            st.dataframe(pd.DataFrame(res_data),height= 800, use_container_width=True)
            
            # Dağılım Özeti
            st.subheader("📊 Nöbet Dağılım Özeti")
            ozet = {doktorlar[d]: solver.Value(toplam_nobetler[d]) for d in range(doktor_sayisi)}
            st.write(ozet)
            
            # İndirme Butonu
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                pd.DataFrame(res_data).to_excel(writer, index=False)
            st.download_button("📥 Excel İndir", output.getvalue(), f"nobet_{yil}_{ay}.xlsx")
        else:
            st.error("❌ Çözüm bulunamadı! Lütfen kotaları veya sabit nöbetçileri kontrol edin.")
