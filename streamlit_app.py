import streamlit as st
import pandas as pd
import json
from io import BytesIO
import base64
from PIL import Image

# Importación dummy para simular el uso de Gemini si fuera necesario para funciones futuras
# from langchain_google_genai import ChatGoogleGenerativeAI 

st.set_page_config(page_title="Analizador DAX y KPI para Power BI", layout="wide")

st.title("🔍 Analizador DAX y Recomendaciones de KPI/OKR")
st.markdown("Sube archivos Excel/CSV para obtener medidas DAX, sugerencias de KPI y recomendaciones de visualización")

# Función para convertir imagen a base64 (Mantenida por si deseas integrar Gemini Vision más adelante)
def imagen_a_base64(imagen):
    buffered = BytesIO()
    imagen.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# Función para analizar imagen con Claude API (Mantenida pero inactiva)
# async def analizar_imagen_con_claude(imagen_base64):
# ... (código Claude API original, dejado fuera por brevedad)

# Función para analizar estructura de datos (EXISTENTE)
def analizar_estructura(df):
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

# Función para generar medidas DAX (EXTENDIDA)
def generar_medidas_dax(analisis, nombre_tabla):
    medidas = []
    
    # --- Medidas básicas (existentes) ---
    for col in analisis['numericas']:
        medidas.append({
            'nombre': f'Total {col}',
            'dax': f'Total {col} = SUM({nombre_tabla}[{col}])',
            'tipo': 'Agregación básica',
            'descripcion': f'Suma total de {col}'
        })
    # ... (Otras agregaciones básicas: Promedio, Max, Min, Conteo) ...
    
    # --- Medidas de conteo (existentes) ---
    if analisis['categoricas']:
        medidas.append({
            'nombre': 'Conteo Total Filas',
            'dax': f'Conteo Total Filas = COUNTROWS({nombre_tabla})',
            'tipo': 'Conteo',
            'descripcion': 'Cuenta todas las filas de la tabla'
        })
        if analisis['categoricas']:
             medidas.append({
                'nombre': f'Conteo Distinto {analisis["categoricas"][0]}',
                'dax': f'Conteo Distinto = DISTINCTCOUNT({nombre_tabla}[{analisis["categoricas"][0]}])',
                'tipo': 'Conteo',
                'descripcion': f'Cuenta valores únicos de {analisis["categoricas"][0]}'
            })
    
    # --- Medidas de tiempo (existentes) ---
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
    
    # --- Medidas de Ranking/TopN (existentes) ---
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

# FUNCIÓN NUEVA: Sugerir KPI/OKR
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
            fecha_col = analisis['fechas'][0]
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
        
        # Sugerencias de KPI/Métricas de Razón
        sugerencias.append({
            'nombre': f'KPI: Ratio de {num_col_1} vs {num_col_2}',
            'objetivo': f'Medir la eficiencia o relación entre `{num_col_1}` y `{num_col_2}` (Ej: Ingreso/Costo).',
            'dax_base': f'DIVIDE([Total {num_col_1}], [Total {num_col_2}], 0)',
            'tipo': 'Eficiencia/Razón',
            'visualizacion': 'Tarjeta o Gráfico de Dispersión'
        })
        
    if analisis['categoricas'] and analisis['numericas']:
        cat_col = analisis['categoricas'][0]
        
        # Sugerencias de OKR (Objetivos y Resultados Clave)
        sugerencias.append({
            'nombre': f'OKR: Top {cat_col} Contribuyentes',
            'objetivo': f'Identificar y aumentar el porcentaje de `{num_col}` aportado por el Top 5 de `{cat_col}`.',
            'dax_base': f'DIVIDE([{num_col} Top 5 {cat_col}], [Total {num_col}], 0)',
            'tipo': 'Foco Estratégico',
            'visualizacion': 'Gráfico de Barras con Pareto'
        })

    return sugerencias

# Función para recomendar gráficas (EXTENDIDA)
def recomendar_graficas(analisis):
    recomendaciones = []
    
    # Gráficas basadas en tipos de datos (EXISTENTES)
    if analisis['fechas'] and analisis['numericas']:
        recomendaciones.append({
            'tipo': 'Gráfico de Líneas',
            'uso': f'Tendencia temporal de {analisis["numericas"][0]} a lo largo del tiempo (KPIs de crecimiento)',
            'columnas': [analisis['fechas'][0], analisis['numericas'][0]],
            'icono': '📈'
        })
        
    if analisis['categoricas'] and analisis['numericas']:
        # Gráfico de Cascada para mostrar la contribución positiva/negativa (Mejor para OKR)
        recomendaciones.append({
            'tipo': 'Gráfico de Cascada (Waterfall)',
            'uso': 'Mostrar la contribución o descomposición de una métrica por categoría o estado (ideal para demostrar el impacto en un OKR).',
            'columnas': [analisis['categoricas'][0], analisis['numericas'][0]],
            'icono': '🌊'
        })
        
        # Gráfico de Barras para comparación (EXISTENTE)
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
            'columnas': analisis['numericas'][:2],
            'icono': '📊'
        })

    # NUEVO: Gráficas enfocadas en KPI/OKR
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

# UI Principal
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📤 Cargar Datos")
    
    tipo_archivo = st.radio("Tipo de entrada:", ["Excel/CSV", "Imagen de tabla"])
    
    if tipo_archivo == "Excel/CSV":
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
                
                if st.button("🚀 Analizar y Generar Soluciones"):
                    with st.spinner("Analizando datos y generando sugerencias..."):
                        analisis = analizar_estructura(df)
                        st.session_state['analisis'] = analisis
                        st.session_state['medidas'] = generar_medidas_dax(analisis, nombre_tabla)
                        st.session_state['graficas'] = recomendar_graficas(analisis)
                        st.session_state['kpi_okr'] = sugerir_kpi_okr(analisis, nombre_tabla) # NUEVO
                        st.session_state['nombre_tabla'] = nombre_tabla
                        st.rerun()
                
            except Exception as e:
                st.error(f"Error al cargar archivo: {str(e)}")
    
    else:
        st.info("📸 Sube una imagen de tu tabla de datos")
        # Lógica de imagen...
        st.warning("⚠️ El análisis de imágenes está deshabilitado. Por favor, usa la carga de Excel/CSV.")


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

# --- Sección de KPI y OKR (NUEVA) ---
if 'kpi_okr' in st.session_state:
    st.markdown("---")
    st.markdown("## 🎯 Sugerencias de KPI y OKR")
    
    for sugerencia in st.session_state['kpi_okr']:
        with st.expander(f"🏅 {sugerencia['nombre']} ({sugerencia['tipo']})"):
            st.markdown(f"**Objetivo/Enfoque:** {sugerencia['objetivo']}")
            st.markdown(f"**Medida DAX base:**")
            st.code(sugerencia['dax_base'], language='dax')
            st.markdown(f"**Visualización Clave:** {sugerencia['visualizacion']}")

# --- Sección de Medidas DAX (EXISTENTE) ---
if 'medidas' in st.session_state:
    st.markdown("---")
    st.markdown("## 📐 Medidas DAX Detalladas")
    
    medidas = st.session_state['medidas']
    
    # ... (Filtro y Botón de Descarga) ...
    
    tipos = list(set([m['tipo'] for m in medidas]))
    tipo_filtro = st.multiselect("Filtrar por tipo:", tipos, default=tipos)
    
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

# --- Sección de Gráficas Recomendadas (EXISTENTE/EXTENDIDA) ---
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
st.markdown("🔧 **Nota:** El análisis de imágenes requiere una implementación de API externa.")
