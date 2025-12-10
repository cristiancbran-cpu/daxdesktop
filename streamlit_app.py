import streamlit as st
import pandas as pd
import json
import base64
from io import BytesIO
from PIL import Image
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

# Necesitamos la librería nativa de Google para la visión multimodal
from google import genai
from google.genai.errors import APIError

# --- Configuración de Streamlit ---
st.set_page_config(page_title="Analizador DAX y KPI con Visión para Power BI", layout="wide")
st.title("👁️ Analizador DAX y Gráficas Power BI (Visión)")
st.markdown("Sube imágenes de tablas o archivos Excel para obtener medidas DAX y recomendaciones de visualización. **¡Ahora con análisis de imágenes via Gemini!**")

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

# Configurar la clave para el resto del script
os.environ["GOOGLE_API_KEY"] = api_key
try:
    # Inicializar el cliente de la API nativa de Google para visión
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Error al inicializar el cliente de Gemini: {e}")
    st.stop()


# Función para convertir imagen a base64 (EXISTENTE)
def imagen_a_base64(imagen):
    buffered = BytesIO()
    imagen.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# FUNCIÓN MODIFICADA: Ahora usa Gemini Vision
def analizar_imagen_con_gemini(imagen_data):
    # Prompt de Instrucción para Gemini (Solicitando JSON)
    system_prompt = (
        "Eres un experto en Power BI y análisis de modelos de datos. Tu tarea es analizar la imagen "
        "que contiene una tabla, datos, o una vista del modelo de datos de Power BI. "
        "Devuelve **SOLO** un objeto JSON con la estructura exacta definida a continuación. "
        "Identifica los nombres de las columnas, su tipo lógico (numerico/categorico/fecha), "
        "y sugiere métricas clave basadas en el contexto de la tabla. "
        "No incluyas texto explicativo, solo el JSON puro."
    )
    
    # Estructura JSON que necesitamos
    json_structure = {
        "nombre_tabla": "nombre sugerido para la tabla",
        "columnas": [
            {"nombre": "nombre_columna", "tipo": "numerico/categorico/fecha", "descripcion": "breve descripción"},
            # ... más columnas
        ],
        "relaciones_posibles": ["descripción de posibles relaciones con otras tablas"],
        "metricas_clave": ["lista de métricas importantes identificadas"]
    }
    
    # Mensaje completo para Gemini
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=[
            "Analiza esta imagen y devuelve la información de la tabla usando el siguiente esquema JSON.",
            "Esquema JSON Requerido: " + json.dumps(json_structure, indent=2)
        ]),
        imagen_data # La imagen en el formato requerido por la API de Google
    ]

    try:
        # Usar gemini-2.5-flash (soporta multimodal y es más rápido)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=messages,
            config={'response_mime_type': 'application/json'} # Pedir respuesta en formato JSON
        )
        
        # El modelo responde con una cadena JSON que necesitamos parsear
        texto_limpio = response.text.strip()
        
        # El modelo puede devolver Markdown JSON (```json ... ```)
        if texto_limpio.startswith("```json"):
            texto_limpio = texto_limpio.split("```json")[1].strip()
        if texto_limpio.endswith("```"):
            texto_limpio = texto_limpio.split("```")[0].strip()

        return json.loads(texto_limpio)
        
    except APIError as e:
        return {"error": f"Error de API de Gemini: {e}. Revise la clave o el uso."}
    except Exception as e:
         return {"error": f"Error de procesamiento de JSON: {e}. Intente con una imagen más clara."}

# Función para analizar estructura de datos (EXISTENTE)
def analizar_estructura(df):
# ... (código analizar_estructura sin cambios) ...
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

# Función para convertir análisis de imagen a formato estándar (EXISTENTE)
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

# Función para generar medidas DAX (EXISTENTE)
def generar_medidas_dax(analisis, nombre_tabla):
    medidas = []
    # ... (Lógica DAX existente: Agregaciones, Tiempo, TopN, etc.) ...
    
    # Medidas básicas para columnas numéricas
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
        # ... (Min, Max) ...
    
    # Medidas de conteo
    if analisis['categoricas']:
        # ... (Conteo Total Filas, Conteo Distinto) ...
        medidas.append({
            'nombre': 'Conteo Total Filas',
            'dax': f'Conteo Total Filas = COUNTROWS({nombre_tabla})',
            'tipo': 'Conteo',
            'descripcion': 'Cuenta todas las filas de la tabla'
        })
        
    # Medidas de tiempo (YTD, MoM, YoY)
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

    # Medidas de Ranking/TopN
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

# Función NUEVA: Sugerir KPI/OKR (EXISTENTE)
def sugerir_kpi_okr(analisis, nombre_tabla):
    sugerencias = []
    
    if analisis['numericas']:
        num_col = analisis['numericas'][0]
        
        # Sugerencias de KPI basados en agregación
        sugerencias.append({
            'nombre': f'KPI: Tasa de {num_col}',
            'objetivo': f'Monitorear la suma promedio o total de `{num_col}` por entidad/tiempo.',
            'dax_base': f'SUM({nombre_tabla}[{num_col}])',
            'tipo': 'Monitoreo de Volumen',
            'visualizacion': 'Tarjeta o Medidor'
        })
        
        # Sugerencias de KPI basados en variación
        if analisis['fechas']:
            # ... (Crecimiento MoM) ...
            sugerencias.append({
                'nombre': f'KPI: Crecimiento de {num_col} (MoM)',
                'objetivo': f'Medir la variación porcentual de `{num_col}` respecto al mes anterior (Month-over-Month).',
                'dax_base': f'DIVIDE([Total {num_col}] - [{num_col} Mes Anterior], [{num_col} Mes Anterior], 0)',
                'tipo': 'Rendimiento y Crecimiento',
                'visualizacion': 'Flechas Condicionales o Gráfico de Área'
            })

    if len(analisis['numericas']) >= 2:
        # ... (Ratio de Eficiencia) ...
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
        # ... (OKR Top Contribuyentes) ...
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

# Función para recomendar gráficas (EXISTENTE)
def recomendar_graficas(analisis):
    recomendaciones = []
    
    if analisis['fechas'] and analisis['numericas']:
        # ... (Gráfico de Líneas) ...
        recomendaciones.append({
            'tipo': 'Gráfico de Líneas',
            'uso': f'Tendencia temporal de {analisis["numericas"][0]} a lo largo del tiempo (KPIs de crecimiento)',
            'columnas': [analisis['fechas'][0], analisis['numericas'][0]],
            'icono': '📈'
        })
        
    if analisis['categoricas'] and analisis['numericas']:
        # ... (Gráfico de Cascada/Barras) ...
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
        # ... (Gráfico de Dispersión) ...
        recomendaciones.append({
            'tipo': 'Gráfico de Dispersión',
            'uso': f'Analizar correlación entre {analisis["numericas"][0]} y {analisis["numericas"][1]} (KPIs de Eficiencia)',
            'columnas': analisis['numericas'][:2],
            'icono': '📊'
        })

    if analisis['numericas']:
         # ... (Tarjeta KPI / Medidor) ...
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

# UI Principal
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📤 Cargar Datos")
    
    # El usuario elige el tipo de entrada
    tipo_archivo = st.radio("Tipo de entrada:", ["Excel/CSV", "Imagen de tabla/Modelo"])
    
    if tipo_archivo == "Excel/CSV":
        archivo = st.file_uploader("Sube tu archivo", type=['xlsx', 'xls', 'csv'])
        
        if archivo:
            # ... (Lógica de procesamiento de DF existente) ...
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
                        analisis = analizar_estructura(df) # Análisis basado en Pandas
                        st.session_state['analisis'] = analisis
                        st.session_state['medidas'] = generar_medidas_dax(analisis, nombre_tabla)
                        st.session_state['graficas'] = recomendar_graficas(analisis)
                        st.session_state['kpi_okr'] = sugerir_kpi_okr(analisis, nombre_tabla)
                        st.session_state['nombre_tabla'] = nombre_tabla
                        st.rerun()
                
            except Exception as e:
                st.error(f"Error al cargar archivo: {str(e)}")
    
    else: # Lógica para IMAGEN
        st.info("📸 Sube una captura de tu tabla o de la vista del modelo en Power BI.")
        imagen = st.file_uploader("Sube imagen de tabla o modelo", type=['png', 'jpg', 'jpeg'])
        
        if imagen:
            img = Image.open(imagen)
            st.image(img, caption="Imagen cargada", use_container_width=True)
            
            nombre_tabla = st.text_input("Nombre de la tabla sugerido (si aplica):", "TablaImagen")
            
            if st.button("🔍 Analizar Imagen con Gemini"):
                with st.spinner("Analizando imagen y extrayendo estructura con Gemini Vision..."):
                    # Preparar la imagen para la API de Google
                    # La función client.models.generate_content acepta objetos PIL Image directamente.
                    
                    # Llamar a la función de análisis de Gemini
                    analisis_claude = analizar_imagen_con_gemini(img) 
                    
                    if 'error' in analisis_claude:
                        st.error(f"Error: {analisis_claude['error']}")
                    else:
                        # Convertir el JSON extraído por Gemini al formato de análisis local
                        analisis = convertir_analisis_imagen(analisis_claude)
                        
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

        # Mostrar información adicional si viene de imagen
        if 'relaciones' in analisis and analisis['relaciones']:
            with st.expander("🔗 Relaciones sugeridas (Extraído de Imagen)"):
                for rel in analisis['relaciones']:
                    st.markdown(f"- {rel}")
        
        if 'metricas_clave' in analisis and analisis['metricas_clave']:
            with st.expander("🎯 Métricas clave identificadas (Extraído de Imagen)"):
                for metrica in analisis['metricas_clave']:
                    st.markdown(f"- {metrica}")


# --- Secciones de Salida (KPI/DAX/Gráficas) (EXISTENTES) ---
if 'kpi_okr' in st.session_state:
    st.markdown("---")
    st.markdown("## 🎯 Sugerencias de KPI y OKR")
    
    for sugerencia in st.session_state['kpi_okr']:
        with st.expander(f"🏅 {sugerencia['nombre']} ({sugerencia['tipo']})"):
            st.markdown(f"**Objetivo/Enfoque:** {sugerencia['objetivo']}")
            st.markdown(f"**Medida DAX base:**")
            st.code(sugerencia['dax_base'], language='dax')
            st.markdown(f"**Visualización Clave:** {sugerencia['visualizacion']}")

if 'medidas' in st.session_state:
    st.markdown("---")
    st.markdown("## 📐 Medidas DAX Detalladas")
    
    # ... (Lógica de DAX existente, omitida por brevedad) ...
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

if 'graficas' in st.session_state:
    st.markdown("---")
    st.markdown("## 📈 Gráficas Recomendadas")
    
    # ... (Lógica de Gráficas existente, omitida por brevedad) ...
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
