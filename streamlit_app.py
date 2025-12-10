import streamlit as st
import pandas as pd
import json
from io import BytesIO
import base64

st.set_page_config(page_title="Analizador DAX para Power BI", layout="wide")

st.title("🔍 Analizador DAX y Gráficas Power BI")
st.markdown("Sube imágenes de tablas o archivos Excel para obtener medidas DAX y recomendaciones de visualización")

# Función para analizar estructura de datos
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

# Función para generar medidas DAX
def generar_medidas_dax(analisis, nombre_tabla):
    medidas = []
    
    # Medidas básicas para columnas numéricas
    for col in analisis['numericas']:
        medidas.append({
            'nombre': f'Total {col}',
            'dax': f'Total {col} = SUM({nombre_tabla}[{col}])',
            'tipo': 'Agregación básica'
        })
        
        medidas.append({
            'nombre': f'Promedio {col}',
            'dax': f'Promedio {col} = AVERAGE({nombre_tabla}[{col}])',
            'tipo': 'Agregación básica'
        })
        
        medidas.append({
            'nombre': f'Max {col}',
            'dax': f'Max {col} = MAX({nombre_tabla}[{col}])',
            'tipo': 'Agregación básica'
        })
        
        medidas.append({
            'nombre': f'Min {col}',
            'dax': f'Min {col} = MIN({nombre_tabla}[{col}])',
            'tipo': 'Agregación básica'
        })
    
    # Medidas de conteo
    if analisis['categoricas']:
        medidas.append({
            'nombre': 'Conteo Total',
            'dax': f'Conteo Total = COUNTROWS({nombre_tabla})',
            'tipo': 'Conteo'
        })
        
        medidas.append({
            'nombre': 'Conteo Distinto',
            'dax': f'Conteo Distinto = DISTINCTCOUNT({nombre_tabla}[{analisis["categoricas"][0]}])',
            'tipo': 'Conteo'
        })
    
    # Medidas de tiempo si hay columnas de fecha
    if analisis['fechas']:
        fecha_col = analisis['fechas'][0]
        if analisis['numericas']:
            num_col = analisis['numericas'][0]
            
            medidas.append({
                'nombre': f'{num_col} YTD',
                'dax': f'{num_col} YTD = TOTALYTD(SUM({nombre_tabla}[{num_col}]), {nombre_tabla}[{fecha_col}])',
                'tipo': 'Inteligencia de tiempo'
            })
            
            medidas.append({
                'nombre': f'{num_col} Mes Anterior',
                'dax': f'{num_col} Mes Anterior = CALCULATE(SUM({nombre_tabla}[{num_col}]), PREVIOUSMONTH({nombre_tabla}[{fecha_col}]))',
                'tipo': 'Inteligencia de tiempo'
            })
            
            medidas.append({
                'nombre': f'Variación % {num_col}',
                'dax': f'''Variación % {num_col} = 
VAR CurrentValue = SUM({nombre_tabla}[{num_col}])
VAR PreviousValue = CALCULATE(SUM({nombre_tabla}[{num_col}]), PREVIOUSMONTH({nombre_tabla}[{fecha_col}]))
RETURN
DIVIDE(CurrentValue - PreviousValue, PreviousValue, 0)''',
                'tipo': 'Análisis comparativo'
            })
    
    return medidas

# Función para recomendar gráficas
def recomendar_graficas(analisis):
    recomendaciones = []
    
    # Gráficas basadas en tipos de datos
    if len(analisis['numericas']) >= 2:
        recomendaciones.append({
            'tipo': 'Gráfico de Dispersión',
            'uso': f'Analizar correlación entre {analisis["numericas"][0]} y {analisis["numericas"][1]}',
            'columnas': analisis['numericas'][:2]
        })
    
    if analisis['categoricas'] and analisis['numericas']:
        recomendaciones.append({
            'tipo': 'Gráfico de Barras/Columnas',
            'uso': f'Comparar {analisis["numericas"][0]} por {analisis["categoricas"][0]}',
            'columnas': [analisis['categoricas'][0], analisis['numericas'][0]]
        })
        
        if len(analisis['categoricas']) >= 2:
            recomendaciones.append({
                'tipo': 'Matriz/Tabla',
                'uso': f'Vista detallada de {analisis["categoricas"][0]} y {analisis["categoricas"][1]}',
                'columnas': analisis['categoricas'][:2] + analisis['numericas'][:1]
            })
    
    if analisis['fechas'] and analisis['numericas']:
        recomendaciones.append({
            'tipo': 'Gráfico de Líneas',
            'uso': f'Tendencia temporal de {analisis["numericas"][0]} a lo largo del tiempo',
            'columnas': [analisis['fechas'][0], analisis['numericas'][0]]
        })
        
        recomendaciones.append({
            'tipo': 'Gráfico de Área',
            'uso': 'Análisis acumulado en el tiempo',
            'columnas': [analisis['fechas'][0], analisis['numericas'][0]]
        })
    
    if len(analisis['numericas']) >= 1 and len(analisis['categoricas']) >= 1:
        recomendaciones.append({
            'tipo': 'Gráfico de Cascada',
            'uso': 'Mostrar contribución de cada categoría al total',
            'columnas': [analisis['categoricas'][0], analisis['numericas'][0]]
        })
        
        recomendaciones.append({
            'tipo': 'Gráfico de Embudo',
            'uso': 'Visualizar proceso secuencial o conversión',
            'columnas': [analisis['categoricas'][0], analisis['numericas'][0]]
        })
    
    if len(analisis['categoricas']) >= 1 and len(analisis['numericas']) >= 1:
        recomendaciones.append({
            'tipo': 'Tarjeta/KPI',
            'uso': f'Mostrar métrica principal: {analisis["numericas"][0]}',
            'columnas': [analisis['numericas'][0]]
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
                
                if st.button("🚀 Analizar y Generar DAX"):
                    analisis = analizar_estructura(df)
                    st.session_state['analisis'] = analisis
                    st.session_state['medidas'] = generar_medidas_dax(analisis, nombre_tabla)
                    st.session_state['graficas'] = recomendar_graficas(analisis)
                    st.session_state['nombre_tabla'] = nombre_tabla
                    
            except Exception as e:
                st.error(f"Error al cargar archivo: {str(e)}")
    
    else:
        st.info("📸 Próximamente: análisis de imágenes con Claude API")
        imagen = st.file_uploader("Sube imagen de tabla", type=['png', 'jpg', 'jpeg'])

with col2:
    st.subheader("📊 Resultados")
    
    if 'analisis' in st.session_state:
        analisis = st.session_state['analisis']
        
        st.markdown("### 📋 Estructura de Datos")
        
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Columnas Numéricas", len(analisis['numericas']))
        col_b.metric("Columnas Categóricas", len(analisis['categoricas']))
        col_c.metric("Columnas Fecha", len(analisis['fechas']))
        
        with st.expander("🔍 Detalle de columnas"):
            for col, tipo in analisis['tipos'].items():
                st.text(f"{col}: {tipo} | Nulos: {analisis['nulls'][col]}")

# Sección de Medidas DAX
if 'medidas' in st.session_state:
    st.markdown("---")
    st.markdown("## 📐 Medidas DAX Sugeridas")
    
    medidas = st.session_state['medidas']
    
    # Filtro por tipo
    tipos = list(set([m['tipo'] for m in medidas]))
    tipo_filtro = st.multiselect("Filtrar por tipo:", tipos, default=tipos)
    
    medidas_filtradas = [m for m in medidas if m['tipo'] in tipo_filtro]
    
    for i, medida in enumerate(medidas_filtradas):
        with st.expander(f"📊 {medida['nombre']} ({medida['tipo']})"):
            st.code(medida['dax'], language='dax')
            if st.button(f"📋 Copiar", key=f"copy_{i}"):
                st.success("✅ Copiado al portapapeles")

# Sección de Gráficas
if 'graficas' in st.session_state:
    st.markdown("---")
    st.markdown("## 📈 Gráficas Recomendadas")
    
    graficas = st.session_state['graficas']
    
    for grafica in graficas:
        with st.container():
            col_g1, col_g2 = st.columns([2, 3])
            
            with col_g1:
                st.markdown(f"### {grafica['tipo']}")
                st.markdown(f"**Uso:** {grafica['uso']}")
            
            with col_g2:
                st.markdown("**Columnas sugeridas:**")
                for col in grafica['columnas']:
                    st.markdown(f"- `{col}`")
            
            st.markdown("---")

# Footer
st.markdown("---")
st.markdown("💡 **Tip:** Ajusta las medidas según tu modelo de datos y relaciones en Power BI")
