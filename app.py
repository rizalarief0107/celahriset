import streamlit as st
import requests
import urllib.parse
from google import genai

# --- PENGATURAN HALAMAN MINIMALIS ---
st.set_page_config(
    page_title="Pencari Celah Riset (Research Gap AI)",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed" 
)

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} 
    header {visibility: hidden;}   
    footer {visibility: hidden;}   
    
    .stTextInput input {
        font-size: 1.1rem !important;
        padding: 14px !important;
        border-radius: 12px !important;
        border: 2px solid #e0e0e0;
    }
    .stTextInput input:focus {
        border-color: #4CAF50;
        box-shadow: 0 0 8px rgba(76, 175, 80, 0.2);
    }
    
    .source-card {
        background-color: #f9f9f9;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 15px;
        border: 1px solid #eeeeee;
    }
    </style>
""", unsafe_allow_html=True)

# --- MANAJEMEN STATE ---
if "telah_mencari" not in st.session_state:
    st.session_state.telah_mencari = False
if "topik_riset" not in st.session_state:
    st.session_state.topik_riset = ""

def mulai_pencarian():
    if st.session_state.input_topik.strip():
        st.session_state.topik_riset = st.session_state.input_topik
        st.session_state.telah_mencari = True

def reset_pencarian():
    st.session_state.telah_mencari = False
    st.session_state.topik_riset = ""

# --- FUNGSI PENGAMBILAN KORPUS (DIPERBAIKI DENGAN JALUR PRIORITAS) ---
def ambil_korpus_ilmiah(topik: str, cakupan: str, batas_tahun: int, jumlah_paper: int):
    url = "https://api.openalex.org/works"
    filter_params = ["has_abstract:true", f"from_publication_date:{batas_tahun}-01-01"]
    
    if cakupan == "Khusus Riset Indonesia (Afiliasi ID)":
        filter_params.append("authorships.institutions.country_code:ID")
    
    params = {
        "search": topik, 
        "filter": ",".join(filter_params),
        "sort": "cited_by_count:desc", 
        "per_page": jumlah_paper,
        "mailto": "riset.akademik.indonesia@gmail.com" # <--- INI KUNCI ANTI-BLOKIRNYA (Polite Pool)
    }
    
    try:
        # Timeout diperpanjang jadi 20 detik agar tidak mudah terputus
        res = requests.get(url, params=params, timeout=20)
        res.raise_for_status() # Akan memunculkan error detail jika server menolak
        data = res.json()
        
        papers = []
        for item in data.get("results", []):
            title = item.get("title", "Tanpa Judul")
            year = item.get("publication_year", "N/A")
            doi = item.get("doi") or f"https://openalex.org/{item.get('id', '')}"
            citations = item.get("cited_by_count", 0)
            
            institusi = []
            for authorship in item.get("authorships", []):
                for inst in authorship.get("institutions", []):
                    inst_name = inst.get("display_name")
                    if inst_name and inst_name not in institusi:
                        institusi.append(inst_name)
            institusi_str = ", ".join(institusi[:2]) if institusi else "Institusi Global"

            abstract_dict = item.get("abstract_inverted_index")
            abstract = "Abstrak tidak tersedia."
            if abstract_dict:
                words = []
                for word, positions in abstract_dict.items():
                    for pos in positions:
                        words.append((pos, word))
                words.sort()
                abstract = " ".join([w[1] for w in words])[:800] + "..."

            papers.append({"title": title, "year": year, "doi": doi, "citations": citations, "institusi": institusi_str, "abstract": abstract})
        
        return papers
        
    # PENANGANAN ERROR AGAR KITA TAHU PENYEBABNYA
    except requests.exceptions.HTTPError as err:
        st.error(f"❌ Server jurnal menolak akses (HTTP Error): {err}")
        return []
    except requests.exceptions.Timeout:
        st.error("❌ Waktu pencarian habis (Timeout). Database sedang lambat, coba lagi.")
        return []
    except Exception as e:
        st.error(f"❌ Terjadi kesalahan sistem: {e}")
        return []

# --- FUNGSI REASONING GEMINI ---
def bedah_celah_riset(topik: str, papers: list, cakupan: str, api_key: str):
    client = genai.Client(api_key=api_key)
    ringkasan_korpus = "".join([f"\n- {p['title']} ({p['year']}). Abstrak: {p['abstract']}" for p in papers])
    prompt = f"""
    Kamu adalah mesin penjawab akademik (seperti Perplexity). Topik: "{topik}". Cakupan: {cakupan}.
    Referensi: {ringkasan_korpus}
    
    TUGAS: Buat jawaban terstruktur dengan format Markdown:
    1. **Kondisi Riset Terkini**: Ringkasan tren dari referensi di atas (1 paragraf).
    2. **Celah Riset (Research Gaps)**: Sebutkan 2 celah metode/konteks (Gunakan sitasi gaya [1], [2]).
    3. **Ide Judul**: Berikan 2 usulan judul baru yang konkret untuk mengatasi celah tersebut.
    Jawab dengan gaya formal dan langsung pada inti (tanpa basa-basi).
    """
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    return response.text

# ==========================================
# 1. TAMPILAN AWAL (BERANDA)
# ==========================================
if not st.session_state.telah_mencari:
    st.write("<br><br><br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; font-size: 3.5rem; color: #1E1E1E;'>Pencari Celah Riset</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 1.2rem; color: #666; margin-bottom: 30px;'>Ajukan topik penelitian, AI akan membaca jurnal dan merumuskan celah kebaruannya.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        st.text_input(
            "Pencarian Utama", 
            key="input_topik", 
            label_visibility="collapsed", 
            placeholder="Tulis topikmu di sini (misal: optimism academic, AI stunting)...",
            on_change=mulai_pencarian
        )
        
        with st.expander("⚙️ Pengaturan & Kunci API (Opsional)"):
            default_api = st.secrets.get("GEMINI_API_KEY", "")
            kunci_api = st.text_input("Gemini API Key:", value=default_api, type="password", key="api_utama")
            cakupan = st.selectbox("Sumber Jurnal:", ["Gabungan (Global + Indonesia)", "Khusus Riset Indonesia", "Internasional Saja"], key="cakupan_utama")
            tahun = st.slider("Tahun Minimal:", 2018, 2026, 2022, key="tahun_utama")

# ==========================================
# 2. TAMPILAN HASIL (ANALISIS AI)
# ==========================================
else:
    st.button("← Kembali ke Beranda", on_click=reset_pencarian)
    
    topik = st.session_state.topik_riset
    kunci_api = st.session_state.get("api_utama", st.secrets.get("GEMINI_API_KEY", ""))
    cakupan = st.session_state.get("cakupan_utama", "Gabungan (Global + Indonesia)")
    tahun = st.session_state.get("tahun_utama", 2022)
    
    st.title(f"🔍 Topik: {topik}")
    st.markdown("---")
    
    if not kunci_api:
        st.error("⚠️ Silakan klik 'Kembali ke Beranda', buka Pengaturan, lalu masukkan Gemini API Key terlebih dahulu.")
        st.stop()
        
    with st.status("🤖 Menghubungi database jurnal internasional...", expanded=True) as status:
        st.write("Mengumpulkan literatur ilmiah...")
        papers = ambil_korpus_ilmiah(topik, cakupan, tahun, 6)
        
        if not papers:
            status.update(label="Gagal Menemukan Jurnal", state="error")
            st.warning("⚠️ Tidak ada jurnal yang cocok, ATAU koneksi ke database sedang sibuk. Silakan ubah Tahun Minimal menjadi lebih lama, atau gunakan kata kunci lain.")
            st.stop()
            
        st.write(f"Berhasil menemukan {len(papers)} jurnal! Membedah abstrak dan merumuskan celah riset...")
        try:
            analisis = bedah_celah_riset(topik, papers, cakupan, kunci_api)
            status.update(label="Selesai Menganalisis!", state="complete", expanded=False)
        except Exception as e:
            status.update(label="Gagal Menganalisis", state="error")
            st.error(f"Gemini API bermasalah (mungkin kuota habis atau Key salah): {e}")
            st.stop()
        
    col_jawaban, col_sumber = st.columns([6, 3], gap="large")
    
    with col_jawaban:
        st.markdown("### 💡 Laporan Kebaruan Riset")
        st.info(analisis)
        st.download_button("📥 Unduh Laporan (.txt)", analisis, file_name="laporan_riset.txt")
        
    with col_sumber:
        st.markdown("### 📚 Sumber Rujukan")
        st.caption("Jurnal asli yang dibaca AI.")
        for i, p in enumerate(papers, 1):
            st.markdown(f"""
            <div class="source-card">
                <strong style="color:#0056b3;">[{i}] {p['title']} ({p['year']})</strong><br>
                <small style="color:#666;">🏢 {p['institusi']}</small><br>
                <small>📑 Sitasi: {p['citations']} | <a href="{p['doi']}" target="_blank">Buka Jurnal ↗</a></small>
            </div>
            """, unsafe_allow_html=True)
            with st.expander(f"Baca Abstrak [{i}]"):
                st.caption(p['abstract'])
