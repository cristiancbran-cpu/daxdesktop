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

# --- Funciones de Análisis ---

# FUNCIÓN RESTAURADA: Análisis de Estructura de Datos (desde DataFrame)
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

# FUNCIÓN: Generar Medidas DAX
def generar_medidas_dax(analisis, nombre_tabla):
    medidas = []
    
    for col in analisis['numericas']:
        medidas.append({
            'nombre': f'Total {col}',
            'dax': f'Total {col} = SUM({nombre_tabla}[{col}])',
            'tipo': 'Agregación básica',
            'descripcion': f'Suma total de {col}'
        })
        medidas.append({
            'nombre': f'Promedio {col}',
            'dax': f'Promedio {col} = AVERAGE({nombre_tabla}[{col}])',
            'tipo': 'Agregación básica',
            'descripcion': f'Promedio de {col}'
        })

    if analisis['columnas']:
        medidas.append({
            'nombre': 'Conteo Total Filas',
            'dax': f'Conteo Total Filas = COUNTROWS({nombre_tabla})',
            'tipo': 'Conteo',
            'descripcion': 'Cuenta todas las filas de la tabla'
        })
    
    if analisis['fechas'] and analisis['numericas']:
        fecha_col = analisis['fechas'][0]
        num_col = analisis['numericas'][0]
        
        medidas.append({
            'nombre': f'{num_col} YTD',
            'dax': f'{num_col} YTD = TOTALYTD(SUM({nombre_tabla}[{num_col}]), {nombre_tabla}[{fecha_col}])',
            'tipo': 'Inteligencia de tiempo',
            'descripcion': f'Acumulado del año hasta la fecha para {num_col}'
        })
        
        medidas.append({
            'nombre': f'Variación % {num_col} vs Mes Anterior',
            'dax': f'''Variación % {num_col} vs Mes Anterior = 
VAR CurrentValue = SUM({nombre_tabla}[{num_col}])
VAR PreviousValue = CALCULATE(SUM({nombre_tabla}[{num_col}]), PREVIOUSMONTH({nombre_tabla}[{fecha_col}]))
RETURN
DIVIDE(CurrentValue - PreviousValue, PreviousValue, 0)''',
            'tipo': 'Análisis comparativo',
            'descripcion': f'Cambio porcentual vs mes anterior'
        })

    if len(analisis['numericas']) >= 1 and len(analisis['categoricas']) >= 1:
        num_col = analisis['numericas'][0]
        cat_col = analisis['categoricas'][0]
        
        medidas.append({
            'nombre': f'{num_col} Top 5 {cat_col}',
            'dax': f'''Top 5 {cat_col} = 
CALCULATE(
    SUM({nombre_tabla}[{num_col}]),
    TOPN(5, ALL({nombre_tabla}[{cat_col}]), SUM({nombre_tabla}[{num_col}]))
)''',
            'tipo': 'Filtrado avanzado',
            'descripcion': f'Total solo para los 5 principales {cat_col}'
        })
    
    return medidas

# FUNCIÓN: Sugerir KPI/OKR
def sugerir_kpi_okr(analisis, nombre_tabla):
    sugerencias = []
    
    if analisis['numericas']:
        num_col = analisis['numericas'][0]
        
        sugerencias.append({
            'nombre': f'KPI: Tasa de {num_col}',
            'objetivo': f'Monitorear la suma promedio o total de `{num_col}` por entidad/tiempo.',
            'dax_base': f'SUM({nombre_tabla}[{num_col}])',
            'tipo': 'Monitoreo de Volumen',
            'visualizacion': 'Tarjeta o Medidor'
        })
        
        if analisis['fechas']:
            sugerencias.append({
                'nombre': f'KPI: Crecimiento de {num_col} (MoM)',
                'objetivo': f'Medir la variación porcentual de `{num_col}` respecto al mes anterior (Month-over-Month).',
                'dax_base': f'DIVIDE([Total {num_col}] - [{num_col} Mes Anterior], [{num_col} Mes Anterior], 0)',
                'tipo': 'Rendimiento y Crecimiento',
                'visualizacion': 'Flechas Condicionales o Gráfico de Área'
            })

    if len(analisis['numericas']) >= 2:
        num_col_1 = analisis['numericas'][0]
        num_col_2 = analisis['numericas'][1]
        
        sugerencias.append({
            'nombre': f'KPI: Ratio de {num_col_1} vs {num_col_2}',
            'objetivo': f'Medir la eficiencia o relación entre `{num_col_1}` y `{num_col_2}` (Ej: Ingreso/Costo).',
            'dax_base': f'DIVIDE([Total {num_col_1}], [Total {num_col_2}], 0)',
            'tipo': 'Eficiencia/Razón',
            'visualizacion': 'Tarjeta o Gráfico de Dispersión'
        })
        
    if analisis['categoricas'] and analisis['numericas']:
        num_col = analisis['numericas'][0]
        cat_col = analisis['categoricas'][0]
        
        sugerencias.append({
            'nombre': f'OKR: Top {cat_col} Contribuyentes',
            'objetivo': f'Identificar y aumentar el porcentaje de `{num_col}` aportado por el Top 5 de `{cat_col}`.',
            'dax_base': f'DIVIDE([{num_col} Top 5 {cat_col}], [Total {num_col}], 0)',
            'tipo': 'Foco Estratégico',
            'visualizacion': 'Gráfico de Barras con Pareto'
        })

    return sugerencias

# FUNCIÓN: Recomendar Gráficas
def recomendar_graficas(analisis):
    recomendaciones = []
    
    if analisis['fechas'] and analisis['numericas']:
        recomendaciones.append({
            'tipo': 'Gráfico de Líneas',
            'uso': f'Tendencia temporal de {analisis["numericas"][0]} a lo largo del tiempo (KPIs de crecimiento)',
            'columnas': [analisis['fechas'][0], analisis['numericas'][0]],
            'icono': '📈'
        })
        
    if analisis['categoricas'] and analisis['numericas']:
        recomendaciones.append({
            'tipo': 'Gráfico de Cascada (Waterfall)',
            'uso': 'Mostrar la contribución o descomposición de una métrica por categoría o estado (ideal para demostrar el impacto en un OKR).',
            'columnas': [analisis['categoricas'][0], analisis['numericas'][0]],
            'icono': '🌊'
        })
        recomendaciones.append({
            'tipo': 'Gráfico de Barras/Columnas',
            'uso': f'Comparar {analisis["numericas"][0]} por {analisis["categoricas"][0]}',
            'columnas': [analisis['categoricas'][0], analisis['numericas'][0]],
            'icono': '📊'
        })
        
    if len(analisis['numericas']) >= 2:
        recomendaciones.append({
            'tipo': 'Gráfico de Dispersión',
            'uso': f'Analizar correlación entre {analisis["numericas"][0]} y {analisis["numericas"][1]} (KPIs de Eficiencia)',
            'columnas': analisis["numericas"][:2],
            'icono': '📊'
        })

    if analisis['numericas']:
        recomendaciones.append({
            'tipo': 'Tarjeta de KPI con Tendencia',
            'uso': f'Visualizar métrica clave ({analisis["numericas"][0]}) con comparación de período anterior (MoM o YoY)',
            'columnas': [analisis['numericas'][0]],
            'icono': '🎯'
        })
        recomendaciones.append({
            'tipo': 'Gráfico de Medidor (Gauge)',
            'uso': f'Visualizar progreso de {analisis["numericas"][0]} hacia una meta (Objetivos)',
            'columnas': [analisis['numericas'][0]],
            'icono': '🎚️'
        })

    return recomendaciones


# --- UI Principal ---
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
                        analisis = analizar_estructura(df) 
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
        imagen_cargada = st.file_uploader("Sube imagen de tabla o modelo", type=['png', 'jpg', 'jpeg']) 
        
        if imagen_cargada:
            # CORRECCIÓN DE ERROR: Usar st.stop() en lugar de return
            try:
                img = Image.open(imagen_cargada)
                st.image(img, caption="Imagen cargada", use_container_width=True)
            except Exception as e:
                st.error(f"Error al procesar la imagen: {e}")
                st.stop() # <-- SOLUCION AL SYNTAXERROR

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

# Footer
st.markdown("---")
st.markdown("💡 **Tip:** Ajusta las medidas según tu modelo de datos y relaciones en Power BI")
