import streamlit as st
import streamlit.components.v1 as components
import fitz  # PyMuPDF
from PIL import Image
import io
import pandas as pd
import base64
import json

st.set_page_config(page_title="Extractor de Tablas PDF", layout="wide")
st.title("📊 Extractor de Tablas PDF")

# ============================
# Inicializar session_state
# ============================
if "pdf_document" not in st.session_state:
    st.session_state.pdf_document = None
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None
if "pdf_name" not in st.session_state:
    st.session_state.pdf_name = None
if "rectangles" not in st.session_state:
    st.session_state.rectangles = []
if "current_page" not in st.session_state:
    st.session_state.current_page = 0

# ============================
# Subir PDF
# ============================
uploaded_file = st.file_uploader("Sube tu PDF", type=["pdf"])

if uploaded_file is not None:
    # Solo recargar el PDF si cambia el archivo
    if (
        st.session_state.pdf_document is None
        or uploaded_file.name != st.session_state.pdf_name
    ):
        st.session_state.pdf_bytes = uploaded_file.getvalue()
        st.session_state.pdf_name = uploaded_file.name
        st.session_state.pdf_document = fitz.open(
            stream=st.session_state.pdf_bytes, filetype="pdf"
        )
        st.session_state.rectangles = []
        st.session_state.current_page = 0

    doc = st.session_state.pdf_document
    total_pages = len(doc)

    st.success(f"✅ PDF cargado: {st.session_state.pdf_name} ({total_pages} páginas)")

    # ============================
    # Controles superiores
    # ============================
    col1, col2, col3 = st.columns([2, 3, 2])

    with col1:
        page_num = (
            st.number_input(
                "Página",
                min_value=1,
                max_value=total_pages,
                value=st.session_state.current_page + 1,
                step=1,
            )
            - 1
        )
        st.session_state.current_page = page_num

    with col2:
        st.info(f"📍 Rectángulos totales: {len(st.session_state.rectangles)}")

    with col3:
        if st.button("🗑️ Limpiar Todo"):
            st.session_state.rectangles = []
            # También limpiamos el valor de la selección del componente
            st.session_state["pdf_canvas"] = None
            st.rerun()

    # ============================
    # Renderizar página como imagen
    # ============================
    page = doc[page_num]
    zoom = 2  # factor de zoom para mejor resolución
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()

    # Rectángulos solo de la página actual
    current_page_rects = [
        r for r in st.session_state.rectangles if r["page"] == page_num
    ]

    st.subheader(f"Página {page_num + 1} de {total_pages}")
    st.caption("🖱️ Haz clic y arrastra para dibujar rectángulos sobre las tablas")

    # ============================
    # HTML del canvas interactivo
    # ============================
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                margin: 0;
                padding: 20px;
                background: #f0f0f0;
            }}
            #container {{
                position: relative;
                display: inline-block;
                background: white;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }}
            #canvas {{
                cursor: crosshair;
                display: block;
            }}
            #info {{
                margin-top: 10px;
                padding: 10px;
                background: #e3f2fd;
                border-radius: 4px;
                font-family: Arial;
                font-size: 14px;
            }}
            button {{
                margin-top: 10px;
                padding: 10px 20px;
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 16px;
            }}
            button:hover {{
                background: #45a049;
            }}
        </style>
    </head>
    <body>
        <div id="container">
            <canvas id="canvas" width="{pix.width}" height="{pix.height}"></canvas>
        </div>
        <div id="info">Dibuja un rectángulo sobre la tabla y presiona "Guardar Selección"</div>
        <button id="saveBtn" style="display:none;">✅ Guardar Selección</button>

        <script>
            const canvas = document.getElementById('canvas');
            const ctx = canvas.getContext('2d');
            const img = new Image();
            const saveBtn = document.getElementById('saveBtn');

            let isDrawing = false;
            let startX, startY, endX, endY;
            let rectangles = {json.dumps(current_page_rects)};
            let tempRect = null;

            img.onload = function() {{
                redraw();
            }};
            img.src = 'data:image/png;base64,{img_base64}';

            function redraw() {{
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.drawImage(img, 0, 0);

                // Dibujar rectángulos guardados
                ctx.strokeStyle = '#FF0000';
                ctx.lineWidth = 3;
                rectangles.forEach((rect, idx) => {{
                    ctx.strokeRect(rect.x0, rect.y0, rect.x1 - rect.x0, rect.y1 - rect.y0);
                    ctx.fillStyle = '#FF0000';
                    ctx.font = 'bold 16px Arial';
                    ctx.fillText('#' + (idx + 1), rect.x0 + 5, rect.y0 + 20);
                }});

                // Dibujar rectángulo temporal
                if (tempRect) {{
                    ctx.strokeStyle = '#00FF00';
                    ctx.lineWidth = 3;
                    ctx.strokeRect(tempRect.x0, tempRect.y0, tempRect.x1 - tempRect.x0, tempRect.y1 - tempRect.y0);
                }}
            }}

            canvas.addEventListener('mousedown', (e) => {{
                const rect = canvas.getBoundingClientRect();
                startX = e.clientX - rect.left;
                startY = e.clientY - rect.top;
                isDrawing = true;
                tempRect = null;
                saveBtn.style.display = 'none';
            }});

            canvas.addEventListener('mousemove', (e) => {{
                if (!isDrawing) return;
                const rect = canvas.getBoundingClientRect();
                endX = e.clientX - rect.left;
                endY = e.clientY - rect.top;

                tempRect = {{
                    x0: Math.min(startX, endX),
                    y0: Math.min(startY, endY),
                    x1: Math.max(startX, endX),
                    y1: Math.max(startY, endY)
                }};

                redraw();
            }});

            canvas.addEventListener('mouseup', (e) => {{
                if (!isDrawing) return;
                const rect = canvas.getBoundingClientRect();
                endX = e.clientX - rect.left;
                endY = e.clientY - rect.top;

                const width = Math.abs(endX - startX);
                const height = Math.abs(endY - startY);

                if (width > 10 && height > 10) {{
                    tempRect = {{
                        x0: Math.min(startX, endX),
                        y0: Math.min(startY, endY),
                        x1: Math.max(startX, endX),
                        y1: Math.max(startY, endY)
                    }};
                    saveBtn.style.display = 'block';
                    redraw();
                }}

                isDrawing = false;
            }});

            saveBtn.addEventListener('click', () => {{
                if (tempRect) {{
                    const newRect = {{
                        page: {page_num},
                        x0: Math.round(tempRect.x0),
                        y0: Math.round(tempRect.y0),
                        x1: Math.round(tempRect.x1),
                        y1: Math.round(tempRect.y1)
                    }};

                    // 👇 Enviar el rectángulo a Streamlit
                    window.parent.postMessage({{
                        type: 'streamlit:setComponentValue',
                        value: JSON.stringify(newRect)
                    }}, '*');

                    // También lo añadimos localmente para que se vea de inmediato
                    rectangles.push(newRect);
                    tempRect = null;
                    saveBtn.style.display = 'none';
                    redraw();
                }}
            }});
        </script>
    </body>
    </html>
    """

    # ============================
    # Renderizar canvas HTML
    # IMPORTANTE: usar un key
    # ============================
    components.html(
        html_code,
        height=pix.height + 150,
        scrolling=True,
    )

    # ============================
    # Leer selección recibida desde el canvas
    # ============================
    # rect_value = st.session_state.get("pdf_canvas")

    if rect_value:
        try:
            # Puede llegar como string JSON o como dict
            if isinstance(rect_value, str):
                rect_data = json.loads(rect_value)
            else:
                rect_data = rect_value

            # Evitar duplicados
            exists = any(
                r["page"] == rect_data["page"]
                and r["x0"] == rect_data["x0"]
                and r["y0"] == rect_data["y0"]
                and r["x1"] == rect_data["x1"]
                and r["y1"] == rect_data["y1"]
                for r in st.session_state.rectangles
            )
            if not exists:
                st.session_state.rectangles.append(rect_data)

        except Exception as e:
            st.warning(f"No se pudo interpretar la selección: {e}")

        # Opcional: limpiar el valor consumido para no procesarlo en cada rerun
        st.session_state["pdf_canvas"] = None

    # ============================
    # Listado de rectángulos guardados
    # ============================
    if st.session_state.rectangles:
        st.subheader("📦 Áreas Seleccionadas")
        for i, rect in enumerate(st.session_state.rectangles):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.text(
                    f"Área {i+1}: Página {rect['page']+1} - "
                    f"({int(rect['x0'])}, {int(rect['y0'])}) → ({int(rect['x1'])}, {int(rect['y1'])})"
                )
            with col2:
                if st.button("❌", key=f"del_{i}"):
                    st.session_state.rectangles.pop(i)
                    st.rerun()

    # ============================
    # Botón de extracción
    # ============================
    st.divider()
    if st.button("🚀 Extraer y Descargar Excel", type="primary", use_container_width=True):
        if len(st.session_state.rectangles) == 0:
            st.error("⚠️ Debes dibujar al menos un rectángulo")
        else:
            with st.spinner("Extrayendo tablas..."):
                all_data = []

                for rect in st.session_state.rectangles:
                    page = doc[rect["page"]]

                    # Recalcular pixmap para escalas
                    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
                    scale_x = page.rect.width / pix.width
                    scale_y = page.rect.height / pix.height

                    x0 = rect["x0"] * scale_x
                    y0 = rect["y0"] * scale_y
                    x1 = rect["x1"] * scale_x
                    y1 = rect["y1"] * scale_y

                    clip_rect = fitz.Rect(x0, y0, x1, y1)
                    text = page.get_text("text", clip=clip_rect)

                    lines = text.strip().split("\n")
                    for line in lines:
                        if line.strip():
                            all_data.append([line.strip()])

                if not all_data:
                    st.warning("No se encontró texto dentro de las áreas seleccionadas.")
                else:
                    df = pd.DataFrame(all_data)

                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        df.to_excel(
                            writer,
                            index=False,
                            header=False,
                            sheet_name="Tablas",
                        )

                    excel_data = output.getvalue()

                    st.success("✅ Tablas extraídas exitosamente!")
                    st.download_button(
                        label="📥 Descargar Excel",
                        data=excel_data,
                        file_name="tablas_extraidas.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

                    st.subheader("Vista previa de datos extraídos")
                    st.dataframe(df, use_container_width=True)

else:
    st.info("👆 Sube un archivo PDF para comenzar")
    st.markdown(
        """
    ### Instrucciones:
    1. Sube tu archivo PDF
    2. Navega entre las páginas
    3. **Haz clic y arrastra** para dibujar rectángulos sobre las tablas
    4. Presiona "Guardar Selección" (aparece en verde abajo del canvas)
    5. Verás crecer el contador de rectángulos
    6. Haz clic en "Extraer y Descargar Excel"
    7. Todas las tablas se unificarán en una sola hoja
    """
    )
