import streamlit as st
import pandas as pd
import json
import base64
from io import BytesIO
from PIL import Image
import os
import tempfile
from google import genai
from google.genai.errors import APIError
from langchain_core.messages import SystemMessage, HumanMessage

# --- Configuración Inicial ---
st.set_page_config(page_title="Analizador DAX y KPI con Visión para Power BI", layout="wide")
st.title("👁️ Analizador DAX y Gráficas Power BI (Visión Ampliada)")
st.markdown("Sube la estructura de tus datos o capturas de pantalla para obtener medidas DAX, KPI y recomendaciones.")

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

os.environ["GOOGLE_API_KEY"] = api_key
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Error al inicializar el cliente de Gemini: {e}")
    st.stop()

# --- Funciones de Análisis (RESTAURADA la función faltante) ---

# FUNCIÓN: Análisis de Estructura de Datos (desde DataFrame)
def analizar_estructura(df):
    """ Función que analiza un DataFrame para extraer tipos de columnas. """
    analisis = {
        'columnas': list(df.columns),
        'tipos': {},
        'numericas': [],
        'categoricas': [],
        'fechas': [],
        'nulls': {}
    }
    
    for col in df.columns:
        tipo = str(df[col].dtype)
        analisis['tipos'][col] = tipo
        analisis['nulls'][col] = df[col].isnull().sum()
        
        if 'datetime' in tipo:
            analisis['fechas'].append(col)
        elif 'object' in tipo or 'category' in tipo:
            analisis['categoricas'].append(col)
        elif 'int' in tipo or 'float' in tipo:
            analisis['numericas'].append(col)
    
    return analisis


# FUNCIÓN: Análisis de Imagen con Gemini Vision
# (El código de analizar_imagen_con_gemini se mantiene igual)
def analizar_imagen_con_gemini(imagen_data):
    system_prompt = (
        "Eres un experto en Power BI y análisis de modelos de datos. Tu tarea es analizar la imagen "
        "que contiene una tabla, datos, o una vista del modelo de datos de Power BI. "
        "Devuelve **SOLO** un objeto JSON con la estructura exacta definida a continuación. "
        "Identifica los nombres de las columnas, su tipo lógico (numerico/categorico/fecha), "
        "y sugiere métricas clave y relaciones. No incluyas texto explicativo."
    )
    
    json_structure = {
        "nombre_tabla": "nombre sugerido para la tabla",
        "columnas": [
            {"nombre": "nombre_columna", "tipo": "numerico/categorico/fecha", "descripcion": "breve descripción"},
        ],
        "relaciones_posibles": ["descripción de posibles relaciones con otras tablas (si aplica)"],
        "metricas_clave": ["lista de métricas importantes identificadas"]
    }
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=[
            "Analiza esta imagen y devuelve la información de la tabla usando el siguiente esquema JSON.",
            "Esquema JSON Requerido: " + json.dumps(json_structure, indent=2)
        ]),
        imagen_data
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
        
    except APIError as e:
        return {"error": f"Error de API de Gemini: {e}. Revise la clave o el uso."}
    except Exception as e:
         return {"error": f"Error de procesamiento de JSON/Visión: {e}. Intente con una imagen más clara."}


# FUNCIÓN: Convertir Análisis de Imagen a formato estándar
def convertir_analisis_imagen(analisis_gemini):
    # ... (código sin cambios) ...
    analisis = {
        'columnas': [],
        'tipos': {},
        'numericas': [],
        'categoricas': [],
        'fechas': [],
        'nulls': {},
        'nombre_tabla': analisis_gemini.get('nombre_tabla', 'Tabla'),
        'relaciones': analisis_gemini.get('relaciones_posibles', []),
        'metricas_clave': analisis_gemini.get('metricas_clave', [])
    }
    
    for col_info in analisis_gemini.get('columnas', []):
        nombre = col_info.get('nombre')
        tipo = col_info.get('tipo', '').lower()
        
        if not nombre: continue

        analisis['columnas'].append(nombre)
        analisis['tipos'][nombre] = tipo
        analisis['nulls'][nombre] = 0
        
        if tipo == 'numerico':
            analisis['numericas'].append(nombre)
        elif tipo == 'fecha':
            analisis['fechas'].append(nombre)
        else:
            analisis['categoricas'].append(nombre)
    
    return analisis


# FUNCIÓN: Manejar Análisis de Archivo de Estructura (TXT, JSON, VSPAX, OSPAX)
def manejar_analisis_archivo(archivo, tipo_archivo):
    """Maneja la lógica para TXT, JSON, VSPAX, OSPAX."""
    nombre_tabla = st.text_input("Nombre de la tabla en Power BI:", archivo.name.split('.')[0])
    analisis = None
    
    if tipo_archivo in ['vspax', 'ovpax']:
        st.warning(
            f"El archivo .{tipo_archivo} es un formato binario comprimido y no puede ser leído directamente por Python."
        )
        st.info(
            "Para obtener el análisis, por favor usa **DAX Studio** (herramienta externa) para **Exportar la Metadata** "
            "del modelo a un archivo **JSON** o **TXT** y cárgalo."
        )
        return False, None, nombre_tabla

    try:
        if tipo_archivo in ['txt', 'json']:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{tipo_archivo}') as tmp_file:
                tmp_file.write(archivo.getvalue())
                temp_file_path = tmp_file.name

            with open(temp_file_path, 'r', encoding='utf-8') as f:
                contenido = f.read()
            
            os.remove(temp_file_path)

            if tipo_archivo == 'json':
                data = json.loads(contenido)
                
                # ... (lógica de análisis JSON/TXT/Gemini sin cambios) ...
                if isinstance(data, dict) and 'columnas' in data:
                    analisis = convertir_analisis_imagen(data)
                elif isinstance(data, list) and data and 'name' in data[0]: 
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


# FUNCIÓN: Analizar Texto con Gemini
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

# --- Lógica de Generación DAX, KPI y Gráficas (sin cambios) ---
# (Las funciones generar_medidas_dax, sugerir_kpi_okr, recomendar_graficas se mantienen igual)


# --- UI Principal (MODIFICADA) ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📤 Cargar Datos")
    
    # Separación de Entradas
    tipo_entrada = st.radio(
        "Tipo de entrada:", 
        ["1. Excel/CSV (Datos)", "2. Archivo (Estructura)", "3. Imagen (Visión)"]
    )
    
    # ----------------------------------------------------
    # 1. Excel/CSV (Datos)
    # ----------------------------------------------------
    if tipo_entrada == "1. Excel/CSV (Datos)":
        archivo = st.file_uploader("Sube tu archivo (Excel o CSV)", type=['xlsx', 'xls', 'csv'])
        
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
                
                if st.button("🚀 Analizar y Generar Soluciones"):
                    with st.spinner("Analizando datos y generando sugerencias..."):
                        analisis = analizar_estructura(df) # <-- FUNCIÓN RESTAURADA
                        st.session_state['analisis'] = analisis
                        st.session_state['medidas'] = generar_medidas_dax(analisis, nombre_tabla)
                        st.session_state['graficas'] = recomendar_graficas(analisis)
                        st.session_state['kpi_okr'] = sugerir_kpi_okr(analisis, nombre_tabla)
                        st.session_state['nombre_tabla'] = nombre_tabla
                        st.rerun()
                
            except Exception as e:
                st.error(f"Error al cargar archivo: {str(e)}")
    
    # ----------------------------------------------------
    # 2. Archivo (Estructura - TXT, JSON, VSPAX, OPAX)
    # ----------------------------------------------------
    elif tipo_entrada == "2. Archivo (Estructura)":
        archivo = st.file_uploader(
            "Sube archivo de estructura o binario (TXT, JSON, VSPAX, OPAX)", 
            type=['txt', 'json', 'vspax', 'ovpax']
        )
        
        if archivo:
            file_extension = archivo.name.split('.')[-1].lower()

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
    # 3. Imagen (Visión)
    # ----------------------------------------------------
    elif tipo_entrada == "3. Imagen (Visión)":
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


with col2:
    st.subheader("📊 Resultados del Análisis")
    
    # ... (El resto del código de resultados se mantiene igual) ...

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

# --- Secciones de Salida (KPI/DAX/Gráficas) (Sin cambios) ---
if 'kpi_okr' in st.session_state:
# ... (código KPI/OKR) ...

if 'medidas' in st.session_state:
# ... (código Medidas DAX) ...

if 'graficas' in st.session_state:
# ... (código Gráficas) ...
