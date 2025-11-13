import streamlit as st
from streamlit_drawable_canvas import st_canvas
import pdfplumber
import pandas as pd
from io import BytesIO

# =========================
# Configuración general
# =========================
st.set_page_config(page_title="Extractor visual de tablas", layout="wide")
RESOLUTION = 150  # DPI para convertir el PDF a imagen

# Inicializamos estado
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None
    st.session_state.pdf_name = None

# rects_by_page: { page_idx: { "rects":[(x0,y0,x1,y1),...],
#                              "canvas_w":int, "canvas_h":int } }
if "rects_by_page" not in st.session_state:
    st.session_state.rects_by_page = {}


# =========================
# Función de mapeo canvas -> PDF
# =========================
def canvas_rect_to_pdf_bbox(rect, canvas_w, canvas_h, pdf_w, pdf_h):
    """
    rect: (x0_c, y0_c, x1_c, y1_c) en coords del canvas (origen arriba-izquierda)
    Devuelve bbox en coords del PDF (mismo origen que pdfplumber.to_image / crop).
    """
    x0_c, y0_c, x1_c, y1_c = rect
    x0_pdf = x0_c / canvas_w * pdf_w
    x1_pdf = x1_c / canvas_w * pdf_w
    y0_pdf = y0_c / canvas_h * pdf_h
    y1_pdf = y1_c / canvas_h * pdf_h
    return (x0_pdf, y0_pdf, x1_pdf, y1_pdf)


# =========================
# Subir PDF
# =========================
st.sidebar.title("Paso 1: Subir PDF")
uploaded_file = st.sidebar.file_uploader("PDF con tablas", type=["pdf"])

if uploaded_file is not None:
    # Si es un archivo nuevo, guardamos bytes y limpiamos selecciones
    if st.session_state.pdf_name != uploaded_file.name:
        st.session_state.pdf_bytes = uploaded_file.read()
        st.session_state.pdf_name = uploaded_file.name
        st.session_state.rects_by_page = {}

if st.session_state.pdf_bytes is None:
    st.info("Sube un PDF en la barra lateral para empezar.")
    st.stop()

pdf_bytes = st.session_state.pdf_bytes

# =========================
# Cargar PDF y elegir página
# =========================
with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
    num_pages = len(pdf.pages)

st.sidebar.title("Paso 2: Seleccionar página")
page_number = st.sidebar.number_input(
    "Página", min_value=1, max_value=num_pages, value=1, step=1
)
page_index = page_number - 1
st.sidebar.caption(f"Página {page_number} de {num_pages}")

# =========================
# Mostrar página como imagen y canvas
# =========================
with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
    page = pdf.pages[page_index]
    pdf_w, pdf_h = page.width, page.height

    # Convertimos la página a imagen PIL
    page_image = page.to_image(resolution=RESOLUTION)
    pil_image = page_image.original
    img_width_px, img_height_px = pil_image.size

st.markdown(f"### Paso 3: Dibuja rectángulos sobre las tablas (Página {page_number})")
st.caption(
    "Usa el mouse para dibujar un cuadro alrededor de cada tabla de esta página. "
    "Luego haz clic en **Guardar selecciones de esta página**."
)

canvas_result = st_canvas(
    fill_color="rgba(0, 0, 0, 0)",  # rectángulo transparente
    stroke_width=2,
    stroke_color="#FF0000",
    background_color="#FFFFFF",
    background_image=pil_image,      # PIL.Image
    update_streamlit=True,
    height=img_height_px,            # alto del lienzo = alto de la imagen
    drawing_mode="rect",
    display_toolbar=True,
    key=f"canvas_page_{page_index}",
)

# =========================
# Guardar rectángulos de esta página
# =========================
if st.button("Guardar selecciones de esta página"):
    rects = []
    if canvas_result is not None and canvas_result.json_data is not None:
        objects = canvas_result.json_data.get("objects", [])

        # dim reales del canvas
        if canvas_result.image_data is not None:
            canvas_h, canvas_w, _ = canvas_result.image_data.shape
        else:
            # fallback (no debería pasar normalmente)
            canvas_h = img_height_px
            canvas_w = img_width_px

        for obj in objects:
            if obj.get("type") == "rect":
                x = obj.get("left", 0)
                y = obj.get("top", 0)
                w = obj.get("width", 0)
                h = obj.get("height", 0)
                x0 = x
                y0 = y
                x1 = x + w
                y1 = y + h
                # nos aseguramos de que x0<x1, y0<y1
                x0, x1 = sorted([x0, x1])
                y0, y1 = sorted([y0, y1])
                rects.append((x0, y0, x1, y1))

        if rects:
            st.session_state.rects_by_page[page_index] = {
                "rects": rects,
                "canvas_w": canvas_w,
                "canvas_h": canvas_h,
            }
            st.success(
                f"Se guardaron {len(rects)} rectángulo(s) para la página {page_number}."
            )
        else:
            st.warning("No se encontraron rectángulos dibujados en el canvas.")
    else:
        st.warning("No se encontró información del canvas (vuelve a intentar).")

# =========================
# Resumen de selecciones
# =========================
st.markdown("### Paso 4: Resumen de selecciones")
if not st.session_state.rects_by_page:
    st.write("Aún no hay rectángulos guardados.")
else:
    for p_idx, info in sorted(st.session_state.rects_by_page.items()):
        st.write(
            f"- Página {p_idx + 1}: {len(info['rects'])} rectángulo(s) guardado(s)."
        )

# =========================
# Extraer tablas y exportar a Excel
# =========================
st.markdown("### Paso 5: Extraer tablas y descargar Excel")

if st.session_state.rects_by_page:
    if st.button("Extraer todas las tablas y crear Excel"):
        all_tables = []

        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for p_idx, info in st.session_state.rects_by_page.items():
                page = pdf.pages[p_idx]
                pdf_w, pdf_h = page.width, page.height

                canvas_w = info["canvas_w"]
                canvas_h = info["canvas_h"]

                for rect in info["rects"]:
                    bbox_pdf = canvas_rect_to_pdf_bbox(
                        rect, canvas_w, canvas_h, pdf_w, pdf_h
                    )

                    # Recortar región correspondiente en el PDF y extraer tablas
                    cropped = page.crop(bbox_pdf)
                    tables = cropped.extract_tables()

                    for table in tables:
                        if not table:
                            continue
                        header, *rows = table
                        # Si hay filas y la primera la tomamos como header
                        if rows:
                            df = pd.DataFrame(rows, columns=header)
                        else:
                            # fallback si no está bien separada header/rows
                            df = pd.DataFrame(table)
                        all_tables.append(df)

        if not all_tables:
            st.error("No se pudieron extraer tablas de las regiones seleccionadas.")
        else:
            merged_df = pd.concat(all_tables, ignore_index=True)

            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                merged_df.to_excel(writer, index=False, sheet_name="Tablas")

            output.seek(0)
            st.success(
                f"Se extrajeron {len(all_tables)} tablas y se unificaron en un solo DataFrame."
            )
            st.download_button(
                "Descargar Excel con todas las tablas",
                data=output,
                file_name="tablas_extraidas.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
            )
else:
    st.info("Primero guarda al menos un rectángulo en alguna página.")
