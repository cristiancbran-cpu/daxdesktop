import streamlit as st
import pandas as pd
import json
from io import BytesIO
import base64
from PIL import Image

st.set_page_config(page_title="Analizador DAX para Power BI", layout="wide")

st.title("🔍 Analizador DAX y Gráficas Power BI")
st.markdown("Sube imágenes de tablas o archivos Excel para obtener medidas DAX y recomendaciones de visualización")

# Función para convertir imagen a base64
def imagen_a_base64(imagen):
    buffered = BytesIO()
    imagen.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# Función para analizar imagen con Claude API
async def analizar_imagen_con_claude(imagen_base64):
    try:
        response = await fetch("https://api.anthropic.com/v1/messages", {
            "method": "POST",
            "headers": {
                "Content-Type": "application/json",
            },
            "body": json.dumps({
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": imagen_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": """Analiza esta tabla/datos y devuelve SOLO un JSON con esta estructura exacta:
{
  "nombre_tabla": "nombre sugerido para la tabla",
  "columnas": [
    {"nombre": "nombre_columna", "tipo": "numerico/categorico/fecha", "descripcion": "breve descripción"}
  ],
  "relaciones_posibles": ["descripción de posibles relaciones con otras tablas"],
  "metricas_clave": ["lista de métricas importantes identificadas"]
}

No incluyas texto adicional, solo el JSON."""
                            }
                        ]
                    }
                ]
            })
        })
        
        data = await response.json()
        texto = data.content[0].text
        
        # Limpiar respuesta y extraer JSON
        texto_limpio = texto.strip()
        if texto_limpio.startswith("```json"):
            texto_limpio = texto_limpio[7:]
        if texto_limpio.endswith("```"):
            texto_limpio = texto_limpio[:-3]
        texto_limpio = texto_limpio.strip()
        
        return json.loads(texto_limpio)
        
    except Exception as e:
        return {"error": str(e)}

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

# Función para convertir análisis de imagen a formato estándar
def convertir_analisis_imagen(analisis_claude):
    analisis = {
        'columnas': [],
        'tipos': {},
        'numericas': [],
        'categoricas': [],
        'fechas': [],
        'nulls': {},
        'nombre_tabla': analisis_claude.get('nombre_tabla', 'Tabla'),
        'relaciones': analisis_claude.get('relaciones_posibles', []),
        'metricas_clave': analisis_claude.get('metricas_clave', [])
    }
    
    for col_info in analisis_claude.get('columnas', []):
        nombre = col_info['nombre']
        tipo = col_info['tipo']
        
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

# Función para generar medidas DAX
def generar_medidas_dax(analisis, nombre_tabla):
    medidas = []
    
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
        
        medidas.append({
            'nombre': f'Max {col}',
            'dax': f'Max {col} = MAX({nombre_tabla}[{col}])',
            'tipo': 'Agregación básica',
            'descripcion': f'Valor máximo de {col}'
        })
        
        medidas.append({
            'nombre': f'Min {col}',
            'dax': f'Min {col} = MIN({nombre_tabla}[{col}])',
            'tipo': 'Agregación básica',
            'descripcion': f'Valor mínimo de {col}'
        })
    
    # Medidas de conteo
    if analisis['categoricas']:
        medidas.append({
            'nombre': 'Conteo Total',
            'dax': f'Conteo Total = COUNTROWS({nombre_tabla})',
            'tipo': 'Conteo',
            'descripcion': 'Cuenta todas las filas de la tabla'
        })
        
        medidas.append({
            'nombre': f'Conteo Distinto {analisis["categoricas"][0]}',
            'dax': f'Conteo Distinto = DISTINCTCOUNT({nombre_tabla}[{analisis["categoricas"][0]}])',
            'tipo': 'Conteo',
            'descripcion': f'Cuenta valores únicos de {analisis["categoricas"][0]}'
        })
    
    # Medidas de tiempo si hay columnas de fecha
    if analisis['fechas']:
        fecha_col = analisis['fechas'][0]
        if analisis['numericas']:
            num_col = analisis['numericas'][0]
            
            medidas.append({
                'nombre': f'{num_col} YTD',
                'dax': f'{num_col} YTD = TOTALYTD(SUM({nombre_tabla}[{num_col}]), {nombre_tabla}[{fecha_col}])',
                'tipo': 'Inteligencia de tiempo',
                'descripcion': f'Acumulado del año hasta la fecha para {num_col}'
            })
            
            medidas.append({
                'nombre': f'{num_col} Mes Anterior',
                'dax': f'{num_col} Mes Anterior = CALCULATE(SUM({nombre_tabla}[{num_col}]), PREVIOUSMONTH({nombre_tabla}[{fecha_col}]))',
                'tipo': 'Inteligencia de tiempo',
                'descripcion': f'Valor de {num_col} en el mes anterior'
            })
            
            medidas.append({
                'nombre': f'Variación % {num_col}',
                'dax': f'''Variación % {num_col} = 
VAR CurrentValue = SUM({nombre_tabla}[{num_col}])
VAR PreviousValue = CALCULATE(SUM({nombre_tabla}[{num_col}]), PREVIOUSMONTH({nombre_tabla}[{fecha_col}]))
RETURN
DIVIDE(CurrentValue - PreviousValue, PreviousValue, 0)''',
                'tipo': 'Análisis comparativo',
                'descripcion': f'Cambio porcentual vs mes anterior'
            })
            
            medidas.append({
                'nombre': f'{num_col} Año Anterior',
                'dax': f'{num_col} Año Anterior = CALCULATE(SUM({nombre_tabla}[{num_col}]), SAMEPERIODLASTYEAR({nombre_tabla}[{fecha_col}]))',
                'tipo': 'Inteligencia de tiempo',
                'descripcion': f'Valor de {num_col} en el mismo período del año anterior'
            })
    
    # Medidas avanzadas con filtros
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

# Función para recomendar gráficas
def recomendar_graficas(analisis):
    recomendaciones = []
    
    # Gráficas basadas en tipos de datos
    if len(analisis['numericas']) >= 2:
        recomendaciones.append({
            'tipo': 'Gráfico de Dispersión',
            'uso': f'Analizar correlación entre {analisis["numericas"][0]} y {analisis["numericas"][1]}',
            'columnas': analisis['numericas'][:2],
            'icono': '📊'
        })
    
    if analisis['categoricas'] and analisis['numericas']:
        recomendaciones.append({
            'tipo': 'Gráfico de Barras/Columnas',
            'uso': f'Comparar {analisis["numericas"][0]} por {analisis["categoricas"][0]}',
            'columnas': [analisis['categoricas'][0], analisis['numericas'][0]],
            'icono': '📊'
        })
        
        if len(analisis['categoricas']) >= 2:
            recomendaciones.append({
                'tipo': 'Matriz/Tabla',
                'uso': f'Vista detallada de {analisis["categoricas"][0]} y {analisis["categoricas"][1]}',
                'columnas': analisis['categoricas'][:2] + analisis['numericas'][:1],
                'icono': '📋'
            })
    
    if analisis['fechas'] and analisis['numericas']:
        recomendaciones.append({
            'tipo': 'Gráfico de Líneas',
            'uso': f'Tendencia temporal de {analisis["numericas"][0]} a lo largo del tiempo',
            'columnas': [analisis['fechas'][0], analisis['numericas'][0]],
            'icono': '📈'
        })
        
        recomendaciones.append({
            'tipo': 'Gráfico de Área',
            'uso': 'Análisis acumulado en el tiempo',
            'columnas': [analisis['fechas'][0], analisis['numericas'][0]],
            'icono': '📉'
        })
    
    if len(analisis['numericas']) >= 1 and len(analisis['categoricas']) >= 1:
        recomendaciones.append({
            'tipo': 'Gráfico de Cascada',
            'uso': 'Mostrar contribución de cada categoría al total',
            'columnas': [analisis['categoricas'][0], analisis['numericas'][0]],
            'icono': '🌊'
        })
        
        recomendaciones.append({
            'tipo': 'Gráfico de Embudo',
            'uso': 'Visualizar proceso secuencial o conversión',
            'columnas': [analisis['categoricas'][0], analisis['numericas'][0]],
            'icono': '🔻'
        })
    
    if len(analisis['categoricas']) >= 1 and len(analisis['numericas']) >= 1:
        recomendaciones.append({
            'tipo': 'Tarjeta/KPI',
            'uso': f'Mostrar métrica principal: {analisis["numericas"][0]}',
            'columnas': [analisis['numericas'][0]],
            'icono': '🎯'
        })
        
        recomendaciones.append({
            'tipo': 'Medidor',
            'uso': f'Visualizar progreso de {analisis["numericas"][0]} hacia meta',
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
                
                if st.button("🚀 Analizar y Generar DAX"):
                    with st.spinner("Analizando datos..."):
                        analisis = analizar_estructura(df)
                        st.session_state['analisis'] = analisis
                        st.session_state['medidas'] = generar_medidas_dax(analisis, nombre_tabla)
                        st.session_state['graficas'] = recomendar_graficas(analisis)
                        st.session_state['nombre_tabla'] = nombre_tabla
                        st.rerun()
                    
            except Exception as e:
                st.error(f"Error al cargar archivo: {str(e)}")
    
    else:
        st.info("📸 Sube una imagen de tu tabla de datos")
        imagen = st.file_uploader("Sube imagen de tabla", type=['png', 'jpg', 'jpeg'])
        
        if imagen:
            img = Image.open(imagen)
            st.image(img, caption="Imagen cargada", use_container_width=True)
            
            nombre_tabla = st.text_input("Nombre de la tabla en Power BI:", "Tabla")
            
            if st.button("🔍 Analizar Imagen con IA"):
                with st.spinner("Analizando imagen con Claude..."):
                    # Convertir imagen a base64
                    img_base64 = imagen_a_base64(img)
                    
                    # Nota: En Streamlit necesitas usar asyncio
                    st.warning("⚠️ Para usar análisis de imágenes, necesitas ejecutar esto en un artifact React o implementar la llamada asíncrona correctamente")
                    st.info("💡 Por ahora, copia manualmente los datos de la imagen a un Excel")

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
            for col in analisis['columnas']:
                tipo_col = analisis['tipos'].get(col, 'N/A')
                nulls = analisis['nulls'].get(col, 0)
                st.text(f"{col}: {tipo_col} | Nulos: {nulls}")
        
        # Mostrar información adicional si viene de imagen
        if 'relaciones' in analisis and analisis['relaciones']:
            with st.expander("🔗 Relaciones sugeridas"):
                for rel in analisis['relaciones']:
                    st.markdown(f"- {rel}")
        
        if 'metricas_clave' in analisis and analisis['metricas_clave']:
            with st.expander("🎯 Métricas clave identificadas"):
                for metrica in analisis['metricas_clave']:
                    st.markdown(f"- {metrica}")

# Sección de Medidas DAX
if 'medidas' in st.session_state:
    st.markdown("---")
    st.markdown("## 📐 Medidas DAX Sugeridas")
    
    medidas = st.session_state['medidas']
    
    # Filtro por tipo
    tipos = list(set([m['tipo'] for m in medidas]))
    tipo_filtro = st.multiselect("Filtrar por tipo:", tipos, default=tipos)
    
    medidas_filtradas = [m for m in medidas if m['tipo'] in tipo_filtro]
    
    # Botón para descargar todas las medidas
    if st.button("📥 Descargar todas las medidas DAX"):
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

# Sección de Gráficas
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
st.markdown("🔧 **Nota:** Para análisis completo de imágenes, usa la versión con artifact React")
