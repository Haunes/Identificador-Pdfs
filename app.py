import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
import pandas as pd
from streamlit_drawable_canvas import st_canvas

st.set_page_config(page_title="Extractor de Tablas PDF", layout="wide")

st.title("📊 Extractor de Tablas PDF")

# Inicializar session state
if 'pdf_document' not in st.session_state:
    st.session_state.pdf_document = None
if 'all_rectangles' not in st.session_state:
    st.session_state.all_rectangles = []
if 'current_page' not in st.session_state:
    st.session_state.current_page = 0

# Subir PDF
uploaded_file = st.file_uploader("Sube tu PDF", type=['pdf'])

if uploaded_file is not None:
    # Cargar PDF
    if st.session_state.pdf_document is None or uploaded_file != st.session_state.get('last_file'):
        st.session_state.pdf_document = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        st.session_state.last_file = uploaded_file
        st.session_state.all_rectangles = []
        st.session_state.current_page = 0
    
    doc = st.session_state.pdf_document
    total_pages = len(doc)
    
    st.success(f"✅ PDF cargado: {uploaded_file.name} ({total_pages} páginas)")
    
    # Controles
    col1, col2, col3 = st.columns([2, 3, 2])
    
    with col1:
        page_num = st.number_input(
            "Página", 
            min_value=1, 
            max_value=total_pages, 
            value=st.session_state.current_page + 1,
            step=1
        ) - 1
        st.session_state.current_page = page_num
    
    with col2:
        st.info(f"📍 Rectángulos seleccionados: {len(st.session_state.all_rectangles)}")
    
    with col3:
        if st.button("🗑️ Limpiar Selecciones"):
            st.session_state.all_rectangles = []
            st.rerun()
    
    # Convertir página a imagen
    page = doc[page_num]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # Canvas para dibujar
    st.subheader(f"Página {page_num + 1} de {total_pages}")
    st.caption("🖱️ Dibuja rectángulos sobre las tablas que quieres extraer")
    
    canvas_result = st_canvas(
        fill_color="rgba(0, 0, 0, 0)",
        stroke_width=3,
        stroke_color="#FF0000",
        background_image=img,
        update_streamlit=True,
        height=pix.height,
        width=pix.width,
        drawing_mode="rect",
        key=f"canvas_{page_num}",
    )
    
    # Guardar rectángulos
    if canvas_result.json_data is not None:
        objects = canvas_result.json_data["objects"]
        if len(objects) > 0:
            for obj in objects:
                if obj["type"] == "rect":
                    rect_data = {
                        'page': page_num,
                        'left': obj['left'],
                        'top': obj['top'],
                        'width': obj['width'],
                        'height': obj['height']
                    }
                    # Evitar duplicados
                    if rect_data not in st.session_state.all_rectangles:
                        st.session_state.all_rectangles.append(rect_data)
    
    # Mostrar rectángulos guardados
    if st.session_state.all_rectangles:
        st.subheader("📦 Áreas Seleccionadas")
        for i, rect in enumerate(st.session_state.all_rectangles):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.text(f"Área {i+1}: Página {rect['page']+1} - Pos({int(rect['left'])}, {int(rect['top'])}) - Tamaño({int(rect['width'])}x{int(rect['height'])})")
            with col2:
                if st.button("❌", key=f"del_{i}"):
                    st.session_state.all_rectangles.pop(i)
                    st.rerun()
    
    # Botón de extracción
    if st.button("🚀 Extraer y Descargar Excel", type="primary"):
        if len(st.session_state.all_rectangles) == 0:
            st.error("⚠️ Debes dibujar al menos un rectángulo")
        else:
            with st.spinner("Extrayendo tablas..."):
                all_data = []
                
                for rect in st.session_state.all_rectangles:
                    page = doc[rect['page']]
                    
                    # Convertir coordenadas del canvas a coordenadas PDF
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    scale_x = page.rect.width / pix.width
                    scale_y = page.rect.height / pix.height
                    
                    x0 = rect['left'] * scale_x
                    y0 = rect['top'] * scale_y
                    x1 = (rect['left'] + rect['width']) * scale_x
                    y1 = (rect['top'] + rect['height']) * scale_y
                    
                    # Extraer texto del área
                    clip_rect = fitz.Rect(x0, y0, x1, y1)
                    text = page.get_text("text", clip=clip_rect)
                    
                    # Separar por líneas
                    lines = text.strip().split('\n')
                    for line in lines:
                        if line.strip():
                            all_data.append([line.strip()])
                
                # Crear DataFrame
                df = pd.DataFrame(all_data)
                
                # Convertir a Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, header=False, sheet_name='Tablas')
                
                excel_data = output.getvalue()
                
                st.success("✅ Tablas extraídas exitosamente!")
                st.download_button(
                    label="📥 Descargar Excel",
                    data=excel_data,
                    file_name="tablas_extraidas.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                # Mostrar preview
                st.subheader("Vista previa de datos extraídos")
                st.dataframe(df, use_container_width=True)

else:
    st.info("👆 Sube un archivo PDF para comenzar")
    st.markdown("""
    ### Instrucciones:
    1. Sube tu archivo PDF
    2. Navega entre las páginas
    3. Dibuja rectángulos sobre las tablas
    4. Haz clic en "Extraer y Descargar Excel"
    5. Todas las tablas se unificarán en una sola hoja
    """)