import os
import io
import time
import hashlib
import secrets
import urllib.request
import math
from collections import Counter
import streamlit as st

try:
    import qrcode
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
    from qrcode.image.styles.colormasks import SolidFillColorMask
    from PIL import Image, ImageDraw, ImageFont
    QR = True
except ImportError:
    QR = False

WORDLIST_URL = 'https://www.taringamberini.com/downloads/diceware_it_IT/lista-di-parole-diceware-in-italiano/4/word_list_diceware_it-IT-4.txt'
WORDLIST_FILE = 'diceware_it.txt'
COLOR_BG = (10, 10, 10)
COLOR_GREEN = (0, 184, 148)
COLOR_DIM = (80, 80, 80)
COLOR_QR_FRONT = (0, 0, 0)
COLOR_QR_BACK = (255, 255, 255)

# ── UTILITY ────────────────────────────────────────────────────

@st.cache_resource
def carica_dizionario():
    if not os.path.exists(WORDLIST_FILE):
        urllib.request.urlretrieve(WORDLIST_URL, WORDLIST_FILE)
    dizionario = {}
    with open(WORDLIST_FILE, 'r', encoding='utf-8') as f:
        for riga in f:
            riga = riga.strip()
            if riga and not riga.startswith('#'):
                parti = riga.split()
                if len(parti) >= 2:
                    dizionario[parti[0]] = parti[1]
    return dizionario

def lancia_dado(faces=6):
    entropy = (os.urandom(32) + str(time.perf_counter_ns()).encode()
               + str(time.time_ns()).encode() + secrets.token_bytes(16) + os.urandom(8))
    digest = hashlib.sha3_256(entropy).digest()
    seed = int.from_bytes(digest, 'big')
    os.urandom(1)
    return (secrets.randbelow(faces * seed) % faces) + 1

def lancia_dadi(num_dadi=5, faces=6):
    return [lancia_dado(faces) for _ in range(num_dadi)]

def calcola_entropia(num_parole, vocab=7776):
    return num_parole * math.log2(vocab)

def tempo_bruteforce(entropia_bit):
    anni = (2 ** entropia_bit) / 2 / 1e12 / (60 * 60 * 24 * 365.25)
    if anni > 1e15: return f'{anni:.2e} anni'
    if anni > 1e9:  return f'{anni/1e9:.1f} miliardi di anni'
    if anni > 1e6:  return f'{anni/1e6:.1f} milioni di anni'
    if anni > 1000: return f'{anni:.0f} anni'
    return f'{anni:.1f} anni'

def livello_sicurezza(entropia):
    if entropia >= 100: return '🟢 ECCELLENTE'
    if entropia >= 77:  return '🟢 OTTIMA'
    if entropia >= 60:  return '🟡 BUONA'
    return '🔴 DEBOLE'

# ── GENERA PASSPHRASE ──────────────────────────────────────────

def genera_passphrase_web(dizionario, num_parole, separatore, aggiungi_numero, aggiungi_simbolo, maiuscola):
    SIMBOLI = ['!', '@', '#', '$', '%', '&', '*', '?', '+', '=']
    parole, lanci = [], []
    for _ in range(num_parole):
        dadi = lancia_dadi(5, 6)
        codice = ''.join(map(str, dadi))
        parola = dizionario.get(codice, f'[{codice}]')
        parole.append(parola)
        lanci.append((codice, parola))
    if maiuscola:
        idx = secrets.randbelow(len(parole))
        parole[idx] = parole[idx].capitalize()
    if aggiungi_simbolo:
        simbolo = SIMBOLI[secrets.randbelow(len(SIMBOLI))]
        idx = secrets.randbelow(len(parole))
        parole[idx] = parole[idx] + simbolo
    passphrase = separatore.join(parole)
    if aggiungi_numero:
        passphrase += separatore + str(secrets.randbelow(900) + 100)
    return passphrase, lanci

# ── GENERA QR ──────────────────────────────────────────────────

def _get_font(size):
    candidates = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
        'C:/Windows/Fonts/consola.ttf', 'C:/Windows/Fonts/cour.ttf',
    ]
    for path in candidates:
        if os.path.exists(path):
            try: return ImageFont.truetype(path, size)
            except: continue
    return ImageFont.load_default()

def genera_qr_web(passphrase, servizio='billikey'):
    if not QR: return None
    contenuto = f'Servizio: {servizio}\nPassphrase: {passphrase}'
    PADDING, BANNER_H, FOOTER_H = 30, 80, 70
    qr_probe = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=3)
    qr_probe.add_data(contenuto); qr_probe.make(fit=True)
    box_size = max(1, 400 // (qr_probe.modules_count + 6))
    qr = qrcode.QRCode(version=qr_probe.version, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=box_size, border=3)
    qr.add_data(contenuto); qr.make(fit=True)
    try:
        qr_img = qr.make_image(image_factory=StyledPilImage, module_drawer=RoundedModuleDrawer(),
                                color_mask=SolidFillColorMask(front_color=COLOR_QR_FRONT, back_color=COLOR_QR_BACK)).convert("RGBA")
    except:
        qr_img = qr.make_image(fill_color=COLOR_QR_FRONT, back_color=COLOR_QR_BACK).convert("RGBA")
    QR_SIZE = qr_img.width
    CANVAS_W = QR_SIZE + PADDING * 2
    CANVAS_H = BANNER_H + QR_SIZE + FOOTER_H + PADDING * 2
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), COLOR_BG)
    draw = ImageDraw.Draw(canvas)
    font_title, font_footer, font_sub = _get_font(34), _get_font(20), _get_font(16)
    draw.rectangle([(0, BANNER_H - 3), (CANVAS_W, BANNER_H)], fill=COLOR_GREEN)
    title_text = '[ BilliKey ]'
    bbox = draw.textbbox((0, 0), title_text, font=font_title)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]; ty = (BANNER_H - th) // 2 - 5
    draw.text(((CANVAS_W - tw) // 2, ty), title_text, fill=COLOR_GREEN, font=font_title)
    draw.text((PADDING, ty), '>_', fill=(0, 255, 150), font=font_title)
    qr_x = (CANVAS_W - QR_SIZE) // 2; qr_y = BANNER_H + PADDING; border = 4
    draw.rectangle([(qr_x-border, qr_y-border), (qr_x+QR_SIZE+border, qr_y+QR_SIZE+border)], outline=COLOR_GREEN, width=border)
    canvas.paste(qr_img.convert("RGB"), (qr_x, qr_y))
    for cx, cy in [(qr_x-14, qr_y-14),(qr_x+QR_SIZE-6, qr_y-14),(qr_x-14, qr_y+QR_SIZE-6),(qr_x+QR_SIZE-6, qr_y+QR_SIZE-6)]:
        draw.rectangle([(cx,cy),(cx+20,cy+20)], outline=(0,255,150), width=3)
    footer_y = qr_y + QR_SIZE + PADDING // 2
    draw.rectangle([(0, footer_y),(CANVAS_W, footer_y+2)], fill=COLOR_GREEN)
    footer_text = f'// {servizio} //'
    bbox2 = draw.textbbox((0,0), footer_text, font=font_footer)
    draw.text(((CANVAS_W-(bbox2[2]-bbox2[0]))//2, footer_y+10), footer_text, fill=COLOR_GREEN, font=font_footer)
    sub_text = 'scan to access · BilliKey v1.0'
    bbox3 = draw.textbbox((0,0), sub_text, font=font_sub)
    draw.text(((CANVAS_W-(bbox3[2]-bbox3[0]))//2, footer_y+36), sub_text, fill=COLOR_DIM, font=font_sub)
    buf = io.BytesIO()
    canvas.save(buf, format='PNG', dpi=(300, 300)); buf.seek(0)
    return buf.getvalue()

# ── INTERFACCIA STREAMLIT ──────────────────────────────────────

st.set_page_config(page_title='BilliKey', page_icon='🗝️', layout='centered')
st.title('🗝️ BilliKey — Generatore Passphrase')
st.caption('Diceware Italiano · Crittograficamente sicuro · v1.0')

dizionario = carica_dizionario()

# ── SIDEBAR con tooltip (parametro help=) ──────────────────────
with st.sidebar:
    st.header('⚙️ Configurazione')

    num_parole = st.slider(
        'Numero di parole', 4, 8, 6,
        help='Più parole = passphrase più sicura. 6 parole offrono ~77 bit di entropia, considerati molto sicuri.'
    )
    separatore = st.selectbox(
        'Separatore', ['-', ' ', '.', ''],
        format_func=lambda x: {'': 'Nessuno', ' ': 'Spazio', '-': 'Trattino', '.': 'Punto'}.get(x, x),
        help='Carattere usato per unire le parole. Es. con trattino: "cane-casa-mare".'
    )

    # ▶ NUOVO: quante passphrase generare
    quante = st.slider(
        'Quante passphrase generare', 1, 10, 1,
        help='Genera più passphrase in una volta sola e scegli quella che preferisci.'
    )

    maiuscola = st.toggle(
        'Parola in maiuscolo', value=False,
        help='Mette in maiuscolo la prima lettera di una parola casuale. Es. "cane-Casa-mare".'
    )
    simbolo = st.toggle(
        'Aggiungi simbolo casuale', value=False,
        help='Aggiunge un simbolo (!@#$%&*?+=) in fondo a una parola casuale. Aumenta la sicurezza contro alcuni attacchi.'
    )
    numero = st.toggle(
        'Aggiungi numero in fondo', value=False,
        help='Aggiunge un numero a 3 cifre (100-999) alla fine della passphrase. Utile per siti che richiedono numeri.'
    )

    st.divider()
    entropia_preview = calcola_entropia(num_parole)
    st.caption(f'Entropia: **{entropia_preview:.1f} bit** — {livello_sicurezza(entropia_preview)}')
    st.caption(f'Brute force: {tempo_bruteforce(entropia_preview)}')

# ── GENERA ────────────────────────────────────────────────────
if st.button('🎲 Genera Passphrase', type='primary', use_container_width=True):
    risultati = []
    for _ in range(quante):
        pp, lanci = genera_passphrase_web(dizionario, num_parole, separatore, numero, simbolo, maiuscola)
        risultati.append((pp, lanci))
    st.session_state['risultati'] = risultati
    st.session_state['num_parole'] = num_parole

# ── RISULTATI ─────────────────────────────────────────────────
if 'risultati' in st.session_state:
    risultati = st.session_state['risultati']
    entropia = calcola_entropia(st.session_state['num_parole'])
    num_risultati = len(risultati)

    for i, (pp, lanci) in enumerate(risultati):
        if num_risultati > 1:
            st.markdown(f'**Passphrase {i+1}**')

        # ▶ st.code mostra la passphrase con il pulsante 📋 Copia integrato
        st.code(pp, language=None)

        col1, col2, col3 = st.columns(3)
        col1.metric('Entropia', f'{entropia:.1f} bit')
        col2.metric('Sicurezza', livello_sicurezza(entropia))
        col3.metric('Brute force', tempo_bruteforce(entropia))

        with st.expander(f'🎲 Dettaglio lanci dadi {"#"+str(i+1) if num_risultati > 1 else ""}'):
            for j, (codice, parola) in enumerate(lanci):
                st.write(f'Lancio {j+1}: `{codice}` → **{parola}**')

        if num_risultati > 1:
            st.divider()

    # ── QR (solo se una passphrase, ha senso) ─────────────────
    st.subheader('📱 Genera QR Code')
    if num_risultati > 1:
        idx_qr = st.selectbox(
            'Scegli quale passphrase usare per il QR',
            options=list(range(1, num_risultati + 1)),
            format_func=lambda x: f'Passphrase {x}'
        ) - 1
        pp_qr = risultati[idx_qr][0]
    else:
        pp_qr = risultati[0][0]

    servizio = st.text_input('Nome servizio (es. Gmail, Bitwarden)', value='billikey')
    if st.button('Genera QR', use_container_width=True):
        qr_bytes = genera_qr_web(pp_qr, servizio)
        if qr_bytes:
            col_qr, _ = st.columns([1, 1])
            with col_qr:
                st.image(qr_bytes, caption=f'QR per: {servizio}')
            st.download_button('⬇️ Scarica QR PNG', data=qr_bytes,
                file_name=f'{servizio.lower().replace(" ", "_")}_qr.png',
                mime='image/png', use_container_width=True)
        else:
            st.error('Dipendenze QR mancanti. Esegui: pip install qrcode[pil] Pillow')

    st.warning('⚠️ Salva questa passphrase adesso. Non viene memorizzata.')