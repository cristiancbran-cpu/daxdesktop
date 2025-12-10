
import React, { useState } from 'react';
import { Upload, FileSpreadsheet, Sparkles, Download, TrendingUp } from 'lucide-react';

export default function DAXAnalyzer() {
  const [inputType, setInputType] = useState('excel');
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [daxMeasures, setDaxMeasures] = useState([]);
  const [chartSuggestions, setChartSuggestions] = useState([]);
  const [tableName, setTableName] = useState('Datos');
  const [preview, setPreview] = useState(null);
  const [filterType, setFilterType] = useState('all');

  // Función para analizar Excel/CSV
  const analyzeExcelFile = (data) => {
    const lines = data.split('\n').filter(line => line.trim());
    if (lines.length === 0) return null;

    const headers = lines[0].split(/[,;\t]/).map(h => h.trim());
    const rows = lines.slice(1, 6).map(line => 
      line.split(/[,;\t]/).map(cell => cell.trim())
    );

    const analysis = {
      columnas: headers,
      tipos: {},
      numericas: [],
      categoricas: [],
      fechas: [],
      rows: rows
    };

    headers.forEach((header, idx) => {
      const sampleValues = rows.map(row => row[idx]).filter(v => v);
      const isNumeric = sampleValues.every(v => !isNaN(v) && v !== '');
      const isDate = sampleValues.some(v => /\d{4}-\d{2}-\d{2}|\d{2}\/\d{2}\/\d{4}/.test(v));

      if (isDate) {
        analysis.fechas.push(header);
        analysis.tipos[header] = 'fecha';
      } else if (isNumeric) {
        analysis.numericas.push(header);
        analysis.tipos[header] = 'numerico';
      } else {
        analysis.categoricas.push(header);
        analysis.tipos[header] = 'categorico';
      }
    });

    return analysis;
  };

  // Función para analizar imagen con Claude
  const analyzeImageWithClaude = async (base64Image) => {
    try {
      const response = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: "claude-sonnet-4-20250514",
          max_tokens: 2000,
          messages: [
            {
              role: "user",
              content: [
                {
                  type: "image",
                  source: {
                    type: "base64",
                    media_type: "image/jpeg",
                    data: base64Image
                  }
                },
                {
                  type: "text",
                  text: `Analiza esta imagen de tabla/datos y devuelve SOLO un JSON válido con esta estructura exacta (sin texto adicional, sin markdown):
{
  "nombre_tabla": "nombre descriptivo de la tabla",
  "columnas": [
    {"nombre": "nombre_columna", "tipo": "numerico/categorico/fecha", "descripcion": "breve descripción"}
  ],
  "relaciones_posibles": ["posibles relaciones con otras tablas"],
  "metricas_clave": ["métricas importantes identificadas"],
  "datos_ejemplo": [["valor1", "valor2"], ["valor3", "valor4"]]
}`
                }
              ]
            }
          ]
        })
      });

      const data = await response.json();
      let text = data.content[0].text.trim();
      
      // Limpiar markdown si existe
      text = text.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
      
      return JSON.parse(text);
    } catch (error) {
      console.error('Error al analizar imagen:', error);
      throw error;
    }
  };

  // Generar medidas DAX
  const generateDAXMeasures = (analysisData, table) => {
    const measures = [];

    // Medidas básicas numéricas
    analysisData.numericas?.forEach(col => {
      measures.push({
        nombre: `Total ${col}`,
        dax: `Total ${col} = SUM(${table}[${col}])`,
        tipo: 'Agregación básica',
        descripcion: `Suma total de ${col}`
      });

      measures.push({
        nombre: `Promedio ${col}`,
        dax: `Promedio ${col} = AVERAGE(${table}[${col}])`,
        tipo: 'Agregación básica',
        descripcion: `Promedio de ${col}`
      });

      measures.push({
        nombre: `Max ${col}`,
        dax: `Max ${col} = MAX(${table}[${col}])`,
        tipo: 'Agregación básica',
        descripcion: `Valor máximo de ${col}`
      });

      measures.push({
        nombre: `Min ${col}`,
        dax: `Min ${col} = MIN(${table}[${col}])`,
        tipo: 'Agregación básica',
        descripcion: `Valor mínimo de ${col}`
      });
    });

    // Medidas de conteo
    if (analysisData.categoricas?.length > 0) {
      measures.push({
        nombre: 'Conteo Total',
        dax: `Conteo Total = COUNTROWS(${table})`,
        tipo: 'Conteo',
        descripcion: 'Cuenta todas las filas'
      });

      measures.push({
        nombre: `Conteo Distinto ${analysisData.categoricas[0]}`,
        dax: `Conteo Distinto = DISTINCTCOUNT(${table}[${analysisData.categoricas[0]}])`,
        tipo: 'Conteo',
        descripcion: `Valores únicos de ${analysisData.categoricas[0]}`
      });
    }

    // Inteligencia de tiempo
    if (analysisData.fechas?.length > 0 && analysisData.numericas?.length > 0) {
      const dateCol = analysisData.fechas[0];
      const numCol = analysisData.numericas[0];

      measures.push({
        nombre: `${numCol} YTD`,
        dax: `${numCol} YTD = TOTALYTD(SUM(${table}[${numCol}]), ${table}[${dateCol}])`,
        tipo: 'Inteligencia de tiempo',
        descripcion: 'Acumulado del año hasta la fecha'
      });

      measures.push({
        nombre: `${numCol} Mes Anterior`,
        dax: `${numCol} Mes Anterior = CALCULATE(SUM(${table}[${numCol}]), PREVIOUSMONTH(${table}[${dateCol}]))`,
        tipo: 'Inteligencia de tiempo',
        descripcion: 'Valor del mes anterior'
      });

      measures.push({
        nombre: `Variación % ${numCol}`,
        dax: `Variación % ${numCol} = 
VAR Actual = SUM(${table}[${numCol}])
VAR Anterior = CALCULATE(SUM(${table}[${numCol}]), PREVIOUSMONTH(${table}[${dateCol}]))
RETURN DIVIDE(Actual - Anterior, Anterior, 0)`,
        tipo: 'Análisis comparativo',
        descripcion: 'Cambio porcentual vs mes anterior'
      });

      measures.push({
        nombre: `${numCol} Año Anterior`,
        dax: `${numCol} Año Anterior = CALCULATE(SUM(${table}[${numCol}]), SAMEPERIODLASTYEAR(${table}[${dateCol}]))`,
        tipo: 'Inteligencia de tiempo',
        descripcion: 'Mismo período año anterior'
      });
    }

    // Medidas avanzadas
    if (analysisData.numericas?.length >= 1 && analysisData.categoricas?.length >= 1) {
      const numCol = analysisData.numericas[0];
      const catCol = analysisData.categoricas[0];

      measures.push({
        nombre: `Top 5 ${catCol}`,
        dax: `Top 5 ${catCol} = 
CALCULATE(
    SUM(${table}[${numCol}]),
    TOPN(5, ALL(${table}[${catCol}]), SUM(${table}[${numCol}]))
)`,
        tipo: 'Filtrado avanzado',
        descripcion: `Total de los 5 principales ${catCol}`
      });

      measures.push({
        nombre: `% del Total ${numCol}`,
        dax: `% del Total = 
DIVIDE(
    SUM(${table}[${numCol}]),
    CALCULATE(SUM(${table}[${numCol}]), ALL(${table}))
)`,
        tipo: 'Análisis comparativo',
        descripcion: 'Porcentaje respecto al total'
      });
    }

    return measures;
  };

  // Generar sugerencias de gráficas
  const generateChartSuggestions = (analysisData) => {
    const suggestions = [];

    if (analysisData.numericas?.length >= 2) {
      suggestions.push({
        tipo: 'Gráfico de Dispersión',
        uso: `Analizar correlación entre ${analysisData.numericas[0]} y ${analysisData.numericas[1]}`,
        columnas: analysisData.numericas.slice(0, 2),
        icon: '📊'
      });
    }

    if (analysisData.categoricas?.length > 0 && analysisData.numericas?.length > 0) {
      suggestions.push({
        tipo: 'Gráfico de Barras/Columnas',
        uso: `Comparar ${analysisData.numericas[0]} por ${analysisData.categoricas[0]}`,
        columnas: [analysisData.categoricas[0], analysisData.numericas[0]],
        icon: '📊'
      });

      suggestions.push({
        tipo: 'Gráfico Circular/Dona',
        uso: `Distribución de ${analysisData.numericas[0]} por ${analysisData.categoricas[0]}`,
        columnas: [analysisData.categoricas[0], analysisData.numericas[0]],
        icon: '🍩'
      });
    }

    if (analysisData.fechas?.length > 0 && analysisData.numericas?.length > 0) {
      suggestions.push({
        tipo: 'Gráfico de Líneas',
        uso: `Tendencia temporal de ${analysisData.numericas[0]}`,
        columnas: [analysisData.fechas[0], analysisData.numericas[0]],
        icon: '📈'
      });

      suggestions.push({
        tipo: 'Gráfico de Área',
        uso: 'Análisis acumulado en el tiempo',
        columnas: [analysisData.fechas[0], analysisData.numericas[0]],
        icon: '📉'
      });
    }

    if (analysisData.categoricas?.length >= 2) {
      suggestions.push({
        tipo: 'Matriz/Tabla',
        uso: `Vista detallada cruzando ${analysisData.categoricas[0]} y ${analysisData.categoricas[1]}`,
        columnas: [...analysisData.categoricas.slice(0, 2), ...(analysisData.numericas?.slice(0, 1) || [])],
        icon: '📋'
      });
    }

    suggestions.push({
      tipo: 'Tarjeta/KPI',
      uso: `Mostrar métrica principal`,
      columnas: analysisData.numericas?.slice(0, 1) || [],
      icon: '🎯'
    });

    suggestions.push({
      tipo: 'Gráfico de Cascada',
      uso: 'Mostrar contribución incremental',
      columnas: [...(analysisData.categoricas?.slice(0, 1) || []), ...(analysisData.numericas?.slice(0, 1) || [])],
      icon: '🌊'
    });

    return suggestions;
  };

  // Manejar carga de archivo
  const handleFileUpload = async (e) => {
    const uploadedFile = e.target.files[0];
    if (!uploadedFile) return;

    setFile(uploadedFile);
    setLoading(true);

    try {
      if (inputType === 'excel') {
        const text = await uploadedFile.text();
        const analysisResult = analyzeExcelFile(text);
        
        if (analysisResult) {
          setAnalysis(analysisResult);
          setPreview(analysisResult.rows);
          const measures = generateDAXMeasures(analysisResult, tableName);
          const charts = generateChartSuggestions(analysisResult);
          setDaxMeasures(measures);
          setChartSuggestions(charts);
        }
      } else {
        // Análisis de imagen
        const reader = new FileReader();
        reader.onload = async (event) => {
          const base64 = event.target.result.split(',')[1];
          setPreview(event.target.result);
          
          try {
            const claudeAnalysis = await analyzeImageWithClaude(base64);
            
            const convertedAnalysis = {
              columnas: claudeAnalysis.columnas?.map(c => c.nombre) || [],
              tipos: {},
              numericas: claudeAnalysis.columnas?.filter(c => c.tipo === 'numerico').map(c => c.nombre) || [],
              categoricas: claudeAnalysis.columnas?.filter(c => c.tipo === 'categorico').map(c => c.nombre) || [],
              fechas: claudeAnalysis.columnas?.filter(c => c.tipo === 'fecha').map(c => c.nombre) || [],
              nombre_tabla: claudeAnalysis.nombre_tabla,
              relaciones: claudeAnalysis.relaciones_posibles || [],
              metricas_clave: claudeAnalysis.metricas_clave || [],
              columnas_detalle: claudeAnalysis.columnas || []
            };

            claudeAnalysis.columnas?.forEach(c => {
              convertedAnalysis.tipos[c.nombre] = c.tipo;
            });

            setAnalysis(convertedAnalysis);
            const measures = generateDAXMeasures(convertedAnalysis, tableName);
            const charts = generateChartSuggestions(convertedAnalysis);
            setDaxMeasures(measures);
            setChartSuggestions(charts);
          } catch (error) {
            alert('Error al analizar imagen: ' + error.message);
          }
        };
        reader.readAsDataURL(uploadedFile);
      }
    } catch (error) {
      alert('Error al procesar archivo: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  // Descargar medidas DAX
  const downloadDAX = () => {
    const content = daxMeasures
      .map(m => `// ${m.nombre}\n// ${m.descripcion}\n${m.dax}\n`)
      .join('\n');
    
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `medidas_dax_${tableName}.txt`;
    a.click();
  };

  const measureTypes = [...new Set(daxMeasures.map(m => m.tipo))];
  const filteredMeasures = filterType === 'all' 
    ? daxMeasures 
    : daxMeasures.filter(m => m.tipo === filterType);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-800 mb-2 flex items-center justify-center gap-3">
            <Sparkles className="text-yellow-500" size={36} />
            Analizador DAX con IA
          </h1>
          <p className="text-gray-600">Genera medidas DAX y sugerencias de gráficas para Power BI</p>
        </div>

        {/* Upload Section */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <div className="flex gap-4 mb-4">
            <button
              onClick={() => setInputType('excel')}
              className={`flex-1 py-3 px-4 rounded-lg font-medium transition-all ${
                inputType === 'excel'
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <FileSpreadsheet className="inline mr-2" size={20} />
              Excel/CSV
            </button>
            <button
              onClick={() => setInputType('image')}
              className={`flex-1 py-3 px-4 rounded-lg font-medium transition-all ${
                inputType === 'image'
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              🖼️ Imagen de Tabla
            </button>
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Nombre de la tabla en Power BI:
            </label>
            <input
              type="text"
              value={tableName}
              onChange={(e) => setTableName(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Ej: Ventas, Clientes, Productos..."
            />
          </div>

          <label className="block w-full cursor-pointer">
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-500 transition-colors">
              <Upload className="mx-auto mb-3 text-gray-400" size={48} />
              <p className="text-gray-600 font-medium mb-1">
                {inputType === 'excel' ? 'Arrastra un archivo Excel/CSV' : 'Arrastra una imagen de tabla'}
              </p>
              <p className="text-sm text-gray-500">
                o haz clic para seleccionar
              </p>
              <input
                type="file"
                onChange={handleFileUpload}
                accept={inputType === 'excel' ? '.csv,.xlsx,.xls' : 'image/*'}
                className="hidden"
              />
            </div>
          </label>

          {loading && (
            <div className="mt-4 text-center">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <p className="text-gray-600 mt-2">Analizando datos con IA...</p>
            </div>
          )}
        </div>

        {/* Preview */}
        {preview && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <h2 className="text-xl font-bold text-gray-800 mb-4">Vista Previa</h2>
            {inputType === 'excel' ? (
              <div className="overflow-x-auto">
                <table className="min-w-full border-collapse border border-gray-300">
                  <thead>
                    <tr className="bg-gray-100">
                      {analysis?.columnas.map((col, idx) => (
                        <th key={idx} className="border border-gray-300 px-4 py-2 text-left font-semibold">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.map((row, ridx) => (
                      <tr key={ridx} className="hover:bg-gray-50">
                        {row.map((cell, cidx) => (
                          <td key={cidx} className="border border-gray-300 px-4 py-2">
                            {cell}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <img src={preview} alt="Preview" className="max-w-full h-auto rounded-lg shadow" />
            )}
          </div>
        )}

        {/* Analysis Results */}
        {analysis && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <h2 className="text-xl font-bold text-gray-800 mb-4">📋 Estructura de Datos</h2>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="bg-blue-50 p-4 rounded-lg text-center">
                <p className="text-2xl font-bold text-blue-600">{analysis.numericas?.length || 0}</p>
                <p className="text-sm text-gray-600">Columnas Numéricas</p>
              </div>
              <div className="bg-green-50 p-4 rounded-lg text-center">
                <p className="text-2xl font-bold text-green-600">{analysis.categoricas?.length || 0}</p>
                <p className="text-sm text-gray-600">Columnas Categóricas</p>
              </div>
              <div className="bg-purple-50 p-4 rounded-lg text-center">
                <p className="text-2xl font-bold text-purple-600">{analysis.fechas?.length || 0}</p>
                <p className="text-sm text-gray-600">Columnas Fecha</p>
              </div>
            </div>

            <div className="space-y-2">
              {analysis.columnas_detalle?.map((col, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                  <div>
                    <span className="font-semibold text-gray-800">{col.nombre}</span>
                    <span className="ml-3 text-sm text-gray-500">{col.tipo}</span>
                  </div>
                  {col.descripcion && (
                    <span className="text-sm text-gray-600">{col.descripcion}</span>
                  )}
                </div>
              ))}
            </div>

            {analysis.relaciones?.length > 0 && (
              <div className="mt-4 p-4 bg-yellow-50 rounded-lg">
                <h3 className="font-semibold text-gray-800 mb-2">🔗 Relaciones Sugeridas:</h3>
                <ul className="list-disc list-inside space-y-1">
                  {analysis.relaciones.map((rel, idx) => (
                    <li key={idx} className="text-sm text-gray-700">{rel}</li>
                  ))}
                </ul>
              </div>
            )}

            {analysis.metricas_clave?.length > 0 && (
              <div className="mt-4 p-4 bg-green-50 rounded-lg">
                <h3 className="font-semibold text-gray-800 mb-2">🎯 Métricas Clave:</h3>
                <ul className="list-disc list-inside space-y-1">
                  {analysis.metricas_clave.map((metrica, idx) => (
                    <li key={idx} className="text-sm text-gray-700">{metrica}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* DAX Measures */}
        {daxMeasures.length > 0 && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-gray-800">📐 Medidas DAX Sugeridas</h2>
              <button
                onClick={downloadDAX}
                className="flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors"
              >
                <Download size={20} />
                Descargar DAX
              </button>
            </div>

            <div className="flex gap-2 mb-4 flex-wrap">
              <button
                onClick={() => setFilterType('all')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  filterType === 'all'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                Todas ({daxMeasures.length})
              </button>
              {measureTypes.map(type => (
                <button
                  key={type}
                  onClick={() => setFilterType(type)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    filterType === type
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {type}
                </button>
              ))}
            </div>

            <div className="space-y-3">
              {filteredMeasures.map((measure, idx) => (
                <details key={idx} className="bg-gray-50 rounded-lg p-4 cursor-pointer hover:bg-gray-100 transition-colors">
                  <summary className="font-semibold text-gray-800 flex justify-between items-center">
                    <span>📊 {measure.nombre}</span>
                    <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                      {measure.tipo}
                    </span>
                  </summary>
                  <div className="mt-3">
                    <p className="text-sm text-gray-600 mb-2">{measure.descripcion}</p>
                    <pre className="bg-gray-900 text-green-400 p-4 rounded-lg overflow-x-auto text-sm">
                      {measure.dax}
                    </pre>
                  </div>
                </details>
              ))}
            </div>
          </div>
        )}

        {/* Chart Suggestions */}
        {chartSuggestions.length > 0 && (
          <div className="bg-white rounded-lg shadow-lg p-6">
            <h2 className="text-xl font-bold text-gray-800 mb-4">📈 Gráficas Recomendadas</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {chartSuggestions.map((chart, idx) => (
                <div key={idx} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                  <h3 className="font-semibold text-gray-800 mb-2">
                    {chart.icon} {chart.tipo}
                  </h3>
                  <p className="text-sm text-gray-600 mb-3">{chart.uso}</p>
                  <div className="bg-blue-50 p-2 rounded">
                    <p className="text-xs font-medium text-gray-700 mb-1">Columnas sugeridas:</p>
                    <div className="flex flex-wrap gap-1">
                      {chart.columnas.map((col, cidx) => (
                        <span key={cidx} className="bg-blue-200 text-blue-800 text-xs px-2 py-1 rounded">
                          {col}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="mt-8 text-center text-gray-600 text-sm">
          <p>💡 Ajusta las medidas según tu modelo de datos en Power BI</p>
          <p className="mt-1">✨ Análisis de imágenes potenciado por Claude AI</p>
        </div>
      </div>
    </div>
  );
}
