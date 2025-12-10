import streamlit as st
import pandas as pd
import json
import base64
from io import BytesIO
from PIL import Image
import os
# Importaciones necesarias para la conexión con Gemini
from google import genai
from google.genai.errors import APIError
from langchain_core.messages import SystemMessage, HumanMessage
import tempfile # Necesario para manejar archivos cargados localmente

# --- Configuración de Streamlit ---
st.set_page_config(page_title="Analizador DAX y KPI con Visión para Power BI", layout="wide")
st.title("👁️ Analizador DAX y Gráficas Power BI (Visión Ampliada)")
st.markdown("Sube la estructura de tus datos (TXT, JSON) o la captura de tu modelo para obtener medidas DAX y recomendaciones.")

# ----------------------------------------------------
# PASO 0: Configuración de la API de Gemini (Seguridad)
# ----------------------------------------------------
api_key = os.getenv("GOOGLE_API_KEY") 

if not api_key:
    with st.sidebar:
        st.warning("⚠️ Introduce tu clave de API de Gemini para continuar.")
        api_key_input = st.text_input("Clave de API de Google Gemini", type="password")
    
    if api_key_input:
        api_key = api_key_input
    else:
        st.info("Introduce la clave de API en la barra lateral.")
        st.stop()

# Configurar el cliente de API de Google para visión
os.environ["GOOGLE_API_KEY"] = api_key
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Error al inicializar el cliente de Gemini: {e}")
    st.stop()

# --- Funciones de Análisis ---

# ... (Las funciones analizar_imagen_con_gemini, imagen_a_base64, convertir_analisis_imagen, analizar_estructura, generar_medidas_dax, sugerir_kpi_okr, recomendar_graficas se mantienen SIN CAMBIOS) ...

# -------------------------------------------------------------------------
# CÓDIGO CLAVE: Manejo de carga de archivos ampliados
# -------------------------------------------------------------------------

def manejar_analisis_archivo(archivo, tipo_archivo):
    """Maneja la lógica para TXT, JSON, VSPAX, OSPAX."""
    nombre_tabla = st.text_input("Nombre de la tabla en Power BI:", archivo.name.split('.')[0])
    analisis = None
    
    # 1. Manejo de archivos binarios/comprimidos (NO LEGIBLES)
    if tipo_archivo in ['vspax', 'ovpax']:
        st.warning(
            f"El archivo .{tipo_archivo} es un formato binario comprimido y no puede ser leído directamente por Python."
        )
        st.info(
            "Para obtener el análisis, por favor usa **DAX Studio** (herramienta externa) para **Exportar la Metadata** "
            "del modelo a un archivo **JSON** o **TXT** y cárgalo en esta aplicación."
        )
        return False, None, nombre_tabla

    # 2. Manejo de JSON o TXT (Metadata legible)
    try:
        if tipo_archivo in ['txt', 'json']:
            # Guardar temporalmente el archivo para leer su contenido completo
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{tipo_archivo}') as tmp_file:
                tmp_file.write(archivo.getvalue())
                temp_file_path = tmp_file.name

            with open(temp_file_path, 'r', encoding='utf-8') as f:
                contenido = f.read()
            
            os.remove(temp_file_path)

            if tipo_archivo == 'json':
                # Si es JSON, intentamos leer la estructura directamente.
                data = json.loads(contenido)
                
                # Asumimos que el JSON es la estructura del modelo (similar al formato de la visión)
                if isinstance(data, dict) and 'columnas' in data:
                    analisis = convertir_analisis_imagen(data)
                elif isinstance(data, list) and data and 'name' in data[0]: # Si es una lista de tablas/columnas
                    # Si el JSON es una exportación compleja de metadata (DAX Studio), la analizamos como texto.
                    st.info("El JSON se analizará como texto debido a su estructura compleja.")
                    analisis_gemini = analizar_texto_con_gemini(contenido)
                    if 'error' in analisis_gemini:
                         st.error(f"Error de análisis JSON/Gemini: {analisis_gemini['error']}")
                         return False, None, nombre_tabla
                    analisis = convertir_analisis_imagen(analisis_gemini)
                else:
                    st.warning("Estructura JSON no reconocida. Por favor, asegúrate de que contenga nombres de columnas.")
                    return False, None, nombre_tabla

            elif tipo_archivo == 'txt':
                 # Para archivos de texto simple, lo pasamos al análisis de Gemini como texto.
                 analisis_gemini = analizar_texto_con_gemini(contenido)
                 if 'error' in analisis_gemini:
                    st.error(f"Error de análisis TXT/Gemini: {analisis_gemini['error']}")
                    return False, None, nombre_tabla
                 analisis = convertir_analisis_imagen(analisis_gemini)
            
            st.success("✅ Estructura de datos procesada correctamente.")
            return True, analisis, nombre_tabla

        else:
            return False, None, nombre_tabla

    except Exception as e:
        st.error(f"Error al leer/procesar el archivo {tipo_archivo}: {e}")
        if os.path.exists(temp_file_path): os.remove(temp_file_path)
        return False, None, nombre_tabla


def analizar_texto_con_gemini(texto_datos):
    """Función auxiliar para analizar texto simple (TXT o JSON complejo) usando Gemini."""
    system_prompt = (
        "Eres un experto en Power BI. Analiza el siguiente texto que contiene la estructura de un modelo de datos (nombres de tablas, columnas y tipos). "
        "Devuelve SOLO un objeto JSON con la estructura solicitada, extrayendo los nombres de las columnas, su tipo lógico (numerico/categorico/fecha) y sugiriendo métricas clave."
    )
    json_structure = {
        "nombre_tabla": "nombre_principal",
        "columnas": [
            {"nombre": "nombre_columna", "tipo": "numerico/categorico/fecha", "descripcion": ""},
        ],
        "relaciones_posibles": ["descripción de relaciones"],
        "metricas_clave": ["métricas importantes"]
    }

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=[
            "Analiza la estructura de datos a continuación. Usa este Esquema JSON Requerido: " + json.dumps(json_structure, indent=2),
            f"Datos: \n{texto_datos}"
        ]),
    ]
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=messages,
            config={'response_mime_type': 'application/json'}
        )
        
        texto_limpio = response.text.strip()
        if texto_limpio.startswith("```json"):
            texto_limpio = texto_limpio.split("```json")[1].strip()
        if texto_limpio.endswith("```"):
            texto_limpio = texto_limpio.split("```")[0].strip()

        return json.loads(texto_limpio)
        
    except Exception as e:
         return {"error": f"Error de análisis de texto con Gemini: {e}"}


# --- UI Principal (MODIFICADA) ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📤 Cargar Datos")
    
    tipo_entrada = st.radio("Tipo de entrada:", ["Archivo (Estructura)", "Imagen de tabla/Modelo", "Excel/CSV (Datos)"])
    
    # ----------------------------------------------------
    # Lógica de Carga de Archivos (.txt, .json, .vspax, .ovpax)
    # ----------------------------------------------------
    if tipo_entrada == "Archivo (Estructura)":
        archivo = st.file_uploader(
            "Sube archivo de estructura o binario (TXT, JSON, VSPAX, OPAX)", 
            type=['txt', 'json', 'vspax', 'ovpax', 'csv', 'xlsx']
        )
        
        if archivo:
            file_extension = archivo.name.split('.')[-1].lower()

            if file_extension in ['csv', 'xlsx']:
                st.warning("Por favor, usa la opción 'Excel/CSV' para analizar estos archivos.")
            else:
                if st.button("🚀 Analizar Estructura Cargada"):
                    with st.spinner(f"Analizando archivo .{file_extension}..."):
                        procesado, analisis, nombre_tabla = manejar_analisis_archivo(archivo, file_extension)
                        
                        if procesado:
                            st.session_state['analisis'] = analisis
                            st.session_state['medidas'] = generar_medidas_dax(analisis, nombre_tabla)
                            st.session_state['graficas'] = recomendar_graficas(analisis)
                            st.session_state['kpi_okr'] = sugerir_kpi_okr(analisis, nombre_tabla)
                            st.session_state['nombre_tabla'] = nombre_tabla
                            st.rerun()
                        elif analisis is not None:
                             st.error("Fallo al procesar el archivo.")

    # ----------------------------------------------------
    # Lógica de Imagen
    # ----------------------------------------------------
    elif tipo_entrada == "Imagen de tabla/Modelo":
        st.info("📸 Sube una captura de tu tabla de datos o de la vista del modelo en Power BI.")
        imagen = st.file_uploader("Sube imagen de tabla o modelo", type=['png', 'jpg', 'jpeg'])
        
        if imagen:
            img = Image.open(imagen)
            st.image(img, caption="Imagen cargada", use_container_width=True)
            
            nombre_tabla = st.text_input("Nombre de la tabla sugerido:", "TablaImagen")
            
            if st.button("🔍 Analizar Imagen con Gemini"):
                with st.spinner("Analizando imagen y extrayendo estructura con Gemini Vision..."):
                    analisis_gemini = analizar_imagen_con_gemini(img) 
                    
                    if 'error' in analisis_gemini:
                        st.error(f"Error: {analisis_gemini['error']}")
                    else:
                        analisis = convertir_analisis_imagen(analisis_gemini)
                        st.session_state['analisis'] = analisis
                        st.session_state['medidas'] = generar_medidas_dax(analisis, nombre_tabla)
                        st.session_state['graficas'] = recomendar_graficas(analisis)
                        st.session_state['kpi_okr'] = sugerir_kpi_okr(analisis, nombre_tabla)
                        st.session_state['nombre_tabla'] = nombre_tabla
                        st.success("¡Estructura de datos extraída por Gemini!")
                        st.rerun()

    # ----------------------------------------------------
    # Lógica de Excel/CSV (Datos)
    # ----------------------------------------------------
    elif tipo_entrada == "Excel/CSV (Datos)":
        archivo = st.file_uploader("Sube tu archivo", type=['xlsx', 'xls', 'csv'])
        
        if archivo:
            try:
                if archivo.name.endswith('.csv'):
                    df = pd.read_csv(archivo)
                else:
                    df = pd.read_excel(archivo)
                
                st.success(f"✅ Archivo cargado: {len(df)} filas, {len(df.columns)} columnas")
                
                with st.expander("👀 Vista previa de datos"):
                    st.dataframe(df.head(10))
                
                nombre_tabla = st.text_input("Nombre de la tabla en Power BI:", "Datos")
                
                if st.button("🚀 Analizar y Generar Soluciones (Archivo)"):
                    with st.spinner("Analizando datos y generando sugerencias..."):
                        analisis = analizar_estructura(df)
                        st.session_state['analisis'] = analisis
                        st.session_state['medidas'] = generar_medidas_dax(analisis, nombre_tabla)
                        st.session_state['graficas'] = recomendar_graficas(analisis)
                        st.session_state['kpi_okr'] = sugerir_kpi_okr(analisis, nombre_tabla)
                        st.session_state['nombre_tabla'] = nombre_tabla
                        st.rerun()
                
            except Exception as e:
                st.error(f"Error al cargar archivo: {str(e)}")


with col2:
    st.subheader("📊 Resultados del Análisis")
    
    # ... (Secciones de resultados: Estructura, KPI/OKR, DAX, Gráficas se mantienen igual) ...

    if 'analisis' in st.session_state:
        analisis = st.session_state['analisis']
        
        st.markdown("### 📋 Estructura de Datos")
        
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Columnas Numéricas", len(analisis['numericas']))
        col_b.metric("Columnas Categóricas", len(analisis['categoricas']))
        col_c.metric("Columnas Fecha", len(analisis['fechas']))
        
        with st.expander("🔍 Detalle de columnas"):
            for col in analisis['columnas']:
                tipo_col = analisis['tipos'].get(col, 'N/A')
                nulls = analisis['nulls'].get(col, 0)
                st.text(f"{col}: {tipo_col} | Nulos: {nulls}")

        if 'relaciones' in analisis and analisis['relaciones']:
            with st.expander("🔗 Relaciones sugeridas"):
                for rel in analisis['relaciones']:
                    st.markdown(f"- {rel}")
        
        if 'metricas_clave' in analisis and analisis['metricas_clave']:
            with st.expander("🎯 Métricas clave identificadas"):
                for metrica in analisis['metricas_clave']:
                    st.markdown(f"- {metrica}")

# --- Sección de KPI y OKR ---
if 'kpi_okr' in st.session_state:
    st.markdown("---")
    st.markdown("## 🎯 Sugerencias de KPI y OKR")
    
    for sugerencia in st.session_state['kpi_okr']:
        with st.expander(f"🏅 {sugerencia['nombre']} ({sugerencia['tipo']})"):
            st.markdown(f"**Objetivo/Enfoque:** {sugerencia['objetivo']}")
            st.markdown(f"**Medida DAX base:**")
            st.code(sugerencia['dax_base'], language='dax')
            st.markdown(f"**Visualización Clave:** {sugerencia['visualizacion']}")

# --- Sección de Medidas DAX ---
if 'medidas' in st.session_state:
    st.markdown("---")
    st.markdown("## 📐 Medidas DAX Detalladas")
    
    medidas = st.session_state['medidas']
    
    tipos = list(set([m['tipo'] for m in medidas]))
    tipo_filtro = st.multiselect("Filtrar por tipo de medida:", tipos, default=tipos)
    
    medidas_filtradas = [m for m in medidas if m['tipo'] in tipo_filtro]
    
    if st.button("📥 Descargar medidas DAX filtradas"):
        contenido = "\n\n".join([f"// {m['nombre']}\n// {m['descripcion']}\n{m['dax']}" for m in medidas_filtradas])
        st.download_button(
            label="💾 Descargar archivo DAX",
            data=contenido,
            file_name=f"medidas_dax_{st.session_state.get('nombre_tabla', 'tabla')}.txt",
            mime="text/plain"
        )
    
    for i, medida in enumerate(medidas_filtradas):
        with st.expander(f"📊 {medida['nombre']} ({medida['tipo']})"):
            st.markdown(f"**Descripción:** {medida.get('descripcion', 'N/A')}")
            st.code(medida['dax'], language='dax')

# --- Sección de Gráficas Recomendadas ---
if 'graficas' in st.session_state:
    st.markdown("---")
    st.markdown("## 📈 Gráficas Recomendadas")
    
    graficas = st.session_state['graficas']
    
    for grafica in graficas:
        with st.container():
            col_g1, col_g2 = st.columns([2, 3])
            
            with col_g1:
                st.markdown(f"### {grafica.get('icono', '📊')} {grafica['tipo']}")
                st.markdown(f"**Uso:** {grafica['uso']}")
            
            with col_g2:
                st.markdown("**Columnas sugeridas:**")
                for col in grafica['columnas']:
                    st.markdown(f"- `{col}`")
            
            st.markdown("---")
