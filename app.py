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

# Inicializar session state
if 'pdf_document' not in st.session_state:
    st.session_state.pdf_document = None
if 'rectangles' not in st.session_state:
    st.session_state.rectangles = []
if 'current_page' not in st.session_state:
    st.session_state.current_page = 0

# Subir PDF
uploaded_file = st.file_uploader("Sube tu PDF", type=['pdf'])

if uploaded_file is not None:
    # Cargar PDF
    if st.session_state.pdf_document is None or uploaded_file != st.session_state.get('last_file'):
        st.session_state.pdf_document = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        st.session_state.last_file = uploaded_file
        st.session_state.rectangles = []
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
        st.info(f"📍 Rectángulos totales: {len(st.session_state.rectangles)}")
    
    with col3:
        if st.button("🗑️ Limpiar Todo"):
            st.session_state.rectangles = []
            st.rerun()
    
    # Convertir página a imagen
    page = doc[page_num]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # Convertir imagen a base64
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    # Filtrar rectángulos de la página actual
    current_page_rects = [r for r in st.session_state.rectangles if r['page'] == page_num]
    
    st.subheader(f"Página {page_num + 1} de {total_pages}")
    st.caption("🖱️ Haz clic y arrastra para dibujar rectángulos sobre las tablas")
    
    # HTML con canvas interactivo
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ margin: 0; padding: 20px; background: #f0f0f0; }}
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
        </style>
    </head>
    <body>
        <div id="container">
            <canvas id="canvas" width="{pix.width}" height="{pix.height}"></canvas>
        </div>
        <div id="info">Dibuja un rectángulo sobre la tabla. Los rectángulos se guardarán automáticamente.</div>
        
        <script>
            const canvas = document.getElementById('canvas');
            const ctx = canvas.getContext('2d');
            const img = new Image();
            
            let isDrawing = false;
            let startX, startY;
            let rectangles = {json.dumps(current_page_rects)};
            
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
            }}
            
            canvas.addEventListener('mousedown', (e) => {{
                const rect = canvas.getBoundingClientRect();
                startX = e.clientX - rect.left;
                startY = e.clientY - rect.top;
                isDrawing = true;
            }});
            
            canvas.addEventListener('mousemove', (e) => {{
                if (!isDrawing) return;
                
                const rect = canvas.getBoundingClientRect();
                const currentX = e.clientX - rect.left;
                const currentY = e.clientY - rect.top;
                
                redraw();
                
                // Dibujar rectángulo temporal
                ctx.strokeStyle = '#00FF00';
                ctx.lineWidth = 2;
                ctx.setLineDash([5, 5]);
                ctx.strokeRect(startX, startY, currentX - startX, currentY - startY);
                ctx.setLineDash([]);
            }});
            
            canvas.addEventListener('mouseup', (e) => {{
                if (!isDrawing) return;
                
                const rect = canvas.getBoundingClientRect();
                const endX = e.clientX - rect.left;
                const endY = e.clientY - rect.top;
                
                const width = Math.abs(endX - startX);
                const height = Math.abs(endY - startY);
                
                // Solo guardar si el rectángulo es suficientemente grande
                if (width > 10 && height > 10) {{
                    const newRect = {{
                        page: {page_num},
                        x0: Math.min(startX, endX),
                        y0: Math.min(startY, endY),
                        x1: Math.max(startX, endX),
                        y1: Math.max(startY, endY)
                    }};
                    
                    // Enviar a Streamlit
                    window.parent.postMessage({{
                        type: 'streamlit:setComponentValue',
                        value: newRect
                    }}, '*');
                }
                
                isDrawing = false;
                redraw();
            }});
            
            // Prevenir scroll al arrastrar
            canvas.addEventListener('touchstart', (e) => e.preventDefault());
            canvas.addEventListener('touchmove', (e) => e.preventDefault());
        </script>
    </body>
    </html>
    """
    
    # Renderizar canvas
    result = components.html(html_code, height=pix.height + 100, scrolling=True)
    
    # Si se dibujó un nuevo rectángulo, agregarlo
    if result is not None and isinstance(result, dict):
        # Verificar si ya existe
        exists = any(
            r['page'] == result['page'] and 
            r['x0'] == result['x0'] and 
            r['y0'] == result['y0'] and
            r['x1'] == result['x1'] and
            r['y1'] == result['y1']
            for r in st.session_state.rectangles
        )
        if not exists:
            st.session_state.rectangles.append(result)
            st.rerun()
    
    # Mostrar rectángulos guardados
    if st.session_state.rectangles:
        st.subheader("📦 Áreas Seleccionadas")
        for i, rect in enumerate(st.session_state.rectangles):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.text(f"Área {i+1}: Página {rect['page']+1} - ({int(rect['x0'])}, {int(rect['y0'])}) → ({int(rect['x1'])}, {int(rect['y1'])})")
            with col2:
                if st.button("❌", key=f"del_{i}"):
                    st.session_state.rectangles.pop(i)
                    st.rerun()
    
    # Botón de extracción
    st.divider()
    if st.button("🚀 Extraer y Descargar Excel", type="primary", use_container_width=True):
        if len(st.session_state.rectangles) == 0:
            st.error("⚠️ Debes dibujar al menos un rectángulo")
        else:
            with st.spinner("Extrayendo tablas..."):
                all_data = []
                
                for rect in st.session_state.rectangles:
                    page = doc[rect['page']]
                    
                    # Convertir coordenadas del canvas a coordenadas PDF
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    scale_x = page.rect.width / pix.width
                    scale_y = page.rect.height / pix.height
                    
                    x0 = rect['x0'] * scale_x
                    y0 = rect['y0'] * scale_y
                    x1 = rect['x1'] * scale_x
                    y1 = rect['y1'] * scale_y
                    
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
    3. **Haz clic y arrastra** para dibujar rectángulos sobre las tablas
    4. Los rectángulos se guardan automáticamente (rojos con números)
    5. Haz clic en "Extraer y Descargar Excel"
    6. Todas las tablas se unificarán en una sola hoja
    """)