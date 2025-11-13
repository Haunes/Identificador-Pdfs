import streamlit as st
from streamlit_drawable_canvas import st_canvas
import pdfplumber
import pandas as pd
from io import BytesIO

# =========================
# Configuración básica
# =========================
st.set_page_config(page_title="Extractor visual de tablas", layout="wide")
RESOLUTION = 150  # DPI para convertir PDF -> imagen

if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None
    st.session_state.pdf_name = None

if "selections" not in st.session_state:
    # {page_index: [ (x0_px, y0_px, x1_px, y1_px), ... ]}
    st.session_state.selections = {}

# =========================
# Subir PDF
# =========================
st.sidebar.title("Paso 1: Subir PDF")
uploaded_file = st.sidebar.file_uploader("PDF con tablas", type=["pdf"])

if uploaded_file is not None:
    # Si es un PDF nuevo, guardamos bytes y limpiamos selecciones
    if st.session_state.pdf_name != uploaded_file.name:
        st.session_state.pdf_bytes = uploaded_file.read()
        st.session_state.pdf_name = uploaded_file.name
        st.session_state.selections = {}

if st.session_state.pdf_bytes is None:
    st.info("Sube un PDF en la barra lateral para empezar.")
    st.stop()

# =========================
# Cargar PDF y elegir página
# =========================
pdf_bytes = st.session_state.pdf_bytes

with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
    num_pages = len(pdf.pages)

st.sidebar.title("Paso 2: Seleccionar página")
page_number = st.sidebar.number_input(
    "Página", min_value=1, max_value=num_pages, value=1, step=1
)
page_index = page_number - 1

with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
    page = pdf.pages[page_index]
    # Convertimos la página a imagen para usarla de fondo en el canvas
    pil_image = page.to_image(resolution=RESOLUTION).annotated
    page_width_pdf, page_height_pdf = page.width, page.height
    img_width_px, img_height_px = pil_image.size

st.sidebar.caption(f"Página {page_number} de {num_pages}")

# =========================
# Canvas para dibujar rectángulos
# =========================
st.markdown("### Paso 3: Dibuja rectángulos sobre las tablas")
st.caption(
    "Usa el mouse para dibujar un cuadro alrededor de cada tabla. "
    "Luego haz clic en **Guardar selecciones de esta página**."
)

canvas_result = st_canvas(
    fill_color="rgba(0, 0, 0, 0)",  # rectángulo transparente
    stroke_width=2,
    stroke_color="#FF0000",
    background_color="#FFFFFF",
    background_image=pil_image,      # <- PIL.Image, no int
    update_streamlit=True,
    height=img_height_px,            # alto del lienzo
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
        for obj in canvas_result.json_data.get("objects", []):
            if obj.get("type") == "rect":
                x = obj.get("left", 0)
                y = obj.get("top", 0)
                w = obj.get("width", 0)
                h = obj.get("height", 0)
                rects.append((x, y, x + w, y + h))

    if rects:
        existing = st.session_state.selections.get(page_index, [])
        existing.extend(rects)
        st.session_state.selections[page_index] = existing
        st.success(
            f"Se guardaron {len(rects)} rectángulos nuevos en la página {page_number}."
        )
    else:
        st.warning("No se encontraron rectángulos dibujados en el canvas.")

# =========================
# Mostrar resumen de selecciones
# =========================
st.markdown("### Selecciones actuales")
if not st.session_state.selections:
    st.write("Aún no hay rectángulos guardados.")
else:
    for p_idx, rects in sorted(st.session_state.selections.items()):
        st.write(f"- Página {p_idx + 1}: {len(rects)} rectángulo(s)")

# =========================
# Función de conversión de píxeles -> coordenadas PDF
# =========================
def px_bbox_to_pdf_bbox(bbox_px, img_w, img_h, pdf_w, pdf_h):
    """
    Convierte un bbox en píxeles (sobre la imagen) a bbox en coordenadas del PDF.
    bbox_px = (x0_px, y0_px, x1_px, y1_px) con origen en la esquina superior izquierda.
    """
    x0_px, y0_px, x1_px, y1_px = bbox_px
    x0_pdf = x0_px / img_w * pdf_w
    x1_pdf = x1_px / img_w * pdf_w
    y0_pdf = y0_px / img_h * pdf_h
    y1_pdf = y1_px / img_h * pdf_h
    return (x0_pdf, y0_pdf, x1_pdf, y1_pdf)


# =========================
# Extraer tablas y exportar a Excel
# =========================
st.markdown("### Paso 4: Extraer tablas y descargar Excel")

if st.session_state.selections:
    if st.button("Extraer todas las tablas y crear Excel"):
        all_tables = []

        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for p_idx, rects in st.session_state.selections.items():
                page = pdf.pages[p_idx]
                page_w, page_h = page.width, page.height

                # Volvemos a generar imagen para obtener mismas dimensiones en píxeles
                pil_image = page.to_image(resolution=RESOLUTION).annotated
                img_w, img_h = pil_image.size

                for bbox_px in rects:
                    bbox_pdf = px_bbox_to_pdf_bbox(
                        bbox_px, img_w, img_h, page_w, page_h
                    )

                    # Recortar región en el PDF y tratar de extraer tabla
                    cropped = page.crop(bbox_pdf)
                    tables = cropped.extract_tables()

                    for table in tables:
                        if not table:
                            continue
                        # Primera fila = encabezados (asumido)
                        header, *rows = table
                        if rows:
                            df = pd.DataFrame(rows, columns=header)
                        else:
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
            st.success(f"Se extrajeron {len(all_tables)} tablas y se unificaron.")
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
    st.info("Primero dibuja y guarda al menos un rectángulo en alguna página.")
